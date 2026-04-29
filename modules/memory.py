from bot.callback_utils import make_callback_data
from typing import Dict, Any, Tuple
import db.queries.memory as memory_queries
from bot.formatter import escape_md, safe_markdown
from bot.keyboards import memory_main_keyboard
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


async def handle_memory_callback(query, pool, data: str):
    """Handles callback queries from the memory dashboard."""
    print(f"DEBUG: handle_memory_callback hit with data={data}", flush=True)
    try:
        if data == "memory:delete_last":
            print("DEBUG: Processing memory:delete_last", flush=True)
            await memory_queries.delete_last_fact(pool)
            await query.answer("Am uitat ultima amintire! 💨")
            # Refresh the view
            text, markup, _ = await handle_memory_intent(pool, "memory_view", {})
            await query.edit_message_text(
                text, parse_mode="MarkdownV2", reply_markup=markup
            )

        elif data == "memory:clear_all":
            print("DEBUG: Processing memory:clear_all", flush=True)
            # First click: Ask for confirmation
            # Using a pattern similar to goals/tasks delete confirmation
            keyboard = [
                [
                    InlineKeyboardButton(
                        "✅ Da, șterge tot",
                        callback_data=make_callback_data(
                            "memory", "clear_all_confirmed"
                        ),
                    ),
                    InlineKeyboardButton(
                        "❌ Nu, anulează",
                        callback_data=make_callback_data("memory", "view", "back"),
                    ),
                ]
            ]
            await query.edit_message_text(
                "⚠️ *Ești sigur că vrei să ștergi TOATE amintirile?*",
                parse_mode="MarkdownV2",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )

        elif data == "memory:clear_all_confirmed":
            print("DEBUG: Processing memory:clear_all_confirmed", flush=True)
            await memory_queries.clear_all_memories(pool)
            await query.answer("Memoria a fost resetată! 🧠✨")
            await query.edit_message_text(
                "Memoria a fost ștearsă complet\\.", parse_mode="MarkdownV2"
            )

        elif data == "memory:view_categories":
            print("DEBUG: Processing memory:view_categories", flush=True)
            await query.answer("Filtrare pe categorii în lucru... 🚧")

        elif data == "memory:view_back" or data == "chat:main":
            print(f"DEBUG: Processing {data}", flush=True)
            from bot.handler import message_handler
            # Reset to main menu or previous view
            if data == "chat:main":
                await query.edit_message_text(
                    "Principal menu is not directly accessible via memory callback. Returning to dashboard.",
                    parse_mode="MarkdownV2"
                )
                # Actually, better to just show the memory view or trigger a main menu command
                # For now, let's just go back to memory_view if it was from memory
                text, markup, _ = await handle_memory_intent(pool, "memory_view", {})
                await query.edit_message_text(
                    text, parse_mode="MarkdownV2", reply_markup=markup
                )
            else:
                text, markup, _ = await handle_memory_intent(pool, "memory_view", {})
                await query.edit_message_text(
                    text, parse_mode="MarkdownV2", reply_markup=markup
                )
    except Exception as e:
        print(f"ERROR in handle_memory_callback: {e}")
        import traceback

        traceback.print_exc()
        await query.answer("A apărut o eroare la procesarea butonului.")


