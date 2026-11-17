# -*- coding: utf-8 -*-
"""
Created on Thu Sep 17 17:32:46 2026
@author: quant
06_analysis/prop_evaluator.py
"""

"""
Generic Prop-Firm Evaluator
===========================

Purpose
-------
Evaluate a completed NEXUS backtest against configurable
prop-firm rules without embedding provider-specific logic in
the trading engine.

Responsibilities
----------------
- Convert timestamps into configurable prop trading days.
- Handle provider reset timezone and reset time.
- Build daily prop-account states.
- Reconstruct realised balance at reset boundaries.
- Track bar-close and intrabar equity behaviour.
- Calculate configurable daily-loss floors.
- Detect the first daily-loss breach.
- Calculate static overall-loss floors.
- Detect the first overall-loss breach.
- Count actual trading days from position entries.
- Count trading days up to an evaluation outcome.
- Evaluate profit-target requirements.
- Enforce minimum trading-day requirements.
- Optionally require the account to be flat when a profit
  target is achieved.
- Determine the first applicable failure or valid pass.
- Return a generic PropEvaluationResult with status:

      ACTIVE
      PASSED
      FAILED

Does Not
--------
- Execute trades.
- Generate strategy signals.
- Modify account balance.
- Calculate commission or swap.
- Contain FTMO-specific or other provider-specific values.
- Decide which provider preset is active.
- Stop NexusEngine when a prop-rule breach occurs.

Architecture
------------
NexusEngine
    produces execution, account, equity and risk history.

PropFirmConfig
    describes generic prop-rule parameters.

Provider preset
    supplies provider-specific values.

Prop evaluator
    interprets the NEXUS result under those rules.

Current V1 Support
------------------
- Balance-based profit target.
- Optional flat-position requirement at target.
- Minimum trading days based on trade-entry activity.
- Daily loss based on configurable allowance and anchor.
- Equity- or balance-based daily-loss measurement.
- Static-initial overall loss model.
- Equity- or balance-based overall-loss measurement.
- Intrabar equity evaluation through RiskPoint history.
- Configurable reset timezone and time.

Notes
-----
The full NEXUS simulation continues after a prop account has
technically failed or passed.

This is intentional: the complete strategy history remains
available for research, while PropEvaluationResult records the
timestamp at which the prop evaluation itself ended.
"""


from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Optional

import pandas as pd

from prop_config import PropFirmConfig
from nexus_engine import BacktestResult

# ============================================================
# DAILY PROP STATE
# ============================================================

@dataclass
class PropDailyState:
    """
    Evaluation state for one prop-firm trading day.
    """

    trading_day: date

    reset_time: pd.Timestamp

    start_balance: float
    start_equity: float

    lowest_balance: float
    lowest_balance_time: pd.Timestamp

    lowest_equity: float
    lowest_equity_time: pd.Timestamp
    
    lowest_intrabar_equity: float
    lowest_intrabar_equity_time: pd.Timestamp

    daily_loss_floor: Optional[float]

    breached: bool = False
    breach_time: Optional[pd.Timestamp] = None
    breach_value: Optional[float] = None

# ============================================================
# TOTAL LOSS STATE
# ============================================================

@dataclass
class PropTotalLossState:
    """
    Evaluation state for the prop firm's overall loss limit.
    """

    loss_floor: Optional[float]

    lowest_value: float
    lowest_value_time: pd.Timestamp

    breached: bool = False

    breach_time: Optional[pd.Timestamp] = None
    breach_value: Optional[float] = None

# ============================================================
# PROP EVALUATION RESULT
# ============================================================

@dataclass
class PropEvaluationResult:
    """
    Final generic result of one prop-firm evaluation phase.

    Status values
    -------------
    ACTIVE
        No failure occurred, but all pass conditions were not
        satisfied during the supplied backtest.

    PASSED
        Profit target and minimum trading-day requirements were
        satisfied before any rule breach.

    FAILED
        A configured loss rule was breached before the phase
        was successfully completed.
    """

    provider_name: str
    programme_name: str
    phase_name: str

    status: str

    starting_balance: float
    ending_balance: float
    ending_equity: float

    # --------------------------------------------------------
    # Evaluation outcome
    # --------------------------------------------------------

    outcome_time: Optional[pd.Timestamp]

    trading_days: int

    # --------------------------------------------------------
    # Profit target
    # --------------------------------------------------------

    profit_target_amount: Optional[float]
    profit_target_balance: Optional[float]

    profit_target_hit: bool
    profit_target_time: Optional[pd.Timestamp]
    profit_target_value: Optional[float]

    # --------------------------------------------------------
    # Loss rules
    # --------------------------------------------------------

    total_loss_floor: Optional[float]

    breach_rule: Optional[str]
    breach_time: Optional[pd.Timestamp]
    breach_value: Optional[float]

    # --------------------------------------------------------
    # Daily audit trail
    # --------------------------------------------------------

    daily_states: List[PropDailyState]


# ============================================================
# PROP TRADING-DAY CLOCK
# ============================================================

