from typing import Dict, Any, Tuple, Optional
from core.mac_bridge import create_apple_note, set_apple_alarm, send_apple_mail
from core.email_client import get_gmail_client, get_outlook_client


async def handle_integrations_intent(
    pool, intent: str, data: Dict[str, Any]
) -> Tuple[str, Any, Optional[int]]:
    """Handler for Mac and Email integrations."""

    if intent == "mac_note_create":
        title = data.get("title", "Lora Note")
        body = data.get("body", "")
        success = create_apple_note(title, body)
        if success:
            return (
                f"✅ Nota *{title}* a fost creată cu succes în Apple Notes.",
                None,
                None,
            )
        return (
            "❌ Eroare: Nu am putut accesa Apple Notes. Verifică permisiunile.",
            None,
            None,
        )

    if intent == "mac_alarm_set":
        hour = data.get("hour")
        minute = data.get("minute", 0)
        label = data.get("label", "Lora Alarm")
        if hour is None:
            return "⚠️ Atenție: Nu ai specificat ora. Te rog să repeți.", None, None

        success = set_apple_alarm(label, hour, minute)
        if success:
            return (
                f"✅ Alarma a fost setată cu succes pentru *{hour:02d}:{minute:02d}*.",
                None,
                None,
            )
        return (
            "❌ Eroare: Nu am putut seta alarma. Verifică aplicația Clock.",
            None,
            None,
        )

    if intent == "email_send":
        recipient = data.get("to")
        subject = data.get("subject", "No Subject")
        body = data.get("body", "")
        if not recipient:
            return "⚠️ Atenție: Nu ai specificat destinatarul.", None, None

        success = send_apple_mail(recipient, subject, body)
        if success:
            return (
                f"✅ Apple Mail a fost deschis pentru a trimite către *{recipient}*.",
                None,
                None,
            )
        return "❌ Eroare: Nu am putut deschide Apple Mail.", None, None

    if intent == "email_check":
        service = data.get("service", "gmail").lower()
        client = get_gmail_client() if service == "gmail" else get_outlook_client()

        if not client:
            return (
                f"❌ Eroare: Contul de {service} nu este configurat în .env (necesită App Password).",
                None,
                None,
            )

        unread = client.get_unread_emails(limit=3)
        if not unread:
            return (
                f"📥 *{service.capitalize()}*\n━━━━━━━━━━━━━━━━━━━━\nNu ai mesaje noi necitite.",
                None,
                None,
            )

        reply = (
            f"📥 *Ultimele mesaje pe {service.capitalize()}*\n━━━━━━━━━━━━━━━━━━━━\n"
        )
        for i, m in enumerate(unread, 1):
            reply += f"{i}. *{m['subject']}* de la {m['from']}\n"

        return reply, None, None

    return "❌ Eroare: Modulul integrări nu recunoaște acest intent.", None, None


async def undo_last_action(pool, intent: str, item_id: int) -> Tuple[bool, str]:
    return (
        False,
        "❌ Eroare: Anularea nu este disponibilă pentru integrările externe (Mac/Email).",
    )
