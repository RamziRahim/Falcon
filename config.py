
"""
Swing Trading Platform Configuration
PROJECT_NAME = "Falcon"
Version: 1.1.0
"""
import os
from dotenv import load_dotenv

# Loads variables from a local .env file (if present) into the environment.
load_dotenv()
# =============================================================================
# Falcon Version
# =============================================================================

FALCON_NAME = "Falcon"

FALCON_VERSION = "0.2.0"

BUILD_DATE = "2026-06-28"

MASTER_FILE = "master_watchlist.xlsx"
DATA_FOLDER = "data"
LOG_FOLDER = "logs"
CACHE_FOLDER = "cache"
OUTPUT_FOLDER = "output"

# ==========================================
# Strategy Configuration
# ==========================================

STRATEGY_FOLDER = "strategies"

QUERY_FILE_NAME = "screen.query"

# ==========================================
# Screener.in
# ==========================================

SCREENER_BASE_URL = "https://www.screener.in"

SCREENER_LOGIN_URL = f"{SCREENER_BASE_URL}/login/"

SCREENER_QUERY_URL = f"{SCREENER_BASE_URL}/screen/raw/"

SCREENER_TIMEOUT = 60000

HEADLESS = True

# ==========================================
# Credentials
# ==========================================

SCREENER_USERNAME = os.environ.get("SCREENER_USERNAME")
SCREENER_PASSWORD = os.environ.get("SCREENER_PASSWORD")

if not SCREENER_USERNAME or not SCREENER_PASSWORD:
    print(
        "[CONFIG WARNING] SCREENER_USERNAME / SCREENER_PASSWORD not found. "
        "Create a .env file in the project root (copy .env.example) and fill "
        "in your real Screener.in login. Screener-dependent features will fail "
        "until this is set."
    )

# ==========================================
# Excel
# ==========================================

EXPORT_INDEX = False

OVERWRITE_OUTPUT = True


DOWNLOAD_PERIOD = "2y"
DOWNLOAD_INTERVAL = "1d"
AUTO_ADJUST = True

SWING_WINDOW = 3
UR_WINDOW = 5

SMA50 = 50
SMA150 = 150
SMA200 = 200

RSI_PERIOD = 14
ATR_PERIOD = 14
RVOL20_PERIOD = 20
RVOL50_PERIOD = 50
VOLUME_Z_PERIOD = 20
VOLUME_TREND_PERIOD = 20
GAP_LOOKBACK = 20

RS_3M = 63
RS_6M = 126
RS_12M = 252

RS_WEIGHT_3M = 0.40
RS_WEIGHT_6M = 0.30
RS_WEIGHT_12M = 0.30

PIVOT_LOOKBACK = 20
NEAR_PIVOT_PCT = 2
BUILDING_BASE_PCT = 5

MIN_RS_RANK = 80
MIN_COMPOSITE_SCORE = 80
MAX_FAKEOUT_RISK = 40

LOW_RISK = 20
MODERATE_RISK = 40
HIGH_RISK = 60

NIFTY50 = "^NSEI"
MIDCAP100 = "^NSEMDCP50"
SMALLCAP100 = "^CNXSC"
INDIA_VIX = "^INDIAVIX"

FAIL_INDUSTRY_KEYWORDS = [
    "bank","insurance","credit services","mortgage",
    "consumer finance","tobacco","wineries","distilleries"
]

REVIEW_INDUSTRY_KEYWORDS = [
    "capital markets","financial conglomerates",
    "asset management","stock exchanges","financial data"
]

SUMMARY_KEYWORDS = [
    "interest income","lending","loan","mortgage",
    "credit card","microfinance","insurance","alcohol",
    "beer","whisky","liquor","tobacco","cigarette",
    "casino","betting","gambling"
]

TOP_CANDIDATES = 20
PLATFORM_VERSION = "1.0"

# =============================================================================
# Market Data
# =============================================================================

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

# Root folders
DATA_FOLDER = PROJECT_ROOT / "data"

RAW_DATA_FOLDER = DATA_FOLDER / "raw"

TECHNICAL_DATA_FOLDER = DATA_FOLDER / "technical"

PATTERN_DATA_FOLDER = DATA_FOLDER / "patterns"

AI_DATA_FOLDER = DATA_FOLDER / "ai"

# Default market data provider
MARKET_DATA_PROVIDER = "NSE"

# OHLCV Columns
DATE_COLUMN = "Date"
OPEN_COLUMN = "Open"
HIGH_COLUMN = "High"
LOW_COLUMN = "Low"
CLOSE_COLUMN = "Close"
VOLUME_COLUMN = "Volume"

# Cache
CACHE_FILE_EXTENSION = ".parquet"

# =============================================================================
# Yahoo Finance
# =============================================================================

YFINANCE_AUTO_ADJUST = False

YFINANCE_PROGRESS = False

DEFAULT_HISTORY_YEARS = 10

# =============================================================================
# Data Validation
# =============================================================================

REQUIRED_HISTORY_COLUMNS = [
    "Date",
    "Open",
    "High",
    "Low",
    "Close",
    "Volume",
]
