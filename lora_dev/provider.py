"""Provider pentru planificarea Lora Dev: Groq opțional, Ollama fallback."""

from __future__ import annotations

import os
from typing import Any

import httpx
from dotenv import load_dotenv

from lora_dev.read_only import DevContext, render_plan_input

# Pentru CLI, cheia din repository-ul local trebuie să fie sursa explicită;
# altfel o variabilă veche exportată în shell poate rămâne activă.
load_dotenv(override=True)


async def generate_dev_plan(context: DevContext) -> str:
    """Generează un plan read-only; nu aplică patch-uri și nu execută tool-uri."""
    prompt = render_plan_input(context)
    groq_key = os.getenv("GROQ_API_KEY")
    if groq_key:
        return await _groq_plan(prompt, groq_key)
    return await _ollama_plan(prompt)


async def _groq_plan(prompt: str, api_key: str) -> str:
    model = os.getenv("GROQ_DEV_MODEL", "openai/gpt-oss-20b")
    payload: dict[str, Any] = {
        "model": model,
        "temperature": 0.1,
        "max_tokens": 1800,
        "messages": [
            {"role": "system", "content": "Ești Lora Dev. Analizează problema și returnează un plan tehnic scurt, fără a pretinde că ai modificat codul. Citește SOURCE EXCERPTS înainte de concluzii. Folosește doar rute, fișiere, funcții și tabele care apar literal în context. Nu inventa nume și nu descrie pași de tip 'deschide fișierul' fără să citezi ce ai găsit. Separă explicit FAPTE CONFIRMATE, IPOTEZE și ÎNTREBĂRI. Dacă nu există dovadă suficientă pentru cauză, răspunde 'Cauza nu poate fi confirmată din contextul colectat' și cere logul exact al requestului."},
            {"role": "user", "content": prompt},
        ],
    }
    async with httpx.AsyncClient(timeout=45) as client:
        response = await client.post("https://api.groq.com/openai/v1/chat/completions", headers={"Authorization": f"Bearer {api_key}"}, json=payload)
        response.raise_for_status()
        body = response.json()
        choice = (body.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        content = message.get("content") or message.get("reasoning") or choice.get("text")
        if not content:
            raise RuntimeError("Groq a răspuns fără conținut; verifică modelul și quota")
        return str(content)


async def _ollama_plan(prompt: str) -> str:
    host = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
    model = os.getenv("OLLAMA_DEV_MODEL", os.getenv("OLLAMA_MODEL", "llama3.2:3b"))
    payload = {"model": model, "prompt": f"Ești Lora Dev. Returnează un plan tehnic scurt, fără modificări de cod. Folosește doar informații confirmate în context și marchează ipotezele.\n\n{prompt}", "stream": False}
    async with httpx.AsyncClient(timeout=90) as client:
        response = await client.post(f"{host}/api/generate", json=payload)
        response.raise_for_status()
        return response.json().get("response", "")
