import os
from pathlib import Path
from dotenv import load_dotenv

BASE = Path(__file__).parent
load_dotenv(BASE / ".env")

DATA_DIR = BASE / "data"
CANDLE_DIR = DATA_DIR / "candles"
DB_PATH = DATA_DIR / "audit.db"
DATA_DIR.mkdir(exist_ok=True)
CANDLE_DIR.mkdir(exist_ok=True)

EXPORT_TZ = os.getenv("EXPORT_TZ", "Africa/Lagos")
SPREAD_PIPS = float(os.getenv("SPREAD_PIPS", "1.0"))
MAX_HOURS = float(os.getenv("MAX_HOURS", "72"))
MISMATCH_SL_MULT = float(os.getenv("MISMATCH_SL_MULT", "1.5"))  # candle vs entry sanity check
MAX_DATA_GAP_MIN = 15

# Symbols that are not plain FX pairs (FX uses f"{SYM}=X" automatically)
YAHOO_MAP = {
    "NATGAS": "NG=F", "USOIL": "CL=F", "UKOIL": "BZ=F",
    "XAUUSD": "GC=F", "XAGUSD": "SI=F", "COPPER": "HG=F",
    "DXY": "DX-Y.NYB", "US30": "YM=F", "NAS100": "NQ=F", "SPX500": "ES=F",
    # Names MercuryEdge actually sends. Without these they fell through to
    # f"{SYM}=X" (e.g. "VIX=X"), which Yahoo has no candles for.
    "VIX": "^VIX", "SPX": "^GSPC", "NASDAQ": "^NDX", "DJI": "^DJI",
}
# Price units per "pip" for non-FX symbols
PIP = {"NATGAS": 0.001, "USOIL": 0.01, "UKOIL": 0.01, "XAUUSD": 0.1,
       "XAGUSD": 0.01, "COPPER": 0.001,
       "DXY": 0.01, "VIX": 0.01, "SPX": 1.0, "NASDAQ": 1.0, "DJI": 1.0}
