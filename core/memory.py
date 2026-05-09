import asyncio
import json
import traceback
from google.genai import types
from db.queries.memory import save_memory_fact, get_relevant_facts, update_fact_seen


async def extract_and_save_facts(
    pool, client, user_id: int, user_message: str, assistant_reply: str
) -> None:
    """Analyzes the message exchange and extracts new facts to store in long-term memory."""
    try:
        # Get some context to avoid duplicates
        existing_facts_text = await get_context_memory(pool, user_id, user_message)

        prompt = f"""
Analyze the following exchange between a User and their AI Assistant (Lora).
Extract any new, noteworthy facts about the user that should be remembered long-term.

CATEGORIES:
- "preference" — ce îi place/nu îi place (mâncare, muzică, stil de lucru)
- "pattern" — obiceiuri recurente, rutine, comportamente
- "personal" — informații personale (vârstă, oraș, job, studii)
- "achievement" — realizări, reușite, milestone-uri
- "people" — persoane menționate și relația cu userul
- "opinion" — păreri puternice despre subiecte (politică, tech, viață)
- "goal" — obiective, planuri de viitor, aspirații
- "relationship" — detalii despre relații (partener, familie, prieteni)

EXTRACT PEOPLE: If the user mentions any person's name, extract it with the relationship context.

EXISTING KNOWLEDGE (Do NOT repeat these — if a fact is already known, skip it):
{existing_facts_text}

USER MESSAGE:
{user_message}

ASSISTANT REPLY:
{assistant_reply}

RULES:
1. Extract ONLY meaningful, long-term-relevant facts.
2. DO NOT extract: greetings, trivial statements, bot commands, questions about the bot itself.
3. DO NOT extract facts about the assistant (Lora). Only about the USER.
4. Each fact must be in Romanian, third-person, concise (max 15 words).
5. Confidence: 1.0 for explicit statements, 0.8 for inferred, 0.6 for uncertain.
6. If the user shares an OPINION during chat, capture it as category "opinion".
7. If the user mentions FUTURE PLANS, capture as category "goal".

RETURN ONLY a JSON list (no markdown fences):
[
  {{
    "category": "...",
    "fact": "...",
    "is_update": boolean,
    "confidence": 0.0 - 1.0
  }}
]
If no new facts → return []
"""
        response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-2.5-flash",
            contents=[types.Content(role="user", parts=[types.Part(text=prompt)])],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1,
            ),
        )

        raw_text = response.text.strip()
        if not raw_text:
            return

        facts = json.loads(raw_text)
        if not isinstance(facts, list):
            return

        for fact_data in facts:
            category = fact_data.get("category", "personal")
            fact = fact_data.get("fact")
            source = fact_data.get("source", "user_stated")
            confidence = fact_data.get("confidence", 1.0)

            if not fact or confidence < 0.6:
                continue

            # Deduplication: check if a similar fact already exists
            is_duplicate = await _is_duplicate_fact(pool, user_id, fact, category)
            if is_duplicate:
                print(f"🔁 MEMORY SKIP (duplicate): [{category}] {fact}")
                continue

            await save_memory_fact(pool, user_id, category, fact, source, confidence)
            print(f"🧠 MEMORY SAVED: [{category}] {fact}")

    except Exception as e:
        print(f"ERROR in extract_and_save_facts: {e}")
        traceback.print_exc()


async def _is_duplicate_fact(pool, user_id: int, new_fact: str, category: str) -> bool:
    """Checks if a similar fact already exists in memory using keyword overlap and fuzzy matching."""
    try:
        # 1. Clean and tokenize the new fact
        import re
        words = [w.lower() for w in re.findall(r'\w+', new_fact) if len(w) >= 3]
        if not words:
            return False
            
        async with pool.acquire() as conn:
            # 2. Check for prefix match (fast)
            prefix = new_fact[:30].strip().lower()
            existing_prefix = await conn.fetchval(
                "SELECT id FROM memory_facts WHERE user_id = $1 AND LOWER(fact) ILIKE $2 LIMIT 1",
                user_id, f"%{prefix}%"
            )
            if existing_prefix:
                return True

            # 3. Keyword overlap check (more robust)
            # We search for facts that contain at least 2 of the main keywords
            search_pattern = " & ".join(words[:3]) # Use first 3 keywords
            existing_semantic = await conn.fetchval(
                """
                SELECT id FROM memory_facts 
                WHERE user_id = $1 
                AND to_tsvector('simple', fact) @@ to_tsquery('simple', $2)
                LIMIT 1
                """,
                user_id, search_pattern
            )
            return existing_semantic is not None
            
    except Exception as e:
        print(f"Deduplication check error: {e}")
        return False


