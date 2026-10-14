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
OLLAMA_FOOD_VISION_MODEL = os.getenv("OLLAMA_FOOD_VISION_MODEL", OLLAMA_VISION_MODEL)
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")

# Local speech-to-text (Faster-Whisper). Inference stays on this machine.
LOCAL_STT_MODEL = os.getenv("LOCAL_STT_MODEL", "small")
LOCAL_STT_DEVICE = os.getenv("LOCAL_STT_DEVICE", "auto")
LOCAL_STT_COMPUTE_TYPE = os.getenv("LOCAL_STT_COMPUTE_TYPE", "int8")
# Ollama normalization can rewrite correct Romanian transcripts incorrectly;
# keep raw local STT by default and enable only for explicitly noisy audio.
VOICE_NORMALIZE = os.getenv("VOICE_NORMALIZE", "false").lower() == "true"

# Local Obsidian export. The vault is never uploaded by Lora.
OBSIDIAN_VAULT_PATH = os.getenv("OBSIDIAN_VAULT_PATH", os.path.join(os.getcwd(), "obsidian"))
OBSIDIAN_SYNC_ENABLED = os.getenv("OBSIDIAN_SYNC_ENABLED", "true").lower() == "true"
OBSIDIAN_SYNC_INTERVAL_MINUTES = int(os.getenv("OBSIDIAN_SYNC_INTERVAL_MINUTES", "15"))
OBSIDIAN_SYNC_INCLUDE_FINANCE = os.getenv("OBSIDIAN_SYNC_INCLUDE_FINANCE", "true").lower() == "true"
OBSIDIAN_SYNC_INCLUDE_PERSONAL_NOTES = os.getenv("OBSIDIAN_SYNC_INCLUDE_PERSONAL_NOTES", "true").lower() == "true"
OBSIDIAN_PROCESS_INTERVAL_MINUTES = int(os.getenv("OBSIDIAN_PROCESS_INTERVAL_MINUTES", "15"))
OBSIDIAN_PROCESS_MODEL = os.getenv("OBSIDIAN_PROCESS_MODEL", "llama3.2:3b")
RECEIPTS_STORAGE_PATH = os.getenv(
    "RECEIPTS_STORAGE_PATH", os.path.join(os.getcwd(), "data", "finance", "receipts")
)

# Human-in-the-loop confirmation for database writes is on by default.  This
# protects personal data when a local model misclassifies an ambiguous message.
REQUIRE_CONFIRMATION = os.getenv("REQUIRE_CONFIRMATION", "true").lower() == "true"

# Optional Weather API
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
WEATHER_CITY = os.getenv("WEATHER_CITY", "Sasciori")

# Optional Nutritionix API
NUTRITIONIX_APP_ID = os.getenv("NUTRITIONIX_APP_ID")
NUTRITIONIX_API_KEY = os.getenv("NUTRITIONIX_API_KEY")

# Explicit opt-in: only food names/barcodes leave the machine, never photos.
NUTRITION_CLOUD_ENABLED = os.getenv("NUTRITION_CLOUD_ENABLED", "false").lower() == "true"
USDA_FDC_API_KEY = os.getenv("USDA_FDC_API_KEY") or os.getenv("USDA_FDC_API", "")
NUTRITION_CACHE_PATH = os.getenv("NUTRITION_CACHE_PATH", os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "nutrition", "references.sqlite3"))
NUTRITION_CACHE_TTL_DAYS = max(1, int(os.getenv("NUTRITION_CACHE_TTL_DAYS", "30")))
OPENFOODFACTS_USER_AGENT = os.getenv("OPENFOODFACTS_USER_AGENT", "Lora/1.0 (personal nutrition assistant)")

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
MORNING_BRIEFING_TIME = os.getenv("MORNING_BRIEFING_TIME", "07:00")
EOD_REFLECTION_TIME = os.getenv("EOD_REFLECTION_TIME", "21:00")
WEEKLY_REVIEW_DAY = os.getenv("WEEKLY_REVIEW_DAY", "sunday")
HABIT_REMINDER_TIME = os.getenv("HABIT_REMINDER_TIME", "18:00")
JOURNAL_NIGHT_TIME = os.getenv("JOURNAL_NIGHT_TIME", "22:00")

# ── Auth / Secrets ───────────────────────────────────────────────────────────
LORA_API_SECRET = os.getenv("LORA_API_SECRET")

# ── University ───────────────────────────────────────────────────────────────
SEMESTER_START_DATE = os.getenv("SEMESTER_START_DATE", "2026-09-28")

# ── iCloud ────────────────────────────────────────────────────────────────────
ICLOUD_USERNAME = os.getenv("ICLOUD_USERNAME")
ICLOUD_APP_PASSWORD = os.getenv("ICLOUD_APP_PASSWORD")
ICLOUD_CALENDAR_NAME = os.getenv("ICLOUD_CALENDAR_NAME", "Lora")
CALENDAR_SYNC_INTERVAL = int(os.getenv("CALENDAR_SYNC_INTERVAL_MINUTES", "60"))

# Dedicated calendar endpoint token — never derived from the public bot ID
CALENDAR_SECRET = os.getenv("CALENDAR_SECRET") or secrets.token_urlsafe(32)

# Task cleanup — auto-delete completed tasks after N days
TASK_CLEANUP_DAYS = int(os.getenv("TASK_CLEANUP_DAYS", "30"))

# TTS — KittenTTS model and voice for English synthesis
KITTEN_TTS_MODEL = os.getenv("KITTEN_TTS_MODEL", "KittenML/kitten-tts-mini-0.8")
KITTEN_TTS_VOICE = os.getenv("KITTEN_TTS_VOICE", "Luna")
EDGE_TTS_VOICE = os.getenv("EDGE_TTS_VOICE", "ro-RO-AlinaNeural")

# ── Email Integrations ────────────────────────────────────────────────────────
GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
OUTLOOK_USER = os.getenv("OUTLOOK_USER")
OUTLOOK_APP_PASSWORD = os.getenv("OUTLOOK_APP_PASSWORD")
