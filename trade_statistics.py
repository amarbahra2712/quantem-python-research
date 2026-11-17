# -*- coding: utf-8 -*-
"""
Created on Wed Sep 16 11:13:02 2026

@author: quant
"""

"""
NEXUS Trade Statistics
======================

Purpose
-------
Provide reusable post-backtest performance analysis for the
NEXUS research framework.

This module converts the raw trade records and mark-to-market
equity history produced by NexusEngine into strategy-level
performance statistics.

Responsibilities
----------------
- Count completed trades, wins, losses, and breakeven trades.
- Calculate win rate.
- Calculate gross profit, gross loss, and net profit.
- Calculate average winning and losing trade P&L.
- Calculate dollar profit factor.
- Reconstruct realised gross R-multiples from each trade's
  original risk distance.
- Calculate average winning R, average losing R, and expectancy
  in R per trade.
- Analyse Maximum Adverse Excursion (MAE).
- Analyse Maximum Favourable Excursion (MFE).
- Compare MAE/MFE characteristics of winners and losers.
- Calculate maximum consecutive winning and losing streaks.
- Calculate mark-to-market equity drawdown statistics.
- Identify the peak and trough associated with maximum
  percentage drawdown.
- Identify whether the maximum drawdown recovered.
- Calculate maximum drawdown duration.
- Calculate the longest period spent below a previous equity
  high.

Does Not
--------
- Generate trading signals.
- Prepare strategy indicators.
- Open, manage, or close positions.
- Determine position size.
- Model trade execution.
- Calculate broker spread, commission, swap, or slippage.
- Modify BacktestResult, Trade, Position, or EquityPoint data.
- Perform hypothetical post-exit opportunity analysis.
- Calculate potential MFE after a trade has already closed.
- Produce charts or formatted reports.

Inputs
------
The main public function expects a completed BacktestResult
produced by NexusEngine.

BacktestResult currently provides:

    trades
        Completed Trade records containing entry/exit data,
        initial risk, MAE/MFE, and P&L information.

    equity_curve
        Bar-by-bar EquityPoint records containing balance,
        mark-to-market equity, and unrealised account P&L.

R-Multiple Convention
---------------------
Realised R is currently reconstructed from executable price
movement relative to the original stop distance:

    realised price movement
    -----------------------
    initial risk distance

The original risk distance is preserved when a position is
opened and does not change if the active stop is later moved.

Current realised R therefore represents gross price-based R.

Commission, swap, slippage, and other execution costs are not
yet included in realised R.

MAE / MFE Convention
--------------------
MAE and MFE describe excursion while the trade actually exists.

For long positions:

    MAE uses adverse BID movement.
    MFE uses favourable BID movement.

For short positions:

    MAE uses adverse ASK movement.
    MFE uses favourable ASK movement.

The engine stores MAE and MFE as non-negative price distances
and R-multiples.

Because historical data is OHLC rather than tick-by-tick,
intrabar event ordering is not always observable. NexusEngine
uses conservative event handling and does not assume that
favourable movement occurring elsewhere within an exit bar
necessarily happened before the trade exited.

Potential / Post-Exit MFE
-------------------------
Potential MFE is intentionally separate from trade MFE.

Trade MFE answers:

    "How far did price move in our favour while this trade
    was actually open?"

Potential or post-exit MFE will answer questions such as:

    "After taking profit at 2R, did price subsequently reach
    3R, 4R, or 5R?"

That hypothetical opportunity analysis belongs to the analysis
layer but is not yet implemented in this module.

Drawdown Convention
-------------------
Drawdown is calculated from the mark-to-market equity curve
produced by NexusEngine.

Equity currently represents:

    realised account balance
    + current unrealised position P&L

The equity curve is recorded once per historical bar using
bar-close executable prices:

    long positions  -> BID close
    short positions -> ASK close

Maximum drawdown is therefore currently a BAR-CLOSE
mark-to-market drawdown rather than a tick-level or worst
intrabar drawdown.

Two different duration concepts are retained:

    max_drawdown_duration
        Time from the peak associated with the deepest
        percentage drawdown until that peak is recovered.
        If never recovered, duration runs to the end of
        the backtest.

    longest_underwater_duration
        Longest period anywhere in the backtest during which
        equity remained below a previous equity high.

These two periods do not necessarily describe the same
drawdown episode.

P&L Convention
--------------
Trade records distinguish:

    gross_pnl_quote
    gross_pnl_account
    swap_pnl_account
    commission_pnl_account
    net_pnl_account

At the current stage of NEXUS development:

    swap_pnl_account       = 0.0
    commission_pnl_account = 0.0

Therefore gross and net P&L are currently identical.

The fields already exist so financing and transaction costs
can later be introduced without changing the Trade data model.

How to Use
----------
Typical use:

    trade_stats = calculate_trade_statistics(
        backtest_result
    )

The returned TradeStatistics object can then be consumed by:

    - console diagnostics
    - reporting modules
    - optimisation tools
    - strategy comparison tools
    - future tear sheets
    - interactive trade-review tools

Architecture
------------
This module belongs to the analysis layer.

The intended separation is:

    Strategy
        decides WHAT to trade

    Risk
        decides HOW MUCH to trade

    Engine
        determines WHAT ACTUALLY HAPPENED

    Analysis
        measures HOW THE RESULT PERFORMED

    Reporting
        decides HOW TO PRESENT IT

Keeping performance calculations outside NexusEngine prevents
the execution engine from becoming coupled to reporting or
research-specific metrics.

Notes
-----
All calculations should use full floating-point precision
internally.

Rounding belongs in the reporting or display layer only.

This module is intended to remain strategy-agnostic and should
work with any strategy that satisfies the NEXUS engine
contract.
"""

