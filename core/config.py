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
    "HABIT_REMINDER_TIME",
    "WEEKLY_REVIEW_DAY",
]

# Optional Weather API
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
WEATHER_CITY = os.getenv("WEATHER_CITY", "Bucharest")

for var in REQUIRED_VARS:
    if not os.getenv(var):
        raise EnvironmentError(f"Missing required environment variable: {var}")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_USER_ID = int(os.getenv("TELEGRAM_USER_ID"))
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")
TIMEZONE = os.getenv("TIMEZONE", "Europe/Bucharest")
MORNING_BRIEFING_TIME = os.getenv("MORNING_BRIEFING_TIME", "08:00")
EOD_REFLECTION_TIME = os.getenv("EOD_REFLECTION_TIME", "21:00")
HABIT_REMINDER_TIME = os.getenv("HABIT_REMINDER_TIME", "18:00")
WEEKLY_REVIEW_DAY = os.getenv("WEEKLY_REVIEW_DAY", "sunday")
