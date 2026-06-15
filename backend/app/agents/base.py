"""Agent 基类 — 标准工具接口，与 MCP 范式对齐"""

from dataclasses import dataclass, field

import asyncio
import pandas as pd
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine


@dataclass
class ColumnInfo:
    name: str
    dtype: str
    nullable: bool
    is_primary_key: bool = False
    semantic_meaning: str | None = None


@dataclass
class TableSchema:
    name: str
    columns: list[ColumnInfo]
    row_count: int | None = None
    semantic_meaning: str | None = None


@dataclass
class SchemaSummary:
    tables: list[TableSchema]
    business_tag: str
    suggested_metrics: list[dict] = field(default_factory=list)


class DataSourceAgent:
    """每个数据源一个实例，暴露标准工具接口给 LLM"""

    def __init__(self, datasource_id: str, connection_url: str, business_tag: str):
        self.datasource_id = datasource_id
        self.connection_url = connection_url
        self.business_tag = business_tag
        self._engine: Engine | None = None
        self.schema_cache: dict | None = None
        self._rls_scope: dict | None = None  # V2: 行级安全范围

    def set_rls_scope(self, scope: dict | None):
        """V2: 设置行级安全范围，由 API 层在权限校验后注入"""
        self._rls_scope = scope

    @property
    def engine(self) -> Engine:
        if self._engine is None:
            connect_args = {"check_same_thread": False} if "sqlite" in self.connection_url else {}
            self._engine = create_engine(self.connection_url, connect_args=connect_args)
        return self._engine

    def list_tables(self) -> list[str]:
        """工具: 列出所有表名"""
        inspector = inspect(self.engine)
        return inspector.get_table_names()

    def describe_table(self, table_name: str) -> TableSchema:
        """工具: 获取单表的列级详情"""
        inspector = inspect(self.engine)
        cols = inspector.get_columns(table_name)
        pk_cols = inspector.get_pk_constraint(table_name).get("constrained_columns", [])
        columns = [
            ColumnInfo(
                name=c["name"], dtype=str(c["type"]),
                nullable=c.get("nullable", True),
                is_primary_key=(c["name"] in pk_cols),
            )
            for c in cols
        ]
        return TableSchema(name=table_name, columns=columns)

    def execute_sql(self, query: str, params: dict | None = None) -> pd.DataFrame:
        """工具: 执行只读 SQL 查询 (V2: 集成 RLS)

        Args:
            query: SQL 语句（仅允许 SELECT）
            params: 可选参数字典，用于参数化查询
        """
        stripped = query.strip().upper()
        if not stripped.startswith("SELECT"):
            raise ValueError("仅允许 SELECT 查询")

        # V2: 权限过滤注入
        if self._rls_scope and self._rls_scope.get("mode") == "filtered":
            from app.core.query_rewriter import QueryInterceptor
            interceptor = QueryInterceptor(self._rls_scope)
            query = interceptor.rewrite_sql(query)

        with self.engine.connect() as conn:
            return pd.read_sql(text(query), conn, params=params or {})

    async def execute_sql_async(self, query: str, params: dict | None = None) -> pd.DataFrame:
        """异步包装 — 在 async 路由中调用以避免阻塞事件循环"""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.execute_sql, query, params)

    def probe_raw_schema(self) -> SchemaSummary:
        """完整探测所有表结构（不含语义推断）"""
        table_names = self.list_tables()
        tables = []
        for t in table_names:
            schema = self.describe_table(t)
            try:
                df = self.execute_sql(f"SELECT COUNT(*) as cnt FROM [{t}]" if "sqlite" in self.connection_url else f"SELECT COUNT(*) as cnt FROM {t}")
                row_count = int(df["cnt"].iloc[0]) if not df.empty else None
            except Exception:
                row_count = None
            schema.row_count = row_count
            schema.semantic_meaning = None
            tables.append(schema)
        return SchemaSummary(tables=tables, business_tag=self.business_tag)

    def dispose(self):
        if self._engine is not None:
            self._engine.dispose()
            self._engine = None
