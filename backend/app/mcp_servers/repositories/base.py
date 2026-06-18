# -*- coding: utf-8 -*-
"""Repository 基类 — 封装通用查询模式

所有 Repository 继承 BaseRepository，通过 engine 执行参数化查询。
handler 调用 repository 方法而非直接写 SQL。
"""
from sqlalchemy import text
import pandas as pd


class BaseRepository:
    """Repository 基类"""

    def __init__(self, engine):
        self._engine = engine

    def _run(self, sql, params=None):
        """执行 SQL 并返回 DataFrame。"""
        stmt = text(sql).bindparams(**params) if params else text(sql)
        return pd.read_sql(stmt, self._engine)

    def _run_dict(self, sql, params=None):
        """执行 SQL 返回 list[dict]。"""
        df = self._run(sql, params)
        return df.to_dict(orient="records")

    def get_by_id(self, table: str, id_col: str, id_val, cols=None):
        """按 ID 查单行。"""
        c = ", ".join(f'"{c}"' for c in cols) if cols else "*"
        return self._run_dict(f'SELECT {c} FROM "{table}" WHERE "{id_col}" = :id', {"id": id_val})

    def find_all(self, table: str, order_by=None, limit=5000):
        """查全部。"""
        sql = f'SELECT * FROM "{table}"'
        if order_by:
            sql += f' ORDER BY "{order_by}"'
        return self._run_dict(sql + f" LIMIT {limit}")

    def find_by(self, table: str, filters: dict, order_by=None, limit=100):
        """等值条件查询。"""
        clauses = [f'"{k}" = :{k}' for k in filters]
        sql = f'SELECT * FROM "{table}" WHERE {" AND ".join(clauses)}'
        if order_by:
            sql += f' ORDER BY "{order_by}"'
        return self._run_dict(sql + f" LIMIT {limit}", filters)
