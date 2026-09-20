import os
import secrets
from dotenv import load_dotenv

load_dotenv()

REQUIRED_VARS = [
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_USER_ID",
    "DATABASE_URL",
    "TIMEZONE",
    "MORNING_BRIEFING_TIME",
    "EOD_REFLECTION_TIME",
    "LORA_API_SECRET",
]

# Optional Ollama (local LLM)
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
OLLAMA_STRUCTURED_MODEL = os.getenv("OLLAMA_STRUCTURED_MODEL", "qwen2.5:7b")
OLLAMA_VISION_MODEL = os.getenv("OLLAMA_VISION_MODEL", "moondream")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")

# Local speech-to-text (Faster-Whisper). Inference stays on this machine.
LOCAL_STT_MODEL = os.getenv("LOCAL_STT_MODEL", "small")
LOCAL_STT_DEVICE = os.getenv("LOCAL_STT_DEVICE", "auto")
LOCAL_STT_COMPUTE_TYPE = os.getenv("LOCAL_STT_COMPUTE_TYPE", "int8")

# Human-in-the-loop confirmation for database writes is on by default.  This
# protects personal data when a local model misclassifies an ambiguous message.
REQUIRE_CONFIRMATION = os.getenv("REQUIRE_CONFIRMATION", "true").lower() == "true"

# Optional Weather API
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
WEATHER_CITY = os.getenv("WEATHER_CITY", "Sasciori")

# Optional Nutritionix API
NUTRITIONIX_APP_ID = os.getenv("NUTRITIONIX_APP_ID")
NUTRITIONIX_API_KEY = os.getenv("NUTRITIONIX_API_KEY")

# Council Multi-Agent System
COUNCIL_API_URL = os.getenv("COUNCIL_API_URL", "https://business-council.onrender.com")
COUNCIL_API_SECRET = os.getenv("COUNCIL_API_SECRET")
COUNCIL_GROUP_CHAT_ID = os.getenv("COUNCIL_GROUP_CHAT_ID")
CTO_BOT_USERNAME = os.getenv("CTO_BOT_USERNAME", "@cto_bot")


for var in REQUIRED_VARS:
    if not os.getenv(var):
        raise EnvironmentError(f"Missing required environment variable: {var}")

# ── Core (required) ──────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_USER_ID = int(os.getenv("TELEGRAM_USER_ID"))
DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# ── Timing (required but with sensible defaults) ─────────────────────────────
TIMEZONE = os.getenv("TIMEZONE", "Europe/Bucharest")
MORNING_BRIEFING_TIME = os.getenv("MORNING_BRIEFING_TIME", "08:00")
EOD_REFLECTION_TIME = os.getenv("EOD_REFLECTION_TIME", "21:00")
WEEKLY_REVIEW_DAY = os.getenv("WEEKLY_REVIEW_DAY", "sunday")
HABIT_REMINDER_TIME = os.getenv("HABIT_REMINDER_TIME", "18:00")
JOURNAL_NIGHT_TIME = os.getenv("JOURNAL_NIGHT_TIME", "22:00")

# ── Auth / Secrets ───────────────────────────────────────────────────────────
LORA_API_SECRET = os.getenv("LORA_API_SECRET")

# ── University ───────────────────────────────────────────────────────────────
SEMESTER_START_DATE = os.getenv("SEMESTER_START_DATE", "2026-02-23")

# ── iCloud ────────────────────────────────────────────────────────────────────
ICLOUD_USERNAME = os.getenv("ICLOUD_USERNAME")
ICLOUD_APP_PASSWORD = os.getenv("ICLOUD_APP_PASSWORD")
ICLOUD_CALENDAR_NAME = os.getenv("ICLOUD_CALENDAR_NAME", "Lora")
CALENDAR_SYNC_INTERVAL = int(os.getenv("CALENDAR_SYNC_INTERVAL_MINUTES", "15"))

# Dedicated calendar endpoint token — never derived from the public bot ID
CALENDAR_SECRET = os.getenv("CALENDAR_SECRET") or secrets.token_urlsafe(32)

# Task cleanup — auto-delete completed tasks after N days
TASK_CLEANUP_DAYS = int(os.getenv("TASK_CLEANUP_DAYS", "30"))

# TTS — KittenTTS model and voice for English synthesis
KITTEN_TTS_MODEL = os.getenv("KITTEN_TTS_MODEL", "KittenML/kitten-tts-mini-0.8")
KITTEN_TTS_VOICE = os.getenv("KITTEN_TTS_VOICE", "Luna")

# ── Email Integrations ────────────────────────────────────────────────────────
GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
OUTLOOK_USER = os.getenv("OUTLOOK_USER")
OUTLOOK_APP_PASSWORD = os.getenv("OUTLOOK_APP_PASSWORD")
