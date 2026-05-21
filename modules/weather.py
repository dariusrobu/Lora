from typing import Optional, Dict, Any, Tuple
import httpx
from core.config import OPENWEATHER_API_KEY, WEATHER_CITY


async def handle_weather_intent(
    pool, intent: str, data: Dict[str, Any]
) -> Tuple[str, Any, Optional[int]]:
    """Handler principal pentru modulul de vreme."""
    if intent == "get_weather":
        from db.queries.profile import get_user_profile
        from core.config import TELEGRAM_USER_ID
        
        profile = await get_user_profile(pool, TELEGRAM_USER_ID)
        lat = profile.get("latitude")
        lon = profile.get("longitude")
        
        if lat and lon:
            reply = await get_weather_summary(lat=float(lat), lon=float(lon))
        else:
            city = data.get("city", WEATHER_CITY)
            reply = await get_weather_summary(city=city)
            
        if not reply:
            return "Nu am putut accesa datele meteo. Verifică API KEY-ul.", None, None
        return reply, None, None

    return "Modulul weather este pregătit!", None, None


async def get_weather_summary(city: str = None, lat: float = None, lon: float = None) -> Optional[str]:
    """
    Fetches weather data from OpenWeatherMap using city name or coordinates.
    """
    if not OPENWEATHER_API_KEY:
        return None

    if lat is not None and lon is not None:
        url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}&units=metric&lang=ro"
    else:
        target_city = city or "Sasciori"
        url = f"https://api.openweathermap.org/data/2.5/weather?q={target_city}&appid={OPENWEATHER_API_KEY}&units=metric&lang=ro"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10.0)
            if response.status_code == 200:
                data = response.json()
                main = data.get("main", {})
                weather = data.get("weather", [{}])[0]
                name = data.get("name", "locația ta")
                temp = round(main.get("temp", 0))
                feels_like = round(main.get("feels_like", 0))
                desc = weather.get("description", "cer variabil")

                return (
                    f"Vremea în {name}: {desc}, {temp}°C (se simte ca {feels_like}°C)."
                )
            else:
                print(f"Weather API error: {response.status_code} - {response.text}")
                return None
    except Exception as e:
        print(f"Weather fetch exception: {e}")
        return None


async def check_weather_for_alerts(lat: float, lon: float) -> Optional[str]:
    """
    Checks for rain or extreme weather and returns a warning message if found.
    """
    if not OPENWEATHER_API_KEY:
        return None

    url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}&units=metric&lang=ro"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10.0)
            if response.status_code == 200:
                data = response.json()
                weather_list = data.get("weather", [])
                if not weather_list:
                    return None
                
                main_weather = weather_list[0]
                weather_id = main_weather.get("id", 800)
                desc = main_weather.get("description", "").capitalize()
                
                # OpenWeather IDs for Rain (5xx) and Storms (2xx) and Snow (6xx)
                # https://openweathermap.org/weather-conditions
                if 200 <= weather_id < 700:
                    icon = "⛈️" if weather_id < 300 else "🌧️" if weather_id < 600 else "❄️"
                    return f"{icon} *Alertă Meteo:* {desc} în zona ta. Mai bine te pregătești!"
                
            return None
    except Exception as e:
        print(f"Weather alert check exception: {e}")
        return None

async def undo_last_action(pool, intent: str, item_id: int) -> Tuple[bool, str]:
    return False, "Anularea nu este disponibilă pentru vreme, fiind o acțiune de citire."

