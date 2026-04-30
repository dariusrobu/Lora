import os
import asyncio
import asyncpg
from dotenv import load_dotenv

load_dotenv()

async def check():
    conn = await asyncpg.connect(os.getenv('DATABASE_URL'))
    query = "preferinte cafea"
    words = [f"%{w[:4]}%" for w in query.split() if len(w) >= 3]
    print(f"Words: {words}")
    
    condition = " OR ".join([f"fact ILIKE ${i+2}" for i in range(len(words))])
    sql = f"SELECT fact FROM memory_facts WHERE user_id = $1 AND ({condition}) LIMIT 5"
    print(f"SQL: {sql}")
    
    rows = await conn.fetch(sql, 6838073664, *words)
    for r in rows:
        print(dict(r))
    await conn.close()

if __name__ == "__main__":
    asyncio.run(check())
