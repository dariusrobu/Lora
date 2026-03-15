from typing import List, Optional, Dict, Any

async def add_note(pool, content: str, type: str = "note", tags: List[str] = [], mood: Optional[str] = None, project_id: Optional[int] = None) -> int:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO notes (content, type, tags, mood, project_id)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id
            """,
            content, type, tags, mood, project_id
        )
        return row['id']

async def list_notes(pool, type: Optional[str] = None, project_id: Optional[int] = None, limit: int = 20) -> List[Dict[str, Any]]:
    async with pool.acquire() as conn:
        query = "SELECT * FROM notes"
        params = []
        where_clauses = []
        
        if type:
            params.append(type)
            where_clauses.append(f"type = ${len(params)}")
        
        if project_id:
            params.append(project_id)
            where_clauses.append(f"project_id = ${len(params)}")
            
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
        
        query += " ORDER BY is_pinned DESC, created_at DESC LIMIT " + str(limit)
        rows = await conn.fetch(query, *params)
        return [dict(r) for r in rows]

async def search_notes(pool, search_query: str) -> List[Dict[str, Any]]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM notes 
            WHERE to_tsvector('english', content) @@ plainto_tsquery('english', $1)
            OR $1 = ANY(tags)
            ORDER BY created_at DESC
            """,
            search_query
        )
        return [dict(r) for r in rows]

async def delete_note(pool, note_id: int):
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM notes WHERE id = $1", note_id)
