from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional


class Settings(BaseSettings):
    """应用配置，从 .env 文件加载"""

    # B 系统配置
    b_system_base_url: str = Field(..., alias="B_SYSTEM_BASE_URL")
    b_system_authorization: str = Field(..., alias="B_SYSTEM_AUTHORIZATION")
    b_system_cookie: Optional[str] = Field(None, alias="B_SYSTEM_COOKIE")

    # A 系统配置（纷享销客）
    a_system_base_url: str = Field(..., alias="A_SYSTEM_BASE_URL")
    a_system_app_id: str = Field(..., alias="A_SYSTEM_APP_ID")
    a_system_permanent_code: str = Field(..., alias="A_SYSTEM_PERMANENT_CODE")
    a_system_app_secret: str = Field(..., alias="A_SYSTEM_APP_SECRET")
    a_system_default_mobile: str = Field(..., alias="A_SYSTEM_DEFAULT_MOBILE")

    # 同步配置
    sync_interval_minutes: int = Field(3, alias="SYNC_INTERVAL_MINUTES")
    sync_batch_size: int = Field(100, alias="SYNC_BATCH_SIZE")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# 全局配置实例
settings = Settings()