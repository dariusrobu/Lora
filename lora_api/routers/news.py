from typing import Optional
from fastapi import APIRouter, Depends, Query
from lora_api.auth import get_current_user
from lora_api.serializers import clean_dict
from modules.news import fetch_news_articles

router = APIRouter(prefix="/api/news", tags=["news"])


@router.get("")
async def get_news(
    category: Optional[str] = Query(None, description="Category: general, politica, economie, tech"),
    limit: int = Query(15, ge=1, le=50),
    user=Depends(get_current_user),
):
    """Returns live Romanian news articles from the last 24 hours."""
    articles = await fetch_news_articles(category=category, limit=limit)
    return [clean_dict(a) for a in articles]
