
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

# Phase 4.6: which frozen v2 consolidation-quality model artifact
# (models/consolidation_quality_{version}.json) live scoring and backtest
# replay both load via scoring.consolidation_quality_model.load_model_artifact().
# The one, explicit place that decides which model is active -- promoting
# a refit means changing this constant in a reviewed, committed change,
# never automatic pickup of "the newest artifact file in the directory".
ACTIVE_MODEL_VERSION = "v1"
MODEL_ARTIFACT_DIR = "models"

# Round-trip transaction cost (brokerage + STT + slippage, entry+exit combined)
# as a fraction of trade value -- backtesting/episode_builder.py subtracts this
# from every episode's gross return to get net_return_pct. 0.3% is a
# conservative blended estimate for NSE cash-market swing trades; every
# backtest report should show gross AND net so this assumption stays visible
# rather than silently baked into a single number.
ROUND_TRIP_COST_PCT = 0.003

# Time stop (I-3): single source of truth for how long a swing trade is
# held before a TIME_EXIT if neither target nor stop was hit --
# backtesting/outcome_measurement.py's measure_forward_outcome() and
# backtesting/backtest_runner.py's run_backtest() both default to this
# rather than each carrying their own hardcoded number, and
# leadership_decision_engine.py's get_entry_target_stop() surfaces it as
# part of the trade plan (alongside entry/stop_loss/target) so a consumer
# knows the intended holding horizon without reaching into backtest-only
# config. Raised from the prior implicit 20 to 40 trading days -- roughly
# two calendar months, a more realistic swing-trade horizon than one month.
MAX_HOLDING_TRADING_DAYS = 40

# Breakout-recency contract (A-5): all 5 continuation-pattern detectors
# confirm a breakout using only the LATEST bar (Close > pivot_level and
# Volume >= volume_baseline * 1.5) -- a stock that broke out weeks ago and
# has simply stayed above its pivot reads identically to one breaking out
# today. technical_analysis/pattern_system/breakout_recency.py's
# compute_breakout_recency() uses this as the "k" in
# breakout_within_last_k_bars -- matches backtest_runner.run_backtest()'s
# own sample_every_n_days default (5): a signal is "fresh" if it wasn't
# already visible as a confirmed breakout the last time a 5-day-cadence
# replay would have looked.
BREAKOUT_RECENCY_K_BARS = 5

# Structural exits + RR floor (2.2, I-6): get_entry_target_stop() prices
# the stop off the pattern's own structural low (VCP's final contraction
# low, the flat base's low, etc. -- see
# decision_engine.candidate_assembler.PATTERN_STRUCTURAL_LOW_COLUMN_MAP)
# instead of a flat 2x-ATR guess, with the target as a measured move
# (entry + the pattern's own height) instead of a flat 2.5x-ATR guess.
# ATR still bounds how tight/wide the structural stop is allowed to be --
# a structural low that's absurdly close or absurdly far from entry
# (thin/noisy data, a mis-detected pivot) shouldn't produce an unusably
# tight or unusably wide stop just because that's literally where the
# pattern's low sat.
ATR_STOP_FLOOR_MULTIPLE = 1.0    # stop can't be tighter than this many ATRs from entry
ATR_STOP_CEILING_MULTIPLE = 3.0  # stop can't be wider than this many ATRs from entry

# Two-low model (2.2 fix, I-6): the stop prices off the pattern's PROXIMAL
# low (its nearest support -- VCP's final contraction low, the flag's
# pullback low, etc.) rather than the deeper structural low the target
# uses, since pricing both off the same low forced reward:risk toward
# 1.0 whenever the stop was unclamped. A small buffer pushes the stop
# below the proximal low itself -- support sitting exactly at the stop
# gets clipped by ordinary noise, not just a genuine breakdown.
STOP_BUFFER_ATR_MULTIPLE = 0.25

# Floor under the measured-move target distance (entry to structural
# low) -- a shallow pattern shouldn't produce a target so close to entry
# that it can't clear the RR floor even with a well-behaved stop.
TARGET_MIN_ATR_MULTIPLE = 2.0

# Minimum acceptable reward:risk (measured-move target distance / actual
# stop distance) for an EXECUTE-grade signal. Below this floor, the signal
# is downgraded to ALERT_WATCHLIST (RR_BELOW_FLOOR cap, see categorize())
# -- a technically well-scored setup with a poor risk:reward isn't worth
# EXECUTE-grade conviction. Threaded end-to-end like
# enable_microstructure_signals: a single config default, overridable per
# call for tuning-split experiments without touching call sites.
MIN_REWARD_RISK = 1.25

