import asyncio
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from config import Config
from analyzer import MarketAnalyzer
from news_fetcher import NewsFetcher

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

analyzer = MarketAnalyzer()
news_fetcher = NewsFetcher()
scheduler = AsyncIOScheduler()
subscribers = set()
user_watchlists = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    subscribers.add(chat_id)
    if chat_id not in user_watchlists:
        user_watchlists[chat_id] = Config.DEFAULT_SYMBOLS.copy()
    keyboard = [
        [InlineKeyboardButton("📈 Signal Maintenant", callback_data="signal_now"),
         InlineKeyboardButton("📰 Dernières News", callback_data="news_now")],
        [InlineKeyboardButton("📊 Analyse Complète", callback_data="full_analysis")],
    ]
    await update.message.reply_text(
        "🤖 *TradingSignal Pro* — Bienvenue !\n\n"
        "🛑 Stop Loss : `1%`\n🎯 Take Profit : `5%` → `10%`\n\n"
        "Choisis une action :",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

def format_signal(signal):
    if not signal:
        return "❌ Signal indisponible"
    d = signal.get('direction','NEUTRE')
    emoji = "🟢" if d == "BUY" else "🔴" if d == "SELL" else "⚪"
    bar = "▓" * signal.get('strength',0) + "░" * (5 - signal.get('strength',0))
    return (
        f"{emoji} *{signal['symbol']}* — *{d}*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 Prix : `{signal.get('price','N/A')}`\n"
        f"🛑 Stop Loss : `{signal.get('sl','N/A')}` *(−1%)*\n"
        f"🎯 TP1 : `{signal.get('tp1','N/A')}` *(+5%)*\n"
        f"🎯 TP2 : `{signal.get('tp2','N/A')}` *(+10%)*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 Force : [{bar}] {signal.get('strength',0)}/5\n"
        f"🕐 `{signal.get('timestamp','')}`"
    )

def format_news(news):
    if not news:
        return "❌ Aucune news disponible"
    msg = "📰 *Dernières News*\n━━━━━━━━━━━━━━━━━━━━\n\n"
    for item in news[:5]:
        s = "🟢" if item.get('sentiment') == 'positive' else "🔴" if item.get('sentiment') == 'negative' else "⚪"
        msg += f"{s} *{item.get('title','')}*\n🔗 {item.get('url','')}\n⏱ {item.get('time','')}\n\n"
    return msg

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    data = query.data
    if data == "signal_now":
        symbols = user_watchlists.get(chat_id, Config.DEFAULT_SYMBOLS)
        for symbol in symbols[:3]:
            signal = await analyzer.get_signal(symbol)
            await query.message.reply_text(format_signal(signal), parse_mode='Markdown')
            await asyncio.sleep(0.5)
    elif data == "news_now":
        news = await news_fetcher.get_latest_news()
        await query.message.reply_text(format_news(news), parse_mode='Markdown', disable_web_page_preview=True)
    elif data == "full_analysis":
        symbols = user_watchlists.get(chat_id, Config.DEFAULT_SYMBOLS[:2])
        for sym in symbols[:2]:
            signal = await analyzer.get_signal(sym)
            await query.message.reply_text(format_signal(signal), parse_mode='Markdown')

async def signal_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    subscribers.add(chat_id)
    symbols = user_watchlists.get(chat_id, Config.DEFAULT_SYMBOLS)
    for symbol in symbols[:3]:
        signal = await analyzer.get_signal(symbol)
        await update.message.reply_text(format_signal(signal), parse_mode='Markdown')
        await asyncio.sleep(0.5)

async def news_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    news = await news_fetcher.get_latest_news()
    await update.message.reply_text(format_news(news), parse_mode='Markdown', disable_web_page_preview=True)

def main():
    app = Application.builder().token(Config.TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("signal", signal_command))
    app.add_handler(CommandHandler("news", news_command))
    app.add_handler(CallbackQueryHandler(button_callback))
    logger.info("🤖 Bot démarré !")
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
