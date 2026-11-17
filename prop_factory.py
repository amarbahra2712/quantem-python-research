# -*- coding: utf-8 -*-
"""
Created on Fri Sep 18 14:33:50 2026
@author: quant
08_config/prop_factory.py
"""

"""
Generic Prop-Firm Configuration Factory
========================================

Purpose
-------
Resolve the active provider / programme / phase selection into
a generic PropFirmConfig instance.

Responsibilities
----------------
- Read the active prop selection.
- Resolve provider, programme and phase identifiers.
- Route requests to the appropriate provider preset module.
- Return PropFirmConfig to the backtesting framework.
- Reload prop_selection.py so parameter changes are detected
  in persistent Python / Spyder kernels.

Does Not
--------
- Evaluate prop rules.
- Execute trades.
- Define strategy behaviour.
- Contain account calculations.
- Modify NexusEngine.
- Require run_backtest.py to know provider-specific values.

Architecture
------------
run_backtest.py
        |
        v
get_active_prop_config()
        |
        v
prop_selection.py
        |
        v
prop_factory.py
        |
        v
provider preset
        |
        v
PropFirmConfig

Notes
-----
Provider-specific imports are intentionally isolated behind
this factory.

Adding another provider should therefore require a new preset
module and routing here, rather than changes to the backtester
or execution engine.
"""

from prop_config import PropFirmConfig

import importlib

import prop_selection


# ============================================================
# PROP CONFIG RESOLVER
# ============================================================

def get_prop_config(
    provider: str,
    programme: str,
    phase: str,
) -> PropFirmConfig:
    """
    Resolve one provider/programme/phase combination.
    """

    provider_key = (
        provider
        .strip()
        .lower()
    )

    programme_key = (
        programme
        .strip()
        .lower()
    )

    phase_key = (
        phase
        .strip()
        .lower()
    )

    # ========================================================
    # FTMO
    # ========================================================

    if provider_key == "ftmo":

        from ftmo_config import (
            get_ftmo_2step_challenge_config,
            get_ftmo_2step_verification_config,
            get_ftmo_2step_account_config,
        )

        if programme_key in (
            "2step",
            "2-step",
            "two_step",
        ):

            if phase_key in (
                "challenge",
                "phase1",
                "phase_1",
            ):

                return (
                    get_ftmo_2step_challenge_config()
                )

            if phase_key in (
                "verification",
                "phase2",
                "phase_2",
            ):

                return (
                    get_ftmo_2step_verification_config()
                )

            if phase_key in (
                "account",
                "funded",
                "ftmo_account",
            ):

                return (
                    get_ftmo_2step_account_config()
                )

        raise ValueError(
            "Unsupported FTMO programme / phase: "
            f"{programme} / {phase}"
        )

    # ========================================================
    # FUTURE PROVIDERS
    # ========================================================

    # Add provider routing here as new preset modules are
    # introduced.

    raise ValueError(
        "Unsupported prop provider: "
        f"{provider}"
    )


# ============================================================
# ACTIVE PROP CONFIGURATION
# ============================================================

def get_active_prop_config() -> PropFirmConfig:
    """
    Return the currently selected prop-firm configuration.

    prop_selection.py is reloaded on every call so that edits
    to provider / programme / phase are picked up immediately
    when the backtest is rerun in a persistent Python kernel.
    """

    importlib.invalidate_caches()

    selection = importlib.reload(
        prop_selection
    )

    return get_prop_config(
        provider=(
            selection.PROP_PROVIDER
        ),

        programme=(
            selection.PROP_PROGRAMME
        ),

        phase=(
            selection.PROP_PHASE
        ),
    )