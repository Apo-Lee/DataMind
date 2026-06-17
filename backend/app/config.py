"""应用配置管理 — 从环境变量加载"""

import logging

from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)

# 占位/弱密钥黑名单 —— 非本地环境命中即拒绝启动
_PLACEHOLDER_SECRET = "dev-secret-key-change-in-production"
_PLACEHOLDER_ENC = "dev-encryption-key-32chars!!"
_PLACEHOLDER_DEEPSEEK = "sk-placeholder"


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
        """安全验证 — 敏感配置为占位/弱值时拒绝启动（development 仅告警不阻断）。

        原 P2-7 仅在 deployment_env == "production" 时校验，导致 staging/test 等非本地
        环境一旦对外暴露即可用公开占位 SECRET_KEY 伪造任意 JWT（含 role=admin）。
        现扩展为：除 development 外的所有环境都强制校验；development 下命中弱密钥仅告警。
        """
        is_dev = self.deployment_env == "development"

        def _fail_or_warn(name, current, placeholder, msg):
            if current == placeholder or (name == "SECRET_KEY" and len(current) < 16):
                full = f"{msg}（当前命中占位/弱值：deployment_env={self.deployment_env}）"
                if is_dev:
                    logger.warning("⚠️ 安全告警：%s", full)
                else:
                    raise ValueError(full)

        _fail_or_warn(
            "DEEPSEEK_API_KEY", self.deepseek_api_key, _PLACEHOLDER_DEEPSEEK,
            "DEEPSEEK_API_KEY 未配置或为占位值，请设置真实 API Key",
        )
        _fail_or_warn(
            "SECRET_KEY", self.secret_key, _PLACEHOLDER_SECRET,
            "SECRET_KEY 为默认占位值或长度不足16，存在 JWT 被伪造风险，请设置强随机值",
        )
        _fail_or_warn(
            "ENCRYPTION_KEY", self.encryption_key, _PLACEHOLDER_ENC,
            "ENCRYPTION_KEY 为默认占位值，请设置强随机值",
        )


settings = Settings()
