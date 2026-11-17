# -*- coding: utf-8 -*-
"""
Created on Wed Sep  9 21:50:27 2026


NEXUS market-data preprocessor.

Purpose
-------
Converts aligned Dukascopy/JForex bid and ask data into the
canonical market-data format used throughout the NEXUS
framework.

The input dataframe is expected to come from `data_loader.py`
and already contain aligned bid and ask timestamps.

Responsibilities
----------------
- confirm required loader-output columns are present
- make timestamps explicitly timezone-aware in UTC
- ensure market-data fields are numeric
- sort observations chronologically
- preserve bid and ask OHLCV data separately
- calculate midpoint OHLC prices
- calculate opening and closing bid/ask spreads
- create generic OHLC aliases for indicators and strategies
- return the canonical NEXUS market dataframe

Does not
--------
- load files from disk
- repair missing market data
- interpolate missing bars
- calculate technical indicators
- generate strategy signals
- convert timestamps into trading-session timezones
- execute trades
- contain strategy-specific logic

How to use
----------
1. Load aligned bid and ask data using `data_loader.py`.
2. Pass the resulting dataframe to
   `preprocess_price_data`.
3. Pass the canonical dataframe to
   `data_validation.py`.
4. Strategies and indicators can use the generic
   open/high/low/close aliases.
5. The execution engine can use the original bid and ask
   price fields for realistic trade execution.

Canonical price convention
--------------------------
Bid market data:
    bid_open
    bid_high
    bid_low
    bid_close
    bid_volume

Ask market data:
    ask_open
    ask_high
    ask_low
    ask_close
    ask_volume

Midpoint prices:
    mid_open
    mid_high
    mid_low
    mid_close

Strategy / indicator aliases:
    open  = mid_open
    high  = mid_high
    low   = mid_low
    close = mid_close

Spread:
    spread_open  = ask_open - bid_open
    spread_close = ask_close - bid_close

Notes
-----
JForex source timestamps are expected to represent UTC.

The canonical `timestamp` field is stored as a timezone-aware
UTC datetime. This allows later conversion to trading-session
timezones such as Europe/London while correctly handling
daylight-saving changes.

Midpoint OHLC values are arithmetic means of the corresponding
bid and ask OHLC values. In particular, midpoint high and low
are bar-level approximations because the bid and ask extrema
within a bar are not guaranteed to have occurred at exactly
the same instant.

Spread values are stored as raw price differences rather than
pips. Pip conversion should be handled elsewhere using
instrument-specific metadata.

The preprocessor is timeframe-independent.
"""



import pandas as pd


# ============================================================
# REQUIRED INPUT COLUMNS
# ============================================================

REQUIRED_COLUMNS = [
    "timestamp",

    "bid_open",
    "bid_high",
    "bid_low",
    "bid_close",
    "bid_volume",

    "ask_open",
    "ask_high",
    "ask_low",
    "ask_close",
    "ask_volume",
]


# ============================================================
# PREPROCESS PRICE DATA
# ============================================================

def preprocess_price_data(
    df: pd.DataFrame
) -> pd.DataFrame:
    """
    Convert aligned JForex bid/ask data into the canonical
    NEXUS market-data format.

    Parameters
    ----------
    df : pd.DataFrame
        Combined bid/ask dataframe returned by
        `load_price_data`.

    Returns
    -------
    pd.DataFrame
        Canonical NEXUS market-data dataframe.

    Raises
    ------
    ValueError
        If required columns are missing or market-data fields
        cannot be converted to numeric values.
    """

    # Work on a copy so the loader output remains untouched
    df = df.copy()

    # ---------------------------------------------------------
    # 1. Confirm required columns are present
    # ---------------------------------------------------------

    missing_columns = [
        column
        for column in REQUIRED_COLUMNS
        if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            "Preprocessor missing required columns: "
            f"{missing_columns}"
        )

    # ---------------------------------------------------------
    # 2. Convert timestamp to datetime
    # ---------------------------------------------------------

    df["timestamp"] = pd.to_datetime(
        df["timestamp"],
        errors="raise"
    )

    # ---------------------------------------------------------
    # 3. Make timestamp explicitly UTC-aware
    # ---------------------------------------------------------

    if df["timestamp"].dt.tz is None:

        df["timestamp"] = (
            df["timestamp"]
            .dt.tz_localize("UTC")
        )

    else:

        df["timestamp"] = (
            df["timestamp"]
            .dt.tz_convert("UTC")
        )

    # ---------------------------------------------------------
    # 4. Ensure market-data fields are numeric
    # ---------------------------------------------------------

    numeric_columns = [
        "bid_open",
        "bid_high",
        "bid_low",
        "bid_close",
        "bid_volume",

        "ask_open",
        "ask_high",
        "ask_low",
        "ask_close",
        "ask_volume",
    ]

    for column in numeric_columns:

        df[column] = pd.to_numeric(
            df[column],
            errors="raise"
        )

    # ---------------------------------------------------------
    # 5. Sort chronologically
    # ---------------------------------------------------------

    df = (
        df
        .sort_values("timestamp")
        .reset_index(drop=True)
    )

    # ---------------------------------------------------------
    # 6. Calculate midpoint OHLC
    # ---------------------------------------------------------

    df["mid_open"] = (
        df["bid_open"] + df["ask_open"]
    ) / 2.0

    df["mid_high"] = (
        df["bid_high"] + df["ask_high"]
    ) / 2.0

    df["mid_low"] = (
        df["bid_low"] + df["ask_low"]
    ) / 2.0

    df["mid_close"] = (
        df["bid_close"] + df["ask_close"]
    ) / 2.0

   

    # ---------------------------------------------------------
    # 7. Calculate spread
    # ---------------------------------------------------------

    df["spread_open"] = (
        df["ask_open"] - df["bid_open"]
    )

    df["spread_close"] = (
        df["ask_close"] - df["bid_close"]
    )

    # ---------------------------------------------------------
    # 8. Arrange canonical column order
    # ---------------------------------------------------------

    column_order = [
    "timestamp",

    "bid_open",
    "bid_high",
    "bid_low",
    "bid_close",
    "bid_volume",

    "ask_open",
    "ask_high",
    "ask_low",
    "ask_close",
    "ask_volume",

    "mid_open",
    "mid_high",
    "mid_low",
    "mid_close",

    "spread_open",
    "spread_close",
    ]

    df = df[
        column_order
    ].copy()

    return df