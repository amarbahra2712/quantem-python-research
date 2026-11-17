# -*- coding: utf-8 -*-
"""
Created on Thu Sep 10 11:19:29 2026

Standard Wilder-style ATR - calculated from scratch rather than using pandas_ta

@author: quant
"""

# indicators/atr.py

import pandas as pd


def calculate_atr(
    df: pd.DataFrame,
    period: int
) -> pd.Series:
    """
    Calculate Average True Range (ATR) using Wilder's smoothing.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame containing:
        high, low, close

    period : int
        ATR lookback period.

    Returns
    -------
    pd.Series
        ATR values.
    """

    required_columns = [
        "mid_high",
        "mid_low",
        "mid_close",
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"ATR calculation missing columns: {missing_columns}"
        )

    if period <= 0:
        raise ValueError(
            "ATR period must be greater than zero."
        )

    previous_close = df["mid_close"].shift(1)

    high_low = (
        df["mid_high"] - df["mid_low"]
    )

    high_previous_close = (
        df["mid_high"] - previous_close
    ).abs()

    low_previous_close = (
        df["mid_low"] - previous_close
    ).abs()

    true_range = pd.concat(
        [
            high_low,
            high_previous_close,
            low_previous_close,
        ],
        axis=1
    ).max(axis=1)

    atr = true_range.ewm(
        alpha=1 / period,
        adjust=False,
        min_periods=period
    ).mean()

    return atr


def add_atr(
    df: pd.DataFrame,
    period: int,
    column_name: str = "atr"
) -> pd.DataFrame:
    """
    Add ATR to a copy of the dataframe.

    Parameters
    ----------
    df : pd.DataFrame
        Standardized price dataframe.

    period : int
        ATR lookback period.

    column_name : str
        Name of the output ATR column.

    Returns
    -------
    pd.DataFrame
        Copy of dataframe with ATR column added.
    """

    df = df.copy()

    df[column_name] = calculate_atr(
        df=df,
        period=period
    )

    return df