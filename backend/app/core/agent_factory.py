"""Agent 工厂 — 按数据源创建 & 缓存 Agent 实例"""

from app.core.agent_base import DataSourceAgent
from app.core.encryption import safe_decrypt
from app.models.datasource import DataSource


class AgentFactory:
    """管理所有数据源的 Agent 实例生命周期"""

    def __init__(self):
        self._agents: dict[str, DataSourceAgent] = {}

    def _build_url(self, ds: DataSource) -> str:
        password = safe_decrypt(ds.password_encrypted)
        if ds.db_type == "sqlite":
            return f"sqlite:///{ds.host}"
        driver_map = {
            "mysql": "pymysql", "postgresql": "psycopg2",
            "mssql": "pymssql",
        }
        driver = driver_map.get(ds.db_type, ds.db_type)
        return f"{ds.db_type}+{driver}://{ds.username}:{password}@{ds.host}:{ds.port}/{ds.db_name}"

    def get_or_create(self, ds: DataSource) -> DataSourceAgent:
        if ds.id not in self._agents:
            url = self._build_url(ds)
            agent = DataSourceAgent(
                datasource_id=ds.id, connection_url=url,
                business_tag=ds.business_tag,
            )
            if ds.schema_summary:
                agent.schema_cache = ds.schema_summary
            self._agents[ds.id] = agent
        return self._agents[ds.id]

    def remove(self, datasource_id: str):
        agent = self._agents.pop(datasource_id, None)
        if agent:
            agent.dispose()

    def invalidate(self, datasource_id: str):
        """A3: 使缓存失效并清理连接 — 在数据源配置变更时调用"""
        self.remove(datasource_id)

    def get_agent_by_tag(self, business_tag: str) -> DataSourceAgent | None:
        """通过 business_tag 查找已缓存的 Agent"""
        for agent in self._agents.values():
            if agent.business_tag == business_tag:
                return agent
        return None


# 全局单例
agent_factory = AgentFactory()
