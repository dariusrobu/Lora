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
        r'\bnews\b': 'niuz',
        r'\bsummarize\b': 'samăraiz',
        r'\bupdate\b': 'apdeit',
        r'\bnotes\b': 'noturi',
        r'\bjournal\b': 'jurnal',
        r'\bfinance\b': 'fainans',
        r'\bscheduling\b': 'scediuling',
        # Added replacements
        r'\bAI\b': 'A I',
        r'\bA\.?I\.?\b': 'A I',
        r'\bChatGPT\b': 'Ceat Ge Pe Te',
        r'\bGemini\b': 'Gemenai',
        r'\bGoogle\b': 'Gugăl',
        r'\bworkflow\b': 'uorcflău',
        r'\bworkflow-ul\b': 'uorcflău-ul',
        r'\bdeep work\b': 'dip uorc',
        r'\bpriority\b': 'praioriti',
        r'\boverdue\b': 'overdiu',
        r'\bcash flow\b': 'caș flău',
        r'\bbudget\b': 'baget',
        r'\btools\b': 'tuls',
        r'\btool\b': 'tul',
        r'\bhacking\b': 'heching',
        r'\bhacker\b': 'hecher',
        r'\bcontent\b': 'contant',
        r'\bcreation\b': 'crieișăn',
        r'\bmarketing\b': 'marketing',
        r'\btraffic\b': 'trafic',
        r'\bperformance\b': 'performans',
        r'\boptimization\b': 'optimaizeişăn',
        r'\bdeveloper\b': 'develăpăr',
        r'\bprofessional\b': 'profesiănal',
        r'\bsolutions\b': 'solușăns',
        r'\bsolution\b': 'solușăn',
        r'\bmanagement\b': 'manajment',
        r'\bsync\b': 'sinc',
        r'\bcaught up\b': 'cat ap',
        r'\bcatch up\b': 'ceaci ap',
        r'\bgym\b': 'gim',
        r'\breading\b': 'riding',
        r'\bduolingo\b': 'duolingo',
        r'\bchess\b': 'ces',
        r'\bheadlines\b': 'hedlains',
        r'\bbuzzword\b': 'baz uord',
        r'\befficiency\b': 'efişăn-si',
        r'\bautomate\b': 'otomeit',
        r'\bdrive\b': 'draiv',
        r'\bmetadata\b': 'metadata',
        r'\bsurveillance\b': 'surveilans',
        r'\bprivacy\b': 'praivasi',
        r'\bbill\b': 'bil',
        r'\b Studio\b': ' Studio',
        r'\bLimeWire\b': 'Laim uair',
    }
    
    for pattern, replacement in replacements.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    # 6. Add some natural pauses between sentences for better pacing
    text = text.replace(". ", ". ... ")
    text = text.replace("! ", "! ... ")
    text = text.replace("? ", "? ... ")

    return text

async def text_to_speech(text: str, filename: str = None) -> str:
    """
    Converts text to speech using edge-tts.
    Returns the path to the generated mp3 file.
    """
    # Use Alina for a warm, premium Romanian voice
    VOICE = "ro-RO-AlinaNeural" 
    
    processed_text = preprocess_text_for_tts(text)
    
    # Prosody markers for edge-tts (some versions support simple markers or we just slow down the stream)
    # We use a slight rate reduction to make it more professional
    rate = "-10%"
    pitch = "+2Hz"
    
    if not filename:
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        filename = temp_file.name
        temp_file.close()

    print(f"DEBUG: edge_tts.Communicate starting for path: {filename}", flush=True)
    try:
        communicate = edge_tts.Communicate(processed_text, VOICE, rate=rate, pitch=pitch)
        await communicate.save(filename)
        print(f"DEBUG: edge_tts.Communicate saved successfully. File exists: {os.path.exists(filename)}", flush=True)
    except Exception as e:
        print(f"DEBUG: edge_tts.Communicate FAILED: {str(e)}", flush=True)
        raise
    
    return filename
