import ccxt
import pandas as pd
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from strategy import analyze_data
from notifier import send_signal

# =========================================================
# EXCHANGE CONFIGURATION
# =========================================================

exchange = ccxt.mexc({
    'enableRateLimit': True
})

# =========================================================
# HIGH QUALITY PAIRS ONLY
# =========================================================
# Add Gold if available on MEXC
# Example possible symbols:
# 'XAU/USDT:USDT'
# 'GOLD/USDT:USDT'

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
    # GOLD (Enable only if available on MEXC)
    # 'XAU/USDT:USDT',
]

# =========================================================
# FETCH OHLCV DATA
# =========================================================

def fetch_data(
    symbol: str,
    timeframe: str = '15m',
    limit: int = 250
) -> pd.DataFrame:
    """
    Fetch OHLCV data from MEXC.
    """

    try:

        ohlcv = exchange.fetch_ohlcv(
            symbol,
            timeframe=timeframe,
            limit=limit
        )

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
            f"Failed fetching data "
            f"{symbol} {timeframe}: {e}"
        )

        return pd.DataFrame()

# =========================================================
# PROCESS SYMBOL
# =========================================================

def process_symbol(symbol: str):

    try:

        # ================================================
        # ENTRY TIMEFRAME (15m)
        # ================================================

        df_15m = fetch_data(
            symbol=symbol,
            timeframe='15m',
            limit=250
        )

        # ================================================
        # HIGHER TIMEFRAME (1h)
        # ================================================

        df_1h = fetch_data(
            symbol=symbol,
            timeframe='1h',
            limit=120
        )

        # ================================================
        # VALIDATION
        # ================================================

        if df_15m.empty or df_1h.empty:
            return None

        # ================================================
        # ANALYZE STRATEGY
        # ================================================

        result = analyze_data(
            df=df_15m,
            df_htf=df_1h,
            symbol=symbol
        )

        if result.get("signal"):

            return {
                "symbol": symbol,
                "signal": result["signal"],
                "price": result["price"],
                "sl": result["sl"],
                "tp": result["tp"],
                "analysis": result["analysis"]
            }

        return None

    except Exception as e:

        print(f"Error processing {symbol}: {e}")

        return None

# =========================================================
# MAIN MARKET SCANNER
# =========================================================

def scan_markets(cooldown_tracker: dict):

    print("\nLoading MEXC markets...")

    try:

        markets = exchange.load_markets()

        # =================================================
        # ACTIVE USDT PERPETUAL SWAP PAIRS ONLY
        # =================================================

        usdt_pairs = [
            symbol for symbol, market in markets.items()
            if (
                market.get('active') and
                market.get('swap') and
                market.get('quote') == 'USDT'
            )
        ]

    except Exception as e:

        print(f"Failed loading markets: {e}")

        return

    # =====================================================
    # FILTER TO HIGH QUALITY PAIRS ONLY
    # =====================================================

    symbols_to_scan = [
        pair for pair in MAJOR_PAIRS
        if pair in usdt_pairs
    ]

    print(
        f"Scanning "
        f"{len(symbols_to_scan)} "
        f"high-quality pairs..."
    )

    # =====================================================
    # COOLDOWN SETTINGS
    # =====================================================

    current_time = time.time()

    # 2 hours cooldown
    COOLDOWN_PERIOD = 7200

    signals_found = 0

    # =====================================================
    # PARALLEL SCANNING
    # =====================================================

    with ThreadPoolExecutor(max_workers=5) as executor:

        future_to_symbol = {
            executor.submit(
                process_symbol,
                symbol
            ): symbol
            for symbol in symbols_to_scan
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
                        f"Cooldown active for "
                        f"{symbol}"
                    )

                    continue

                # =========================================
                # VALIDATE TRADE LEVELS
                # =========================================

                if (
                    data['price'] is None or
                    data['sl'] is None or
                    data['tp'] is None
                ):
                    continue

                # =========================================
                # PRINT SIGNAL
                # =========================================

                print("\n================================================")

                print(
                    f"SIGNAL FOUND => "
                    f"{data['signal']} "
                    f"{symbol}"
                )

                print(
                    f"ENTRY : {data['price']:.4f}"
                )

                print(
                    f"SL    : {data['sl']:.4f}"
                )

                print(
                    f"TP    : {data['tp']:.4f}"
                )

                print("================================================")

                # =========================================
                # SEND TELEGRAM SIGNAL
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
    # SCAN SUMMARY
    # =====================================================

    print("\n========================================")

    print(
        f"Scan completed | "
        f"Signals found: {signals_found}"
    )

    print("========================================")
