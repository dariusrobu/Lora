"""Local-only voice transcription for Telegram messages."""

import asyncio
import os
import tempfile
from typing import Any, Tuple

from core.config import LOCAL_STT_COMPUTE_TYPE, LOCAL_STT_DEVICE, LOCAL_STT_MODEL

_whisper_model: Any = None


def _get_local_stt_model() -> Any:
    """Lazily load Faster-Whisper; it never sends the audio to a cloud API."""
    global _whisper_model
    if _whisper_model is not None:
        return _whisper_model

    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError(
            "Transcrierea locală nu este instalată. Instalează dependențele Lora "
            "și descarcă un model Faster-Whisper local."
        ) from exc

    _whisper_model = WhisperModel(
        LOCAL_STT_MODEL,
        device=LOCAL_STT_DEVICE,
        compute_type=LOCAL_STT_COMPUTE_TYPE,
    )
    return _whisper_model


def _transcribe_file(path: str) -> str:
    model = _get_local_stt_model()
    segments, _info = model.transcribe(
        path,
        language="ro",
        vad_filter=True,
        beam_size=5,
        initial_prompt=(
            "Română și Romglish: task, meeting, review, proiect, reminder, "
            "calendar, Cluj."
        ),
    )
    return " ".join(segment.text.strip() for segment in segments).strip()


async def transcribe_voice(update: Any, context: Any) -> Tuple[str, str]:
    """Download from Telegram, transcribe on this machine, then delete the file."""
    voice = update.message.voice
    if not voice:
        return "", ""
    if voice.file_size and voice.file_size > 20 * 1024 * 1024:
        raise ValueError("Mesajul vocal e prea lung — încearcă unul mai scurt. 🎙")

    voice_file = await context.bot.get_file(voice.file_id)
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp_file:
        tmp_path = tmp_file.name

    try:
        await voice_file.download_to_drive(tmp_path)
        transcription = await asyncio.to_thread(_transcribe_file, tmp_path)
        if not transcription:
            raise ValueError("Nu am putut înțelege mesajul vocal.")

        # Return the raw transcript.  The handler performs exactly one
        # normalization pass; normalizing here as well caused two local LLM
        # rewrites and could turn an unclear phrase into a different intent.
        return transcription, f"local://faster-whisper/{LOCAL_STT_MODEL}"
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
