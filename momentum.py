# -*- coding: utf-8 -*-
"""
Created on Fri Sep 11 21:32:57 2026

@author: quant
"""

# -*- coding: utf-8 -*-


def add_momentum(df, period=26):
    """
    Add causal backward-looking momentum.

    momentum:
        Current close minus close N bars ago.

    momentum_atr:
        Momentum normalised by current ATR.

    Positive = upward displacement.
    Negative = downward displacement.
    """

    df = df.copy()

    df["momentum"] = (
        df["close"] - df["close"].shift(period)
    )

    df["momentum_atr"] = (
        df["momentum"] / df["atr"]
    )

    return df