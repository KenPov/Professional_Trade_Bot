import pandas as pd
import numpy as np
import ta

def analyze_data(df: pd.DataFrame, df_htf: pd.DataFrame = None, sentiment: str = None) -> dict:
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

    # --- NEWS SENTIMENT FILTER ---
    # Fetch sentiment if not provided (fallback)
    if sentiment is None:
        from news import get_market_sentiment
        # Check global sentiment for general trend alignment
        sentiment = get_market_sentiment()

    # --- ELITE SNIPER (Final Pro Version) ---
    is_uptrend = last_closed['close'] > last_closed['ema_200']
    strong_trend = last_closed['adx'] > 30 # Strong Trend only
    bullish_fvg_recent = df['fvg_bullish'].iloc[-5:-1].any() 
    # Institutional Volume Only (2.5x MA)
    vol_surge_threshold = df['vol_ma'].iloc[-1] * 2.5
    institutional_vol = last_closed['volume'] > vol_surge_threshold
    
    rsi_momentum_up = last_closed['rsi'] > prev_closed['rsi']
    rsi_safe_long = last_closed['rsi'] < 60 # Not at the absolute top
    
    if (is_uptrend and htf_trend == "BULLISH" and strong_trend and 
        bullish_fvg_recent and institutional_vol and rsi_momentum_up and rsi_safe_long):
        
        if sentiment == "BEARISH":
            print("LONG signal blocked by BEARISH news sentiment.")
        else:
            signal = "LONG"
            analysis = (
                f"• Institutional Sniper: 1H + 15m Trend Alignment\n"
                f"• Sentiment: {sentiment}\n"
                f"• Strength: ADX Very Strong ({last_closed['adx']:.1f})\n"
                f"• Volume: Institutional Surge (2.5x)\n"
                f"• Target: 1.2 RR High Probability"
            )

    is_downtrend = last_closed['close'] < last_closed['ema_200']
    bearish_fvg_recent = df['fvg_bearish'].iloc[-5:-1].any()
    rsi_momentum_down = last_closed['rsi'] < prev_closed['rsi']
    rsi_safe_short = last_closed['rsi'] > 40 # Not at the absolute bottom

    if (is_downtrend and htf_trend == "BEARISH" and strong_trend and 
        bearish_fvg_recent and institutional_vol and rsi_momentum_down and rsi_safe_short):
        
        if sentiment == "BULLISH":
            print("SHORT signal blocked by BULLISH news sentiment.")
        else:
            signal = "SHORT"
            analysis = (
                f"• Institutional Sniper: 1H + 15m Trend Alignment\n"
                f"• Sentiment: {sentiment}\n"
                f"• Strength: ADX Very Strong ({last_closed['adx']:.1f})\n"
                f"• Volume: Institutional Surge (2.5x)\n"
                f"• Target: 1.2 RR High Probability"
            )

    limit_price = None
    sl = None
    tp = None
    
    if signal:
        # Professional Entry: 50% Equilibrium
        limit_price = (last_closed['high'] + last_closed['low']) / 2.0
        
        if signal == "LONG":
            sl = limit_price * 0.99
            tp = limit_price * 1.012
        elif signal == "SHORT":
            sl = limit_price * 1.01
            tp = limit_price * 0.988

    return {
        "signal": signal,
        "analysis": analysis,
        "price": limit_price,
        "sl": sl,
        "tp": tp
    }
