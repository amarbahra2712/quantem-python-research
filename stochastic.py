# -*- coding: utf-8 -*-
"""
Created on Thu Sep 10 14:07:50 2026

This is calculating a Stochastic Price Oscillator as opposed to StochRSI
for details on the different methods see:
Users\quant\OneDrive\Documents\Quantem Capital\Algo Project\My Custom Stochastic vs StochRSI.doc

@author: quant
"""

# indicators/stochastic.py

import pandas as pd


def calculate_stochastic(
    df: pd.DataFrame,
    k_period: int,
    smooth_k: int,
    d_period: int
) -> pd.DataFrame:
    """
    Calculate the standard price Stochastic Oscillator.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame containing:
        high, low, close

    k_period : int
        Lookback period used to calculate Fast %K.

    smooth_k : int
        SMA smoothing period applied to Fast %K.

    d_period : int
        SMA smoothing period applied to Slow %K
        to calculate %D.

    Returns
    -------
    pd.DataFrame
        DataFrame containing:
        fast_k
        slow_k
        stoch_d
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
            f"Stochastic calculation missing columns: "
            f"{missing_columns}"
        )

    if (
        k_period <= 0
        or smooth_k <= 0
        or d_period <= 0
    ):
        raise ValueError(
            "Stochastic periods must be greater than zero."
        )

    # ---------------------------------------------------------
    # 1. Rolling price range
    # ---------------------------------------------------------
    rolling_low = df["low"].rolling(
        window=k_period
    ).min()

    rolling_high = df["high"].rolling(
        window=k_period
    ).max()

    price_range = rolling_high - rolling_low

    # ---------------------------------------------------------
    # 2. Fast %K
    # ---------------------------------------------------------
    fast_k = (
        100
        * (df["close"] - rolling_low)
        / price_range
    )

    # Avoid division by zero when high == low
    fast_k = fast_k.where(
        price_range != 0
    )

    # ---------------------------------------------------------
    # 3. Slow %K
    # ---------------------------------------------------------
    slow_k = fast_k.rolling(
        window=smooth_k
    ).mean()

    # ---------------------------------------------------------
    # 4. %D
    # ---------------------------------------------------------
    stoch_d = slow_k.rolling(
        window=d_period
    ).mean()

    return pd.DataFrame(
        {
            "stoch_fast_k": fast_k,
            "stoch_k": slow_k,
            "stoch_d": stoch_d,
        },
        index=df.index
    )


def add_stochastic(
    df: pd.DataFrame,
    k_period: int,
    smooth_k: int,
    d_period: int
) -> pd.DataFrame:
    """
    Add Stochastic Oscillator columns to a copy
    of the dataframe.
    """

    df = df.copy()

    stochastic = calculate_stochastic(
        df=df,
        k_period=k_period,
        smooth_k=smooth_k,
        d_period=d_period
    )

    df["stoch_fast_k"] = stochastic["stoch_fast_k"]
    df["stoch_k"] = stochastic["stoch_k"]
    df["stoch_d"] = stochastic["stoch_d"]

    return df