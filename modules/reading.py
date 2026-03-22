# modules/reading.py

from typing import Dict, Any, Tuple
import db.queries.reading as reading_queries
from bot.formatter import escape_md

async def handle_reading_intent(pool, intent: str, data: Dict[str, Any], bot=None) -> Tuple[str, None]:

    if intent == "reading_add":
        title = data.get("title", "")
        author = data.get("author")
        total_pages = data.get("total_pages")
        
        if not title:
            return "Care e titlul cărții?", None
        
        book_id = await reading_queries.add_book(pool, title, author, total_pages)
        
        author_str = f" de {escape_md(author)}" if author else ""
        pages_str = f", {total_pages} pagini" if total_pages else ""
        return data.get("_original_reply", f"*{escape_md(title)}*{author_str} adăugat în bibliotecă{escape_md(pages_str)}\\. 📚"), None

    elif intent == "reading_update":
        title = data.get("title", "")
        pages_read = data.get("pages_read")
        
        if not title or pages_read is None:
            return "Spune-mi cartea și pagina la care ești.", None
        
        book = await reading_queries.get_book_by_title(pool, title)
        if not book:
            return f"Nu am găsit cartea *{escape_md(title)}* în bibliotecă\\.", None
        
        await reading_queries.update_progress(pool, book['id'], pages_read)
        
        progress_str = ""
        category = escape_md(book['title'])
        if book.get('total_pages'):
            pct = int((pages_read / book['total_pages']) * 100)
            filled = min(pct // 10, 10)
            bar = "█" * filled + "░" * (10 - filled)
            progress_str = f"\n`{bar}` {pct}%"
        
        return f"*{category}* — pagina {pages_read}{progress_str}", None

    elif intent == "reading_complete":
        title = data.get("title", "")
        rating = data.get("rating")
        
        if not title:
            return "Care carte ai terminat?", None
        
        book = await reading_queries.get_book_by_title(pool, title)
        if not book:
            return f"Nu am găsit *{escape_md(title)}* în bibliotecă\\.", None
        
        await reading_queries.complete_book(pool, book['id'], rating)
        
        stars = " ⭐" * int(rating) if rating else ""
        return f"*{escape_md(book['title'])}* terminată\\.{stars}", None

    elif intent == "reading_note":
        title = data.get("title", "")
        content = data.get("content", "")
        page = data.get("page_number")
        
        if not title or not content:
            return "Spune-mi cartea și nota.", None
        
        book = await reading_queries.get_book_by_title(pool, title)
        if not book:
            return f"Nu am găsit *{escape_md(title)}*\\.", None
        
        await reading_queries.add_book_note(pool, book['id'], content, page)
        page_str = f" \\(p\\. {page}\\)" if page else ""
        return f"Notă salvată din *{escape_md(book['title'])}*{page_str}\\. 📝", None

    elif intent == "reading_list":
        books = await reading_queries.get_all_books(pool)
        if not books:
            return "Biblioteca e goală\\. Adaugă prima carte cu 'am început să citesc X'\\.", None
        
        reading = [b for b in books if b['status'] == 'reading']
        completed = [b for b in books if b['status'] == 'completed']
        
        lines = ["📚 *Biblioteca ta*\n"]
        
        if reading:
            lines.append("*În curs*")
            for b in reading:
                title = escape_md(b['title'])
                author = f" — _{escape_md(b['author'])}_" if b.get('author') else ""
                
                progress = ""
                if b.get('total_pages') and b.get('pages_read'):
                    pct = int((b['pages_read'] / b['total_pages']) * 100)
                    filled = min(pct // 10, 10)
                    bar = "█" * filled + "░" * (10 - filled)
                    progress = f"\n  `{bar}` {b['pages_read']}/{b['total_pages']} pag \\({pct}%\\)"
                elif b.get('pages_read'):
                    progress = f" — p\\. {b['pages_read']}"
                
                lines.append(f"• *{title}*{author}{progress}")
            lines.append("")
        
        if completed:
            lines.append("*Terminate*")
            for b in completed[:10]:
                title = escape_md(b['title'])
                stars = " ⭐" * b['rating'] if b.get('rating') else ""
                year = f" _{b['finished_at'].year}_" if b.get('finished_at') else ""
                lines.append(f"• {title}{year}{stars}")
        
        return "\n".join(lines), None

    elif intent == "reading_stats":
        stats = await reading_queries.get_reading_stats(pool)
        if not stats or not stats.get('completed'):
            return "Nu ai terminat nicio carte încă\\.", None
        
        lines = [
            "📊 *Reading Stats*\n",
            f"• Terminate total: *{stats['completed']}*",
            f"• În curs: *{stats['in_progress']}*",
            f"• Anul acesta: *{stats['this_year']}*",
        ]
        if stats.get('avg_rating'):
            lines.append(f"• Rating mediu: *{stats['avg_rating']}* ⭐")
        
        return "\n".join(lines), None

    return "Nu am înțeles cererea legată de cărți\\.", None