def get_prop_trading_day(
    timestamp: pd.Timestamp,
    config: PropFirmConfig,
) -> date:
    """
    Return the prop-firm trading-day key for a timestamp.

    The timestamp is first converted into the configured
    prop-firm timezone.

    The configured reset time is then treated as the start of
    each prop trading day.

    Example
    -------
    If reset time is:

        17:00 New York

    then:

        Monday 16:59
            belongs to the previous prop day

        Monday 17:00
            begins the new prop day

    For a midnight reset, this naturally behaves like a normal
    local calendar date.
    """

    timestamp = pd.Timestamp(
        timestamp
    )

    if timestamp.tzinfo is None:
        raise ValueError(
            "Prop evaluation timestamps must be "
            "timezone-aware."
        )

    local_time = timestamp.tz_convert(
        config.daily_reset_timezone
    )

    reset_offset = pd.Timedelta(
        hours=config.daily_reset_hour,
        minutes=config.daily_reset_minute,
    )

    shifted_time = (
        local_time
        - reset_offset
    )

    return shifted_time.date()


# ============================================================
# PROP RESET TIMESTAMP
# ============================================================

def get_prop_reset_time(
    trading_day: date,
    config: PropFirmConfig,
    output_timezone: Optional[str] = None,
) -> pd.Timestamp:
    """
    Return the exact reset timestamp beginning one prop trading
    day.

    Parameters
    ----------
    trading_day : date
        Prop trading-day key.

    config : PropFirmConfig
        Prop-firm configuration.

    output_timezone : str, optional
        Desired timezone for returned timestamp.

        If omitted, the timestamp remains in the prop firm's
        reset timezone.
    """

    reset_naive = pd.Timestamp(
        year=trading_day.year,
        month=trading_day.month,
        day=trading_day.day,
        hour=config.daily_reset_hour,
        minute=config.daily_reset_minute,
    )

    reset_local = (
        reset_naive.tz_localize(
            config.daily_reset_timezone
        )
    )

    if output_timezone is not None:

        return reset_local.tz_convert(
            output_timezone
        )

    return reset_local

# ============================================================
# DAILY LOSS ALLOWANCE
# ============================================================

def _calculate_daily_loss_allowance(
    config: PropFirmConfig,
    initial_balance: float,
    day_start_balance: float,
    day_start_equity: float,
) -> Optional[float]:
    """
    Calculate the permitted monetary loss for one prop day.

    A fixed configured amount takes precedence.

    Otherwise the percentage allowance is applied to the
    configured reference value.
    """

    if config.daily_loss_amount is not None:

        return float(
            config.daily_loss_amount
        )

    if config.daily_loss_pct is None:

        return None

    if (
        config.daily_loss_allowance_reference
        == "initial_balance"
    ):

        reference_value = (
            initial_balance
        )

    elif (
        config.daily_loss_allowance_reference
        == "day_start_balance"
    ):

        reference_value = (
            day_start_balance
        )

    elif (
        config.daily_loss_allowance_reference
        == "day_start_equity"
    ):

        reference_value = (
            day_start_equity
        )

    else:

        raise ValueError(
            "Unsupported daily loss allowance reference: "
            f"{config.daily_loss_allowance_reference}"
        )

    return float(
        reference_value
        * config.daily_loss_pct
    )


# ============================================================
# DAILY LOSS FLOOR
# ============================================================

def _calculate_daily_loss_floor(
    config: PropFirmConfig,
    initial_balance: float,
    day_start_balance: float,
    day_start_equity: float,
) -> Optional[float]:
    """
    Calculate the account floor for one prop trading day.
    """

    allowance = (
        _calculate_daily_loss_allowance(
            config=config,
            initial_balance=initial_balance,
            day_start_balance=day_start_balance,
            day_start_equity=day_start_equity,
        )
    )

    if allowance is None:

        return None

    if config.daily_loss_anchor == "day_start_balance":

        anchor = (
            day_start_balance
        )

    elif config.daily_loss_anchor == "day_start_equity":

        anchor = (
            day_start_equity
        )

    else:

        raise ValueError(
            "Unsupported daily loss anchor: "
            f"{config.daily_loss_anchor}"
        )

    return float(
        anchor - allowance
    )

# ============================================================
# BALANCE AT PROP RESET
# ============================================================

def _get_balance_at_reset(
    backtest_result: BacktestResult,
    reset_time: pd.Timestamp,
) -> float:
    """
    Return realised account balance immediately before a prop
    trading day begins.

    Account events occurring exactly at the reset timestamp
    belong to the new prop day and are therefore not included
    in the starting balance.
    """

    balance = float(
        backtest_result.starting_balance
    )

    for event in backtest_result.account_events:

        if event.timestamp >= reset_time:

            break

        balance = float(
            event.balance_after
        )

    return balance

# ============================================================
# BALANCE AT OR BEFORE TIMESTAMP
# ============================================================

def _get_balance_at_or_before(
    backtest_result: BacktestResult,
    timestamp: pd.Timestamp,
) -> float:
    """
    Return realised account balance after all account events
    occurring at or before the supplied timestamp.
    """

    timestamp = pd.Timestamp(
        timestamp
    )

    if timestamp.tzinfo is None:

        raise ValueError(
            "Balance lookup timestamp must be "
            "timezone-aware."
        )

    balance = float(
        backtest_result.starting_balance
    )

    for event in backtest_result.account_events:

        if event.timestamp > timestamp:
            break

        balance = float(
            event.balance_after
        )

    return balance

# ============================================================
# PROFIT TARGET
# ============================================================

