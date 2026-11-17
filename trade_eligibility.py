# -*- coding: utf-8 -*-
"""
Created on Mon Sep 21 11:30:58 2026

@author: quant
"""

"""
NEXUS Trade Eligibility
=======================

Purpose
-------
Provide generic entry-eligibility checks used by NexusEngine
before opening new positions.

Responsibilities
----------------
- Evaluate candidate entry timestamps.
- Convert timestamps into the configured trading timezone.
- Enforce permitted weekdays.
- Enforce one or more trading windows.
- Support overnight trading windows.
- Return diagnostic information explaining an eligibility
  decision.

Does Not
--------
- Generate strategy signals.
- Execute trades.
- Manage open positions.
- Calculate P&L.
- Define prop-firm rules.
- Define trading-window parameters.

Design Principle
----------------
Trading eligibility applies only to NEW ENTRIES.

Once a position has been opened, normal NEXUS position
management continues even after the permitted entry window has
closed.

This keeps strategy signal generation independent from generic
execution restrictions.
"""


from dataclasses import dataclass
from typing import Optional

import pandas as pd

from trading_window_config import (
    TradingWindow,
    TradingWindowConfig,
)


# ============================================================
# ELIGIBILITY RESULT
# ============================================================

@dataclass(frozen=True)
class EntryEligibilityResult:
    """
    Result of one entry-eligibility evaluation.
    """

    allowed: bool

    local_timestamp: pd.Timestamp

    reason: str

    matched_window: Optional[str] = None


# ============================================================
# WINDOW MATCHING
# ============================================================

def _timestamp_matches_window(
    local_timestamp: pd.Timestamp,
    window: TradingWindow,
    allowed_weekdays,
) -> bool:
    """
    Return True when a local timestamp falls inside one
    permitted trading window.

    Overnight windows belong to the weekday on which the
    window starts.
    """

    local_time = (
        local_timestamp.time()
    )

    start_time = (
        window.start_time
    )

    end_time = (
        window.end_time
    )

    # ========================================================
    # SAME-DAY WINDOW
    #
    # Example:
    #
    #     06:00 -> 11:00
    # ========================================================

    if start_time < end_time:

        if (
            local_timestamp.weekday()
            not in allowed_weekdays
        ):

            return False

        return bool(
            start_time
            <= local_time
            < end_time
        )

    # ========================================================
    # OVERNIGHT WINDOW
    #
    # Example:
    #
    #     22:00 -> 02:00
    # ========================================================

    if local_time >= start_time:

        window_start_weekday = (
            local_timestamp.weekday()
        )

    elif local_time < end_time:

        previous_day = (
            local_timestamp
            - pd.Timedelta(
                days=1
            )
        )

        window_start_weekday = (
            previous_day.weekday()
        )

    else:

        return False

    if (
        window_start_weekday
        not in allowed_weekdays
    ):

        return False

    return True


# ============================================================
# ENTRY ELIGIBILITY
# ============================================================

def evaluate_entry_eligibility(
    timestamp: pd.Timestamp,
    config: TradingWindowConfig,
) -> EntryEligibilityResult:
    """
    Evaluate whether a new position may be opened at the
    supplied timestamp.

    Parameters
    ----------
    timestamp : pd.Timestamp
        Candidate ENTRY timestamp.

        Must be timezone-aware.

    config : TradingWindowConfig
        Generic trading-window configuration.

    Returns
    -------
    EntryEligibilityResult
        Decision plus diagnostic information.
    """

    timestamp = pd.Timestamp(
        timestamp
    )

    if timestamp.tzinfo is None:

        raise ValueError(
            "Entry eligibility timestamp must be "
            "timezone-aware."
        )

    local_timestamp = (
        timestamp.tz_convert(
            config.timezone
        )
    )

    # ========================================================
    # FILTER DISABLED
    # ========================================================

    if not config.enabled:

        return EntryEligibilityResult(
            allowed=True,

            local_timestamp=(
                local_timestamp
            ),

            reason="filter_disabled",

            matched_window=None,
        )

    # ========================================================
    # ALL-DAY MODE
    #
    # Empty windows means:
    #
    #     any time on an allowed weekday
    # ========================================================

    if not config.windows:

        allowed = (
            local_timestamp.weekday()
            in config.allowed_weekdays
        )

        return EntryEligibilityResult(
            allowed=allowed,

            local_timestamp=(
                local_timestamp
            ),

            reason=(
                "allowed_weekday"
                if allowed
                else "weekday_blocked"
            ),

            matched_window=None,
        )

    # ========================================================
    # WINDOW MODE
    # ========================================================

    for window in config.windows:

        if _timestamp_matches_window(
            local_timestamp=(
                local_timestamp
            ),

            window=window,

            allowed_weekdays=(
                config.allowed_weekdays
            ),
        ):

            return EntryEligibilityResult(
                allowed=True,

                local_timestamp=(
                    local_timestamp
                ),

                reason="matched_window",

                matched_window=(
                    window.name
                ),
            )

    # ========================================================
    # NO WINDOW MATCH
    # ========================================================

    return EntryEligibilityResult(
        allowed=False,

        local_timestamp=(
            local_timestamp
        ),

        reason="outside_allowed_window",

        matched_window=None,
    )