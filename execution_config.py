# -*- coding: utf-8 -*-
"""
Created on Sat Sep 12 09:55:53 2026
@author: quant
08_config/execution_config.py
"""

"""
NEXUS Execution Configuration
=============================

Purpose
-------
Define generic execution and transaction-cost assumptions used
by NexusEngine.

Responsibilities
----------------
- Configure commission inclusion.
- Configure supported commission models.
- Configure commission charging scope.
- Configure standard lot size used by per-lot commission.
- Configure FX swap / rollover behaviour.
- Configure long and short swap rates.
- Configure rollover timezone and rollover time.
- Configure triple-rollover weekday and multiplier.
- Hold execution assumptions shared across strategies.

Does Not
--------
- Generate strategy signals.
- Size positions.
- Define prop-firm rules.
- Select a prop provider.
- Execute trades itself.
- Produce performance statistics.

Commission
----------
Supported V1 commission concepts include:

    none
    per_lot
    percentage_notional

Commission scope may represent:

    per_side
    round_trip

Commission inputs are expressed as positive rates or fees.
NexusEngine converts the calculated charge into negative
account P&L.

Swap / Rollover
---------------
Rollover rules are timezone-aware.

Swap can differ between long and short positions and can use a
configurable triple-rollover weekday and multiplier.

Notes
-----
ExecutionConfig describes market/execution assumptions.

Provider evaluation rules belong to PropFirmConfig even where
a particular provider publishes typical commission values.
"""

from dataclasses import dataclass


@dataclass
class ExecutionConfig:

    # --------------------------------------------------------
    # BID / ASK EXECUTION
    # --------------------------------------------------------

    use_bid_ask: bool = True

    # --------------------------------------------------------
    # SPREAD
    # --------------------------------------------------------

    include_spread: bool = True
    use_data_spread: bool = True

    fixed_spread: float = 0.0

    
    # --------------------------------------------------------
    # COMMISSION
    # --------------------------------------------------------

    include_commission: bool = True

    # Supported models:
    #
    #     "none"
    #     "per_lot"
    #     "percentage_notional"
    #
    # per_lot:
    #     commission_rate is the cash fee per standard lot.
    #
    # percentage_notional:
    #     commission_rate is expressed as a decimal fraction.
    #
    #     Example:
    #         0.0002 = 0.02%
    #
    commission_model: str = "per_lot"

    # Positive number representing the quoted commission fee.
    #
    # The engine converts this into a negative P&L adjustment.
    commission_rate: float = 2.50

    # Supported scopes:
    #
    #     "per_side"
    #     "round_trip"
    #
    # If round_trip is specified, the engine allocates half
    # of the quoted commission to entry and half to exit.
    commission_scope: str = "per_side"

    # Standard FX lot size in base-currency units.
    commission_lot_size: float = 100000.0    

    # --------------------------------------------------------
    # SWAP / ROLLOVER
    # --------------------------------------------------------

    include_swap: bool = True

    # Signed quote-currency amount per base-currency unit
    # per normal rollover event.
    #
    # Negative = financing debit.
    # Positive = financing credit.
    swap_long_per_unit: float = -0.00007
    swap_short_per_unit: float = -0.00005

    # Standard FX rollover boundary.
    swap_rollover_timezone: str = "America/New_York"
    swap_rollover_hour: int = 17
    swap_rollover_minute: int = 0

    # Python weekday convention:
    # Monday = 0
    # Tuesday = 1
    # Wednesday = 2
    # Thursday = 3
    # Friday = 4
    swap_triple_weekday: int = 2

    swap_triple_multiplier: float = 3.0

    # --------------------------------------------------------
    # SLIPPAGE
    # --------------------------------------------------------

    include_slippage: bool = False
    slippage_per_unit: float = 0.0