NIFTY50 = "^NSEI"
NIFTY_MIDCAP_150 = "NIFTYMIDCAP150.NS"   # renamed from MIDCAP100 — it was never Midcap 100
NIFTY_SMALLCAP_250 = "NIFTYSMLCAP250.NS"  # renamed from SMALLCAP100 — it was never Smallcap 100
INDIA_VIX = "^INDIAVIX"

# =============================================================================
# Ethical Exclusion Filter
# =============================================================================
# Permanent, code-level exclusion -- holds regardless of which universe feeds
# categorize() (live Screener-sourced scan, any future wider scan, or the
# backtest replay path), unlike the live Screener.in query's own filters,
# which only apply to that one candidate source. See
# decision_engine.leadership_decision_engine.TECHNICAL_DISQUALIFIERS for
# where this is enforced (unconditionally -- sector/ticker identity is
# static, point-in-time-safe data, so there's no lookahead-bias reason to
# ever skip this check, including in backtests).
#
# Both lists are meant to be extended later -- keep entries one-per-line
# with a short comment, alphabetized isn't required.

# Sector-level exclusion (Yahoo's own "Sector" classification, already
# threaded through scoring.sector_map / scoring.scoring_engine). Safe to do
# at the sector level for Financial Services specifically -- Yahoo's broad
# bucket (banks, NBFCs, insurance, asset managers, interest-based lending)
# is a reasonably clean match for the actual intent without meaningfully
# over-excluding unrelated companies. Do NOT add Consumer Defensive here to
# try to catch alcohol -- that bucket also contains hundreds of unrelated
# packaged-food/household-goods companies (see EXCLUDED_TICKERS below,
# which is why alcohol is excluded by ticker instead).
EXCLUDED_SECTORS = [
    "Financial Services",
]

# Verified against live NSE data as of 2026-08-17 (see the detailed note
# below for method) -- re-sweep periodically, not just once. Tickers can
# rename (this project already hit MCDOWELL-N -> UNITDSPR once), new
# alcohol companies list, and existing ones delist -- nothing else in
# this codebase will notice if this list quietly goes stale.
#
# Hand-curated, ticker-level exclusion for alcohol manufacturers/distillers/
# breweries/vineyards -- NOT done at the sector level (Yahoo's beverage
# companies sit under "Consumer Defensive" alongside hundreds of unrelated
# staples companies). Every symbol below individually confirmed directly
# against NSE's own data (nselib.capital_market.equity_list() for the
# mainboard master list, sme_band_complete() for the SME segment, and
# price_volume_and_deliverable_position_data() to confirm each symbol
# actually has real recent trading data -- the same source this codebase
# already uses elsewhere for authoritative ticker data, not a secondary
# web source) on 2026-08-17. An initial pass sourced from Screener.in/
# Tickertape included several symbols that turned out to be BSE-only or
# not currently NSE-listed under any symbol (Asgard Alcobev, Jagatjit
# Industries, Fratelli Vineyards, Monika Alcobev, Cupid Breweries and
# Distilleries, Piccadily Sugar and Allied Industries, Valencia
# Nutrition) -- a Screener.in page existing doesn't confirm NSE listing,
# it covers BSE too, so those were dropped rather than left in as
# unverified/dead entries. A full sweep of NSE's mainboard company-name
# list for alcohol-related keywords also surfaced two real, currently-
# traded companies missing from that initial pass (Grand Oak Canyons
# Distillery, Ravi Kumar Distilleries), added below.
EXCLUDED_TICKERS = [
    "UNITDSPR.NS",    # United Spirits
    "UBL.NS",         # United Breweries
    "RADICO.NS",      # Radico Khaitan
    "ABDL.NS",        # Allied Blenders and Distillers
    "TI.NS",          # Tilaknagar Industries
    "PICCADIL.NS",    # Piccadily Agro Industries
    "GLOBUSSPR.NS",   # Globus Spirits
    "GMBREW.NS",      # G M Breweries
    "SDBL.NS",        # Som Distilleries and Breweries
    "ASALCBR.NS",     # Associated Alcohols & Breweries
    "SULA.NS",        # Sula Vineyards
    "IFBAGRO.NS",     # IFB Agro Industries
    "ALCODIS.NS",     # Alcokraft Distilleries (NSE SME segment)
    "GRANDOAK.NS",    # Grand Oak Canyons Distillery
    "RKDL.NS",        # Ravi Kumar Distilleries
]

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
