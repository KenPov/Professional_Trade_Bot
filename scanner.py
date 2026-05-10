import ccxt
import pandas as pd
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from strategy import analyze_data
from notifier import send_signal

# Initialize Exchange (MEXC to avoid Binance restrictions)
exchange = ccxt.mexc({'enableRateLimit': True})

def fetch_data(symbol: str, timeframe: str = '15m', limit: int = 210) -> pd.DataFrame:
    """
    Fetches historical OHLCV data for a specific symbol.
    """
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df
    except Exception as e:
        # Silently fail for individual pairs to avoid spamming logs during parallel execution
        return pd.DataFrame()

def process_symbol(symbol: str):
    """
    Fetches data and applies the strategy for a single symbol.
    Uses multi-timeframe analysis (15m and 1h).
    """
    df_15m = fetch_data(symbol, timeframe='15m', limit=250)
    df_1h = fetch_data(symbol, timeframe='1h', limit=100)
    
    if df_15m.empty or df_1h.empty:
        return None

    result = analyze_data(df_15m, df_htf=df_1h)
    
    if result.get("signal"):
        return {
            "symbol": symbol,
            "signal": result["signal"],
            "price": result["price"],
            "sl": result.get("sl"),
            "tp": result.get("tp"),
            "analysis": result["analysis"]
        }
    return None

def scan_markets(cooldown_tracker: dict):
    """
    Scans the top USDT perpetual futures markets in parallel.
    Uses a cooldown_tracker (dict) to prevent duplicate signals within a timeframe.
    """
    print("Fetching active USDT markets from MEXC...")
    try:
        markets = exchange.load_markets()
        # Filter for active USDT perpetual swap markets
        usdt_pairs = [
            symbol for symbol, market in markets.items() 
            if market['active'] and market['swap'] and market['quote'] == 'USDT'
        ]
    except Exception as e:
        print(f"Failed to fetch markets: {e}")
        return

    # Limit to top 150 pairs to save time and API limits
    symbols_to_scan = usdt_pairs[:150]
    print(f"Starting parallel scan for {len(symbols_to_scan)} pairs...")

    # Current time for cooldown tracking
    current_time = time.time()
    COOLDOWN_PERIOD = 7200 # 2 hours cooldown per signal per pair

    signals_found = 0

    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_symbol = {executor.submit(process_symbol, symbol): symbol for symbol in symbols_to_scan}
        
        for future in as_completed(future_to_symbol):
            symbol = future_to_symbol[future]
            try:
                data = future.result()
                if data:
                    # Check cooldown
                    last_signal_time = cooldown_tracker.get(symbol, 0)
                    if current_time - last_signal_time > COOLDOWN_PERIOD:
                        print(f"SIGNAL FOUND! {data['signal']} {symbol}")
                        send_signal(
                            symbol=data['symbol'],
                            side=data['signal'],
                            price=data['price'],
                            sl=data['sl'],
                            tp=data['tp'],
                            analysis=data['analysis']
                        )
                        cooldown_tracker[symbol] = current_time
                        signals_found += 1
            except Exception as e:
                print(f"Error processing {symbol}: {e}")

    print(f"Scan complete. Total signals found this cycle: {signals_found}")
