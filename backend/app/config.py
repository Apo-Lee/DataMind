"""应用配置管理 — 从环境变量加载"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # 部署环境
    deployment_env: str = "development"

    # 数据库
    database_url: str = "sqlite+aiosqlite:///./datamind.db"

    # JWT
    secret_key: str = "dev-secret-key-change-in-production"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # DeepSeek
    deepseek_api_key: str = "sk-placeholder"
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"

    # 加密
    encryption_key: str = "dev-encryption-key-32chars!!"

    # CORS
    cors_origins: str = "*"  # 生产环境应设置为前端域名，如 "http://localhost:5173,https://datamind.example.com"

    # Demo 数据
    demo_data_dir: str = "../demo_data"

    # 沙箱
    sandbox_image: str = "datamind-sandbox:latest"
    sandbox_timeout: int = 60
    sandbox_memory_limit: str = "1g"
    sandbox_cpu_limit: float = 2.0

    model_config = {"env_file": ".env", "extra": "ignore"}

    def model_post_init(self, __context):
        """P2-7: 生产环境安全验证 — 敏感配置为占位值时拒绝启动"""
        if self.deployment_env == "production":
            if self.deepseek_api_key in ("sk-placeholder", ""):
                raise ValueError(
                    "DEEPSEEK_API_KEY 未配置！生产环境必须设置 DEEPSEEK_API_KEY 环境变量。"
                )
            if self.secret_key == "dev-secret-key-change-in-production":
                raise ValueError(
                    "SECRET_KEY 未更换！生产环境必须设置强随机 SECRET_KEY 环境变量。"
                )
            if self.encryption_key == "dev-encryption-key-32chars!!":
                raise ValueError(
                    "ENCRYPTION_KEY 未更换！生产环境必须设置强随机 ENCRYPTION_KEY 环境变量。"
                )


settings = Settings()
