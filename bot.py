import os
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler

TOKEN = os.environ.get("TELEGRAM_TOKEN")

# Base de datos en memoria
alerts = {}  # {chat_id: {symbol: threshold%}}
last_prices = {}  # {symbol: price}

COINGECKO_IDS = {
    "BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana",
    "BNB": "binancecoin", "XRP": "ripple", "ADA": "cardano",
    "DOGE": "dogecoin", "AVAX": "avalanche-2", "DOT": "polkadot",
    "MATIC": "matic-network"
}

def get_price(symbol):
    symbol = symbol.upper()
    coin_id = COINGECKO_IDS.get(symbol)
    if not coin_id:
        return None, "Crypto no reconocida. Probá con BTC, ETH, SOL, BNB, XRP, etc."
    try:
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd&include_24hr_change=true"
        r = requests.get(url, timeout=10)
        data = r.json()
        price = data[coin_id]["usd"]
        change = data[coin_id]["usd_24h_change"]
        return price, change
    except:
        return None, "Error al obtener precio."

async def cmd_precio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Uso: /precio BTC")
        return
    symbol = context.args[0].upper()
    price, change = get_price(symbol)
    if price is None:
        await update.message.reply_text(f"❌ {change}")
        return
    emoji = "🟢" if change >= 0 else "🔴"
    await update.message.reply_text(
        f"{emoji} *{symbol}*\n"
        f"💵 Precio: ${price:,.2f}\n"
        f"📊 Cambio 24h: {change:+.2f}%",
        parse_mode="Markdown"
    )

async def cmd_alerta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("Uso: /alerta BTC 5\n(te avisa si cambia ±5%)")
        return
    symbol = context.args[0].upper()
    try:
        threshold = float(context.args[1])
    except:
        await update.message.reply_text("El porcentaje debe ser un número. Ej: /alerta BTC 5")
        return
    if symbol not in COINGECKO_IDS:
        await update.message.reply_text("Crypto no reconocida.")
        return
    chat_id = update.effective_chat.id
    if chat_id not in alerts:
        alerts[chat_id] = {}
    price, _ = get_price(symbol)
    alerts[chat_id][symbol] = {"threshold": threshold, "base_price": price}
    last_prices[symbol] = price
    await update.message.reply_text(
        f"✅ Alerta creada para *{symbol}*\n"
        f"Te aviso si cambia ±{threshold}% desde ${price:,.2f}",
        parse_mode="Markdown"
    )

async def cmd_alertas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in alerts or not alerts[chat_id]:
        await update.message.reply_text("No tenés alertas activas.\nUsá /alerta BTC 5 para crear una.")
        return
    msg = "🔔 *Tus alertas activas:*\n\n"
    for symbol, data in alerts[chat_id].items():
        msg += f"• {symbol}: ±{data['threshold']}% desde ${data['base_price']:,.2f}\n"
    await update.message.reply_text(msg, parse_mode="Markdown")

async def cmd_borrar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Uso: /borraralerta BTC")
        return
    symbol = context.args[0].upper()
    chat_id = update.effective_chat.id
    if chat_id in alerts and symbol in alerts[chat_id]:
        del alerts[chat_id][symbol]
        await update.message.reply_text(f"🗑️ Alerta de {symbol} eliminada.")
    else:
        await update.message.reply_text(f"No tenías alerta para {symbol}.")

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 *Bienvenido al Bot de Cryptos!*\n\n"
        "📌 Comandos disponibles:\n"
        "/precio BTC — Ver precio actual\n"
        "/alerta BTC 5 — Alerta si cambia ±5%\n"
        "/alertas — Ver tus alertas\n"
        "/borraralerta BTC — Eliminar alerta\n\n"
        "Cryptos soportadas: BTC, ETH, SOL, BNB, XRP, ADA, DOGE, AVAX, DOT, MATIC",
        parse_mode="Markdown"
    )

async def check_alerts(app):
    for chat_id, user_alerts in list(alerts.items()):
        for symbol, data in list(user_alerts.items()):
            price, _ = get_price(symbol)
            if price is None:
                continue
            base = data["base_price"]
            threshold = data["threshold"]
            change = ((price - base) / base) * 100
            if abs(change) >= threshold:
                emoji = "🚀" if change > 0 else "🔴"
                await app.bot.send_message(
                    chat_id=chat_id,
                    text=f"{emoji} *ALERTA {symbol}*\n"
                         f"Cambió {change:+.2f}% desde tu alerta\n"
                         f"💵 Precio actual: ${price:,.2f}",
                    parse_mode="Markdown"
                )
                alerts[chat_id][symbol]["base_price"] = price

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("precio", cmd_precio))
    app.add_handler(CommandHandler("alerta", cmd_alerta))
    app.add_handler(CommandHandler("alertas", cmd_alertas))
    app.add_handler(CommandHandler("borraralerta", cmd_borrar))

    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_alerts, "interval", minutes=5, args=[app])
    scheduler.start()

    print("Bot corriendo...")
    app.run_polling()

if __name__ == "__main__":
    main()
