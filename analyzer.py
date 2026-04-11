import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from config import Config
from analyzer import MarketAnalyzer
from news_fetcher import NewsFetcher

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

analyzer = MarketAnalyzer()
news_fetcher = NewsFetcher()
subscribers = set()
user_watchlists = {}

def format_signal(signal):
    if not signal:
        return "Signal indisponible"
    d = signal.get('direction', 'NEUTRE')
    bar = "X" * signal.get('strength', 0) + "." * (5 - signal.get('strength', 0))
    return (
        f"{d} {signal['symbol']}\n"
        f"Prix: {signal.get('price','N/A')}\n"
        f"Stop Loss: {signal.get('sl','N/A')} (-1%)\n"
        f"TP1: {signal.get('tp1','N/A')} (+5%)\n"
        f"TP2: {signal.get('tp2','N/A')} (+10%)\n"
        f"Force: [{bar}] {signal.get('strength',0)}/5\n"
        f"Heure: {signal.get('timestamp','')}"
    )

def format_news(news):
    if not news:
        return "Aucune news disponible"
    msg = "Dernieres News\n\n"
    for item in news[:5]:
        s = "HAUSSE" if item.get('sentiment') == 'positive' else "BAISSE" if item.get('sentiment') == 'negative' else "NEUTRE"
        msg += f"{s} - {item.get('title','')}\n{item.get('time','')}\n\n"
    return msg

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    subscribers.add(chat_id)
    if chat_id not in user_watchlists:
        user_watchlists[chat_id] = Config.DEFAULT_SYMBOLS.copy()
    keyboard = [
        [InlineKeyboardButton("Signal Maintenant", callback_data="signal_now"),
         InlineKeyboardButton("Dernieres News", callback_data="news_now")],
        [InlineKeyboardButton("Analyse Complete", callback_data="full_analysis")],
    ]
    await update.message.reply_text(
        "TradingSignal Pro\n\nStop Loss: 1%\nTake Profit: 5% et 10%\n\nChoisis une action:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def signal_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    subscribers.add(chat_id)
    symbols = user_watchlists.get(chat_id, Config.DEFAULT_SYMBOLS)
    for symbol in symbols[:3]:
        signal = await analyzer.get_signal(symbol)
        await update.message.reply_text(format_signal(signal))

async def news_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    news = await news_fetcher.get_latest_news()
    await update.message.reply_text(format_news(news), disable_web_page_preview=True)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    data = query.data
    if data == "signal_now":
        symbols = user_watchlists.get(chat_id, Config.DEFAULT_SYMBOLS)
        for symbol in symbols[:3]:
            signal = await analyzer.get_signal(symbol)
            await query.message.reply_text(format_signal(signal))
    elif data == "news_now":
        news = await news_fetcher.get_latest_news()
        await query.message.reply_text(format_news(news), disable_web_page_preview=True)
    elif data == "full_analysis":
        symbols = user_watchlists.get(chat_id, Config.DEFAULT_SYMBOLS[:2])
        for sym in symbols[:2]:
            signal = await analyzer.get_signal(sym)
            await query.message.reply_text(format_signal(signal))

def main():
    app = Application.builder().token(Config.TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("signal", signal_command))
    app.add_handler(CommandHandler("news", news_command))
    app.add_handler(CallbackQueryHandler(button_callback))
    logger.info("Bot demarre!")
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