async def get_context_memory(
    pool, user_id: int, current_message: str, category_hint: str = None
) -> str:
    """Retrieves relevant facts from long-term memory to include in the context.

    Args:
        pool: Database connection pool.
        current_message: The user's current message to search for relevant facts.
        category_hint: Optional category to prioritize.

    Returns:
        A formatted string of relevant facts.
    """
    try:
        # Simple keyword extraction from the current message
        keywords = [
            word.lower().rstrip(".,!?")
            for word in current_message.split()
            if len(word) >= 3
        ]

        # 1. Fetch relevant facts by keywords
        facts = []
        if keywords:
            facts = await get_relevant_facts(pool, keywords)

        # 2. If we have a category hint, fetch a few from that category too
        if category_hint:
            from db.queries.memory import get_all_facts_by_category

            cat_facts = await get_all_facts_by_category(pool, category_hint)
            # Merge and avoid duplicates
            existing_ids = {f["id"] for f in facts}
            for cf in cat_facts[:3]:
                if cf["id"] not in existing_ids:
                    facts.append(cf)

        if not facts:
            return "Nicio amintire relevantă identificată."

        formatted_facts = []
        for f in facts[:15]:  # Increased limit to 15 for better deduplication
            # Update last_seen for the fact since it's being used
            await update_fact_seen(pool, f["id"])
            formatted_facts.append(f"• [{f['category'].capitalize()}] {f['fact']}")

        return "\n".join(formatted_facts)

    except Exception as e:
        print(f"ERROR in get_context_memory: {e}")
        return "Eroare la recuperarea memoriei."


async def optimize_user_memory(pool, client, user_id: int) -> str:
    """Uses Gemini to deduplicate and clean up all memories for a user."""
    from db.queries.memory import list_all_memories, delete_fact

    try:
        memories = await list_all_memories(pool)
        if not memories:
            return "Nu am nicio amintire de optimizat."

        facts_text = ""
        for m in memories:
            facts_text += f"ID: {m['id']} | [{m['category']}] {m['fact']}\n"

        prompt = f"""
Analyze the following list of facts remembered about the user.
Identify redundant, repetitive, or conflicting information.
Propose a cleanup plan to make the memory concise and unique.

RULES:
1. If two facts are almost identical, keep the most detailed one and mark the other for deletion.
2. If two facts can be merged into one concise fact, propose the merge.
3. Remove trivial or nonsensical facts.
4. Keep the output in Romanian, third person.

CURRENT MEMORIES:
{facts_text}

RETURN ONLY a JSON object (no markdown):
{{
  "to_delete": [id1, id2, ...],
  "to_update": [
    {{ "id": id, "fact": "new fact text", "category": "..." }}
  ],
  "to_add": [
    {{ "fact": "new merged fact", "category": "..." }}
  ]
}}
"""
        response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-2.5-flash",
            contents=[types.Content(role="user", parts=[types.Part(text=prompt)])],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1,
            ),
        )

        plan = json.loads(response.text.strip())
        
        async with pool.acquire() as conn:
            # 1. Delete
            for fid in plan.get("to_delete", []):
                await conn.execute("DELETE FROM memory_facts WHERE id = $1", fid)
            
            # 2. Update
            for item in plan.get("to_update", []):
                await conn.execute(
                    "UPDATE memory_facts SET fact = $1, category = $2 WHERE id = $3",
                    item["fact"], item["category"], item["id"]
                )
            
            # 3. Add
            for item in plan.get("to_add", []):
                await conn.execute(
                    "INSERT INTO memory_facts (user_id, fact, category, source) VALUES ($1, $2, $3, 'optimization')",
                    user_id, item["fact"], item["category"]
                )

        total_deleted = len(plan.get("to_delete", []))
        total_updated = len(plan.get("to_update", []))
        total_added = len(plan.get("to_add", []))
        
        return f"Optimizare completă! 🧠✨\nAm eliminat {total_deleted} duplicate și am consolidat {total_updated + total_added} amintiri."

    except Exception as e:
        print(f"ERROR in optimize_user_memory: {e}")
        traceback.print_exc()
        return "A apărut o eroare la optimizarea memoriei."
