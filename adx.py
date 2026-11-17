# -*- coding: utf-8 -*-
"""
Created on Thu Sep 10 13:55:01 2026

ADX calculation - (also includes +DI and -DI)

@author: quant
"""

# indicators/adx.py

import pandas as pd


def calculate_adx(
    df: pd.DataFrame,
    period: int
) -> pd.DataFrame:
    """
    Calculate ADX, +DI and -DI using Wilder's smoothing.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame containing:
        high, low, close

    period : int
        ADX lookback period.

    Returns
    -------
    pd.DataFrame
        DataFrame containing:
        adx
        plus_di
        minus_di
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
            f"ADX calculation missing columns: {missing_columns}"
        )

    if period <= 0:
        raise ValueError(
            "ADX period must be greater than zero."
        )

    # ---------------------------------------------------------
    # 1. Price movement
    # ---------------------------------------------------------
    up_move = df["mid_high"].diff()

    down_move = -df["mid_low"].diff()

    plus_dm = up_move.where(
        (up_move > down_move) &
        (up_move > 0),
        0.0
    )

    minus_dm = down_move.where(
        (down_move > up_move) &
        (down_move > 0),
        0.0
    )

    # ---------------------------------------------------------
    # 2. True Range
    # ---------------------------------------------------------
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

    # ---------------------------------------------------------
    # 3. Wilder smoothing
    # ---------------------------------------------------------
    alpha = 1 / period

    smoothed_tr = true_range.ewm(
        alpha=alpha,
        adjust=False,
        min_periods=period
    ).mean()

    smoothed_plus_dm = plus_dm.ewm(
        alpha=alpha,
        adjust=False,
        min_periods=period
    ).mean()

    smoothed_minus_dm = minus_dm.ewm(
        alpha=alpha,
        adjust=False,
        min_periods=period
    ).mean()

    # ---------------------------------------------------------
    # 4. Directional indicators
    # ---------------------------------------------------------
    plus_di = (
        100 * smoothed_plus_dm / smoothed_tr
    )

    minus_di = (
        100 * smoothed_minus_dm / smoothed_tr
    )

    # ---------------------------------------------------------
    # 5. Directional Index
    # ---------------------------------------------------------
    di_sum = plus_di + minus_di

    dx = (
        100 *
        (plus_di - minus_di).abs() /
        di_sum
    )

    # Avoid division by zero
    dx = dx.where(di_sum != 0)

    # ---------------------------------------------------------
    # 6. Average Directional Index
    # ---------------------------------------------------------
    adx = dx.ewm(
        alpha=alpha,
        adjust=False,
        min_periods=period
    ).mean()

    return pd.DataFrame(
        {
            "adx": adx,
            "plus_di": plus_di,
            "minus_di": minus_di,
        },
        index=df.index
    )


def add_adx(
    df: pd.DataFrame,
    period: int
) -> pd.DataFrame:
    """
    Add ADX, +DI and -DI columns to a copy
    of the dataframe.
    """

    df = df.copy()

    adx_data = calculate_adx(
        df=df,
        period=period
    )

    df["adx"] = adx_data["adx"]
    df["plus_di"] = adx_data["plus_di"]
    df["minus_di"] = adx_data["minus_di"]

    return df