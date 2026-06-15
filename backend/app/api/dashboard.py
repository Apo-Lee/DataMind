"""看板 API — 为 BI 驾驶舱提供数据，含详情页 ECharts 数据 (V2: 集成 RLS)"""

import asyncio
import time

import pandas as pd
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.factory import agent_factory
from app.core.auth import get_current_user, get_role_str
from app.core.permissions import get_accessible_datasources, get_agent_with_rls, check_datasource_access  # A1: 统一权限入口
from app.database import get_db
from app.models.conversation import KpiPreference
from app.models.datasource import DataSource
from app.models.user import User
from app.schemas.dashboard import DashboardResponse, PanelData, KpiCard, AvailableMetric

router = APIRouter(prefix="/api/dashboard", tags=["看板"])
log = logging.getLogger(__name__)

# V2.5: 动态日期 SQL 片段 (SQLite)，替代硬编码日期
# WHY: 硬编码日期如 '2026-06-01' 会在跨月/跨年后导致 KPI 全部归零
# 所有"本月"指标使用 _SQL_THIS_MONTH，"今年"指标使用 _SQL_THIS_YEAR，"近6月"趋势使用 _SQL_6M_AGO
_SQL_THIS_MONTH = "strftime('%Y-%m-%d','now','start of month')"
_SQL_THIS_YEAR = "CAST(strftime('%Y','now') AS INTEGER)"
_SQL_6M_AGO = "strftime('%Y-%m-%d','now','start of month','-5 months')"

# P2-1: 看板数据 TTL 缓存 — 避免每次刷新触发 30+ 次 SQL
_panels_cache: dict[str, tuple[float, dict]] = {}
_PANELS_CACHE_TTL = 60  # 60秒


