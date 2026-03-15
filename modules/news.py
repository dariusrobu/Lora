import feedparser
import httpx
import asyncio
from typing import List, Dict, Any, Optional

RSS_FEEDS = {
    "tech": "https://feeds.feedburner.com/TechCrunch/",
    "hacker_news": "https://news.ycombinator.com/rss",
    "romania_insider": "https://www.romania-insider.com/feed"
}

async def fetch_feed(client: httpx.AsyncClient, source: str, url: str, limit: int) -> List[str]:
    """Fetches a single feed and returns a list of formatted headlines."""
    try:
        response = await client.get(url, timeout=10.0)
        response.raise_for_status()
        # feedparser.parse can take a string/bytes
        feed = feedparser.parse(response.content)
        items = []
        for entry in feed.entries[:limit]:
            items.append(f"• {entry.title} ({source.replace('_', ' ').title()})")
        return items
    except Exception as e:
        print(f"Error fetching news from {source}: {e}")
        return []

async def fetch_tech_news(limit: int = 3) -> str:
    """
    Fetches latest tech news from RSS feeds in parallel and returns a summary string.
    """
    async with httpx.AsyncClient(follow_redirects=True) as client:
        tasks = [fetch_feed(client, source, url, limit) for source, url in RSS_FEEDS.items()]
        results = await asyncio.gather(*tasks)
    
    # Flatten results
    news_items = [item for sublist in results for item in sublist]

    if not news_items:
        return "Nu am putut găsi știri tech în acest moment."

    return "Știri Tech de ultimă oră:\n" + "\n".join(news_items[:limit*2])