from dataclasses import dataclass
from typing import List, Optional
import math
import pandas as pd

from nexus_engine import BacktestResult, Trade


# ============================================================
# RESULT MODEL
# ============================================================

@dataclass
class TradeStatistics:
    """
    Summary statistics for a completed backtest.
    """

    total_trades: int

    wins: int
    losses: int
    breakevens: int

    win_rate: float

    gross_profit: float
    gross_loss: float
    net_profit: float

    average_win: float
    average_loss: float

    profit_factor: float

    average_win_r: float
    average_loss_r: float
    expectancy_r: float

    average_mae_r: float
    average_mfe_r: float

    winner_average_mae_r: float
    loser_average_mfe_r: float

    max_winning_streak: int
    max_losing_streak: int
    
    # --------------------------------------------------------
    # Maximum absolute account-currency drawdown
    # --------------------------------------------------------

    max_drawdown_amount: float
    max_drawdown_amount_pct: float

    max_drawdown_amount_peak_time: pd.Timestamp
    max_drawdown_amount_trough_time: pd.Timestamp

    max_drawdown_amount_recovery_time: Optional[pd.Timestamp]
    max_drawdown_amount_duration: pd.Timedelta
    max_drawdown_amount_recovered: bool

    # --------------------------------------------------------
    # Maximum percentage drawdown
    # --------------------------------------------------------

    max_drawdown_pct: float
    max_drawdown_pct_amount: float

    max_drawdown_pct_peak_time: pd.Timestamp
    max_drawdown_pct_trough_time: pd.Timestamp

    max_drawdown_pct_recovery_time: Optional[pd.Timestamp]
    max_drawdown_pct_duration: pd.Timedelta
    max_drawdown_pct_recovered: bool

    # --------------------------------------------------------
    # Longest underwater period
    # --------------------------------------------------------

    longest_underwater_duration: pd.Timedelta 


# ============================================================
# R MULTIPLE
# ============================================================

def _calculate_trade_r(
    trade: Trade,
) -> float:
    """
    Calculate realised gross R-multiple for one trade.
    """

    if trade.initial_risk_distance <= 0:
        raise ValueError(
            "Trade initial_risk_distance must be positive."
        )

    realised_price_move = (
        trade.direction
        * (trade.exit_price - trade.entry_price)
    )

    realised_r = (
        realised_price_move
        / trade.initial_risk_distance
    )

    return float(realised_r)


# ============================================================
# STREAKS
# ============================================================

def _calculate_streaks(
    trades: List[Trade],
) -> tuple:
    """
    Calculate maximum consecutive winning and losing trades.

    Breakeven trades reset both streaks.
    """

    current_winning_streak = 0
    current_losing_streak = 0

    max_winning_streak = 0
    max_losing_streak = 0

    for trade in trades:

        pnl = trade.net_pnl_account

        if pnl > 0:

            current_winning_streak += 1
            current_losing_streak = 0

            max_winning_streak = max(
                max_winning_streak,
                current_winning_streak,
            )

        elif pnl < 0:

            current_losing_streak += 1
            current_winning_streak = 0

            max_losing_streak = max(
                max_losing_streak,
                current_losing_streak,
            )

        else:

            current_winning_streak = 0
            current_losing_streak = 0

    return (
        max_winning_streak,
        max_losing_streak,
    )

# ============================================================
# DRAWDOWN ANALYSIS
# ============================================================

