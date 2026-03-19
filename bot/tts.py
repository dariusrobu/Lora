import edge_tts
import tempfile
import os
import re
from typing import Optional


# ─── Text Cleanup ─────────────────────────────────────────────────────────────

def _strip_markdown(text: str) -> str:
    """Remove Telegram MarkdownV2 markers."""
    text = text.replace("*", "").replace("`", "").replace("\\", "")
    text = re.sub(r'_+', '', text)          # italic/underline
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)  # [label](url) → label
    return text


def _strip_urls(text: str) -> str:
    """Remove URLs that would sound terrible when read aloud."""
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'www\.\S+', '', text)
    return text


def _strip_emojis(text: str) -> str:
    """Remove emoji characters that TTS reads as gibberish or silence."""
    # Covers most Unicode emoji ranges
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map
        "\U0001F1E0-\U0001F1FF"  # flags
        "\U00002700-\U000027BF"  # dingbats
        "\U0001F900-\U0001F9FF"  # supplemental symbols
        "\U00002600-\U000026FF"  # misc symbols
        "\U0000200D"             # zero-width joiner
        "\U0000FE0F"             # variation selector
        "⚠️✅❌💡💸💰📋📅✅⬜🔥☀️🌙🎙️📊📜🌦️"
        "]+",
        flags=re.UNICODE
    )
    return emoji_pattern.sub('', text)


