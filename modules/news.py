import asyncio
from datetime import datetime, timedelta, timezone
import logging
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote_plus

import feedparser
import httpx

from bot.formatter import escape_md

logger = logging.getLogger(__name__)

GOOGLE_NEWS_FEEDS = {
    "general": {
        "title": "Actualitate & Top Știri",
        "icon": "📰",
        "url": "https://news.google.com/rss?hl=ro&gl=RO&ceid=RO:ro",
    },
    "politica": {
        "title": "Politică",
        "icon": "🏛️",
        "url": "https://news.google.com/rss/headlines/section/topic/NATION?hl=ro&gl=RO&ceid=RO:ro",
    },
    "economie": {
        "title": "Economie & Finanțe",
        "icon": "📈",
        "url": "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=ro&gl=RO&ceid=RO:ro",
    },
    "tech": {
        "title": "Tehnologie & AI",
        "icon": "💻",
        "url": "https://news.google.com/rss/headlines/section/topic/TECHNOLOGY?hl=ro&gl=RO&ceid=RO:ro",
    },
}


def _format_relative_time(pub_time: Optional[datetime]) -> str:
    """Returns Romanian relative time string (e.g. acum 3 ore)."""
    if not pub_time:
        return "recent"
    diff = datetime.now(timezone.utc) - pub_time
    hours = diff.total_seconds() / 3600
    if hours < 1:
        mins = int(diff.total_seconds() / 60)
        return f"acum {max(1, mins)} min"
    elif hours < 24:
        return f"acum {int(hours)} ore"
    return "ieri"


async def _fetch_feed_items(
    client: httpx.AsyncClient,
    category_title: str,
    icon: str,
    url: str,
    limit: int = 3,
) -> Tuple[str, str, List[str]]:
    """Fetches articles from a Google News RSS feed, filtering strictly for the last 24h."""
    try:
        response = await client.get(url, timeout=7.0)
        response.raise_for_status()
        feed = feedparser.parse(response.content)

        now = datetime.now(timezone.utc)
        cutoff_24h = now - timedelta(hours=24)
        items: List[str] = []

        for entry in feed.entries:
            pub_time: Optional[datetime] = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                pub_time = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)

            # Strict 24-hour cutoff
            if pub_time and pub_time < cutoff_24h:
                continue

            # Split title and source name (Google News format: "Headline - Source")
            parts = entry.title.rsplit(" - ", 1)
            if len(parts) == 2:
                headline, source = parts[0].strip(), parts[1].strip()
            else:
                headline, source = entry.title.strip(), "Știri"

            time_str = _format_relative_time(pub_time)
            item_md = (
                f"• *{escape_md(headline)}*\n"
                f"  _{escape_md(source)} · {escape_md(time_str)}_"
            )
            items.append(item_md)

            if len(items) >= limit:
                break

        return category_title, icon, items
    except Exception as e:
        logger.warning(f"Error fetching news feed '{category_title}': {e}")
        return category_title, icon, []


async def fetch_news_digest(topic: str = "all", limit: Optional[int] = 3) -> str:
    """Fetches and formats a clean news digest strictly from the last 24 hours."""
    normalized_topic = (topic or "all").lower().strip()
    clean_topic = normalized_topic.replace(";", "l")

    # Ensure safe integer limit
    try:
        safe_limit = int(limit) if limit is not None else 3
    except (ValueError, TypeError):
        safe_limit = 3

    # Map variations & typos to standard feed keys
    if any(k in clean_topic for k in ("politi", "guvern", "senat", "parlament")):
        normalized_topic = "politica"
    elif any(k in clean_topic for k in ("econom", "finan", "bani", "bancar", "piat")):
        normalized_topic = "economie"
    elif any(k in clean_topic for k in ("tech", "tehnol", "gadget", "it", "ai", "soft")):
        normalized_topic = "tech"
    elif any(k in clean_topic for k in ("general", "actual", "top", "lume", "romania", "tara")):
        normalized_topic = "general"

    async with httpx.AsyncClient(follow_redirects=True) as client:
        # 1. Custom topic search (e.g. bursa, alegeri, razboi)
        if normalized_topic not in ("all", "politica", "economie", "tech", "general"):
            search_url = (
                f"https://news.google.com/rss/search?q={quote_plus(normalized_topic + ' when:1d')}"
                f"&hl=ro&gl=RO&ceid=RO:ro"
            )
            _, _, items = await _fetch_feed_items(
                client, f"Știri: {normalized_topic.title()}", "🔍", search_url, limit=max(4, safe_limit)
            )
            if not items:
                return f"⚠️ Nu am găsit știri recente din ultimele 24h despre *{escape_md(topic)}*."

            header = f"📰 *Știri recente despre {escape_md(topic.title())} (ultimele 24h):*\n━━━━━━━━━━━━━━━━━━━━\n\n"
            return header + "\n\n".join(items)

        # 2. Specific single category
        if normalized_topic in GOOGLE_NEWS_FEEDS:
            conf = GOOGLE_NEWS_FEEDS[normalized_topic]
            _, icon, items = await _fetch_feed_items(
                client, conf["title"], conf["icon"], conf["url"], limit=max(4, safe_limit)
            )
            if not items:
                return f"⚠️ Nu am putut prelua știri din secțiunea {conf['title']} în acest moment."

            header = f"{icon} *{escape_md(conf['title'])} (ultimele 24h):*\n━━━━━━━━━━━━━━━━━━━━\n\n"
            return header + "\n\n".join(items)

        # 3. 'all' - Comprehensive briefing: Politică, Economie, General, Tech
        tasks = [
            _fetch_feed_items(
                client,
                GOOGLE_NEWS_FEEDS["politica"]["title"],
                GOOGLE_NEWS_FEEDS["politica"]["icon"],
                GOOGLE_NEWS_FEEDS["politica"]["url"],
                limit=2,
            ),
            _fetch_feed_items(
                client,
                GOOGLE_NEWS_FEEDS["economie"]["title"],
                GOOGLE_NEWS_FEEDS["economie"]["icon"],
                GOOGLE_NEWS_FEEDS["economie"]["url"],
                limit=2,
            ),
            _fetch_feed_items(
                client,
                GOOGLE_NEWS_FEEDS["general"]["title"],
                GOOGLE_NEWS_FEEDS["general"]["icon"],
                GOOGLE_NEWS_FEEDS["general"]["url"],
                limit=2,
            ),
            _fetch_feed_items(
                client,
                GOOGLE_NEWS_FEEDS["tech"]["title"],
                GOOGLE_NEWS_FEEDS["tech"]["icon"],
                GOOGLE_NEWS_FEEDS["tech"]["url"],
                limit=2,
            ),
        ]

        results = await asyncio.gather(*tasks)

        blocks: List[str] = []
        for cat_title, icon, items in results:
            if items:
                block = f"{icon} *{escape_md(cat_title)}:*\n" + "\n".join(items)
                blocks.append(block)

        if not blocks:
            return "⚠️ Nu am putut găsi știri noi din ultimele 24 de ore."

        header = "📰 *Sinteza Știrilor din Ultimele 24h*\n━━━━━━━━━━━━━━━━━━━━\n\n"
        return header + "\n\n".join(blocks)


