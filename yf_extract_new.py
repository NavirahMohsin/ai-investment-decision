"""
yf_extract.py - Per-company Yahoo Finance extraction with explicit statuses.
Free, no account, no API key (uses the unofficial `yfinance` library).

WHAT THIS DOES DIFFERENTLY FROM A TYPICAL "UNAVAILABLE" IMPLEMENTATION
  * Resolves Indian symbols for you: INFY -> INFY.NS (then INFY.BO, then as-is).
  * Every piece of data ("part") ends with one of these statuses, with the reason:
        OK            data saved
        EMPTY         Yahoo answered but has no data (often legitimate, e.g. no dividends)
        RATE_LIMITED  Yahoo throttled us even after backoff  -> re-run later with --resume
        ERROR         a real failure; the exception type + message is shown
        NOT_FOUND     the symbol does not exist on Yahoo under any tried suffix
  * Retries with backoff on rate limits, stops hammering Yahoo if it keeps refusing.
  * One failing part never kills the others.
  * --resume skips parts already saved, so you can fill gaps after a rate limit.

INSTALL
    pip install -U yfinance pandas
    (old yfinance versions are a common cause of failures - always upgrade first)

USAGE
    python yf_extract.py                              # default TICKERS below
    python yf_extract.py INFY RELIANCE TMPV           # bare NSE symbols
    python yf_extract.py INFY.BO --period 5y          # explicit suffix is respected
    python yf_extract.py --resume                     # only fetch what is missing

OUTPUT (folder "data" by default)
    data/<SYMBOL>/<module>__<part>.csv|json
    data/status.csv            one row per part, with status + reason
    data/sector_peers.csv      your own companies grouped by sector (built from profiles)
    data/sector_summary.csv    per-sector counts / market cap / median ratios
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import re
import sys
import time
import warnings
from pathlib import Path

# yfinance 1.7 + pandas 3 prints many "inplace keyword is deprecated" warnings from
# yfinance's own internals. They are harmless noise, so hide just those.
warnings.filterwarnings("ignore", message=r".*inplace keyword.*")

import pandas as pd
import yfinance as yf
from yfinance.exceptions import (
    YFPricesMissingError,
    YFRateLimitError,
    YFTickerMissingError,
    YFTzMissingError,
)

# Bare NSE symbols. Tata Motors' passenger-vehicle company now trades as TMPV.
TICKERS = ["RELIANCE", "INFY", "HDFCBANK", "TMPV"]

MODULES = [
    "ohlcv", "adjusted_close", "dividends_splits", "fundamentals",
    "profile", "sector", "analyst", "holders",
]

OK, PARTIAL, EMPTY, RATE_LIMITED, ERROR, NOT_FOUND = (
    "OK", "PARTIAL", "EMPTY", "RATE_LIMITED", "ERROR", "NOT_FOUND")

PROFILE_KEYS = [
    "symbol", "longName", "shortName", "exchange", "currency", "country", "state",
    "city", "website", "sector", "sectorKey", "industry", "industryKey",
    "fullTimeEmployees", "longBusinessSummary", "marketCap",
]
RATIO_KEYS = [
    "marketCap", "enterpriseValue", "trailingPE", "forwardPE", "priceToBook",
    "priceToSalesTrailing12Months", "enterpriseToEbitda", "trailingEps", "forwardEps",
    "bookValue", "dividendYield", "dividendRate", "payoutRatio", "beta",
    "returnOnEquity", "returnOnAssets", "profitMargins", "operatingMargins",
    "grossMargins", "revenueGrowth", "earningsGrowth", "debtToEquity", "currentRatio",
    "quickRatio", "totalRevenue", "ebitda", "freeCashflow", "operatingCashflow",
    "totalCash", "totalDebt", "fiftyTwoWeekHigh", "fiftyTwoWeekLow",
    "sharesOutstanding", "floatShares",
]
CAPTURE = {("profile", "profile"), ("fundamentals", "key_ratios")}  # kept for peer table


class NoData(Exception):
    """Raised by our own code when Yahoo returned a stub / nothing usable."""


class State:
    """Shared retry + circuit-breaker settings for one run."""

    def __init__(self, retries=3, base_delay=8.0, max_consec_rl=2, pause=0.6):
        self.retries = retries
        self.base_delay = base_delay
        self.max_consec_rl = max_consec_rl
        self.pause = pause
        self.consec_rl = 0

    @property
    def circuit_open(self) -> bool:
        return self.consec_rl >= self.max_consec_rl


# ------------------------------------------------------------------ helpers
def _has_value(v) -> bool:
    if v is None:
        return False
    if isinstance(v, float) and math.isnan(v):
        return False
    if isinstance(v, str) and not v.strip():
        return False
    if isinstance(v, (list, tuple, set, dict)) and len(v) == 0:
        return False
    return True


def _is_empty(x) -> bool:
    if x is None:
        return True
    if isinstance(x, pd.DataFrame):
        return x.empty or x.dropna(how="all").empty
    if isinstance(x, pd.Series):
        return x.empty or x.dropna().empty
    if isinstance(x, dict):
        return not any(_has_value(v) for v in x.values())
    if isinstance(x, (list, tuple, set)):
        return len(x) == 0
    return False


def _rows(x) -> int:
    try:
        return len(x)
    except TypeError:
        return 0


def _looks_rate_limited(e: Exception) -> bool:
    s = str(e).lower()
    return "too many requests" in s or "429" in s or "rate limit" in s


def _pick(d: dict, keys) -> dict:
    return {k: d[k] for k in keys if k in d and _has_value(d[k])}


def cached(fn):
    box = {}

    def inner():
        if "v" not in box:
            box["v"] = fn()
        return box["v"]
    return inner


class _Capture(logging.Handler):
    """Collects yfinance's own log messages. yfinance swallows many Yahoo errors
    (e.g. HTTP 404) and only logs them, returning an empty table. Capturing the
    message lets us report Yahoo's real reason instead of a vague 'empty'."""

    def __init__(self):
        super().__init__(level=logging.WARNING)
        self.msgs: list[str] = []

    def emit(self, record):
        self.msgs.append(record.getMessage())