@router.get("/panels", response_model=DashboardResponse)
async def get_panels(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    # P2-1: 看板数据 TTL 缓存 — 用户级缓存避免重复计算
    cache_key = f"{current_user.id}:{current_user.role}:{current_user.data_scope}:{current_user.extra_dept_ids or ''}"
    cached = _panels_cache.get(cache_key)
    if cached and (time.time() - cached[0]) < _PANELS_CACHE_TTL:
        return DashboardResponse(**cached[1])

    datasources = await get_accessible_datasources(current_user, db)
    if not datasources:
        return DashboardResponse(panels=[])
    user_role = get_role_str(current_user)
    # WHY: 按用户角色确定主看板，覆盖所有角色类型
    primary_tag_map = {
        "hr_director": "hr",
        "finance_bp": "finance",
        "finance_director": "finance",
        "sales_manager": "crm",
        "viewer": "hr",
        "dept_ceo": None,
        "dept_manager": None,
        "employee": None,
    }
    primary_tag = primary_tag_map.get(user_role)
    panels = []
    for i, ds in enumerate(datasources):
        is_primary = (primary_tag and ds.business_tag == primary_tag) or (not primary_tag and i == 0)
        # A1: 使用统一权限入口注入 RLS (get_agent_with_rls 内部已创建/缓存 agent)
        agent_with_rls, rls_scope = await get_agent_with_rls(current_user, ds.id, db)
        all_cards = await _generate_kpi_cards_via_agent(agent_with_rls, ds)
        available_metrics = _get_available_metrics(ds)

        # V2.3: 按角色定制默认KPI
        enabled_ids = await _get_user_kpi_prefs_from_db(current_user.id, ds.id, db)
        if enabled_ids:
            filtered_cards = [c for c in all_cards if c.id in enabled_ids]
        else:
            role_defaults = _get_role_default_kpi_ids(user_role, ds.business_tag)
            if role_defaults:
                filtered_cards = [c for c in all_cards if c.id in role_defaults]
            else:
                filtered_cards = []  # 该角色在这个数据源上不应显示任何KPI

        # V2.4: 生成图表数据 (从 agent 获取 tables) — 使用线程池避免阻塞事件循环
        agent_tables = agent_with_rls.list_tables()
        charts = await asyncio.to_thread(_build_chart_for_tag, ds.business_tag, agent_with_rls, agent_tables)

        panels.append(PanelData(
            datasource_id=ds.id, datasource_name=ds.name, business_tag=ds.business_tag,
            is_primary=is_primary, kpi_cards=filtered_cards, available_metrics=available_metrics,
            charts=charts,
        ))
    result = DashboardResponse(panels=panels)
    _panels_cache[cache_key] = (time.time(), result.model_dump())
    return result


async def _generate_kpi_cards_via_agent(agent, ds: DataSource) -> list[KpiCard]:
    cards = []
    try:
        tables = agent.list_tables()
        if not tables:
            return cards
        for m in _get_available_metrics(ds):
            if not m.sql_template:
                continue
            try:
                df = await agent.execute_sql_async(m.sql_template)
                if df is not None and not df.empty and len(df.columns) == 1:
                    raw = df.iloc[0, 0]
                    if raw is None or (isinstance(raw, float) and str(raw) == 'nan'):
                        val = "0"
                    else:
                        # WHY: 保留小数精度 — int(raw) 会将 85.3 截断为 85
                        if isinstance(raw, float) and raw != int(raw):
                            val = f"{raw:.1f}"
                        else:
                            val = str(int(raw)) if isinstance(raw, (int, float)) else str(raw)
                    cards.append(KpiCard(id=m.id, label=m.label, value=val, unit=m.unit, trend="stable", enabled=True, sql_template=m.sql_template))
            except Exception as e:
                log.warning("KPI %s SQL failed: %s", m.id, e)
                continue
    except Exception as e:
        log.warning("Agent table listing failed: %s", e)
    return cards


def _get_available_metrics(ds: DataSource) -> list[AvailableMetric]:
    """返回该数据源所有可用的指标列表，MVP 硬编码，后续从 schema 自动生成"""
    tag = ds.business_tag
    if tag == "hr":
        return [
            AvailableMetric(id="total_employees", label="员工总数", sql_template=f"SELECT COUNT(*) FROM employees WHERE status = '在职'"),
            AvailableMetric(id="avg_perf_score", label="平均绩效分", sql_template=f"SELECT ROUND(AVG(performance_score), 1) FROM employees WHERE status = '在职'"),
            AvailableMetric(id="attendance_rate", label="本月出勤率", sql_template=f"SELECT ROUND(SUM(CASE WHEN status='出勤' THEN 1 ELSE 0 END)*100.0/COUNT(*), 1) FROM attendance WHERE date >= {_SQL_THIS_MONTH}"),
            AvailableMetric(id="attendance_late_rate", label="本月迟到率", sql_template=f"SELECT ROUND(SUM(CASE WHEN status='迟到' THEN 1 ELSE 0 END)*100.0/COUNT(*), 1) FROM attendance WHERE date >= {_SQL_THIS_MONTH}"),
            AvailableMetric(id="leave_rate", label="本月请假率", sql_template=f"SELECT ROUND(SUM(CASE WHEN status='请假' THEN 1 ELSE 0 END)*100.0/COUNT(*), 1) FROM attendance WHERE date >= {_SQL_THIS_MONTH}"),
            AvailableMetric(id="avg_salary", label="平均薪资", unit="元", sql_template=f"SELECT ROUND(AVG(salary), 0) FROM employees WHERE status = '在职'"),
            AvailableMetric(id="new_employees", label="本月新入职", sql_template=f"SELECT COUNT(*) FROM employees WHERE join_date >= {_SQL_THIS_MONTH}"),
            AvailableMetric(id="new_employees_6m", label="近6月新入职", sql_template=f"SELECT COUNT(*) FROM employees WHERE status = '在职' AND join_date >= {_SQL_6M_AGO}"),
            AvailableMetric(id="high_perf_count", label="优秀员工(90+)", sql_template=f"SELECT COUNT(*) FROM employees WHERE status = '在职' AND performance_score >= 90"),
        ]
    elif tag == "crm":
        return [
            AvailableMetric(id="total_customers", label="客户总数", sql_template=f"SELECT COUNT(*) FROM customers"),
            AvailableMetric(id="deal_amount_ytd", label="年度成交额", unit="元", sql_template=f"SELECT ROUND(SUM(amount), 0) FROM deals WHERE status = '赢单' AND close_date >= {_SQL_THIS_MONTH}"),
            AvailableMetric(id="deal_win_rate", label="赢单率", unit="%", sql_template=f"SELECT ROUND(SUM(CASE WHEN status='赢单' THEN 1 ELSE 0 END)*100.0/COUNT(*), 1) FROM deals WHERE close_date >= {_SQL_6M_AGO}"),
            AvailableMetric(id="lost_customers_30d", label="近30天失联客户", sql_template=f"SELECT COUNT(*) FROM customers WHERE id NOT IN (SELECT customer_id FROM follow_ups WHERE date >= {_SQL_6M_AGO})"),
            AvailableMetric(id="avg_deal_amount", label="平均成交金额", unit="元", sql_template=f"SELECT ROUND(AVG(amount), 0) FROM deals WHERE status = '赢单' AND close_date >= {_SQL_6M_AGO}"),
            AvailableMetric(id="new_customers_30d", label="近30天新增客户", sql_template=f"SELECT COUNT(*) FROM customers WHERE created_date >= {_SQL_6M_AGO}"),
        ]
    elif tag == "finance":
        return [
            AvailableMetric(id="budget_usage_rate", label="预算使用率", unit="%", sql_template=f"SELECT ROUND(SUM(used)*100.0/NULLIF(SUM(amount),0), 1) FROM budgets WHERE year = {_SQL_THIS_YEAR}"),
            AvailableMetric(id="expense_total", label="年度总费用", unit="元", sql_template=f"SELECT ROUND(SUM(amount), 0) FROM expenses WHERE date >= {_SQL_THIS_MONTH}"),
            AvailableMetric(id="travel_expense", label="差旅费累计", unit="元", sql_template=f"SELECT ROUND(SUM(amount), 0) FROM expenses WHERE category = '差旅' AND date >= {_SQL_THIS_MONTH}"),
            AvailableMetric(id="entertainment_expense", label="招待费累计", unit="元", sql_template=f"SELECT ROUND(SUM(amount), 0) FROM expenses WHERE category = '招待' AND date >= {_SQL_THIS_MONTH}"),
            AvailableMetric(id="avg_expense_per_dept", label="部门平均费用", unit="元", sql_template=f"SELECT ROUND(AVG(amount), 0) FROM expenses WHERE date >= {_SQL_THIS_MONTH}"),
            AvailableMetric(id="pending_reimbursement", label="待报销笔数", sql_template=f"SELECT COUNT(*) FROM expenses WHERE status = '待报销'"),
            AvailableMetric(id="dept_with_budget", label="有预算部门数", sql_template=f"SELECT COUNT(DISTINCT dept_id) FROM (SELECT dept_id, SUM(used) AS u, SUM(amount) AS a FROM budgets WHERE year={_SQL_THIS_YEAR} GROUP BY dept_id HAVING a > 0)"),
        ]
    elif tag == "erp":
        return [
            AvailableMetric(id="active_projects", label="进行中项目", sql_template=f"SELECT COUNT(*) FROM projects WHERE status = '进行中'"),
            AvailableMetric(id="total_budget", label="项目总预算", unit="元", sql_template=f"SELECT ROUND(SUM(budget), 0) FROM projects"),
            AvailableMetric(id="cost_ratio", label="整体成本执行率", unit="%", sql_template=f"SELECT ROUND(SUM(actual_cost)*100.0/NULLIF(SUM(budget),0), 1) FROM projects"),
            AvailableMetric(id="avg_resource_alloc", label="平均资源分配率", unit="%", sql_template=f"SELECT ROUND(AVG(allocation_pct), 1) FROM resources"),
        ]
    return []


def _get_role_default_kpi_ids(role: str, tag: str) -> list[str]:
    """按角色+数据源返回默认启用的KPI ID列表"""
    defaults = {
        "admin": {
            "hr": ["total_employees", "avg_perf_score", "attendance_rate", "avg_salary", "new_employees"],
            "crm": ["total_customers", "deal_amount_ytd", "deal_win_rate", "avg_deal_amount"],
            "finance": ["budget_usage_rate", "expense_total", "travel_expense", "entertainment_expense"],
            "erp": ["active_projects", "total_budget", "cost_ratio"],
        },
        "hr_director": {
            "hr": ["total_employees", "avg_perf_score", "attendance_rate", "avg_salary", "new_employees"],
        },
        "finance_bp": {
            "finance": ["budget_usage_rate", "expense_total", "travel_expense", "pending_reimbursement"],
        },
        "finance_director": {
            "finance": ["budget_usage_rate", "expense_total", "travel_expense", "entertainment_expense", "avg_expense_per_dept"],
            "hr": ["total_employees", "avg_salary"],
        },
        "dept_ceo": {
            "hr": ["total_employees", "avg_perf_score", "attendance_rate"],
            "crm": ["total_customers", "deal_amount_ytd"],
            "finance": ["budget_usage_rate", "expense_total"],
            "erp": ["active_projects", "total_budget"],
        },
        "dept_manager": {
            "hr": ["total_employees", "avg_perf_score"],
            "crm": ["total_customers", "deal_amount_ytd"],
            "finance": ["budget_usage_rate", "expense_total"],
            "erp": ["active_projects"],
        },
        "sales_manager": {
            "crm": ["total_customers", "deal_amount_ytd", "deal_win_rate"],
        },
        "employee": {},
        "viewer": {},
    }
    return defaults.get(role, {}).get(tag, [])


async def _get_user_kpi_prefs_from_db(user_id: str, ds_id: str, db: AsyncSession) -> list[str]:
    try:
        stmt = select(KpiPreference).where(KpiPreference.user_id == user_id, KpiPreference.datasource_id == ds_id)
        result = await db.execute(stmt)
        pref = result.scalar_one_or_none()
        if pref and pref.enabled_ids:
            return json.loads(pref.enabled_ids)
    except Exception:
        pass
    return []


async def _save_user_kpi_prefs_to_db(user_id: str, ds_id: str, enabled_ids: list[str], db: AsyncSession):
    try:
        stmt = select(KpiPreference).where(KpiPreference.user_id == user_id, KpiPreference.datasource_id == ds_id)
        result = await db.execute(stmt)
        pref = result.scalar_one_or_none()
        if pref:
            pref.enabled_ids = json.dumps(enabled_ids)
        else:
            pref = KpiPreference(user_id=user_id, datasource_id=ds_id, enabled_ids=json.dumps(enabled_ids))
            db.add(pref)
        await db.commit()
    except Exception:
        await db.rollback()


@router.post("/panels/{ds_id}/kpi-prefs")
async def save_panel_config(ds_id: str, body: dict, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    enabled_ids = body.get("enabled_ids", [])
    await _save_user_kpi_prefs_to_db(current_user.id, ds_id, enabled_ids, db)
    return {"status": "ok"}


@router.get("/panels/{ds_id}/kpi-prefs")
async def get_panel_config(ds_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    enabled_ids = await _get_user_kpi_prefs_from_db(current_user.id, ds_id, db)
    return {"enabled_ids": enabled_ids}


@router.post("/panels/{ds_id}/refresh")
async def refresh_panel(ds_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    cache_key = f"{current_user.id}:{current_user.role}:{current_user.data_scope}:{current_user.extra_dept_ids or ''}"
    _panels_cache.pop(cache_key, None)
    return {"status": "ok"}


@router.get("/panels/{ds_id}/detail")
async def get_panel_detail(ds_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    from app.core.permissions import check_datasource_access
    ds = await check_datasource_access(current_user, ds_id, db)
    agent_with_rls, rls_scope = await get_agent_with_rls(current_user, ds_id, db)
    available_metrics = _get_available_metrics(ds)
    all_cards = await _generate_kpi_cards_via_agent(agent_with_rls, ds)
    enabled_ids = await _get_user_kpi_prefs_from_db(current_user.id, ds_id, db)
    if enabled_ids:
        filtered_cards = [c for c in all_cards if c.id in enabled_ids]
    else:
        user_role = get_role_str(current_user)
        role_defaults = _get_role_default_kpi_ids(user_role, ds.business_tag)
        filtered_cards = [c for c in all_cards if c.id in (role_defaults or [])]
    agent_tables = agent_with_rls.list_tables()
    charts = await asyncio.to_thread(_build_chart_for_tag, ds.business_tag, agent_with_rls, agent_tables)
    return PanelData(
        datasource_id=ds.id, datasource_name=ds.name, business_tag=ds.business_tag,
        is_primary=False, kpi_cards=filtered_cards, available_metrics=available_metrics,
        charts=charts,
    )


def _try_query(agent, sql: str = None):
    """同步执行 SQL 查询并返回 DataFrame（V2: 集成 RLS 已注入 agent）"""
    try:
        return agent.execute_sql(sql) if sql else None
    except Exception as e:
        log.warning("Query failed: %s", e)
        return None


def _build_charts(agent, tables: list[str], tag: str) -> list[dict]:
    return _build_chart_for_tag(tag, agent, tables)


def _build_chart_for_tag(tag: str, agent, tables: list[str]) -> list[dict]:
    if tag == "hr": return _build_hr_charts(agent, tables)
    if tag == "crm": return _build_crm_charts(agent, tables)
    if tag == "finance": return _build_finance_charts(agent, tables)
    if tag == "erp": return _build_erp_charts(agent, tables)
    return []


def _build_hr_charts(agent, tables: list[str]) -> list[dict]:
    charts = []
    if "employees" in tables and "departments" in tables:
        df = _try_query(agent, "SELECT d.name AS 部门, COUNT(e.id) AS 在职人数 FROM departments d LEFT JOIN employees e ON e.dept_id = d.id AND e.status = '在职' GROUP BY d.name ORDER BY 在职人数 DESC")
        if df is not None and not df.empty:
            charts.append({"id": "dept_headcount", "title": "各部门在职人数", "type": "bar", "xAxis": df["部门"].tolist(), "series": [{"name": "在职人数", "data": [int(v) for v in df["在职人数"].values]}], "height": 320})
    if "employees" in tables:
        df2 = _try_query(agent, "SELECT CASE WHEN performance_score >= 90 THEN '优秀(90+)' WHEN performance_score >= 75 THEN '良好(75-89)' WHEN performance_score >= 60 THEN '待改进(60-74)' ELSE '不合格(<60)' END AS 等级, COUNT(*) AS 人数 FROM employees WHERE status = '在职' GROUP BY 等级 ORDER BY 等级")
        if df2 is not None and not df2.empty:
            charts.append({"id": "perf_dist", "title": "绩效分布", "type": "pie", "data": [{"name": row["等级"], "value": int(row["人数"])} for _, row in df2.iterrows()], "height": 300})
    if "attendance" in tables:
        df4 = _try_query(agent, f"SELECT strftime('%Y-%m', date) AS 月份, SUM(CASE WHEN status='出勤' THEN 1 ELSE 0 END) AS 出勤, SUM(CASE WHEN status='请假' THEN 1 ELSE 0 END) AS 请假, SUM(CASE WHEN status='迟到' THEN 1 ELSE 0 END) AS 迟到 FROM attendance WHERE date >= {_SQL_6M_AGO} GROUP BY 月份 ORDER BY 月份 LIMIT 6")
        if df4 is not None and not df4.empty:
            charts.append({"id": "attendance", "title": "近6月考勤统计", "type": "bar", "subtype": "stack", "xAxis": df4["月份"].tolist(), "series": [{"name": "出勤", "data": [int(v) for v in df4["出勤"].values]}, {"name": "请假", "data": [int(v) for v in df4["请假"].values]}, {"name": "迟到", "data": [int(v) for v in df4["迟到"].values]}], "height": 300})
    return charts


def _build_crm_charts(agent, tables: list[str]) -> list[dict]:
    charts = []
    if "customers" in tables:
        df = _try_query(agent, "SELECT industry AS 行业, COUNT(*) AS 客户数 FROM customers GROUP BY 行业")
        if df is not None and not df.empty:
            charts.append({"id": "industry_dist", "title": "客户行业分布", "type": "pie", "data": [{"name": row["行业"], "value": int(row["客户数"])} for _, row in df.iterrows()], "height": 300})
    if "deals" in tables:
        df2 = _try_query(agent, f"SELECT strftime('%Y-%m', close_date) AS 月份, SUM(CASE WHEN status='赢单' THEN amount ELSE 0 END) AS 成交金额, COUNT(CASE WHEN status='赢单' THEN 1 END) AS 成交笔数 FROM deals WHERE close_date >= {_SQL_6M_AGO} GROUP BY 月份 ORDER BY 月份 LIMIT 6")
        if df2 is not None and not df2.empty:
            charts.append({"id": "deal_trend", "title": "月度成交趋势", "type": "line", "xAxis": df2["月份"].tolist(), "series": [{"name": "成交金额(万元)", "data": [round(v/10000, 1) for v in df2["成交金额"].values]}, {"name": "成交笔数", "data": [int(v) for v in df2["成交笔数"].values]}], "height": 320, "dualY": True})
    if "customers" in tables:
        df3 = _try_query(agent, "SELECT level AS 等级, COUNT(*) AS 数量 FROM customers GROUP BY 等级 ORDER BY 等级")
        if df3 is not None and not df3.empty:
            charts.append({"id": "level_dist", "title": "客户等级分布", "type": "bar", "xAxis": df3["等级"].tolist(), "series": [{"name": "客户数", "data": [int(v) for v in df3["数量"].values]}], "height": 280})
    return charts


def _build_finance_charts(agent, tables: list[str]) -> list[dict]:
    charts = []
    if "budgets" in tables:
        df = _try_query(agent, "SELECT dept_id AS 部门, SUM(amount) AS 预算 FROM budgets GROUP BY 部门 ORDER BY 部门")
        if df is not None and not df.empty:
            charts.append({"id": "budget_amount", "title": "各部门预算分配", "type": "bar", "xAxis": [str(d) for d in df["部门"].tolist()], "series": [{"name": "预算(元)", "data": [round(v, 0) for v in df["预算"].values]}], "height": 320})
    if "expenses" in tables:
        df2 = _try_query(agent, "SELECT category AS 类别, SUM(amount) AS 金额 FROM expenses GROUP BY 类别 ORDER BY 金额 DESC")
        if df2 is not None and not df2.empty:
            charts.append({"id": "expense_cat", "title": "费用类别构成", "type": "pie", "data": [{"name": row["类别"], "value": round(float(row["金额"]), 0)} for _, row in df2.iterrows()], "height": 320})
        df3 = _try_query(agent, f"SELECT strftime('%Y-%m', date) AS 月份, SUM(amount) AS 总金额 FROM expenses WHERE date >= {_SQL_6M_AGO} GROUP BY 月份 ORDER BY 月份 LIMIT 6")
        if df3 is not None and not df3.empty:
            charts.append({"id": "expense_trend", "title": "月度费用趋势", "type": "line", "xAxis": df3["月份"].tolist(), "series": [{"name": "费用(万元)", "data": [round(v/10000, 1) for v in df3["总金额"].values]}], "height": 300})
    return charts


def _build_erp_charts(agent, tables: list[str]) -> list[dict]:
    charts = []
    if "projects" in tables:
        df = _try_query(agent, "SELECT name AS 项目, budget/10000 AS 预算万元 FROM projects ORDER BY budget DESC")
        if df is not None and not df.empty:
            charts.append({"id": "proj_budget", "title": "项目预算分布（万元）", "type": "bar", "xAxis": df["项目"].tolist(), "series": [{"name": "预算(万元)", "data": [round(v, 1) for v in df["预算万元"].values]}], "height": 320})
        df2 = _try_query(agent, "SELECT status AS 状态, COUNT(*) AS 数量 FROM projects GROUP BY 状态")
        if df2 is not None and not df2.empty:
            charts.append({"id": "proj_status", "title": "项目状态分布", "type": "pie", "data": [{"name": row["状态"], "value": int(row["数量"])} for _, row in df2.iterrows()], "height": 300})
    if "inventory" in tables:
        df3 = _try_query(agent, "SELECT category AS 类别, SUM(quantity) AS 总数 FROM inventory GROUP BY 类别 ORDER BY 总数 DESC")
        if df3 is not None and not df3.empty:
            charts.append({"id": "inv_cat", "title": "库存类别分布", "type": "bar", "xAxis": df3["类别"].tolist(), "series": [{"name": "库存量", "data": [int(v) for v in df3["总数"].values]}], "height": 300})
    return charts
