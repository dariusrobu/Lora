# modules/reading.py

from typing import Dict, Any, Tuple, Optional
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from bot.formatter import escape_md
from bot.keyboards import (
    reading_main_keyboard,
    reading_stats_period_keyboard,
    reading_books_keyboard,
    reading_book_detail_keyboard,
    reading_confirm_delete_keyboard,
)
import db.queries.reading as reading_queries
from core.state import set_state, clear_state


async def get_reading_dashboard(pool) -> Tuple[str, InlineKeyboardMarkup]:
    """Renders the main reading dashboard."""
    stats = await reading_queries.get_reading_stats(pool)
    current = await reading_queries.get_current_books(pool)
    streak = await reading_queries.get_reading_streak(pool)

    lines = ["📚 *Reading Dashboard*\n"]

    if stats:
        completed = stats.get("completed", 0)
        in_progress = stats.get("in_progress", 0)
        this_year = stats.get("this_year", 0)
        avg_rating = stats.get("avg_rating")

        lines.append(f"📖 În curs: *{in_progress}*")
        lines.append(f"✅ Terminate: *{completed}*")
        lines.append(f"📅 Anul acesta: *{this_year}*")
        if avg_rating:
            lines.append(f"⭐ Rating mediu: *{avg_rating}*")
        if streak > 0:
            lines.append(f"🔥 Streak lectură: *{streak}* zile")

    if current:
        lines.append("\n*În progres acum:*")
        for book in current[:3]:
            title = escape_md(book.get("title", ""))
            if book.get("total_pages") and book.get("pages_read"):
                pct = int((book["pages_read"] / book["total_pages"]) * 100)
                filled = min(pct // 10, 10)
                bar = "█" * filled + "░" * (10 - filled)
                lines.append(f"\n  *{title}*")
                lines.append(
                    f"  `{bar}` {book['pages_read']}/{book['total_pages']} pag \\({pct}%\\)"
                )
            else:
                pages = book.get("pages_read", 0)
                lines.append(f"\n  *{title}* \\(p\\. {pages}\\)")
    else:
        lines.append("\n_Nu ai cărți în progres\\. Adaugă o carte nouă\\!_")

    return "\n".join(lines), reading_main_keyboard()


async def get_reading_library_view(pool) -> Tuple[str, InlineKeyboardMarkup]:
    """Shows the full library grouped by status."""
    books = await reading_queries.get_all_books(pool)

    if not books:
        return (
            "📚 *Biblioteca ta*\n\nNu ai cărți în bibliotecă\\. Adaugă una cu 'am început să citesc X'\\.",
            reading_main_keyboard(),
        )

    reading_books = [b for b in books if b["status"] == "reading"]
    completed_books = [b for b in books if b["status"] == "completed"]

    lines = ["📚 *Biblioteca ta*\n"]

    if reading_books:
        lines.append(f"*În curs \\({len(reading_books)}\\):*")
        for b in reading_books:
            title = escape_md(b.get("title", ""))
            author = f" — _{escape_md(b['author'])}_" if b.get("author") else ""
            if b.get("total_pages") and b.get("pages_read"):
                pct = int((b["pages_read"] / b["total_pages"]) * 100)
                lines.append(f"• *{title}*{author} \\({pct}%\\)")
            else:
                pages = b.get("pages_read", 0)
                lines.append(f"• *{title}*{author} \\(p\\. {pages}\\)")
        lines.append("")

    if completed_books:
        lines.append(f"*Terminate \\({len(completed_books)}\\):*")
        for b in completed_books[:10]:
            title = escape_md(b.get("title", ""))
            stars = " ⭐" * b["rating"] if b.get("rating") else ""
            year = f" \\({b['finished_at'].year}\\)" if b.get("finished_at") else ""
            lines.append(f"• {title}{year}{stars}")
        if len(completed_books) > 10:
            lines.append(f"\\_...și încă {len(completed_books) - 10}\\_")

    books_for_keyboard = reading_books if reading_books else completed_books
    return "\n".join(lines), reading_books_keyboard(books_for_keyboard)


async def get_reading_stats_view(
    pool, days: int = 30, all_time: bool = False
) -> Tuple[str, InlineKeyboardMarkup]:
    """Shows detailed reading statistics."""
    if all_time:
        stats = await reading_queries.get_reading_stats(pool)
        streak = await reading_queries.get_reading_streak(pool)
        recent = await reading_queries.get_recent_completed_books(pool, limit=5)

        lines = ["📊 *Reading Stats \\- Toate timpurile*\n"]
        lines.append(f"✅ Terminate total: *{stats.get('completed', 0)}*")
        lines.append(f"📖 În curs: *{stats.get('in_progress', 0)}*")
        lines.append(f"📅 Anul acesta: *{stats.get('this_year', 0)}*")
        if stats.get("avg_rating"):
            lines.append(f"⭐ Rating mediu: *{stats['avg_rating']}*")
        if streak > 0:
            lines.append(f"🔥 Streak lectură: *{streak}* zile")

        if recent:
            lines.append("\n*Ultimele cărți terminate:*")
            for b in recent:
                title = escape_md(b.get("title", ""))
                stars = " ⭐" * b["rating"] if b.get("rating") else ""
                year = f" \\({b['finished_at'].year}\\)" if b.get("finished_at") else ""
                lines.append(f"• {title}{year}{stars}")

        return "\n".join(lines), reading_stats_period_keyboard()

    stats = await reading_queries.get_reading_stats_detailed(pool, days)

    lines = [f"📊 *Reading Stats \\({days} zile\\)*\n"]
    lines.append(f"✅ Terminate: *{stats.get('completed_period', 0)}*")
    lines.append(f"📖 Pagini citite: *{stats.get('pages_read_period', 0)}*")
    lines.append(f"📚 În curs: *{stats.get('currently_reading', 0)}*")
    if stats.get("avg_rating_period"):
        lines.append(f"⭐ Rating mediu perioadă: *{stats['avg_rating_period']}*")

    return "\n".join(lines), reading_stats_period_keyboard()


async def get_book_detail_view(pool, book_id: int) -> Tuple[str, InlineKeyboardMarkup]:
    """Shows detailed view of a single book."""
    book = await reading_queries.get_book_by_id(pool, book_id)

    if not book:
        return "❌ Cartea nu a fost găsită\\.", reading_main_keyboard()

    title = escape_md(book.get("title", ""))
    author = escape_md(book.get("author", "")) if book.get("author") else "_necunoscut_"

    lines = [f"📖 *{title}*\n"]
    lines.append(f"👤 Autor: *{author}*")

    if book.get("total_pages"):
        pct = 0
        if book.get("pages_read"):
            pct = int((book["pages_read"] / book["total_pages"]) * 100)
            filled = min(pct // 10, 10)
            bar = "█" * filled + "░" * (10 - filled)
            lines.append(
                f"📄 Progres: `{bar}` {book['pages_read']}/{book['total_pages']} \\({pct}%\\)"
            )
        else:
            lines.append(f"📄 Pagini totale: *{book['total_pages']}*")

    if book.get("rating"):
        lines.append(f"⭐ Rating: *{book['rating']}*\\/5")

    status_emoji = "📖" if book["status"] == "reading" else "✅"
    lines.append(f"{status_emoji} Status: *{book['status']}*")

    if book.get("started_at"):
        lines.append(f"📅 Începută: *{book['started_at'].strftime('%d %b %Y')}*")
    if book.get("finished_at"):
        lines.append(f"🏁 Terminată: *{book['finished_at'].strftime('%d %b %Y')}*")

    notes = await reading_queries.get_book_notes(pool, book_id)
    if notes:
        lines.append(f"\n📝 Note: *{len(notes)}* salvate")

    return "\n".join(lines), reading_book_detail_keyboard(book_id, book["status"])


# ── NLP Intent Handlers ─────────────────────────────────────────────


async def handle_reading_intent(
    pool, intent: str, data: Dict[str, Any], bot=None
) -> Tuple[str, Optional[InlineKeyboardMarkup]]:
    if intent == "reading_add":
        title = data.get("title", "")
        author = data.get("author")
        total_pages = data.get("total_pages")

        if not title:
            await set_state(pool, "reading_add_book", "reading", "add", None)
            return "Care e titlul cărții?", None

        await reading_queries.add_book(pool, title, author, total_pages)

        author_str = f" de {escape_md(author)}" if author else ""
        pages_str = f", {total_pages} pagini" if total_pages else ""
        return data.get(
            "_original_reply",
            f"*{escape_md(title)}*{escape_md(author_str)} adăugat în bibliotecă{escape_md(pages_str)}\\. 📚",
        ), reading_main_keyboard()

    elif intent == "reading_update":
        title = data.get("title", "")
        pages_read = data.get("pages_read")

        if not title or pages_read is None:
            return "Spune-mi cartea și pagina la care ești\\.", None

        book = await reading_queries.get_book_by_title(pool, title)
        if not book:
            return f"Nu am găsit cartea *{escape_md(title)}* în bibliotecă\\.", None

        await reading_queries.update_progress(pool, book["id"], pages_read)

        progress_str = ""
        if book.get("total_pages"):
            pct = int((pages_read / book["total_pages"]) * 100)
            filled = min(pct // 10, 10)
            bar = "█" * filled + "░" * (10 - filled)
            progress_str = f"\n`{bar}` {pct}%"

        return f"*{escape_md(book['title'])}* — pagina {pages_read}{progress_str}", None

    elif intent == "reading_complete":
        title = data.get("title", "")
        rating = data.get("rating")

        if not title:
            return "Care carte ai terminat?", None

        book = await reading_queries.get_book_by_title(pool, title)
        if not book:
            return f"Nu am găsit *{escape_md(title)}* în bibliotecă\\.", None

        await reading_queries.complete_book(pool, book["id"], rating)

        stars = " ⭐" * int(rating) if rating else ""
        return f"*{escape_md(book['title'])}* terminată\\.{stars}", None

    elif intent == "reading_note":
        title = data.get("title", "")
        content = data.get("content", "")
        page = data.get("page_number")

        if not title or not content:
            return "Spune-mi cartea și nota\\.", None

        book = await reading_queries.get_book_by_title(pool, title)
        if not book:
            return f"Nu am găsit *{escape_md(title)}*\\.", None

        await reading_queries.add_book_note(pool, book["id"], content, page)
        page_str = f" \\(p\\. {page}\\)" if page else ""
        return f"Notă salvată din *{escape_md(book['title'])}*{page_str}\\. 📝", None

    elif intent == "reading_list":
        return await get_reading_library_view(pool)

    elif intent == "reading_stats":
        return await get_reading_stats_view(pool)

    return "Nu am înțeles cererea legată de cărți\\.", None


# ── Callback Handlers ───────────────────────────────────────────────


async def handle_reading_callback(query, pool, data: str) -> None:
    """Routes reading callbacks."""
    await query.answer()
    parts = data.split("_")

    if data == "reading_main":
        text, markup = await get_reading_dashboard(pool)
        await query.edit_message_text(
            text, parse_mode="MarkdownV2", reply_markup=markup
        )

    elif data == "reading_library":
        text, markup = await get_reading_library_view(pool)
        await query.edit_message_text(
            text, parse_mode="MarkdownV2", reply_markup=markup
        )

    elif data == "reading_stats_menu":
        await query.edit_message_text(
            "📊 *Statistici lectură*\n\nAlege perioada:",
            parse_mode="MarkdownV2",
            reply_markup=reading_stats_period_keyboard(),
        )

    elif data == "reading_stats_7":
        text, markup = await get_reading_stats_view(pool, days=7)
        await query.edit_message_text(
            text, parse_mode="MarkdownV2", reply_markup=markup
        )

    elif data == "reading_stats_30":
        text, markup = await get_reading_stats_view(pool, days=30)
        await query.edit_message_text(
            text, parse_mode="MarkdownV2", reply_markup=markup
        )

    elif data == "reading_stats_year":
        text, markup = await get_reading_stats_view(pool, days=365)
        await query.edit_message_text(
            text, parse_mode="MarkdownV2", reply_markup=markup
        )

    elif data == "reading_stats_all":
        text, markup = await get_reading_stats_view(pool, all_time=True)
        await query.edit_message_text(
            text, parse_mode="MarkdownV2", reply_markup=markup
        )

    elif data == "reading_notes":
        current = await reading_queries.get_current_books(pool)
        if not current:
            await query.edit_message_text(
                "📝 *Note lectură*\n\nNu ai cărți în progres pentru care să adaugi note\\.",
                parse_mode="MarkdownV2",
                reply_markup=reading_main_keyboard(),
            )
        else:
            text = "📝 *Adaugă notă*\n\nAlege cartea pentru care vrei să adaugi o notă:"
            await query.edit_message_text(
                text,
                parse_mode="MarkdownV2",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                f"📖 {escape_md(b.get('title', '')[:30])}",
                                callback_data=f"reading_note_book_{b['id']}",
                            )
                        ]
                        for b in current
                    ]
                    + [[InlineKeyboardButton("◀️ Înapoi", callback_data="reading_main")]]
                ),
            )

    elif data.startswith("reading_detail_"):
        book_id = int(parts[-1])
        text, markup = await get_book_detail_view(pool, book_id)
        await query.edit_message_text(
            text, parse_mode="MarkdownV2", reply_markup=markup
        )

    elif data == "reading_update_prompt":
        current = await reading_queries.get_current_books(pool)
        if not current:
            await query.edit_message_text(
                "📖 *Update progres*\n\n_Nu ai cărți în progres\\. Adaugă o carte mai întâi\\.",
                parse_mode="MarkdownV2",
                reply_markup=reading_main_keyboard(),
            )
        else:
            await query.edit_message_text(
                "🔄 *Update progres lectură*\n\nAlege cartea pentru care vrei să actualizezi progresul:",
                parse_mode="MarkdownV2",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                f"📖 {escape_md(b.get('title', '')[:30])}",
                                callback_data=f"reading_update_book_{b['id']}",
                            )
                        ]
                        for b in current
                    ]
                    + [[InlineKeyboardButton("◀️ Înapoi", callback_data="reading_main")]]
                ),
            )

    elif data.startswith("reading_update_book_"):
        book_id = int(parts[-1])
        book = await reading_queries.get_book_by_id(pool, book_id)
        if book:
            await set_state(pool, "reading_update_pages", "reading", "update", book_id)
            current_pages = book.get("pages_read", 0)
            total_pages = book.get("total_pages", "")
            await query.edit_message_text(
                f"🔄 Update *{escape_md(book['title'])}*\n\nPagina curentă: *{current_pages}*/{total_pages}\n\nIntrodu noua pagină:",
                parse_mode="MarkdownV2",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "❌ Anulează", callback_data=f"reading_detail_{book_id}"
                            )
                        ]
                    ]
                ),
            )

    elif data == "reading_complete_prompt":
        current = await reading_queries.get_current_books(pool)
        if not current:
            await query.edit_message_text(
                "🏁 *Finalizează carte*\n\n_Nu ai cărți în progres\\. Adaugă o carte mai întâi\\.",
                parse_mode="MarkdownV2",
                reply_markup=reading_main_keyboard(),
            )
        else:
            await query.edit_message_text(
                "🏁 *Finalizează carte*\n\nAlege cartea pe care ai terminat-o:",
                parse_mode="MarkdownV2",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                f"📖 {escape_md(b.get('title', '')[:30])}",
                                callback_data=f"reading_finish_book_{b['id']}",
                            )
                        ]
                        for b in current
                    ]
                    + [[InlineKeyboardButton("◀️ Înapoi", callback_data="reading_main")]]
                ),
            )

    elif data.startswith("reading_finish_book_"):
        book_id = int(parts[-1])
        book = await reading_queries.get_book_by_id(pool, book_id)
        if book:
            await set_state(pool, "reading_rate_book", "reading", "rate", book_id)
            await query.edit_message_text(
                f"🏁 Finalizează *{escape_md(book['title'])}*\n\nAi vrea să îi dai un rating \\(1\\-5 stele\\)?\n\n_Scrie numărul sau 'nu' dacă nu vrei rating\\._",
                parse_mode="MarkdownV2",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "❌ Fără rating",
                                callback_data=f"reading_finish_no_rating_{book_id}",
                            )
                        ]
                    ]
                ),
            )

    elif data.startswith("reading_finish_no_rating_"):
        book_id = int(parts[-1])
        book = await reading_queries.get_book_by_id(pool, book_id)
        await reading_queries.complete_book(pool, book_id, None)
        await query.answer("Cartea marcată ca terminată!")
        text, markup = await get_reading_dashboard(pool)
        await query.edit_message_text(
            text, parse_mode="MarkdownV2", reply_markup=markup
        )

    elif data.startswith("reading_note_book_"):
        book_id = int(parts[-1])
        book = await reading_queries.get_book_by_id(pool, book_id)
        if book:
            await set_state(pool, "reading_add_note", "reading", "note", book_id)
            await query.edit_message_text(
                f"📝 Notă pentru *{escape_md(book['title'])}*\n\nScrie nota ta \\(poți include și numărul paginii\\):",
                parse_mode="MarkdownV2",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "❌ Anulează", callback_data=f"reading_detail_{book_id}"
                            )
                        ]
                    ]
                ),
            )

    elif data.startswith("reading_view_notes_"):
        book_id = int(parts[-1])
        book = await reading_queries.get_book_by_id(pool, book_id)
        notes = await reading_queries.get_book_notes(pool, book_id)

        if not book:
            await query.answer("Cartea nu a fost găsită.")
            return

        lines = [f"📝 *Note pentru {escape_md(book['title'])}*\n"]

        if not notes:
            lines.append("Nu ai nicio notă pentru această carte.")
        else:
            for i, note in enumerate(notes, 1):
                page_str = (
                    f" \\(p\\. {note['page_number']}\\)"
                    if note.get("page_number")
                    else ""
                )
                lines.append(f"{i}\\. {escape_md(note['content'])}{page_str}")

        keyboard = [
            [
                InlineKeyboardButton(
                    "◀️ Înapoi", callback_data=f"reading_detail_{book_id}"
                )
            ]
        ]

        await query.edit_message_text(
            "\n".join(lines),
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    elif data.startswith("reading_delete_book_"):
        book_id = int(parts[-1])
        book = await reading_queries.get_book_by_id(pool, book_id)
        if book:
            await query.edit_message_text(
                f"⚠️ Șterge carte\n\nEști sigur că vrei să ștergi *{escape_md(book['title'])}* și toate notele?",
                parse_mode="MarkdownV2",
                reply_markup=reading_confirm_delete_keyboard(book_id),
            )

    elif data.startswith("reading_confirm_delete_"):
        book_id = int(parts[-1])
        book = await reading_queries.get_book_by_id(pool, book_id)
        await reading_queries.delete_book(pool, book_id)
        await query.answer("Carte ștearsă!")
        text, markup = await get_reading_library_view(pool)
        await query.edit_message_text(
            text, parse_mode="MarkdownV2", reply_markup=markup
        )

    elif data == "reading_add":
        await set_state(pool, "reading_add_book", "reading", "add", None)
        await query.edit_message_text(
            "➕ *Carte nouă*\n\nIntrodu titlul cărții:\n_Poți include autorul și numărul de pagini în același mesaj \\(ex: '1984 de George Orwell, 328 pagini'\\)_",
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("❌ Anulează", callback_data="reading_main")]]
            ),
        )


