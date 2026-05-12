import ccxt
import pandas as pd
import warnings
import time
import ta
from scanner import PROFESSIONAL_WHITELIST

warnings.filterwarnings('ignore', category=pd.errors.SettingWithCopyWarning)
warnings.filterwarnings('ignore', category=FutureWarning)

exchange = ccxt.mexc({'enableRateLimit': True})

def fetch_all_ohlcv(symbol, timeframe, candle_count=5000):
    all_ohlcv = []
    limit = 1000
    since = None
    iterations = (candle_count // limit) + 1
    
    try:
        for _ in range(iterations):
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=limit)
            if not ohlcv:
                break
            all_ohlcv = ohlcv + all_ohlcv
            since = ohlcv[0][0] - (limit * 15 * 60 * 1000 if timeframe == '15m' else limit * 60 * 60 * 1000)
            time.sleep(0.05)
            
        df = pd.DataFrame(all_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df = df.drop_duplicates(subset=['timestamp']).sort_values('timestamp')
        return df
    except Exception as e:
        print(f"Error fetching {symbol}: {e}")
        return pd.DataFrame()

def backtest_symbol(symbol):
    print(f"Backtesting {symbol}...", flush=True)
    df_15m = fetch_all_ohlcv(symbol, '15m', candle_count=6000)
    df_1h = fetch_all_ohlcv(symbol, '1h', candle_count=2000)
    
    if len(df_15m) < 1000 or len(df_1h) < 200:
        return []

    # --- Pre-calculate Indicators for 15m ---
    df_15m['ema_200'] = ta.trend.ema_indicator(df_15m['close'], window=200)
    df_15m['adx'] = ta.trend.ADXIndicator(df_15m['high'], df_15m['low'], df_15m['close'], window=14).adx()
    df_15m['rsi'] = ta.momentum.rsi(df_15m['close'], window=14)
    df_15m['fvg_bullish'] = (df_15m['low'] > df_15m['high'].shift(2)) & (df_15m['close'] > df_15m['open'])
    df_15m['fvg_bearish'] = (df_15m['high'] < df_15m['low'].shift(2)) & (df_15m['close'] < df_15m['open'])
    df_15m['vol_ma'] = df_15m['volume'].rolling(window=20).mean()
    df_15m['volume_surge'] = df_15m['volume'] > (df_15m['vol_ma'] * 2.0)

    # --- Pre-calculate Indicators for 1h ---
    df_1h['ema_50_htf'] = ta.trend.ema_indicator(df_1h['close'], window=50)

    results = []
    
    # Fast Loop
    for i in range(500, len(df_15m) - 50):
        # 1. 15m Data
        row = df_15m.iloc[i]
        prev_row = df_15m.iloc[i-1]
        
        # 2. HTF Data (Matching timestamp)
        current_time = row['timestamp']
        htf_data = df_1h[df_1h['timestamp'] <= current_time]
        if htf_data.empty: continue
        last_htf = htf_data.iloc[-1]
        
        htf_trend = "NEUTRAL"
        if last_htf['close'] > last_htf['ema_50_htf']: htf_trend = "BULLISH"
        elif last_htf['close'] < last_htf['ema_50_htf']: htf_trend = "BEARISH"

        signal = None
        
        # Institutional Sniper Logic
        if (row['close'] > row['ema_200'] and htf_trend == "BULLISH" and row['adx'] > 30 and 
            df_15m['fvg_bullish'].iloc[i-5:i+1].any() and row['volume'] > (row['vol_ma'] * 2.5) and 
            row['rsi'] > prev_row['rsi'] and row['rsi'] < 60):
            signal = "LONG"
        elif (row['close'] < row['ema_200'] and htf_trend == "BEARISH" and row['adx'] > 30 and 
              df_15m['fvg_bearish'].iloc[i-5:i+1].any() and row['volume'] > (row['vol_ma'] * 2.5) and 
              row['rsi'] < prev_row['rsi'] and row['rsi'] > 40):
            signal = "SHORT"

        if signal:
            limit_price = (row['high'] + row['low']) / 2.0
            if signal == "LONG":
                sl = limit_price * 0.99
                tp = limit_price * 1.012
            else:
                sl = limit_price * 1.01
                tp = limit_price * 0.988

            # Simple Outcome check (next 50 candles)
            future = df_15m.iloc[i+1:i+51]
            filled = False
            for _, f_row in future.iterrows():
                if not filled:
                    if (signal == "LONG" and f_row['low'] <= limit_price) or (signal == "SHORT" and f_row['high'] >= limit_price):
                        filled = True
                        # Check if it hit SL in the same candle it filled
                        if signal == "LONG" and f_row['low'] <= sl:
                            results.append({'symbol': symbol, 'outcome': 'LOSS'})
                            break
                        if signal == "SHORT" and f_row['high'] >= sl:
                            results.append({'symbol': symbol, 'outcome': 'LOSS'})
                            break
                else:
                    if signal == "LONG":
                        if f_row['low'] <= sl: 
                            results.append({'symbol': symbol, 'outcome': 'LOSS'})
                            break
                        if f_row['high'] >= tp: 
                            results.append({'symbol': symbol, 'outcome': 'WIN'})
                            break
                    else:
                        if f_row['high'] >= sl: 
                            results.append({'symbol': symbol, 'outcome': 'LOSS'})
                            break
                        if f_row['low'] <= tp: 
                            results.append({'symbol': symbol, 'outcome': 'WIN'})
                            break
    return results

def main():
    print("--- STARTING OPTIMIZED BACKTEST (3 MONTHS) ---", flush=True)
    all_results = []
    for sym in PROFESSIONAL_WHITELIST:
        res = backtest_symbol(sym)
        all_results.extend(res)

    total = len(all_results)
    if total == 0:
        print("No signals found.")
        return

    wins = len([r for r in all_results if r['outcome'] == 'WIN'])
    losses = len([r for r in all_results if r['outcome'] == 'LOSS'])
    win_rate = (wins / (wins + losses)) * 100

    print(f"\n--- FINAL BACKTEST RESULTS ---", flush=True)
    print(f"Total Signals: {total}", flush=True)
    print(f"Wins: {wins} | Losses: {losses}", flush=True)
    print(f"Overall Win Rate: {win_rate:.2f}%", flush=True)

    df_res = pd.DataFrame(all_results)
    print("\n--- By Symbol ---", flush=True)
    for sym in PROFESSIONAL_WHITELIST:
        s_data = df_res[df_res['symbol'] == sym]
        if not s_data.empty:
            s_wr = (len(s_data[s_data['outcome'] == 'WIN']) / len(s_data)) * 100
            print(f"{sym}: {s_wr:.1f}% ({len(s_data)} signals)", flush=True)

if __name__ == "__main__":
    main()
