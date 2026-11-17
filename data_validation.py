# -*- coding: utf-8 -*-
"""
Created on Wed Sep  9 22:15:22 2026

@author: quant


NEXUS market-data validation module.

Purpose
-------
Checks canonical NEXUS market data for structural and
market-quality issues before the data is used by strategies
or the backtest engine.

The validator inspects the dataframe but does not modify it.

Responsibilities
----------------
- confirm required canonical columns are present
- report dataset size and date range
- confirm timestamps are timezone-aware
- detect duplicate timestamps
- detect out-of-order timestamps
- validate bid OHLC relationships
- validate ask OHLC relationships
- validate midpoint OHLC relationships
- check for non-positive prices
- check bid/ask price relationships
- validate opening and closing spread values
- check bid and ask volume data
- identify weekend bars
- infer the normal bar timeframe from timestamps
- identify gaps larger than the normal bar interval
- return a structured ValidationReport
- provide a readable console validation report

Does not
--------
- load files from disk
- modify or repair market data
- remove duplicate rows
- fill missing bars
- interpolate prices
- calculate indicators
- generate strategy signals
- execute trades
- contain strategy-specific logic

How to use
----------
1. Load data using `data_loader.py`.
2. Process it using `data_preprocessor.py`.
3. Pass the canonical dataframe to
   `validate_price_data`.
4. Inspect the returned `ValidationReport`.
5. Use `print_validation_report` for a readable console
   summary.

Timeframe handling
------------------
By default, the validator infers the normal bar interval from
the timestamp series.

For example:

    1-minute data  -> inferred as 1 minute
    5-minute data  -> inferred as 5 minutes
    15-minute data -> inferred as 15 minutes
    1-hour data    -> inferred as 60 minutes

The most common positive timestamp difference is used so that
normal weekend and market-closure gaps do not distort the
inferred timeframe.

An expected timeframe may also be supplied explicitly when
the caller wants the validator to compare the dataset against
a known bar interval.

Notes
-----
FX datasets naturally contain gaps while the market is closed,
particularly over weekends. A gap larger than the normal bar
interval is therefore reported for inspection rather than
automatically treated as corrupt data.

`timezone_aware = True` confirms that timestamps carry explicit
timezone information. For the current JForex pipeline this
should normally mean timezone-aware UTC timestamps.

The validator is timeframe-independent and can therefore be
used with different JForex bar periods without changing its
core validation logic.
"""


from dataclasses import dataclass, field
from typing import Optional, List

import pandas as pd


# ============================================================
# VALIDATION REPORT
# ============================================================

@dataclass
class ValidationReport:
    """
    Structured summary of market-data validation results.
    """

    rows: int = 0

    start_timestamp: Optional[pd.Timestamp] = None
    end_timestamp: Optional[pd.Timestamp] = None

    inferred_bar_minutes: Optional[int] = None

    timezone_aware: bool = False

    duplicate_timestamps: int = 0
    out_of_order_timestamps: int = 0

    invalid_bid_ohlc_rows: int = 0
    invalid_ask_ohlc_rows: int = 0
    invalid_mid_ohlc_rows: int = 0

    non_positive_price_rows: int = 0

    ask_below_bid_rows: int = 0

    missing_spread_open_rows: int = 0
    missing_spread_close_rows: int = 0

    negative_spread_open_rows: int = 0
    negative_spread_close_rows: int = 0

    zero_spread_open_rows: int = 0
    zero_spread_close_rows: int = 0

    missing_volume_rows: int = 0
    negative_volume_rows: int = 0

    weekend_rows: int = 0

    irregular_gap_count: int = 0
    largest_gap: Optional[pd.Timedelta] = None

    warnings: List[str] = field(
        default_factory=list
    )


# ============================================================
# INTERNAL OHLC CHECK
# ============================================================

def _invalid_ohlc_mask(
    df: pd.DataFrame,
    prefix: str
) -> pd.Series:
    """
    Return a boolean mask identifying invalid OHLC rows
    for the supplied price prefix.
    """

    open_col = f"{prefix}_open"
    high_col = f"{prefix}_high"
    low_col = f"{prefix}_low"
    close_col = f"{prefix}_close"

    return (
        (df[high_col] < df[open_col]) |
        (df[high_col] < df[close_col]) |
        (df[high_col] < df[low_col]) |
        (df[low_col] > df[open_col]) |
        (df[low_col] > df[close_col]) |
        (df[low_col] > df[high_col])
    )


