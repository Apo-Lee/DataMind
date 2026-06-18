"""Agent 基类 — 标准工具接口，与 MCP 范式对齐"""

from dataclasses import dataclass, field
import asyncio
import re

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
        self._rls_scope: dict | None = None

    def set_rls_scope(self, scope: dict | None):
        self._rls_scope = scope

    @property
    def engine(self) -> Engine:
        if self._engine is None:
            connect_args = {"check_same_thread": False} if "sqlite" in self.connection_url else {}
            self._engine = create_engine(self.connection_url, connect_args=connect_args)
        return self._engine

    def list_tables(self) -> list[str]:
        inspector = inspect(self.engine)
        return inspector.get_table_names()

    def describe_table(self, table_name: str) -> TableSchema:
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

    def _extract_table_name(self, query: str) -> str | None:
        """从 SQL 中提取 FROM 子句的主表名"""
        m = re.search(r'FROM\s+"?(\w+)"?', query, re.IGNORECASE)
        return m.group(1) if m else None

    def execute_sql(self, query: str, params: dict | None = None) -> pd.DataFrame:
        """工具: 执行只读 SQL 查询 (V3: 注入 RLS 前进行列存在性检查)"""
        stripped = query.strip().upper()
        if not stripped.startswith("SELECT"):
            raise ValueError("仅允许 SELECT 查询")

        if self._rls_scope and self._rls_scope.get("mode") == "filtered":
            from app.core.query_rewriter import QueryInterceptor
            interceptor = QueryInterceptor(self._rls_scope)

            # 自动检测主表并设置列缓存
            main_table = self._extract_table_name(query)
            if main_table:
                try:
                    schema = self.describe_table(main_table)
                    col_names = [c.name for c in schema.columns]
                    interceptor.set_table_columns(main_table, col_names)
                except Exception:
                    pass

            query = interceptor.rewrite_sql(query, table_name=main_table)

        with self.engine.connect() as conn:
            return pd.read_sql(text(query), conn, params=params or {})

    async def execute_sql_async(self, query: str, params: dict | None = None) -> pd.DataFrame:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.execute_sql, query, params)

    def probe_raw_schema(self) -> SchemaSummary:
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
