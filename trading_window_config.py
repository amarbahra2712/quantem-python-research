# -*- coding: utf-8 -*-
"""
Created on Mon Sep 21 11:25:50 2026

@author: quant
"""

"""
NEXUS Trading-Window Configuration
==================================

Purpose
-------
Define generic time-based eligibility rules controlling when
NEXUS is permitted to open new positions.

Responsibilities
----------------
- Enable or disable trading-window filtering.
- Define the timezone used by trading windows.
- Define permitted weekdays.
- Define one or more permitted entry windows.
- Support windows contained within one day.
- Support windows crossing midnight.
- Keep trading-window parameters outside strategies and
  run_backtest.py.

Does Not
--------
- Generate strategy signals.
- Execute trades.
- Close or manage existing positions.
- Define prop-firm trading days.
- Define broker rollover times.
- Modify strategy logic.

Architecture
------------
Strategy
    generates potential entry instructions.

Trading-window framework
    determines whether a new entry is permitted.

NexusEngine
    executes the entry only when eligible.

Existing open positions remain subject to normal position
management regardless of whether the entry window has closed.

Time Semantics
--------------
Window start times are inclusive.

Window end times are exclusive.

Example:

    06:00 -> 10:00

allows:

    06:00:00
    ...
    09:59:59

but not:

    10:00:00

Weekdays use the standard Python convention:

    Monday    = 0
    Tuesday   = 1
    Wednesday = 2
    Thursday  = 3
    Friday    = 4
    Saturday  = 5
    Sunday    = 6

Overnight Windows
-----------------
A window such as:

    22:00 -> 02:00

belongs to the weekday on which the window STARTS.

Therefore, if Friday is an allowed weekday:

    Friday 23:00   -> allowed
    Saturday 01:00 -> allowed

because both belong to Friday's overnight window.

An empty windows tuple means all times are permitted on the
configured weekdays.

Notes
-----
This module defines eligibility parameters only.

The actual eligibility calculation lives in the generic engine
utility:

    04_engine/trade_eligibility.py
"""


from dataclasses import dataclass
from datetime import time
from typing import Tuple


# ============================================================
# TRADING WINDOW
# ============================================================

@dataclass(frozen=True)
class TradingWindow:
    """
    One permitted entry window.
    """

    name: str

    start_time: time

    end_time: time


    def __post_init__(self) -> None:
        """
        Validate one trading window.
        """

        if not self.name.strip():

            raise ValueError(
                "TradingWindow name cannot be empty."
            )

        if self.start_time == self.end_time:

            raise ValueError(
                "TradingWindow start_time and end_time "
                "cannot be identical. Use an empty windows "
                "tuple for all-day trading."
            )


# ============================================================
# TRADING-WINDOW CONFIG
# ============================================================

@dataclass(frozen=True)
class TradingWindowConfig:
    """
    Generic configuration controlling entry-time eligibility.
    """

    enabled: bool = False

    timezone: str = "UTC"

    allowed_weekdays: Tuple[int, ...] = (
        0,
        1,
        2,
        3,
        4,
    )

    windows: Tuple[TradingWindow, ...] = ()


    def __post_init__(self) -> None:
        """
        Validate trading-window configuration.
        """

        if not self.timezone.strip():

            raise ValueError(
                "Trading-window timezone cannot be empty."
            )

        if len(
            set(
                self.allowed_weekdays
            )
        ) != len(
            self.allowed_weekdays
        ):

            raise ValueError(
                "allowed_weekdays contains duplicates."
            )

        for weekday in self.allowed_weekdays:

            if weekday not in range(
                0,
                7,
            ):

                raise ValueError(
                    "allowed_weekdays values must be "
                    "between 0 and 6."
                )


# ============================================================
# ACTIVE TRADING-WINDOW CONFIGURATION
# ============================================================

def get_active_trading_window_config(
) -> TradingWindowConfig:
    """
    Return the trading-window configuration used by the
    current NEXUS run.

    Filtering is initially DISABLED so introducing this module
    does not change the existing baseline backtest.
    """

    return TradingWindowConfig(
        enabled=True,

        timezone="Europe/London",

        allowed_weekdays=(
            0,
            1,
            2,
            3,
            4,
        ),

        windows=(
            TradingWindow(
                name="London Morning",
                start_time=time(
                    6,
                    0,
                ),
                end_time=time(
                    11,
                    0,
                ),
            ),
        ),
    )