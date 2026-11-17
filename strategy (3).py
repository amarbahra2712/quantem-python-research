# -*- coding: utf-8 -*-
"""
Created on Thu Sep 10 15:33:10 2026


NEXUS base strategy orchestration module.

Purpose
-------
Coordinates indicator calculation and signal generation for
the NEXUS reference strategy.

The current reference strategy uses:

- fast EMA
- slow EMA
- trend-filter EMA
- ATR

The strategy exists primarily to validate the complete NEXUS
pipeline and provide a reusable starting point for future
strategies.

Responsibilities
----------------
- prepare strategy data
- calculate required indicators
- call signal generation

Does not
--------
- size positions
- execute trades
- manage account equity
- apply execution costs
- apply prop-firm rules

How to use
----------
1. Configure indicator periods in `config.py`.
2. Add or remove generic indicators in `prepare_data`.
3. Keep entry and trade-instruction logic in `signals.py`.
4. Keep execution and position management inside the NEXUS
   engine.

Notes
-----
NEXUS strategy analysis uses midpoint market prices.

Indicator modules therefore operate on the appropriate
`mid_*` price columns.
"""

import pandas as pd

from config import StrategyConfig
from signals import generate_signals

from ema import add_ema
from atr import add_atr


class Strategy:
    """
    NEXUS reference strategy orchestrator.
    """

    def __init__(
        self,
        config: StrategyConfig,
    ):
        self.config = config

    def prepare_data(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Add all indicators required by the reference strategy.
        """

        df = df.copy()

        # -----------------------------------------------------
        # Fast EMA
        # -----------------------------------------------------

        df = add_ema(
            df=df,
            period=self.config.ema_fast_period,
            column_name="ema_fast",
        )

        # -----------------------------------------------------
        # Slow EMA
        # -----------------------------------------------------

        df = add_ema(
            df=df,
            period=self.config.ema_slow_period,
            column_name="ema_slow",
        )

        # -----------------------------------------------------
        # Trend-filter EMA
        # -----------------------------------------------------

        df = add_ema(
            df=df,
            period=self.config.ema_filter_period,
            column_name="ema_filter",
        )

        # -----------------------------------------------------
        # ATR
        # -----------------------------------------------------

        df = add_atr(
            df=df,
            period=self.config.atr_period,
        )

        return df

    def generate_signals(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Generate strategy signals and trade instructions.
        """

        return generate_signals(
            df=df,
            config=self.config,
        )

    def run(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Prepare indicators and generate strategy signals.
        """

        df = self.prepare_data(df)

        df = self.generate_signals(df)

        return df