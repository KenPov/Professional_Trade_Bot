import ccxt
import pandas as pd
import warnings
from strategy import analyze_data
warnings.filterwarnings('ignore', category=pd.errors.SettingWithCopyWarning)
warnings.filterwarnings('ignore', category=FutureWarning)
from concurrent.futures import ThreadPoolExecutor, as_completed

exchange = ccxt.mexc({'enableRateLimit': True})

def backtest_symbol(symbol):
    try:
        # Fetch 15m data
        ohlcv_15m = exchange.fetch_ohlcv(symbol, '15m', limit=1000)
        df_15m = pd.DataFrame(ohlcv_15m, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        
        # Fetch 1h data for MTF
        ohlcv_1h = exchange.fetch_ohlcv(symbol, '1h', limit=500)
        df_1h = pd.DataFrame(ohlcv_1h, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        
        if len(df_15m) < 500 or len(df_1h) < 100:
            return []
            
        results = []
        
        # We loop through 15m data
        for i in range(250, len(df_15m) - 25):
            slice_15m = df_15m.iloc[:i+1]
            current_time = slice_15m.iloc[-1]['timestamp']
            
            # Get 1h data up to the current 15m candle's timestamp
            slice_1h = df_1h[df_1h['timestamp'] <= current_time]
            
            if len(slice_1h) < 50:
                continue
                
            # Call the real strategy function for high-fidelity backtest
            res = analyze_data(slice_15m, df_htf=slice_1h)
            
            if res.get("signal"):
                signal = res["signal"]
                limit_price = res["price"]
                sl = res["sl"]
                tp = res["tp"]
                
                # Check outcome in the next 25 candles
                future_df = df_15m.iloc[i:]
                outcome = "UNFILLED"
                is_filled = False
                
                for _, row in future_df.iterrows():
                    if not is_filled:
                        if signal == 'LONG' and row['low'] <= limit_price:
                            is_filled = True
                            if row['low'] <= sl: 
                                outcome = 'LOSS'
                                break
                        elif signal == 'SHORT' and row['high'] >= limit_price:
                            is_filled = True
                            if row['high'] >= sl:
                                outcome = 'LOSS'
                                break
                    else:
                        if signal == 'LONG':
                            if row['low'] <= sl:
                                outcome = 'LOSS'
                                break
                            if row['high'] >= tp:
                                outcome = 'WIN'
                                break
                        else: # SHORT
                            if row['high'] >= sl:
                                outcome = 'LOSS'
                                break
                            if row['low'] <= tp:
                                outcome = 'WIN'
                                break
                
                if is_filled and outcome == "UNFILLED":
                    outcome = "PENDING"
                    
                if is_filled:
                    results.append({
                        'symbol': symbol,
                        'signal': signal,
                        'outcome': outcome
                    })
        return results
    except Exception as e:
        print(f"Error backtesting {symbol}: {e}")
        return []

def main():
    print("Fetching markets...")
    markets = exchange.load_markets()
    usdt_pairs = [s for s, m in markets.items() if m['active'] and m['swap'] and m['quote'] == 'USDT'][:5]
    
    print(f"Running historical backtest on top {len(usdt_pairs)} pairs over the last 10 days...")
    all_results = []
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(backtest_symbol, sym): sym for sym in usdt_pairs}
        for future in as_completed(futures):
            res = future.result()
            if res:
                all_results.extend(res)

    # Analyze
    total = len(all_results)
    wins = len([r for r in all_results if r['outcome'] == 'WIN'])
    losses = len([r for r in all_results if r['outcome'] == 'LOSS'])
    pending = len([r for r in all_results if r['outcome'] == 'PENDING'])
    
    print(f"--- BACKTEST RESULTS ---")
    print(f"Total Signals: {total}")
    if total > 0:
        completed = wins + losses
        if completed > 0:
            win_rate = (wins / completed) * 100
            print(f"Wins: {wins}")
            print(f"Losses: {losses}")
            print(f"Pending/Timeout: {pending}")
            print(f"Win Rate (excluding pending): {win_rate:.2f}%")
        else:
            print("No completed trades.")

if __name__ == "__main__":
    main()
