# -*- coding: utf-8 -*-
"""
Created on Thu Sep 10 15:33:10 2026

@author: quant
"""

# strategies/ichimoku_v1/strategy.py

import pandas as pd

from config import StrategyConfig
from signals import generate_signals

from atr import add_atr
from adx import add_adx
from stochastic import add_stochastic
from ichimoku import add_ichimoku
from momentum import add_momentum

class Strategy:
    """
    Recovered Ichimoku strategy.

    Responsibilities:
    - calculate required indicators
    - generate strategy signals

    Does NOT:
    - size positions
    - execute trades
    - manage account equity
    - apply FTMO rules
    """

    def __init__(self, config: StrategyConfig):
        self.config = config

    def prepare_data(self, df: pd.DataFrame) -> pd.DataFrame:
        
        
        """
        Add all indicators required by this strategy.
        """

        df = df.copy()

        # -----------------------------------------------------
        # ATR
        # -----------------------------------------------------
        df = add_atr(
            df=df,
            period=self.config.atr_period
        )

        # -----------------------------------------------------
        # ADX
        # -----------------------------------------------------
        df = add_adx(
            df=df,
            period=self.config.adx_period
        )

        # -----------------------------------------------------
        # Stochastic
        # -----------------------------------------------------
        df = add_stochastic(
            df=df,
            k_period=self.config.stoch_k_period,
            smooth_k=self.config.stoch_smooth_k,
            d_period=self.config.stoch_d_period
        )

        # -----------------------------------------------------
        # Ichimoku
        # -----------------------------------------------------
        df = add_ichimoku(
            df=df,
            tenkan_period=self.config.tenkan_period,
            kijun_period=self.config.kijun_period,
            senkou_period=self.config.senkou_period
        )
        
        # -----------------------------------------------------
        # Momentum
        # -----------------------------------------------------
        df = add_momentum(
        df=df,
        period=self.config.momentum_period
        )

        return df

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        
        
        """
        Generate entry signals using prepared indicator data.
        """

        return generate_signals(
            df=df,
            config=self.config
        )

    def run(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Prepare indicators and generate signals.
        """

        df = self.prepare_data(df)

        df = self.generate_signals(df)

        return df