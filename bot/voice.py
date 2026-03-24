import os
import tempfile
import asyncio
from google import genai
from google.genai import types
from core.config import GEMINI_API_KEY

client = genai.Client(api_key=GEMINI_API_KEY)

async def transcribe_voice(update, context) -> str:
    """
    Download voice file from Telegram, transcribe with Gemini multimodal,
    and return the transcribed text.
    """
    voice = update.message.voice
    if not voice:
        return ""

    # Error: Voice file too large (>20MB)
    if voice.file_size > 20 * 1024 * 1024:
        raise ValueError("Mesajul vocal e prea lung — încearcă unul mai scurt 🎙")

    # 1. Get file from Telegram
    print(f"🎙 VOICE: Downloading file_id {voice.file_id}...", flush=True)
    voice_file = await context.bot.get_file(voice.file_id)
    
    # 2. Download to temp file
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp_file:
        tmp_path = tmp_file.name
    
    try:
        await voice_file.download_to_drive(tmp_path)
        print(f"🎙 VOICE: Downloaded to {tmp_path}, size={os.path.getsize(tmp_path)} bytes", flush=True)
        
        # 3. Upload to Gemini
        print(f"🎙 VOICE: Uploading to Gemini...", flush=True)
        myfile = client.files.upload(
            file=tmp_path,
            config=types.UploadFileConfig(mime_type="audio/ogg")
        )
        print(f"🎙 VOICE: Uploaded, URI: {myfile.uri}", flush=True)
        
        # 4. Call Gemini for transcription
        prompt = "Transcribe this voice message exactly as spoken. Return only the transcribed text, nothing else."
        
        print(f"🎙 VOICE: Requesting transcription...", flush=True)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_uri(file_uri=myfile.uri, mime_type=myfile.mime_type),
                        types.Part.from_text(text=prompt)
                    ]
                )
            ]
        )
        
        transcription = response.text.strip()
        print(f"🎙 VOICE: Transcription result: {repr(transcription)}", flush=True)
        return transcription

    except Exception as e:
        print(f"❌ VOICE ERROR: {e}", flush=True)
        raise
    finally:
        # 5. Delete the temp file after transcription
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
