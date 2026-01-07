from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

from market_config import load_market_instruments, market_display_order


MARKET_FILE = Path("data/market_snapshot.json")
MACRO_FILE = Path("data/macro_releases.json")
EVENTS_FILE = Path("data/events.json")


@st.cache_data
def load_json(path: Path) -> Optional[Any]:
    if not path.exists():
        return None
    with path.open() as f:
        return json.load(f)


def format_price(value: Optional[float]) -> str:
    if value is None:
        return "n/a"
    return f"{value:,.2f}"


def format_pct(value: Optional[float]) -> str:
    if value is None:
        return "n/a"
    return f"{value:+.2f}%"


def load_market_snapshot() -> Optional[Dict[str, Any]]:
    data = load_json(MARKET_FILE)
    if not isinstance(data, dict):
        return None
    return data


def load_rows(path: Path) -> List[Dict[str, Any]]:
    data = load_json(path)
    if isinstance(data, list):
        return data
    return []


def render_metrics(df: pd.DataFrame) -> None:
    metric_names = ["SPX", "10Y", "DXY"]
    cols = st.columns(len(metric_names))
    for col, name in zip(cols, metric_names):
        row = df[df["name"] == name]
        if row.empty:
            col.metric(label=name, value="n/a", delta="n/a")
            continue
        values = row.iloc[0]
        col.metric(
            label=name,
            value=format_price(values.get("price")),
            delta=format_pct(values.get("change_1d_pct")),
        )


def render_market() -> None:
    st.subheader("Market Snapshot")
    snapshot = load_market_snapshot()
    if snapshot is None:
        st.warning("Market snapshot missing. Run `python update_market.py` to refresh.")
        return

    updated_at = snapshot.get("updated_at")
    if updated_at:
        st.caption(f"Updated at (UTC): {updated_at}")

    items = snapshot.get("items") or []
    df = pd.DataFrame(items)
    if df.empty:
        st.info("No market data available.")
        return

    instruments = load_market_instruments()
    display_order = market_display_order(instruments)
    order_map = {name: idx for idx, name in enumerate(display_order)}
    df["order"] = df["name"].map(order_map).fillna(len(order_map))
    df = df.sort_values(["order", "name"]).drop(columns=["order"])

    render_metrics(df)

    display_cols = [
        "name",
        "symbol",
        "price",
        "change_1d_pct",
        "change_5d_pct",
        "change_20d_pct",
        "error",
    ]
    existing_cols = [col for col in display_cols if col in df.columns]
    st.dataframe(df[existing_cols], use_container_width=True)


def render_macro() -> None:
    st.subheader("Macro Releases")
    rows = load_rows(MACRO_FILE)
    if not rows:
        st.info("No macro releases available.")
        return
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True)


def render_events() -> None:
    st.subheader("Breaking Events")
    rows = load_rows(EVENTS_FILE)
    if not rows:
        st.info("No events available.")
        return
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True)


def main() -> None:
    st.set_page_config(page_title="Macro + Market + Events (MVP)", layout="wide")
    st.title("Macro + Market + Events (MVP)")

    render_market()
    st.divider()
    render_macro()
    st.divider()
    render_events()


if __name__ == "__main__":
    main()
