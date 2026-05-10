import pandas as pd
import numpy as np
import ta

def analyze_data(df: pd.DataFrame, df_htf: pd.DataFrame = None) -> dict:
    """
    Analyzes OHLCV data to generate high-probability signals.
    Optimized for Accuracy & Professional Limit Entries.
    """
    if len(df) < 200:
        return {"signal": None, "analysis": "Not enough data"}

    # --- Technical Indicators (Optimized) ---
    df['ema_200'] = ta.trend.ema_indicator(df['close'], window=200)
    adx_indicator = ta.trend.ADXIndicator(df['high'], df['low'], df['close'], window=14)
    df['adx'] = adx_indicator.adx()
    df['rsi'] = ta.momentum.rsi(df['close'], window=14)

    # --- SMC & Institutional Flow ---
    df['fvg_bullish'] = (df['low'] > df['high'].shift(2)) & (df['close'] > df['open'])
    df['fvg_bearish'] = (df['high'] < df['low'].shift(2)) & (df['close'] < df['open'])
    
    df['vol_ma'] = df['volume'].rolling(window=20).mean()
    df['volume_surge'] = df['volume'] > (df['vol_ma'] * 2.0) # Optimized multiplier

    # --- Higher Timeframe Trend (1H) ---
    htf_trend = "NEUTRAL"
    if df_htf is not None and len(df_htf) > 50:
        df_htf['ema_50'] = ta.trend.ema_indicator(df_htf['close'], window=50)
        last_htf = df_htf.iloc[-1]
        if last_htf['close'] > last_htf['ema_50']:
            htf_trend = "BULLISH"
        elif last_htf['close'] < last_htf['ema_50']:
            htf_trend = "BEARISH"

    last_closed = df.iloc[-2]
    prev_closed = df.iloc[-3]
    current_candle = df.iloc[-1] # Open of current candle is a proxy for current market price

    signal = None
    analysis = ""

    # --- REFINED LONG LOGIC ---
    # 1. 15m Trend: Above EMA 200
    # 2. HTF Trend: Bullish
    # 3. Strength: ADX > 25 (Optimized)
    # 4. Institutional: Recent FVG AND Volume Surge
    # 5. Momentum: RSI increasing
    
    is_uptrend = last_closed['close'] > last_closed['ema_200']
    strong_trend = last_closed['adx'] > 25
    bullish_fvg_recent = df['fvg_bullish'].iloc[-6:-1].any()
    recent_vol_surge = df['volume_surge'].iloc[-4:-1].any()
    rsi_momentum_up = last_closed['rsi'] > prev_closed['rsi']
    
    if (is_uptrend and htf_trend == "BULLISH" and strong_trend and 
        bullish_fvg_recent and recent_vol_surge and rsi_momentum_up):
        signal = "LONG"
        analysis = (
            f"• MTF Trend: 1H Bullish Alignment\n"
            f"• Strength: ADX strong at {last_closed['adx']:.1f}\n"
            f"• SMC: Bullish FVG + High Vol Surge\n"
            f"• Entry: Professional 50% Retracement"
        )

    # --- REFINED SHORT LOGIC ---
    is_downtrend = last_closed['close'] < last_closed['ema_200']
    bearish_fvg_recent = df['fvg_bearish'].iloc[-6:-1].any()
    rsi_momentum_down = last_closed['rsi'] < prev_closed['rsi']

    if (is_downtrend and htf_trend == "BEARISH" and strong_trend and 
        bearish_fvg_recent and recent_vol_surge and rsi_momentum_down):
        signal = "SHORT"
        analysis = (
            f"• MTF Trend: 1H Bearish Alignment\n"
            f"• Strength: ADX strong at {last_closed['adx']:.1f}\n"
            f"• SMC: Bearish FVG + High Vol Surge\n"
            f"• Entry: Professional 50% Retracement"
        )

    limit_price = None
    sl = None
    tp = None
    
    if signal:
        # Professional Limit Entry: 50% retracement of the impulse candle
        limit_price = (last_closed['high'] + last_closed['low']) / 2.0
        
        # --- CRITICAL FIX: Ensure limit is below market for LONG, above for SHORT ---
        # Current price (approx) is current_candle['open']
        current_market = current_candle['open']
        
        if signal == "LONG":
            # If current price is already below our limit, we use a deeper retracement (0.618)
            # to avoid immediate execution at a bad price.
            if limit_price >= current_market:
                limit_price = last_closed['low'] + (last_closed['high'] - last_closed['low']) * 0.382
            
            # Final check: if still above, discard or set slightly below
            if limit_price >= current_market:
                limit_price = current_market * 0.998 # 0.2% below market
                
            sl = last_closed['low'] * 0.998
            risk = limit_price - sl
            if risk <= 0: return {"signal": None} # Avoid invalid trades
            tp = limit_price + (risk * 2.0)
            
        elif signal == "SHORT":
            if limit_price <= current_market:
                limit_price = last_closed['low'] + (last_closed['high'] - last_closed['low']) * 0.618
            
            if limit_price <= current_market:
                limit_price = current_market * 1.002
                
            sl = last_closed['high'] * 1.002
            risk = sl - limit_price
            if risk <= 0: return {"signal": None}
            tp = limit_price - (risk * 2.0)

    return {
        "signal": signal,
        "analysis": analysis,
        "price": limit_price,
        "sl": sl,
        "tp": tp
    }
