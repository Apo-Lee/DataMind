# -*- coding: utf-8 -*-
"""SQL 生成 Agent - 将自然语言问题翻译为安全的 SQL 查询"""

import json
import logging
import re

from app.agents.base import DataSourceAgent
from app.core.llm_client import llm_client

logger = logging.getLogger(__name__)


SQL_SYSTEM_PROMPT = """你是一个 SQL 专家。根据数据源的表结构、列值示例和用户的自然语言问题，生成正确的 SQL 查询。
**必须遵守的规则（违反会导致错误）：**
1. 只允许 SELECT 语句，禁止 INSERT/UPDATE/DELETE/DROP/ALTER/TRUNCATE
2. 自动添加 LIMIT 1000
3. 列名和表名使用数据库原始名称（不要翻译或造词）
4. 返回格式: 严格 JSON: {"sql": "生成的SQL", "explanation": "查询说明"}
5. **WHERE 条件中的值必须从每列的"可用值"中选取，绝对不要自己编造或使用英文值**
6. 出勤率用 attendance 表计算: SUM(CASE WHEN status='出勤' THEN 1 ELSE 0 END) * 100.0 / COUNT(*)
7. 计算百分比用 x * 100.0 / NULLIF(y, 0) 避免除零错误
8. 用户说部门时，用 departments 表中实际存在的部门名称
9. 多表关联时注意正确的 JOIN 条件（外键关系在列名后用 -> 标注）
10. 日期过滤用 strftime('%Y-%m', date_column) 或 date() 函数
11. **权限约束（必须遵守，违反会导致越权！）：**
    - 你的 data_scope 决定了你能看到什么范围的数据
    - 如果是 self_only：只能用当前用户自己的数据（WHERE id/employee_id = 当前用户ID）
    - 如果是 team：只能查自己和直属下级的数据
    - 如果是 dept：只能查本部门的数据（WHERE dept_id = 当前部门ID）
    - 如果是 dept_and_sub：只能查本部门及子部门的数据
    - 如果是 all：才能查全公司数据（需要特别确认）
12. **敏感字段保护：** salary（薪资）、phone（电话）、email（邮箱）属于敏感信息
    - employee 角色：绝对不能查询这些字段
    - dept_manager/dept_ceo：只能查自己部门内员工的这些字段，不能做全公司聚合
    - 如果用户问题涉及敏感字段但权限不足，务必在 explanation 中说明原因
13. **防止全表扫描：** 除非 data_scope=all，否则查询必须有合理的 WHERE 限制
"""



# 敏感字段列表（按表名 -> 列名集合）
_SENSITIVE_COLUMNS = {
    "employees": {"salary", "phone", "email"},
    "attendance": set(),
    "departments": {"budget"},
}

# 各角色允许查询的数据范围描述
_ROLE_DATA_SCOPE = {
    "admin": "可以查看全公司所有数据",
    "hr_director": "可以查看全公司HR相关数据（员工信息、薪资、考勤）",
    "finance_bp": "可以查看全公司财务数据（预算、费用）",
    "finance_director": "可以查看全公司财务数据",
    "dept_ceo": "可以查看自己部门及子部门的全部数据",
    "dept_manager": "可以查看自己部门的数据和直属下级数据",
    "sales_manager": "可以查看自己团队的销售数据",
    "employee": "只能查看自己的数据",
    "viewer": "只读权限，可以查看被授权的数据源",
}


def _get_role_permission_context(user_info: dict) -> str:
    """根据用户信息生成权限上下文描述，注入 LLM prompt"""
    role = user_info.get("role", "employee")
    data_scope = user_info.get("data_scope", "team")
    dept_name = user_info.get("dept_name", "未知部门")
    role_desc = _ROLE_DATA_SCOPE.get(role, "未知权限")
    parts = []
    parts.append("【当前用户权限】")
    parts.append("- 角色: " + role + " (" + role_desc + ")")
    parts.append("- 数据范围: " + data_scope)
    parts.append("- 所属部门: " + dept_name)
    parts.append("- 用户ID: " + str(user_info.get("user_id", "")))
    parts.append("- 员工ID: " + str(user_info.get("employee_id", "")))
    parts.append("- 部门ID: " + str(user_info.get("dept_id", "")))
    return chr(10).join(parts)


