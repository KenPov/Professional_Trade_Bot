import time
from datetime import datetime, timedelta
import ccxt
from notifier import send_telegram_message
from scanner import scan_markets

# Configuration
RUN_DURATION_HOURS = 5
RUN_DURATION_MINUTES = 50
DELAY_BETWEEN_SCANS_MINUTES = 1

def get_btc_price() -> float:
    try:
        exchange = ccxt.mexc()
        ticker = exchange.fetch_ticker('BTC/USDT')
        return ticker['last']
    except Exception as e:
        print(f"Error fetching BTC price: {e}")
        return 0.0

def main():
    start_time = datetime.now()
    end_time = start_time + timedelta(hours=RUN_DURATION_HOURS, minutes=RUN_DURATION_MINUTES)
    
    # 1. Startup routine
    print(f"Starting Bot at {start_time}")
    btc_price = get_btc_price()
    
    startup_msg = (
        f"🤖 <b>Bot Scheduled Run Started</b> 🤖\n\n"
        f"<b>Current BTC Price:</b> {btc_price:.2f} USDT\n"
        f"<b>Status:</b> Scanning markets...\n"
        f"<b>Duration:</b> Will run for {RUN_DURATION_HOURS}h {RUN_DURATION_MINUTES}m"
    )
    send_telegram_message(startup_msg)

    # Cooldown tracker in memory: { "BTC/USDT": timestamp_of_last_signal }
    cooldown_tracker = {}

    # 2. Main Scanning Loop
    scan_count = 1
    while datetime.now() < end_time:
        print(f"\n--- Starting Scan Loop {scan_count} at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")
        
        # Run parallel scanner
        scan_markets(cooldown_tracker)
        
        # Check if we still have time left after scan before sleeping
        if datetime.now() >= end_time:
            break
            
        print(f"Scan complete. Delaying for {DELAY_BETWEEN_SCANS_MINUTES} minute(s)...")
        time.sleep(DELAY_BETWEEN_SCANS_MINUTES * 60)
        scan_count += 1

    # 3. Shutdown routine
    print(f"Time limit reached ({end_time}). Exiting gracefully for next schedule.")

if __name__ == "__main__":
    main()
