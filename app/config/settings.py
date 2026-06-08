from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = Field(default="development", alias="APP_ENV")
    app_timezone: str = Field(default="Asia/Shanghai", alias="APP_TIMEZONE")
    database_url: str = Field(default="sqlite:///./data/assistant.db", alias="DATABASE_URL")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    memory_file_path: str = Field(default="data/memory.md", alias="MEMORY_FILE_PATH")

    deepseek_api_key: str = Field(default="", alias="DEEPSEEK_API_KEY")
    deepseek_base_url: str = Field(default="https://api.deepseek.com", alias="DEEPSEEK_BASE_URL")
    deepseek_model: str = Field(default="deepseek-v4-pro", alias="DEEPSEEK_MODEL")
    deepseek_reasoning_effort: str = Field(default="high", alias="DEEPSEEK_REASONING_EFFORT")
    deepseek_thinking_enabled: bool = Field(default=True, alias="DEEPSEEK_THINKING_ENABLED")
    deepseek_max_tokens: int = Field(default=2048, alias="DEEPSEEK_MAX_TOKENS")
    deepseek_timeout_seconds: float = Field(default=30.0, alias="DEEPSEEK_TIMEOUT_SECONDS")

    feishu_app_id: str = Field(default="", alias="FEISHU_APP_ID")
    feishu_app_secret: str = Field(default="", alias="FEISHU_APP_SECRET")
    feishu_encrypt_key: str = Field(default="", alias="FEISHU_ENCRYPT_KEY")
    feishu_verification_token: str = Field(default="", alias="FEISHU_VERIFICATION_TOKEN")
    feishu_event_mode: str = Field(default="long_connection", alias="FEISHU_EVENT_MODE")
    feishu_webhook_path: str = Field(default="/webhooks/feishu", alias="FEISHU_WEBHOOK_PATH")
    feishu_allowed_open_id: str = Field(default="", alias="FEISHU_ALLOWED_OPEN_ID")
    feishu_allowed_chat_id: str = Field(default="", alias="FEISHU_ALLOWED_CHAT_ID")

    @property
    def is_test(self) -> bool:
        return self.app_env == "test"


@lru_cache
def get_settings() -> Settings:
    return Settings()
