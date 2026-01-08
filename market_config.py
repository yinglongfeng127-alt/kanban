from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional


MARKET_CONFIG_PATH = Path("data/market_instruments.json")


@dataclass(frozen=True)
class MarketInstrumentConfig:
    name: str
    symbol: str
    order: Optional[int] = None


DEFAULT_MARKET_INSTRUMENTS: List[MarketInstrumentConfig] = [
    MarketInstrumentConfig(name="SPX", symbol="^GSPC", order=0),
    MarketInstrumentConfig(name="NDX", symbol="^NDX", order=1),
    MarketInstrumentConfig(name="10Y", symbol="^TNX", order=2),
    MarketInstrumentConfig(name="DXY", symbol="DX-Y.NYB", order=3),
    MarketInstrumentConfig(name="WTI", symbol="CL=F", order=4),
    MarketInstrumentConfig(name="GOLD", symbol="GC=F", order=5),
    MarketInstrumentConfig(name="BTC", symbol="BTC-USD", order=6),
]


def _parse_market_config(raw: Any) -> List[MarketInstrumentConfig]:
    if not isinstance(raw, list):
        raise ValueError("market config must be a list")

    seen_names: set[str] = set()
    seen_symbols: set[str] = set()
    items: List[MarketInstrumentConfig] = []

    for idx, entry in enumerate(raw):
        if not isinstance(entry, dict):
            raise ValueError(f"entry {idx} is not an object")
        name = entry.get("name")
        symbol = entry.get("symbol")
        order = entry.get("order")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"entry {idx} missing name")
        if not isinstance(symbol, str) or not symbol.strip():
            raise ValueError(f"entry {idx} missing symbol")
        if order is not None and not isinstance(order, int):
            raise ValueError(f"entry {idx} order must be int")
        if name in seen_names:
            raise ValueError(f"duplicate name: {name}")
        if symbol in seen_symbols:
            raise ValueError(f"duplicate symbol: {symbol}")
        seen_names.add(name)
        seen_symbols.add(symbol)
        items.append(MarketInstrumentConfig(name=name, symbol=symbol, order=order))

    if not items:
        raise ValueError("market config is empty")

    return items


def load_market_instruments() -> List[MarketInstrumentConfig]:
    if not MARKET_CONFIG_PATH.exists():
        logging.warning(
            "Market config missing at %s. Falling back to defaults.",
            MARKET_CONFIG_PATH,
        )
        return DEFAULT_MARKET_INSTRUMENTS

    try:
        raw = json.loads(MARKET_CONFIG_PATH.read_text())
        return _parse_market_config(raw)
    except Exception as exc:
        logging.warning("Market config invalid (%s). Falling back to defaults.", exc)
        return DEFAULT_MARKET_INSTRUMENTS


def market_display_order(instruments: List[MarketInstrumentConfig]) -> List[str]:
    indexed = list(enumerate(instruments))

    def sort_key(item: tuple[int, MarketInstrumentConfig]) -> tuple[bool, int, int]:
        idx, instrument = item
        order = instrument.order
        return (order is None, order if order is not None else 0, idx)

    ordered = sorted(indexed, key=sort_key)
    return [instrument.name for _, instrument in ordered]
