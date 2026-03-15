from typing import Dict, Any, Tuple
from db.queries.shopping import add_shopping_item, list_shopping_items, delete_item_by_name
from bot.formatter import escape_md

async def handle_shopping_intent(pool, intent: str, data: Dict[str, Any]) -> Tuple[str, Any]:
    if intent == "add_item":
        item = data.get("item")
        category = data.get("category")
        if not item:
            return "Ce vrei să adaug pe listă? (Nu am prins numele obiectului)", None
        
        await add_shopping_item(pool, item, category)
        return f"✅ Am adăugat *{escape_md(item)}* pe lista de cumpărături.", None

    elif intent == "list_items":
        items = await list_shopping_items(pool)
        if not items:
            return "Lista de cumpărături e goală! 🎉", None
        
        reply = "🛒 *Lista de cumpărături:*\n"
        for i in items:
            cat = f" ({escape_md(i['category'])})" if i['category'] else ""
            reply += f"• {escape_md(i['item'])}{cat}\n"
        
        return reply, None

    elif intent == "delete_item":
        item = data.get("item")
        if not item:
            return "Ce vrei să șterg de pe listă?", None
        
        await delete_item_by_name(pool, item)
        return f"🗑️ Am șters *{escape_md(item)}* de pe listă.", None

    return "Modulul shopping nu recunoaște acest intent.", None
