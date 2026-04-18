# core/vision.py
import json
import asyncio
from typing import Tuple, Dict, Any
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from google.genai import types


async def analyze_image(
    client, photo_bytes: bytes, caption: str | None
) -> Dict[str, Any]:
    """Sends image to Gemini 2.5 Flash to automatically detect its type and extract data."""

    prompt = f"""
    Analizează această imagine. Ești Lora, asistentul inteligent.
    Avem 4 categorii posibile de imagini:
    1. 'receipt' (bon fiscal / chitanță)
    2. 'menu' (meniu de restaurant / cafenea)
    3. 'workout_screenshot' (captură dintr-o aplicație sport / smartwatch)
    4. 'handwritten_notes' (notițe scrise pe hârtie sau ecran)
    5. 'other' (orice altceva)
    
    {f"Text adițional de la utilizator (caption): {caption}" if caption else ""}
    
    Extrage datele relevante pe baza tipului:
    - Pentru 'receipt': suma totală (amount) ca FLOAT și o categorie sugerată (mâncare, transport, utilități, sănătate, ieșiri, shopping, altele), plus numele comerciantului.
    - Pentru 'menu': nu trebuie să extragi sume, doar identifică dacă e meniu și extrage 3 categorii de mâncare/produse oferite.
    - Pentru 'workout_screenshot': numele sportului/activității, durata în minute (int), calorii (int dacă există), distanța (float dacă există).
    - Pentru 'handwritten_notes': textul brut complet transcris.
    
    Trebuie să răspunzi DOAR cu un JSON (fără blocuri markdown, scrie JSON-ul direct!):
    {{
      "type": "receipt" | "menu" | "workout_screenshot" | "handwritten_notes" | "other",
      "confidence": float,
      "extracted_data": dict,
      "reply": "Răspunsul tău scurt în română (markdownV2)"
    }}
    
    Exemplu extracted_data receipt: {{"amount": 105.50, "category": "mâncare", "merchant": "Kaufland"}}
    Exemplu extracted_data workout: {{"sport_name": "Alergare", "duration_min": 45, "calories": 400, "distance_km": 5.2}}
    Exemplu extracted_data notes: {{"text": "Cumpără lapte, du câinele afară..."}}
    """

    try:
        response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-2.5-flash",
            contents=[
                types.Part.from_bytes(data=photo_bytes, mime_type="image/jpeg"),
                types.Part.from_text(text=prompt),
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.2,
            ),
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"Error analyzing image: {e}", flush=True)
        return {"type": "error", "reply": f"Eroare la procesarea imaginii: {e}"}


async def process_vision_result(
    pool, result: Dict[str, Any], user_profile: Dict[str, Any], client
) -> Tuple[str, InlineKeyboardMarkup | None]:
    """Routes the extracted data to the corresponding module action or asks for confirmation."""
    from bot.formatter import escape_md, safe_markdown
    from core.state import set_state

    img_type = result.get("type")
    data = result.get("extracted_data", {})
    base_reply = result.get("reply", "")

    if img_type == "receipt":
        amount = data.get("amount")
        category = data.get("category", "altele").lower()
        merchant = data.get("merchant", "Necunoscut")

        if amount is None:
            return safe_markdown(
                "Am detectat un bon, dar nu am putut citi suma totală clar."
            ), None

        # Pregătește starea pentru confirmare
        extra = {
            "amount": amount,
            "category": category,
            "description": merchant,
            "type": "expense",
        }
        await set_state(
            pool,
            "awaiting_vision_confirmation",
            "finance",
            "log_expense",
            None,
            extra=extra,
        )

        msg = f"🧾 Am extras un bon de la *{escape_md(str(merchant))}*.\n\nSuma: `{amount} RON`\nCategorie: {escape_md(category)}\n\n_Dorești să înregistrez această cheltuială?_"
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("✅ Confirmă", callback_data="vision:confirm"),
                    InlineKeyboardButton("❌ Anulează", callback_data="vision:cancel"),
                ]
            ]
        )
        return msg, keyboard

    elif img_type == "menu":
        # Generate suggestion based on user preferences
        personal_notes = user_profile.get("personal_notes", "")
        prompt = f"""
        Ești Lora. Utilizatorul ți-a trimis un meniu de restaurant. Datele extrase: {data}
        Luând în calcul preferințele lui: {personal_notes}
        Sugerează-i CCEVA BUN și SĂNĂTOS de pe acest meniu.
        Răspunde direct, în română, formatat elegant cu MarkdownV2. Max 3 propoziții.
        """
        try:
            response = await asyncio.to_thread(
                client.models.generate_content,
                model="gemini-2.5-flash",
                contents=[types.Part.from_text(text=prompt)],
                config=types.GenerateContentConfig(temperature=0.7),
            )
            return safe_markdown(response.text.strip()), None
        except Exception:
            return safe_markdown(
                "Arată apetisant! Din păcate nu am putut genera o recomandare specifică."
            ), None

    elif img_type == "workout_screenshot":
        import db.queries.workout as workout_queries

        sport = data.get("sport_name", "Cardio")
        duration = data.get("duration_min", 0)
        calories = data.get("calories")

        if not duration:
            return safe_markdown(
                f"Antrenament detectat ({sport}), dar nu am găsit durata. Încearcă să o introduci manual."
            ), None

        # Log direct (or could also ask for confirmation, but prompt said "pregătește log_workout")
        # Let's just log it directly to be frictionless
        await workout_queries.log_workout(
            pool,
            workout_date=None,  # azi
            sport_name=sport,
            duration_min=duration,
            calories=calories,
            notes="Extras din screenshot",
            exercises=[],
        )
        msg = f"💪 Antrenament salvat din imagine!\n\nSport: *{escape_md(str(sport))}*\nDurată: `{duration} min`\nCalorii: `{calories or 'N/A'}`"
        return msg, None

    elif img_type == "handwritten_notes":
        text = data.get("text", "")
        if not text:
            return safe_markdown("Nu am putut transcrie un text lizibil."), None

        import db.queries.notes as note_queries

        await note_queries.add_note(pool, content=text, note_type="note")

        return safe_markdown(f"✍️ Notiță salvată cu succes:\n\n_{text}_"), None

    else:
        # 'other' or error
        return safe_markdown(
            base_reply or "Nu am putut clasifica clar această imagine."
        ), None


async def handle_vision_callback(query, pool, callback_data: str):
    """Handles the 'vision:confirm/cancel' buttons for actions requiring user review."""
    from db.queries.finance import log_finance
    from core.state import get_state, clear_state

    state = await get_state(pool)
    if not state or state.get("state_type") != "awaiting_vision_confirmation":
        await query.answer("Acțiunea a expirat sau nu mai este validă.")
        # Attempt to remove keyboard
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass
        return

    if callback_data == "vision:cancel":
        await clear_state(pool)
        await query.answer("Acțiune anulată.")
        await query.edit_message_text("❌ Acțiune anulată.")
        return

    if callback_data == "vision:confirm":
        action = state.get("action")
        extra = state.get("extra", {})

        if action == "log_expense":
            amount = extra.get("amount")
            category = extra.get("category")
            desc = extra.get("description")

            await log_finance(
                pool, "expense", amount, category=category, description=desc
            )
            await clear_state(pool)

            await query.answer("Salvat!")
            await query.edit_message_text("✅ Cheltuială înregistrată cu succes.")
            return

    await query.answer("Tip de acțiune necunoscut.")
    await clear_state(pool)
