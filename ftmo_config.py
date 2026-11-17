# -*- coding: utf-8 -*-
"""
Created on Wed Sep  9 21:08:13 2026
08_config/ftmo_config.py
"""

"""
FTMO Prop-Firm Presets
======================

Purpose
-------
Represent FTMO-specific prop-rule values using the generic
PropFirmConfig schema.

Responsibilities
----------------
- Define supported FTMO programme presets.
- Define phase-specific FTMO parameter values.
- Return generic PropFirmConfig instances.
- Keep FTMO-specific values isolated from NexusEngine,
  run_backtest.py and the generic prop evaluator.

Does Not
--------
- Execute trades.
- Evaluate prop rules.
- Calculate account equity.
- Calculate commission or swap.
- Modify NexusEngine.
- Modify run_backtest.py.
- Contain generic prop-evaluation algorithms.

Architecture
------------
This module contains provider-specific configuration DATA.

Evaluation logic remains in:

    prop_evaluator.py

Generic schema remains in:

    prop_config.py

Selection and routing remain in:

    prop_selection.py
    prop_factory.py

Maintenance
-----------
Provider rules may change.

Values in this module should therefore be periodically checked
against the provider's current official rules before being
relied upon for live challenge planning.
"""


from prop_config import PropFirmConfig


# ============================================================
# COMMON FTMO 2-STEP CONFIGURATION
# ============================================================

def _get_ftmo_2step_config(
    phase_name: str,
    profit_target_pct,
    minimum_trading_days: int,
    profit_target_requires_flat: bool,
) -> PropFirmConfig:
    """
    Build one FTMO 2-Step phase configuration.
    """

    return PropFirmConfig(
        # ----------------------------------------------------
        # Identity
        # ----------------------------------------------------

        provider_name="FTMO",

        programme_name="FTMO Challenge: 2-Step",

        phase_name=phase_name,

        # ----------------------------------------------------
        # Profit target
        # ----------------------------------------------------

        profit_target_pct=(
            profit_target_pct
        ),

        profit_target_measure="balance",

        profit_target_requires_flat=(
            profit_target_requires_flat
        ),

        # ----------------------------------------------------
        # Maximum Daily Loss
        #
        # Allowance:
        #
        #     5% of initial simulated capital
        #
        # Daily floor:
        #
        #     balance at 00:00 CE(S)T
        #     minus daily allowance
        #
        # Rule is tested against equity.
        # ----------------------------------------------------

        daily_loss_pct=0.05,

        daily_loss_amount=None,

        daily_loss_allowance_reference=(
            "initial_balance"
        ),

        daily_loss_anchor=(
            "day_start_balance"
        ),

        daily_loss_measure="equity",

        # ----------------------------------------------------
        # Maximum Loss
        #
        # Static floor:
        #
        #     initial balance - 10%
        # ----------------------------------------------------

        total_loss_pct=0.10,

        total_loss_amount=None,

        total_loss_model=(
            "static_initial"
        ),

        total_loss_measure="equity",

        # ----------------------------------------------------
        # FTMO trading-day clock
        # ----------------------------------------------------

        daily_reset_timezone=(
            "Europe/Prague"
        ),

        daily_reset_hour=0,
        daily_reset_minute=0,

        # ----------------------------------------------------
        # Trading days
        # ----------------------------------------------------

        minimum_trading_days=(
            minimum_trading_days
        ),

        maximum_trading_days=None,

        trading_day_activity_basis=(
            "entry"
        ),

        # ----------------------------------------------------
        # Boundary behaviour
        #
        # FTMO describes violation as equity dropping BELOW
        # the applicable limit.
        # ----------------------------------------------------

        breach_on_equal=False,
    )


# ============================================================
# FTMO 2-STEP CHALLENGE
# ============================================================

def get_ftmo_2step_challenge_config() -> PropFirmConfig:
    """
    Return the FTMO 2-Step Challenge phase configuration.
    """

    return _get_ftmo_2step_config(
        phase_name="FTMO Challenge",
        profit_target_pct=0.10,
        minimum_trading_days=4,
        profit_target_requires_flat=True,
    )


# ============================================================
# FTMO 2-STEP VERIFICATION
# ============================================================

def get_ftmo_2step_verification_config() -> PropFirmConfig:
    """
    Return the FTMO 2-Step Verification configuration.
    """

    return _get_ftmo_2step_config(
        phase_name="Verification",
        profit_target_pct=0.05,
        minimum_trading_days=4,
        profit_target_requires_flat=True,
    )


# ============================================================
# FTMO ACCOUNT
# ============================================================

def get_ftmo_2step_account_config() -> PropFirmConfig:
    """
    Return the subsequent FTMO Account configuration.

    There is no profit target or minimum trading-day
    requirement on the subsequent FTMO Account.
    """

    return _get_ftmo_2step_config(
        phase_name="FTMO Account",
        profit_target_pct=None,
        minimum_trading_days=0,
        profit_target_requires_flat=False,
    )