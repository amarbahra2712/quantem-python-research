# -*- coding: utf-8 -*-
"""
Created on Thu Sep 10 15:01:25 2026

NEXUS signal-generation template.

Purpose
-------
Generates long, short and final entry signals for a strategy.

How to use
----------
1. Update `required_columns` for any indicators or fields needed
   by the new strategy.
2. Replace the placeholder `long_signal` and `short_signal`
   conditions with the strategy rules.
3. Leave the final `entry_signal` mapping unchanged unless the
   engine interface itself is intentionally being changed.

Output convention
-----------------
 1 = long
-1 = short
 0 = no trade


@author: quant
"""

import pandas as pd

from config import StrategyConfig


def generate_signals(
    df: pd.DataFrame,
    config: StrategyConfig
) -> pd.DataFrame:
    """
    Generate entry signals for the strategy.

    The function assumes that any required indicators have
    already been calculated and added to the dataframe.

    Returns
    -------
    pd.DataFrame
        Copy of dataframe with:

        long_signal
        short_signal
        entry_signal

         1 = long
        -1 = short
         0 = no trade
    """

    df = df.copy()

    # ---------------------------------------------------------
    # Required columns
    # ---------------------------------------------------------
    required_columns = [
        "mid_open",
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
            f"Signal generation missing columns: "
            f"{missing_columns}"
        )

    # ---------------------------------------------------------
    # Strategy conditions
    # ---------------------------------------------------------
    #
    # Replace these placeholder conditions when creating
    # a new strategy.
    #

    df["long_signal"] = False
    df["short_signal"] = False

    # ---------------------------------------------------------
    # Final entry signal
    # ---------------------------------------------------------

    df["entry_signal"] = 0

    df.loc[
        df["long_signal"],
        "entry_signal"
    ] = 1

    df.loc[
        df["short_signal"],
        "entry_signal"
    ] = -1

    return df