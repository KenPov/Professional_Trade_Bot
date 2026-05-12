import ccxt
import pandas as pd
import time

from concurrent.futures import (
    ThreadPoolExecutor,
    as_completed
)

from strategy import analyze_data
from notifier import send_signal

# =========================================================
# MEXC FUTURES CONFIGURATION
# =========================================================

exchange = ccxt.mexc({
    'enableRateLimit': True,
    'timeout': 30000,
    'options': {
        'defaultType': 'swap'
    }
})

# =========================================================
# HIGH QUALITY PAIRS ONLY
# =========================================================

MAJOR_PAIRS = [
    'BTC/USDT:USDT',
    'ETH/USDT:USDT',
    'SOL/USDT:USDT',
    'BNB/USDT:USDT',
    'XRP/USDT:USDT',
    'DOGE/USDT:USDT',
    'ADA/USDT:USDT',
    'AVAX/USDT:USDT',
    'LINK/USDT:USDT',
    'SUI/USDT:USDT',
    'LTC/USDT:USDT',
    'BCH/USDT:USDT',
    'XAU/USDT:USDT'
]

# =========================================================
# FETCH MARKET DATA
# =========================================================

def fetch_data(
    symbol: str,
    timeframe: str = '15m',
    limit: int = 250
) -> pd.DataFrame:

    max_retries = 3

    for attempt in range(max_retries):

        try:

            ohlcv = exchange.fetch_ohlcv(
                symbol,
                timeframe=timeframe,
                limit=limit
            )

            if not ohlcv:
                return pd.DataFrame()

            df = pd.DataFrame(
                ohlcv,
                columns=[
                    'timestamp',
                    'open',
                    'high',
                    'low',
                    'close',
                    'volume'
                ]
            )

            df['timestamp'] = pd.to_datetime(
                df['timestamp'],
                unit='ms'
            )

            return df

        except Exception as e:

            print(
                f"Retry "
                f"{attempt + 1}/{max_retries} "
                f"fetching {symbol} "
                f"{timeframe}: {e}"
            )

            time.sleep(2)

    return pd.DataFrame()

# =========================================================
# PROCESS SINGLE SYMBOL
# =========================================================

def process_symbol(symbol: str):

    try:

        # =================================================
        # ENTRY TIMEFRAME
        # =================================================

        df_15m = fetch_data(
            symbol=symbol,
            timeframe='15m',
            limit=250
        )

        # =================================================
        # HIGHER TIMEFRAME
        # =================================================

        df_1h = fetch_data(
            symbol=symbol,
            timeframe='1h',
            limit=120
        )

        # =================================================
        # VALIDATION
        # =================================================

        if df_15m.empty:
            return None

        if df_1h.empty:
            return None

        # =================================================
        # ANALYZE STRATEGY
        # =================================================

        result = analyze_data(
            df=df_15m,
            df_htf=df_1h,
            symbol=symbol
        )

        if not result.get("signal"):
            return None

        return {
            "symbol": symbol,
            "signal": result["signal"],
            "price": result["price"],
            "sl": result["sl"],
            "tp": result["tp"],
            "analysis": result["analysis"]
        }

    except Exception as e:

        print(
            f"Error processing "
            f"{symbol}: {e}"
        )

        return None

# =========================================================
# MAIN SCANNER
# =========================================================

def scan_markets(cooldown_tracker: dict):

    print("\nLoading MEXC futures markets...")

    try:

        markets = exchange.load_markets()

    except Exception as e:

        print(f"Failed loading markets: {e}")

        return

    # =====================================================
    # FILTER AVAILABLE PAIRS
    # =====================================================

    available_pairs = []

    for pair in MAJOR_PAIRS:

        if pair in markets:

            market = markets[pair]

            if (
                market.get('active') and
                (
                    market.get('swap') or
                    market.get('future')
                )
            ):

                available_pairs.append(pair)

    # =====================================================
    # NO PAIRS FOUND
    # =====================================================

    if not available_pairs:

        print("No valid futures pairs found.")

        return

    print(
        f"Scanning "
        f"{len(available_pairs)} "
        f"pairs..."
    )

    # =====================================================
    # COOLDOWN
    # =====================================================

    current_time = time.time()

    COOLDOWN_PERIOD = 7200

    signals_found = 0

    # =====================================================
    # IMPORTANT:
    # Lower workers for MEXC stability
    # =====================================================

    with ThreadPoolExecutor(max_workers=2) as executor:

        future_to_symbol = {
            executor.submit(
                process_symbol,
                symbol
            ): symbol
            for symbol in available_pairs
        }

        for future in as_completed(future_to_symbol):

            symbol = future_to_symbol[future]

            try:

                data = future.result()

                if not data:
                    continue

                # =========================================
                # COOLDOWN CHECK
                # =========================================

                last_signal_time = cooldown_tracker.get(
                    symbol,
                    0
                )

                if (
                    current_time - last_signal_time
                    < COOLDOWN_PERIOD
                ):

                    print(
                        f"Cooldown active "
                        f"for {symbol}"
                    )

                    continue

                # =========================================
                # VALIDATE PRICES
                # =========================================

                if (
                    data['price'] is None or
                    data['sl'] is None or
                    data['tp'] is None
                ):
                    continue

                # =========================================
                # DISPLAY SIGNAL
                # =========================================

                print("\n===================================")

                print(
                    f"SIGNAL => "
                    f"{data['signal']} "
                    f"{symbol}"
                )

                print(
                    f"ENTRY : "
                    f"{data['price']:.4f}"
                )

                print(
                    f"SL    : "
                    f"{data['sl']:.4f}"
                )

                print(
                    f"TP    : "
                    f"{data['tp']:.4f}"
                )

                print("===================================")

                # =========================================
                # SEND TELEGRAM
                # =========================================

                send_signal(
                    symbol=data['symbol'],
                    side=data['signal'],
                    price=data['price'],
                    sl=data['sl'],
                    tp=data['tp'],
                    analysis=data['analysis']
                )

                # =========================================
                # UPDATE COOLDOWN
                # =========================================

                cooldown_tracker[symbol] = current_time

                signals_found += 1

            except Exception as e:

                print(
                    f"Error handling "
                    f"{symbol}: {e}"
                )

    # =====================================================
    # SUMMARY
    # =====================================================

    print("\n===================================")

    print(
        f"Scan completed | "
        f"Signals found: {signals_found}"
    )

    print("===================================")