def _call_logged(fn):
    cap, lg = _Capture(), logging.getLogger("yfinance")
    lg.addHandler(cap)  # also stops Python printing these messages to the console
    try:
        return fn(), cap.msgs
    finally:
        lg.removeHandler(cap)


def _clean_log(msg: str) -> str:
    d = re.search(r'"description"\s*:\s*"([^"]+)"', msg)
    if d:
        code = re.search(r"HTTP Error (\d+)", msg)
        return f"Yahoo {code.group(1) + ': ' if code else ''}{d.group(1)}"
    return re.sub(r"\s+", " ", msg).strip()[:160]


def attempt(fn, st: State):
    """Call fn() with retries. Returns (status, value, detail)."""
    if st.circuit_open:
        return (RATE_LIMITED, None,
                "skipped: Yahoo kept rate-limiting (circuit open). Wait, then re-run with --resume")
    delay = st.base_delay
    generic_tries = 0
    for n in range(1, st.retries + 1):
        try:
            val, logs = _call_logged(fn)
        except (YFTickerMissingError, YFPricesMissingError, YFTzMissingError, NoData) as e:
            st.consec_rl = 0
            return EMPTY, None, f"{type(e).__name__}: {e}"
        except Exception as e:  # noqa: BLE001 - we classify everything on purpose
            msg = f"{type(e).__name__}: {e}"
            if isinstance(e, YFRateLimitError) or _looks_rate_limited(e):
                if n < st.retries:
                    time.sleep(delay)
                    delay *= 2
                    continue
                st.consec_rl += 1
                return RATE_LIMITED, None, f"{msg} (gave up after {n} attempts)"
            generic_tries += 1
            if generic_tries < 2 and n < st.retries:
                time.sleep(2.0)
                continue
            return ERROR, None, msg
        st.consec_rl = 0
        if _is_empty(val):
            if logs:
                return EMPTY, val, "Yahoo returned no data - " + _clean_log(logs[-1])
            return EMPTY, val, "Yahoo returned no data (can be legitimate for this company/ticker)"
        return OK, val, ""
    return ERROR, None, "exhausted retries"


def aggregate(statuses: list[str]) -> str:
    if statuses and all(s == OK for s in statuses):
        return OK
    if any(s == OK for s in statuses):
        return PARTIAL
    for s in (RATE_LIMITED, ERROR, EMPTY):
        if s in statuses:
            return s
    return EMPTY


# ------------------------------------------------------------------ symbols
def candidate_symbols(raw: str) -> list[str]:
    raw = raw.strip().upper()
    if "." in raw or raw.startswith("^"):
        return [raw]
    return [f"{raw}.NS", f"{raw}.BO", raw]


def resolve_symbol(raw: str, st: State):
    """Return (symbol_or_None, status, tried_list)."""
    tried, saw_rl = [], False
    for cand in candidate_symbols(raw):
        status, _, detail = attempt(
            lambda c=cand: yf.Ticker(c).history(period="1mo", interval="1d"), st)
        tried.append(f"{cand}:{status}")
        if status == OK:
            return cand, OK, tried
        saw_rl = saw_rl or status == RATE_LIMITED
        time.sleep(st.pause)
    return None, (RATE_LIMITED if saw_rl else NOT_FOUND), tried


