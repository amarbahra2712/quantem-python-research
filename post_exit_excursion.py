# -*- coding: utf-8 -*-
"""
Created on Wed Sep 16 14:05:34 2026

@author: quant
"""

"""
NEXUS Post-Exit Excursion Analysis
==================================

Purpose
-------
Analyse favourable price movement that occurs after a real
NEXUS trade has already exited.

The module asks counterfactual research questions such as:

    "What would the maximum favourable excursion have been if
    the original trade had remained open after its real exit?"

Two post-exit holding scenarios are currently defined.

Scenario 1 - Same-Day Runner
----------------------------
After the real trade exits, hypothetically keep the original
position open until whichever occurs first:

    1. the original stop price is hit, or
    2. the next applicable 17:00 New York FX close is reached.
        If the trade exits before 17:00 New York, that day's
        close is used.

If the trade exits after 17:00 New York, the next valid
weekday 17:00 New York close is used.

The New York close is timezone-aware and therefore naturally
handles US daylight-saving changes.

Scenario 2 - Until-Stop Runner
------------------------------
After the real trade exits, hypothetically keep the original
position open without a time limit until the original stop
price is eventually hit.

If the historical dataset ends before the original stop is
hit, the observation is marked as censored rather than
pretending that the stop occurred.

Responsibilities
----------------
- Analyse post-exit favourable movement for completed trades.
- Preserve the original trade entry price and original stop.
- Calculate potential MFE in raw price distance.
- Calculate potential MFE in R.
- Calculate additional MFE beyond the real trade's MFE.
- Measure the duration of each hypothetical post-exit holding
  scenario.
- Record when post-exit price action creates a new MFE beyond
  the actual trade MFE.
- Record how long after the real exit that new maximum took
  to occur.
- Record why each hypothetical holding scenario ended.
- Identify observations truncated by the end of the available
  historical dataset.

Does Not
--------
- Modify the original Trade.
- Modify NexusEngine.
- Recalculate realised trade P&L.
- Change historical account balance or equity.
- Assume that the hypothetical position was actually held.
- Apply hypothetical partial exits.
- Apply trailing stops.
- Apply breakeven rules.
- Calculate hypothetical swap, commission, or rollover costs.
- Generate strategy signals.
- Use midpoint prices as executable prices.
- Use unknown movement after the real exit within the same
  OHLC exit bar.

Original Stop Convention
------------------------
Both hypothetical scenarios use:

    trade.initial_stop_price

rather than any later active stop or breakeven stop.

The research question is therefore:

    "What might have happened if the original setup had simply
    been allowed to continue until its original invalidation?"

Executable Price Convention
---------------------------
Long positions:

    favourable excursion -> BID high
    original stop hit     -> BID low

Short positions:

    favourable excursion -> ASK low
    original stop hit     -> ASK high

This is consistent with NEXUS execution conventions.

Exit-Bar Convention
-------------------
Post-exit analysis begins on the first complete historical bar
AFTER the real trade's exit bar.

The remainder of the actual exit candle is deliberately
ignored.

OHLC data cannot reveal whether movement elsewhere within that
bar occurred before or after the real exit. Starting on the
next bar avoids introducing artificial look-ahead or invented
intrabar sequencing.

Stop-First Convention
---------------------
If a future bar touches both:

    - the original stop, and
    - a new favourable extreme,

the original stop is assumed to occur first.

No new favourable excursion from that bar is credited.

This conservative assumption is consistent with the current
NexusEngine same-bar policy.

Potential MFE Convention
------------------------
Potential MFE represents the greatest favourable excursion
from the ORIGINAL ENTRY PRICE over:

    actual trade life
    +
    hypothetical post-exit extension

Therefore:

    potential_mfe_r >= actual_mfe_r

Additional MFE is:

    potential_mfe_r - actual_mfe_r

Example:

    actual trade exits at 2.0R

    hypothetical extension later reaches 5.3R
    before the original stop is hit

then:

    actual_mfe_r       = 2.0R
    potential_mfe_r    = 5.3R
    additional_mfe_r   = 3.3R

Duration Convention
-------------------
extension_duration measures the elapsed time from the REAL
trade exit until the hypothetical scenario ends.

For the same-day scenario this may end because of:

    original_stop
    original_stop_already_hit
    ny_close
    end_of_data

For the until-stop scenario this may end because of:

    original_stop
    end_of_data

If the dataset ends before the intended termination condition
is observed, censored is True.

new_peak_time records the timestamp of the post-exit bar that
creates the greatest MFE beyond the actual trade MFE.

time_to_new_peak measures elapsed time from the real exit to
that bar.

If post-exit price never exceeds the actual trade MFE:

    new_peak_time    = None
    time_to_new_peak = None

New York Close
--------------
The default same-day close is:

    17:00 America/New_York

This is intentionally timezone-aware rather than hard-coded
as a UTC hour because the corresponding UTC time changes with
US daylight-saving time.

Architecture
------------
NexusEngine records:

    WHAT ACTUALLY HAPPENED

This module evaluates:

    WHAT MIGHT HAVE HAPPENED AFTER EXIT

Post-exit excursion therefore belongs in:

    06_analysis

rather than:

    04_engine

Future Extensions
-----------------
Possible later additions include:

- probability of reaching 3R / 4R / 5R / 10R
- distributions of additional MFE
- comparison by actual exit reason
- comparison by strategy/session/direction
- hypothetical runner P&L
- hypothetical trailing-stop analysis
- hypothetical post-exit financing and rollover costs
- end-of-session definitions other than New York close

Notes
-----
All calculations should retain full floating-point precision.

Rounding belongs in reporting rather than analysis.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional

import pandas as pd

from nexus_engine import BacktestResult, Trade

# ============================================================
# ANALYSIS CONFIGURATION
# ============================================================

@dataclass(frozen=True)
class PostExitConfig:
    """
    Configuration for post-exit excursion analysis.
    """

    ny_timezone: str = "America/New_York"

    ny_close_hour: int = 17
    ny_close_minute: int = 0

    same_bar_policy: str = "stop_first"


# ============================================================
# SCENARIO RESULT
# ============================================================

@dataclass
class PostExitScenarioResult:
    """
    Result of one hypothetical post-exit holding scenario.
    """

    scenario_name: str

    # --------------------------------------------------------
    # Potential excursion
    # --------------------------------------------------------

    potential_mfe_price_distance: float
    potential_mfe_r: float

    additional_mfe_r: float

    # --------------------------------------------------------
    # New post-exit maximum
    # --------------------------------------------------------

    new_peak_time: Optional[pd.Timestamp]
    time_to_new_peak: Optional[pd.Timedelta]

    # --------------------------------------------------------
    # Scenario termination
    # --------------------------------------------------------

    end_time: pd.Timestamp
    end_reason: str

    extension_duration: pd.Timedelta

    # --------------------------------------------------------
    # Diagnostic information
    # --------------------------------------------------------

    bars_examined: int

    censored: bool


# ============================================================
# COMPLETE TRADE RESULT
# ============================================================

@dataclass
class PostExitExcursion:
    """
    Post-exit excursion analysis for one completed NEXUS trade.
    """

    trade_number: int

    entry_time: pd.Timestamp
    exit_time: pd.Timestamp

    direction: int

    actual_exit_reason: str

    entry_price: float

    initial_stop_price: float
    initial_risk_distance: float

    actual_mfe_r: float

    # --------------------------------------------------------
    # Counterfactual scenarios
    # --------------------------------------------------------

    same_day: PostExitScenarioResult
    until_stop: PostExitScenarioResult

# ============================================================
# AGGREGATE STATISTICS MODELS
# ============================================================

@dataclass
class PostExitScenarioStatistics:
    """
    Aggregate statistics for one post-exit scenario.

    Censored observations are reported separately and are
    excluded from completed-scenario averages, medians,
    durations, and threshold rates.
    """

    eligible_trades: int

    completed_observations: int
    censored_observations: int

    termination_counts: Dict[str, int]

    # --------------------------------------------------------
    # Potential excursion
    # --------------------------------------------------------

    average_potential_mfe_r: float
    median_potential_mfe_r: float

    average_additional_mfe_r: float
    median_additional_mfe_r: float

    # --------------------------------------------------------
    # New post-exit peak
    # --------------------------------------------------------

    new_peak_count: int
    new_peak_rate: float

    average_time_to_new_peak: Optional[pd.Timedelta]
    median_time_to_new_peak: Optional[pd.Timedelta]

    # --------------------------------------------------------
    # Scenario duration
    # --------------------------------------------------------

    average_extension_duration: Optional[pd.Timedelta]
    median_extension_duration: Optional[pd.Timedelta]

    # --------------------------------------------------------
    # R thresholds
    # --------------------------------------------------------

    threshold_counts: Dict[float, int]
    threshold_rates: Dict[float, float]


@dataclass
class PostExitStatistics:
    """
    Aggregate post-exit statistics across a complete backtest.
    """

    total_trades: int
    eligible_trades: int

    same_day: PostExitScenarioStatistics
    until_stop: PostExitScenarioStatistics    

# ============================================================
# TIME HELPERS
# ============================================================

def _get_next_ny_close(
    exit_time: pd.Timestamp,
    config: PostExitConfig,
) -> pd.Timestamp:
    """
    Return the next applicable 17:00 New York FX close.

    If the real trade exits before or exactly at 17:00
    New York on a valid weekday, that day's close is used.

    If the trade exits after 17:00 New York, the next valid
    weekday 17:00 New York close is used.

    Saturday and Sunday are skipped because they are not
    normal FX daily-close dates.

    The returned timestamp uses the same timezone as
    exit_time.
    """

    exit_time = pd.Timestamp(
        exit_time
    )

    if exit_time.tzinfo is None:
        raise ValueError(
            "Trade exit_time must be timezone-aware."
        )

    exit_ny = exit_time.tz_convert(
        config.ny_timezone
    )

    candidate_date = exit_ny.date()

    while True:

        ny_close_naive = pd.Timestamp(
            year=candidate_date.year,
            month=candidate_date.month,
            day=candidate_date.day,
            hour=config.ny_close_hour,
            minute=config.ny_close_minute,
        )

        ny_close = ny_close_naive.tz_localize(
            config.ny_timezone
        )

        # ----------------------------------------------------
        # Valid FX close day: Monday-Friday
        # ----------------------------------------------------

        valid_weekday = (
            ny_close.weekday() <= 4
        )

        # ----------------------------------------------------
        # Use today's close if it has not yet passed.
        # ----------------------------------------------------

        if (
            valid_weekday
            and exit_ny <= ny_close
        ):

            return ny_close.tz_convert(
                exit_time.tz
            )

        # ----------------------------------------------------
        # Otherwise examine the next calendar date.
        # ----------------------------------------------------

        candidate_date = (
            pd.Timestamp(candidate_date)
            + pd.Timedelta(days=1)
        ).date()


# ============================================================
# PRICE HELPERS
# ============================================================

def _original_stop_hit(
    trade: Trade,
    bar: pd.Series,
) -> bool:
    """
    Return True if the trade's original stop is touched
    during the supplied historical bar.
    """

    if trade.initial_stop_price is None:
        raise ValueError(
            "Post-exit analysis requires "
            "initial_stop_price."
        )

    stop_price = float(
        trade.initial_stop_price
    )

    if trade.direction == 1:

        if "bid_low" not in bar.index:
            raise ValueError(
                "Required column missing: bid_low"
            )

        return (
            float(bar["bid_low"])
            <= stop_price
        )

    if trade.direction == -1:

        if "ask_high" not in bar.index:
            raise ValueError(
                "Required column missing: ask_high"
            )

        return (
            float(bar["ask_high"])
            >= stop_price
        )

    raise ValueError(
        f"Invalid trade direction: "
        f"{trade.direction}"
    )


def _get_favourable_distance(
    trade: Trade,
    bar: pd.Series,
) -> float:
    """
    Return favourable executable price distance from the
    original entry price for one historical bar.

    Returned distance is always non-negative.
    """

    if trade.direction == 1:

        if "bid_high" not in bar.index:
            raise ValueError(
                "Required column missing: bid_high"
            )

        return max(
            0.0,
            float(bar["bid_high"])
            - trade.entry_price,
        )

    if trade.direction == -1:

        if "ask_low" not in bar.index:
            raise ValueError(
                "Required column missing: ask_low"
            )

        return max(
            0.0,
            trade.entry_price
            - float(bar["ask_low"]),
        )

    raise ValueError(
        f"Invalid trade direction: "
        f"{trade.direction}"
    )
    
# ============================================================
# SAME-DAY RUNNER
# ============================================================

def _calculate_same_day_scenario(
    trade: Trade,
    market_data: pd.DataFrame,
    exit_index: int,
    config: PostExitConfig,
) -> PostExitScenarioResult:
    """
    Calculate hypothetical post-exit MFE if the original
    position remained open until:

        original stop hit

    or:

        17:00 New York time on the same New York calendar day

    whichever occurs first.

    Analysis begins on the first complete bar after the real
    trade exit.

    Stop-first logic is used if a future bar both touches the
    original stop and contains a new favourable extreme.
    """

    if config.same_bar_policy != "stop_first":
        raise NotImplementedError(
            "Post-exit analysis currently supports only "
            "same_bar_policy='stop_first'."
        )

    if trade.initial_stop_price is None:
        raise ValueError(
            "Post-exit analysis requires "
            "trade.initial_stop_price."
        )

    if trade.initial_risk_distance <= 0:
        raise ValueError(
            "trade.initial_risk_distance must be positive."
        )

    if "timestamp" not in market_data.columns:
        raise ValueError(
            "market_data must contain timestamp."
        )

    exit_time = pd.Timestamp(
        trade.exit_time
    )

    if exit_time.tzinfo is None:
        raise ValueError(
            "Trade exit_time must be timezone-aware."
        )
        
    # --------------------------------------------------------
    # Original stop already hit in the real trade
    # --------------------------------------------------------

    if trade.exit_reason == "stop":

        return PostExitScenarioResult(
            scenario_name="same_day",

            potential_mfe_price_distance=float(
                trade.mfe_price_distance
            ),

            potential_mfe_r=float(
                trade.mfe_r
            ),

            additional_mfe_r=0.0,

            new_peak_time=None,
            time_to_new_peak=None,

            end_time=exit_time,
            end_reason="original_stop_already_hit",

            extension_duration=pd.Timedelta(0),

            bars_examined=0,

            censored=False,
        )    

    # --------------------------------------------------------
    # Same-day New York close
    # --------------------------------------------------------

    ny_close = _get_next_ny_close(
        exit_time=exit_time,
        config=config,
    )

    
    # --------------------------------------------------------
    # Initial state
    # --------------------------------------------------------

    potential_mfe_distance = float(
        trade.mfe_price_distance
    )

    potential_mfe_r = float(
        trade.mfe_r
    )

    new_peak_time = None

    bars_examined = 0

    # --------------------------------------------------------
    # Begin on first COMPLETE bar after real exit
    # --------------------------------------------------------

    start_index = exit_index + 1

    # --------------------------------------------------------
    # Walk forward
    # --------------------------------------------------------

    for row_position in range(
        start_index,
        len(market_data),
    ):

        bar = market_data.iloc[
            row_position
        ]

        bar_time = pd.Timestamp(
            bar["timestamp"]
        )

        if bar_time.tzinfo is None:
            raise ValueError(
                "market_data timestamps must be "
                "timezone-aware."
            )

        # ----------------------------------------------------
        # NY close reached
        #
        # A bar timestamped exactly at the NY close is NOT
        # included because it begins at/after our cutoff.
        # ----------------------------------------------------

        if bar_time >= ny_close:

            break

        bars_examined += 1

        # ----------------------------------------------------
        # Conservative stop-first handling
        # ----------------------------------------------------

        if _original_stop_hit(
            trade=trade,
            bar=bar,
        ):

            end_time = bar_time

            extension_duration = (
                end_time - exit_time
            )

            if new_peak_time is not None:

                time_to_new_peak = (
                    new_peak_time
                    - exit_time
                )

            else:

                time_to_new_peak = None

            return PostExitScenarioResult(
                scenario_name="same_day",

                potential_mfe_price_distance=float(
                    potential_mfe_distance
                ),

                potential_mfe_r=float(
                    potential_mfe_r
                ),

                additional_mfe_r=float(
                    max(
                        0.0,
                        potential_mfe_r
                        - trade.mfe_r,
                    )
                ),

                new_peak_time=new_peak_time,
                time_to_new_peak=time_to_new_peak,

                end_time=end_time,
                end_reason="original_stop",

                extension_duration=(
                    extension_duration
                ),

                bars_examined=bars_examined,

                censored=False,
            )

        # ----------------------------------------------------
        # Favourable excursion
        # ----------------------------------------------------

        favourable_distance = (
            _get_favourable_distance(
                trade=trade,
                bar=bar,
            )
        )

        favourable_r = (
            favourable_distance
            / trade.initial_risk_distance
        )

        if favourable_r > potential_mfe_r:

            potential_mfe_distance = (
                favourable_distance
            )

            potential_mfe_r = (
                favourable_r
            )

            new_peak_time = bar_time

    # --------------------------------------------------------
    # No stop before NY close
    # --------------------------------------------------------

    final_data_time = pd.Timestamp(
        market_data.iloc[-1]["timestamp"]
    )

    # Dataset ends before the required NY close.
    if final_data_time < ny_close:

        end_time = final_data_time
        end_reason = "end_of_data"
        censored = True

    else:

        end_time = ny_close
        end_reason = "ny_close"
        censored = False

    extension_duration = (
        end_time - exit_time
    )

    if new_peak_time is not None:

        time_to_new_peak = (
            new_peak_time
            - exit_time
        )

    else:

        time_to_new_peak = None

    return PostExitScenarioResult(
        scenario_name="same_day",

        potential_mfe_price_distance=float(
            potential_mfe_distance
        ),

        potential_mfe_r=float(
            potential_mfe_r
        ),

        additional_mfe_r=float(
            max(
                0.0,
                potential_mfe_r
                - trade.mfe_r,
            )
        ),

        new_peak_time=new_peak_time,
        time_to_new_peak=time_to_new_peak,

        end_time=end_time,
        end_reason=end_reason,

        extension_duration=(
            extension_duration
        ),

        bars_examined=bars_examined,

        censored=censored,
    )

# ============================================================
# UNTIL-ORIGINAL-STOP RUNNER
# ============================================================

def _calculate_until_stop_scenario(
    trade: Trade,
    market_data: pd.DataFrame,
    exit_index: int,
    config: PostExitConfig,
) -> PostExitScenarioResult:
    """
    Calculate hypothetical post-exit MFE if the original
    position remained open indefinitely until its original
    stop was hit.

    If the historical dataset ends before the original stop
    is observed, the result is marked as censored.

    Analysis begins on the first complete bar after the real
    trade exit.

    Stop-first logic is used if a future bar both touches the
    original stop and contains a new favourable extreme.
    """

    if config.same_bar_policy != "stop_first":
        raise NotImplementedError(
            "Post-exit analysis currently supports only "
            "same_bar_policy='stop_first'."
        )

    if trade.initial_stop_price is None:
        raise ValueError(
            "Post-exit analysis requires "
            "trade.initial_stop_price."
        )

    if trade.initial_risk_distance <= 0:
        raise ValueError(
            "trade.initial_risk_distance must be positive."
        )

    if "timestamp" not in market_data.columns:
        raise ValueError(
            "market_data must contain timestamp."
        )

    exit_time = pd.Timestamp(
        trade.exit_time
    )

    if exit_time.tzinfo is None:
        raise ValueError(
            "Trade exit_time must be timezone-aware."
        )

    # --------------------------------------------------------
    # If the real trade already exited at its original stop,
    # there is no meaningful post-exit continuation.
    # --------------------------------------------------------

    if trade.exit_reason == "stop":

        return PostExitScenarioResult(
            scenario_name="until_stop",

            potential_mfe_price_distance=float(
                trade.mfe_price_distance
            ),

            potential_mfe_r=float(
                trade.mfe_r
            ),

            additional_mfe_r=0.0,

            new_peak_time=None,
            time_to_new_peak=None,

            end_time=exit_time,
            end_reason="original_stop_already_hit",

            extension_duration=pd.Timedelta(0),

            bars_examined=0,

            censored=False,
        )

    # --------------------------------------------------------
    # Initial state
    # --------------------------------------------------------

    potential_mfe_distance = float(
        trade.mfe_price_distance
    )

    potential_mfe_r = float(
        trade.mfe_r
    )

    new_peak_time = None

    bars_examined = 0

    # --------------------------------------------------------
    # Start on first complete bar after real exit
    # --------------------------------------------------------

    start_index = exit_index + 1

    # --------------------------------------------------------
    # Walk forward until original stop or end of data
    # --------------------------------------------------------

    for row_position in range(
        start_index,
        len(market_data),
    ):

        bar = market_data.iloc[
            row_position
        ]

        bar_time = pd.Timestamp(
            bar["timestamp"]
        )

        if bar_time.tzinfo is None:
            raise ValueError(
                "market_data timestamps must be "
                "timezone-aware."
            )

        bars_examined += 1

        # ----------------------------------------------------
        # Conservative stop-first handling
        # ----------------------------------------------------

        if _original_stop_hit(
            trade=trade,
            bar=bar,
        ):

            end_time = bar_time

            extension_duration = (
                end_time - exit_time
            )

            if new_peak_time is not None:

                time_to_new_peak = (
                    new_peak_time
                    - exit_time
                )

            else:

                time_to_new_peak = None

            return PostExitScenarioResult(
                scenario_name="until_stop",

                potential_mfe_price_distance=float(
                    potential_mfe_distance
                ),

                potential_mfe_r=float(
                    potential_mfe_r
                ),

                additional_mfe_r=float(
                    max(
                        0.0,
                        potential_mfe_r
                        - trade.mfe_r,
                    )
                ),

                new_peak_time=new_peak_time,
                time_to_new_peak=time_to_new_peak,

                end_time=end_time,
                end_reason="original_stop",

                extension_duration=(
                    extension_duration
                ),

                bars_examined=bars_examined,

                censored=False,
            )

        # ----------------------------------------------------
        # Favourable excursion
        # ----------------------------------------------------

        favourable_distance = (
            _get_favourable_distance(
                trade=trade,
                bar=bar,
            )
        )

        favourable_r = (
            favourable_distance
            / trade.initial_risk_distance
        )

        if favourable_r > potential_mfe_r:

            potential_mfe_distance = (
                favourable_distance
            )

            potential_mfe_r = (
                favourable_r
            )

            new_peak_time = bar_time

    # --------------------------------------------------------
    # Dataset ended before original stop
    # --------------------------------------------------------

    if len(market_data) > 0:

        end_time = pd.Timestamp(
            market_data.iloc[-1]["timestamp"]
        )

    else:

        end_time = exit_time

    extension_duration = (
        end_time - exit_time
    )

    if new_peak_time is not None:

        time_to_new_peak = (
            new_peak_time
            - exit_time
        )

    else:

        time_to_new_peak = None

    return PostExitScenarioResult(
        scenario_name="until_stop",

        potential_mfe_price_distance=float(
            potential_mfe_distance
        ),

        potential_mfe_r=float(
            potential_mfe_r
        ),

        additional_mfe_r=float(
            max(
                0.0,
                potential_mfe_r
                - trade.mfe_r,
            )
        ),

        new_peak_time=new_peak_time,
        time_to_new_peak=time_to_new_peak,

        end_time=end_time,
        end_reason="end_of_data",

        extension_duration=(
            extension_duration
        ),

        bars_examined=bars_examined,

        censored=True,
    )

# ============================================================
# PUBLIC POST-EXIT ANALYSIS
# ============================================================

def calculate_post_exit_excursions(
    market_data: pd.DataFrame,
    backtest_result: BacktestResult,
    config: Optional[PostExitConfig] = None,
) -> List[PostExitExcursion]:
    """
    Calculate post-exit excursion analysis for every completed
    trade in a NEXUS BacktestResult.

    Two counterfactual scenarios are calculated for each trade:

        1. Same-day runner:
           original stop or same-day New York close,
           whichever occurs first.

        2. Until-stop runner:
           continue indefinitely until the original stop is
           hit or historical data ends.

    Parameters
    ----------
    market_data : pd.DataFrame
        Canonical NEXUS historical market data.

    backtest_result : BacktestResult
        Completed result produced by NexusEngine.

    config : PostExitConfig, optional
        Post-exit analysis configuration.

    Returns
    -------
    List[PostExitExcursion]
        One analysis result for every completed trade.
    """

    if config is None:
        config = PostExitConfig()

    # --------------------------------------------------------
    # Basic market-data validation
    # --------------------------------------------------------

    required_columns = [
        "timestamp",
        "bid_high",
        "bid_low",
        "ask_high",
        "ask_low",
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in market_data.columns
    ]

    if missing_columns:

        raise ValueError(
            "Post-exit market data is missing required "
            f"columns: {missing_columns}"
        )

    if market_data.empty:

        raise ValueError(
            "Cannot calculate post-exit excursions because "
            "market_data is empty."
        )

    # --------------------------------------------------------
    # Timestamp validation
    # --------------------------------------------------------

    timestamps = market_data[
        "timestamp"
    ]

    if timestamps.isna().any():

        raise ValueError(
            "market_data contains missing timestamps."
        )

    if not timestamps.is_monotonic_increasing:

        raise ValueError(
            "market_data timestamps must be in ascending "
            "chronological order."
        )

    if timestamps.duplicated().any():

        raise ValueError(
            "market_data contains duplicate timestamps."
        )

    first_timestamp = pd.Timestamp(
        timestamps.iloc[0]
    )

    if first_timestamp.tzinfo is None:

        raise ValueError(
            "market_data timestamps must be timezone-aware."
        )

    # --------------------------------------------------------
    # Nothing to analyse
    # --------------------------------------------------------

    if not backtest_result.trades:
        return []

    # --------------------------------------------------------
    # Timestamp -> integer row-position lookup
    # --------------------------------------------------------

    timestamp_positions = {
        pd.Timestamp(timestamp): position
        for position, timestamp
        in enumerate(timestamps)
    }

    results = []

    # --------------------------------------------------------
    # Analyse each completed trade
    # --------------------------------------------------------

    for trade_number, trade in enumerate(
        backtest_result.trades,
        start=1,
    ):

        exit_time = pd.Timestamp(
            trade.exit_time
        )

        if exit_time not in timestamp_positions:

            raise ValueError(
                "Trade exit timestamp was not found in "
                "market_data: "
                f"{exit_time}"
            )

        if trade.initial_stop_price is None:

            raise ValueError(
                "Post-exit analysis requires an original "
                "stop price for every trade."
            )

        if trade.initial_risk_distance <= 0:

            raise ValueError(
                "Post-exit analysis requires positive "
                "initial risk distance."
            )

        exit_index = timestamp_positions[
            exit_time
        ]

        # ----------------------------------------------------
        # Scenario 1 - same-day runner
        # ----------------------------------------------------

        same_day_result = (
            _calculate_same_day_scenario(
                trade=trade,
                market_data=market_data,
                exit_index=exit_index,
                config=config,
            )
        )

        # ----------------------------------------------------
        # Scenario 2 - until-original-stop runner
        # ----------------------------------------------------

        until_stop_result = (
            _calculate_until_stop_scenario(
                trade=trade,
                market_data=market_data,
                exit_index=exit_index,
                config=config,
            )
        )

        # ----------------------------------------------------
        # Combined trade result
        # ----------------------------------------------------

        excursion = PostExitExcursion(
            trade_number=trade_number,

            entry_time=trade.entry_time,
            exit_time=trade.exit_time,

            direction=trade.direction,

            actual_exit_reason=(
                trade.exit_reason
            ),

            entry_price=float(
                trade.entry_price
            ),

            initial_stop_price=float(
                trade.initial_stop_price
            ),

            initial_risk_distance=float(
                trade.initial_risk_distance
            ),

            actual_mfe_r=float(
                trade.mfe_r
            ),

            same_day=same_day_result,
            until_stop=until_stop_result,
        )

        results.append(
            excursion
        )

    return results

# ============================================================
# STATISTICS HELPERS
# ============================================================

def _average_timedelta(
    values: List[pd.Timedelta],
) -> Optional[pd.Timedelta]:
    """
    Return arithmetic mean of Timedelta values.
    """

    if not values:
        return None

    total_seconds = sum(
        value.total_seconds()
        for value in values
    )

    mean_seconds = (
        total_seconds / len(values)
    )

    return pd.Timedelta(
        seconds=mean_seconds
    )


def _median_timedelta(
    values: List[pd.Timedelta],
) -> Optional[pd.Timedelta]:
    """
    Return median of Timedelta values.
    """

    if not values:
        return None

    seconds = sorted(
        value.total_seconds()
        for value in values
    )

    count = len(seconds)
    midpoint = count // 2

    if count % 2 == 1:

        median_seconds = (
            seconds[midpoint]
        )

    else:

        median_seconds = (
            seconds[midpoint - 1]
            + seconds[midpoint]
        ) / 2.0

    return pd.Timedelta(
        seconds=median_seconds
    )

# ============================================================
# SCENARIO AGGREGATION
# ============================================================

def _calculate_scenario_statistics(
    scenarios: List[PostExitScenarioResult],
    thresholds: List[float],
) -> PostExitScenarioStatistics:
    """
    Aggregate one type of post-exit scenario.

    Censored observations are retained in termination counts
    but excluded from completed-scenario averages, medians,
    durations, and threshold rates.
    """

    eligible_trades = len(
        scenarios
    )

    # --------------------------------------------------------
    # Termination counts
    # --------------------------------------------------------

    termination_counts = {}

    for scenario in scenarios:

        reason = scenario.end_reason

        termination_counts[reason] = (
            termination_counts.get(
                reason,
                0,
            )
            + 1
        )

    # --------------------------------------------------------
    # Completed vs censored observations
    # --------------------------------------------------------

    completed = [
        scenario
        for scenario in scenarios
        if not scenario.censored
    ]

    censored = [
        scenario
        for scenario in scenarios
        if scenario.censored
    ]

    completed_count = len(
        completed
    )

    censored_count = len(
        censored
    )

    # --------------------------------------------------------
    # Handle case where every observation is censored
    # --------------------------------------------------------

    if completed_count == 0:

        return PostExitScenarioStatistics(
            eligible_trades=eligible_trades,

            completed_observations=0,
            censored_observations=censored_count,

            termination_counts=termination_counts,

            average_potential_mfe_r=0.0,
            median_potential_mfe_r=0.0,

            average_additional_mfe_r=0.0,
            median_additional_mfe_r=0.0,

            new_peak_count=0,
            new_peak_rate=0.0,

            average_time_to_new_peak=None,
            median_time_to_new_peak=None,

            average_extension_duration=None,
            median_extension_duration=None,

            threshold_counts={
                threshold: 0
                for threshold in thresholds
            },

            threshold_rates={
                threshold: 0.0
                for threshold in thresholds
            },
        )

    # --------------------------------------------------------
    # Potential MFE
    # --------------------------------------------------------

    potential_values = [
        scenario.potential_mfe_r
        for scenario in completed
    ]

    additional_values = [
        scenario.additional_mfe_r
        for scenario in completed
    ]

    average_potential_mfe_r = (
        sum(potential_values)
        / completed_count
    )

    average_additional_mfe_r = (
        sum(additional_values)
        / completed_count
    )

    # --------------------------------------------------------
    # Median potential / additional MFE
    # --------------------------------------------------------

    sorted_potential = sorted(
        potential_values
    )

    sorted_additional = sorted(
        additional_values
    )

    midpoint = (
        completed_count // 2
    )

    if completed_count % 2 == 1:

        median_potential_mfe_r = (
            sorted_potential[midpoint]
        )

        median_additional_mfe_r = (
            sorted_additional[midpoint]
        )

    else:

        median_potential_mfe_r = (
            sorted_potential[midpoint - 1]
            + sorted_potential[midpoint]
        ) / 2.0

        median_additional_mfe_r = (
            sorted_additional[midpoint - 1]
            + sorted_additional[midpoint]
        ) / 2.0

    # --------------------------------------------------------
    # New post-exit peak
    # --------------------------------------------------------

    new_peak_scenarios = [
        scenario
        for scenario in completed
        if scenario.new_peak_time is not None
    ]

    new_peak_count = len(
        new_peak_scenarios
    )

    new_peak_rate = (
        new_peak_count
        / completed_count
    )

    time_to_peak_values = [
        scenario.time_to_new_peak
        for scenario in new_peak_scenarios
        if scenario.time_to_new_peak is not None
    ]

    # --------------------------------------------------------
    # Extension duration
    # --------------------------------------------------------

    extension_durations = [
        scenario.extension_duration
        for scenario in completed
    ]

    # --------------------------------------------------------
    # Potential-MFE thresholds
    # --------------------------------------------------------

    threshold_counts = {}
    threshold_rates = {}

    for threshold in thresholds:

        count = sum(
            1
            for scenario in completed
            if scenario.potential_mfe_r >= threshold
        )

        threshold_counts[
            threshold
        ] = count

        threshold_rates[
            threshold
        ] = (
            count / completed_count
        )

    # --------------------------------------------------------
    # Result
    # --------------------------------------------------------

    return PostExitScenarioStatistics(
        eligible_trades=eligible_trades,

        completed_observations=(
            completed_count
        ),

        censored_observations=(
            censored_count
        ),

        termination_counts=(
            termination_counts
        ),

        average_potential_mfe_r=float(
            average_potential_mfe_r
        ),

        median_potential_mfe_r=float(
            median_potential_mfe_r
        ),

        average_additional_mfe_r=float(
            average_additional_mfe_r
        ),

        median_additional_mfe_r=float(
            median_additional_mfe_r
        ),

        new_peak_count=(
            new_peak_count
        ),

        new_peak_rate=float(
            new_peak_rate
        ),

        average_time_to_new_peak=(
            _average_timedelta(
                time_to_peak_values
            )
        ),

        median_time_to_new_peak=(
            _median_timedelta(
                time_to_peak_values
            )
        ),

        average_extension_duration=(
            _average_timedelta(
                extension_durations
            )
        ),

        median_extension_duration=(
            _median_timedelta(
                extension_durations
            )
        ),

        threshold_counts=(
            threshold_counts
        ),

        threshold_rates=(
            threshold_rates
        ),
    )

# ============================================================
# PUBLIC AGGREGATE STATISTICS
# ============================================================

def calculate_post_exit_statistics(
    post_exit_results: List[PostExitExcursion],
    thresholds: Optional[List[float]] = None,
) -> PostExitStatistics:
    """
    Calculate aggregate statistics from per-trade post-exit
    excursion results.

    Parameters
    ----------
    post_exit_results : List[PostExitExcursion]
        Results returned by:

            calculate_post_exit_excursions()

    thresholds : List[float], optional
        Potential-MFE R thresholds to measure.

        Defaults to:

            3R
            4R
            5R
            10R

    Returns
    -------
    PostExitStatistics
        Aggregate same-day and until-stop statistics.
    """

    if thresholds is None:

        thresholds = [
            3.0,
            4.0,
            5.0,
            10.0,
        ]

    if not post_exit_results:

        raise ValueError(
            "Cannot calculate post-exit statistics because "
            "post_exit_results is empty."
        )

    # --------------------------------------------------------
    # Eligible continuation trades
    #
    # Trades that already exited at their original stop have
    # no meaningful hypothetical continuation.
    # --------------------------------------------------------

    eligible_results = [
        result
        for result in post_exit_results
        if result.actual_exit_reason != "stop"
    ]

    # --------------------------------------------------------
    # Separate the two counterfactual scenarios
    # --------------------------------------------------------

    same_day_scenarios = [
        result.same_day
        for result in eligible_results
    ]

    until_stop_scenarios = [
        result.until_stop
        for result in eligible_results
    ]

    # --------------------------------------------------------
    # Aggregate each scenario independently
    # --------------------------------------------------------

    same_day_stats = (
        _calculate_scenario_statistics(
            scenarios=same_day_scenarios,
            thresholds=thresholds,
        )
    )

    until_stop_stats = (
        _calculate_scenario_statistics(
            scenarios=until_stop_scenarios,
            thresholds=thresholds,
        )
    )

    # --------------------------------------------------------
    # Result
    # --------------------------------------------------------

    return PostExitStatistics(
        total_trades=len(
            post_exit_results
        ),

        eligible_trades=len(
            eligible_results
        ),

        same_day=same_day_stats,
        until_stop=until_stop_stats,
    )