# DataMind 项目开发规范

## 技术栈

- **后端**: Python 3.12+ / FastAPI / SQLAlchemy (async) / LangGraph / SQLite (dev) / PostgreSQL (prod)
- **前端**: Vue 3 + TypeScript / Vite / Element Plus / ECharts
- **基础设施**: Docker / Docker Compose / GitHub Actions CI

## 架构核心原则

### 分层架构
```
API层 → Orchestrator层(LangGraph) → MCP Server层(业务工具) → Repository层(数据访问)
```
- API层只做请求校验和响应组装，不包含业务逻辑
- Orchestrator层通过LangGraph StateGraph编排：intent → sql → analysis → report
- MCP Server层暴露结构化业务工具（每个数据源独立server）
- Repository层统一封装数据库查询，禁止直接 pd.read_sql

### 权限体系

权限在 MCP Server 的 `MCPAuth` 类中统一处理，通过 contextvar 传递，避免并发竞态：
```
请求进入 → JWT鉴权 → contextvar注入 → execute_tool覆写
                    → _check_table_access (表级准入)
                    → handler执行业务逻辑
                    → _apply_auth (结果集脱敏)
```

### 代码规范

1. **导入顺序**: 标准库 → 第三方库 → 本地模块，每组间空行
2. **类型注解**: 所有函数参数和返回值必须有类型注解
3. **错误处理**: 使用 `AgentFriendlyError` 抛出用户友好的中文错误，不在API层直接暴露SQL异常
4. **异步**: 所有 I/O 操作（DB查询、LLM调用、MCP调用）必须使用 async/await
5. **RLS注入**: 统一通过 `QueryInterceptor` 或 `_apply_rls_fallback` 实现，禁止在SQLBuilder中内联RLS
6. **日志**: 使用 `logging.getLogger(__name__)`，禁止 print

### 测试规范

- Repository层测试不依赖外部数据（使用SQLite :memory:）
- MCP Auth/RLS测试覆盖所有角色×数据源矩阵
- 集成测试需要种子数据
- 运行: `python -m pytest tests/ -v`
