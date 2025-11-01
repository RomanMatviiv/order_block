# src/config.py
# List of symbols to process. Edit this list to add or remove trading pairs.
SYMBOLS = [
    "LINKUSDT",
    "ADAUSDT",
    "1000PEPEUSDT",
    "1000FLOKIUSDT",
    "XRPUSDT",
    "DOGEUSDT",
    "TRBUSDT",
    "AAVEUSDT",
    "1000SHIBUSDT",
    "DYDXUSDT",
    "LDOUSDT",
    "SUIUSDT",
    "DODOXUSDT",
    "JUPUSDT",
    "TONUSDT",
    "ZROUSDT",
    "AEROUSDT",
    "AVAUSDT",
    "DOODUSDT",
]

# Timeframes to run the detector for (both history and live). Default: 15m and 30m
TIMEFRAMES = ["15m", "30m"]

# Live polling interval in seconds (used by run_live worker)
POLL_INTERVAL_SEC = 30

# Number of days of historical data to fetch
HISTORY_DAYS = 2

# Strong move threshold for order block detection (multiplier)
STRONG_MOVE_THRESHOLD = 1.5

# Telegram notification timeout in seconds
TELEGRAM_TIMEOUT_SEC = 10

# ========================================
# Advanced Order Block Detection Parameters
# ========================================

# ATR (Average True Range) settings
ATR_PERIOD = 14  # Number of periods for ATR calculation
ATR_MULT = 1.0  # Multiplier for ATR-based thresholds

# Candle body and wick filters
BODY_MIN_RATIO = 0.5  # Minimum body size as ratio of ATR (0.5 = 50% of ATR)
WICK_MAX_RATIO = 0.3  # Maximum opposite-side wick as ratio of body (0.3 = 30% of body)

# Impulse confirmation settings
DETECTION_LOOKAHEAD = 10  # Number of bars to look ahead for impulse confirmation
IMPULSE_MIN_DIR_CANDLES = 6  # Minimum number of directional candles in lookahead period (out of DETECTION_LOOKAHEAD)
IMPULSE_MIN_NET_MOVE = 1.5  # Minimum net price movement as multiple of ATR

# Multi-touch validation
TOUCHES_REQUIRED = 1  # Minimum touches for zone validation (1 = initial touch)
MAX_TOUCHES = 5  # Maximum touches before zone is considered exhausted

# Zone management
ZONE_EXPIRY_BARS = 100  # Number of bars after which a zone expires if not touched
ZONE_MERGE_THRESHOLD = 0.5  # Merge zones if they overlap by this percentage

# Volume and liquidity sweep settings
MIN_VOLUME_SPIKE_MULT = 1.5  # Minimum volume spike as multiple of average volume
LIQUIDITY_SWEEP_WICK_RATIO = 0.6  # Wick must be at least 60% of total range for sweep detection
LIQUIDITY_SWEEP_REVERSAL_BARS = 3  # Number of bars to check for reversal after sweep

# Scoring weights (must sum to 1.0)
SCORE_WEIGHT_BODY_SIZE = 0.20  # Weight for candle body size score
SCORE_WEIGHT_IMPULSE = 0.30  # Weight for impulse strength score
SCORE_WEIGHT_TOUCHES = 0.20  # Weight for number of touches score
SCORE_WEIGHT_VOLUME = 0.15  # Weight for volume spike score
SCORE_WEIGHT_LIQUIDITY_SWEEP = 0.15  # Weight for liquidity sweep detection

# Validate scoring weights sum to 1.0
_TOTAL_SCORE_WEIGHT = (SCORE_WEIGHT_BODY_SIZE + SCORE_WEIGHT_IMPULSE + 
                       SCORE_WEIGHT_TOUCHES + SCORE_WEIGHT_VOLUME + 
                       SCORE_WEIGHT_LIQUIDITY_SWEEP)
assert abs(_TOTAL_SCORE_WEIGHT - 1.0) < 0.001, \
    f"Score weights must sum to 1.0, got {_TOTAL_SCORE_WEIGHT}"
