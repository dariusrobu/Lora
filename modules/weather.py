from typing import Optional, Dict, Any, Tuple
import httpx
from core.config import OPENWEATHER_API_KEY, WEATHER_CITY


async def handle_weather_intent(
    pool, intent: str, data: Dict[str, Any]
) -> Tuple[str, Any, Optional[int]]:
    """Handler principal pentru modulul de vreme."""
    if intent == "get_weather":
        city = data.get("city", WEATHER_CITY)
        reply = await get_weather_summary(city)
        if not reply:
            return "Nu am putut accesa datele meteo. Verifică API KEY-ul.", None, None
        return reply, None, None

    return "Modulul weather este pregătit!", None, None


async def get_weather_summary(city: str = WEATHER_CITY) -> Optional[str]:
    """
    Fetches weather data from OpenWeatherMap and returns a text summary.
    """
    if not OPENWEATHER_API_KEY:
        return None

    url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={OPENWEATHER_API_KEY}&units=metric&lang=ro"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10.0)
            if response.status_code == 200:
                data = response.json()
                main = data.get("main", {})
                weather = data.get("weather", [{}])[0]
                temp = round(main.get("temp", 0))
                feels_like = round(main.get("feels_like", 0))
                desc = weather.get("description", "cer variabil")

                return (
                    f"Vremea în {city}: {desc}, {temp}°C (se simte ca {feels_like}°C)."
                )
            else:
                print(f"Weather API error: {response.status_code} - {response.text}")
                return None
    except Exception as e:
        print(f"Weather fetch exception: {e}")
        return None
