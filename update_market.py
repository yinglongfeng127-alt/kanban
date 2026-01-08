from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

from market_config import MarketInstrumentConfig, load_market_instruments


DATA_DIR = Path("data")
MARKET_FILE = DATA_DIR / "market_snapshot.json"


MARKET_INSTRUMENTS: List[MarketInstrumentConfig] = load_market_instruments()


def pct_change(current: Optional[float], previous: Optional[float]) -> Optional[float]:
    """Return percentage change or None when unavailable/invalid."""
    if current is None or previous is None:
        return None
    if previous == 0:
        return None
    return (current - previous) / previous * 100


def last_nth(series: pd.Series, n: int) -> Optional[float]:
    """Return the nth value from the end (n=0 is last), skipping NaNs."""
    cleaned = series.dropna()
    if cleaned.empty:
        return None
    if n < 0 or n >= len(cleaned):
        return None
    return float(cleaned.iloc[-(n + 1)])


def suppress_yf_output() -> Tuple[StringIO, StringIO]:
    """Silence noisy yfinance stdout/stderr for failed downloads."""
    import contextlib

    stdout_buffer, stderr_buffer = StringIO(), StringIO()
    suppress_ctx = contextlib.ExitStack()
    suppress_ctx.enter_context(contextlib.redirect_stdout(stdout_buffer))
    suppress_ctx.enter_context(contextlib.redirect_stderr(stderr_buffer))
    logging.getLogger("yfinance").setLevel(logging.ERROR)
    logging.getLogger("urllib3").setLevel(logging.ERROR)
    return suppress_ctx, stdout_buffer, stderr_buffer


def fetch_all_history() -> Tuple[Optional[Dict[str, pd.Series]], Optional[str]]:
    try:
        import yfinance as yf
    except Exception as exc:  # pragma: no cover - import failure path
        return None, f"import_failed: {exc}"

    suppress_ctx, _, _ = suppress_yf_output()
    with suppress_ctx:
        tickers = [i.symbol for i in MARKET_INSTRUMENTS]
        history = None
        periods = ["1y", "6mo", "3mo", "1mo"]
        for period in periods:
            try:
                history = yf.download(
                    tickers=tickers,
                    period=period,
                    interval="1d",
                    progress=False,
                    auto_adjust=False,
                    group_by="ticker",
                    threads=False,
                )
            except Exception:
                history = None
            if history is not None and len(history) > 0:
                break
        if history is None or len(history) == 0:
            return None, "no_data"

        # Fallback: if batched download yields nothing per symbol, retry individually with shorter periods.
        if isinstance(history.columns, pd.MultiIndex):
            available_symbols = {
                col[0] for col in history.columns if history[col].dropna().shape[0] > 0
            }
        else:
            available_symbols = set()
        missing_symbols = [s for s in tickers if s not in available_symbols]
        if missing_symbols:
            for symbol in missing_symbols:
                single_history = None
                for period in periods:
                    try:
                        single_history = yf.download(
                            tickers=symbol,
                            period=period,
                            interval="1d",
                            progress=False,
                            auto_adjust=False,
                            group_by="ticker",
                            threads=False,
                        )
                    except Exception:
                        single_history = None
                    if single_history is not None and len(single_history) > 0:
                        break
                if single_history is not None and len(single_history) > 0:
                    # Merge into combined history-like structure by adding MultiIndex columns
                    if not isinstance(history.columns, pd.MultiIndex):
                        history = pd.concat({symbol: single_history}, axis=1)
                    else:
                        history = pd.concat(
                            [history, pd.concat({symbol: single_history}, axis=1)],
                            axis=1,
                        )

    series_map: Dict[str, pd.Series] = {}
    # When downloading multiple tickers, yfinance returns a DataFrame with a column MultiIndex: (symbol, field)
    if isinstance(history.columns, pd.MultiIndex):
        for symbol in {col[0] for col in history.columns}:
            close = history[symbol].get("Close")
            if close is not None and not close.dropna().empty:
                series_map[symbol] = close
    else:
        close = history.get("Close")
        if (
            close is not None
            and not close.dropna().empty
            and len(MARKET_INSTRUMENTS) == 1
        ):
            series_map[MARKET_INSTRUMENTS[0].symbol] = close

    return series_map, None


def fetch_market_entry(
    instrument: MarketInstrumentConfig,
    series_map: Dict[str, pd.Series],
    global_error: Optional[str],
) -> dict:
    fields = {
        "name": instrument.name,
        "symbol": instrument.symbol,
        "price": None,
        "change_1d_pct": None,
        "change_5d_pct": None,
        "change_20d_pct": None,
        "error": "",
    }

    if global_error:
        fields["error"] = global_error
        return fields

    closes = series_map.get(instrument.symbol)
    if closes is None or closes.dropna().empty:
        fields["error"] = "no_close_prices"
        return fields

    latest = last_nth(closes, 0)
    day_ago = last_nth(closes, 1)
    five_ago = last_nth(closes, 5)
    twenty_ago = last_nth(closes, 20)

    fields["price"] = latest
    fields["change_1d_pct"] = pct_change(latest, day_ago)
    fields["change_5d_pct"] = pct_change(latest, five_ago)
    fields["change_20d_pct"] = pct_change(latest, twenty_ago)

    return fields


def build_snapshot() -> dict:
    series_map, global_error = fetch_all_history()
    items = [
        fetch_market_entry(instrument, series_map or {}, global_error)
        for instrument in MARKET_INSTRUMENTS
    ]
    return {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "items": items,
    }


def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def write_snapshot(snapshot: dict) -> None:
    ensure_data_dir()
    MARKET_FILE.write_text(json.dumps(snapshot, indent=2))


def main() -> None:
    snapshot = build_snapshot()
    write_snapshot(snapshot)


if __name__ == "__main__":
    main()
