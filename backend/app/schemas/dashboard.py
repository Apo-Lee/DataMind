"""看板相关 Pydantic schemas"""

from pydantic import BaseModel


class KpiCard(BaseModel):
    id: str = ""           # 唯一标识，如 "dept_count" 用于自定义
    label: str
    value: str
    unit: str = ""
    trend: str | None = None  # up | down | stable
    enabled: bool = True   # 用户是否启用此卡片
    sql_template: str = "" # 保存 SQL 模板供手动刷新


class AvailableMetric(BaseModel):
    """供用户勾选用的可选指标列表"""
    id: str
    label: str
    sql_template: str
    unit: str = ""


class DashboardChart(BaseModel):
    """面板图表"""
    id: str = ""
    title: str = ""
    type: str = ""  # bar / pie / line / stackbar
    xAxis: list = []
    series: list[dict] = []
    data: list[dict] = []  # pie 直接 data
    height: int = 300
    subtitle: str = ""


class PanelData(BaseModel):
    datasource_id: str
    datasource_name: str
    business_tag: str
    is_primary: bool
    kpi_cards: list[KpiCard] = []
    available_metrics: list[AvailableMetric] = []
    charts: list[DashboardChart] = []  # V2.4: 面板图表


class DashboardResponse(BaseModel):
    panels: list[PanelData]
