from fastapi import APIRouter, Depends, Query
from lora_api.auth import get_current_user
from lora_api.config import OPENWEATHER_API_KEY

router = APIRouter(prefix="/api", tags=["weather"])

OWM_BASE = "https://api.openweathermap.org/data/2.5"


@router.get("/weather")
async def get_weather(lat: float = Query(...), lon: float = Query(...), user=Depends(get_current_user)):
    import aiohttp
    if not OPENWEATHER_API_KEY:
        return {"error": "OPENWEATHER_API_KEY not configured"}

    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{OWM_BASE}/weather",
            params={"lat": lat, "lon": lon, "appid": OPENWEATHER_API_KEY, "units": "metric", "lang": "ro"},
        ) as resp:
            current = await resp.json()

        async with session.get(
            f"{OWM_BASE}/forecast",
            params={"lat": lat, "lon": lon, "appid": OPENWEATHER_API_KEY, "units": "metric", "lang": "ro"},
        ) as resp:
            forecast_raw = await resp.json()

    c = current
    main = c.get("main", {})
    weather = c.get("weather", [{}])[0]
    wind = c.get("wind", {})
    sys = c.get("sys", {})

    daily: dict[str, dict] = {}
    for item in forecast_raw.get("list", []):
        date_str = item["dt_txt"][:10]
        if date_str not in daily:
            daily[date_str] = {
                "date": date_str,
                "temp_min": item["main"]["temp_min"],
                "temp_max": item["main"]["temp_max"],
                "condition": item["weather"][0]["description"],
                "icon": item["weather"][0]["icon"],
                "humidity": item["main"]["humidity"],
                "wind_speed": item["wind"]["speed"],
            }
        else:
            d = daily[date_str]
            d["temp_min"] = min(d["temp_min"], item["main"]["temp_min"])
            d["temp_max"] = max(d["temp_max"], item["main"]["temp_max"])

    forecast = list(daily.values())

    return {
        "current": {
            "temp": main.get("temp"),
            "feels_like": main.get("feels_like"),
            "temp_min": main.get("temp_min"),
            "temp_max": main.get("temp_max"),
            "humidity": main.get("humidity"),
            "pressure": main.get("pressure"),
            "visibility": c.get("visibility"),
            "wind_speed": wind.get("speed"),
            "wind_deg": wind.get("deg"),
            "condition": weather.get("description"),
            "icon": weather.get("icon"),
            "city": c.get("name"),
            "country": sys.get("country"),
            "sunrise": sys.get("sunrise"),
            "sunset": sys.get("sunset"),
        },
        "forecast": forecast,
    }


@router.get("/nearby")
async def get_nearby(lat: float = Query(...), lon: float = Query(...), radius: int = 1000, user=Depends(get_current_user)):
    import aiohttp
    overpass = f"[out:json];(node(around:{radius},{lat},{lon}););out;"
    async with aiohttp.ClientSession() as session:
        async with session.post("https://overpass-api.de/api/interpreter", data={"data": overpass}) as resp:
            data = await resp.json()
    return data.get("elements", [])
