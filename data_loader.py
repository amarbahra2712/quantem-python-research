# -*- coding: utf-8 -*-
"""
Created on Wed Sep  9 21:19:23 2026

@author: quant


NEXUS JForex market-data loader.

Purpose
-------
Loads separate Dukascopy/JForex bid and ask CSV files and
combines them into one aligned raw dataframe for downstream
NEXUS processing.

The loader assumes both files represent the same instrument,
timeframe and date range.

Responsibilities
----------------
- load JForex bid CSV data
- load JForex ask CSV data
- strip whitespace from source column names
- standardise source column names
- parse source timestamps
- verify required source columns are present
- detect duplicate bid or ask timestamps
- verify bid and ask row counts match
- verify bid and ask timestamps align exactly
- combine bid and ask OHLCV data into one dataframe
- preserve bid and ask prices and volumes separately
- sort the combined dataframe chronologically

Does not
--------
- convert timestamps between timezones
- calculate midpoint prices
- calculate spreads
- repair missing or irregular market data
- calculate indicators
- generate strategy signals
- execute trades

How to use
----------
1. Export separate Bid and Ask files from Dukascopy/JForex.
2. Configure JForex to export timestamps in UTC.
3. Ensure both files use the same instrument, timeframe and
   date range.
4. Pass both file paths to `load_price_data`.
5. Pass the returned dataframe to
   `data_preprocessor.py`.

Expected JForex columns
-----------------------
Time (UTC)
Open
High
Low
Close
Volume

Notes
-----
JForex may export column names with trailing whitespace, such
as "Volume ". The loader strips this whitespace before
processing.

The bid and ask files must contain identical timestamps.

The loader intentionally preserves bid and ask market data
separately. Midpoint prices, spreads and canonical strategy
price aliases are created later by the data preprocessor.

The loader is timeframe-independent. It can therefore process
1-minute, 5-minute, 15-minute, hourly or other JForex bar
exports without strategy-specific changes.
"""

from pathlib import Path
from typing import Union

import pandas as pd


# ============================================================
# TYPE ALIAS
# ============================================================

PathLike = Union[str, Path]


# ============================================================
# JFOREX COLUMN MAPS
# ============================================================

BID_RENAME_MAP = {
    "Time (UTC)": "timestamp",
    "Open": "bid_open",
    "High": "bid_high",
    "Low": "bid_low",
    "Close": "bid_close",
    "Volume": "bid_volume",
}


ASK_RENAME_MAP = {
    "Time (UTC)": "timestamp",
    "Open": "ask_open",
    "High": "ask_high",
    "Low": "ask_low",
    "Close": "ask_close",
    "Volume": "ask_volume",
}


# ============================================================
# INTERNAL FILE LOADER
# ============================================================

def _load_jforex_file(
    file_path: PathLike,
    rename_map: dict
) -> pd.DataFrame:
    """
    Load and standardise one JForex CSV file.
    """

    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(
            f"Market-data file not found: {file_path}"
        )

    df = pd.read_csv(file_path)

    # Remove accidental whitespace from source headers,
    # for example "Volume ".
    df.columns = [
        column.strip()
        for column in df.columns
    ]

    missing_columns = [
        column
        for column in rename_map
        if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Missing expected JForex columns in "
            f"{file_path.name}: {missing_columns}"
        )

    df = df.rename(
        columns=rename_map
    )

    # Keep only the standard fields expected from JForex.
    df = df[
        list(rename_map.values())
    ].copy()

    df["timestamp"] = pd.to_datetime(
        df["timestamp"],
        errors="raise"
    )

    return df


# ============================================================
# PUBLIC DATA LOADER
# ============================================================

def load_price_data(
    bid_file: PathLike,
    ask_file: PathLike
) -> pd.DataFrame:
    """
    Load and combine separate JForex bid and ask files.

    Parameters
    ----------
    bid_file : str or pathlib.Path
        Path to the JForex bid CSV file.

    ask_file : str or pathlib.Path
        Path to the JForex ask CSV file.

    Returns
    -------
    pd.DataFrame
        Combined bid/ask dataframe with aligned timestamps.

    Raises
    ------
    FileNotFoundError
        If either source file cannot be found.

    ValueError
        If expected columns are missing, row counts differ,
        timestamps contain duplicates, or bid/ask timestamps
        do not align exactly.
    """

    # ---------------------------------------------------------
    # 1. Load source files
    # ---------------------------------------------------------

    bid_df = _load_jforex_file(
        file_path=bid_file,
        rename_map=BID_RENAME_MAP
    )

    ask_df = _load_jforex_file(
        file_path=ask_file,
        rename_map=ASK_RENAME_MAP
    )

    # ---------------------------------------------------------
    # 2. Check duplicate timestamps
    # ---------------------------------------------------------

    if bid_df["timestamp"].duplicated().any():
        raise ValueError(
            "Duplicate timestamps found in JForex bid data."
        )

    if ask_df["timestamp"].duplicated().any():
        raise ValueError(
            "Duplicate timestamps found in JForex ask data."
        )

    # ---------------------------------------------------------
    # 3. Check row counts
    # ---------------------------------------------------------

    if len(bid_df) != len(ask_df):
        raise ValueError(
            "Bid and ask files contain different numbers "
            f"of rows: bid={len(bid_df):,}, "
            f"ask={len(ask_df):,}"
        )

    # ---------------------------------------------------------
    # 4. Check timestamp alignment
    # ---------------------------------------------------------

    if not bid_df["timestamp"].equals(
        ask_df["timestamp"]
    ):
        raise ValueError(
            "Bid and ask timestamps do not align exactly."
        )

    # ---------------------------------------------------------
    # 5. Combine bid and ask data
    # ---------------------------------------------------------

    df = pd.concat(
        [
            bid_df,
            ask_df.drop(columns=["timestamp"])
        ],
        axis=1
    )

    # ---------------------------------------------------------
    # 6. Sort chronologically
    # ---------------------------------------------------------

    df = (
        df
        .sort_values("timestamp")
        .reset_index(drop=True)
    )

    return df