# ------------------------------------------------------------------ parts
def sector_key_from(info: dict) -> str:
    k = info.get("sectorKey")
    if k:
        return k
    s = info.get("sector")
    if s:
        return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    raise NoData("profile has no sector/sectorKey, cannot query yf.Sector")


def industry_key_from(info: dict) -> str:
    k = info.get("industryKey")
    if k:
        return k
    raise NoData("profile has no industryKey, cannot query yf.Industry")


def build_parts(t, period: str, region: str):
    """List of (module, part, callable). Callables may raise; attempt() classifies."""

    def info_call():
        info = t.info
        if not isinstance(info, dict) or not (info.get("longName") or info.get("shortName")):
            raise NoData("Yahoo returned a stub info dict with no company name")
        return info

    get_info = cached(info_call)
    get_hist = cached(lambda: t.history(period=period, interval="1d",
                                        auto_adjust=False, actions=False))

    def need_cols(df, cols):
        missing = [c for c in cols if c not in df.columns]
        if missing:
            raise NoData(f"history has no column(s) {missing}")
        return df[cols]

    def make_sector():
        try:
            return yf.Sector(sector_key_from(get_info()), region=region)
        except TypeError:  # older yfinance without region=
            return yf.Sector(sector_key_from(get_info()))

    get_sector = cached(make_sector)
    get_industry = cached(lambda: yf.Industry(industry_key_from(get_info())))

    parts = [
        ("ohlcv", "daily", lambda: need_cols(get_hist(), ["Open", "High", "Low", "Close", "Volume"])),
        ("adjusted_close", "adj_close", lambda: need_cols(get_hist(), ["Close", "Adj Close"])),
        ("dividends_splits", "dividends", lambda: t.dividends),
        ("dividends_splits", "splits", lambda: t.splits),
    ]
    for name in ["income_stmt", "balance_sheet", "cashflow", "quarterly_income_stmt",
                 "quarterly_balance_sheet", "quarterly_cashflow"]:
        parts.append(("fundamentals", name, lambda n=name: getattr(t, n)))
    parts += [
        ("fundamentals", "key_ratios", lambda: _pick(get_info(), RATIO_KEYS)),
        ("profile", "profile", lambda: _pick(get_info(), PROFILE_KEYS)),
        ("profile", "info_raw", lambda: get_info()),
    ]
    for name in ["overview", "top_companies", "industries", "top_etfs",
                 "top_mutual_funds", "research_reports"]:
        parts.append(("sector", f"sector_{name}", lambda n=name: getattr(get_sector(), n)))
    for name in ["overview", "top_companies"]:
        parts.append(("sector", f"industry_{name}", lambda n=name: getattr(get_industry(), n)))
    parts += [
        ("analyst", "price_targets", lambda: t.analyst_price_targets),
        ("analyst", "recommendations", lambda: t.recommendations),
        ("analyst", "upgrades_downgrades", lambda: t.upgrades_downgrades),
        ("analyst", "earnings_estimate", lambda: t.earnings_estimate),
        ("analyst", "revenue_estimate", lambda: t.revenue_estimate),
        ("holders", "institutional_holders", lambda: t.institutional_holders),
        ("holders", "major_holders", lambda: t.major_holders),
        ("holders", "mutualfund_holders", lambda: t.mutualfund_holders),
    ]
    return parts


# ------------------------------------------------------------------ storage
def save_value(base: Path, value) -> Path:
    base.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(value, pd.Series):
        value = value.to_frame()
    if isinstance(value, pd.DataFrame):
        p = Path(str(base) + ".csv")
        value.to_csv(p)
        return p
    p = Path(str(base) + ".json")
    p.write_text(json.dumps(value, default=str, indent=2, ensure_ascii=False), encoding="utf-8")
    return p


def existing_file(base: Path):
    for ext in (".csv", ".json"):
        p = Path(str(base) + ext)
        if p.exists():
            return p
    return None


# ------------------------------------------------------------------ run
def extract_symbol(symbol: str, out: Path, st: State, period: str, region: str,
                   resume: bool, captured: dict) -> list[dict]:
    t = yf.Ticker(symbol)
    rows = []
    for module, part, fn in build_parts(t, period, region):
        base = out / symbol / f"{module}__{part}"
        prior = existing_file(base) if resume else None
        if prior is not None:
            status, detail, n = OK, "already on disk (--resume)", 0
            if (module, part) in CAPTURE and prior.suffix == ".json":
                captured.setdefault(symbol, {})[part] = json.loads(prior.read_text(encoding="utf-8"))
        else:
            status, val, detail = attempt(fn, st)
            n = _rows(val) if status == OK else 0
            if status == OK:
                save_value(base, val)
                if (module, part) in CAPTURE:
                    captured.setdefault(symbol, {})[part] = val
            time.sleep(st.pause)
        rows.append({"symbol": symbol, "module": module, "part": part,
                     "status": status, "rows": n, "detail": detail})
    return rows


