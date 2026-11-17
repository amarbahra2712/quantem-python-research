# -*- coding: utf-8 -*-
"""
Created on Thu Sep 10 14:51:46 2026


NEXUS account configuration.

Purpose
-------
Stores account-level settings used by the NEXUS backtesting
and risk-management framework.

These settings describe the trading account rather than the
strategy or execution-cost model.

Responsibilities
----------------
- define starting account balance
- define risk per trade
- define whether margin constrains position sizing
- define broker margin parameters

Does not
--------
- define strategy rules
- calculate indicators
- generate signals
- determine stop or target placement
- define spread, commission, swap or slippage
- execute trades
- apply prop-firm evaluation rules

How to use
----------
1. Set `starting_balance` to the account size being tested.
2. Set `risk_per_trade` as a decimal fraction of capital.
3. Set `use_margin_limit=True` when broker margin should
   constrain position sizing.
4. Set `use_margin_limit=False` when margin should not be used
   as the position-sizing constraint.
5. Set margin parameters only where applicable.
"""

from dataclasses import dataclass


@dataclass
class AccountConfig:
    """
    Generic NEXUS account and risk settings.
    """

    account_currency: str = "USD"

    starting_balance: float = 30000.0
    risk_per_trade: float = 0.02

    use_margin_limit: bool = True
    margin_requirement: float = 0.0334
    max_margin_fraction: float = 0.90