def _calculate_profit_target(
    backtest_result: BacktestResult,
    config: PropFirmConfig,
):
    """
    Calculate profit-target amount and target balance.

    Returns
    -------
    tuple
        (
            profit_target_amount,
            profit_target_balance,
        )

    If no profit target is configured:

        (None, None)
    """

    if config.profit_target_pct is None:

        return (
            None,
            None,
        )

    starting_balance = float(
        backtest_result.starting_balance
    )

    profit_target_amount = (
        starting_balance
        * config.profit_target_pct
    )

    profit_target_balance = (
        starting_balance
        + profit_target_amount
    )

    return (
        float(
            profit_target_amount
        ),
        float(
            profit_target_balance
        ),
    )


# ============================================================
# OPEN POSITION AT TIMESTAMP
# ============================================================

def _has_open_position_at(
    backtest_result: BacktestResult,
    timestamp: pd.Timestamp,
) -> bool:
    """
    Return True if a NEXUS position is still open immediately
    after the supplied timestamp.

    Completed trades use:

        entry_time <= timestamp < exit_time

    Therefore a position whose exit_time equals the supplied
    timestamp is considered closed at that timestamp.

    A position still open at dataset end is also considered.
    """

    timestamp = pd.Timestamp(
        timestamp
    )

    if timestamp.tzinfo is None:

        raise ValueError(
            "Position-state timestamp must be "
            "timezone-aware."
        )

    # --------------------------------------------------------
    # Completed trades
    # --------------------------------------------------------

    for trade in backtest_result.trades:

        entry_time = pd.Timestamp(
            trade.entry_time
        )

        exit_time = pd.Timestamp(
            trade.exit_time
        )

        if (
            entry_time
            <= timestamp
            < exit_time
        ):

            return True

    # --------------------------------------------------------
    # Position still open at dataset end
    # --------------------------------------------------------

    if backtest_result.open_position is not None:

        entry_time = pd.Timestamp(
            backtest_result
            .open_position
            .entry_time
        )

        if entry_time <= timestamp:

            return True

    return False

# ============================================================
# FIRST VALID PROFIT-TARGET COMPLETION
# ============================================================

def get_first_valid_pass(
    backtest_result: BacktestResult,
    config: PropFirmConfig,
):
    """
    Find the first timestamp at which all currently supported
    pass conditions are simultaneously satisfied.

    V1 pass conditions
    ------------------
    - configured profit target reached
    - minimum trading days satisfied
    - account flat, when required by configuration

    Profit target is currently measured using realised account
    balance.

    Returns
    -------
    tuple
        (
            pass_time,
            pass_value,
        )

    If no valid pass occurs:

        (None, None)
    """

    (
        profit_target_amount,
        profit_target_balance,
    ) = _calculate_profit_target(
        backtest_result=backtest_result,
        config=config,
    )

    # --------------------------------------------------------
    # No profit target configured
    # --------------------------------------------------------

    if profit_target_balance is None:

        return (
            None,
            None,
        )

    # --------------------------------------------------------
    # V1 currently supports realised balance targets only
    # --------------------------------------------------------

    if config.profit_target_measure != "balance":

        raise NotImplementedError(
            "V1 prop evaluator currently supports only "
            "profit_target_measure='balance'."
        )

    # --------------------------------------------------------
    # Candidate timestamps
    #
    # Account events matter because realised balance can
    # change there.
    #
    # Trade entries matter because a new entry can create the
    # minimum required trading day.
    # --------------------------------------------------------

    candidate_times = set()

    for event in backtest_result.account_events:

        candidate_times.add(
            pd.Timestamp(
                event.timestamp
            )
        )

    for trade in backtest_result.trades:

        candidate_times.add(
            pd.Timestamp(
                trade.entry_time
            )
        )

    if backtest_result.open_position is not None:

        candidate_times.add(
            pd.Timestamp(
                backtest_result
                .open_position
                .entry_time
            )
        )

    # --------------------------------------------------------
    # Evaluate candidate timestamps chronologically
    # --------------------------------------------------------

    for candidate_time in sorted(
        candidate_times
    ):

        # ----------------------------------------------------
        # Realised balance at this point
        # ----------------------------------------------------

        balance = (
            _get_balance_at_or_before(
                backtest_result=(
                    backtest_result
                ),
                timestamp=(
                    candidate_time
                ),
            )
        )

        # ----------------------------------------------------
        # Profit target not yet reached
        # ----------------------------------------------------

        if balance < profit_target_balance:

            continue

        # ----------------------------------------------------
        # Minimum trading-day requirement
        # ----------------------------------------------------

        trading_days = (
            get_prop_trading_days_up_to(
                backtest_result=(
                    backtest_result
                ),
                config=config,
                cutoff_time=(
                    candidate_time
                ),
            )
        )

        if (
            len(
                trading_days
            )
            < config.minimum_trading_days
        ):

            continue

        # ----------------------------------------------------
        # Some providers require all positions to be closed
        # before the profit target is considered achieved.
        # ----------------------------------------------------

        if (
            config.profit_target_requires_flat
            and _has_open_position_at(
                backtest_result=(
                    backtest_result
                ),
                timestamp=(
                    candidate_time
                ),
            )
        ):

            continue

        # ----------------------------------------------------
        # All pass conditions satisfied
        # ----------------------------------------------------

        return (
            candidate_time,
            float(
                balance
            ),
        )

    # --------------------------------------------------------
    # No valid pass occurred anywhere in the backtest
    # --------------------------------------------------------

    return (
        None,
        None,
    )        

