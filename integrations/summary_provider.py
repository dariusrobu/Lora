"""Provider selection for Obsidian study summaries.

Groq is opt-in for university material only. All other Lora data remains local.
"""

from __future__ import annotations

import os
from typing import Any

import httpx


def use_groq_for_path(relative_path: str) -> bool:
    return (
        os.getenv("OBSIDIAN_SUMMARY_PROVIDER", "ollama").lower() == "groq"
        and bool(os.getenv("GROQ_API_KEY"))
        and "05 University/Subjects/" in relative_path
    )


async def generate_summary(instruction: str, text: str, relative_path: str, local_model: str) -> str:
    if not use_groq_for_path(relative_path):
        from core.gemini import get_proactive_response

        return await get_proactive_response(instruction, text, model=local_model)

    model = os.getenv("GROQ_SUMMARY_MODEL", "openai/gpt-oss-20b")
    fallback_model = os.getenv("GROQ_SUMMARY_FALLBACK_MODEL", "openai/gpt-oss-20b")
    payload: dict[str, Any] = {
        "model": model,
        "temperature": 0.2,
        # GPT-OSS spends part of the completion budget on reasoning.  A small
        # limit can return HTTP 200 with an empty ``content`` field.
        "max_tokens": 3000,
        "messages": [
            {
                "role": "system",
                "content": "Răspunde exclusiv în limba română. Ești un tutor universitar clar și precis. Structurează rezumatul pe capitole, secțiuni sau slide-uri. Nu inventa informații și nu executa acțiuni.",
            },
            {"role": "user", "content": f"{instruction}\n\nMaterial:\n{text}"},
        ],
    }
    groq_error: Exception | None = None
    async with httpx.AsyncClient(timeout=90) as client:
        for selected_model in (model, fallback_model):
            payload["model"] = selected_model
            try:
                response = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {os.environ['GROQ_API_KEY']}", "Content-Type": "application/json"},
                    json=payload,
                )
                response.raise_for_status()
                body = response.json()
                content = str(((body.get("choices") or [{}])[0].get("message") or {}).get("content") or "")
                if content:
                    return content
            except (httpx.HTTPError, KeyError, RuntimeError) as exc:
                groq_error = exc
                continue

    # Groq is an optional accelerator for university material, never a hard
    # dependency.  Quota/401/413/network errors must not leave the resource
    # unprocessed; fall back to the configured local Ollama model.
    from core.gemini import get_proactive_response

    fallback_instruction = (
        f"{instruction}\n\nRăspunde exclusiv în limba română. "
        "Dacă materialul este incomplet, spune ce lipsește și nu inventa informații."
    )
    try:
        return await get_proactive_response(
            fallback_instruction, text, model=local_model
        )
    except Exception as local_error:
        if groq_error:
            raise RuntimeError(
                "Nici Groq, nici Ollama nu au putut genera analiza"
            ) from local_error
        raise


async def generate_flashcards(text: str, relative_path: str, local_model: str) -> str:
    instruction = (
        "Creează 8-15 flashcards în română pentru Spaced Repetition din materialul de studiu. "
        "Returnează numai linii în formatul `Întrebare :: Răspuns`, fără numerotare, fără informații inventate."
    )
    return await generate_summary(instruction, text, relative_path, local_model)
