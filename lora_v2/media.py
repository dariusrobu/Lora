"""Private local media storage and offline interpretation for Telegram captures."""

import asyncio
import io
import uuid
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

from PIL import Image, ImageOps
from faster_whisper import WhisperModel
from ollama import AsyncClient

from lora_v2.agent import Interpretation
from lora_v2.config import Settings


def save_photo(settings: Settings, data: bytes) -> str:
    if len(data) > 10 * 1024 * 1024:
        raise ValueError("Fotografia este prea mare")
    with Image.open(io.BytesIO(data)) as source:
        image = ImageOps.exif_transpose(source)
        if image.width * image.height > 25_000_000:
            raise ValueError("Fotografia este prea mare")
        image.thumbnail((1600, 1600))
        output = io.BytesIO()
        image.convert("RGB").save(output, format="JPEG", quality=86, optimize=True)
    directory = Path(settings.media_dir).resolve()
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = directory / f"{uuid.uuid4()}.jpg"
    path.write_bytes(output.getvalue())
    path.chmod(0o600)
    return str(path)


def save_voice(settings: Settings, data: bytes) -> str:
    if len(data) > 20 * 1024 * 1024:
        raise ValueError("Mesajul vocal este prea mare")
    directory = Path(settings.media_dir).resolve()
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = directory / f"{uuid.uuid4()}.ogg"
    path.write_bytes(data)
    path.chmod(0o600)
    return str(path)


def _trusted_path(settings: Settings, reference: str, suffix: str) -> Path:
    directory = Path(settings.media_dir).resolve()
    path = Path(reference).resolve()
    if path.parent != directory or path.suffix != suffix:
        raise ValueError("Invalid media reference")
    return path


@lru_cache(maxsize=2)
def _whisper(name: str) -> WhisperModel:
    return WhisperModel(name, device="cpu", compute_type="int8")


def _transcribe(path: Path, model_name: str) -> str:
    segments, _ = _whisper(model_name).transcribe(str(path), language="ro", beam_size=3)
    return " ".join(segment.text.strip() for segment in segments).strip()


async def transcribe_voice(settings: Settings, reference: str) -> str:
    path = _trusted_path(settings, reference, ".ogg")
    return await asyncio.wait_for(
        asyncio.to_thread(_transcribe, path, settings.whisper_model), timeout=120
    )


async def interpret_photo(
    settings: Settings, reference: str, caption: str, now: datetime | None = None,
) -> Interpretation:
    """Estimate food visually; uncertainty is mandatory and the user can edit every value."""
    path = _trusted_path(settings, reference, ".jpg")
    prompt = (
        "Analizează fotografia ca asistent de jurnal alimentar, în română. "
        f"Ora fotografiei: {(now or datetime.now(ZoneInfo(settings.timezone))).isoformat()}. "
        "Dacă este mâncare, întoarce o singură acțiune log_meal cu eaten_at la ora fotografiei, "
        "estimate_source='photo', photo_ref setat la referința dată și items cu alimentele observabile. "
        "Estimează gramajul și macro-urile numai dacă le poți aproxima rezonabil; "
        "nu prezenta valorile ca exacte. Dacă porția sau alimentul nu pot fi identificate, "
        "setează missing_information și confidence sub 0.85. "
        "Dacă imaginea nu arată mâncare, nu crea acțiuni. "
        f"Referință: {reference}. Context utilizator: {caption or 'fără descriere'}. "
        "Fiecare dată trebuie să includă offsetul Europe/Bucharest. Răspunde strict în schema JSON."
    )
    client = AsyncClient(host=settings.ollama_host)
    response = await asyncio.wait_for(
        client.chat(
            model=settings.ollama_vision_model,
            messages=[{"role": "user", "content": prompt, "images": [path.read_bytes()]}],
            format=Interpretation.model_json_schema(),
            options={"temperature": 0.1},
        ),
        timeout=90,
    )
    interpretation = Interpretation.model_validate_json(response["message"]["content"])
    for candidate in interpretation.actions:
        if candidate.type == "log_meal":
            candidate.estimate_source = "photo"
            candidate.photo_ref = reference
    return interpretation
