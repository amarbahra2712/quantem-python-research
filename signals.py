# -*- coding: utf-8 -*-
"""
Created on Thu Sep 10 15:01:25 2026

Generates signals for the Ichimoku strategy

note: there is a switch for legacy chikou calc and audited chikou calc
using the 'use_legacy_chikou' Boolean setting
Also same thing for legacy hour (which was based on a crude Moscow time conversion +3/2hrs)

@author: quant
"""

# strategies/ichimoku_v1/signals.py

import pandas as pd

from config import StrategyConfig


def generate_signals(
    df: pd.DataFrame,
    config: StrategyConfig
) -> pd.DataFrame:
    """
    Generate entry signals for the recovered Ichimoku strategy.

    The function assumes that the required indicators have
    already been calculated and added to the dataframe.

    Returns
    -------
    pd.DataFrame
        Copy of dataframe with individual signal/filter columns
        and final entry_signal:

         1 = long
        -1 = short
         0 = no trade
    """

    df = df.copy()

    # ---------------------------------------------------------
    # Required columns
    # ---------------------------------------------------------
    required_columns = [
        "open",
        "high",
        "low",
        "close",
        "hour",
        "tenkan",
        "kijun",
        "senkou_a",
        "senkou_b",
        "chikou",
        "stoch_k",
        "adx",
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

    # =========================================================
    # S1 - SESSION FILTER
    # =========================================================

    if config.use_legacy_session_time:
        session_hour = df["legacy_hour"]
    else:
        session_hour = df["hour"]

    df["s1_session"] = (
        (session_hour >= config.session_start_hour)
        &
        (session_hour < config.session_end_hour)
    )

   # =========================================================
# S2 - ICHIMOKU CLOUD BREAKOUT
# =========================================================

    bullish_cloud = (
    df["senkou_a"] > df["senkou_b"]
    )

    bearish_cloud = (
    df["senkou_a"] < df["senkou_b"]
    )

    df["s2_long"] = (
    bullish_cloud
    & (df["open"] <= df["senkou_a"])
    & (df["close"] > df["senkou_a"])
    )

    df["s2_short"] = (
    bearish_cloud
    & (df["open"] >= df["senkou_a"])
    & (df["close"] < df["senkou_a"])
    )

    # =========================================================
    # S3 - TENKAN / KIJUN CONFIRMATION
    # =========================================================

    df["s3_long"] = (
        df["tenkan"] >= df["kijun"]
    )

    df["s3_short"] = (
        df["tenkan"] <= df["kijun"]
    )

    # =========================================================
    # S4 - CHIKOU CONFIRMATION
    # =========================================================

    if config.use_legacy_chikou:

        # -----------------------------------------------------
        # Legacy behaviour
        #
        # Reproduces the old strategy logic:
        #
        # ICS_26[i] > High[i - 26]
        # ICS_26[i] < Low[i - 26]
        #
        # Because plotted Chikou is created with shift(-26),
        # this may contain future information.
        # -----------------------------------------------------

        historical_high = df["high"].shift(
            config.kijun_period
        )

        historical_low = df["low"].shift(
            config.kijun_period
        )

        df["s4_long"] = (
            df["chikou"] > historical_high
        )

        df["s4_short"] = (
            df["chikou"] < historical_low
        )

    else:

        # -----------------------------------------------------
        # Audited causal behaviour
        #
        # Current close is compared with price 26 bars ago.
        # No future data is used.
        # -----------------------------------------------------

        df["s4_long"] = (
            df["momentum_atr"]
            > config.momentum_atr_threshold
        )

        df["s4_short"] = (
            df["momentum_atr"]
            < -config.momentum_atr_threshold
        )

#        historical_high = df["high"].shift(
#            config.kijun_period
#        )
#
#        historical_low = df["low"].shift(
#            config.kijun_period
#        )
#
#        df["s4_long"] = (
#            df["close"] > historical_high
#        )
#
#        df["s4_short"] = (
#            df["close"] < historical_low
#        )

    # =========================================================
    # S5 - STOCHASTIC FILTER
    # =========================================================

    # Original logic:
    #
    # Long rejected if smoothed %K > 70
    # Short rejected if smoothed %K < 30

    df["s5_long"] = (
        df["stoch_k"] <= config.stoch_upper
    )

    df["s5_short"] = (
        df["stoch_k"] >= config.stoch_lower
    )

    # =========================================================
    # S6 - ADX FILTER
    # =========================================================

    df["s6_adx"] = (
        df["adx"] >= config.adx_threshold
    )

    # =========================================================
    # FINAL LONG / SHORT CONDITIONS
    # =========================================================

    df["long_signal"] = (
        df["s1_session"]
        & df["s2_long"]
        & df["s3_long"]
        & df["s4_long"]
        & df["s5_long"]
        & df["s6_adx"]
    )

    df["short_signal"] = (
        df["s1_session"]
        & df["s2_short"]
        & df["s3_short"]
        & df["s4_short"]
        & df["s5_short"]
        & df["s6_adx"]
    )

    # =========================================================
    # FINAL ENTRY SIGNAL
    # =========================================================

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