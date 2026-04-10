import asyncio
import aiohttp
import logging
from datetime import datetime
import pandas as pd
import numpy as np
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

    def _is_crypto(self, symbol):
        return any(symbol.endswith(c) for c in ['USDT','BTC','ETH','BNB'])

    def _generate_demo_data(self, symbol):
        np.random.seed(hash(symbol) % 1000)
        n = 100
        base = {'BTCUSDT':65000,'ETHUSDT':3200,'EURUSD':1.08,'XAUUSD':2300}.get(symbol,100)
        close = base + np.cumsum(np.random.randn(n) * base * 0.005)
        return pd.DataFrame({
            'timestamp': pd.date_range(end=datetime.now(), periods=n, freq='1h'),
            'open': close * (1 + np.random.randn(n)*0.001),
            'high': close * (1 + np.abs(np.random.randn(n))*0.003),
            'low': close * (1 - np.abs(np.random.randn(n))*0.003),
            'close': close,
            'volume': np.random.uniform(1e6, 5e6, n),
        })

    async def get_ohlcv(self, symbol, interval='1h', limit=100):
        cache_key = f"{symbol}_{interval}"
        cached = self.cache.get(cache_key)
        if cached and (datetime.now() - cached['ts']).seconds < self.cache_ttl:
            return cached['df']
        df = None
        if self._is_crypto(symbol):
            df = await self._fetch_binance(symbol, interval, limit)
        if df is None:
            df = self._generate_demo_data(symbol)
        self.cache[cache_key] = {'df': df, 'ts': datetime.now()}
        return df

    async def _fetch_binance(self, symbol, interval, limit):
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
        try:
            session = await self._get_session()
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as r:
                if r.status == 200:
                    data = await r.json()
                    df = pd.DataFrame(data, columns=['timestamp','open','high','low','close','volume','ct','qv','trades','tb','tq','ignore'])
                    df = df[['timestamp','open','high','low','close','volume']].copy()
                    for col in ['open','high','low','close','volume']:
                        df[col] = pd.to_numeric(df[col])
                    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                    return df
        except Exception as e:
            logger.error(f"Binance error {symbol}: {e}")
        return None

    def calculate_rsi(self, prices, period=14):
        delta = prices.diff()
        gain = delta.where(delta > 0, 0).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
        rs = gain / loss
        return round(float((100 - (100 / (1 + rs))).iloc[-1]), 2)

    def calculate_macd(self, prices):
        ema12 = prices.ewm(span=12, adjust=False).mean()
        ema26 = prices.ewm(span=26, adjust=False).mean()
        macd = ema12 - ema26
        signal = macd.ewm(span=9, adjust=False).mean()
        return {'macd': round(float(macd.iloc[-1]),4), 'signal': round(float(signal.iloc[-1]),4), 'histogram': round(float((macd-signal).iloc[-1]),4)}

    def calculate_ema(self, prices, period):
        return round(float(prices.ewm(span=period, adjust=False).mean().iloc[-1]), 4)

    def calculate_bollinger(self, prices, period=20):
        sma = prices.rolling(period).mean()
        std = prices.rolling(period).std()
        upper = sma + 2*std
        lower = sma - 2*std
        pos = (prices.iloc[-1] - float(lower.iloc[-1])) / (float(upper.iloc[-1]) - float(lower.iloc[-1]))
        return {'upper': round(float(upper.iloc[-1]),4), 'lower': round(float(lower.iloc[-1]),4), 'position': round(float(pos),2)}

    async def get_signal(self, symbol):
        try:
            df = await self.get_ohlcv(symbol)
            if df is None or len(df) < 30:
                return {'symbol': symbol, 'direction': 'NEUTRE', 'strength': 0}
            prices = df['close']
            current_price = float(prices.iloc[-1])
            rsi = self.calculate_rsi(prices)
            macd_data = self.calculate_macd(prices)
            ema20 = self.calculate_ema(prices, 20)
            ema50 = self.calculate_ema(prices, 50)
            bb = self.calculate_bollinger(prices)
            score = 0
            if rsi < 30: score += 2
            elif rsi < 40: score += 1
            elif rsi > 70: score -= 2
            elif rsi > 60: score -= 1
            if macd_data['histogram'] > 0: score += 1
            else: score -= 1
            if ema20 > ema50 and current_price > ema20: score += 1
            elif ema20 < ema50 and current_price < ema20: score -= 1
            if bb['position'] < 0.1: score += 1
            elif bb['position'] > 0.9: score -= 1
            direction = 'BUY' if score >= 3 else 'SELL' if score <= -3 else 'NEUTRE'
            strength = min(5, abs(score))
            if direction == 'BUY':
                sl = round(current_price * 0.99, 4)
                tp1 = round(current_price * 1.05, 4)
                tp2 = round(current_price * 1.10, 4)
            elif direction == 'SELL':
                sl = round(current_price * 1.01, 4)
                tp1 = round(current_price * 0.95, 4)
                tp2 = round(current_price * 0.90, 4)
            else:
                sl = tp1 = tp2 = current_price
            return {
                'symbol': symbol, 'direction': direction,
                'price': round(current_price, 4),
                'sl': sl, 'tp1': tp1, 'tp2': tp2,
                'strength': strength, 'rsi': rsi,
                'timeframe': '1H',
                'timestamp': datetime.now().strftime('%H:%M %d/%m/%Y'),
            }
        except Exception as e:
            logger.error(f"Signal error {symbol}: {e}")
            return {'symbol': symbol, 'direction': 'NEUTRE', 'strength': 0, 'timestamp': datetime.now().strftime('%H:%M %d/%m/%Y')}

    async def get_detailed_analysis(self, symbol):
        try:
            df = await self.get_ohlcv(symbol)
            if df is None or len(df) < 30:
                return {}
            prices = df['close']
            rsi = self.calculate_rsi(prices)
            macd_data = self.calculate_macd(prices)
            ema20 = self.calculate_ema(prices, 20)
            ema50 = self.calculate_ema(prices, 50)
            bb = self.calculate_bollinger(prices)
            vol_avg = df['volume'].rolling(20).mean().iloc[-1]
            vol_cur = df['volume'].iloc[-1]
            vol_trend = "📈 ÉLEVÉ" if vol_cur > vol_avg * 1.5 else "→ Normal"
            return {
                'rsi': f"{rsi} ({'Survendu 🟢' if rsi < 30 else 'Suracheté 🔴' if rsi > 70 else 'Neutre'})",
                'macd': f"{macd_data['macd']} ({'Haussier ↑' if macd_data['histogram'] > 0 else 'Baissier ↓'})",
                'ema20': ema20, 'ema50': ema50,
                'bb_position': "Bande haute" if bb['position'] > 0.8 else "Bande basse" if bb['position'] < 0.2 else "Zone centrale",
                'volume_trend': vol_trend,
                'trend': "📈 HAUSSIÈRE" if ema20 > ema50 else "📉 BAISSIÈRE",
            }
        except Exception as e:
            logger.error(f"Detail error {symbol}: {e}")
            return {}