def _validate_sql_permissions(sql: str, user_info: dict) -> tuple:
    """SQL 执行前的权限校验规则引擎
    Returns: (is_allowed: bool, reason: str)
    """
    sql_lower = sql.lower()
    role = user_info.get("role", "")
    data_scope = user_info.get("data_scope", "")

    # 规则1: employee 角色不能查询敏感字段
    if role == "employee":
        for table, cols in _SENSITIVE_COLUMNS.items():
            for col in cols:
                if col.lower() in sql_lower and table in sql_lower:
                    return (False, "角色为 employee，无权查询敏感字段 "" + col + ""，请联系你的上级")

    # 规则2: 非 all 范围必须有 WHERE 条件
    if data_scope != "all" and role != "admin":
        has_where = "where" in sql_lower
        has_limit = "limit" in sql_lower
        has_dept_filter = "dept_id" in sql_lower
        has_emp_filter = "employee_id" in sql_lower
        count_only = "count(" in sql_lower or "sum(" in sql_lower
        if not has_where and not has_limit and not has_dept_filter and not has_emp_filter:
            if not count_only:
                return (False, "权限受限：非管理员查询必须有 WHERE 条件限制数据范围")

    # 规则3: employee 不能执行全公司聚合
    if role == "employee" and ("avg(" in sql_lower or "sum(" in sql_lower):
        if "where" not in sql_lower:
            return (False, "员工角色不能执行全公司范围的聚合统计")

    # 规则4: 批量导出敏感字段需要权限
    if role not in ("admin", "hr_director"):
        for table, cols in _SENSITIVE_COLUMNS.items():
            sin = [c for c in cols if c.lower() in sql_lower]
            if sin and table in sql_lower and "where" not in sql_lower:
                return (False, "批量导出敏感字段（" + ", ".join(sin) + "）需要权限审批")

    return (True, "")
_TABLE_SEMANTICS = {
    "hr": {
        "employees": "员工信息表（个人基本信息、岗位、薪资、绩效等）",
        "departments": "部门组织架构表（部门名称、层级关系、负责人、预算等）",
        "attendance": "每日考勤记录（status: 出勤/请假/迟到/缺勤）",
        "org_hierarchy": "组织层级关系（ancestor->descendant, depth层级深度）",
    },
    "crm": {
        "customers": "客户信息表（行业、等级、联系方式等）",
        "deals": "销售商机/交易表（status: 赢单/输单/跟进中/暂停/已签约）",
        "follow_ups": "客户跟进记录（type: 上门拜访/邮件跟进/方案演示等）",
        "sales_targets": "销售目标与完成情况表",
    },
    "finance": {
        "budgets": "部门预算表（按年度/季度/类别分配）",
        "cost_centers": "成本中心表",
        "expenses": "费用明细（category: IT设备/物业/通讯/招待/营销; status: 已审批/待审批/驳回/已支付）",
        "travel_expenses": "差旅费用明细（交通/住宿/餐饮等）",
    },
    "erp": {
        "inventory": "库存物料表（category: IT设备/家具/耗材/安全设备/网络设备）",
        "projects": "项目表（status: 进行中/已完成/暂停/规划中; priority: P0/P1/P2）",
        "project_dept": "项目-部门关联表",
        "purchase_orders": "采购订单表（status: 已下单/已到货/审批中/已完成/驳回）",
        "resources": "项目资源分配表（角色、分配比例、成本）",
    },
}

