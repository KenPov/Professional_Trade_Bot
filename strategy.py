import pandas as pd
import ta


def analyze_data(
    df: pd.DataFrame,
    df_htf: pd.DataFrame = None,
    symbol: str = ""
) -> dict:

    # =========================================================
    # MINIMUM DATA CHECK
    # =========================================================

    if len(df) < 200:
        return {"signal": None}

    # =========================================================
    # SYMBOL SETTINGS
    # =========================================================

    is_gold = (
        'XAU' in symbol.upper() or
        'GOLD' in symbol.upper()
    )

    # Gold uses wider stop and bigger RR
    if is_gold:
        atr_multiplier = 2.0
        rr_ratio = 2.0
        adx_min = 20
        adx_max = 40
    else:
        atr_multiplier = 1.5
        rr_ratio = 1.5
        adx_min = 18
        adx_max = 35

    # =========================================================
    # INDICATORS
    # =========================================================

    df['ema_50'] = ta.trend.ema_indicator(
        df['close'],
        window=50
    )

    df['ema_200'] = ta.trend.ema_indicator(
        df['close'],
        window=200
    )

    adx_indicator = ta.trend.ADXIndicator(
        df['high'],
        df['low'],
        df['close'],
        window=14
    )

    df['adx'] = adx_indicator.adx()

    df['rsi'] = ta.momentum.rsi(
        df['close'],
        window=14
    )

    df['atr'] = ta.volatility.average_true_range(
        df['high'],
        df['low'],
        df['close'],
        window=14
    )

    # =========================================================
    # FAIR VALUE GAPS
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
    # VOLUME ANALYSIS
    # =========================================================

    df['vol_ma'] = (
        df['volume']
        .rolling(window=20)
        .mean()
    )

    df['volume_surge'] = (
        df['volume'] >
        (df['vol_ma'] * 1.5)
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
        last_closed['close'] >
        last_closed['open']
    )

    bearish_candle = (
        last_closed['close'] <
        last_closed['open']
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

    strong_trend = (
        adx_min <
        last_closed['adx'] <
        adx_max
    )

    # =========================================================
    # RSI FILTERS
    # =========================================================

    rsi_good_long = (
        50 <
        last_closed['rsi'] <
        68
    )

    rsi_good_short = (
        32 <
        last_closed['rsi'] <
        50
    )

    # =========================================================
    # MARKET STRUCTURE BREAK
    # =========================================================

    higher_high = (
        last_closed['high'] >
        prev_closed['high']
    )

    lower_low = (
        last_closed['low'] <
        prev_closed['low']
    )

    # =========================================================
    # FVG + VOLUME CONFIRMATION
    # =========================================================

    bullish_fvg_recent = (
        df['fvg_bullish']
        .iloc[-6:-1]
        .any()
    )

    bearish_fvg_recent = (
        df['fvg_bearish']
        .iloc[-6:-1]
        .any()
    )

    recent_vol_surge = (
        df['volume_surge']
        .iloc[-4:-1]
        .any()
    )

    # =========================================================
    # AVOID HUGE OVEREXTENDED CANDLES
    # =========================================================

    candle_size = (
        last_closed['high'] -
        last_closed['low']
    )

    avoid_extreme_candle = (
        candle_size <
        (last_closed['atr'] * 2.5)
    )

    # =========================================================
    # LONG CONDITION
    # =========================================================

    long_condition = (
        is_uptrend and
        htf_trend == "BULLISH" and
        strong_trend and
        bullish_candle and
        bullish_fvg_recent and
        recent_vol_surge and
        rsi_good_long and
        higher_high and
        avoid_extreme_candle
    )

    # =========================================================
    # SHORT CONDITION
    # =========================================================

    short_condition = (
        is_downtrend and
        htf_trend == "BEARISH" and
        strong_trend and
        bearish_candle and
        bearish_fvg_recent and
        recent_vol_surge and
        rsi_good_short and
        lower_low and
        avoid_extreme_candle
    )

    signal = None
    analysis = ""

    # =========================================================
    # LONG SIGNAL
    # =========================================================

    if long_condition:

        signal = "LONG"

        analysis = (
            f"• Strong Bullish Trend\n"
            f"• ADX: {last_closed['adx']:.1f}\n"
            f"• RSI: {last_closed['rsi']:.1f}\n"
            f"• Volume Confirmed\n"
            f"• Bullish Structure Break"
        )

    # =========================================================
    # SHORT SIGNAL
    # =========================================================

    elif short_condition:

        signal = "SHORT"

        analysis = (
            f"• Strong Bearish Trend\n"
            f"• ADX: {last_closed['adx']:.1f}\n"
            f"• RSI: {last_closed['rsi']:.1f}\n"
            f"• Volume Confirmed\n"
            f"• Bearish Structure Break"
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
            (
                (last_closed['high'] - last_closed['low'])
                * 0.5
            )
        )

        atr = last_closed['atr']

        # =====================================================
        # LONG
        # =====================================================

        if signal == "LONG":

            # Ensure limit is below market
            if limit_price >= current_market:

                limit_price = (
                    current_market * 0.998
                )

            sl = (
                limit_price -
                (atr * atr_multiplier)
            )

            risk = (
                limit_price - sl
            )

            if risk <= 0:
                return {"signal": None}

            tp = (
                limit_price +
                (risk * rr_ratio)
            )

        # =====================================================
        # SHORT
        # =====================================================

        elif signal == "SHORT":

            # Ensure limit above market
            if limit_price <= current_market:

                limit_price = (
                    current_market * 1.002
                )

            sl = (
                limit_price +
                (atr * atr_multiplier)
            )

            risk = (
                sl - limit_price
            )

            if risk <= 0:
                return {"signal": None}

            tp = (
                limit_price -
                (risk * rr_ratio)
            )

    return {
        "signal": signal,
        "analysis": analysis,
        "price": limit_price,
        "sl": sl,
        "tp": tp
    }
