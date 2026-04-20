import os
from dotenv import load_dotenv

load_dotenv()

REQUIRED_VARS = [
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_USER_ID",
    "GEMINI_API_KEY",
    "DATABASE_URL",
    "TIMEZONE",
    "MORNING_BRIEFING_TIME",
    "EOD_REFLECTION_TIME",
    "LORA_API_SECRET",
]

# Optional with defaults
WEEKLY_REVIEW_DAY = os.getenv("WEEKLY_REVIEW_DAY", "sunday")
HABIT_REMINDER_TIME = os.getenv("HABIT_REMINDER_TIME", "18:00")
JOURNAL_NIGHT_TIME = os.getenv("JOURNAL_NIGHT_TIME", "22:00")
TIMEZONE = os.getenv("TIMEZONE", "Europe/Bucharest")
MORNING_BRIEFING_TIME = os.getenv("MORNING_BRIEFING_TIME", "08:00")
EOD_REFLECTION_TIME = os.getenv("EOD_REFLECTION_TIME", "21:00")

# Optional Weather API
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
WEATHER_CITY = os.getenv("WEATHER_CITY", "Bucharest")

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

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_USER_ID = int(os.getenv("TELEGRAM_USER_ID"))
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
TIMEZONE = os.getenv("TIMEZONE", "Europe/Bucharest")
MORNING_BRIEFING_TIME = os.getenv("MORNING_BRIEFING_TIME", "08:00")
EOD_REFLECTION_TIME = os.getenv("EOD_REFLECTION_TIME", "21:00")
WEEKLY_REVIEW_DAY = os.getenv("WEEKLY_REVIEW_DAY", "sunday")
HABIT_REMINDER_TIME = os.getenv("HABIT_REMINDER_TIME", "18:00")
JOURNAL_NIGHT_TIME = os.getenv("JOURNAL_NIGHT_TIME", "22:00")
LORA_API_SECRET = os.getenv("LORA_API_SECRET")
