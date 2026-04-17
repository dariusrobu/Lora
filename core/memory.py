import asyncio
import json
import traceback
from google.genai import types
from db.queries.memory import save_memory_fact, get_relevant_facts, update_fact_seen


async def extract_and_save_facts(
    pool, client, user_message: str, assistant_reply: str
) -> None:
    """Analyzes the message exchange and extracts new facts to store in long-term memory."""
    try:
        # Get some context to avoid duplicates
        existing_facts_text = await get_context_memory(pool, user_message)

        prompt = f"""
Analyze the following exchange between a User and their AI Assistant (Lora).
Extract any new, noteworthy facts about the user that should be remembered long-term.
Facts should be personal, significant, or related to preferences, patterns, achievements, and people.

EXTRACT PEOPLE: If the user mentions any person's name (first name, full name, nickname),
extract it with the context. Examples:
- "Am vorbit cu Ana despre proiect" → {{"category": "people", "fact": "A discutat cu Ana despre un proiect"}}
- "Mihai e prietenul meu cel mai bun" → {{"category": "people", "fact": "Prietenul lui e Mihai"}}
- "Am întâlnit-o pe Elena la conferință" → {{"category": "people", "fact": "A întâlnit-o pe Elena la o conferință"}}

EXISTING KNOWLEDGE (Do NOT repeat these):
{existing_facts_text}

USER MESSAGE:
{user_message}

ASSISTANT REPLY:
{assistant_reply}

RETURN ONLY a JSON list of objects (no markdown fences):
[
  {{
    "category": "preference" | "pattern" | "personal" | "achievement" | "people",
    "fact": "The fact in Romanian (direct, concise, third-person e.g. 'Îi place...', 'Locuiește...', 'A discutat cu...')",
    "is_update": boolean (true if this updates an existing fact),
    "confidence": 0.0 - 1.0
  }}
]
If no new facts are found, return an empty list [].
Do NOT extract trivial strings like "User said hello".
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

            if fact:
                await save_memory_fact(pool, category, fact, source, confidence)
                print(f"🧠 MEMORY SAVED: [{category}] {fact}")

    except Exception as e:
        print(f"ERROR in extract_and_save_facts: {e}")
        traceback.print_exc()


async def get_context_memory(pool, current_message: str) -> str:
    """Retrieves relevant facts from long-term memory to include in the context.

    Args:
        pool: Database connection pool.
        current_message: The user's current message to search for relevant facts.

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
        if not keywords:
            return "Nicio amintire relevantă identificată."

        facts = await get_relevant_facts(pool, keywords)

        if not facts:
            return "Nicio amintire relevantă identificată."

        formatted_facts = []
        for f in facts:
            # Update last_seen for the fact since it's being used
            await update_fact_seen(pool, f["id"])
            formatted_facts.append(f"• [{f['category'].capitalize()}] {f['fact']}")

        return "\n".join(formatted_facts)

    except Exception as e:
        print(f"ERROR in get_context_memory: {e}")
        return "Eroare la recuperarea memoriei."