# ============================================================
# EQUITY AT PROP RESET
# ============================================================

def _get_equity_at_reset(
    backtest_result: BacktestResult,
    reset_time: pd.Timestamp,
) -> Optional[float]:
    """
    Return account equity at the exact prop reset timestamp
    when an exact equity observation exists.

    Returns None when the backtest contains no equity point at
    exactly that timestamp.

    We deliberately do not silently substitute a later bar,
    because that would no longer represent true day-start
    equity.
    """

    for point in backtest_result.equity_curve:

        if point.timestamp < reset_time:
            continue

        if point.timestamp == reset_time:

            return float(
                point.equity
            )

        # Equity curve is chronological.
        # Once we pass reset_time there cannot be an exact
        # observation later.
        if point.timestamp > reset_time:
            break

    return None

# ============================================================
# DAILY PROP STATE GENERATOR
# ============================================================

def build_prop_daily_states(
    backtest_result: BacktestResult,
    config: PropFirmConfig,
) -> List[PropDailyState]:
    """
    Build one PropDailyState for each prop trading day observed
    in the NEXUS equity history.

    V1 daily states use bar-close equity observations.

    Exact intrabar loss-limit evaluation will be added
    separately.
    """

    if not backtest_result.equity_curve:

        return []

    # --------------------------------------------------------
    # Group equity points by prop trading day
    # --------------------------------------------------------

    equity_by_day = {}

    for point in backtest_result.equity_curve:

        trading_day = (
            get_prop_trading_day(
                timestamp=point.timestamp,
                config=config,
            )
        )

        if trading_day not in equity_by_day:

            equity_by_day[
                trading_day
            ] = []

        equity_by_day[
            trading_day
        ].append(
            point
        )

    # --------------------------------------------------------
    # Group intrabar risk points by prop trading day
    # --------------------------------------------------------

    risk_by_day = {}

    for point in backtest_result.risk_curve:

        trading_day = (
            get_prop_trading_day(
                timestamp=point.timestamp,
                config=config,
            )
        )

        if trading_day not in risk_by_day:

            risk_by_day[
                trading_day
            ] = []

        risk_by_day[
            trading_day
        ].append(
            point
        )
            
    # --------------------------------------------------------
    # Group account events by prop trading day
    # --------------------------------------------------------

    events_by_day = {}

    for event in backtest_result.account_events:

        trading_day = (
            get_prop_trading_day(
                timestamp=event.timestamp,
                config=config,
            )
        )

        if trading_day not in events_by_day:

            events_by_day[
                trading_day
            ] = []

        events_by_day[
            trading_day
        ].append(
            event
        )

    # --------------------------------------------------------
    # Build daily states
    # --------------------------------------------------------

    daily_states = []

    for trading_day in sorted(
        equity_by_day.keys()
    ):

        equity_points = (
            equity_by_day[
                trading_day
            ]
        )

        risk_points = (
            risk_by_day.get(
                trading_day,
                [],
            )
        )

        if not risk_points:

            raise ValueError(
                "Missing risk points for prop trading day: "
                f"{trading_day}"
            )
        
        reset_time = (
            get_prop_reset_time(
                trading_day=trading_day,
                config=config,
                output_timezone=(
                    str(
                        equity_points[
                            0
                        ].timestamp.tz
                    )
                ),
            )
        )

        # ----------------------------------------------------
        # Starting realised balance
        # ----------------------------------------------------

        start_balance = (
            _get_balance_at_reset(
                backtest_result=(
                    backtest_result
                ),
                reset_time=reset_time,
            )
        )

        # ----------------------------------------------------
        # Starting equity
        # ----------------------------------------------------
        
        exact_reset_equity = (
            _get_equity_at_reset(
                backtest_result=(
                    backtest_result
                ),
                reset_time=(
                    reset_time
                ),
            )
        )
        
        
        if exact_reset_equity is not None:
        
            start_equity = float(
                exact_reset_equity
            )
        
        else:
        
            # ------------------------------------------------
            # If the configured prop rule actually depends on
            # day-start equity, an approximation is not safe.
            # ------------------------------------------------
        
            requires_exact_start_equity = (
                config.daily_loss_allowance_reference
                == "day_start_equity"
                or config.daily_loss_anchor
                == "day_start_equity"
            )
        
            if requires_exact_start_equity:
        
                raise ValueError(
                    "Prop configuration requires exact "
                    "day-start equity, but no equity point "
                    "exists at reset time: "
                    f"{reset_time}"
                )
        
            # ------------------------------------------------
            # The current rule does not depend on start equity.
            #
            # Retain the first observed equity only as a useful
            # daily diagnostic.
            # ------------------------------------------------
        
            start_equity = float(
                equity_points[
                    0
                ].equity
            )

        # ----------------------------------------------------
        # Lowest observed equity
        # ----------------------------------------------------

        lowest_equity_point = min(
            equity_points,
            key=lambda point: (
                point.equity
            ),
        )

        # ----------------------------------------------------
        # Lowest intrabar equity
        # ----------------------------------------------------

        lowest_intrabar_point = min(
            risk_points,
            key=lambda point: (
                point.intrabar_min_equity
            ),
        )

        lowest_intrabar_equity = float(
            lowest_intrabar_point
            .intrabar_min_equity
        )

        lowest_intrabar_equity_time = (
            lowest_intrabar_point
            .timestamp
        )

        lowest_equity = float(
            lowest_equity_point.equity
        )

        lowest_equity_time = (
            lowest_equity_point.timestamp
        )

        # ----------------------------------------------------
        # Lowest realised balance
        # ----------------------------------------------------

        day_events = (
            events_by_day.get(
                trading_day,
                [],
            )
        )

        if day_events:

            lowest_balance_event = min(
                day_events,
                key=lambda event: (
                    event.balance_after
                ),
            )

            lowest_balance = min(
                start_balance,
                float(
                    lowest_balance_event
                    .balance_after
                ),
            )

            if (
                lowest_balance
                == start_balance
            ):

                lowest_balance_time = (
                    reset_time
                )

            else:

                lowest_balance_time = (
                    lowest_balance_event
                    .timestamp
                )

        else:

            lowest_balance = (
                start_balance
            )

            lowest_balance_time = (
                reset_time
            )

        # ----------------------------------------------------
        # Daily loss floor
        # ----------------------------------------------------

        daily_loss_floor = (
            _calculate_daily_loss_floor(
                config=config,

                initial_balance=(
                    backtest_result
                    .starting_balance
                ),

                day_start_balance=(
                    start_balance
                ),

                day_start_equity=(
                    start_equity
                ),
            )
        )

        # ----------------------------------------------------
        # No breach decision yet.
        #
        # That belongs to the next evaluation layer.
        # ----------------------------------------------------

        daily_state = PropDailyState(
            trading_day=(
                trading_day
            ),

            reset_time=(
                reset_time
            ),

            start_balance=float(
                start_balance
            ),

            start_equity=float(
                start_equity
            ),

            lowest_balance=float(
                lowest_balance
            ),

            lowest_balance_time=(
                lowest_balance_time
            ),

            lowest_equity=float(
                lowest_equity
            ),

            lowest_equity_time=(
                lowest_equity_time
            ),
            
            lowest_intrabar_equity=float(
                lowest_intrabar_equity
            ),

            lowest_intrabar_equity_time=(
                lowest_intrabar_equity_time
            ),            

            daily_loss_floor=(
                daily_loss_floor
            ),

            breached=False,
            breach_time=None,
            breach_value=None,
        )

        daily_states.append(
            daily_state
        )

    return daily_states

