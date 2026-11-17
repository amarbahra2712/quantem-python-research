# -*- coding: utf-8 -*-
"""
Created on Fri Sep 18 14:40:14 2026
@author: quant
08_config/prop_selection.py
"""

"""
Active Prop-Firm Selection
==========================

Purpose
-------
Select the provider, programme and phase to be used by the
current NEXUS backtest.

Responsibilities
----------------
- Identify the active prop provider.
- Identify the active programme.
- Identify the active evaluation phase.

Does Not
--------
- Define provider rule values.
- Evaluate prop rules.
- Import NexusEngine.
- Modify run_backtest.py.
- Contain execution or strategy parameters.

How to Use
----------
Change only the selection values in this file when switching
between supported prop environments.

The generic prop factory resolves the selection into a
PropFirmConfig.

Example
-------
A selection may identify:

    provider
    programme
    phase

without run_backtest.py requiring provider-specific logic.
"""


# ============================================================
# ACTIVE PROP-FIRM SELECTION
# ============================================================

PROP_PROVIDER = "FTMO"

PROP_PROGRAMME = "2step"

PROP_PHASE = "challenge"