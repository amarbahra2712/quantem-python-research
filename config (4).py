# -*- coding: utf-8 -*-
"""
Created on Wed Sep  9 20:39:33 2026




NEXUS base strategy configuration.

Purpose
-------
Provides a fully working reference strategy configuration
for the NEXUS framework.

The current reference strategy uses an EMA crossover with an
EMA trend filter and ATR-based stop distance.

This strategy exists primarily to test the complete NEXUS
pipeline and provide a starting template for future strategies.

Responsibilities
----------------
- define indicator periods
- define strategy-specific stop geometry
- define strategy-specific reward-to-risk target

Does not
--------
- define instrument characteristics
- define account risk
- define execution assumptions
- size positions
- execute trades
- manage account equity
- contain prop-firm rules

How to use
----------
1. Use this configuration with the NEXUS base strategy.
2. Adjust parameters when testing the reference strategy.
3. When creating a new strategy, copy the `nexus_base`
   strategy folder and replace parameters that are specific
   to the new strategy.

Notes
-----
The EMA crossover rules used here are intentionally simple.

They are designed to provide a clear, causal test strategy
for validating the NEXUS framework rather than to represent
a final production trading strategy.
"""

from dataclasses import dataclass


@dataclass
class StrategyConfig:
    """
    Parameters defining the NEXUS reference strategy.
    """

    # ---------------------------------------------------------
    # EMA periods
    # ---------------------------------------------------------

    ema_fast_period: int = 20
    ema_slow_period: int = 50
    ema_filter_period: int = 200

    # ---------------------------------------------------------
    # ATR
    # ---------------------------------------------------------

    atr_period: int = 14

    # ---------------------------------------------------------
    # Exit geometry
    # ---------------------------------------------------------

    stop_atr_multiple: float = 1.5
    reward_r: float = 2.0