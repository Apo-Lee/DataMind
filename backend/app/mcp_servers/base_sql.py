# -*- coding: utf-8 -*-
"""app/mcp_servers/base_sql.py - SQL DB MCP Server Base (V3 fix)"""

import json, logging
from typing import Any
from sqlalchemy import create_engine, inspect, text
import pandas as pd
from . import BaseMCPServer, MCPTool, MCPResult
from app.core.query_engine import _COLUMN_SENSITIVITY, _ROLE_SENSITIVITY_ACCESS
logger = logging.getLogger(__name__)

Q = chr(34)

class MCPAuth:
    def __init__(self, user_role="employee", data_scope="self_only", employee_id=None, dept_id=None):
        self.role = user_role
        self.max_level = _ROLE_SENSITIVITY_ACCESS.get(user_role, {"safe"})
        self.data_scope = data_scope
        self.employee_id = employee_id
        self.dept_id = dept_id
    def visible_columns(self, bt, tn):
        s = _COLUMN_SENSITIVITY.get(bt, {}).get(tn, {})
        return {c for c, l in s.items() if l in self.max_level}
    def filter_columns(self, bt, tn, cols):
        v = self.visible_columns(bt, tn)
        return [c for c in cols if c in v] if v else cols
    def mask_sensitive_data(self, bt, rows):
        if "highly_sensitive" in self.max_level: return rows
        sens = _COLUMN_SENSITIVITY.get(bt, {})
        masked = []
        for row in rows:
            mrow = dict(row)
            for tcols in sens.values():
                for col, level in tcols.items():
                    if col not in mrow: continue
                    if level == "highly_sensitive": mrow[col] = "***"
                    elif level == "sensitive" and "sensitive" not in self.max_level:
                        v = mrow[col]
                        if col == "phone" and isinstance(v, str) and len(v) > 7:
                            mrow[col] = v[:3] + "****" + v[-4:]
                        elif col == "email" and isinstance(v, str) and "@" in v:
                            p = v.split("@")
                            mrow[col] = p[0][:2] + "***@" + p[1]
                        else: mrow[col] = "***"
            masked.append(mrow)
        return masked
    def can_access_table(self, bt, tn):
        if self.role == "admin": return True
        if self.role == "employee": return tn not in {"org_hierarchy"}
        return True
    def apply_rls_filter(self, bt, mt, sql):
        if self.data_scope == "all": return sql
        fk = {"employees": ("id","employee_id"),"departments":("id","dept_id"),"attendance":("employee_id","employee_id"),"deals":("dept_id","dept_id"),"customers":("owner_dept_id","dept_id"),"sales_targets":("dept_id","dept_id"),"projects":("dept_id","dept_id"),"purchase_orders":("dept_id","dept_id"),"resources":("employee_id","employee_id"),"budgets":("dept_id","dept_id"),"expenses":("dept_id","dept_id"),"cost_centers":("dept_id","dept_id")}
        cm = fk.get(mt)
        if not cm: return sql
        sc = self.data_scope
        wc = None
        if sc == "self_only" and self.employee_id is not None:
            wc = Q + cm[0] + Q + " = " + str(self.employee_id)
        elif sc in ("team","dept") and self.dept_id is not None:
            wc = Q + cm[0] + Q + " = " + str(self.dept_id)
        elif sc == "dept_and_sub" and self.dept_id is not None:
            wc = Q + cm[0] + Q + " IN (SELECT descendant_id FROM org_hierarchy WHERE ancestor_id = " + str(self.dept_id) + ")"
        if wc:
            if "WHERE" in sql.upper():
                sql = sql.replace("WHERE", "WHERE (" + wc + ") AND ", 1)
            else:
                idx = max(sql.upper().rfind("ORDER BY"), sql.upper().rfind("LIMIT"))
                if idx < 0: sql += " WHERE " + wc
                else: sql = sql[:idx] + " WHERE " + wc + " " + sql[idx:]
        return sql


