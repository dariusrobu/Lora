from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
from lora_api.auth import get_current_user
from lora_api.database import get_pool
from lora_api.serializers import clean_dict
from lora_api.config import TELEGRAM_USER_ID

router = APIRouter(prefix="/api", tags=["profile"])


class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    timezone: Optional[str] = None
    tone: Optional[str] = None
    morning_time: Optional[str] = None
    eod_time: Optional[str] = None
    preferred_tone: Optional[str] = None
    active_hours_start: Optional[str] = None
    active_hours_end: Optional[str] = None
    university_name: Optional[str] = None
    faculty: Optional[str] = None
    specialization: Optional[str] = None
    study_year: Optional[int] = None
    study_group: Optional[str] = None
    water_target_ml: Optional[int] = None
    personal_notes: Optional[str] = None
    llm_provider: Optional[str] = None
    llm_host: Optional[str] = None
    llm_model: Optional[str] = None
    gemini_api_key: Optional[str] = None
    city_name: Optional[str] = None
    home_latitude: Optional[float] = None
    home_longitude: Optional[float] = None
    is_at_home: Optional[bool] = None
    units: Optional[str] = None
    language: Optional[str] = None
    week_start_day: Optional[str] = None
    currency: Optional[str] = None
    dietary_preferences: Optional[str] = None
    notification_config: Optional[dict] = None


@router.get("/profile")
async def get_profile(user=Depends(get_current_user)):
    import db.queries.profile as q
    pool = await get_pool()
    row = await q.get_user_profile(pool, TELEGRAM_USER_ID)
    return clean_dict(dict(row)) if row else {}


@router.put("/profile")
async def update_profile(body: ProfileUpdate, user=Depends(get_current_user)):
    import db.queries.profile as q
    pool = await get_pool()
    kwargs = {k: v for k, v in body.model_dump(exclude_none=True).items() if v is not None}
    if not kwargs:
        raise HTTPException(status_code=400, detail="No fields to update")
    await q.update_user_profile(pool, TELEGRAM_USER_ID, **kwargs)
    row = await q.get_user_profile(pool, TELEGRAM_USER_ID)
    return clean_dict(dict(row)) if row else {}


class TestOllamaRequest(BaseModel):
    host: str
    model: str


@router.post("/integrations/test/ollama")
async def test_ollama(body: TestOllamaRequest, user=Depends(get_current_user)):
    import httpx
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{body.host.rstrip('/')}/api/generate",
                json={"model": body.model, "prompt": "ping", "stream": False},
            )
            if resp.status_code == 200:
                return {"ok": True, "message": f"Ollama {body.model} răspunde corect"}
            if resp.status_code == 404:
                return {"ok": False, "message": f"Modelul '{body.model}' nu a fost găsit", "hint": f"Instalează modelul: ollama pull {body.model}"}
            return {"ok": False, "message": f"Status: {resp.status_code}", "hint": "Verifică host-ul și portul. Default: http://localhost:11434"}
    except Exception as e:
        msg = str(e)
        exc_name = type(e).__name__
        if "ConnectError" in msg or "Connection refused" in msg or "Timeout" in msg or "Timeout" in exc_name:
            return {"ok": False, "message": msg or exc_name, "hint": "Pornește Ollama: ollama serve. Dacă e pe alt calculator, verifică host-ul."}
        return {"ok": False, "message": msg or exc_name, "hint": "Verifică host-ul și portul."}


class TestGeminiRequest(BaseModel):
    api_key: str


@router.post("/integrations/test/gemini")
async def test_gemini(body: TestGeminiRequest, user=Depends(get_current_user)):
    try:
        from google import genai
        client = genai.Client(api_key=body.api_key)
        resp = client.models.generate_content(model="gemini-2.0-flash", contents="ping")
        return {"ok": True, "message": "Gemini API răspunde corect"}
    except Exception as e:
        msg = str(e)
        if "API_KEY" in msg or "403" in msg or "PERMISSION_DENIED" in msg:
            return {"ok": False, "message": msg, "hint": "Cheia API nu e validă. Generează una nouă la https://aistudio.google.com/app/apikey"}
        return {"ok": False, "message": msg, "hint": "Verifică cheia API — fără spații, activă și corect copiată."}


@router.post("/integrations/test/weather")
async def test_weather(user=Depends(get_current_user)):
    from lora_api.config import OPENWEATHER_API_KEY
    import httpx
    if not OPENWEATHER_API_KEY:
        return {"ok": False, "message": "OPENWEATHER_API_KEY nu e configurat", "hint": "Adaugă OPENWEATHER_API_KEY în .env. Obții o cheie gratuită la https://openweathermap.org/api"}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://api.openweathermap.org/data/2.5/weather",
                params={"q": "Bucharest", "appid": OPENWEATHER_API_KEY, "units": "metric"},
            )
            if resp.status_code == 200:
                return {"ok": True, "message": "OpenWeather API răspunde corect"}
            if resp.status_code in (401, 403):
                return {"ok": False, "message": f"Status: {resp.status_code}", "hint": "Cheia API OpenWeather nu e validă. Verifică valoarea din .env."}
            return {"ok": False, "message": f"Status: {resp.status_code}", "hint": "Verifică conexiunea la api.openweathermap.org"}
    except Exception as e:
        msg = str(e)
        if "ConnectError" in msg or "Timeout" in msg:
            return {"ok": False, "message": msg, "hint": "Verifică conexiunea la api.openweathermap.org"}
        return {"ok": False, "message": msg, "hint": "Verifică conexiunea la internet."}
