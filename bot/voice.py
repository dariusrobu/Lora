import os
import tempfile
import asyncio
from google import genai
from google.genai import types
from core.config import GEMINI_API_KEY

client = genai.Client(api_key=GEMINI_API_KEY)


async def transcribe_voice(update, context) -> tuple[str, str]:
    """
    Download voice file from Telegram, transcribe with Gemini multimodal,
    and return a tuple of (transcription, file_uri).
    """
    voice = update.message.voice
    if not voice:
        return "", ""

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
        print(
            f"🎙 VOICE: Downloaded to {tmp_path}, size={os.path.getsize(tmp_path)} bytes",
            flush=True,
        )

        # 3. Upload to Gemini
        print("🎙 VOICE: Uploading to Gemini...", flush=True)
        myfile = await asyncio.to_thread(
            client.files.upload,
            file=tmp_path,
            config=types.UploadFileConfig(mime_type="audio/ogg"),
        )
        print(f"🎙 VOICE: Uploaded, URI: {myfile.uri}", flush=True)

        # 4. Call Gemini for transcription (still needed for UI/History)
        prompt = (
            "Transcribe this voice message in ROMANIAN. The user speaks Romanian. "
            "Clean up fillers like 'ăăă', 'îîî' but keep the natural flow. "
            "Return only the transcribed text, nothing else."
        )

        print("🎙 VOICE: Requesting transcription...", flush=True)
        response = await asyncio.wait_for(
            asyncio.to_thread(
                client.models.generate_content,
                model="gemini-2.5-flash",
                contents=[
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_uri(
                                file_uri=myfile.uri, mime_type=myfile.mime_type
                            ),
                            types.Part.from_text(text=prompt),
                        ],
                    )
                ],
            ),
            timeout=45.0,
        )

        transcription = response.text.strip()
        print(f"🎙 VOICE: Transcription result: {repr(transcription)}", flush=True)

        # 4.5 Post-processing transcription with Gemini to fix Romglish and project names
        pool = context.bot_data.get("pool") if context else None
        project_names = []
        if pool:
            try:
                async with pool.acquire() as conn:
                    rows = await conn.fetch(
                        "SELECT name FROM projects WHERE status != 'archived'"
                    )
                    project_names = [row["name"] for row in rows]
            except Exception as db_err:
                print(
                    f"⚠️ Failed to fetch projects for STT normalization: {db_err}",
                    flush=True,
                )

        lista_proiecte = (
            ", ".join(project_names) if project_names else "fără proiecte specifice"
        )

        post_prompt = (
            f"Corectează transcrierea următoare știind că userul vorbește Romglish "
            f"(română + termeni tehnici englezi). Proiectele cunoscute: {lista_proiecte}.\n"
            f"Corectează doar greșeli evidente de transcriere, nu modifica sensul.\n"
            f"Răspunde DOAR cu textul corectat."
        )

        try:
            print("🎙 VOICE: Post-processing transcription with Gemini...", flush=True)
            post_response = await asyncio.wait_for(
                asyncio.to_thread(
                    client.models.generate_content,
                    model="gemini-2.5-flash",
                    contents=[
                        types.Content(
                            role="user",
                            parts=[
                                types.Part.from_text(text=post_prompt),
                                types.Part.from_text(
                                    text=f"Text de corectat: {transcription}"
                                ),
                            ],
                        )
                    ],
                    config=types.GenerateContentConfig(
                        temperature=0.1,
                    ),
                ),
                timeout=20.0,
            )
            corrected_text = post_response.text.strip()
            if corrected_text:
                print(f"🎙 VOICE: Corrected text: {repr(corrected_text)}", flush=True)
                transcription = corrected_text
        except Exception as post_err:
            print(f"⚠️ VOICE: STT post-processing failed: {post_err}", flush=True)

        return transcription, myfile.uri

    except Exception as e:
        print(f"❌ VOICE ERROR: {e}", flush=True)
        raise
    finally:
        # 5. Delete the temp file after transcription
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
