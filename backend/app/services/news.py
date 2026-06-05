from datetime import datetime
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus

import feedparser
import httpx

from app.config import get_settings
from app.models import Stock, TrackingItem


class NewsService:
    def __init__(self) -> None:
        self.settings = get_settings()

    async def search(self, stock: Stock, item: TrackingItem) -> list[dict]:
        query = item.query or f"{stock.ticker} {stock.company_name} {item.label}"
        url = f"https://news.google.com/rss/search?q={quote_plus(query)}&hl=en-US&gl=US&ceid=US:en"
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
        parsed = feedparser.parse(response.text)
        results = []
        for entry in parsed.entries[: self.settings.news_max_items_per_tracking_item]:
            published_at = self._parse_date(entry.get("published"))
            results.append(
                {
                    "title": entry.get("title", "").strip(),
                    "summary": entry.get("summary", "").strip(),
                    "url": entry.get("link"),
                    "source": "google_news_rss",
                    "published_at": published_at,
                    "raw_payload": {
                        "id": entry.get("id"),
                        "source": entry.get("source", {}),
                    },
                }
            )
        return [result for result in results if result["title"]]

    def _parse_date(self, value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return None

