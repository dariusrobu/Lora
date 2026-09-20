import asyncio
import os
import re
import tempfile
from typing import Optional

from core.config import KITTEN_TTS_MODEL, KITTEN_TTS_VOICE


# ─── Lazy KittenTTS singleton ─────────────────────────────────────────────────

_kitten_model = None
_kitten_lock = asyncio.Lock()


async def _get_kitten():
    global _kitten_model
    if _kitten_model is not None:
        return _kitten_model
    async with _kitten_lock:
        if _kitten_model is not None:
            return _kitten_model
        try:
            # TTS is local-only: never trigger a Hugging Face metadata/download
            # request while the bot is starting. A missing local model falls back
            # to the existing edge-tts path below.
            os.environ.setdefault("HF_HUB_OFFLINE", "1")
            from kittentts import KittenTTS
            _kitten_model = await asyncio.wait_for(
                asyncio.to_thread(KittenTTS, KITTEN_TTS_MODEL),
                timeout=30,
            )
            print(f"🐱 KittenTTS loaded: {KITTEN_TTS_MODEL}", flush=True)
        except asyncio.TimeoutError:
            print("⚠️ KittenTTS load timed out after 30s", flush=True)
            _kitten_model = False
        except Exception as e:
            print(f"⚠️ KittenTTS load failed: {e}", flush=True)
            _kitten_model = False
    return _kitten_model


# ─── Language detection ────────────────────────────────────────────────────────

# Romanian diacritics + high-frequency words → strong signal
_RO_DIACRITICS = re.compile(r"[ăâîșțĂÂÎȘȚ]")
_RO_COMMON = re.compile(
    r"\b(?:și|în|pe|cu|la|să|pentru|din|prin|după|peste|fără|printr|dintr|într| acum|azi|mâine|așa|foarte|trebuie|poate|chiar|numai|decât|doar|când|cum|unde|acolo|aceasta|acest|câte|toate|unele|fiecare|orice|cineva|ceva|nimic|toți|mulți|puțini|uneori|mereu|niciodată|apoi|încă|deja|abia)\b",
    re.IGNORECASE,
)


def _is_romanian(text: str) -> bool:
    if not text:
        return False
    if _RO_DIACRITICS.search(text):
        return True
    matches = _RO_COMMON.findall(text)
    return len(matches) >= 2


# ─── Text Cleanup ─────────────────────────────────────────────────────────────


def _strip_markdown(text: str) -> str:
    text = text.replace("*", "").replace("`", "").replace("\\", "")
    text = re.sub(r"_+", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    return text


def _strip_urls(text: str) -> str:
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"www\.\S+", "", text)
    return text


def _strip_emojis(text: str) -> str:
    emoji_pattern = re.compile(
        "["
        "\U0001f600-\U0001f64f"
        "\U0001f300-\U0001f5ff"
        "\U0001f680-\U0001f6ff"
        "\U0001f1e0-\U0001f1ff"
        "\U00002700-\U000027bf"
        "\U0001f900-\U0001f9ff"
        "\U00002600-\U000026ff"
        "\U0000200d"
        "\U0000fe0f"
        "⚠️✅❌💡💸💰📋📅✅⬜🔥☀️🌙🎙️📊📜🌦️"
        "]+",
        flags=re.UNICODE,
    )
    return emoji_pattern.sub("", text)


