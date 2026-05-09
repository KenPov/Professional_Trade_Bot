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
    Formats and sends a trading signal to Telegram.
    """
    icon = "🟢" if side.upper() == "LONG" else "🔴"
    
    # Calculate Risk/Reward ratio dynamically for display
    risk = abs(price - sl)
    reward = abs(tp - price)
    rr_ratio = reward / risk if risk > 0 else 0
    
    msg = (
        f"{icon} <b>{side.upper()} SIGNAL: {symbol}</b> {icon}\n\n"
        f"<b>Limit Entry Price:</b> {price:.5f}\n"
        f"<b>Take Profit (Target):</b> {tp:.5f}\n"
        f"<b>Stop Loss (Structure):</b> {sl:.5f}\n"
        f"<b>Risk/Reward:</b> 1:{rr_ratio:.1f}\n"
        f"<b>Strategy:</b> SMC + Pro Indicators\n"
        f"<b>Analysis:</b>\n{analysis}\n\n"
        f"<i>Automated Alert via Professional Trade Bot</i>"
    )
    send_telegram_message(msg)
