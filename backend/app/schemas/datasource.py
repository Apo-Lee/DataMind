"""数据源相关 Pydantic schemas"""

from pydantic import BaseModel, Field, field_validator
from datetime import datetime


class DataSourceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    db_type: str
    host: str
    port: int
    db_name: str
    username: str
    password: str
    business_tag: str


class DataSourceUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=100)
    host: str | None = None
    port: int | None = None
    db_name: str | None = None
    username: str | None = None
    password: str | None = None
    business_tag: str | None = None
    is_active: bool | None = None


class DataSourceResponse(BaseModel):
    id: str
    name: str
    db_type: str
    host: str
    port: int
    db_name: str
    username: str
    business_tag: str
    schema_summary: dict | None = None
    is_active: bool
    is_system: bool = False
    created_at: str | None = None

    model_config = {"from_attributes": True}

    @field_validator("created_at", mode="before")
    @classmethod
    def dt_to_str(cls, v):
        if isinstance(v, datetime):
            return v.isoformat()
        return v


class PermissionRequest(BaseModel):
    grants: list[dict] = Field(default_factory=list)  # V2: [{grant_type, grant_target, can_query, row_filter_scope}]


class ProbeResponse(BaseModel):
    status: str
    tables_found: int
    schema_summary: dict | None = None