# ============================================================
# LOSS-FLOOR COMPARISON
# ============================================================

def _loss_floor_breached(
    observed_value: float,
    floor: float,
    breach_on_equal: bool,
) -> bool:
    """
    Return True when an observed account value breaches the
    configured loss floor.

    Parameters
    ----------
    observed_value : float
        Balance or equity being tested.

    floor : float
        Minimum permitted account value.

    breach_on_equal : bool
        If True:

            observed_value <= floor

        is considered a breach.

        If False:

            observed_value < floor

        is required.
    """

    if breach_on_equal:

        return bool(
            observed_value <= floor
        )

    return bool(
        observed_value < floor
    )


# ============================================================
# DAILY LOSS EVALUATION
# ============================================================

def evaluate_daily_loss_limits(
    backtest_result: BacktestResult,
    daily_states: List[PropDailyState],
    config: PropFirmConfig,
) -> List[PropDailyState]:
    """
    Evaluate generic daily-loss rules and record the first
    observed breach for each prop trading day.

    Balance-based rules use the exact account-event ledger.

    Equity-based rules currently use bar-close equity points.

    Intrabar worst-equity evaluation will be added separately.

    Returns
    -------
    List[PropDailyState]
        The supplied daily states with breach information
        populated.
    """

    if not daily_states:

        return daily_states

    # --------------------------------------------------------
    # Index daily states by prop trading day
    # --------------------------------------------------------

    state_by_day = {
        state.trading_day: state
        for state in daily_states
    }

    # --------------------------------------------------------
    # Reset any previous evaluation state
    # --------------------------------------------------------

    for state in daily_states:

        state.breached = False
        state.breach_time = None
        state.breach_value = None

    # --------------------------------------------------------
    # No daily-loss rule configured
    # --------------------------------------------------------

    if (
        config.daily_loss_pct is None
        and config.daily_loss_amount is None
    ):

        return daily_states

    # ========================================================
    # EQUITY-BASED DAILY LOSS
    # ========================================================

    if config.daily_loss_measure == "equity":

        for point in backtest_result.risk_curve:

            trading_day = (
                get_prop_trading_day(
                    timestamp=point.timestamp,
                    config=config,
                )
            )

            state = state_by_day.get(
                trading_day
            )

            if state is None:
                continue

            if state.daily_loss_floor is None:
                continue

            # First breach only.
            if state.breached:
                continue

            observed_equity = float(
                point.intrabar_min_equity
            )

            breached = (
                _loss_floor_breached(
                    observed_value=(
                        observed_equity
                    ),

                    floor=(
                        state.daily_loss_floor
                    ),

                    breach_on_equal=(
                        config.breach_on_equal
                    ),
                )
            )

            if breached:

                state.breached = True

                state.breach_time = (
                    point.timestamp
                )

                state.breach_value = (
                    observed_equity
                )

        return daily_states

    # ========================================================
    # BALANCE-BASED DAILY LOSS
    # ========================================================

    if config.daily_loss_measure == "balance":

        # ----------------------------------------------------
        # First test the balance at the beginning of each day.
        # ----------------------------------------------------

        for state in daily_states:

            if state.daily_loss_floor is None:
                continue

            if _loss_floor_breached(
                observed_value=(
                    state.start_balance
                ),

                floor=(
                    state.daily_loss_floor
                ),

                breach_on_equal=(
                    config.breach_on_equal
                ),
            ):

                state.breached = True
                state.breach_time = (
                    state.reset_time
                )
                state.breach_value = (
                    state.start_balance
                )

        # ----------------------------------------------------
        # Then scan exact realised-balance events.
        # ----------------------------------------------------

        for event in backtest_result.account_events:

            trading_day = (
                get_prop_trading_day(
                    timestamp=event.timestamp,
                    config=config,
                )
            )

            state = state_by_day.get(
                trading_day
            )

            if state is None:
                continue

            if state.daily_loss_floor is None:
                continue

            if state.breached:
                continue

            observed_balance = float(
                event.balance_after
            )

            breached = (
                _loss_floor_breached(
                    observed_value=(
                        observed_balance
                    ),

                    floor=(
                        state.daily_loss_floor
                    ),

                    breach_on_equal=(
                        config.breach_on_equal
                    ),
                )
            )

            if breached:

                state.breached = True

                state.breach_time = (
                    event.timestamp
                )

                state.breach_value = (
                    observed_balance
                )

        return daily_states

    # --------------------------------------------------------
    # Unsupported rule
    # --------------------------------------------------------

    raise ValueError(
        "Unsupported daily_loss_measure: "
        f"{config.daily_loss_measure}"
    )

