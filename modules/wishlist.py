from typing import Dict, Any, Tuple, Optional
import db.queries.wishlist as wishlist_queries
from bot.formatter import escape_md
from core.config import TELEGRAM_USER_ID

async def handle_wishlist_intent(
    pool, intent: str, data: Dict[str, Any]
) -> Tuple[str, Optional[Any], Optional[int]]:
    """Handler principal pentru modulul Wish List."""
    user_id = TELEGRAM_USER_ID

    if intent == "add_wish":
        item = data.get("item")
        description = data.get("description")
        price = data.get("price")
        category = data.get("category", "altele")
        priority = data.get("priority", "medium")

        if not item:
            return "Ce anume vrei să adaugi în Wish List? (Lipsește numele obiectului)", None, None

        await wishlist_queries.add_wish_item(
            pool, user_id, item, description, price, category, priority
        )
        
        reply = f"✨ *{escape_md(item)}* a fost adăugat în Wish List\\."
        if description:
            reply += f"\n📝 _Justificare: {escape_md(description)}_"
            
        return reply, None, None

    elif intent == "list_wish":
        items = await wishlist_queries.list_wish_items(pool, user_id)
        if not items:
            return "Wish List-ul tău este gol momentan. Ce visăm azi? ✨", None, None

        reply = "✨ *WISH LIST* ✨\n\n"
        for i in items:
            price_str = f" \\- `{i['price']} RON`" if i['price'] else ""
            priority_emoji = "🔴" if i['priority'] == 'high' else "🟡" if i['priority'] == 'medium' else "🟢"
            
            reply += f"{priority_emoji} *{escape_md(i['item'])}*{price_str}\n"
            if i['description']:
                reply += f"└ 📝 _{escape_md(i['description'])}_\n"
            reply += "\n"

        return reply, None, None

    elif intent == "delete_wish":
        query = data.get("item")
        if not query:
            return "Ce anume vrei să ștergi din Wish List?", None, None
            
        await wishlist_queries.delete_wish_item(pool, user_id, query)
        return f"🗑️ Am eliminat *{escape_md(query)}* din listă.", None, None

    return "Modulul Wish List este pregătit!", None, None
