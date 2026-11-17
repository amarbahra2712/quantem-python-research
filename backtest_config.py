# -*- coding: utf-8 -*-
"""
Created on Wed Sep  9 21:10:16 2026
@author: quant
08_config/backtest_config.py
"""

"""
NEXUS Backtest Configuration
============================

Purpose
-------
Define generic behavioural settings controlling how a NEXUS
historical simulation is run.

Responsibilities
----------------
- Hold backtest-level behavioural switches.
- Configure whether positions may remain open across rollover.
- Provide generic simulation controls shared by strategies.
- Keep backtest mechanics separate from strategy parameters,
  execution costs and prop-firm rules.

Does Not
--------
- Define strategy signals.
- Define provider-specific prop rules.
- Calculate position size.
- Calculate commission or swap.
- Perform trade analysis.
- Produce reports.

Architecture
------------
BacktestConfig controls simulation behaviour.

ExecutionConfig controls transaction-cost and execution
assumptions.

AccountConfig controls account-level settings.

PropFirmConfig controls evaluation rules.

Strategy configuration controls strategy-specific parameters.

Keeping these concerns separate allows the same strategy to be
tested across different accounts, execution environments and
prop-firm programmes without modifying the strategy itself.
"""

from dataclasses import dataclass


@dataclass
class BacktestConfig:
    """
    Generic NEXUS historical simulation settings.
    """

    # ---------------------------------------------------------
    # Entry execution
    # ---------------------------------------------------------
    entry_timing: str = "next_open"

    # ---------------------------------------------------------
    # Same-bar event handling
    # ---------------------------------------------------------
    same_bar_policy: str = "stop_first"

    # ---------------------------------------------------------
    # Position handling
    # ---------------------------------------------------------
    allow_overnight_positions: bool = True
    force_close_at_end: bool = True

    # ---------------------------------------------------------
    # Time handling
    # ---------------------------------------------------------
    market_timezone: str = "Europe/London"