async def handle_news_intent(
    pool: Any, intent: str, data: Dict[str, Any]
) -> Tuple[str, Any, Optional[int]]:
    """Main handler for the news module."""
    topic = data.get("topic")
    if intent == "get_tech_news" or not topic:
        topic = "tech" if intent == "get_tech_news" else "all"
    limit = data.get("limit") or 3
    reply = await fetch_news_digest(topic=topic, limit=limit)
    return reply, None, None


async def undo_last_action(pool: Any, intent: str, item_id: int) -> Tuple[bool, str]:
    return False, "❌ Anularea nu este disponibilă pentru modulul de știri."


async def fetch_news_articles(
    category: Optional[str] = None, limit: int = 15
) -> List[Dict[str, Any]]:
    """Fetches structured articles for the dashboard and REST API."""
    category_map = {
        "all": None,
        "romania": "politica",
        "business": "economie",
        "finance": "economie",
        "world": "general",
    }
    cat = category_map.get(category.lower() if category else "", category)

    feeds_to_fetch = []
    if cat == "ai":
        feeds_to_fetch.append((
            "ai",
            "Inteligență Artificială",
            "🤖",
            "https://news.google.com/rss/search?q=inteligenta+artificiala+AI+when:3d&hl=ro&gl=RO&ceid=RO:ro",
        ))
    elif cat and cat in GOOGLE_NEWS_FEEDS:
        cfg = GOOGLE_NEWS_FEEDS[cat]
        feeds_to_fetch.append((cat, cfg["title"], cfg["icon"], cfg["url"]))
    else:
        for cat_key, cfg in GOOGLE_NEWS_FEEDS.items():
            feeds_to_fetch.append((cat_key, cfg["title"], cfg["icon"], cfg["url"]))

    articles: List[Dict[str, Any]] = []
    now = datetime.now(timezone.utc)
    cutoff_time = now - timedelta(hours=48)

    async with httpx.AsyncClient(headers={"User-Agent": "Mozilla/5.0 LoraBot/1.0"}) as client:
        for cat_key, title, icon, url in feeds_to_fetch:
            try:
                res = await client.get(url, timeout=7.0)
                if res.status_code != 200:
                    continue
                feed = feedparser.parse(res.content)
                cat_count = 0
                max_per_feed = limit if category else max(3, limit // len(feeds_to_fetch))
                for entry in feed.entries:
                    pub_time: Optional[datetime] = None
                    if hasattr(entry, "published_parsed") and entry.published_parsed:
                        pub_time = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)

                    if pub_time and pub_time < cutoff_time:
                        continue

                    parts = entry.title.rsplit(" - ", 1)
                    headline = parts[0].strip() if len(parts) == 2 else entry.title.strip()
                    source = parts[1].strip() if len(parts) == 2 else "Știri"
                    link = getattr(entry, "link", "")

                    articles.append({
                        "id": f"{cat_key}_{abs(hash(link)) % 1000000}",
                        "title": headline,
                        "source": source,
                        "url": link,
                        "category": cat_key,
                        "category_title": title,
                        "category_icon": icon,
                        "relative_time": _format_relative_time(pub_time),
                        "published_at": pub_time.isoformat() if pub_time else None,
                    })
                    cat_count += 1
                    if cat_count >= max_per_feed:
                        break
            except Exception as e:
                logger.warning(f"Error fetching news feed {cat_key}: {e}")

    articles.sort(key=lambda a: a["published_at"] or "", reverse=True)
    return articles[:limit]