# 每列的业务语义描述（按 business_tag -> table -> column -> 中文含义）
_COLUMN_SEMANTICS = {
    "hr": {
        "employees": {
            "id": "员工唯一ID（主键）",
            "name": "员工姓名",
            "dept_id": "所在部门ID -> departments.id",
            "position": "岗位名称（如：工程师、经理）",
            "level": "职级（如：P5、P6、M1）",
            "status": "员工状态：在职/离职/试用期",
            "join_date": "入职日期（格式：YYYY-MM-DD）",
            "salary": "月薪（元）",
            "performance_score": "绩效评分（0-100）",
            "phone": "联系电话",
            "email": "电子邮箱",
            "manager_id": "直属上级ID -> employees.id",
            "position_category": "岗位类别（如：技术、市场、销售）",
            "gender": "性别（男/女）",
            "education": "学历（如：本科、硕士、博士）",
        },
        "departments": {
            "id": "部门ID（主键）",
            "name": "部门名称",
            "parent_dept_id": "上级部门ID -> departments.id",
            "manager_name": "部门负责人姓名",
            "budget": "部门年度预算（元）",
            "location": "部门办公地点",
        },
        "attendance": {
            "id": "考勤记录ID（主键）",
            "employee_id": "员工ID -> employees.id",
            "date": "考勤日期（格式：YYYY-MM-DD）",
            "check_in": "上班打卡时间（HH:MM格式）",
            "check_out": "下班打卡时间（HH:MM格式）",
            "status": "考勤状态：出勤/请假/迟到/缺勤",
        },
        "org_hierarchy": {
            "ancestor_id": "上级节点ID（组织树祖先）",
            "descendant_id": "下级节点ID（组织树后代）",
            "depth": "层级深度（0=自身，1=直接下级）",
        },
    },
    "crm": {
        "customers": {
            "id": "客户ID（主键）",
            "name": "客户名称/公司名",
            "industry": "所属行业",
            "level": "客户等级（如：A/B/C）",
            "contact_person": "联系人姓名",
            "phone": "联系电话",
            "email": "电子邮箱",
            "status": "客户状态",
        },
        "deals": {
            "id": "交易ID（主键）",
            "customer_id": "客户ID -> customers.id",
            "title": "交易标题",
            "amount": "交易金额（元）",
            "status": "交易状态：赢单/输单/跟进中/暂停/已签约",
            "close_date": "预计关闭日期（格式：YYYY-MM-DD）",
            "probability": "赢单概率（%）",
        },
        "follow_ups": {
            "id": "跟进记录ID（主键）",
            "customer_id": "客户ID -> customers.id",
            "date": "跟进日期",
            "type": "跟进方式：上门拜访/邮件跟进/方案演示等",
            "content": "跟进内容描述",
            "next_plan": "下一步计划",
        },
        "sales_targets": {
            "id": "目标ID（主键）",
            "year": "年份",
            "quarter": "季度",
            "target_amount": "目标金额（元）",
            "actual_amount": "实际完成金额（元）",
            "dept_id": "部门ID",
        },
    },
    "finance": {
        "budgets": {
            "id": "预算ID（主键）",
            "dept_id": "部门ID",
            "year": "年份",
            "quarter": "季度（1-4）",
            "category": "预算类别",
            "amount": "预算金额（元）",
        },
        "cost_centers": {
            "id": "成本中心ID（主键）",
            "code": "成本中心编码",
            "name": "成本中心名称",
            "manager": "负责人",
        },
        "expenses": {
            "id": "费用ID（主键）",
            "dept_id": "部门ID",
            "category": "费用类别：IT设备/物业/通讯/招待/营销",
            "amount": "费用金额（元）",
            "date": "费用发生日期",
            "status": "状态：已审批/待审批/驳回/已支付",
            "description": "费用说明",
        },
        "travel_expenses": {
            "id": "差旅ID（主键）",
            "employee_id": "员工ID",
            "date": "出差日期",
            "category": "类别：交通/住宿/餐饮",
            "amount": "金额（元）",
            "destination": "目的地",
        },
    },
    "erp": {
        "inventory": {
            "id": "库存ID（主键）",
            "name": "物料名称",
            "category": "类别：IT设备/家具/耗材/安全设备/网络设备",
            "quantity": "库存数量",
            "unit_price": "单价（元）",
            "location": "存放位置",
        },
        "projects": {
            "id": "项目ID（主键）",
            "name": "项目名称",
            "status": "状态：进行中/已完成/暂停/规划中",
            "priority": "优先级：P0/P1/P2",
            "budget": "预算（元）",
            "start_date": "开始日期",
            "end_date": "结束日期",
        },
        "purchase_orders": {
            "id": "采购单ID（主键）",
            "project_id": "项目ID",
            "item": "采购物品",
            "quantity": "数量",
            "unit_price": "单价",
            "total_amount": "总金额",
            "status": "状态：已下单/已到货/审批中/已完成/驳回",
            "order_date": "下单日期",
        },
    },
}



