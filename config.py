# -*- coding: utf-8 -*-
"""
Created on Wed Sep  9 20:39:33 2026
Config - Strategy 1 - Ichimoku

This contains everything that defines the strategy itself:
indicator settings, entry filters, stop/target logic, risk-per-trade, 
session hours, and compatibility switches that let us reproduce legacy behaviour.
@author: quant
"""

# strategies/ichimoku_v1/config.py

from dataclasses import dataclass


@dataclass
class StrategyConfig:
    """
    Parameters defining the recovered Ichimoku strategy.
    """

    # ---------------------------------------------------------
    # Exit geometry - optimizer sim 10
    # ---------------------------------------------------------
    target_atr: float = 30.0
    stop_atr: float = 5.0
    breakeven_atr: float = 5.0

    # ---------------------------------------------------------
    # Ichimoku
    # ---------------------------------------------------------
    tenkan_period: int = 9
    kijun_period: int = 26
    senkou_period: int = 52

    # ---------------------------------------------------------
    # ADX
    # ---------------------------------------------------------
    adx_period: int = 7
    adx_threshold: float = 25.0

    # ---------------------------------------------------------
    # ATR
    # ---------------------------------------------------------
    atr_period: int = 7

    # ---------------------------------------------------------
    # Stochastic
    # ---------------------------------------------------------
    stoch_k_period: int = 5
    stoch_smooth_k: int = 3
    stoch_d_period: int = 3

    stoch_upper: float = 70.0
    stoch_lower: float = 30.0
    
    # ---------------------------------------------------------
    # Momentum
    # ---------------------------------------------------------
    momentum_period: int = 26
    momentum_atr_threshold: float = 0.0

    # ---------------------------------------------------------
    # Session
    # ---------------------------------------------------------
    session_start_hour: int = 9
    session_end_hour: int = 23

    # ---------------------------------------------------------
    # Strategy-specific compatibility
    # ---------------------------------------------------------
    use_legacy_chikou: bool = True
    use_legacy_session_time: bool = True
    