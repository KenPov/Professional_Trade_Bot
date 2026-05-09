import ccxt
import pandas as pd
from strategy import analyze_data
from concurrent.futures import ThreadPoolExecutor, as_completed

exchange = ccxt.mexc({'enableRateLimit': True})

def backtest_symbol(symbol):
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, '15m', limit=1000)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        if len(df) < 500:
            return []
            
        results = []
        # Pre-calculate indicators for speed
        import ta
        df['ema_200'] = ta.trend.ema_indicator(df['close'], window=200)
        adx_indicator = ta.trend.ADXIndicator(df['high'], df['low'], df['close'], window=14)
        df['adx'] = adx_indicator.adx()
        df['rsi'] = ta.momentum.rsi(df['close'], window=14)
        df['fvg_bullish'] = (df['low'] > df['high'].shift(2)) & (df['close'] > df['open'])
        df['fvg_bearish'] = (df['high'] < df['low'].shift(2)) & (df['close'] < df['open'])
        df['vol_ma'] = df['volume'].rolling(window=20).mean()
        df['volume_surge'] = df['volume'] > (df['vol_ma'] * 1.5)

        # Loop through historical data, starting after indicators are warm
        for i in range(250, len(df) - 20):  # Leave 20 candles at end to check outcome
            # Provide a slice of data up to the current simulated time
            slice_df = df.iloc[:i+1]
            
            # Since analyze_data recalculates everything, we'll just implement the core check here 
            # to be faster, rather than calling analyze_data on 750 slices per symbol.
            
            last_closed = slice_df.iloc[-2]
            prev_closed = slice_df.iloc[-3]
            
            is_uptrend = last_closed['close'] > last_closed['ema_200']
            is_downtrend = last_closed['close'] < last_closed['ema_200']
            strong_trend = last_closed['adx'] > 20
            
            bullish_fvg_recent = slice_df['fvg_bullish'].iloc[-6:-1].any()
            bearish_fvg_recent = slice_df['fvg_bearish'].iloc[-6:-1].any()
            recent_vol_surge = slice_df['volume_surge'].iloc[-4:-1].any()
            
            rsi_momentum_up = last_closed['rsi'] > prev_closed['rsi']
            rsi_momentum_down = last_closed['rsi'] < prev_closed['rsi']
            
            signal = None
            if is_uptrend and strong_trend and bullish_fvg_recent and recent_vol_surge and rsi_momentum_up:
                signal = 'LONG'
            elif is_downtrend and strong_trend and bearish_fvg_recent and recent_vol_surge and rsi_momentum_down:
                signal = 'SHORT'
                
            if signal:
                # Limit Entry Calculation (50% retracement)
                limit_price = (last_closed['high'] + last_closed['low']) / 2.0
                
                # Check outcome in the next 20 candles
                future_df = df.iloc[i:]
                outcome = "UNFILLED"
                
                # Assuming Dynamic Structure-based SL and TP
                if signal == 'LONG':
                    sl = last_closed['low'] * 0.999
                    risk = limit_price - sl
                    tp = limit_price + (risk * 2.0)
                    is_filled = False
                    
                    for _, row in future_df.iterrows():
                        if not is_filled:
                            # Check if limit order is filled
                            if row['low'] <= limit_price:
                                is_filled = True
                                # If it fills and hits SL in the same candle (extreme drop)
                                if row['low'] <= sl:
                                    outcome = 'LOSS'
                                    break
                        else:
                            # Order is active, check TP and SL
                            if row['low'] <= sl:
                                outcome = 'LOSS'
                                break
                            if row['high'] >= tp:
                                outcome = 'WIN'
                                break
                else: # SHORT
                    sl = last_closed['high'] * 1.001
                    risk = sl - limit_price
                    tp = limit_price - (risk * 2.0)
                    is_filled = False
                    
                    for _, row in future_df.iterrows():
                        if not is_filled:
                            # Check if limit order is filled
                            if row['high'] >= limit_price:
                                is_filled = True
                                if row['high'] >= sl:
                                    outcome = 'LOSS'
                                    break
                        else:
                            # Order is active
                            if row['high'] >= sl:
                                outcome = 'LOSS'
                                break
                            if row['low'] <= tp:
                                outcome = 'WIN'
                                break
                
                # If filled but neither TP nor SL hit within 20 candles
                if is_filled and outcome == "UNFILLED":
                    outcome = "PENDING"
                    
                results.append({
                    'symbol': symbol,
                    'signal': signal,
                    'outcome': outcome
                })
        return results
    except Exception as e:
        return []

def main():
    print("Fetching markets...")
    markets = exchange.load_markets()
    usdt_pairs = [s for s, m in markets.items() if m['active'] and m['swap'] and m['quote'] == 'USDT'][:50]
    
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