# ============================================================
# TOTAL LOSS FLOOR
# ============================================================

def _calculate_total_loss_floor(
    config: PropFirmConfig,
    initial_balance: float,
) -> Optional[float]:
    """
    Calculate the overall loss floor.

    V1 currently implements:

        static_initial

    A fixed configured amount takes precedence over a
    percentage-based allowance.
    """

    if config.total_loss_amount is not None:

        loss_allowance = float(
            config.total_loss_amount
        )

    elif config.total_loss_pct is not None:

        loss_allowance = (
            initial_balance
            * config.total_loss_pct
        )

    else:

        return None

    if config.total_loss_model != "static_initial":

        raise NotImplementedError(
            "Generic prop evaluator currently implements "
            "only total_loss_model='static_initial'."
        )

    return float(
        initial_balance
        - loss_allowance
    )

# ============================================================
# TOTAL LOSS EVALUATION
# ============================================================

def evaluate_total_loss_limit(
    backtest_result: BacktestResult,
    config: PropFirmConfig,
) -> PropTotalLossState:
    """
    Evaluate the generic maximum-total-loss rule.

    V1 supports a static floor derived from initial balance.

    Equity-based evaluation currently uses bar-close equity.

    Balance-based evaluation uses the exact account-event
    ledger.

    Intrabar worst-equity evaluation will be added separately.
    """

    initial_balance = float(
        backtest_result.starting_balance
    )

    loss_floor = (
        _calculate_total_loss_floor(
            config=config,
            initial_balance=initial_balance,
        )
    )

    # --------------------------------------------------------
    # No total-loss rule configured
    # --------------------------------------------------------

    if loss_floor is None:

        first_timestamp = (
            backtest_result
            .equity_curve[0]
            .timestamp
        )

        return PropTotalLossState(
            loss_floor=None,

            lowest_value=initial_balance,
            lowest_value_time=first_timestamp,

            breached=False,
            breach_time=None,
            breach_value=None,
        )

    # ========================================================
    # EQUITY-BASED TOTAL LOSS
    # ========================================================

    if config.total_loss_measure == "equity":

        if not backtest_result.risk_curve:

            raise ValueError(
                "Cannot evaluate equity-based total loss "
                "because risk_curve is empty."
            )

        lowest_point = min(
            backtest_result.risk_curve,
            key=lambda point: (
                point.intrabar_min_equity
            ),
        )

        lowest_value = float(
            lowest_point.intrabar_min_equity
        )

        lowest_value_time = (
            lowest_point.timestamp
        )

        breach_time = None
        breach_value = None

        # ----------------------------------------------------
        # Find first observed breach
        # ----------------------------------------------------

        for point in backtest_result.risk_curve:

            observed_value = float(
                point.intrabar_min_equity
            )

            if _loss_floor_breached(
                observed_value=observed_value,
                floor=loss_floor,
                breach_on_equal=(
                    config.breach_on_equal
                ),
            ):

                breach_time = (
                    point.timestamp
                )

                breach_value = (
                    observed_value
                )

                break

        return PropTotalLossState(
            loss_floor=float(
                loss_floor
            ),

            lowest_value=(
                lowest_value
            ),

            lowest_value_time=(
                lowest_value_time
            ),

            breached=(
                breach_time is not None
            ),

            breach_time=(
                breach_time
            ),

            breach_value=(
                breach_value
            ),
        )

    # ========================================================
    # BALANCE-BASED TOTAL LOSS
    # ========================================================

    if config.total_loss_measure == "balance":

        if backtest_result.equity_curve:

            first_timestamp = (
                backtest_result
                .equity_curve[0]
                .timestamp
            )

        else:

            first_timestamp = pd.Timestamp(
                "1970-01-01",
                tz="UTC",
            )

        lowest_value = (
            initial_balance
        )

        lowest_value_time = (
            first_timestamp
        )

        breach_time = None
        breach_value = None

        # ----------------------------------------------------
        # Initial balance itself
        # ----------------------------------------------------

        if _loss_floor_breached(
            observed_value=initial_balance,
            floor=loss_floor,
            breach_on_equal=(
                config.breach_on_equal
            ),
        ):

            breach_time = (
                first_timestamp
            )

            breach_value = (
                initial_balance
            )

        # ----------------------------------------------------
        # Exact realised account events
        # ----------------------------------------------------

        for event in backtest_result.account_events:

            balance_after = float(
                event.balance_after
            )

            if balance_after < lowest_value:

                lowest_value = (
                    balance_after
                )

                lowest_value_time = (
                    event.timestamp
                )

            if breach_time is not None:

                continue

            if _loss_floor_breached(
                observed_value=balance_after,
                floor=loss_floor,
                breach_on_equal=(
                    config.breach_on_equal
                ),
            ):

                breach_time = (
                    event.timestamp
                )

                breach_value = (
                    balance_after
                )

        return PropTotalLossState(
            loss_floor=float(
                loss_floor
            ),

            lowest_value=float(
                lowest_value
            ),

            lowest_value_time=(
                lowest_value_time
            ),

            breached=(
                breach_time is not None
            ),

            breach_time=(
                breach_time
            ),

            breach_value=(
                breach_value
            ),
        )

    raise ValueError(
        "Unsupported total_loss_measure: "
        f"{config.total_loss_measure}"
    )