def _build_schema_with_values(agent, tables):
    """构建包含列语义、样本值、主键、外键的完整 schema 描述"""
    tag = agent.business_tag
    col_semantics = _COLUMN_SEMANTICS.get(tag, {})
    schema_desc = "数据库表结构（按业务领域：" + tag + "）："

    for t in tables:
        try:
            ts = agent.describe_table(t)
            cols_info = []
            table_semantics = col_semantics.get(t, {})

            for c in ts.columns:
                tags = []
                if c.is_primary_key:
                    tags.append("PK")
                if not c.nullable:
                    tags.append("NOT NULL")
                tag_str = " [" + ",".join(tags) + "]" if tags else ""
                col_desc = c.name + "(" + c.dtype + ")" + tag_str

                meaning = table_semantics.get(c.name, "")
                if meaning:
                    col_desc += " " + meaning

                dtype_lower = c.dtype.lower()
                is_text_like = any(k in dtype_lower for k in ["varchar", "text", "char", "string"])
                is_date_like = any(k in dtype_lower for k in ["date", "time", "timestamp"])

                if is_text_like:
                    samples = _get_sample_values(agent, t, c.name)
                    if samples:
                        col_desc += " 可用值:[" + ", ".join(samples) + "]"
                elif is_date_like:
                    col_desc += " (日期格式: YYYY-MM-DD)"
                elif any(k in dtype_lower for k in ["int", "real", "float", "decimal"]):
                    sv = _get_sample_values(agent, t, c.name, max_samples=3)
                    if sv:
                        col_desc += " 例如:[" + ", ".join(sv) + "]"

                if c.name.endswith("_id") and c.name != "id":
                    base = c.name[:-3]
                    cands = [base, base + "s", base + "es"]
                    found = [x for x in cands if x in tables]
                    if found:
                        col_desc += " -> " + found[0] + ".id"

                cols_info.append(col_desc)

            try:
                csql = 'SELECT COUNT(*) as cnt FROM "' + t + '"'
                cdf = agent.execute_sql(csql)
                rc = int(cdf.iloc[0, 0]) if cdf is not None and not cdf.empty else None
            except Exception:
                rc = None

            cols = ", ".join(cols_info)
            sem = _TABLE_SEMANTICS.get(tag, {}).get(t)
            schema_desc += "\n" + "  - " + t + ": " + cols
            if sem:
                schema_desc += "  # " + sem
            if rc is not None:
                schema_desc += " [" + str(rc) + "行]"
        except Exception:
            schema_desc += "\n" + "  - " + t

    return schema_desc


def _has_multi_statement(sql: str) -> bool:
    """智能检测是否为真实多语句（允许尾部单分号）"""
    cleaned = re.sub(r"'[^']*'", "", sql)
    cleaned = re.sub(r'"[^"]*"', "", cleaned)
    semicolons = [i for i, c in enumerate(cleaned) if c == ';']
    if not semicolons:
        return False
    if len(semicolons) == 1 and semicolons[0] == len(cleaned.strip()) - 1:
        return False
    return True