async def handle_reading_message(update, pool, state: dict) -> bool:
    """Handles text input for reading state machine."""
    msg_text = update.message.text.strip()
    state_type = state.get("state_type")
    item_id = state.get("item_id")

    print(
        f"📖 handle_reading_message: state_type='{state_type}', msg='{msg_text}'",
        flush=True,
    )

    try:
        if state_type == "reading_add_book":
            import re

            # Strip common prefixes like "adauga cartea", "cartea"
            title = msg_text
            prefixes = [
                "adauga cartea",
                "adaug cartea",
                "adaugati cartea",
                "cartea",
                "book",
                "adauga",
                "adaug",
            ]
            lower_text = msg_text.lower()
            for prefix in prefixes:
                if lower_text.startswith(prefix):
                    title = msg_text[len(prefix) :].strip()
                    break

            author = None
            total_pages = None

            match = re.match(
                r"(.+?)(?:,?\s*de\s+(.+?))?(?:,?\s*(\d+)\s*(?:pag|pagini|pages)?)?$",
                title,
                re.IGNORECASE,
            )
            print(
                f"📖 DEBUG: after regex match, title='{title}', match={match}",
                flush=True,
            )
            if match:
                title = match.group(1).strip() or msg_text
                author = match.group(2).strip() if match.group(2) else None
                pages_str = match.group(3)
                total_pages = int(pages_str) if pages_str else None
                print(
                    f"📖 DEBUG: parsed - title='{title}', author='{author}', pages={total_pages}",
                    flush=True,
                )

            print(f"📖 DEBUG: calling add_book with title='{title}'", flush=True)
            await reading_queries.add_book(pool, title, author, total_pages)
            print("📖 DEBUG: add_book completed", flush=True)
            await clear_state(pool)

            author_str = f" de {author}" if author else ""
            pages_str = f", {total_pages} pagini" if total_pages else ""
            await update.message.reply_text(
                f"✅ *{escape_md(title)}*{escape_md(author_str)} adăugat în bibliotecă{escape_md(pages_str)}\\. 📚",
                parse_mode="MarkdownV2",
            )
            return True

        elif state_type == "reading_update_pages":
            try:
                pages = int(msg_text)
                book = await reading_queries.get_book_by_id(pool, item_id)
                await reading_queries.update_progress(pool, item_id, pages)
                await clear_state(pool)

                if book and book.get("total_pages"):
                    pct = int((pages / book["total_pages"]) * 100)
                    filled = min(pct // 10, 10)
                    bar = "█" * filled + "░" * (10 - filled)
                    progress_str = f"\n`{bar}` {pct}%"
                else:
                    progress_str = ""

                await update.message.reply_text(
                    f"✅ Progres actualizat: pagina *{pages}*{progress_str}",
                    parse_mode="MarkdownV2",
                )
                return True
            except ValueError:
                await update.message.reply_text(
                    "❌ Te rog introdu un număr valid de pagini\\.",
                    parse_mode="MarkdownV2",
                )
                return True

        elif state_type == "reading_rate_book":
            book = await reading_queries.get_book_by_id(pool, item_id)
            rating = None

            if msg_text.lower() not in ("nu", "nu stiu", "fara", "-"):
                try:
                    rating = int(msg_text)
                    if rating < 1 or rating > 5:
                        raise ValueError()
                except ValueError:
                    await update.message.reply_text(
                        "❌ Rating invalid\\. Introdu un număr 1\\-5 sau 'nu'\\.",
                        parse_mode="MarkdownV2",
                    )
                    return True

            await reading_queries.complete_book(pool, item_id, rating)
            await clear_state(pool)

            stars = " ⭐" * rating if rating else ""
            await update.message.reply_text(
                f"✅ *{escape_md(book['title'])}* terminată\\.{stars}",
                parse_mode="MarkdownV2",
            )
            return True

        elif state_type == "reading_add_note":
            book = await reading_queries.get_book_by_id(pool, item_id)
            import re

            page_match = re.search(r"p\.?\s*(\d+)", msg_text, re.IGNORECASE)
            page_number = int(page_match.group(1)) if page_match else None

            note_content = re.sub(
                r"p\.?\s*\d+\s*[:\-]?\s*", "", msg_text, flags=re.IGNORECASE
            ).strip()
            if not note_content:
                note_content = msg_text

            await reading_queries.add_book_note(
                pool, item_id, note_content, page_number
            )
            await clear_state(pool)

            page_str = f" \\(p\\. {page_number}\\)" if page_number else ""
            await update.message.reply_text(
                f"✅ Notă salvată pentru *{escape_md(book['title'])}*{page_str}\\. 📝",
                parse_mode="MarkdownV2",
            )
            return True

    except Exception as e:
        import traceback

        print(f"Error in reading message handler: {e}")
        traceback.print_exc()
        await update.message.reply_text(
            "❌ A apărut o eroare. Te rog încearcă din nou\\.", parse_mode="MarkdownV2"
        )
        await clear_state(pool)
        return True

    return False


# ── Command Handler ─────────────────────────────────────────────────


async def reading_command(update, context) -> None:
    """/reading command handler."""
    pool = context.bot_data["pool"]
    try:
        text, markup = await get_reading_dashboard(pool)
        await update.message.reply_text(
            text, reply_markup=markup, parse_mode="MarkdownV2"
        )
    except Exception as e:
        import logging

        logging.error(f"Error in reading command: {e}")
        await update.message.reply_text(
            "Eroare la deschiderea dashboard\\-ului de lectură\\.",
            parse_mode="MarkdownV2",
        )
