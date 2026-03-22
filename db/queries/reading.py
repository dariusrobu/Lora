# db/queries/reading.py

async def add_book(pool, title, author=None, total_pages=None) -> int:
    async with pool.acquire() as conn:
        return await conn.fetchval("""
            INSERT INTO books (title, author, total_pages)
            VALUES ($1, $2, $3) RETURNING id
        """, title, author, total_pages)

async def update_progress(pool, book_id, pages_read) -> None:
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE books SET pages_read = $1 WHERE id = $2
        """, pages_read, book_id)

async def complete_book(pool, book_id, rating=None) -> None:
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE books 
            SET status = 'completed', finished_at = CURRENT_DATE, rating = $1
            WHERE id = $2
        """, rating, book_id)

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
        row = await conn.fetchrow("""
            SELECT id, title, author, total_pages, pages_read, status, rating, started_at, finished_at, notes, created_at 
            FROM books 
            WHERE LOWER(title) LIKE LOWER($1)
            ORDER BY created_at DESC LIMIT 1
        """, f"%{title}%")
        return dict(row) if row else None

async def add_book_note(pool, book_id, content, page_number=None) -> None:
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO book_notes (book_id, content, page_number)
            VALUES ($1, $2, $3)
        """, book_id, content, page_number)

async def get_book_notes(pool, book_id) -> list:
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT id, book_id, content, page_number, created_at 
            FROM book_notes 
            WHERE book_id = $1
            ORDER BY created_at ASC
        """, book_id)
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
