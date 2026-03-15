import edge_tts
import tempfile
import os
import re

def preprocess_text_for_tts(text: str) -> str:
    """
    Cleans and expands text for more natural voicing by the Romanian TTS.
    Handles temperatures, times, currencies, and common English terms.
    """
    if not text:
        return ""

    # 1. Basic Markdown/Telegram cleanup
    text = text.replace("*", "").replace("`", "").replace("\\", "")
    
    # 2. Expand Temperature (e.g., 25°C -> 25 de grade Celsius)
    text = re.sub(r'(\d+)°C', r'\1 de grade Celsius', text)
    text = re.sub(r'(\d+)°', r'\1 de grade', text)
    
    # 3. Expand Currency (e.g., 100 RON -> 100 de lei)
    text = re.sub(r'(\d+)\s*RON', r'\1 de lei', text)
    
    # 4. Handle Time (e.g., 10:30 -> ora 10 și 30)
    # This is a bit simplistic but helps.
    text = re.sub(r'(\d{1,2}):(\d{2})', r'ora \1 și \2', text)

    # 5. Handle common Romglish terms phonetically for the Romanian voice
    # This is a "hack" to make English words sound recognizable when read by a Romanian voice.
    replacements = {
        r'\bdeadline\b': 'dedlain',
        r'\bdeadline-ul\b': 'dedlain-ul',
        r'\btasks\b': 'tăscuri',
        r'\btask\b': 'tasc',
        r'\bmeeting\b': 'miting',
        r'\bsetup\b': 'setap',
        r'\bfocus\b': 'focăs',
        r'\bbriefing\b': 'brifing',
        r'\bpodcast\b': 'podcast',
        r'\bfeedback\b': 'fidbec',
        r'\banyway\b': 'eniuei',
        r'\bcool\b': 'cul',
        r'\bby the way\b': 'bai dă uei',
    }
    
    for pattern, replacement in replacements.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    return text

async def text_to_speech(text: str, filename: str = None) -> str:
    """
    Converts text to speech using edge-tts.
    Returns the path to the generated mp3 file.
    """
    # Use Alina for a warm, premium Romanian voice
    VOICE = "ro-RO-AlinaNeural" 
    
    processed_text = preprocess_text_for_tts(text)
    
    if not filename:
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        filename = temp_file.name
        temp_file.close()

    communicate = edge_tts.Communicate(processed_text, VOICE)
    await communicate.save(filename)
    
    return filename
