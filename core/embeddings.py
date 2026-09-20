import logging
from typing import List


async def get_embedding(text: str) -> List[float]:
    """
    Generates an embedding locally through the dedicated Ollama embedding model.

    An unavailable model returns an empty vector.  Returning a fabricated
    all-zero vector would make unrelated memories appear semantically equal.
    """
    if not text:
        return []

    # Try Ollama.
    from core.config import OLLAMA_EMBED_MODEL, OLLAMA_HOST
    import asyncio
    try:
        from ollama import AsyncClient
        ollama_client = AsyncClient(host=OLLAMA_HOST)
        response = await asyncio.wait_for(
            ollama_client.embeddings(model=OLLAMA_EMBED_MODEL, prompt=text),
            timeout=10.0,
        )
        if "embedding" in response:
            return response["embedding"]
    except Exception as e:
        logging.warning("Ollama embedding failed: %s", e)

    logging.warning("Embedding unavailable; semantic memory is temporarily disabled")
    return []