async def handle_memory_intent(
    pool, intent: str, data: Dict[str, Any]
) -> Tuple[str, Any]:
    """Handles memory-related intents: viewing and deleting facts."""

    if intent == "memory_view":
        memories = await memory_queries.list_all_memories(pool)
        if not memories:
            return (
                "Nu am salvat nicio amintire despre tine încă\\. 🧠",
                memory_main_keyboard(),
                None,
            )

        # Group by category
        grouped = {}
        for m in memories:
            cat = m["category"].upper()
            if cat not in grouped:
                grouped[cat] = []
            grouped[cat].append(m)

        # Refine text: remove "Utilizatorul" or "The user" prefixes for better flow
        def clean_fact(f):
            f = f.replace("Utilizatorul ", "").replace("utilizatorul ", "")
            f = f.strip()
            return f[0].upper() + f[1:] if f else f

        text = "🧠 *LORA CORE MEMORY* 🧠\n"
        text += "‾" * 20 + "\n"

        category_icons = {
            "PREFERENCE": "💎",
            "PATTERN": "📊",
            "PERSONAL": "🆔",
            "ACHIEVEMENT": "🏆",
        }

        for cat in ["PERSONAL", "PREFERENCE", "PATTERN", "ACHIEVEMENT"]:
            if cat in grouped:
                items = grouped[cat]
                icon = category_icons.get(cat, "🔹")
                text += f"\n{icon} *{cat}*\n"
                for m in items:
                    fact = clean_fact(m["fact"])
                    text += f"` {m['id']:02} ` • {fact}\n"

        text += "\n" + "—" * 15 + "\n"
        text += "💡 _Atinge codul pentru copy-paste_\n"
        text += "🗑 _Ex: 'șterge #03'_"

        return safe_markdown(text), memory_main_keyboard(), None

    elif intent == "memory_delete":
        fact_id = data.get("fact_id")
        query = data.get("query")

        # Strip '#' if user included it in ID
        if isinstance(fact_id, str) and fact_id.startswith("#"):
            try:
                fact_id = int(fact_id[1:])
            except (ValueError, TypeError):
                pass

        if not fact_id and query:
            # Try to find by search
            results = await memory_queries.search_memories(pool, query)
            if len(results) == 1:
                fact_id = results[0]["id"]
            elif len(results) > 1:
                text = "Am găsit mai multe amintiri similare. Pe care vrei să o șterg? (Folosește ID-ul)\n\n"
                for r in results:
                    text += f"◽ `#{r['id']}` {r['fact']}\n"
                return safe_markdown(text), None, None
            else:
                return (
                    f"Nu am găsit nicio amintire legată de '{escape_md(str(query))}'.",
                    None,
                    None,
                )

        if fact_id:
            await memory_queries.delete_fact(pool, int(fact_id))
            return f"✅ Amintirea `#{fact_id}` a fost ștearsă. Am uitat! 💨", None, None

        return (
            "Nu am înțeles ce amintire vrei să șterg. Te rog să menționezi ID-ul (ex: #3).",
            None,
            None,
        )

    elif intent == "memory_search":
        topic = data.get("topic")
        user_id = data.get("user_id")
        if not topic:
            return "Despre ce anume vrei să afli ce știu?", None, None

        results = await search_memory_core(pool, topic, user_id)

        if results["facts"]:
            # If we have direct facts, be direct and warm
            fact_texts = [f['fact'] for f in results["facts"]]
            main_fact = fact_texts[0]
            
            # Clean common prefixes
            main_fact = main_fact.replace("Utilizatorul ", "").replace("utilizatorul ", "")
            main_fact = main_fact[0].upper() + main_fact[1:] if main_fact else main_fact
            
            text = f"✨ {safe_markdown(main_fact)}"
            
            if len(fact_texts) > 1:
                text += "\n\n💡 _Mai știu și:_ " + ", ".join(fact_texts[1:])
            
            return text, None, None

        if results["history"]:
            text = f"🔍 *Din ce am vorbit recent despre {escape_md(topic)}:*\n\n"
            for h in results["history"][:3]:
                content = h["content"]
                if len(content) > 120:
                    content = content[:117] + "..."
                text += f'• _"{escape_md(content)}"_\n'
            return safe_markdown(text), None, None

        return (
            f"Momentan nu am nicio informație salvată despre *{escape_md(topic)}*.",
            None,
            None,
        )

    return "Modulul de memorie a primit o intenție necunoscută.", None, None


async def search_memory_core(pool, topic: str, user_id: int) -> Dict[str, Any]:
    """Aggregates search results from memory_facts and message_history."""
    from db.queries.history import search_history
    from db.queries.memory import semantic_search_memories

    facts = await semantic_search_memories(pool, user_id, topic)
    history = await search_history(pool, user_id, topic)

    return {"facts": facts, "history": history}

    return "Modulul de memorie a primit o intenție necunoscută.", None