def _calculate_drawdown_statistics(
    backtest_result: BacktestResult,
) -> dict:
    """
    Calculate mark-to-market drawdown statistics.

    Maximum absolute account-currency drawdown and maximum
    percentage drawdown are tracked independently because
    they may occur during different drawdown episodes.

    Equity is currently recorded at bar close, so these are
    bar-close mark-to-market drawdowns rather than tick-level
    or worst-intrabar drawdowns.
    """

    equity_curve = backtest_result.equity_curve

    if not equity_curve:
        raise ValueError(
            "Cannot calculate drawdown because the "
            "equity curve is empty."
        )

    # --------------------------------------------------------
    # Initial running peak
    # --------------------------------------------------------

    first_point = equity_curve[0]

    running_peak_equity = float(
        first_point.equity
    )

    running_peak_time = (
        first_point.timestamp
    )

    # --------------------------------------------------------
    # Maximum absolute drawdown
    # --------------------------------------------------------

    max_drawdown_amount = 0.0
    max_drawdown_amount_pct = 0.0

    max_drawdown_amount_peak_time = (
        first_point.timestamp
    )

    max_drawdown_amount_trough_time = (
        first_point.timestamp
    )

    max_drawdown_amount_peak_equity = float(
        first_point.equity
    )

    # --------------------------------------------------------
    # Maximum percentage drawdown
    # --------------------------------------------------------

    max_drawdown_pct = 0.0
    max_drawdown_pct_amount = 0.0

    max_drawdown_pct_peak_time = (
        first_point.timestamp
    )

    max_drawdown_pct_trough_time = (
        first_point.timestamp
    )

    max_drawdown_pct_peak_equity = float(
        first_point.equity
    )

    # --------------------------------------------------------
    # Underwater-period tracking
    # --------------------------------------------------------

    underwater_start_time = None

    longest_underwater_duration = pd.Timedelta(0)

    # --------------------------------------------------------
    # Walk through equity curve
    # --------------------------------------------------------

    for point in equity_curve:

        timestamp = point.timestamp
        equity = float(point.equity)

        # ----------------------------------------------------
        # New equity high / recovery
        # ----------------------------------------------------

        if equity >= running_peak_equity:

            if underwater_start_time is not None:

                underwater_duration = (
                    timestamp
                    - underwater_start_time
                )

                longest_underwater_duration = max(
                    longest_underwater_duration,
                    underwater_duration,
                )

                underwater_start_time = None

            running_peak_equity = equity
            running_peak_time = timestamp

            continue

        # ----------------------------------------------------
        # Equity is below running peak
        # ----------------------------------------------------

        if underwater_start_time is None:

            underwater_start_time = (
                running_peak_time
            )

        drawdown_amount = (
            running_peak_equity
            - equity
        )

        if running_peak_equity > 0:

            drawdown_pct = (
                drawdown_amount
                / running_peak_equity
            )

        else:

            drawdown_pct = 0.0

        # ----------------------------------------------------
        # New maximum absolute drawdown
        # ----------------------------------------------------

        if drawdown_amount > max_drawdown_amount:

            max_drawdown_amount = (
                drawdown_amount
            )

            max_drawdown_amount_pct = (
                drawdown_pct
            )

            max_drawdown_amount_peak_time = (
                running_peak_time
            )

            max_drawdown_amount_trough_time = (
                timestamp
            )

            max_drawdown_amount_peak_equity = (
                running_peak_equity
            )

        # ----------------------------------------------------
        # New maximum percentage drawdown
        # ----------------------------------------------------

        if drawdown_pct > max_drawdown_pct:

            max_drawdown_pct = (
                drawdown_pct
            )

            max_drawdown_pct_amount = (
                drawdown_amount
            )

            max_drawdown_pct_peak_time = (
                running_peak_time
            )

            max_drawdown_pct_trough_time = (
                timestamp
            )

            max_drawdown_pct_peak_equity = (
                running_peak_equity
            )

    # --------------------------------------------------------
    # Unfinished underwater period
    # --------------------------------------------------------

    final_time = (
        equity_curve[-1].timestamp
    )

    if underwater_start_time is not None:

        unfinished_duration = (
            final_time
            - underwater_start_time
        )

        longest_underwater_duration = max(
            longest_underwater_duration,
            unfinished_duration,
        )

    # --------------------------------------------------------
    # Helper: find recovery from a specific drawdown episode
    # --------------------------------------------------------

    def find_recovery(
        trough_time,
        peak_equity,
    ):

        for point in equity_curve:

            if point.timestamp < trough_time:
                continue

            if float(point.equity) >= peak_equity:
                return point.timestamp

        return None

    # --------------------------------------------------------
    # Absolute drawdown recovery
    # --------------------------------------------------------

    max_drawdown_amount_recovery_time = (
        find_recovery(
            trough_time=(
                max_drawdown_amount_trough_time
            ),
            peak_equity=(
                max_drawdown_amount_peak_equity
            ),
        )
    )

    if max_drawdown_amount_recovery_time is not None:

        max_drawdown_amount_duration = (
            max_drawdown_amount_recovery_time
            - max_drawdown_amount_peak_time
        )

        max_drawdown_amount_recovered = True

    else:

        max_drawdown_amount_duration = (
            final_time
            - max_drawdown_amount_peak_time
        )

        max_drawdown_amount_recovered = False

    # --------------------------------------------------------
    # Percentage drawdown recovery
    # --------------------------------------------------------

    max_drawdown_pct_recovery_time = (
        find_recovery(
            trough_time=(
                max_drawdown_pct_trough_time
            ),
            peak_equity=(
                max_drawdown_pct_peak_equity
            ),
        )
    )

    if max_drawdown_pct_recovery_time is not None:

        max_drawdown_pct_duration = (
            max_drawdown_pct_recovery_time
            - max_drawdown_pct_peak_time
        )

        max_drawdown_pct_recovered = True

    else:

        max_drawdown_pct_duration = (
            final_time
            - max_drawdown_pct_peak_time
        )

        max_drawdown_pct_recovered = False

    # --------------------------------------------------------
    # Result
    # --------------------------------------------------------

    return {
        "max_drawdown_amount": float(
            max_drawdown_amount
        ),

        "max_drawdown_amount_pct": float(
            max_drawdown_amount_pct
        ),

        "max_drawdown_amount_peak_time": (
            max_drawdown_amount_peak_time
        ),

        "max_drawdown_amount_trough_time": (
            max_drawdown_amount_trough_time
        ),

        "max_drawdown_amount_recovery_time": (
            max_drawdown_amount_recovery_time
        ),

        "max_drawdown_amount_duration": (
            max_drawdown_amount_duration
        ),

        "max_drawdown_amount_recovered": (
            max_drawdown_amount_recovered
        ),

        "max_drawdown_pct": float(
            max_drawdown_pct
        ),

        "max_drawdown_pct_amount": float(
            max_drawdown_pct_amount
        ),

        "max_drawdown_pct_peak_time": (
            max_drawdown_pct_peak_time
        ),

        "max_drawdown_pct_trough_time": (
            max_drawdown_pct_trough_time
        ),

        "max_drawdown_pct_recovery_time": (
            max_drawdown_pct_recovery_time
        ),

        "max_drawdown_pct_duration": (
            max_drawdown_pct_duration
        ),

        "max_drawdown_pct_recovered": (
            max_drawdown_pct_recovered
        ),

        "longest_underwater_duration": (
            longest_underwater_duration
        ),
    }


