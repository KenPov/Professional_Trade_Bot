import requests
import os

# Telegram Configuration (Directly in code)
TELEGRAM_BOT_TOKEN = "8317215211:AAFR_pTgQptiT5N79Y9VzcftotceBbXLAhE"
TELEGRAM_CHAT_ID = "-1003708562178"

def send_telegram_message(message: str):
    """
    Sends a message to the configured Telegram chat.
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram credentials not configured. Skipping message.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code != 200:
            print(f"Failed to send message via Telegram. Response: {response.text}")
    except Exception as e:
        print(f"Exception sending message to Telegram: {e}")

def send_signal(symbol: str, side: str, price: float, sl: float, tp: float, analysis: str):
    """
    Formats and sends a high-win-rate signal in a clean professional format.
    """
    icon = "🚀" if side.upper() == "LONG" else "📉"
    side_icon = "🔵 BUY" if side.upper() == "LONG" else "🔴 SELL"
    
    msg = (
        f"{icon} <b>{symbol} - {side_icon}</b> {icon}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📍 <b>ENTRY:</b> <code>{price:.5f}</code>\n"
        f"🎯 <b>TP:</b> <code>{tp:.5f}</code>\n"
        f"🛡️ <b>SL:</b> <code>{sl:.5f}</code>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📊 <b>Market Analysis:</b>\n"
        f"{analysis}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"💰 <i>Professional Sniper Signal</i>"
    )
    send_telegram_message(msg)