# ============================================================
# FIRST PROP RULE BREACH
# ============================================================

def get_first_prop_breach(
    daily_states: List[PropDailyState],
    total_loss_state: PropTotalLossState,
):
    """
    Return the first observed prop-rule breach.

    Returns
    -------
    tuple
        (
            breach_rule,
            breach_time,
            breach_value,
        )

    If no breach occurred:

        (None, None, None)
    """

    breach_candidates = []

    # --------------------------------------------------------
    # Daily-loss breaches
    # --------------------------------------------------------

    for state in daily_states:

        if not state.breached:
            continue

        if state.breach_time is None:
            continue

        breach_candidates.append(
            (
                state.breach_time,
                "daily_loss",
                state.breach_value,
            )
        )

    # --------------------------------------------------------
    # Total-loss breach
    # --------------------------------------------------------

    if (
        total_loss_state.breached
        and total_loss_state.breach_time is not None
    ):

        breach_candidates.append(
            (
                total_loss_state.breach_time,
                "total_loss",
                total_loss_state.breach_value,
            )
        )

    # --------------------------------------------------------
    # No breach
    # --------------------------------------------------------

    if not breach_candidates:

        return (
            None,
            None,
            None,
        )

    # --------------------------------------------------------
    # Earliest breach wins
    # --------------------------------------------------------

    breach_candidates.sort(
        key=lambda item: item[0]
    )

    first = breach_candidates[0]

    return (
        first[1],
        first[0],
        first[2],
    )

# ============================================================
# PROP TRADING DAYS
# ============================================================

def get_prop_trading_days(
    backtest_result: BacktestResult,
    config: PropFirmConfig,
) -> List[date]:
    """
    Return unique prop trading days on which actual trading
    activity occurred.

    V1 activity definition:

        entry

    A prop day counts when at least one position was opened
    during that prop trading day.

    Closed trades are inspected through Trade.entry_time.

    If the backtest finishes with a position still open, that
    position's entry day is also counted.
    """

    if config.trading_day_activity_basis != "entry":

        raise NotImplementedError(
            "V1 prop evaluator currently supports only "
            "trading_day_activity_basis='entry'."
        )

    trading_days = set()

    # --------------------------------------------------------
    # Completed trades
    # --------------------------------------------------------

    for trade in backtest_result.trades:

        entry_time = pd.Timestamp(
            trade.entry_time
        )

        if entry_time.tzinfo is None:

            raise ValueError(
                "Trade entry_time must be timezone-aware."
            )

        trading_day = (
            get_prop_trading_day(
                timestamp=entry_time,
                config=config,
            )
        )

        trading_days.add(
            trading_day
        )

    # --------------------------------------------------------
    # Position still open at dataset end
    # --------------------------------------------------------

    if backtest_result.open_position is not None:

        entry_time = pd.Timestamp(
            backtest_result
            .open_position
            .entry_time
        )

        if entry_time.tzinfo is None:

            raise ValueError(
                "Open-position entry_time must be "
                "timezone-aware."
            )

        trading_day = (
            get_prop_trading_day(
                timestamp=entry_time,
                config=config,
            )
        )

        trading_days.add(
            trading_day
        )

    return sorted(
        trading_days
    )

# ============================================================
# PROP TRADING DAYS UP TO TIMESTAMP
# ============================================================

