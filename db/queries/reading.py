# db/queries/reading.py

from datetime import timedelta


async def add_book(pool, title, author=None, total_pages=None) -> int:
    async with pool.acquire() as conn:
        return await conn.fetchval(
            """
            INSERT INTO books (title, author, total_pages)
            VALUES ($1, $2, $3) RETURNING id
        """,
            title,
            author,
            total_pages,
        )


async def update_progress(pool, book_id, pages_read) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE books SET pages_read = $1 WHERE id = $2
        """,
            pages_read,
            book_id,
        )


async def complete_book(pool, book_id, rating=None) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE books 
            SET status = 'completed', finished_at = CURRENT_DATE, rating = $1
            WHERE id = $2
        """,
            rating,
            book_id,
        )


async def get_current_books(pool) -> list:
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT id, title, author, total_pages, pages_read, status, rating, started_at, finished_at, notes, created_at 
            FROM books 
            WHERE status = 'reading'
            ORDER BY created_at DESC
        """)
        return [dict(r) for r in rows]


async def get_all_books(pool) -> list:
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT id, title, author, total_pages, pages_read, status, rating, started_at, finished_at, notes, created_at 
            FROM books
            ORDER BY 
                CASE status WHEN 'reading' THEN 0 WHEN 'completed' THEN 1 ELSE 2 END,
                created_at DESC
        """)
        return [dict(r) for r in rows]


async def get_book_by_title(pool, title) -> dict | None:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, title, author, total_pages, pages_read, status, rating, started_at, finished_at, notes, created_at 
            FROM books 
            WHERE LOWER(title) LIKE LOWER($1)
            ORDER BY created_at DESC LIMIT 1
        """,
            f"%{title}%",
        )
        return dict(row) if row else None


async def add_book_note(pool, book_id, content, page_number=None) -> int:
    async with pool.acquire() as conn:
        return await conn.fetchval(
            """
            INSERT INTO book_notes (book_id, content, page_number)
            VALUES ($1, $2, $3)
            RETURNING id
        """,
            book_id,
            content,
            page_number,
        )


async def delete_book_note(pool, note_id: int) -> bool:
    async with pool.acquire() as conn:
        result = await conn.execute("DELETE FROM book_notes WHERE id = $1", note_id)
        return "DELETE 1" in result


async def get_book_notes(pool, book_id) -> list:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, book_id, content, page_number, created_at 
            FROM book_notes 
            WHERE book_id = $1
            ORDER BY created_at ASC
        """,
            book_id,
        )
        return [dict(r) for r in rows]


async def get_reading_stats(pool) -> dict:
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT 
                COUNT(*) FILTER (WHERE status = 'completed') as completed,
                COUNT(*) FILTER (WHERE status = 'reading') as in_progress,
                COUNT(*) FILTER (WHERE status = 'completed' 
                    AND finished_at >= DATE_TRUNC('year', CURRENT_DATE)) as this_year,
                ROUND(AVG(rating) FILTER (WHERE rating IS NOT NULL), 1) as avg_rating
            FROM books
        """)
        return dict(row) if row else {}


async def get_reading_stats_detailed(pool, days: int = 30) -> dict:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT 
                COUNT(*) FILTER (WHERE status = 'completed' 
                    AND finished_at >= CURRENT_DATE - INTERVAL '1 day' * $1) as completed_period,
                COALESCE(SUM(pages_read) FILTER (
                    WHERE started_at >= CURRENT_DATE - INTERVAL '1 day' * $1
                ), 0) as pages_read_period,
                COUNT(*) FILTER (WHERE status = 'reading') as currently_reading,
                COUNT(*) FILTER (WHERE status = 'completed') as total_completed,
                ROUND(AVG(rating) FILTER (
                    WHERE rating IS NOT NULL 
                    AND finished_at >= CURRENT_DATE - INTERVAL '1 day' * $1
                ), 1) as avg_rating_period
            FROM books
        """,
            days,
        )
        return dict(row) if row else {}


async def get_reading_streak(pool) -> int:
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT DISTINCT started_at as log_date
            FROM books
            WHERE pages_read > 0
            ORDER BY started_at DESC
        """)

        if not rows:
            return 0

        streak = 0
        today = None
        for row in rows:
            log_date = row["log_date"]
            if today is None:
                today = log_date
                streak = 1
            else:
                expected = today - timedelta(days=1)
                if log_date == expected:
                    streak += 1
                    today = log_date
                else:
                    break
        return streak


async def get_recent_completed_books(pool, limit: int = 5) -> list:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, title, author, rating, finished_at, total_pages
            FROM books
            WHERE status = 'completed'
            ORDER BY finished_at DESC
            LIMIT $1
        """,
            limit,
        )
        return [dict(r) for r in rows]


async def get_book_by_id(pool, book_id: int) -> dict | None:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, title, author, total_pages, pages_read, status, rating, 
                   started_at, finished_at, notes, created_at
            FROM books 
            WHERE id = $1
        """,
            book_id,
        )
        return dict(row) if row else None


async def delete_book(pool, book_id: int) -> bool:
    async with pool.acquire() as conn:
        result = await conn.execute("DELETE FROM books WHERE id = $1", book_id)
        return "DELETE 1" in result


async def get_books_by_status(pool, status: str) -> list:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, title, author, total_pages, pages_read, status, rating, 
                   started_at, finished_at, created_at
            FROM books
            WHERE status = $1
            ORDER BY created_at DESC
        """,
            status,
        )
        return [dict(r) for r in rows]


async def update_book(pool, book_id: int, **kwargs) -> None:
    if not kwargs:
        return

    fields = []
    values = [book_id]
    for i, (key, value) in enumerate(kwargs.items(), start=2):
        fields.append(f"{key} = ${i}")
        values.append(value)

    query = f"UPDATE books SET {', '.join(fields)} WHERE id = $1"
    async with pool.acquire() as conn:
        await conn.execute(query, *values)
