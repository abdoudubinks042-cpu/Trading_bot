import aiohttp
import asyncio
import logging
from datetime import datetime
import feedparser
from config import Config

logger = logging.getLogger(__name__)

POSITIVE_KEYWORDS = ['bull','surge','rally','gain','rise','bullish','hausse','rebond','record','profit']
NEGATIVE_KEYWORDS = ['bear','crash','drop','fall','dump','bearish','loss','baisse','chute','perte']

class NewsFetcher:
    def __init__(self):
        self.session = None
        self.news_cache = []
        self.cache_time = None
        self.cache_ttl = 300

    async def _get_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session

    def _analyze_sentiment(self, text):
        text = text.lower()
        pos = sum(1 for k in POSITIVE_KEYWORDS if k in text)
        neg = sum(1 for k in NEGATIVE_KEYWORDS if k in text)
        return 'positive' if pos > neg else 'negative' if neg > pos else 'neutral'

    async def _fetch_cryptocompare(self):
        url = "https://min-api.cryptocompare.com/data/v2/news/?lang=EN&sortOrder=latest"
        try:
            session = await self._get_session()
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as r:
                if r.status == 200:
                    data = await r.json()
                    news = []
                    for a in data.get('Data', [])[:5]:
                        title = a.get('title', '')
                        ts = a.get('published_on', 0)
                        try:
                            dt = datetime.fromtimestamp(ts)
                            diff = datetime.now() - dt
                            time_str = f"Il y a {diff.seconds//60}m" if diff.seconds < 3600 else f"Il y a {diff.seconds//3600}h"
                        except:
                            time_str = "Récent"
                        news.append({'title': title[:100], 'url': a.get('url',''), 'time': time_str, 'sentiment': self._analyze_sentiment(title), 'source': 'CryptoCompare'})
                    return news
        except Exception as e:
            logger.warning(f"CryptoCompare: {e}")
        return []

    async def get_latest_news(self, limit=5):
        if self.news_cache and self.cache_time:
            if (datetime.now() - self.cache_time).seconds < self.cache_ttl:
                return self.news_cache[:limit]
        all_news = await self._fetch_cryptocompare()
        seen = set()
        unique = []
        for item in all_news:
            key = item['title'][:40].lower()
            if key not in seen:
                seen.add(key)
                unique.append(item)
        self.news_cache = unique
        self.cache_time = datetime.now()
        return unique[:limit]
