import asyncio
import logging
import os
from typing import List
from google import genai

_genai_client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY", ""))

async def get_embedding(text: str) -> List[float]:
    """
    Generates an embedding for the given text using Google text-embedding-004.
    """
    if not text:
        return []

    try:
        result = await asyncio.to_thread(
            _genai_client.models.embed_content,
            model="text-embedding-004",
            contents=text
        )
        return result.embeddings[0].values
    except Exception as e:
        logging.error(f"Error generating embedding: {e}")
        return []
