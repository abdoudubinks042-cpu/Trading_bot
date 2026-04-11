import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext
from config import Config
from analyzer import MarketAnalyzer
from news_fetcher import NewsFetcher

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

analyzer = MarketAnalyzer()
news_fetcher = NewsFetcher()
subscribers = set()
user_watchlists = {}

def format_signal(signal):
    if not signal:
        return "Signal indisponible"
    d = signal.get('direction', 'NEUTRE')
    emoji = "BUY" if d == "BUY" else "SELL" if d == "SELL" else "NEUTRE"
    bar = "X" * signal.get('strength', 0) + "." * (5 - signal.get('strength', 0))
    return (
        f"{emoji} {signal['symbol']}\n"
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
        msg += f"{s} - {item.get('title','')}\n{item.get('url','')}\n{item.get('time','')}\n\n"
    return msg

def start(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    subscribers.add(chat_id)
    if chat_id not in user_watchlists:
        user_watchlists[chat_id] = Config.DEFAULT_SYMBOLS.copy()
    keyboard = [
        [InlineKeyboardButton("Signal Maintenant", callback_data="signal_now"),
         InlineKeyboardButton("Dernieres News", callback_data="news_now")],
        [InlineKeyboardButton("Analyse Complete", callback_data="full_analysis")],
    ]
    update.message.reply_text(
        "TradingSignal Pro\n\nStop Loss: 1%\nTake Profit: 5% et 10%\n\nChoisis une action:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

def signal_command(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    subscribers.add(chat_id)
    symbols = user_watchlists.get(chat_id, Config.DEFAULT_SYMBOLS)
    import asyncio
    loop = asyncio.new_event_loop()
    for symbol in symbols[:3]:
        signal = loop.run_until_complete(analyzer.get_signal(symbol))
        update.message.reply_text(format_signal(signal))
    loop.close()

def news_command(update: Update, context: CallbackContext):
    import asyncio
    loop = asyncio.new_event_loop()
    news = loop.run_until_complete(news_fetcher.get_latest_news())
    loop.close()
    update.message.reply_text(format_news(news), disable_web_page_preview=True)

def button_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    chat_id = query.message.chat_id
    data = query.data
    import asyncio
    loop = asyncio.new_event_loop()
    if data == "signal_now":
        symbols = user_watchlists.get(chat_id, Config.DEFAULT_SYMBOLS)
        for symbol in symbols[:3]:
            signal = loop.run_until_complete(analyzer.get_signal(symbol))
            query.message.reply_text(format_signal(signal))
    elif data == "news_now":
        news = loop.run_until_complete(news_fetcher.get_latest_news())
        query.message.reply_text(format_news(news), disable_web_page_preview=True)
    elif data == "full_analysis":
        symbols = user_watchlists.get(chat_id, Config.DEFAULT_SYMBOLS[:2])
        for sym in symbols[:2]:
            signal = loop.run_until_complete(analyzer.get_signal(sym))
            query.message.reply_text(format_signal(signal))
    loop.close()

def main():
    updater = Updater(Config.TELEGRAM_TOKEN)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("signal", signal_command))
    dp.add_handler(CommandHandler("news", news_command))
    dp.add_handler(CallbackQueryHandler(button_callback))
    logger.info("Bot demarre!")
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
