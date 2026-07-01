import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

LORA_API_SECRET = os.getenv("LORA_API_SECRET", "")
LORA_API_PASSWORD = os.getenv("LORA_API_PASSWORD", "")

JWT_SECRET = os.getenv("JWT_SECRET", LORA_API_SECRET)
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 72

API_PORT = int(os.getenv("API_PORT", "8088"))
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
NUTRITIONIX_APP_ID = os.getenv("NUTRITIONIX_APP_ID")
NUTRITIONIX_API_KEY = os.getenv("NUTRITIONIX_API_KEY")
TIMEZONE = os.getenv("TIMEZONE", "Europe/Bucharest")
TELEGRAM_USER_ID = int(os.getenv("TELEGRAM_USER_ID", "0"))
SEMESTER_START_DATE = os.getenv("SEMESTER_START_DATE", "2026-02-23")

# Home server
SERVER_IP = os.getenv("SERVER_IP", "192.168.1.15")
SERVER_SSH_USER = os.getenv("SERVER_SSH_USER", "robu")
SERVER_SSH_PASSWORD = os.getenv("SERVER_SSH_PASSWORD", "")
QBIT_USERNAME = os.getenv("QBIT_USERNAME", "robu")
QBIT_PASSWORD = os.getenv("QBIT_PASSWORD", "")
RADARR_API_KEY = os.getenv("RADARR_API_KEY", "")
SONARR_API_KEY = os.getenv("SONARR_API_KEY", "")
