# -*- coding: utf-8 -*-
"""
Created on Tue Sep 15 14:31:21 2026

@author: quant
"""

"""
NEXUS exponential moving average indicator.

Purpose
-------
Calculates an exponential moving average using midpoint close
prices.

Responsibilities
----------------
- calculate EMA values
- add the EMA as a new dataframe column
- provide a reusable generic indicator for strategies

Does not
--------
- generate trading signals
- decide trade direction
- apply trend filters
- calculate stops or targets
- size positions
- execute trades

How to use
----------
Call `add_ema()` with:

- a prepared NEXUS dataframe
- the EMA period
- an optional output column name

Example:

    df = add_ema(
        df=df,
        period=20,
        column_name="ema_20"
    )

Notes
-----
NEXUS strategy analysis uses midpoint prices.

The EMA is therefore calculated from:

    mid_close

The function does not modify the input dataframe in place.
"""

import pandas as pd


def add_ema(
    df: pd.DataFrame,
    period: int,
    column_name: str = None,
) -> pd.DataFrame:
    """
    Add an exponential moving average to the dataframe.

    Parameters
    ----------
    df : pd.DataFrame
        Prepared NEXUS market data.

    period : int
        EMA lookback period.

    column_name : str, optional
        Name of the output column.

        If omitted, the default format is:

            ema_<period>

        Example:

            period=20 -> ema_20

    Returns
    -------
    pd.DataFrame
        Copy of the input dataframe with the EMA column added.
    """

    if "mid_close" not in df.columns:
        raise ValueError(
            "Required column missing: mid_close"
        )

    if period <= 0:
        raise ValueError(
            "EMA period must be greater than zero."
        )

    if column_name is None:
        column_name = f"ema_{period}"

    df = df.copy()

    df[column_name] = (
        df["mid_close"]
        .ewm(
            span=period,
            adjust=False,
        )
        .mean()
    )

    return df