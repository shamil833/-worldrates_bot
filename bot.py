import os
import requests
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)

TOKEN = os.getenv("BOT_TOKEN")
API = "https://api.frankfurter.dev/v1"

logging.basicConfig(level=logging.INFO)

users = {}
alerts = {}

TEXT = {
    "ru": {
        "welcome": "🌍 Добро пожаловать в WorldRates!\n\nВыберите действие:",
        "rates": "💵 Курсы валют",
        "convert": "🔄 Конвертер",
        "alerts": "🔔 Уведомления",
        "language": "🌐 Язык",
        "help": "ℹ️ Помощь",
        "choose": "Выберите валюту:",
        "error": "Не удалось получить курс. Попробуйте позже."
    },
    "en": {
        "welcome": "🌍 Welcome to WorldRates!\n\nChoose an action:",
        "rates": "💵 Exchange rates",
        "convert": "🔄 Converter",
        "alerts": "🔔 Alerts",
        "language": "🌐 Language",
        "help": "ℹ️ Help",
        "choose": "Choose currency:",
        "error": "Unable to get rates. Try again later."
    }
}

def get_rates(base="EUR"):
    response = requests.get(
        f"{API}/latest",
        params={"base": base},
        timeout=15
    )
    response.raise_for_status()
    return response.json()

def menu(lang):
    keyboard = [
        [InlineKeyboardButton(TEXT[lang]["rates"], callback_data="rates")],
        [InlineKeyboardButton(TEXT[lang]["convert"], callback_data="convert")],
        [InlineKeyboardButton(TEXT[lang]["alerts"], callback_data="alerts")],
        [InlineKeyboardButton(TEXT[lang]["language"], callback_data="language")],
        [InlineKeyboardButton(TEXT[lang]["help"], callback_data="help")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    users.setdefault(uid, {"lang": "ru"})
    lang = users[uid]["lang"]

    await update.message.reply_text(
        TEXT[lang]["welcome"],
        reply_markup=menu(lang)
    )

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    uid = query.from_user.id
    users.setdefault(uid, {"lang": "ru"})
    lang = users[uid]["lang"]

    if query.data == "language":
        keyboard = [
            [InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru")],
            [InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")]
        ]
        await query.edit_message_text(
            "Choose language / Выберите язык:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data.startswith("lang_"):
        users[uid]["lang"] = query.data[-2:]
        lang = users[uid]["lang"]
        await query.edit_message_text(
            TEXT[lang]["welcome"],
            reply_markup=menu(lang)
        )

    elif query.data == "rates":
        try:
            data = get_rates("EUR")
            result = "💵 EUR exchange rates\n\n"
            for currency in ["USD", "GBP", "RUB", "CNY", "JPY",
                             "CHF", "TRY", "AED", "CAD", "AUD"]:
                if currency in data["rates"]:
                    result += f"1 EUR = {data['rates'][currency]} {currency}\n"

            result += f"\n📅 Date: {data['date']}"
            await query.edit_message_text(result)
        except Exception:
            await query.edit_message_text(TEXT[lang]["error"])

    elif query.data == "convert":
        context.user_data["mode"] = "convert"
        await query.edit_message_text(
            "Send amount and currencies, e.g. 100 EUR USD"
        )

    elif query.data == "alerts":
        context.user_data["mode"] = "alert"
        await query.edit_message_text(
            "Send alert like EUR RUB 100\n"
            "The bot will notify you when EUR/RUB reaches 100."
        )

    elif query.data == "help":
        await query.edit_message_text(
            "WorldRates — exchange rates, conversion and alerts."
        )

async def messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    mode = context.user_data.get("mode")

    try:
        parts = update.message.text.upper().split()

        if mode == "convert":
            amount = float(parts[0])
            base, target = parts[1], parts[2]
            data = get_rates(base)
            value = amount * data["rates"][target]
            await update.message.reply_text(
                f"{amount:g} {base} = {value:.4f} {target}\n"
                f"Date: {data['date']}"
            )

        elif mode == "alert":
            base, target = parts[0], parts[1]
            threshold = float(parts[2])

            alerts.setdefault(uid, []).append(
                (base, target, threshold)
            )
            await update.message.reply_text(
                f"🔔 Alert created: {base}/{target} >= {threshold}"
            )

        else:
            await update.message.reply_text("Use /start")

    except Exception:
        await update.message.reply_text(
            "Invalid format. Please try again."
        )

async def check_alerts(context: ContextTypes.DEFAULT_TYPE):
    for uid, user_alerts in list(alerts.items()):
        for base, target, threshold in user_alerts:
            try:
                data = get_rates(base)
                rate = data["rates"][target]

                if rate >= threshold:
                    await context.bot.send_message(
                        uid,
                        f"🔔 ALERT!\n{base}/{target} = {rate}\n"
                        f"Your threshold: {threshold}"
                    )
                    alerts[uid].remove((base, target, threshold))
            except Exception as e:
                logging.error(e)

def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, messages
    ))

    app.job_queue.run_repeating(
        check_alerts,
        interval=900,
        first=10
    )

    app.run_polling()

if __name__ == "__main__":
    main()