# ============================================================
# MAIN VALIDATION FUNCTION
# ============================================================

def _infer_bar_minutes(
    timestamps: pd.Series
) -> int:
    """
    Infer the normal bar interval from timestamp differences.

    Uses the most common positive time difference so that
    weekend and market-closure gaps do not distort the result.
    """

    timestamp_diff = (
        timestamps
        .sort_values()
        .diff()
        .dropna()
    )

    positive_diff = timestamp_diff[
        timestamp_diff > pd.Timedelta(0)
    ]

    if positive_diff.empty:
        raise ValueError(
            "Unable to infer bar timeframe from timestamps."
        )

    most_common_gap = (
        positive_diff
        .value_counts()
        .idxmax()
    )

    bar_minutes = (
        most_common_gap.total_seconds()
        / 60.0
    )

    if bar_minutes <= 0:
        raise ValueError(
            "Invalid inferred bar timeframe."
        )

    return int(bar_minutes)


def validate_price_data(
    df: pd.DataFrame,
    expected_bar_minutes: Optional[int] = None
) -> ValidationReport:
    """
    Inspect canonical NEXUS market data.

    This function does not alter the dataframe.

    Parameters
    ----------
    df : pd.DataFrame
        Canonical dataframe produced by
        `data_preprocessor.py`.

    expected_bar_minutes : int
        Expected timeframe of the dataset.

    Returns
    -------
    ValidationReport
        Summary of detected market-data issues.

    Raises
    ------
    ValueError
        If the dataframe is empty or required columns
        are missing.
    """

    # ---------------------------------------------------------
    # Required canonical columns
    # ---------------------------------------------------------

    required_columns = [
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

    # ---------------------------------------------------------
    # 1. Basic dataframe checks
    # ---------------------------------------------------------

    if df.empty:
        raise ValueError(
            "Price dataframe is empty."
        )

    missing_columns = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            "Validation cannot continue. "
            f"Missing columns: {missing_columns}"
        )

    report = ValidationReport()
    
    # ---------------------------------------------------------
    # Infer normal bar timeframe
    # ---------------------------------------------------------

    inferred_bar_minutes = _infer_bar_minutes(
        df["timestamp"]
    )
    
    report.inferred_bar_minutes = (
        inferred_bar_minutes
    )
    
    if expected_bar_minutes is None:
    
        expected_bar_minutes = (
            inferred_bar_minutes
        )
    
    elif expected_bar_minutes != inferred_bar_minutes:
    
        report.warnings.append(
            "Expected bar timeframe does not match "
            f"the data. Expected "
            f"{expected_bar_minutes} minutes, "
            f"inferred {inferred_bar_minutes} minutes."
        )

    report.rows = len(df)

    report.start_timestamp = (
        df["timestamp"].min()
    )

    report.end_timestamp = (
        df["timestamp"].max()
    )

    # ---------------------------------------------------------
    # 2. Timezone awareness
    # ---------------------------------------------------------

    report.timezone_aware = (
        df["timestamp"].dt.tz is not None
    )

    if not report.timezone_aware:
        report.warnings.append(
            "Timestamp column is timezone-naive."
        )

    # ---------------------------------------------------------
    # 3. Duplicate timestamps
    # ---------------------------------------------------------

    report.duplicate_timestamps = int(
        df["timestamp"].duplicated().sum()
    )

    if report.duplicate_timestamps > 0:
        report.warnings.append(
            f"{report.duplicate_timestamps} "
            "duplicate timestamps found."
        )

    # ---------------------------------------------------------
    # 4. Timestamp ordering
    # ---------------------------------------------------------

    timestamp_diff = (
        df["timestamp"].diff()
    )

    report.out_of_order_timestamps = int(
        (
            timestamp_diff
            < pd.Timedelta(0)
        ).sum()
    )

    if report.out_of_order_timestamps > 0:
        report.warnings.append(
            f"{report.out_of_order_timestamps} "
            "timestamps are out of order."
        )

    # ---------------------------------------------------------
    # 5. Bid OHLC validation
    # ---------------------------------------------------------

    invalid_bid = _invalid_ohlc_mask(
        df,
        prefix="bid"
    )

    report.invalid_bid_ohlc_rows = int(
        invalid_bid.sum()
    )

    if report.invalid_bid_ohlc_rows > 0:
        report.warnings.append(
            f"{report.invalid_bid_ohlc_rows} "
            "rows have invalid bid OHLC values."
        )

    # ---------------------------------------------------------
    # 6. Ask OHLC validation
    # ---------------------------------------------------------

    invalid_ask = _invalid_ohlc_mask(
        df,
        prefix="ask"
    )

    report.invalid_ask_ohlc_rows = int(
        invalid_ask.sum()
    )

    if report.invalid_ask_ohlc_rows > 0:
        report.warnings.append(
            f"{report.invalid_ask_ohlc_rows} "
            "rows have invalid ask OHLC values."
        )

    # ---------------------------------------------------------
    # 7. Midpoint OHLC validation
    # ---------------------------------------------------------

    invalid_mid = _invalid_ohlc_mask(
        df,
        prefix="mid"
    )

    report.invalid_mid_ohlc_rows = int(
        invalid_mid.sum()
    )

    if report.invalid_mid_ohlc_rows > 0:
        report.warnings.append(
            f"{report.invalid_mid_ohlc_rows} "
            "rows have invalid midpoint OHLC values."
        )

    # ---------------------------------------------------------
    # 8. Non-positive prices
    # ---------------------------------------------------------

    price_columns = [
        "bid_open",
        "bid_high",
        "bid_low",
        "bid_close",

        "ask_open",
        "ask_high",
        "ask_low",
        "ask_close",

        "mid_open",
        "mid_high",
        "mid_low",
        "mid_close",
    ]

    non_positive = (
        df[price_columns] <= 0
    ).any(axis=1)

    report.non_positive_price_rows = int(
        non_positive.sum()
    )

    if report.non_positive_price_rows > 0:
        report.warnings.append(
            f"{report.non_positive_price_rows} "
            "rows contain non-positive prices."
        )

    # ---------------------------------------------------------
    # 9. Bid / ask relationship
    # ---------------------------------------------------------

    ask_below_bid = (
        (df["ask_open"] < df["bid_open"]) |
        (df["ask_high"] < df["bid_high"]) |
        (df["ask_low"] < df["bid_low"]) |
        (df["ask_close"] < df["bid_close"])
    )

    report.ask_below_bid_rows = int(
        ask_below_bid.sum()
    )

    if report.ask_below_bid_rows > 0:
        report.warnings.append(
            f"{report.ask_below_bid_rows} "
            "rows contain ask prices below bid prices."
        )

    # ---------------------------------------------------------
    # 10. Spread checks
    # ---------------------------------------------------------

    report.missing_spread_open_rows = int(
        df["spread_open"].isna().sum()
    )

    report.missing_spread_close_rows = int(
        df["spread_close"].isna().sum()
    )

    report.negative_spread_open_rows = int(
        (df["spread_open"] < 0).sum()
    )

    report.negative_spread_close_rows = int(
        (df["spread_close"] < 0).sum()
    )

    report.zero_spread_open_rows = int(
        (df["spread_open"] == 0).sum()
    )

    report.zero_spread_close_rows = int(
        (df["spread_close"] == 0).sum()
    )

    if report.missing_spread_open_rows > 0:
        report.warnings.append(
            f"{report.missing_spread_open_rows} "
            "rows have missing opening spread."
        )

    if report.missing_spread_close_rows > 0:
        report.warnings.append(
            f"{report.missing_spread_close_rows} "
            "rows have missing closing spread."
        )

    if report.negative_spread_open_rows > 0:
        report.warnings.append(
            f"{report.negative_spread_open_rows} "
            "rows have negative opening spread."
        )

    if report.negative_spread_close_rows > 0:
        report.warnings.append(
            f"{report.negative_spread_close_rows} "
            "rows have negative closing spread."
        )

    if report.zero_spread_open_rows > 0:
        report.warnings.append(
            f"{report.zero_spread_open_rows} "
            "rows have zero opening spread."
        )

    if report.zero_spread_close_rows > 0:
        report.warnings.append(
            f"{report.zero_spread_close_rows} "
            "rows have zero closing spread."
        )

    # ---------------------------------------------------------
    # 11. Volume checks
    # ---------------------------------------------------------

    volume_columns = [
        "bid_volume",
        "ask_volume",
    ]

    report.missing_volume_rows = int(
        df[volume_columns]
        .isna()
        .any(axis=1)
        .sum()
    )

    report.negative_volume_rows = int(
        (
            df[volume_columns] < 0
        )
        .any(axis=1)
        .sum()
    )

    if report.missing_volume_rows > 0:
        report.warnings.append(
            f"{report.missing_volume_rows} "
            "rows have missing volume data."
        )

    if report.negative_volume_rows > 0:
        report.warnings.append(
            f"{report.negative_volume_rows} "
            "rows have negative volume values."
        )

    # ---------------------------------------------------------
    # 12. Weekend bars
    # ---------------------------------------------------------

    weekday_number = (
        df["timestamp"].dt.dayofweek
    )

    weekend_mask = (
        weekday_number >= 5
    )

    report.weekend_rows = int(
        weekend_mask.sum()
    )

    if report.weekend_rows > 0:
        report.warnings.append(
            f"{report.weekend_rows} "
            "weekend bars found."
        )

    # ---------------------------------------------------------
    # 13. Time-gap analysis
    # ---------------------------------------------------------

    expected_gap = pd.Timedelta(
        minutes=expected_bar_minutes
    )

    gaps = timestamp_diff[
        timestamp_diff > expected_gap
    ]

    report.irregular_gap_count = int(
        len(gaps)
    )

    if len(gaps) > 0:

        report.largest_gap = (
            gaps.max()
        )

        report.warnings.append(
            f"{len(gaps)} gaps larger than "
            f"{expected_bar_minutes} minutes found."
        )

    return report