_STATUS_FIXES = [
    # 考勤状态
    ('present', '出勤'),
    ('"present"', '出勤'),
    ("'present'", '出勤'),
    ('absent', '缺勤'),
    ('"absent"', '缺勤'),
    ("'absent'", '缺勤'),
    ('leave', '请假'),
    ('"leave"', '请假'),
    ("'leave'", '请假'),
    ('late', '迟到'),
    ('"late"', '迟到'),
    ("'late'", '迟到'),
    # 员工状态
    ('active', '在职'),
    ('"active"', '在职'),
    ("'active'", '在职'),
    ('employed', '在职'),
    ('"employed"', '在职'),
    ("'employed'", '在职'),
    ('resigned', '离职'),
    ('"resigned"', '离职'),
    ("'resigned'", '离职'),
    ('inactive', '离职'),
    ('"inactive"', '离职'),
    ("'inactive'", '离职'),
    ('probation', '试用期'),
    ('"probation"', '试用期'),
    ("'probation'", '试用期'),
    # 出勤率相关
    ('attendance_rate', '出勤率'),
    # 交易状态 (CRM)
    ('won', '赢单'),
    ('"won"', '赢单'),
    ("'won'", '赢单'),
    ('lost', '输单'),
    ('"lost"', '输单'),
    ("'lost'", '输单'),
    ('closed_won', '赢单'),
    ('closed_lost', '输单'),
    # 项目状态 (ERP)
    ('in_progress', '进行中'),
    ('"in_progress"', '进行中'),
    ("'in_progress'", '进行中'),
    ('completed', '已完成'),
    ('"completed"', '已完成'),
    ("'completed'", '已完成'),
    ('planned', '规划中'),
    ('"planned"', '规划中'),
    ("'planned'", '规划中'),
    # 费用状态 (Finance)
    ('pending', '待审批'),
    ('approved', '已审批'),
    ('rejected', '驳回'),
    ('paid', '已支付'),
]


def _normalize_sql_values(sql):
    """自动修正 LLM 常见的枚举值错误（英文 -> 中文）"""
    for eng, chn in _STATUS_FIXES:
        sql = sql.replace(eng, "'" + chn + "'")
    return sql


async def generate_sql(question: str, agent) -> dict:
    """生成安全的 SQL 查询"""
    tables = agent.list_tables()
    schema_desc = _build_schema_with_values(agent, tables)

    # 注入权限上下文（A层：LLM提示约束）
    permission_ctx = _get_role_permission_context({
        "role": getattr(agent, "_user_role", "employee"),
        "data_scope": getattr(agent, "_user_data_scope", "team"),
        "dept_name": getattr(agent, "_user_dept_name", "未知"),
        "user_id": getattr(agent, "_user_id", ""),
        "employee_id": getattr(agent, "_user_employee_id", None),
        "dept_id": getattr(agent, "_user_dept_id", None),
    })

    user_msg = permission_ctx + "\n\n数据库结构:\n" + schema_desc + "\n\n用户问题: " + question

    try:
        msg = await llm_client.chat([
            {"role": "system", "content": SQL_SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ])
        content = msg.get("content", "{}").strip()
        if content.startswith("'''"):
            content = content.split("\n", 1)[1].rsplit("\n", 1)[0]

        result = json.loads(content)
        sql = result.get("sql", "").strip()
        sql = _normalize_sql_values(sql)
        sql_upper = sql.upper()

        # 权限规则引擎校验（B层：SQL越权检测）
        allowed, reason = _validate_sql_permissions(sql, {
            "role": getattr(agent, "_user_role", "employee"),
            "data_scope": getattr(agent, "_user_data_scope", "team"),
            "employee_id": getattr(agent, "_user_employee_id", None),
            "dept_id": getattr(agent, "_user_dept_id", None),
        })
        if not allowed:
            return {"sql": "", "explanation": "权限拒绝: " + reason, "rejected": True}

        if not sql_upper.startswith("SELECT"):
            return {"sql": "", "explanation": "拒绝执行: 仅允许 SELECT 查询", "rejected": True}
        if _has_multi_statement(sql):
            return {"sql": "", "explanation": "拒绝执行: 禁止多语句", "rejected": True}

        dangerous = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "CREATE", "GRANT", "REVOKE", "EXEC", "EXECUTE", "INTO OUTFILE"]
        for keyword in dangerous:
            if re.search(r"\b" + re.escape(keyword) + r"\b", sql_upper):
                return {"sql": "", "explanation": "拒绝执行: 检测到危险操作 " + keyword, "rejected": True}

        if "LIMIT" not in sql_upper:
            result["sql"] = sql.rstrip(";") + " LIMIT 1000"
        result["rejected"] = False
        return result
    except Exception as e:
        return {"sql": "", "explanation": "SQL 生成失败: " + str(e), "rejected": True}