class SQLMCPServer(BaseMCPServer):
    def __init__(self, name, bt, url):
        super().__init__(name, bt)
        self.business_tag = bt
        ca = {"check_same_thread": False} if "sqlite" in url else {}
        self._engine = create_engine(url, connect_args=ca)
        self._register_core_tools()
        self._register_business_tools()
        self._auth = MCPAuth()
    def set_auth(self, a): self._auth = a
    def _apply_auth(self, rows): return self._auth.mask_sensitive_data(self.business_tag, rows)
    def _apply_column_filter(self, t, cols): return self._auth.filter_columns(self.business_tag, t, cols)
    def _check_table_access(self, t):
        if not self._auth.can_access_table(self.business_tag, t): raise Exception("Access denied: " + t)
    def _apply_rls(self, sql, mt): return self._auth.apply_rls_filter(self.business_tag, mt, sql)
    def _register_core_tools(self):
        self.register_tool(MCPTool(name="query",description="Structured query",parameters={"main_table":{"type":"string"},"select_columns":{"type":"array","items":{"type":"string"}},"aggregations":{"type":"array","items":{"type":"object","properties":{"column":{"type":"string"},"type":{"type":"string","enum":["COUNT","SUM","AVG","MAX","MIN"]},"alias":{"type":"string"}}}},"filters":{"type":"array","items":{"type":"object","properties":{"column":{"type":"string"},"op":{"type":"string"},"value":{"type":"string"}}}},"join_tables":{"type":"array","items":{"type":"string"}},"group_by":{"type":"array","items":{"type":"string"}},"order_by":{"type":"array","items":{"type":"object","properties":{"column":{"type":"string"},"direction":{"type":"string"}}}},"limit":{"type":"integer"}},required=["main_table","select_columns"]),self._handle_query)
        self.register_tool(MCPTool(name="list_tables",description="List all tables",parameters={}),self._handle_list_tables)
        self.register_tool(MCPTool(name="describe_table",description="Describe table structure",parameters={"table_name":{"type":"string"}},required=["table_name"]),self._handle_describe_table)
        self.register_tool(MCPTool(name="execute_sql",description="Execute safe SELECT SQL",parameters={"sql":{"type":"string"},"limit":{"type":"integer"}},required=["sql"]),self._handle_execute_sql)
    def _register_business_tools(self): pass
    def _foreign_keys(self): return {}
    def _safe_quote(self, val):
        if val is None: return ""
        return str(val).replace(chr(39), chr(39)+chr(39))
    def _build_sql(self, args):
        mt = (args.get("main_table","") or "").strip()
        cols = args.get("select_columns",[]) or []
        aggs = args.get("aggregations",[]) or []
        flts = args.get("filters",[]) or []
        joins = args.get("join_tables",[]) or []
        gb = args.get("group_by",[]) or []
        ob = args.get("order_by",[]) or []
        limit_arg = args.get("limit",100)
        if limit_arg is None: limit_arg = 100
        limit = min(int(limit_arg), 5000)
        if limit <= 0: limit = 100
        sp = [Q + c + Q for c in cols]
        for a in aggs:
            ac = a.get("column","") or ""
            at = a.get("type","COUNT") or "COUNT"
            aa = a.get("alias","") or ""
            if not aa: aa = at + ("_" + ac if ac else "")
            if ac: sp.append("%s(%s%s%s) AS %s%s%s" % (at,Q,ac,Q,Q,aa,Q))
            else: sp.append("%s(*) AS %s%s%s" % (at,Q,aa,Q))
        sql = "SELECT " + (", ".join(sp) if sp else "*") + " FROM " + Q + mt + Q
        fk = self._foreign_keys()
        for jt in joins:
            if (mt,jt) in fk:
                fkc,pkc = fk[(mt,jt)]
                sql += " LEFT JOIN " + Q + jt + Q + " ON " + Q + jt + Q + "." + Q + pkc + Q + " = " + Q + mt + Q + "." + Q + fkc + Q
            elif (jt,mt) in fk:
                fkc,pkc = fk[(jt,mt)]
                sql += " LEFT JOIN " + Q + jt + Q + " ON " + Q + mt + Q + "." + Q + fkc + Q + " = " + Q + jt + Q + "." + Q + pkc + Q
        wp = []
        for f in flts:
            fc = f.get("column","") or ""
            fo = f.get("op","=") or "="
            fv = f.get("value","") or ""
            wp.append(Q + fc + Q + " " + fo + " " + chr(39) + self._safe_quote(fv) + chr(39))
        if wp: sql += " WHERE " + " AND ".join(wp)
        if gb: sql += " GROUP BY " + ", ".join(Q + c + Q for c in gb)
        if ob: sql += " ORDER BY " + ", ".join(Q + o["column"] + Q + " " + o.get("direction","ASC") for o in ob)
        sql += " LIMIT %d" % limit
        return sql
    async def _handle_query(self, args):
        mt = args.get("main_table","") or ""
        if mt:
            self._check_table_access(mt)
            args["select_columns"] = self._apply_column_filter(mt, args.get("select_columns",[]) or [])
        sql = self._build_sql(args)
        if mt: sql = self._apply_rls(sql, mt)
        try:
            df = pd.read_sql(text(sql), self._engine)
            rows = df.head(1000).to_dict(orient="records")
            rows = self._apply_auth(rows)
            return {"sql":sql,"rows":rows,"total_rows":len(df),"columns":list(df.columns)}
        except Exception as e:
            raise Exception("SQL Error: %s\n%s" % (e, sql))
    async def _handle_list_tables(self, args):
        ins = inspect(self._engine)
        result = []
        for t in ins.get_table_names():
            try: self._check_table_access(t)
            except: continue
            cols = ins.get_columns(t)
            pk = ins.get_pk_constraint(t).get("constrained_columns",[])
            visible = self._auth.visible_columns(self.business_tag, t)
            result.append({"name":t,"columns":[{"name":c["name"],"type":str(c["type"]),"is_pk":c["name"] in pk} for c in cols if not visible or c["name"] in visible]})
        return {"tables": result}
    async def _handle_describe_table(self, args):
        tn = args.get("table_name","") or ""
        if tn: self._check_table_access(tn)
        if not tn: raise Exception("Missing table_name")
        ins = inspect(self._engine)
        cols = ins.get_columns(tn)
        pk = ins.get_pk_constraint(tn).get("constrained_columns",[])
        fk_list = [{"col":f["constrained_columns"][0],"ref_table":f["referred_table"],"ref_col":f["referred_columns"][0]} for f in ins.get_foreign_keys(tn) if f.get("constrained_columns")]
        visible = self._auth.visible_columns(self.business_tag, tn)
        return {"table":tn,"columns":[{"name":c["name"],"type":str(c["type"]),"is_pk":c["name"] in pk} for c in cols if not visible or c["name"] in visible],"foreign_keys":fk_list}
    async def _handle_execute_sql(self, args):
        sql = (args.get("sql","") or "").strip()
        limit_arg = args.get("limit",100)
        if limit_arg is None: limit_arg = 100
        limit = min(int(limit_arg), 5000)
        if limit <= 0: limit = 100
        if not sql.upper().startswith("SELECT"): raise Exception("Only SELECT allowed")
        if "LIMIT" not in sql.upper(): sql += " LIMIT %d" % limit
        try:
            df = pd.read_sql(text(sql), self._engine)
            rows = df.head(1000).to_dict(orient="records")
            rows = self._apply_auth(rows)
            return {"sql":sql,"rows":rows,"total_rows":len(df),"columns":list(df.columns)}
        except Exception as e:
            raise Exception("SQL Error: %s\n%s" % (e, sql))
    def dispose(self):
        self._engine.dispose()