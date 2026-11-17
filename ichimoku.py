# -*- coding: utf-8 -*-
"""
Created on Thu Sep 10 14:28:50 2026

Standard Ichimoku calculations: 
Tenkan-sen
Kijun-sen
Senkou Span A
Senkou Span B
Chikou Span

@author: quant
"""

# indicators/ichimoku.py

import pandas as pd


def calculate_ichimoku(
    df: pd.DataFrame,
    tenkan_period: int,
    kijun_period: int,
    senkou_period: int
) -> pd.DataFrame:
    """
    Calculate Ichimoku indicator components.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame containing:
        high, low, close

    tenkan_period : int
        Tenkan-sen lookback period.

    kijun_period : int
        Kijun-sen lookback period.
        Also used as the standard displacement.

    senkou_period : int
        Senkou Span B lookback period.

    Returns
    -------
    pd.DataFrame
        DataFrame containing:
        tenkan
        kijun
        senkou_a
        senkou_b
        chikou
    """

    required_columns = [
        "high",
        "low",
        "close",
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Ichimoku calculation missing columns: "
            f"{missing_columns}"
        )

    if (
        tenkan_period <= 0
        or kijun_period <= 0
        or senkou_period <= 0
    ):
        raise ValueError(
            "Ichimoku periods must be greater than zero."
        )

    # ---------------------------------------------------------
    # 1. Tenkan-sen
    # ---------------------------------------------------------
    tenkan_high = df["high"].rolling(
        window=tenkan_period
    ).max()

    tenkan_low = df["low"].rolling(
        window=tenkan_period
    ).min()

    tenkan = (
        tenkan_high + tenkan_low
    ) / 2

    # ---------------------------------------------------------
    # 2. Kijun-sen
    # ---------------------------------------------------------
    kijun_high = df["high"].rolling(
        window=kijun_period
    ).max()

    kijun_low = df["low"].rolling(
        window=kijun_period
    ).min()

    kijun = (
        kijun_high + kijun_low
    ) / 2

    # ---------------------------------------------------------
    # 3. Senkou Span A
    # ---------------------------------------------------------
    senkou_a_unshifted = (
        tenkan + kijun
    ) / 2

    senkou_a = senkou_a_unshifted.shift(
        kijun_period
    )

    # ---------------------------------------------------------
    # 4. Senkou Span B
    # ---------------------------------------------------------
    senkou_high = df["high"].rolling(
        window=senkou_period
    ).max()

    senkou_low = df["low"].rolling(
        window=senkou_period
    ).min()

    senkou_b_unshifted = (
        senkou_high + senkou_low
    ) / 2

    senkou_b = senkou_b_unshifted.shift(
        kijun_period
    )

    # ---------------------------------------------------------
    # 5. Chikou Span
    # ---------------------------------------------------------
    chikou = df["close"].shift(
        -kijun_period
    )

    return pd.DataFrame(
        {
            "tenkan": tenkan,
            "kijun": kijun,
            "senkou_a": senkou_a,
            "senkou_b": senkou_b,
            "chikou": chikou,
        },
        index=df.index
    )


def add_ichimoku(
    df: pd.DataFrame,
    tenkan_period: int,
    kijun_period: int,
    senkou_period: int
) -> pd.DataFrame:
    """
    Add Ichimoku indicator columns to a copy
    of the dataframe.
    """

    df = df.copy()

    ichimoku = calculate_ichimoku(
        df=df,
        tenkan_period=tenkan_period,
        kijun_period=kijun_period,
        senkou_period=senkou_period
    )

    df["tenkan"] = ichimoku["tenkan"]
    df["kijun"] = ichimoku["kijun"]
    df["senkou_a"] = ichimoku["senkou_a"]
    df["senkou_b"] = ichimoku["senkou_b"]
    df["chikou"] = ichimoku["chikou"]

    return df