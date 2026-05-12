import pandas as pd
import ta


def analyze_data(df: pd.DataFrame, df_htf: pd.DataFrame = None) -> dict:

    if len(df) < 200:
        return {"signal": None}

    # =========================================================
    # INDICATORS
    # =========================================================

    df['ema_50'] = ta.trend.ema_indicator(df['close'], window=50)
    df['ema_200'] = ta.trend.ema_indicator(df['close'], window=200)

    adx_indicator = ta.trend.ADXIndicator(
        df['high'],
        df['low'],
        df['close'],
        window=14
    )

    df['adx'] = adx_indicator.adx()

    df['rsi'] = ta.momentum.rsi(df['close'], window=14)

    df['atr'] = ta.volatility.average_true_range(
        df['high'],
        df['low'],
        df['close'],
        window=14
    )

    # =========================================================
    # FAIR VALUE GAPS (SMC)
    # =========================================================

    df['fvg_bullish'] = (
        (df['low'] > df['high'].shift(2)) &
        (df['close'] > df['open'])
    )

    df['fvg_bearish'] = (
        (df['high'] < df['low'].shift(2)) &
        (df['close'] < df['open'])
    )

    # =========================================================
    # VOLUME
    # =========================================================

    df['vol_ma'] = df['volume'].rolling(window=20).mean()

    df['volume_surge'] = (
        df['volume'] > (df['vol_ma'] * 1.5)
    )

    # =========================================================
    # HIGHER TIMEFRAME TREND
    # =========================================================

    htf_trend = "NEUTRAL"

    if df_htf is not None and len(df_htf) > 50:

        df_htf['ema_50'] = ta.trend.ema_indicator(
            df_htf['close'],
            window=50
        )

        last_htf = df_htf.iloc[-1]

        if last_htf['close'] > last_htf['ema_50']:
            htf_trend = "BULLISH"

        elif last_htf['close'] < last_htf['ema_50']:
            htf_trend = "BEARISH"

    # =========================================================
    # CANDLES
    # =========================================================

    last_closed = df.iloc[-2]
    prev_closed = df.iloc[-3]
    current_candle = df.iloc[-1]

    bullish_candle = (
        last_closed['close'] > last_closed['open']
    )

    bearish_candle = (
        last_closed['close'] < last_closed['open']
    )

    # =========================================================
    # TREND FILTERS
    # =========================================================

    is_uptrend = (
        last_closed['close'] >
        last_closed['ema_50'] >
        last_closed['ema_200']
    )

    is_downtrend = (
        last_closed['close'] <
        last_closed['ema_50'] <
        last_closed['ema_200']
    )

    # Better ADX range
    strong_trend = (
        18 < last_closed['adx'] < 35
    )

    # =========================================================
    # RSI FILTERS
    # =========================================================

    rsi_good_long = (
        50 < last_closed['rsi'] < 68
    )

    rsi_good_short = (
        32 < last_closed['rsi'] < 50
    )

    # =========================================================
    # MARKET STRUCTURE BREAK
    # =========================================================

    higher_high = (
        last_closed['high'] > prev_closed['high']
    )

    lower_low = (
        last_closed['low'] < prev_closed['low']
    )

    # =========================================================
    # FVG + VOLUME CONFIRMATION
    # =========================================================

    bullish_fvg_recent = (
        df['fvg_bullish'].iloc[-6:-1].any()
    )

    bearish_fvg_recent = (
        df['fvg_bearish'].iloc[-6:-1].any()
    )

    recent_vol_surge = (
        df['volume_surge'].iloc[-4:-1].any()
    )

    # =========================================================
    # LONG CONDITIONS
    # =========================================================

    long_condition = (
        is_uptrend and
        htf_trend == "BULLISH" and
        strong_trend and
        bullish_candle and
        bullish_fvg_recent and
        recent_vol_surge and
        rsi_good_long and
        higher_high
    )

    # =========================================================
    # SHORT CONDITIONS
    # =========================================================

    short_condition = (
        is_downtrend and
        htf_trend == "BEARISH" and
        strong_trend and
        bearish_candle and
        bearish_fvg_recent and
        recent_vol_surge and
        rsi_good_short and
        lower_low
    )

    signal = None
    analysis = ""

    if long_condition:
        signal = "LONG"

        analysis = (
            f"• Trend: Strong Bullish Alignment\n"
            f"• ADX: {last_closed['adx']:.1f}\n"
            f"• RSI: {last_closed['rsi']:.1f}\n"
            f"• Volume Surge Confirmed\n"
            f"• Market Structure Break Up"
        )

    elif short_condition:
        signal = "SHORT"

        analysis = (
            f"• Trend: Strong Bearish Alignment\n"
            f"• ADX: {last_closed['adx']:.1f}\n"
            f"• RSI: {last_closed['rsi']:.1f}\n"
            f"• Volume Surge Confirmed\n"
            f"• Market Structure Break Down"
        )

    # =========================================================
    # ENTRY / SL / TP
    # =========================================================

    limit_price = None
    sl = None
    tp = None

    if signal:

        current_market = current_candle['open']

        # Professional retracement entry
        limit_price = (
            last_closed['low'] +
            (last_closed['high'] - last_closed['low']) * 0.5
        )

        atr = last_closed['atr']

        # =====================================================
        # LONG
        # =====================================================

        if signal == "LONG":

            if limit_price >= current_market:
                limit_price = (
                    current_market * 0.998
                )

            sl = (
                limit_price - (atr * 1.5)
            )

            risk = (
                limit_price - sl
            )

            if risk <= 0:
                return {"signal": None}

            # Better TP ratio for higher win rate
            tp = (
                limit_price + (risk * 1.5)
            )

        # =====================================================
        # SHORT
        # =====================================================

        elif signal == "SHORT":

            if limit_price <= current_market:
                limit_price = (
                    current_market * 1.002
                )

            sl = (
                limit_price + (atr * 1.5)
            )

            risk = (
                sl - limit_price
            )

            if risk <= 0:
                return {"signal": None}

            tp = (
                limit_price - (risk * 1.5)
            )

    return {
        "signal": signal,
        "analysis": analysis,
        "price": limit_price,
        "sl": sl,
        "tp": tp
    }
