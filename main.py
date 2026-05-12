import time
from datetime import datetime, timedelta

import ccxt

from notifier import send_telegram_message
from scanner import scan_markets

# =========================================================
# CONFIGURATION
# =========================================================

RUN_DURATION_HOURS = 5
RUN_DURATION_MINUTES = 50

# IMPORTANT:
# 15m strategy does NOT need 1-minute scans
DELAY_BETWEEN_SCANS_MINUTES = 5

# =========================================================
# FETCH BTC PRICE
# =========================================================

def get_btc_price() -> float:

    try:

        exchange = ccxt.mexc()

        ticker = exchange.fetch_ticker('BTC/USDT')

        return ticker['last']

    except Exception as e:

        print(f"Error fetching BTC price: {e}")

        return 0.0

# =========================================================
# MAIN BOT
# =========================================================

def main():

    start_time = datetime.now()

    end_time = start_time + timedelta(
        hours=RUN_DURATION_HOURS,
        minutes=RUN_DURATION_MINUTES
    )

    # =====================================================
    # STARTUP
    # =====================================================

    print(f"\nStarting Bot at {start_time}")

    btc_price = get_btc_price()

    startup_msg = (
        f"🤖 <b>Trading Bot Started</b> 🤖\n\n"
        f"<b>BTC Price:</b> {btc_price:.2f} USDT\n"
        f"<b>Status:</b> Market scanning active\n"
        f"<b>Scan Delay:</b> {DELAY_BETWEEN_SCANS_MINUTES} minutes\n"
        f"<b>Duration:</b> "
        f"{RUN_DURATION_HOURS}h "
        f"{RUN_DURATION_MINUTES}m\n\n"
        f"✅ Improved Smart Money Strategy Enabled"
    )

    send_telegram_message(startup_msg)

    # =====================================================
    # COOLDOWN TRACKER
    # =====================================================

    cooldown_tracker = {}

    # =====================================================
    # MAIN LOOP
    # =====================================================

    scan_count = 1

    while datetime.now() < end_time:

        try:

            print(
                f"\n========================================"
            )

            print(
                f"Starting Scan Loop "
                f"{scan_count}"
            )

            print(
                f"Time: "
                f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )

            print(
                f"========================================"
            )

            # =============================================
            # RUN MARKET SCANNER
            # =============================================

            scan_markets(cooldown_tracker)

        except Exception as e:

            error_msg = (
                f"❌ <b>Bot Error</b>\n\n"
                f"<b>Error:</b>\n"
                f"{str(e)}"
            )

            print(error_msg)

            try:
                send_telegram_message(error_msg)
            except:
                pass

        # =================================================
        # CHECK END TIME
        # =================================================

        if datetime.now() >= end_time:
            break

        # =================================================
        # DELAY
        # =================================================

        print(
            f"\nNext scan in "
            f"{DELAY_BETWEEN_SCANS_MINUTES} minute(s)..."
        )

        time.sleep(
            DELAY_BETWEEN_SCANS_MINUTES * 60
        )

        scan_count += 1

    # =====================================================
    # SHUTDOWN
    # =====================================================

    shutdown_msg = (
        f"🛑 <b>Trading Bot Stopped</b>\n\n"
        f"<b>Status:</b> Scheduled runtime completed\n"
        f"<b>Finished At:</b>\n"
        f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )

    print("\nBot finished scheduled runtime.")

    try:
        send_telegram_message(shutdown_msg)
    except:
        pass

# =========================================================
# ENTRY POINT
# =========================================================

if __name__ == "__main__":

    main()
