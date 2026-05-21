from typing import Dict, Any, Tuple, Optional
from db.queries.shopping import (
    add_shopping_item,
    list_shopping_items,
    delete_item_by_name,
    clear_bought_items,
)
from bot.formatter import escape_md


async def handle_shopping_intent(
    pool, intent: str, data: Dict[str, Any]
) -> Tuple[str, Any, Optional[int]]:
    if intent == "add_item":
        item = data.get("item")
        category = data.get("category")
        if not item:
            return (
                "⚠️ Atenție: Nu ai specificat ce vrei să adaugi pe listă. Te rog să repeți.",
                None,
                None,
            )

        item_id = await add_shopping_item(pool, item, category)
        return (
            f"✅ Item-ul *{escape_md(item)}* a fost adăugat cu succes pe lista de cumpărături.",
            None,
            item_id,
        )

    elif intent == "list_items":
        items = await list_shopping_items(pool, include_bought=False)
        if not items:
            return (
                "🛒 *Lista de cumpărături:*\n━━━━━━━━━━━━━━━━━━━━\nLista este goală.",
                None,
                None,
            )

        reply = "🛒 *Lista de cumpărături:*\n━━━━━━━━━━━━━━━━━━━━\n"
        for i in items:
            cat = f" ({escape_md(i['category'])})" if i["category"] else ""
            reply += f"• {escape_md(i['item'])}{cat}\n"

        return reply, None, None

    elif intent == "delete_item":
        item = data.get("item")
        if not item:
            return (
                "⚠️ Atenție: Nu ai specificat ce vrei să ștergi de pe listă.",
                None,
                None,
            )

        await delete_item_by_name(pool, item)
        return f"🗑️ Item-ul *{escape_md(item)}* a fost șters de pe listă.", None, None

    elif intent == "clear_items":
        await clear_bought_items(pool)
        return (
            "🗑️ Lista de cumpărături a fost curățată cu succes (produsele bifate au fost șterse).",
            None,
            None,
        )

    return "❌ Eroare: Modulul shopping nu recunoaște acest intent.", None, None


async def undo_last_action(pool, intent: str, item_id: int) -> Tuple[bool, str]:
    if not item_id:
        return False, "❌ Eroare: Nu s-a găsit ID-ul entității de anulat."

    from db.queries.shopping import delete_item_by_id

    try:
        if intent == "add_item":
            await delete_item_by_id(pool, item_id)
            return True, "🗑️ Item-ul adăugat a fost șters de pe lista de cumpărături."

        return (
            False,
            f"❌ Eroare: Anularea nu este implementată pentru intentul '{intent}'.",
        )
    except Exception as e:
        return False, f"❌ Eroare la anulare: {str(e)}"