# ============================================================
# MAIN ANALYSIS
# ============================================================

def calculate_trade_statistics(
    backtest_result: BacktestResult,
) -> TradeStatistics:
    """
    Calculate trade-level statistics from a BacktestResult.
    """

    trades = backtest_result.trades

    if not trades:
        raise ValueError(
            "Cannot calculate trade statistics because "
            "the backtest contains no completed trades."
        )

    # --------------------------------------------------------
    # Basic trade groups
    # --------------------------------------------------------

    winning_trades = [
        trade
        for trade in trades
        if trade.net_pnl_account > 0
    ]

    losing_trades = [
        trade
        for trade in trades
        if trade.net_pnl_account < 0
    ]

    breakeven_trades = [
        trade
        for trade in trades
        if trade.net_pnl_account == 0
    ]

    total_trades = len(trades)

    wins = len(winning_trades)
    losses = len(losing_trades)
    breakevens = len(breakeven_trades)

    win_rate = (
        wins / total_trades
    )

    # --------------------------------------------------------
    # Account-currency P&L
    # --------------------------------------------------------

    gross_profit = sum(
        trade.net_pnl_account
        for trade in winning_trades
    )

    gross_loss = abs(
        sum(
            trade.net_pnl_account
            for trade in losing_trades
        )
    )

    net_profit = sum(
        trade.net_pnl_account
        for trade in trades
    )

    average_win = (
        gross_profit / wins
        if wins > 0
        else 0.0
    )

    average_loss = (
        -gross_loss / losses
        if losses > 0
        else 0.0
    )

    if gross_loss > 0:

        profit_factor = (
            gross_profit / gross_loss
        )

    else:

        profit_factor = math.inf

    # --------------------------------------------------------
    # R multiples
    # --------------------------------------------------------

    realised_r_values = [
        _calculate_trade_r(trade)
        for trade in trades
    ]

    winning_r_values = [
        _calculate_trade_r(trade)
        for trade in winning_trades
    ]

    losing_r_values = [
        _calculate_trade_r(trade)
        for trade in losing_trades
    ]

    average_win_r = (
        sum(winning_r_values)
        / len(winning_r_values)
        if winning_r_values
        else 0.0
    )

    average_loss_r = (
        sum(losing_r_values)
        / len(losing_r_values)
        if losing_r_values
        else 0.0
    )

    expectancy_r = (
        sum(realised_r_values)
        / len(realised_r_values)
    )

    # --------------------------------------------------------
    # MAE / MFE
    # --------------------------------------------------------

    average_mae_r = (
        sum(
            trade.mae_r
            for trade in trades
        )
        / total_trades
    )

    average_mfe_r = (
        sum(
            trade.mfe_r
            for trade in trades
        )
        / total_trades
    )

    winner_average_mae_r = (
        sum(
            trade.mae_r
            for trade in winning_trades
        )
        / wins
        if wins > 0
        else 0.0
    )

    loser_average_mfe_r = (
        sum(
            trade.mfe_r
            for trade in losing_trades
        )
        / losses
        if losses > 0
        else 0.0
    )

    # --------------------------------------------------------
    # Streaks
    # --------------------------------------------------------

    (
        max_winning_streak,
        max_losing_streak,
    ) = _calculate_streaks(
        trades=trades
    )

    # --------------------------------------------------------
    # Drawdown statistics
    # --------------------------------------------------------

    drawdown_stats = (
        _calculate_drawdown_statistics(
            backtest_result=backtest_result
        )
    )
        
    # --------------------------------------------------------
    # Result
    # --------------------------------------------------------

    return TradeStatistics(
        total_trades=total_trades,

        wins=wins,
        losses=losses,
        breakevens=breakevens,

        win_rate=float(win_rate),

        gross_profit=float(gross_profit),
        gross_loss=float(gross_loss),
        net_profit=float(net_profit),

        average_win=float(average_win),
        average_loss=float(average_loss),

        profit_factor=float(profit_factor),

        average_win_r=float(average_win_r),
        average_loss_r=float(average_loss_r),
        expectancy_r=float(expectancy_r),

        average_mae_r=float(average_mae_r),
        average_mfe_r=float(average_mfe_r),

        winner_average_mae_r=float(
            winner_average_mae_r
        ),

        loser_average_mfe_r=float(
            loser_average_mfe_r
        ),

        max_winning_streak=max_winning_streak,
        max_losing_streak=max_losing_streak,
        
        max_drawdown_amount=(
            drawdown_stats[
                "max_drawdown_amount"
            ]
        ),

        max_drawdown_amount_pct=(
            drawdown_stats[
                "max_drawdown_amount_pct"
            ]
        ),

        max_drawdown_amount_peak_time=(
            drawdown_stats[
                "max_drawdown_amount_peak_time"
            ]
        ),

        max_drawdown_amount_trough_time=(
            drawdown_stats[
                "max_drawdown_amount_trough_time"
            ]
        ),

        max_drawdown_amount_recovery_time=(
            drawdown_stats[
                "max_drawdown_amount_recovery_time"
            ]
        ),

        max_drawdown_amount_duration=(
            drawdown_stats[
                "max_drawdown_amount_duration"
            ]
        ),

        max_drawdown_amount_recovered=(
            drawdown_stats[
                "max_drawdown_amount_recovered"
            ]
        ),

        max_drawdown_pct=(
            drawdown_stats[
                "max_drawdown_pct"
            ]
        ),

        max_drawdown_pct_amount=(
            drawdown_stats[
                "max_drawdown_pct_amount"
            ]
        ),

        max_drawdown_pct_peak_time=(
            drawdown_stats[
                "max_drawdown_pct_peak_time"
            ]
        ),

        max_drawdown_pct_trough_time=(
            drawdown_stats[
                "max_drawdown_pct_trough_time"
            ]
        ),

        max_drawdown_pct_recovery_time=(
            drawdown_stats[
                "max_drawdown_pct_recovery_time"
            ]
        ),

        max_drawdown_pct_duration=(
            drawdown_stats[
                "max_drawdown_pct_duration"
            ]
        ),

        max_drawdown_pct_recovered=(
            drawdown_stats[
                "max_drawdown_pct_recovered"
            ]
        ),

        longest_underwater_duration=(
            drawdown_stats[
                "longest_underwater_duration"
            ]
        ),                
    )