from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

from market_config import (
    MARKET_CONFIG_PATH,
    MarketInstrumentConfig,
    load_market_instruments,
    market_display_order,
)


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


def pct_background(value: float, max_abs: float = 5.0) -> str:
    if pd.isna(value):
        return ""
    clipped = max(min(value, max_abs), -max_abs)
    intensity = abs(clipped) / max_abs
    base = "0, 153, 51" if value > 0 else "204, 0, 0"
    alpha = 0.15 + 0.55 * intensity
    return f"background-color: rgba({base}, {alpha}); color: #0f1115;"


def style_changes(df: pd.DataFrame) -> pd.io.formats.style.Styler:
    change_cols = [
        col
        for col in ["change_1d_pct", "change_5d_pct", "change_20d_pct"]
        if col in df.columns
    ]
    styler = df.style.format(
        {col: "{:+.2f}%" for col in change_cols},
        na_rep="n/a",
    )
    return styler.applymap(pct_background, subset=change_cols)


def rerun() -> None:
    """Compatibility wrapper for Streamlit rerun across versions."""
    if hasattr(st, "experimental_rerun"):
        st.experimental_rerun()
    else:  # Streamlit >=1.30+
        st.rerun()


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


def _serialize_instruments(
    instruments: List[MarketInstrumentConfig],
) -> List[Dict[str, Any]]:
    return [
        {
            "name": instrument.name,
            "symbol": instrument.symbol,
            "order": instrument.order,
            "favorite": instrument.favorite,
        }
        for instrument in instruments
    ]


def save_market_instruments(instruments: List[MarketInstrumentConfig]) -> None:
    MARKET_CONFIG_PATH.write_text(
        json.dumps(_serialize_instruments(instruments), indent=2)
    )


def render_instrument_admin() -> None:
    st.subheader("Manage Instruments")
    instruments = load_market_instruments()
    if not instruments:
        st.info("No instruments configured.")
        return

    df = pd.DataFrame(_serialize_instruments(instruments))
    st.markdown("**Current instruments** (edit favorites/order inline)")
    edited_df = st.data_editor(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "favorite": st.column_config.CheckboxColumn(
                "Favorite", help="Pinned to top metrics strip", default=False
            ),
            "order": st.column_config.NumberColumn(
                "Order", help="Optional integer for display ordering"
            ),
        },
        disabled=["name", "symbol"],
    )
    if st.button("Save table changes"):
        errors: List[str] = []
        updated: List[MarketInstrumentConfig] = []
        for row in edited_df.to_dict("records"):
            order_val = row.get("order")
            if order_val is not None:
                if isinstance(order_val, float) and order_val.is_integer():
                    order_val = int(order_val)
                elif not isinstance(order_val, int):
                    errors.append(f"Order for {row.get('name')} must be integer.")
            updated.append(
                MarketInstrumentConfig(
                    name=row["name"],
                    symbol=row["symbol"],
                    order=order_val,
                    favorite=bool(row.get("favorite", False)),
                )
            )
        if errors:
            for msg in errors:
                st.error(msg)
        else:
            save_market_instruments(updated)
            st.success("Saved table changes. Rerunning to refresh view.")
            rerun()

    st.caption(
        "Add or remove instruments. After changes, rerun `python update_market.py` to refresh data."
    )

    with st.form("add_instrument"):
        st.markdown("**Add instrument**")
        name = st.text_input("Name").strip()
        symbol = st.text_input("Symbol").strip()
        order_raw = st.text_input("Order (optional, int)").strip()
        favorite = st.checkbox("Favorite (pin to metrics)", value=False)

        add_submitted = st.form_submit_button("Add")
        if add_submitted:
            errors: List[str] = []
            existing_names = {i.name for i in instruments}
            existing_symbols = {i.symbol for i in instruments}

            if not name:
                errors.append("Name is required.")
            if not symbol:
                errors.append("Symbol is required.")
            if name in existing_names:
                errors.append(f"Name '{name}' already exists.")
            if symbol in existing_symbols:
                errors.append(f"Symbol '{symbol}' already exists.")

            order_val: Optional[int] = None
            if order_raw:
                try:
                    order_val = int(order_raw)
                except ValueError:
                    errors.append("Order must be an integer.")

            if errors:
                for msg in errors:
                    st.error(msg)
            else:
                instruments.append(
                    MarketInstrumentConfig(
                        name=name,
                        symbol=symbol,
                        order=order_val,
                        favorite=favorite,
                    )
                )
                save_market_instruments(instruments)
                st.success(f"Added {name}. Rerunning to refresh view.")
                rerun()

    with st.form("remove_instrument"):
        st.markdown("**Remove instrument**")
        name_options = [inst.name for inst in instruments]
        selected_name = st.selectbox("Select instrument", name_options)
        remove_submitted = st.form_submit_button("Remove")
        if remove_submitted:
            updated = [inst for inst in instruments if inst.name != selected_name]
            save_market_instruments(updated)
            st.success(f"Removed {selected_name}. Rerunning to refresh view.")
            rerun()


def render_metrics(df: pd.DataFrame, metric_names: List[str]) -> None:
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

    favorites = [inst.name for inst in instruments if inst.favorite]
    metric_names = favorites if favorites else display_order[:3]
    metric_names = [name for name in metric_names if name in set(df["name"])]
    render_metrics(df, metric_names)

    if "history" in df.columns:
        trend_cols = ["name", "price", "change_1d_pct", "history"]
        st.markdown("**Trends**")
        trend_df = df[trend_cols]
        trend_styler = trend_df.style.format(
            {"price": "{:,.2f}", "change_1d_pct": "{:+.2f}%"},
            na_rep="n/a",
        ).applymap(pct_background, subset=["change_1d_pct"])
        st.dataframe(
            trend_styler,
            use_container_width=True,
            hide_index=True,
            column_config={
                "price": st.column_config.NumberColumn("Price", format="%.2f"),
                "change_1d_pct": st.column_config.NumberColumn("1D %", format="%+.2f"),
                "history": st.column_config.LineChartColumn(
                    "Trend (last ~90d)",
                    y_min=None,
                    y_max=None,
                ),
            },
        )

    change_cols = [
        "name",
        "change_1d_pct",
        "change_5d_pct",
        "change_20d_pct",
    ]
    existing_change_cols = [col for col in change_cols if col in df.columns]
    if existing_change_cols:
        st.markdown("**Change heatmap**")
        st.dataframe(
            style_changes(df[existing_change_cols]),
            use_container_width=True,
            hide_index=True,
        )
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
    st.markdown("**Raw data**")
    st.dataframe(df[existing_cols], use_container_width=True, hide_index=True)
    with st.expander("Edit instruments", expanded=False):
        render_instrument_admin()


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
