import os
from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    telegram_bot_token: str = Field(default="", validation_alias="TELEGRAM_BOT_TOKEN")
    telegram_channel_id: str = Field(default="", validation_alias="TELEGRAM_CHANNEL_ID")
    admin_chat_id: str = Field(default="", validation_alias="ADMIN_CHAT_ID")
    data_dir: str = Field(default="data", validation_alias="DATA_DIR")
    secret_key: str = Field(default="", validation_alias="SECRET_KEY")
    vapid_private_key: str = Field(default="", validation_alias="VAPID_PRIVATE_KEY")
    vapid_public_key: str = Field(default="", validation_alias="VAPID_PUBLIC_KEY")
    vapid_contact_email: str = Field(default="rekvizitor.ua@gmail.com", validation_alias="VAPID_CONTACT_EMAIL")
    schedule_api_url: str = Field(default="", validation_alias="SCHEDULE_API_URL")
    allowed_origins: str = Field(default="https://power.srvrs.top", validation_alias="ALLOWED_ORIGINS")
    port_binding: str = Field(default="127.0.0.1", validation_alias="PORT_BINDING")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore"
    }

# Create a global instance
settings = Settings()
