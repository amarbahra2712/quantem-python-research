# -*- coding: utf-8 -*-
"""
Created on Thu Sep 10 15:01:25 2026


NEXUS base strategy signal-generation module.

Purpose
-------
Generates entry signals and trade instructions for the NEXUS
reference strategy.

The current reference strategy uses:

- fast / slow EMA crossover
- trend-filter EMA
- candle-close confirmation
- ATR-based stop distance
- reward-to-risk target

Responsibilities
----------------
- detect causal EMA crossovers
- apply trend-direction filtering
- apply candle-close confirmation
- generate long and short entry signals
- calculate stop distance
- calculate target distance

Does not
--------
- calculate indicators
- size positions
- execute trades
- manage open positions
- move stops
- apply breakeven logic
- manage account equity
- apply prop-firm rules

How to use
----------
This module is called by `strategy.py` after all required
indicators have been calculated.

Expected indicator columns:

    ema_fast
    ema_slow
    ema_filter
    atr

Output columns:

    long_signal
    short_signal
    entry_signal
    stop_distance
    target_distance

Notes
-----
Signals are generated using completed midpoint candles.

A crossover on bar t is detected using bar t and bar t-1.

Execution does not occur inside this module. Under the default
NEXUS backtest configuration, a signal generated on bar t is
executed at the executable open of bar t+1.
"""

import pandas as pd

from config import StrategyConfig


def generate_signals(
    df: pd.DataFrame,
    config: StrategyConfig,
) -> pd.DataFrame:
    """
    Generate EMA crossover signals and trade instructions.

    Parameters
    ----------
    df : pd.DataFrame
        Prepared strategy dataframe containing midpoint prices
        and required indicators.

    config : StrategyConfig
        Strategy-specific parameter configuration.

    Returns
    -------
    pd.DataFrame
        Copy of the dataframe with signal and trade-instruction
        columns added.
    """

    df = df.copy()

    # ---------------------------------------------------------
    # Required columns
    # ---------------------------------------------------------

    required_columns = [
        "mid_close",
        "ema_fast",
        "ema_slow",
        "ema_filter",
        "atr",
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Missing required strategy columns: "
            f"{missing_columns}"
        )

    # ---------------------------------------------------------
    # Previous EMA values
    # ---------------------------------------------------------

    previous_fast = df["ema_fast"].shift(1)
    previous_slow = df["ema_slow"].shift(1)

    # ---------------------------------------------------------
    # Crossover detection
    # ---------------------------------------------------------

    bullish_cross = (
        (previous_fast <= previous_slow)
        & (df["ema_fast"] > df["ema_slow"])
    )

    bearish_cross = (
        (previous_fast >= previous_slow)
        & (df["ema_fast"] < df["ema_slow"])
    )

    # ---------------------------------------------------------
    # Candle-close confirmation
    # ---------------------------------------------------------

    long_close_confirmation = (
        (df["mid_close"] > df["ema_fast"])
        & (df["mid_close"] > df["ema_slow"])
    )

    short_close_confirmation = (
        (df["mid_close"] < df["ema_fast"])
        & (df["mid_close"] < df["ema_slow"])
    )

    # ---------------------------------------------------------
    # EMA 200 trend filter
    # ---------------------------------------------------------

    long_trend_filter = (
        df["mid_close"] > df["ema_filter"]
    )

    short_trend_filter = (
        df["mid_close"] < df["ema_filter"]
    )

    # ---------------------------------------------------------
    # Indicator readiness
    # ---------------------------------------------------------

    #
    # Our EMA implementation begins calculating immediately.
    # For the reference strategy, wait until at least the
    # longest EMA period has elapsed before permitting signals.
    #

    warmup_ready = (
        df["mid_close"]
        .rolling(
            window=config.ema_filter_period,
            min_periods=config.ema_filter_period,
        )
        .count()
        == config.ema_filter_period
    )

    atr_ready = df["atr"].notna()

    # ---------------------------------------------------------
    # Final long / short signals
    # ---------------------------------------------------------

    df["long_signal"] = (
        bullish_cross
        & long_close_confirmation
        & long_trend_filter
        & warmup_ready
        & atr_ready
    )

    df["short_signal"] = (
        bearish_cross
        & short_close_confirmation
        & short_trend_filter
        & warmup_ready
        & atr_ready
    )

    # ---------------------------------------------------------
    # Entry signal
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

    # ---------------------------------------------------------
    # Stop and target instructions
    # ---------------------------------------------------------

    df["stop_distance"] = float("nan")
    df["target_distance"] = float("nan")

    signal_mask = (
        df["entry_signal"] != 0
    )

    df.loc[
        signal_mask,
        "stop_distance"
    ] = (
        df.loc[
            signal_mask,
            "atr"
        ]
        * config.stop_atr_multiple
    )

    df.loc[
        signal_mask,
        "target_distance"
    ] = (
        df.loc[
            signal_mask,
            "stop_distance"
        ]
        * config.reward_r
    )

    return df