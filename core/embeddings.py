import logging
from typing import List
from google import genai
from google.genai import types
from core.config import GEMINI_API_KEY

client = genai.Client(api_key=GEMINI_API_KEY)

async def get_embedding(text: str) -> List[float]:
    """
    Generates a 768-dimensional embedding for the given text using gemini-embedding-001.
    """
    if not text:
        return []
    
    try:
        response = client.models.embed_content(
            model="gemini-embedding-001",
            contents=text,
            config=types.EmbedContentConfig(
                task_type="RETRIEVAL_DOCUMENT",
                output_dimensionality=768
            )
        )
        return response.embeddings[0].values
    except Exception as e:
        logging.error(f"Error generating embedding: {e}")
        return []
