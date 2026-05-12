import ccxt
import pandas as pd
import numpy as np
import ta
import itertools
import time
from scanner import PROFESSIONAL_WHITELIST

exchange = ccxt.mexc({'enableRateLimit': True})

def fetch_historical_data(symbol, timeframe='15m', limit=3000):
    all_ohlcv = []
    since = None
    iterations = (limit // 1000)
    try:
        for _ in range(iterations):
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=1000)
            if not ohlcv: break
            all_ohlcv = ohlcv + all_ohlcv
            since = ohlcv[0][0] - (1000 * 15 * 60 * 1000)
            time.sleep(0.1)
        df = pd.DataFrame(all_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        return df.drop_duplicates(subset=['timestamp']).sort_values('timestamp')
    except:
        return pd.DataFrame()

def evaluate(df, params):
    adx_t = params['adx']
    vol_m = params['vol']
    rr = params['rr']
    
    df = df.copy()
    df['ema_200'] = ta.trend.ema_indicator(df['close'], window=200)
    df['adx'] = ta.trend.ADXIndicator(df['high'], df['low'], df['close'], window=14).adx()
    df['rsi'] = ta.momentum.rsi(df['close'], window=14)
    df['vol_ma'] = df['volume'].rolling(window=20).mean()
    df['fvg_bull'] = (df['low'] > df['high'].shift(2)) & (df['close'] > df['open'])
    df['fvg_bear'] = (df['high'] < df['low'].shift(2)) & (df['close'] < df['open'])

    results = []
    for i in range(250, len(df) - 51):
        row = df.iloc[i]
        prev = df.iloc[i-1]
        
        signal = None
        if row['close'] > row['ema_200'] and row['adx'] > adx_t and df['fvg_bull'].iloc[i-5:i+1].any() and row['volume'] > (df['vol_ma'].iloc[i] * vol_m) and row['rsi'] > prev['rsi']:
            signal = "LONG"
        elif row['close'] < row['ema_200'] and row['adx'] > adx_t and df['fvg_bear'].iloc[i-5:i+1].any() and row['volume'] > (df['vol_ma'].iloc[i] * vol_m) and row['rsi'] < prev['rsi']:
            signal = "SHORT"
            
        if signal:
            entry = (row['high'] + row['low']) / 2.0
            future = df.iloc[i+1:i+51]
            win, loss, filled = False, False, False
            sl = row['low'] * 0.995 if signal == "LONG" else row['high'] * 1.005
            tp = entry + (entry - sl) * rr if signal == "LONG" else entry - (sl - entry) * rr
            
            for _, f in future.iterrows():
                if not filled:
                    if (signal == "LONG" and f['low'] <= entry) or (signal == "SHORT" and f['high'] >= entry):
                        filled = True
                        if (signal == "LONG" and f['low'] <= sl) or (signal == "SHORT" and f['high'] >= sl):
                            loss = True; break
                else:
                    if (signal == "LONG" and f['low'] <= sl) or (signal == "SHORT" and f['high'] >= sl):
                        loss = True; break
                    if (signal == "LONG" and f['high'] >= tp) or (signal == "SHORT" and f['low'] <= tp):
                        win = True; break
            if filled and (win or loss):
                results.append(1 if win else 0)
    return results

def train():
    print("Fetching data for optimization...")
    data = {sym: fetch_historical_data(sym) for sym in PROFESSIONAL_WHITELIST[:6]} # Use 6 pairs for faster training
    
    grid = {
        'adx': [25, 30, 35],
        'vol': [1.5, 2.0, 2.5],
        'rr': [1.5, 2.0]
    }
    
    best_wr = 0
    best_p = None
    
    keys, values = zip(*grid.items())
    for v in itertools.product(*values):
        p = dict(zip(keys, v))
        all_r = []
        for sym, df in data.items():
            if not df.empty: all_r.extend(evaluate(df, p))
        
        if len(all_r) > 20:
            wr = sum(all_r) / len(all_r)
            print(f"Params: {p} | WR: {wr:.2f} | Count: {len(all_r)}")
            if wr > best_wr:
                best_wr = wr
                best_p = p
                
    print(f"\nBEST WIN RATE: {best_wr:.2f}")
    print(f"BEST PARAMS: {best_p}")

if __name__ == "__main__":
    train()
