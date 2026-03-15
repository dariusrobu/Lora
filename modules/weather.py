import httpx
from typing import Optional, Dict, Any
from core.config import OPENWEATHER_API_KEY, WEATHER_CITY

async def get_weather_summary(city: str = WEATHER_CITY) -> Optional[str]:
    """
    Fetches weather data from OpenWeatherMap and returns a text summary.
    """
    if not OPENWEATHER_API_KEY:
        return None
        
    url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={OPENWEATHER_API_KEY}&units=metric&lang=ro"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10.0)
            if response.status_code == 200:
                data = response.json()
                main = data.get('main', {})
                weather = data.get('weather', [{}])[0]
                temp = main.get('temp')
                feels_like = main.get('feels_like')
                desc = weather.get('description', 'cer variabil')
                
                return f"Vremea în {city}: {desc}, {temp}°C (se simte ca {feels_like}°C)."
            else:
                print(f"Weather API error: {response.status_code} - {response.text}")
                return None
    except Exception as e:
        print(f"Weather fetch exception: {e}")
        return None
