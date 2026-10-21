"""Configuration for the isolated Lora v2 runtime."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    database_url: str
    telegram_bot_token: str
    telegram_user_id: int
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"
    timezone: str = "Europe/Bucharest"
    followup_hour: int = 20
    daily_agent_enabled: bool = True
    icloud_username: str = ""
    icloud_app_password: str = ""
    apple_reminders_list: str = "Lora v2"
    apple_sync_enabled: bool = False
    apple_calendar_name: str = "Lora v2 Calendar"
    apple_events_enabled: bool = False
    media_dir: str = "lora_v2/media"
    ollama_vision_model: str = "moondream"
    whisper_model: str = "base"
    nutrition_enabled: bool = False
    usda_api_key: str = ""
    nutrition_cache_path: str = "lora_v2/nutrition_references.sqlite3"
    nutrition_user_agent: str = "Lora/2.0 (personal nutrition assistant)"

    @classmethod
    def from_env(cls) -> "Settings":
        database_url = os.getenv("LORA_V2_DATABASE_URL", "")
        token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        user_id = os.getenv("TELEGRAM_USER_ID", "")
        if not database_url:
            raise ValueError("LORA_V2_DATABASE_URL is required; never reuse DATABASE_URL")
        if database_url == os.getenv("DATABASE_URL"):
            raise ValueError("Lora v2 must use a separate database")
        if not token or not user_id:
            raise ValueError("TELEGRAM_BOT_TOKEN and TELEGRAM_USER_ID are required")
        return cls(
            database_url=database_url,
            telegram_bot_token=token,
            telegram_user_id=int(user_id),
            ollama_host=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
            ollama_model=os.getenv("LORA_V2_OLLAMA_MODEL", "qwen2.5:7b"),
            timezone=os.getenv("TIMEZONE", "Europe/Bucharest"),
            followup_hour=int(os.getenv("LORA_V2_FOLLOWUP_HOUR", "20")),
            daily_agent_enabled=os.getenv("LORA_V2_DAILY_AGENT_ENABLED", "true").lower() == "true",
            icloud_username=os.getenv("ICLOUD_USERNAME", ""),
            icloud_app_password=os.getenv("ICLOUD_APP_PASSWORD", ""),
            apple_reminders_list=os.getenv("LORA_V2_APPLE_REMINDERS_LIST", "Lora v2"),
            apple_sync_enabled=os.getenv("LORA_V2_APPLE_SYNC_ENABLED", "false").lower() == "true",
            apple_calendar_name=os.getenv("LORA_V2_APPLE_CALENDAR_NAME", "Lora v2 Calendar"),
            apple_events_enabled=os.getenv("LORA_V2_APPLE_EVENTS_ENABLED", "false").lower() == "true",
            media_dir=os.getenv("LORA_V2_MEDIA_DIR", "lora_v2/media"),
            ollama_vision_model=os.getenv("LORA_V2_VISION_MODEL", "moondream"),
            whisper_model=os.getenv("LORA_V2_WHISPER_MODEL", "base"),
            nutrition_enabled=os.getenv("NUTRITION_CLOUD_ENABLED", "false").lower() == "true",
            usda_api_key=os.getenv("USDA_FDC_API_KEY") or os.getenv("USDA_FDC_API", ""),
            nutrition_cache_path=os.getenv("LORA_V2_NUTRITION_CACHE_PATH", "lora_v2/nutrition_references.sqlite3"),
            nutrition_user_agent=os.getenv("OPENFOODFACTS_USER_AGENT", "Lora/2.0 (personal nutrition assistant)"),
        )
