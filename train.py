import ccxt
import pandas as pd
import numpy as np
import ta
import itertools
from concurrent.futures import ThreadPoolExecutor, as_completed

exchange = ccxt.mexc({'enableRateLimit': True})

def fetch_historical_data(symbol, timeframe='15m', limit=1000):
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        return df
    except:
        return pd.DataFrame()

def evaluate_strategy(df, params):
    ema_window = params['ema_window']
    adx_threshold = params['adx_threshold']
    vol_multiplier = params['vol_multiplier']
    retrace_pct = params['retrace_pct'] # e.g., 0.5 for 50% retracement
    
    df = df.copy()
    df['ema'] = ta.trend.ema_indicator(df['close'], window=ema_window)
    adx_ind = ta.trend.ADXIndicator(df['high'], df['low'], df['close'], window=14)
    df['adx'] = adx_ind.adx()
    df['rsi'] = ta.momentum.rsi(df['close'], window=14)
    
    # FVG
    df['fvg_bull'] = (df['low'] > df['high'].shift(2)) & (df['close'] > df['open'])
    df['fvg_bear'] = (df['high'] < df['low'].shift(2)) & (df['close'] < df['open'])
    
    # Volume Surge
    df['vol_ma'] = df['volume'].rolling(window=20).mean()
    df['vol_surge'] = df['volume'] > (df['vol_ma'] * vol_multiplier)
    
    results = []
    
    # Evaluate signals
    for i in range(250, len(df) - 25):
        last_closed = df.iloc[i-1]
        prev_closed = df.iloc[i-2]
        current_price = df.iloc[i]['open'] # Simplified "current" price at start of signal candle
        
        signal = None
        if (last_closed['close'] > last_closed['ema'] and 
            last_closed['adx'] > adx_threshold and 
            df['fvg_bull'].iloc[i-6:i].any() and 
            df['vol_surge'].iloc[i-4:i].any() and 
            last_closed['rsi'] > prev_closed['rsi']):
            signal = 'LONG'
        elif (last_closed['close'] < last_closed['ema'] and 
              last_closed['adx'] > adx_threshold and 
              df['fvg_bear'].iloc[i-6:i].any() and 
              df['vol_surge'].iloc[i-4:i].any() and 
              last_closed['rsi'] < prev_closed['rsi']):
            signal = 'SHORT'
            
        if signal:
            # Entry Logic: Retracement of the impulse candle
            limit_price = last_closed['low'] + (last_closed['high'] - last_closed['low']) * (1 - retrace_pct)
            
            # Outcome check
            future = df.iloc[i:i+25]
            win = False
            loss = False
            filled = False
            
            if signal == 'LONG':
                sl = last_closed['low'] * 0.998
                risk = limit_price - sl
                tp = limit_price + (risk * 2.0)
                
                for _, row in future.iterrows():
                    if not filled:
                        if row['low'] <= limit_price:
                            filled = True
                            if row['low'] <= sl: 
                                loss = True
                                break
                    else:
                        if row['low'] <= sl:
                            loss = True
                            break
                        if row['high'] >= tp:
                            win = True
                            break
            else: # SHORT
                sl = last_closed['high'] * 1.002
                risk = sl - limit_price
                tp = limit_price - (risk * 2.0)
                
                for _, row in future.iterrows():
                    if not filled:
                        if row['high'] >= limit_price:
                            filled = True
                            if row['high'] >= sl:
                                loss = True
                                break
                    else:
                        if row['high'] >= sl:
                            loss = True
                            break
                        if row['low'] <= tp:
                            win = True
                            break
            
            if filled:
                results.append(1 if win else (0 if loss else -1)) # -1 for timeout
                
    return results

def train():
    print("Fetching top pairs...")
    markets = exchange.load_markets()
    usdt_pairs = [s for s, m in markets.items() if m['active'] and m['swap'] and m['quote'] == 'USDT'][:20]
    
    print(f"Downloading data for {len(usdt_pairs)} pairs...")
    data_map = {}
    for sym in usdt_pairs:
        df = fetch_historical_data(sym)
        if not df.empty:
            data_map[sym] = df
            
    param_grid = {
        'ema_window': [100, 200],
        'adx_threshold': [20, 25],
        'vol_multiplier': [1.5, 2.0],
        'retrace_pct': [0.5, 0.618]
    }
    
    keys = param_grid.keys()
    combinations = [dict(zip(keys, v)) for v in itertools.product(*param_grid.values())]
    
    best_params = None
    best_win_rate = 0
    
    print(f"Testing {len(combinations)} parameter combinations...")
    
    for params in combinations:
        all_results = []
        for sym, df in data_map.items():
            res = evaluate_strategy(df, params)
            all_results.extend(res)
            
        completed = [r for r in all_results if r != -1]
        if len(completed) > 10:
            win_rate = sum(completed) / len(completed)
            print(f"Params: {params} | Win Rate: {win_rate:.2f} | Total: {len(completed)}")
            if win_rate > best_win_rate:
                best_win_rate = win_rate
                best_params = params
                
    print("\n--- OPTIMIZATION COMPLETE ---")
    print(f"Best Win Rate: {best_win_rate:.2f}")
    print(f"Best Params: {best_params}")

if __name__ == "__main__":
    train()
