from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT_MARKET_INSTRUMENTS: List[Dict[str, Any]] = [
    {"name": "SPX", "symbol": "^GSPC", "order": 0},
    {"name": "NDX", "symbol": "^NDX", "order": 1},
    {"name": "10Y", "symbol": "^TNX", "order": 2},
    {"name": "DXY", "symbol": "DX-Y.NYB", "order": 3},
    {"name": "WTI", "symbol": "CL=F", "order": 4},
    {"name": "GOLD", "symbol": "GC=F", "order": 5},
    {"name": "BTC", "symbol": "BTC-USD", "order": 6},
]

CONFIG_PATH = Path("config/market_instruments.json")


def _validate_instruments(raw: Any) -> Optional[List[Dict[str, Any]]]:
    if not isinstance(raw, list):
        return None

    names: set[str] = set()
    symbols: set[str] = set()
    items: List[Dict[str, Any]] = []

    for idx, entry in enumerate(raw):
        if not isinstance(entry, dict):
            return None
        name = entry.get("name")
        symbol = entry.get("symbol")
        order = entry.get("order")

        if not isinstance(name, str) or not isinstance(symbol, str):
            return None
        if name in names or symbol in symbols:
            return None
        if order is not None and not isinstance(order, int):
            return None

        names.add(name)
        symbols.add(symbol)
        items.append({"name": name, "symbol": symbol, "order": order, "_index": idx})

    items.sort(
        key=lambda item: (
            item["order"] is None,
            item["order"] if item["order"] is not None else 0,
            item["_index"],
        )
    )

    return [
        {"name": item["name"], "symbol": item["symbol"], "order": item["order"]}
        for item in items
    ]


def load_market_instruments() -> List[Dict[str, Any]]:
    if not CONFIG_PATH.exists():
        logging.warning("Market config missing at %s; using defaults.", CONFIG_PATH)
        return DEFAULT_MARKET_INSTRUMENTS.copy()

    try:
        raw = json.loads(CONFIG_PATH.read_text())
    except json.JSONDecodeError as exc:
        logging.warning("Market config invalid JSON (%s); using defaults.", exc)
        return DEFAULT_MARKET_INSTRUMENTS.copy()

    validated = _validate_instruments(raw)
    if validated is None:
        logging.warning("Market config schema invalid; using defaults.")
        return DEFAULT_MARKET_INSTRUMENTS.copy()

    return validated
