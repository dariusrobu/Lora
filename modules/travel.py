from typing import Dict, Any, Tuple
from db.queries.travel import (
    add_travel_item,
    get_travel_items,
    mark_item_packed_by_name,
    clear_travel_list,
    toggle_packed_status,
)
from bot.formatter import escape_md
from bot.keyboards import travel_list_keyboard

async def handle_travel_intent(
    pool, intent: str, data: Dict[str, Any]
) -> Tuple[str, Any, Optional[int]]:
    if intent == "travel_add":
        items_str = data.get("items") or data.get("item")
        list_name = data.get("list_name") or "General"
        trip_type = data.get("trip_type", "both")
        
        if not items_str:
            return "Ce vrei să adaug pe lista de travel? 🤔", None, None
            
        # Support comma separated items
        items = [i.strip() for i in items_str.split(",") if i.strip()]
        last_id = None
        for item in items:
            last_id = await add_travel_item(pool, item, list_name, trip_type=trip_type)
            
        items_joined = ", ".join([f"*{escape_md(i)}*" for i in items])
        # Return list with keyboard after adding
        items_list = await get_travel_items(pool, list_name)
        return f"✅ Am adăugat {items_joined} pe lista *{escape_md(list_name)}*\\.", travel_list_keyboard(items_list, list_name), last_id

    elif intent == "travel_list" or intent == "travel_check":
        list_name = data.get("list_name") or "General"
        trip_type = data.get("trip_type") # Can be null, departure, or return
        
        items = await get_travel_items(pool, list_name, trip_type)
        if not items:
            return f"Lista *{escape_md(list_name)}* este goală\\! 🎉 Drum bun\\!", None, None

        reply = f"🧳 *Lista de bagaj: {escape_md(list_name)}*\n"
        if trip_type and trip_type != 'both':
            dir_text = "Plecare" if trip_type == "departure" else "Întoarcere"
            reply += f"Direcție: _{escape_md(dir_text)}_\n"
        reply += "━━━━━━━━━━━━━━━━━━━━\n"
        
        for i in items:
            status = "✅" if i["is_packed"] else "⬜"
            item_text = escape_md(i["item"])
            if i["is_packed"]:
                item_text = f"~{item_text}~"
            reply += f"{status} {item_text}\n"

        if intent == "travel_check":
            reply = f"🛫 *Drum bun\\!* Nu uita să verifici lista pentru *{escape_md(list_name)}*:\n\n" + reply
            
        return reply, travel_list_keyboard(items, list_name), None

    elif intent == "travel_packed":
        item_name = data.get("item")
        list_name = data.get("list_name") or "General"
        
        if not item_name:
            return "Ce ai pus în bagaj? 🤔", None, None
            
        await mark_item_packed_by_name(pool, list_name, item_name)
        items = await get_travel_items(pool, list_name)
        return f"👍 Am bifat *{escape_md(item_name)}* pe lista *{escape_md(list_name)}*\\.", travel_list_keyboard(items, list_name), None

    elif intent == "travel_clear":
        list_name = data.get("list_name")
        if not list_name:
            return "Ce listă vrei să resetezi?", None, None
            
        reset_only = data.get("reset_only", True)
        await clear_travel_list(pool, list_name, reset_only=reset_only)
        
        action = "resetat" if reset_only else "șters"
        items = await get_travel_items(pool, list_name) if reset_only else []
        markup = travel_list_keyboard(items, list_name) if reset_only else None
        return f"🧹 Am {action} lista *{escape_md(list_name)}*\\.", markup, None

    return "Modulul travel nu recunoaște acest intent.", None, None

async def undo_last_action(pool, intent: str, item_id: int) -> Tuple[bool, str]:
    if not item_id:
        return False, "Nu s-a găsit ID-ul entității de anulat."

    from db.queries.travel import delete_travel_item
    try:
        if intent == "travel_add":
            await delete_travel_item(pool, item_id)
            return True, "Item-ul de travel a fost șters."
        
        return False, f"Anularea nu este implementată pentru intentul '{intent}'."
    except Exception as e:
        return False, f"Eroare la anulare: {str(e)}"


async def handle_travel_callback(query, pool, data: str):
    from bot.callback_utils import parse_callback_data
    action, params = parse_callback_data(data)
    
    # params: [action_type, item_id/list_name, extra...]
    if action == "travel":
        sub_action = params[0]
        
        if sub_action == "toggle":
            item_id = int(params[1])
            list_name = params[2]
            
            # Get current status
            rows = await pool.fetch("SELECT is_packed FROM travel_items WHERE id = $1", item_id)
            if rows:
                new_status = not rows[0]["is_packed"]
                await toggle_packed_status(pool, item_id, new_status)
            
            # Refresh list
            items = await get_travel_items(pool, list_name)
            reply = f"🧳 *Lista de bagaj: {escape_md(list_name)}*\n━━━━━━━━━━━━━━━━━━━━\n"
            for i in items:
                status = "✅" if i["is_packed"] else "⬜"
                item_text = escape_md(i["item"])
                if i["is_packed"]:
                    item_text = f"~{item_text}~"
                reply += f"{status} {item_text}\n"
                
            await query.edit_message_text(
                reply,
                parse_mode="MarkdownV2",
                reply_markup=travel_list_keyboard(items, list_name)
            )
            
        elif sub_action == "list":
            list_name = params[1]
            items = await get_travel_items(pool, list_name)
            reply = f"🧳 *Lista de bagaj: {escape_md(list_name)}*\n━━━━━━━━━━━━━━━━━━━━\n"
            for i in items:
                status = "✅" if i["is_packed"] else "⬜"
                item_text = escape_md(i["item"])
                if i["is_packed"]:
                    item_text = f"~{item_text}~"
                reply += f"{status} {item_text}\n"
                
            await query.edit_message_text(
                reply,
                parse_mode="MarkdownV2",
                reply_markup=travel_list_keyboard(items, list_name)
            )
            
        elif sub_action == "clear":
            list_name = params[1]
            await clear_travel_list(pool, list_name, reset_only=True)
            items = await get_travel_items(pool, list_name)
            await query.edit_message_text(
                f"🧹 Lista *{escape_md(list_name)}* a fost resetată\\.",
                parse_mode="MarkdownV2",
                reply_markup=travel_list_keyboard(items, list_name)
            )
