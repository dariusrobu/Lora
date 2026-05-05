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
    """Checks if a similar fact already exists in memory using fuzzy matching."""
    try:
        # Normalize: lowercase, strip, take first 40 chars as prefix
        prefix = new_fact[:40].strip().lower()
        async with pool.acquire() as conn:
            # Check for exact or near-prefix match in same category
            existing = await conn.fetchval(
                """
                SELECT id FROM memory_facts
                WHERE user_id = $1
                AND (category = $2 OR category = $3)
                AND (LOWER(fact) ILIKE $4 OR LOWER(fact) ILIKE $5)
                LIMIT 1
                """,
                user_id,
                category,
                category + "s"
                if not category.endswith("s")
                else category[:-1],  # handle plural variants
                f"{prefix}%",
                f"%{prefix}%",
            )
            return existing is not None
    except Exception:
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
        for f in facts[:5]:  # Limit to top 5 as requested
            # Update last_seen for the fact since it's being used
            await update_fact_seen(pool, f["id"])
            formatted_facts.append(f"• [{f['category'].capitalize()}] {f['fact']}")

        return "\n".join(formatted_facts)

    except Exception as e:
        print(f"ERROR in get_context_memory: {e}")
        return "Eroare la recuperarea memoriei."
