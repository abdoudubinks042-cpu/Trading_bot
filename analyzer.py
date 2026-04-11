import asyncio
import aiohttp
import logging
from datetime import datetime
from config import Config

logger = logging.getLogger(__name__)

class MarketAnalyzer:
    def __init__(self):
        self.session = None
        self.cache = {}
        self.cache_ttl = 60

    async def _get_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session

    async def get_price(self, symbol):
        try:
            session = await self._get_session()
            url = f"https://api.binance.com/api/v3/ticker/24hr?symbol={symbol}"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as r:
                if r.status == 200:
                    data = await r.json()
                    return {
                        'price': float(data['lastPrice']),
                        'change': float(data['priceChangePercent']),
                        'high': float(data['highPrice']),
                        'low': float(data['lowPrice']),
                        'volume': float(data['volume']),
                    }
        except Exception as e:
            logger.error(f"Price error {symbol}: {e}")
        return None

    async def get_signal(self, symbol):
        try:
            data = await self.get_price(symbol)
            if not data:
                return {'symbol': symbol, 'direction': 'NEUTRE', 'strength': 0, 'timestamp': datetime.now().strftime('%H:%M %d/%m/%Y')}

            price = data['price']
            change = data['change']
            high = data['high']
            low = data['low']

            # Signal basé sur le % de changement 24h et position dans le range
            score = 0
            range_size = high - low if high != low else 1
            position = (price - low) / range_size

            if change > 3: score += 2
            elif change > 1: score += 1
            elif change < -3: score -= 2
            elif change < -1: score -= 1

            if position < 0.3: score += 1
            elif position > 0.7: score -= 1

            direction = 'BUY' if score >= 2 else 'SELL' if score <= -2 else 'NEUTRE'
            strength = min(5, abs(score) + 1)

            if direction == 'BUY':
                sl = round(price * 0.99, 4)
                tp1 = round(price * 1.05, 4)
                tp2 = round(price * 1.10, 4)
            elif direction == 'SELL':
                sl = round(price * 1.01, 4)
                tp1 = round(price * 0.95, 4)
                tp2 = round(price * 0.90, 4)
            else:
                sl = tp1 = tp2 = price

            return {
                'symbol': symbol,
                'direction': direction,
                'price': round(price, 4),
                'sl': sl, 'tp1': tp1, 'tp2': tp2,
                'strength': strength,
                'change': change,
                'timeframe': '24H',
                'timestamp': datetime.now().strftime('%H:%M %d/%m/%Y'),
            }
        except Exception as e:
            logger.error(f"Signal error {symbol}: {e}")
            return {'symbol': symbol, 'direction': 'NEUTRE', 'strength': 0, 'timestamp': datetime.now().strftime('%H:%M %d/%m/%Y')}

    async def get_detailed_analysis(self, symbol):
        data = await self.get_price(symbol)
        if not data:
            return {}
        change = data['change']
        return {
            'change_24h': f"{change:+.2f}%",
            'high_24h': data['high'],
            'low_24h': data['low'],
            'trend': "📈 HAUSSIÈRE" if change > 0 else "📉 BAISSIÈRE",
            'volume_trend': "📈 Actif" if data['volume'] > 1000 else "→ Normal",
        }
