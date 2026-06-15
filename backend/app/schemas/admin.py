"""管理后台相关 Pydantic schemas (V2)"""
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


# ---- 系统监控 ----
class HealthStatus(BaseModel):
    component: str
    status: str  # ok / warning / error
    detail: str = ""


class MonitorHealthResponse(BaseModel):
    overall: str  # healthy / degraded / down
    components: list[HealthStatus]
    checked_at: str


class MonitorStatsResponse(BaseModel):
    total_users: int
    active_users: int
    total_datasources: int
    total_queries: int
    queries_24h: int
    avg_query_time_ms: float = 0


# ---- 审计日志 ----
class AuditLogResponse(BaseModel):
    id: str
    user_id: str | None = None
    username: str
    action: str
    resource_type: str | None = None
    resource_id: str | None = None
    detail: dict | None = None
    ip_address: str | None = None
    created_at: str | None = None

    model_config = {"from_attributes": True}

    @field_validator("created_at", mode="before")
    @classmethod
    def dt_to_str(cls, v):
        if isinstance(v, datetime):
            return v.isoformat()
        return v


# ---- HR 同步 ----
class HrSyncStatusResponse(BaseModel):
    last_sync_at: str | None = None
    last_sync_status: str | None = None
    hr_employee_count: int | None = None
    matched_users: int | None = None
    unmatched_users: int | None = None


class HrSyncLogResponse(BaseModel):
    id: str
    started_at: str | None = None
    completed_at: str | None = None
    status: str
    total_hr_employees: int | None = None
    created_users: int = 0
    updated_users: int = 0
    deactivated_users: int = 0
    errors: dict | None = None
    created_at: str | None = None

    model_config = {"from_attributes": True}

    @field_validator("started_at", "completed_at", "created_at", mode="before")
    @classmethod
    def dt_to_str(cls, v):
        if isinstance(v, datetime):
            return v.isoformat()
        return v


# ---- 系统配置 ----
class SystemConfigItem(BaseModel):
    key: str
    value: str | None = None
    value_type: str = "string"
    description: str | None = None
    updated_at: str | None = None

    model_config = {"from_attributes": True}

    @field_validator("updated_at", mode="before")
    @classmethod
    def dt_to_str(cls, v):
        if isinstance(v, datetime):
            return v.isoformat()
        return v


class SystemConfigUpdate(BaseModel):
    value: str
    value_type: str | None = None


# ---- 数据权限分配 ----
class UserPermissionUpdate(BaseModel):
    data_scope: str | None = None
    extra_dept_ids: list[int] | None = None


class DatasourceGrant(BaseModel):
    grant_type: str = "user"  # role / user / dept
    grant_target: str         # role值 / user_id / dept_id
    can_query: bool = True
    row_filter_scope: str | None = None


class DatasourcePermissionUpdate(BaseModel):
    grants: list[DatasourceGrant]