def get_prop_trading_days_up_to(
    backtest_result: BacktestResult,
    config: PropFirmConfig,
    cutoff_time: Optional[pd.Timestamp],
) -> List[date]:
    """
    Return unique prop trading days containing trade entries
    up to and including a supplied timestamp.

    If cutoff_time is None, all trading days are returned.

    This is useful for determining the number of trading days
    completed before:

        challenge failure
        challenge pass
        dataset end
    """

    if cutoff_time is None:

        return get_prop_trading_days(
            backtest_result=backtest_result,
            config=config,
        )

    cutoff_time = pd.Timestamp(
        cutoff_time
    )

    if cutoff_time.tzinfo is None:

        raise ValueError(
            "cutoff_time must be timezone-aware."
        )

    trading_days = set()

    # --------------------------------------------------------
    # Completed trades
    # --------------------------------------------------------

    for trade in backtest_result.trades:

        entry_time = pd.Timestamp(
            trade.entry_time
        )

        if entry_time.tzinfo is None:

            raise ValueError(
                "Trade entry_time must be timezone-aware."
            )

        if entry_time > cutoff_time:

            continue

        trading_day = (
            get_prop_trading_day(
                timestamp=entry_time,
                config=config,
            )
        )

        trading_days.add(
            trading_day
        )

    # --------------------------------------------------------
    # Open position
    # --------------------------------------------------------

    if backtest_result.open_position is not None:

        entry_time = pd.Timestamp(
            backtest_result
            .open_position
            .entry_time
        )

        if entry_time.tzinfo is None:

            raise ValueError(
                "Open-position entry_time must be "
                "timezone-aware."
            )

        if entry_time <= cutoff_time:

            trading_day = (
                get_prop_trading_day(
                    timestamp=entry_time,
                    config=config,
                )
            )

            trading_days.add(
                trading_day
            )

    return sorted(
        trading_days
    )

# ============================================================
# MASTER PROP EVALUATION
# ============================================================

def evaluate_prop_firm(
    backtest_result: BacktestResult,
    config: PropFirmConfig,
) -> PropEvaluationResult:
    """
    Perform one complete generic prop-firm evaluation.

    V1 supports:

        profit target
        minimum trading days
        daily loss
        static total loss
        intrabar equity loss evaluation

    Provider-specific values belong in PropFirmConfig presets,
    not in this evaluator.
    """

    # --------------------------------------------------------
    # V1 limitation
    # --------------------------------------------------------

    if config.maximum_trading_days is not None:

        raise NotImplementedError(
            "maximum_trading_days evaluation has not yet "
            "been implemented."
        )

    # ========================================================
    # DAILY STATES
    # ========================================================

    daily_states = (
        build_prop_daily_states(
            backtest_result=(
                backtest_result
            ),
            config=config,
        )
    )

    daily_states = (
        evaluate_daily_loss_limits(
            backtest_result=(
                backtest_result
            ),
            daily_states=(
                daily_states
            ),
            config=config,
        )
    )

    # ========================================================
    # TOTAL LOSS
    # ========================================================

    total_loss_state = (
        evaluate_total_loss_limit(
            backtest_result=(
                backtest_result
            ),
            config=config,
        )
    )

    # ========================================================
    # FIRST FAILURE
    # ========================================================

    (
        breach_rule,
        breach_time,
        breach_value,
    ) = get_first_prop_breach(
        daily_states=daily_states,
        total_loss_state=(
            total_loss_state
        ),
    )

    # ========================================================
    # FIRST VALID PASS
    # ========================================================

    (
        pass_time,
        pass_value,
    ) = get_first_valid_pass(
        backtest_result=(
            backtest_result
        ),
        config=config,
    )

    # ========================================================
    # DETERMINE STATUS
    #
    # Failure wins if failure occurs before or at the same
    # timestamp as a possible pass.
    # ========================================================

    if (
        breach_time is not None
        and (
            pass_time is None
            or breach_time <= pass_time
        )
    ):

        status = "FAILED"

        outcome_time = (
            breach_time
        )

    elif pass_time is not None:

        status = "PASSED"

        outcome_time = (
            pass_time
        )

    else:

        status = "ACTIVE"

        if backtest_result.equity_curve:

            outcome_time = (
                backtest_result
                .equity_curve[
                    -1
                ]
                .timestamp
            )

        else:

            outcome_time = None

    # ========================================================
    # TRADING DAYS AT OUTCOME
    # ========================================================

    trading_days_at_outcome = (
        get_prop_trading_days_up_to(
            backtest_result=(
                backtest_result
            ),
            config=config,
            cutoff_time=(
                outcome_time
            ),
        )
    )

    # ========================================================
    # PROFIT TARGET
    # ========================================================

    (
        profit_target_amount,
        profit_target_balance,
    ) = _calculate_profit_target(
        backtest_result=(
            backtest_result
        ),
        config=config,
    )

    # ========================================================
    # RESULT
    # ========================================================

    return PropEvaluationResult(
        provider_name=(
            config.provider_name
        ),

        programme_name=(
            config.programme_name
        ),

        phase_name=(
            config.phase_name
        ),

        status=(
            status
        ),

        starting_balance=float(
            backtest_result.starting_balance
        ),

        ending_balance=float(
            backtest_result.ending_balance
        ),

        ending_equity=float(
            backtest_result.ending_equity
        ),

        outcome_time=(
            outcome_time
        ),

        trading_days=len(
            trading_days_at_outcome
        ),

        profit_target_amount=(
            profit_target_amount
        ),

        profit_target_balance=(
            profit_target_balance
        ),

        profit_target_hit=(
            pass_time is not None
        ),

        profit_target_time=(
            pass_time
        ),

        profit_target_value=(
            pass_value
        ),

        total_loss_floor=(
            total_loss_state.loss_floor
        ),

        breach_rule=(
            breach_rule
        ),

        breach_time=(
            breach_time
        ),

        breach_value=(
            breach_value
        ),

        daily_states=(
            daily_states
        ),
    )