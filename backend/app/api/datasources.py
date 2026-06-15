"""数据源管理 API（仅管理员）"""

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import create_engine as create_sync_engine

from app.agents.factory import agent_factory
from app.core.audit import write_audit_log
from app.core.encryption import encrypt, safe_decrypt
from app.core.permissions import require_admin
from app.database import get_db
from app.models.audit_log import AuditAction
from app.models.datasource import DataSource, DataSourcePermission
from app.models.user import User
from app.schemas.datasource import (
    DataSourceCreate, DataSourceResponse, DataSourceUpdate,
    PermissionRequest, ProbeResponse,
)

router = APIRouter(prefix="/api/datasources", tags=["数据源管理"])


def _build_sync_url(ds: DataSource, password: str) -> str:
    if ds.db_type == "sqlite":
        return f"sqlite:///{ds.host}"
    driver_map = {"mysql": "pymysql", "postgresql": "psycopg2", "mssql": "pymssql"}
    driver = driver_map.get(ds.db_type, ds.db_type)
    return f"{ds.db_type}+{driver}://{ds.username}:{password}@{ds.host}:{ds.port}/{ds.db_name}"


def _test_connection_sync(ds: DataSource, password: str) -> dict:
    """同步连接测试 — 在线程池中执行以避免阻塞事件循环"""
    url = _build_sync_url(ds, password)
    engine = create_sync_engine(
        url,
        connect_args={"connect_timeout": 5} if ds.db_type != "sqlite" else {"check_same_thread": False},
    )
    try:
        with engine.connect() as conn:
            conn.execute(sa_text("SELECT 1"))
        return {"status": "ok", "message": "连接成功"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        engine.dispose()


@router.get("", response_model=list[DataSourceResponse])
async def list_datasources(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    result = await db.execute(select(DataSource).order_by(DataSource.created_at.desc()))
    return result.scalars().all()


@router.post("", response_model=DataSourceResponse, status_code=status.HTTP_201_CREATED)
async def create_datasource(
    body: DataSourceCreate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    ds = DataSource(
        name=body.name, db_type=body.db_type, host=body.host, port=body.port,
        db_name=body.db_name, username=body.username,
        password_encrypted=encrypt(body.password), business_tag=body.business_tag,
    )
    db.add(ds)
    await db.commit()
    await db.refresh(ds)
    await write_audit_log(
        db, _admin, AuditAction.config_changed,
        resource_type="datasource", resource_id=ds.id,
        detail={"name": body.name, "action": "create"},
    )
    return ds


@router.put("/{ds_id}", response_model=DataSourceResponse)
async def update_datasource(
    ds_id: str, body: DataSourceUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    result = await db.execute(select(DataSource).where(DataSource.id == ds_id))
    ds = result.scalar_one_or_none()
    if ds is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="数据源不存在")
    for field in ("name", "host", "port", "db_name", "username", "business_tag"):
        if (v := getattr(body, field, None)) is not None:
            setattr(ds, field, v)
    if body.password is not None:
        ds.password_encrypted = encrypt(body.password)
    if body.is_active is not None:
        ds.is_active = body.is_active
    await db.commit()
    await db.refresh(ds)
    # A3: 配置变更后使Agent缓存失效
    agent_factory.invalidate(ds_id)
    await write_audit_log(
        db, _admin, AuditAction.config_changed,
        resource_type="datasource", resource_id=ds_id,
        detail={"name": ds.name, "action": "update"},
    )
    return ds


@router.delete("/{ds_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_datasource(
    ds_id: str,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    result = await db.execute(select(DataSource).where(DataSource.id == ds_id))
    ds = result.scalar_one_or_none()
    if ds is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="数据源不存在")
    if ds.is_system:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="系统预定义数据源不可删除")
    # A3: 删除前清理Agent缓存
    agent_factory.invalidate(ds_id)
    await write_audit_log(
        db, _admin, AuditAction.config_changed,
        resource_type="datasource", resource_id=ds_id,
        detail={"name": ds.name, "action": "delete"},
    )
    await db.delete(ds)
    await db.commit()


@router.post("/{ds_id}/test")
async def test_connection(
    ds_id: str,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    result = await db.execute(select(DataSource).where(DataSource.id == ds_id))
    ds = result.scalar_one_or_none()
    if ds is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    password = safe_decrypt(ds.password_encrypted)
    return await asyncio.to_thread(_test_connection_sync, ds, password)


@router.post("/{ds_id}/probe", response_model=ProbeResponse)
async def probe_schema(
    ds_id: str,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    result = await db.execute(select(DataSource).where(DataSource.id == ds_id))
    ds = result.scalar_one_or_none()
    if ds is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    # Step 1: 获取 Agent 并探测原始 schema
    agent = agent_factory.get_or_create(ds)
    raw_schema = await asyncio.to_thread(agent.probe_raw_schema)

    # Step 2: LLM 语义推断
    tables_desc = []
    for t in raw_schema.tables:
        cols = ", ".join(f"{c.name}({c.dtype})" for c in t.columns)
        tables_desc.append(f"表 {t.name}: {cols} (行数: {t.row_count or '未知'})")

    llm_prompt = f"""业务标签: {ds.business_tag}
数据库表结构:
{chr(10).join(tables_desc)}

请推断每张表的业务含义和核心指标建议。输出严格 JSON:
{{
  "tables": [
    {{
      "name": "原始表名",
      "semantic_meaning": "业务含义(中文)",
      "columns": [{{"name": "列名", "semantic_meaning": "字段含义"}}],
      "suggested_metrics": [
        {{"label": "指标名", "sql_template": "SELECT ...", "unit": "单位"}}
      ]
    }}
  ]
}}"""

    try:
        from app.core.llm_client import llm_client
        msg = await llm_client.chat([
            {"role": "system", "content": "你是一个数据库分析专家，精确输出 JSON。"},
            {"role": "user", "content": llm_prompt},
        ])
        content = msg.get("content", "{}").strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1].rsplit("\n", 1)[0]
        semantic = json.loads(content)
    except Exception:
        semantic = {"tables": []}

    # Step 3: 合并语义到原始 schema
    schema_dict = {
        "business_tag": ds.business_tag,
        "tables": [],
        "suggested_metrics": [],
    }
    for t in raw_schema.tables:
        t_dict = {
            "name": t.name,
            "row_count": t.row_count,
            "columns": [{"name": c.name, "dtype": c.dtype} for c in t.columns],
        }
        sem_t = next((st for st in semantic.get("tables", []) if st["name"] == t.name), None)
        if sem_t:
            t_dict["semantic_meaning"] = sem_t.get("semantic_meaning")
            for col in t_dict["columns"]:
                sem_col = next((sc for sc in sem_t.get("columns", []) if sc["name"] == col["name"]), None)
                if sem_col:
                    col["semantic_meaning"] = sem_col.get("semantic_meaning")
            for m in sem_t.get("suggested_metrics", []):
                schema_dict["suggested_metrics"].append(m)
        schema_dict["tables"].append(t_dict)

    # 持久化
    ds.schema_summary = schema_dict
    await db.commit()
    await write_audit_log(
        db, _admin, AuditAction.config_changed,
        resource_type="datasource", resource_id=ds_id,
        detail={"name": ds.name, "action": "probe", "tables_found": len(raw_schema.tables)},
    )

    return ProbeResponse(status="ok", tables_found=len(raw_schema.tables), schema_summary=schema_dict)


# 权限管理端点
@router.get("/{ds_id}/permissions")
async def get_permissions(
    ds_id: str,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    result = await db.execute(
        select(DataSourcePermission).where(DataSourcePermission.datasource_id == ds_id)
    )
    perms = result.scalars().all()
    return {
        "datasource_id": ds_id,
        "grants": [
            {
                "grant_type": p.grant_type,
                "grant_target": p.grant_target,
                "can_query": p.can_query,
                "row_filter_scope": p.row_filter_scope,
            }
            for p in perms if p.can_query
        ],
    }


@router.put("/{ds_id}/permissions")
async def update_permissions(
    ds_id: str,
    body: PermissionRequest,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    ds_result = await db.execute(select(DataSource).where(DataSource.id == ds_id))
    ds = ds_result.scalar_one_or_none()
    if ds is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="数据源不存在")
    old_perms = (await db.execute(
        select(DataSourcePermission).where(DataSourcePermission.datasource_id == ds_id)
    )).scalars().all()
    for p in old_perms:
        await db.delete(p)
    for grant in body.grants:
        db.add(DataSourcePermission(
            datasource_id=ds_id,
            grant_type=grant.get("grant_type", "role"),
            grant_target=grant.get("grant_target", ""),
            can_query=grant.get("can_query", True),
            row_filter_scope=grant.get("row_filter_scope"),
        ))
    await db.commit()
    await write_audit_log(
        db, _admin, AuditAction.permission_changed,
        resource_type="datasource", resource_id=ds_id,
        detail={"name": ds.name, "grants_count": len(body.grants), "action": "replace_permissions"},
    )
    return {"datasource_id": ds_id, "grants": body.grants}