# ============================================================
# CONSOLE REPORT
# ============================================================

def print_validation_report(
    report: ValidationReport
) -> None:
    """
    Print a readable market-data validation summary.
    """

    print(
    f"Bar timeframe:            "
    f"{report.inferred_bar_minutes} minute(s)"
    )

    print("\nDATA VALIDATION REPORT")
    print("-" * 55)

    print(
        f"Rows:                    "
        f"{report.rows:,}"
    )

    print(
        f"Start:                   "
        f"{report.start_timestamp}"
    )

    print(
        f"End:                     "
        f"{report.end_timestamp}"
    )

    print(
        f"Timezone aware:          "
        f"{report.timezone_aware}"
    )

    print()

    print(
        f"Duplicates:               "
        f"{report.duplicate_timestamps}"
    )

    print(
        f"Out of order:             "
        f"{report.out_of_order_timestamps}"
    )

    print()

    print(
        f"Invalid bid OHLC:         "
        f"{report.invalid_bid_ohlc_rows}"
    )

    print(
        f"Invalid ask OHLC:         "
        f"{report.invalid_ask_ohlc_rows}"
    )

    print(
        f"Invalid midpoint OHLC:    "
        f"{report.invalid_mid_ohlc_rows}"
    )

    print(
        f"Non-positive prices:      "
        f"{report.non_positive_price_rows}"
    )

    print(
        f"Ask below bid:            "
        f"{report.ask_below_bid_rows}"
    )

    print()

    print(
        f"Missing spread open:      "
        f"{report.missing_spread_open_rows}"
    )

    print(
        f"Missing spread close:     "
        f"{report.missing_spread_close_rows}"
    )

    print(
        f"Negative spread open:     "
        f"{report.negative_spread_open_rows}"
    )

    print(
        f"Negative spread close:    "
        f"{report.negative_spread_close_rows}"
    )

    print(
        f"Zero spread open:         "
        f"{report.zero_spread_open_rows}"
    )

    print(
        f"Zero spread close:        "
        f"{report.zero_spread_close_rows}"
    )

    print()

    print(
        f"Missing volume rows:      "
        f"{report.missing_volume_rows}"
    )

    print(
        f"Negative volume rows:     "
        f"{report.negative_volume_rows}"
    )

    print()

    print(
        f"Weekend bars:             "
        f"{report.weekend_rows}"
    )

    print(
        f"Large gaps:               "
        f"{report.irregular_gap_count}"
    )

    print(
        f"Largest gap:              "
        f"{report.largest_gap}"
    )

    print()

    if report.warnings:

        print("WARNINGS")

        for warning in report.warnings:
            print(
                f"  - {warning}"
            )

    else:

        print(
            "No validation warnings."
        )

    print("-" * 55)