"""用户相关 Pydantic schemas (V2)"""
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class UserCreate(BaseModel):
    username: str = Field(min_length=2, max_length=50)
    password: str = Field(min_length=6)
    display_name: str = Field(min_length=1, max_length=100)
    role: str = Field(default="employee")
    employee_id: int | None = None
    dept_id: int | None = None


class UserUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=100)
    role: str | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=6)
    # V2: 权限字段
    data_scope: str | None = None
    extra_dept_ids: list[int] | None = None


class UserResponse(BaseModel):
    id: str
    username: str
    display_name: str
    role: str
    is_active: bool
    created_at: str | None = None
    # V2: HR 锚点 & 权限字段
    employee_id: int | None = None
    dept_id: int | None = None
    manager_id: int | None = None
    data_scope: str | None = None
    extra_dept_ids: str | None = None
    hr_synced_at: str | None = None
    source: str | None = None

    model_config = {"from_attributes": True}

    @field_validator("created_at", "hr_synced_at", mode="before")
    @classmethod
    def dt_to_str(cls, v):
        if isinstance(v, datetime):
            return v.isoformat()
        return v