def _strip_special_chars(text: str) -> str:
    """Remove characters that produce odd TTS artefacts."""
    # Remove bullet-like chars and Markdown heading markers
    text = re.sub(r'[•·#►▶–—]', ' ', text)
    # Remove lines that are pure separators (---  ===  ***)
    text = re.sub(r'^[-=*_]{3,}$', '', text, flags=re.MULTILINE)
    # Collapse multiple spaces / blank lines
    text = re.sub(r'  +', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text


def _expand_abbreviations(text: str) -> str:
    """Expand temperatures, currencies, times for natural Romanian TTS."""
    text = re.sub(r'(\d+)°C', r'\1 de grade Celsius', text)
    text = re.sub(r'(\d+)°', r'\1 de grade', text)
    text = re.sub(r'(\d+)\s*RON', r'\1 de lei', text)
    text = re.sub(r'(\d{1,2}):(\d{2})', r'ora \1 și \2', text)
    return text


def _phonetic_romglish(text: str) -> str:
    """Transliterate English tech terms for the Romanian TTS voice."""
    replacements: dict[str, str] = {
        r'\bdeadline-ul\b': 'dedlain-ul',
        r'\bdeadline\b': 'dedlain',
        r'\btask-ul\b': 'tasc-ul',
        r'\btask-urile\b': 'tasc-urile',
        r'\btasks\b': 'tăscuri',
        r'\btask\b': 'tasc',
        r'\bhabit-urile\b': 'hebit-urile',
        r'\bhabit-ul\b': 'hebit-ul',
        r'\bhabits\b': 'hebituri',
        r'\bhabit\b': 'hebit',
        r'\bmeeting\b': 'miting',
        r'\bsetup\b': 'setap',
        r'\bfocus\b': 'focăs',
        r'\bbriefing\b': 'brifing',
        r'\bpodcast\b': 'podcast',
        r'\bfeedback\b': 'fidbec',
        r'\banyway\b': 'eniuei',
        r'\bcool\b': 'cul',
        r'\bby the way\b': 'bai dă uei',
        r'\bnews\b': 'niuz',
        r'\bupdate\b': 'apdeit',
        r'\bjournal\b': 'jurnal',
        r'\bscheduling\b': 'scediuling',
        r'\bAI\b': 'A I',
        r'\bA\.?I\.?\b': 'A I',
        r'\bChatGPT\b': 'Ceat Ge Pe Te',
        r'\bGemini\b': 'Gemenai',
        r'\bGoogle\b': 'Gugăl',
        r'\bworkflow-ul\b': 'uorcflău-ul',
        r'\bworkflow\b': 'uorcflău',
        r'\bdeep work\b': 'dip uorc',
        r'\bpriority\b': 'praioriti',
        r'\boverdue\b': 'overdiu',
        r'\bcash flow\b': 'caș flău',
        r'\bbudget\b': 'baget',
        r'\btool\b': 'tul',
        r'\bhacking\b': 'heching',
        r'\bhacker\b': 'hecher',
        r'\bcontent\b': 'contant',
        r'\bmarketing\b': 'marketing',
        r'\bperformance\b': 'performans',
        r'\bdeveloper\b': 'develăpăr',
        r'\bmanagement\b': 'manajment',
        r'\bsync\b': 'sinc',
        r'\bgym\b': 'gim',
        r'\bheadlines\b': 'hedlains',
        r'\befficiency\b': 'efișăn-si',
        r'\bautomate\b': 'otomeit',
        r'\bprivacy\b': 'praivasi',
        r'\bproject\b': 'proiect',
        r'\bcheck-in\b': 'cec-in',
        r'\bcheck in\b': 'cec in',
    }
    for pattern, replacement in replacements.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text


def _add_natural_pauses(text: str) -> str:
    """Insert breathing room between sentences for a more conversational pace.

    Uses ellipsis-space '... ' which edge-tts treats as a brief pause.
    Longer pauses ('... ... ') are added after paragraph breaks.
    """
    # Sentence-level pauses
    text = re.sub(r'([.!?])\s+', r'\1 ... ', text)
    # Paragraph-level pauses (double newline → longer breath)
    text = re.sub(r'\n\n+', ' ... ... \n', text)
    # Single newlines → short pause
    text = re.sub(r'\n', ' ... ', text)
    # Clean up multiple consecutive pauses
    text = re.sub(r'(\.\.\. ){3,}', '... ... ', text)
    return text.strip()


def preprocess_text_for_tts(text: str) -> str:
    """Full pipeline: strip → expand → phonetics → pauses.

    Used for generic TTS (actions, short replies).
    """
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


def prepare_podcast_text(text: str) -> str:
    """Extended pipeline for podcast TTS — includes emoji/URL stripping and
    stronger pause insertion suited for longer narrated content.

    This is what gets passed to text_to_speech() for briefings and EOD.
    """
    if not text:
        return ""
    text = _strip_markdown(text)
    text = _strip_urls(text)
    text = _strip_emojis(text)
    text = _strip_special_chars(text)
    text = _expand_abbreviations(text)
    text = _phonetic_romglish(text)

    # For podcasts, insert slightly longer pauses at section boundaries
    # (detected by lines that look like section headers — short lines ending with ':')
    lines = text.splitlines()
    processed_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            processed_lines.append('... ...')
            continue
        # Short lines (likely section titles) get a longer breath after them
        if len(stripped) < 60 and stripped.endswith(':'):
            processed_lines.append(stripped + ' ...')
        else:
            processed_lines.append(stripped)
    text = ' '.join(processed_lines)

    # Sentence-level pauses
    text = re.sub(r'([.!?])\s+', r'\1 ... ', text)
    # Clean up excessive pauses
    text = re.sub(r'(\.\.\. ){3,}', '... ... ', text)
    return text.strip()


# ─── TTS Engine ───────────────────────────────────────────────────────────────

async def text_to_speech(
    text: str,
    filename: Optional[str] = None,
    podcast_mode: bool = False,
) -> str:
    """Convert text to speech using edge-tts.

    Args:
        text: Raw text (MarkdownV2 and emojis still present — cleaned internally).
        filename: Optional output path. Defaults to a temp .mp3 file.
        podcast_mode: If True, uses prepare_podcast_text() for deeper cleaning
                      and slightly slower rate suited for narration.

    Returns:
        Absolute path to the generated audio file.
    """
    VOICE = "ro-RO-AlinaNeural"

    if podcast_mode:
        processed_text = prepare_podcast_text(text)
        rate = "-15%"   # slightly slower for narration
        pitch = "+1Hz"
    else:
        processed_text = preprocess_text_for_tts(text)
        rate = "-10%"
        pitch = "+2Hz"

    if not processed_text:
        # Fallback so we never pass empty string to edge-tts
        processed_text = "Lora este activ."

    if not filename:
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        filename = temp_file.name
        temp_file.close()

    print(f"DEBUG: edge_tts.Communicate starting | mode={'podcast' if podcast_mode else 'normal'} | chars={len(processed_text)}", flush=True)
    try:
        communicate = edge_tts.Communicate(processed_text, VOICE, rate=rate, pitch=pitch)
        await communicate.save(filename)
        print(f"DEBUG: edge_tts saved → {filename} (exists={os.path.exists(filename)})", flush=True)
    except Exception as e:
        print(f"DEBUG: edge_tts FAILED: {e}", flush=True)
        raise

    return filename