def build_peer_tables(captured: dict, out: Path):
    recs = []
    for symbol, d in captured.items():
        p, r = d.get("profile", {}), d.get("key_ratios", {})
        if not p:
            continue
        recs.append({
            "symbol": symbol, "name": p.get("longName") or p.get("shortName"),
            "sector": p.get("sector"), "industry": p.get("industry"),
            "marketCap": p.get("marketCap") or r.get("marketCap"),
            "trailingPE": r.get("trailingPE"), "priceToBook": r.get("priceToBook"),
            "returnOnEquity": r.get("returnOnEquity"), "profitMargins": r.get("profitMargins"),
            "debtToEquity": r.get("debtToEquity"),
        })
    if not recs:
        return None, None
    df = pd.DataFrame(recs).sort_values(["sector", "marketCap"], ascending=[True, False])
    df.to_csv(out / "sector_peers.csv", index=False)
    summ = df.groupby("sector", dropna=False).agg(
        companies=("symbol", "count"), total_market_cap=("marketCap", "sum"),
        median_pe=("trailingPE", "median"), median_roe=("returnOnEquity", "median"),
        median_margin=("profitMargins", "median")).reset_index()
    summ.to_csv(out / "sector_summary.csv", index=False)
    return df, summ


def matrix(all_rows: list[dict], unresolved: dict) -> str:
    syms = list(dict.fromkeys([r["symbol"] for r in all_rows] + list(unresolved)))
    table = []
    for s in syms:
        if s in unresolved:
            table.append([s] + [unresolved[s]] * len(MODULES))
            continue
        line = [s]
        for m in MODULES:
            line.append(aggregate([r["status"] for r in all_rows if r["symbol"] == s and r["module"] == m]))
        table.append(line)
    header = ["symbol"] + MODULES
    widths = [max(len(str(x)) for x in col) for col in zip(header, *table)]
    fmt = lambda row: "  ".join(str(c).ljust(w) for c, w in zip(row, widths))
    return "\n".join([fmt(header), fmt(["-" * w for w in widths])] + [fmt(r) for r in table])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tickers", nargs="*", default=TICKERS)
    ap.add_argument("--out", default="data")
    ap.add_argument("--period", default="max", help="history period: 1mo, 1y, 5y, max ...")
    ap.add_argument("--resume", action="store_true", help="skip parts already saved on disk")
    ap.add_argument("--region", default="US", help="region passed to yf.Sector (see notes)")
    ap.add_argument("--pause", type=float, default=0.6, help="seconds between requests")
    ap.add_argument("--ticker-pause", type=float, default=3.0, help="seconds between companies")
    args = ap.parse_args(argv)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    print(f"yfinance {yf.__version__}  |  output folder: {out.resolve()}")
    st = State(pause=args.pause)
    all_rows, unresolved, captured = [], {}, {}

    for i, raw in enumerate(args.tickers):
        print(f"\n[{i + 1}/{len(args.tickers)}] {raw}")
        symbol, status, tried = resolve_symbol(raw, st)
        if symbol is None:
            unresolved[raw.upper()] = status
            print(f"  could not resolve ({status}); tried: {', '.join(tried)}")
            continue
        print(f"  resolved to {symbol}  (tried: {', '.join(tried)})")
        rows = extract_symbol(symbol, out, st, args.period, args.region, args.resume, captured)
        all_rows += rows
        ok = sum(r["status"] == OK for r in rows)
        print(f"  {ok}/{len(rows)} parts OK")
        if st.circuit_open:
            print("  Yahoo is rate-limiting: cooling down 60s before the next company")
            time.sleep(60)
            st.consec_rl = 0
        time.sleep(args.ticker_pause)

    pd.DataFrame(all_rows).to_csv(out / "status.csv", index=False)
    build_peer_tables(captured, out)

    print("\n=== MODULE STATUS ===")
    print(matrix(all_rows, unresolved))
    bad = [r for r in all_rows if r["status"] != OK]
    if bad:
        print("\n=== WHY (non-OK parts) ===")
        for r in bad:
            where = f"{r['module']}.{r['part']}"
            print(f"{r['symbol']:<12} {where:<44} {r['status']:<13} {r['detail'][:110]}")
    for s in set(r["symbol"] for r in all_rows):
        rs = [r for r in all_rows if r["symbol"] == s]
        if rs and sum(r["status"] == EMPTY for r in rs) / len(rs) >= 0.7:
            print(f"\nWARNING {s}: most parts are EMPTY. Check the symbol is current, upgrade "
                  f"yfinance, or Yahoo may be silently throttling this IP.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