def _strip_special_chars(text: str) -> str:
    text = re.sub(r"[•·#►▶–—]", " ", text)
    text = re.sub(r"^[-=*_]{3,}$", "", text, flags=re.MULTILINE)
    text = re.sub(r"  +", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def _expand_abbreviations(text: str) -> str:
    text = re.sub(r"(\d+)°C", r"\1 de grade Celsius", text)
    text = re.sub(r"(\d+)°", r"\1 de grade", text)
    text = re.sub(r"(\d+)\s*RON", r"\1 de lei", text)
    text = re.sub(r"(\d{1,2}):(\d{2})", r"ora \1 și \2", text)
    return text


def _expand_english(text: str) -> str:
    """Expand abbreviations for English TTS (KittenTTS)."""
    text = re.sub(r"(\d+)°C", r"\1 degrees Celsius", text)
    text = re.sub(r"(\d+)°", r"\1 degrees", text)
    text = re.sub(r"(\d+)\s*RON", r"\1 RON", text)
    text = re.sub(r"(\d{1,2}):(\d{2})", r"\1 \2", text)
    return text


def _phonetic_romglish(text: str) -> str:
    replacements = {
        r"\bdeadline-ul\b": "dedlain-ul",
        r"\bdeadline\b": "dedlain",
        r"\btask-ul\b": "tasc-ul",
        r"\btask-urile\b": "tasc-urile",
        r"\btasks\b": "tăscuri",
        r"\btask\b": "tasc",
        r"\bmeeting\b": "miting",
        r"\bsetup\b": "setap",
        r"\bfocus\b": "focăs",
        r"\bbriefing\b": "brifing",
        r"\bpodcast\b": "podcast",
        r"\bfeedback\b": "fidbec",
        r"\banyway\b": "eniuei",
        r"\bcool\b": "cul",
        r"\bby the way\b": "bai dă uei",
        r"\bnews\b": "niuz",
        r"\bupdate\b": "apdeit",
        r"\bjournal\b": "jurnal",
        r"\bscheduling\b": "scediuling",
        r"\bAI\b": "A I",
        r"\bA\.?I\.?\b": "A I",
        r"\bChatGPT\b": "Ceat Ge Pe Te",
        r"\bGemini\b": "Gemenai",
        r"\bGoogle\b": "Gugăl",
        r"\bworkflow-ul\b": "uorcflău-ul",
        r"\bworkflow\b": "uorcflău",
        r"\bdeep work\b": "dip uorc",
        r"\bpriority\b": "praioriti",
        r"\boverdue\b": "overdiu",
        r"\bcash flow\b": "caș flău",
        r"\bbudget\b": "baget",
        r"\btool\b": "tul",
        r"\bhacking\b": "heching",
        r"\bhacker\b": "hecher",
        r"\bcontent\b": "contant",
        r"\bmarketing\b": "marketing",
        r"\bperformance\b": "performans",
        r"\bdeveloper\b": "develăpăr",
        r"\bmanagement\b": "manajment",
        r"\bsync\b": "sinc",
        r"\bgym\b": "gim",
        r"\bheadlines\b": "hedlains",
        r"\befficiency\b": "efișăn-si",
        r"\bautomate\b": "otomeit",
        r"\bprivacy\b": "praivasi",
        r"\bproject\b": "proiect",
        r"\bcheck-in\b": "cec-in",
        r"\bcheck in\b": "cec in",
    }
    for pattern, replacement in replacements.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text


def _add_natural_pauses(text: str) -> str:
    text = re.sub(r"([.!?])\s+", r"\1 ... ", text)
    text = re.sub(r"\n\n+", " ... ... \n", text)
    text = re.sub(r"\n", " ... ", text)
    text = re.sub(r"(\.\.\. ){3,}", "... ... ", text)
    return text.strip()


def preprocess_text_for_tts(text: str) -> str:
    """Full pipeline for local text-to-speech."""
    if not text:
        return ""
    text = _strip_markdown(text)
    text = _strip_urls(text)
    text = _strip_emojis(text)
    text = _strip_special_chars(text)
    text = _expand_abbreviations(text)
    text = _phonetic_romglish(text)
    text = _add_natural_pauses(text)
    return text


def preprocess_text_english(text: str) -> str:
    """Preprocessing for English KittenTTS — lighter, no Romglish phonetics."""
    if not text:
        return ""
    text = _strip_markdown(text)
    text = _strip_urls(text)
    text = _strip_emojis(text)
    text = _strip_special_chars(text)
    text = _expand_english(text)
    return text


def prepare_podcast_text(text: str) -> str:
    """Extended pipeline for local podcast TTS."""
    if not text:
        return ""
    text = _strip_markdown(text)
    text = _strip_urls(text)
    text = _strip_emojis(text)
    text = _strip_special_chars(text)
    text = _expand_abbreviations(text)
    text = _phonetic_romglish(text)

    lines = text.splitlines()
    processed_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            processed_lines.append("... ...")
            continue
        if len(stripped) < 60 and stripped.endswith(":"):
            processed_lines.append(stripped + " ...")
        else:
            processed_lines.append(stripped)
    text = " ".join(processed_lines)

    text = re.sub(r"([.!?])\s+", r"\1 ... ", text)
    text = re.sub(r"(\.\.\. ){3,}", "... ... ", text)
    return text.strip()


# ─── TTS Engine ───────────────────────────────────────────────────────────────


async def text_to_speech(
    text: str,
    filename: Optional[str] = None,
    podcast_mode: bool = False,
    voice: str = "auto",
) -> str:
    """Convert text to speech locally with KittenTTS.

    Args:
        text: Raw text (MarkdownV2 and emojis cleaned internally).
        filename: Optional output path. Defaults to a temp file.
        podcast_mode: If True, uses podcast-specific cleaning.
        voice: Reserved for compatibility. Local synthesis uses the configured
            KittenTTS voice for every language.

    Returns:
        Absolute path to the generated audio file.
    """
    return await _synthesize_kitten(text, filename, podcast_mode)


async def _synthesize_edge(
    text: str,
    filename: Optional[str] = None,
    podcast_mode: bool = False,
    voice: str = "ro-RO-AlinaNeural",
) -> str:
    """Compatibility wrapper for callers that selected the retired cloud voice."""
    return await _synthesize_kitten(text, filename, podcast_mode)


async def _synthesize_kitten(
    text: str,
    filename: Optional[str] = None,
    podcast_mode: bool = False,
) -> str:
    """KittenTTS synthesis performed entirely on the local machine."""
    model = await _get_kitten()
    if not model:
        raise RuntimeError("Motorul local KittenTTS nu este disponibil.")

    processed_text = preprocess_text_for_tts(text) if _is_romanian(text) else preprocess_text_english(text)

    if not processed_text:
        processed_text = "Lora is active."

    if not filename:
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        filename = temp_file.name
        temp_file.close()

    print(
        f"DEBUG: KittenTTS start | mode={'podcast' if podcast_mode else 'normal'} | chars={len(processed_text)}",
        flush=True,
    )
    await asyncio.to_thread(
        model.generate_to_file,
        processed_text,
        filename,
        voice=KITTEN_TTS_VOICE,
        sample_rate=24000,
        clean_text=True,
    )
    return filename
