import pandas as pd
import numpy as np
import ta

def analyze_data(df: pd.DataFrame) -> dict:
    """
    Analyzes OHLCV data to generate a trading signal based on 
    Professional & Smart Money Concepts (SMC).
    
    Expected DataFrame columns: timestamp, open, high, low, close, volume
    """
    if len(df) < 200:
        return {"signal": None, "analysis": "Not enough data"}

    # --- Technical Indicators ---
    # 1. Trend: EMA 200
    df['ema_200'] = ta.trend.ema_indicator(df['close'], window=200)
    
    # 2. Trend Strength: ADX
    adx_indicator = ta.trend.ADXIndicator(df['high'], df['low'], df['close'], window=14)
    df['adx'] = adx_indicator.adx()
    
    # 3. Momentum: RSI
    df['rsi'] = ta.momentum.rsi(df['close'], window=14)

    # --- Smart Money Concepts (SMC) ---
    # 4. Fair Value Gaps (FVG)
    # Bullish FVG: Low of current candle is higher than High of candle 2 periods ago
    df['fvg_bullish'] = (df['low'] > df['high'].shift(2)) & (df['close'] > df['open'])
    # Bearish FVG: High of current candle is lower than Low of candle 2 periods ago
    df['fvg_bearish'] = (df['high'] < df['low'].shift(2)) & (df['close'] < df['open'])

    # 5. Volume Surge (Institutional footprint)
    # Volume is greater than 1.5x the 20-period moving average of volume
    df['vol_ma'] = df['volume'].rolling(window=20).mean()
    df['volume_surge'] = df['volume'] > (df['vol_ma'] * 1.5)

    # Get the latest completed candle (index -2) and the current forming candle (index -1)
    # We base our signal on the last fully closed candle to avoid repainting
    last_closed = df.iloc[-2]
    prev_closed = df.iloc[-3]

    signal = None
    analysis = ""

    # --- LONG LOGIC ---
    # 1. Price is above EMA 200 (Uptrend)
    # 2. ADX > 20 (Strong trend emerging)
    # 3. Bullish FVG formed recently (SMC)
    # 4. Volume Surge present recently
    # 5. RSI showing upward momentum
    
    is_uptrend = last_closed['close'] > last_closed['ema_200']
    strong_trend = last_closed['adx'] > 20
    bullish_fvg_recent = df['fvg_bullish'].iloc[-6:-1].any() # FVG in the last 5 closed candles
    recent_vol_surge = df['volume_surge'].iloc[-4:-1].any()  # Volume surge in last 3 candles
    rsi_momentum_up = last_closed['rsi'] > prev_closed['rsi']
    
    if is_uptrend and strong_trend and bullish_fvg_recent and recent_vol_surge and rsi_momentum_up:
        signal = "LONG"
        analysis = (
            f"• Trend: Above EMA200\n"
            f"• Strength: ADX at {last_closed['adx']:.1f}\n"
            f"• SMC: Bullish FVG detected\n"
            f"• Momentum: RSI Up ({last_closed['rsi']:.1f})\n"
            f"• Volume: Institutional surge detected"
        )

    # --- SHORT LOGIC ---
    is_downtrend = last_closed['close'] < last_closed['ema_200']
    bearish_fvg_recent = df['fvg_bearish'].iloc[-6:-1].any()
    rsi_momentum_down = last_closed['rsi'] < prev_closed['rsi']

    if is_downtrend and strong_trend and bearish_fvg_recent and recent_vol_surge and rsi_momentum_down:
        signal = "SHORT"
        analysis = (
            f"• Trend: Below EMA200\n"
            f"• Strength: ADX at {last_closed['adx']:.1f}\n"
            f"• SMC: Bearish FVG detected\n"
            f"• Momentum: RSI Down ({last_closed['rsi']:.1f})\n"
            f"• Volume: Institutional surge detected"
        )

    limit_price = None
    sl = None
    tp = None
    
    if signal == "LONG":
        # Professional Limit Entry: 50% retracement of the bullish impulse candle
        limit_price = (last_closed['high'] + last_closed['low']) / 2.0
        sl = last_closed['low'] * 0.999 # Just below the impulse candle
        risk = limit_price - sl
        tp = limit_price + (risk * 2.0) # 1:2 Risk/Reward
    elif signal == "SHORT":
        # Professional Limit Entry: 50% retracement of the bearish impulse candle
        limit_price = (last_closed['high'] + last_closed['low']) / 2.0
        sl = last_closed['high'] * 1.001 # Just above the impulse candle
        risk = sl - limit_price
        tp = limit_price - (risk * 2.0) # 1:2 Risk/Reward

    return {
        "signal": signal,
        "analysis": analysis,
        "price": limit_price if limit_price else last_closed['close'],
        "sl": sl,
        "tp": tp
    }
