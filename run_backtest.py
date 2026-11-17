# -*- coding: utf-8 -*-
"""
Created on Sat Sep 12 10:27:33 2026
@author: quant
09_backtester/run_backtest.py
"""

##############################################################################
#   CHECK FOR EXPLICT PARAMETERS IN THIS ie. data files are explict
##############################################################################

"""
NEXUS Backtest Runner
=====================

Purpose
-------
Provide the top-level orchestration script for running a NEXUS
historical backtest.

Responsibilities
----------------
- Bootstrap the NEXUS project import paths.
- Load account, execution, instrument and backtest settings.
- Obtain the active generic prop configuration through the
  prop configuration factory.
- Load and validate historical market data.
- Prepare required indicators.
- Load the selected strategy.
- Run NexusEngine.
- Execute downstream analysis modules.
- Evaluate prop-firm objectives generically.
- Print development diagnostics and validation checks.

Does Not
--------
- Contain strategy logic.
- Contain provider-specific prop-rule values.
- Contain FTMO-specific imports or parameters.
- Implement execution mechanics.
- Calculate commission or swap directly.
- Implement prop-rule calculations.
- Serve as the long-term reporting layer.

Design Principle
----------------
This file is an orchestrator, not a model component.

Configuration parameters should live in the appropriate config
modules rather than being embedded directly in the runner.

Provider changes should be made through:

    prop_selection.py

Strategy changes should be made through the appropriate
strategy-selection / configuration layer.

Future Direction
----------------
As NEXUS matures, development printouts currently produced by
this runner should progressively move into dedicated reporting
and diagnostic modules.

The runner should ultimately remain small and stable while the
engine, strategies, analysis and reporting layers evolve
independently.
"""

from pathlib import Path
import sys


# ============================================================
# PROJECT ROOT
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ============================================================
# USER SELECTIONS
# ============================================================

STRATEGY_NAME = "nexus_base"



# ============================================================
# PROJECT MODULE PATHS
# ============================================================

DATA_MODULES = (
    PROJECT_ROOT
    / "01_data"
)

INDICATOR_MODULES = (
    PROJECT_ROOT
    / "02_indicators"
)

STRATEGY_MODULES = (
    PROJECT_ROOT
    / "03_strategies"
    / STRATEGY_NAME
)

ENGINE_MODULES = (
    PROJECT_ROOT
    / "04_engine"
)

RISK_MODULES = (
    PROJECT_ROOT
    / "05_risk"
)

ANALYSIS_MODULES = (
    PROJECT_ROOT
    / "06_analysis"
)

REPORTING_MODULES = (
    PROJECT_ROOT
    / "07_reporting"
)

CONFIG_MODULES = (
    PROJECT_ROOT
    / "08_config"
)

ANALYSIS_DIR = (
    PROJECT_ROOT
    / "06_analysis"
)

# ============================================================
# ADD MODULE PATHS TO PYTHON PATH
# ============================================================

for module_path in [
    DATA_MODULES,
    INDICATOR_MODULES,
    STRATEGY_MODULES,
    ENGINE_MODULES,
    RISK_MODULES,
    ANALYSIS_MODULES,
    REPORTING_MODULES,
    CONFIG_MODULES,
]:
    sys.path.insert(
        0,
        str(module_path)
    )


# ============================================================
# IMPORT NEXUS MODULES
# ============================================================

from run_logger import start_run_log

from data_config import get_active_data_config

from data_loader import load_price_data

from data_preprocessor import (
    preprocess_price_data,
)

from data_validation import (
    validate_price_data,
    print_validation_report,
)

from strategy import Strategy
from config import StrategyConfig

from account_config import AccountConfig
from execution_config import ExecutionConfig
from backtest_config import BacktestConfig
from trading_window_config import get_active_trading_window_config

from nexus_engine import (
    NexusEngine,
    ENGINE_NAME,
    ENGINE_VERSION,
    POSITION_MODEL,
    ORDER_MODEL,
)

from run_manifest import (
    create_run_context,
    write_initial_manifest,
    finalise_run_manifest,
)

from run_logger import (
    start_run_log,
)


from instrument_config import get_instrument_config

from trade_statistics import calculate_trade_statistics

from post_exit_excursion import (
    PostExitConfig,
    calculate_post_exit_excursions,
    calculate_post_exit_statistics,
)

from prop_factory import get_active_prop_config

from prop_evaluator import (
    build_prop_daily_states,
    evaluate_daily_loss_limits,
    evaluate_total_loss_limit,
    get_first_prop_breach,
    get_prop_trading_days,
    get_prop_trading_day,
    get_prop_trading_days_up_to,
    evaluate_prop_firm,
)


# ============================================================
# RUN CONTEXT
# ============================================================

run_context = (
    create_run_context(
        project_root=(
            PROJECT_ROOT
        )
    )
)


# ============================================================
# RUN LOG
# ============================================================

(
    run_log_path,
    run_log_file,
    original_stdout,
    original_stderr,
) = start_run_log(
    run_dir=(
        run_context.run_dir
    )
)


print()
print("NEXUS RUN")
print("-------------------------------------------------------")

print(
    "Run ID:",
    run_context.run_id
)

print(
    "Run directory:",
    run_context.run_dir
)

print(
    "Log file:",
    run_log_path
)

print("-------------------------------------------------------")

# ============================================================
# CONFIGURATION
# ============================================================

data_config = get_active_data_config()

data_config.validate()

strategy_config = StrategyConfig()

#account_config = AccountConfig()
account_config = AccountConfig(
    account_currency="USD",
    starting_balance=30000.0,
    risk_per_trade=0.01,
    use_margin_limit=False,
)

execution_config = ExecutionConfig()

#backtest_config = BacktestConfig()
backtest_config = BacktestConfig(
    entry_timing="next_open",
    same_bar_policy="stop_first",
    allow_overnight_positions=True,
    force_close_at_end=True,
)

trading_window_config = get_active_trading_window_config()

print()
print("ACTIVE TRADING WINDOW CONFIG")
print("-------------------------------------------------------")

print(
    "Enabled:",
    trading_window_config.enabled
)

print(
    "Timezone:",
    trading_window_config.timezone
)

print(
    "Allowed weekdays:",
    trading_window_config.allowed_weekdays
)

print(
    "Number of windows:",
    len(
        trading_window_config.windows
    )
)

for window in trading_window_config.windows:

    print(
        window.name,
        "|",
        window.start_time,
        "->",
        window.end_time,
    )

print("-------------------------------------------------------")

# ============================================================
# PROP-FIRM CONFIGURATION
# ============================================================

prop_config = (
    get_active_prop_config()
)

instrument_config = get_instrument_config("GBPUSD")


# ============================================================
# RUN MANIFEST
# ============================================================

manifest_path = (
    write_initial_manifest(
        context=(
            run_context
        ),

        project_root=(
            PROJECT_ROOT
        ),

        strategy_name=(
            STRATEGY_NAME
        ),

        engine_metadata={
            "engine_name": (
                ENGINE_NAME
            ),

            "engine_version": (
                ENGINE_VERSION
            ),

            "position_model": (
                POSITION_MODEL
            ),

            "order_model": (
                ORDER_MODEL
            ),
        },

        config_sections={
            "data": (
                data_config
            ),

            "strategy": (
                strategy_config
            ),

            "account": (
                account_config
            ),

            "execution": (
                execution_config
            ),

            "backtest": (
                backtest_config
            ),

            "instrument": (
                instrument_config
            ),

            "trading_window": (
                trading_window_config
            ),

            "prop_firm": (
                prop_config
            ),
        },

        data_files={
            "bid": (
                data_config.bid_path
            ),

            "ask": (
                data_config.ask_path
            ),
        },
    )
)


print()
print("RUN MANIFEST")
print("-------------------------------------------------------")

print(
    "Manifest:",
    manifest_path
)

print("-------------------------------------------------------")

# ============================================================
# LOAD HISTORICAL DATA
# ============================================================

df = load_price_data(
    bid_file=(
        data_config.bid_path
    ),
    ask_file=(
        data_config.ask_path
    ),
)

# ============================================================
# PREPROCESS DATA
# ============================================================

df = preprocess_price_data(
    df
)


# ============================================================
# VALIDATE DATA
# ============================================================

validation_report = validate_price_data(
    df
)

print_validation_report(
    validation_report
)


# ============================================================
# CREATE STRATEGY
# ============================================================

strategy = Strategy(
    config=strategy_config
)


# ============================================================
# RUN STRATEGY PIPELINE
# ============================================================

signal_data = strategy.run(
    df
)
#>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
#     <<<<<<<<<<<<<<<<<<<<<<<<<<<<    TEMPORARY CODE      >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
#>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>

# ------------------------------------------------------------
# Strategy diagnostics
# ------------------------------------------------------------

print()
print("STRATEGY DIAGNOSTICS")
print("-------------------------------------------------------")

print(
    "Long signals:",
    int(signal_data["long_signal"].sum())
)

print(
    "Short signals:",
    int(signal_data["short_signal"].sum())
)

print(
    "Total signals:",
    int((signal_data["entry_signal"] != 0).sum())
)

print()
print("Indicator columns present:")

for column in [
    "ema_fast",
    "ema_slow",
    "ema_filter",
    "atr",
]:
    print(
        f"  {column}:",
        column in signal_data.columns
    )

print()
print("Trade instruction columns present:")

for column in [
    "entry_signal",
    "stop_distance",
    "target_distance",
]:
    print(
        f"  {column}:",
        column in signal_data.columns
    )

print("-------------------------------------------------------")


# ============================================================
# NEXUS BASE STRATEGY CONTRACT TEST
# ============================================================

print()
print("NEXUS BASE STRATEGY CONTRACT TEST")
print("-------------------------------------------------------")


# ------------------------------------------------------------
# Required indicator columns
# ------------------------------------------------------------

required_indicator_columns = [
    "ema_fast",
    "ema_slow",
    "ema_filter",
    "atr",
]


# ------------------------------------------------------------
# Required strategy output columns
# ------------------------------------------------------------

required_signal_columns = [
    "long_signal",
    "short_signal",
    "entry_signal",
    "stop_distance",
    "target_distance",
]


required_columns = (
    required_indicator_columns
    + required_signal_columns
)


missing_columns = [
    column
    for column in required_columns
    if column not in signal_data.columns
]


if missing_columns:
    raise ValueError(
        f"NEXUS base strategy missing columns: "
        f"{missing_columns}"
    )


# ------------------------------------------------------------
# Validate entry signals
# ------------------------------------------------------------

valid_entry_signals = {-1, 0, 1}

actual_entry_signals = set(
    signal_data["entry_signal"]
    .dropna()
    .unique()
)


if not actual_entry_signals.issubset(
    valid_entry_signals
):
    raise ValueError(
        f"Invalid entry_signal values found: "
        f"{actual_entry_signals}"
    )


# ------------------------------------------------------------
# Extract signal rows
# ------------------------------------------------------------

signal_mask = (
    signal_data["entry_signal"] != 0
)

signal_rows = signal_data.loc[
    signal_mask
].copy()


# ------------------------------------------------------------
# Validate stop distances
# ------------------------------------------------------------

if (
    signal_rows["stop_distance"] <= 0
).any():
    raise ValueError(
        "Non-positive stop distance found."
    )


# ------------------------------------------------------------
# Validate target distances
# ------------------------------------------------------------

if (
    signal_rows["target_distance"] <= 0
).any():
    raise ValueError(
        "Non-positive target distance found."
    )


# ------------------------------------------------------------
# Validate reward-to-risk geometry
# ------------------------------------------------------------

expected_target_distance = (
    signal_rows["stop_distance"]
    * strategy_config.reward_r
)


target_error = (
    signal_rows["target_distance"]
    - expected_target_distance
).abs()


if (
    target_error > 1e-12
).any():
    raise ValueError(
        "Target distance does not match configured "
        "reward-to-risk multiple."
    )


# ------------------------------------------------------------
# Validate ATR stop geometry
# ------------------------------------------------------------

expected_stop_distance = (
    signal_rows["atr"]
    * strategy_config.stop_atr_multiple
)


stop_error = (
    signal_rows["stop_distance"]
    - expected_stop_distance
).abs()


if (
    stop_error > 1e-12
).any():
    raise ValueError(
        "Stop distance does not match configured "
        "ATR stop multiple."
    )


# ------------------------------------------------------------
# Summary
# ------------------------------------------------------------

long_signals = int(
    signal_data["long_signal"].sum()
)

short_signals = int(
    signal_data["short_signal"].sum()
)

total_signals = len(signal_rows)


print("Required columns:         PASS")
print("Entry signal values:      PASS")
print("Stop distances:           PASS")
print("Target distances:         PASS")
print("ATR stop geometry:        PASS")
print("Reward/Risk geometry:     PASS")

print()
print("Long signals:", long_signals)
print("Short signals:", short_signals)
print("Total signals:", total_signals)

print("-------------------------------------------------------")




#>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
#     <<<<<<<<<<<<<<<<<<<<<<<<<<<<    TEMPORARY CODE END    >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
#>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>

# ============================================================
# BACKTEST ENGINE
# ============================================================

# The new generic NEXUS BacktestEngine will be connected here
# after `04_engine` has been rebuilt.
#
# It will receive the prepared market data, strategy signals,
# account configuration, execution configuration and backtest
# configuration.


# ============================================================
# PROP-FIRM EVALUATION
# ============================================================

# A generic prop-firm selector/evaluator will be connected here
# later.
#
# The runner should not need to import FTMO, FundingPips,
# The5ers or any other provider directly.


# ============================================================
# RESULTS
# ============================================================

print("\nNEXUS STRATEGY PIPELINE COMPLETE")
print("-" * 55)

print(
    f"Strategy:             "
    f"{STRATEGY_NAME}"
)

print(
    f"Rows processed:       "
    f"{len(signal_data):,}"
)

print(
    f"Detected timeframe:   "
    f"{validation_report.inferred_bar_minutes} minute(s)"
)

signals_generated = int(
    (
        signal_data[
            "entry_signal"
        ]
        != 0
    )
    .sum()
)

print(
    f"Signals generated:    "
    f"{signals_generated:,}"
)

print("-" * 55)


print()
print("COMMISSION CONFIGURATION")
print("-------------------------------------------------------")

print(
    "Commission enabled:",
    execution_config.include_commission
)

print(
    "Commission model:",
    execution_config.commission_model
)

print(
    "Commission rate:",
    execution_config.commission_rate
)

print(
    "Commission scope:",
    execution_config.commission_scope
)

print(
    "Commission lot size:",
    execution_config.commission_lot_size
)

print("-------------------------------------------------------")


# ============================================================
# NEXUS ENGINE
# ============================================================

engine = NexusEngine(
    instrument_config=instrument_config,
    account_config=account_config,
    execution_config=execution_config,
    backtest_config=backtest_config,
    trading_window_config=trading_window_config
)


backtest_result = engine.run(
    df=signal_data
)

trade_stats = calculate_trade_statistics(
    backtest_result
)

# ============================================================
# POST-EXIT EXCURSION ANALYSIS
# ============================================================

post_exit_config = PostExitConfig()

post_exit_results = (
    calculate_post_exit_excursions(
        market_data=signal_data,
        backtest_result=backtest_result,
        config=post_exit_config,
    )
)

post_exit_stats = (
    calculate_post_exit_statistics(
        post_exit_results
    )
)

# ============================================================
# POST-EXIT CONTRACT TEST
# ============================================================

post_exit_count_ok = (
    len(post_exit_results)
    == len(backtest_result.trades)
)

potential_not_below_actual = all(
    result.same_day.potential_mfe_r
    + 1e-12
    >= result.actual_mfe_r
    and
    result.until_stop.potential_mfe_r
    + 1e-12
    >= result.actual_mfe_r
    for result in post_exit_results
)

until_stop_not_below_same_day = all(
    result.until_stop.potential_mfe_r
    + 1e-12
    >= result.same_day.potential_mfe_r
    for result in post_exit_results
)


# ============================================================
# POST-EXIT TERMINATION DIAGNOSTICS
# ============================================================

same_day_reasons = {}

until_stop_reasons = {}


for result in post_exit_results:

    same_day_reason = (
        result.same_day.end_reason
    )

    until_stop_reason = (
        result.until_stop.end_reason
    )

    same_day_reasons[
        same_day_reason
    ] = (
        same_day_reasons.get(
            same_day_reason,
            0,
        )
        + 1
    )

    until_stop_reasons[
        until_stop_reason
    ] = (
        until_stop_reasons.get(
            until_stop_reason,
            0,
        )
        + 1
    )


print()
print("POST-EXIT TERMINATION DIAGNOSTICS")
print("-------------------------------------------------------")

print("Same-day runner:")

for reason, count in sorted(
    same_day_reasons.items()
):

    print(
        " ",
        reason,
        ":",
        count,
    )


print()
print("Until-stop runner:")

for reason, count in sorted(
    until_stop_reasons.items()
):

    print(
        " ",
        reason,
        ":",
        count,
    )

print("-------------------------------------------------------")

print()
print("POST-EXIT EXCURSION CONTRACT TEST")
print("-------------------------------------------------------")

print(
    "Trade count:",
    "PASS" if post_exit_count_ok else "FAIL"
)

print(
    "Potential MFE >= actual MFE:",
    "PASS"
    if potential_not_below_actual
    else "FAIL"
)

print(
    "Until-stop MFE >= same-day MFE:",
    "PASS"
    if until_stop_not_below_same_day
    else "FAIL"
)

print(
    "Trades analysed:",
    len(post_exit_results)
)

print("-------------------------------------------------------")


# ============================================================
# BACKTEST SUMMARY
# ============================================================

print()
print("NEXUS BACKTEST SUMMARY")
print("-------------------------------------------------------")

print(
    "Starting balance:",
    backtest_result.starting_balance
)

print(
    "Ending balance:",
    backtest_result.ending_balance
)

print(
    "Ending equity:",
    backtest_result.ending_equity
)

print(
    "Closed trades:",
    len(backtest_result.trades)
)

print(
    "Open position:",
    backtest_result.open_position
)

print(
    "Rows processed:",
    backtest_result.rows_processed
)

total_return = (
    backtest_result.ending_balance
    / backtest_result.starting_balance
    - 1.0
)

print(
    "Total return:",
    f"{total_return * 100:.2f}%"
)

print("-------------------------------------------------------")

# ============================================================
# COMMISSION DIAGNOSTICS
# ============================================================

total_commission_pnl = sum(
    trade.commission_pnl_account
    for trade in backtest_result.trades
)

commissioned_trades = [
    trade
    for trade in backtest_result.trades
    if abs(
        trade.commission_pnl_account
    ) > 1e-12
]

average_commission = (
    total_commission_pnl
    / len(commissioned_trades)
    if commissioned_trades
    else 0.0
)


print()
print("COMMISSION DIAGNOSTICS")
print("-------------------------------------------------------")

print(
    "Commission enabled:",
    execution_config.include_commission
)

print(
    "Commission model:",
    execution_config.commission_model
)

print(
    "Commissioned trades:",
    len(commissioned_trades)
)

print(
    "Total commission P&L:",
    round(
        total_commission_pnl,
        2
    )
)

print(
    "Average commission per trade:",
    round(
        average_commission,
        4
    )
)

print("-------------------------------------------------------")


# ============================================================
# OVERNIGHT / ROLLOVER DIAGNOSTICS
# ============================================================

overnight_close_trades = [
    trade
    for trade in backtest_result.trades
    if trade.exit_reason == "overnight_close"
]

rolled_trades = [
    trade
    for trade in backtest_result.trades
    if trade.rollover_events > 0
]

total_rollover_events = sum(
    trade.rollover_events
    for trade in backtest_result.trades
)

total_rollover_units = sum(
    trade.rollover_units
    for trade in backtest_result.trades
)

total_swap_pnl = sum(
    trade.swap_pnl_account
    for trade in backtest_result.trades
)

swap_debits = sum(
    trade.swap_pnl_account
    for trade in backtest_result.trades
    if trade.swap_pnl_account < 0.0
)

swap_credits = sum(
    trade.swap_pnl_account
    for trade in backtest_result.trades
    if trade.swap_pnl_account > 0.0
)

max_rollover_events = max(
    (
        trade.rollover_events
        for trade in backtest_result.trades
    ),
    default=0,
)

max_rollover_units = max(
    (
        trade.rollover_units
        for trade in backtest_result.trades
    ),
    default=0.0,
)


print()
print("OVERNIGHT / ROLLOVER DIAGNOSTICS")
print("-------------------------------------------------------")

print(
    "Allow overnight positions:",
    backtest_config.allow_overnight_positions
)

print(
    "Swap enabled:",
    execution_config.include_swap
)

print(
    "Overnight-close trades:",
    len(overnight_close_trades)
)

print(
    "Trades crossing rollover:",
    len(rolled_trades)
)

print(
    "Total rollover events:",
    total_rollover_events
)

print(
    "Total rollover units:",
    round(
        total_rollover_units,
        4
    )
)

print(
    "Total swap P&L:",
    round(
        total_swap_pnl,
        8
    )
)

print(
    "Swap debits:",
    round(
        swap_debits,
        2
    )
)

print(
    "Swap credits:",
    round(
        swap_credits,
        2
    )
)

print(
    "Maximum rollover events on one trade:",
    max_rollover_events
)

print(
    "Maximum rollover units on one trade:",
    max_rollover_units
)

print("-------------------------------------------------------")

# ============================================================
# ROLLOVER / ACCOUNTING CONTRACT TEST
# ============================================================

trade_net_reconciliation = all(
    abs(
        trade.net_pnl_account
        - (
            trade.gross_pnl_account
            + trade.swap_pnl_account
            + trade.commission_pnl_account
        )
    )
    < 1e-8
    for trade in backtest_result.trades
)


realised_trade_net = sum(
    trade.net_pnl_account
    for trade in backtest_result.trades
)


# ------------------------------------------------------------
# Costs already posted on any position still open at the end
# ------------------------------------------------------------

open_position_costs = 0.0

if backtest_result.open_position is not None:

    open_position_costs = (
        backtest_result
        .open_position
        .accrued_swap_pnl_account

        +

        backtest_result
        .open_position
        .accrued_commission_pnl_account
    )


expected_ending_balance = (
    backtest_result.starting_balance
    + realised_trade_net
    + open_position_costs
)


balance_reconciliation = (
    abs(
        backtest_result.ending_balance
        - expected_ending_balance
    )
    < 1e-6
)


# ------------------------------------------------------------
# Overnight-disabled contract
# ------------------------------------------------------------

if not backtest_config.allow_overnight_positions:

    overnight_policy_pass = all(
        trade.rollover_events == 0
        and abs(
            trade.swap_pnl_account
        ) < 1e-12
        for trade in backtest_result.trades
    )

else:

    overnight_policy_pass = True


# ------------------------------------------------------------
# Swap-disabled contract
# ------------------------------------------------------------

if not execution_config.include_swap:

    swap_disabled_pass = all(
        abs(
            trade.swap_pnl_account
        ) < 1e-12
        for trade in backtest_result.trades
    )

else:

    swap_disabled_pass = True

print()
print("ROLLED TRADE DETAILS")
print("-------------------------------------------------------")

for trade_number, trade in enumerate(
    backtest_result.trades,
    start=1,
):

    if trade.rollover_events <= 0:
        continue

    if trade.direction == 1:
        direction_name = "LONG"
        configured_rate = (
            execution_config
            .swap_long_per_unit
        )

    else:
        direction_name = "SHORT"
        configured_rate = (
            execution_config
            .swap_short_per_unit
        )

    expected_swap_quote = (
        trade.size
        * configured_rate
        * trade.rollover_units
    )

    print()
    print(
        "Trade:",
        trade_number,
        "|",
        direction_name,
    )

    print(
        "Entry:",
        trade.entry_time
    )

    print(
        "Exit:",
        trade.exit_time
    )

    print(
        "Size:",
        trade.size
    )

    print(
        "Rollover events:",
        trade.rollover_events
    )

    print(
        "Rollover units:",
        trade.rollover_units
    )

    print(
        "Configured rate:",
        configured_rate
    )

    print(
        "Expected quote swap:",
        expected_swap_quote
    )

    print(
        "Recorded account swap:",
        trade.swap_pnl_account
    )


print()
print("-------------------------------------------------------")


print()
print("ROLLOVER / ACCOUNTING CONTRACT TEST")
print("-------------------------------------------------------")

print(
    "Trade net reconciliation:",
    (
        "PASS"
        if trade_net_reconciliation
        else "FAIL"
    )
)

print(
    "Account balance reconciliation:",
    (
        "PASS"
        if balance_reconciliation
        else "FAIL"
    )
)

print(
    "Overnight policy:",
    (
        "PASS"
        if overnight_policy_pass
        else "FAIL"
    )
)

if execution_config.include_swap:

    swap_disabled_display = "N/A"

else:

    swap_disabled_display = (
        "PASS"
        if swap_disabled_pass
        else "FAIL"
    )


print(
    "Swap-disabled behaviour:",
    swap_disabled_display
)

print(
    "Expected ending balance:",
    expected_ending_balance
)

print(
    "Actual ending balance:",
    backtest_result.ending_balance
)

print("-------------------------------------------------------")

print()
print("FIRST 10 COMPLETED TRADES")
print("-------------------------------------------------------")

for trade in backtest_result.trades[:10]:

    print(
        trade.entry_time,
        "|",
        "LONG" if trade.direction == 1 else "SHORT",
        "| entry:",
        round(trade.entry_price, 5),
        "| exit:",
        round(trade.exit_price, 5),
        "| reason:",
        trade.exit_reason,
        "| gross P&L:",
        round(trade.gross_pnl_account, 2),
    )
    
   
    print(
        "| swap:",
        round(
            trade.swap_pnl_account,
            2
        ),
        "| rollover events:",
        trade.rollover_events,
        "| rollover units:",
        trade.rollover_units,
    )

print("-------------------------------------------------------")

#>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
#<<<<<<<<<<<<<<<<<<<<<<<<<<<< TEMPORARY CODE >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
#>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>

print()
print("NEW ENGINE DIAGNOSTICS")
print("-------------------------------------------------------")

print(
    "Equity points:",
    len(backtest_result.equity_curve)
)

print(
    "Expected equity points:",
    len(signal_data)
)

print()
print("FIRST 5 TRADE EXCURSIONS")
print("-------------------------------------------------------")

for trade in backtest_result.trades[:5]:

    print(
    trade.exit_time,
    "|",
    "LONG" if trade.direction == 1 else "SHORT",
    "| MAE:",
    round(trade.mae_r, 4),
    "R",
    "| MFE:",
    round(trade.mfe_r, 4),
    "R",
    "| gross P&L:",
    round(trade.gross_pnl_account, 2),
    "| commission:",
    round(trade.commission_pnl_account, 4),
    "| swap:",
    round(trade.swap_pnl_account, 8),
    "| net:",
    round(trade.net_pnl_account, 2),
)


# ============================================================
# SAMPLE POST-EXIT RESULTS
# ============================================================

interesting_results = [
    result
    for result in post_exit_results
    if result.actual_exit_reason != "stop"
]


print()
print("FIRST 5 NON-STOP POST-EXIT RESULTS")
print("-------------------------------------------------------")


for result in interesting_results[:5]:

    direction = (
        "LONG"
        if result.direction == 1
        else "SHORT"
    )

    print()

    print(
        "Trade:",
        result.trade_number,
        "|",
        result.exit_time,
        "|",
        direction,
        "| exit:",
        result.actual_exit_reason,
    )

    print(
        "  Actual MFE:",
        round(
            result.actual_mfe_r,
            4
        ),
        "R"
    )

    print(
        "  Same-day potential:",
        round(
            result.same_day.potential_mfe_r,
            4
        ),
        "R",
        "| additional:",
        round(
            result.same_day.additional_mfe_r,
            4
        ),
        "R",
    )

    print(
        "  Same-day duration:",
        result.same_day.extension_duration,
        "| end:",
        result.same_day.end_reason,
    )

    print(
        "  Until-stop potential:",
        round(
            result.until_stop.potential_mfe_r,
            4
        ),
        "R",
        "| additional:",
        round(
            result.until_stop.additional_mfe_r,
            4
        ),
        "R",
    )

    print(
        "  Until-stop duration:",
        result.until_stop.extension_duration,
        "| end:",
        result.until_stop.end_reason,
    )


print()
print("-------------------------------------------------------")

# ============================================================
# POST-EXIT AGGREGATE STATISTICS
# ============================================================

print()
print("POST-EXIT AGGREGATE STATISTICS")
print("-------------------------------------------------------")

print(
    "Total trades:",
    post_exit_stats.total_trades
)

print(
    "Eligible continuation trades:",
    post_exit_stats.eligible_trades
)


for name, stats in [
    (
        "SAME-DAY RUNNER",
        post_exit_stats.same_day,
    ),
    (
        "UNTIL-STOP RUNNER",
        post_exit_stats.until_stop,
    ),
]:

    print()
    print(name)
    print("-------------------------------------------------------")

    print(
        "Eligible:",
        stats.eligible_trades
    )

    print(
        "Completed:",
        stats.completed_observations
    )

    print(
        "Censored:",
        stats.censored_observations
    )

    print()

    print(
        "Average potential MFE:",
        round(
            stats.average_potential_mfe_r,
            4
        ),
        "R"
    )

    print(
        "Median potential MFE:",
        round(
            stats.median_potential_mfe_r,
            4
        ),
        "R"
    )

    print(
        "Average additional MFE:",
        round(
            stats.average_additional_mfe_r,
            4
        ),
        "R"
    )

    print(
        "Median additional MFE:",
        round(
            stats.median_additional_mfe_r,
            4
        ),
        "R"
    )

    print()

    print(
        "New post-exit peak:",
        stats.new_peak_count,
        "/",
        stats.completed_observations,
        "=",
        round(
            stats.new_peak_rate * 100,
            2
        ),
        "%"
    )

    print(
        "Average time to new peak:",
        stats.average_time_to_new_peak
    )

    print(
        "Median time to new peak:",
        stats.median_time_to_new_peak
    )

    print()

    print(
        "Average extension duration:",
        stats.average_extension_duration
    )

    print(
        "Median extension duration:",
        stats.median_extension_duration
    )

    print()

    print("Potential MFE thresholds:")

    for threshold in sorted(
        stats.threshold_rates
    ):

        print(
            " ",
            f">= {threshold:g}R:",
            stats.threshold_counts[
                threshold
            ],
            "/",
            stats.completed_observations,
            "=",
            round(
                stats.threshold_rates[
                    threshold
                ] * 100,
                2
            ),
            "%"
        )

    print()

    print(
        "Termination counts:",
        stats.termination_counts
    )


print("-------------------------------------------------------")



print()
print("TRADE STATISTICS")
print("-------------------------------------------------------")

print("Total trades:", trade_stats.total_trades)
print("Wins:", trade_stats.wins)
print("Losses:", trade_stats.losses)
print("Breakevens:", trade_stats.breakevens)

print(
    "Win rate:",
    round(trade_stats.win_rate * 100, 2),
    "%"
)

print()
print(
    "Gross profit:",
    round(trade_stats.gross_profit, 2)
)

print(
    "Gross loss:",
    round(trade_stats.gross_loss, 2)
)

print(
    "Net profit:",
    round(trade_stats.net_profit, 2)
)

print(
    "Profit factor:",
    round(trade_stats.profit_factor, 4)
)

print()
print(
    "Average win R:",
    round(trade_stats.average_win_r, 4)
)

print(
    "Average loss R:",
    round(trade_stats.average_loss_r, 4)
)

print(
    "Expectancy R:",
    round(trade_stats.expectancy_r, 4)
)

print()
print(
    "Average MAE:",
    round(trade_stats.average_mae_r, 4),
    "R"
)

print(
    "Average MFE:",
    round(trade_stats.average_mfe_r, 4),
    "R"
)

print(
    "Winner average MAE:",
    round(
        trade_stats.winner_average_mae_r,
        4
    ),
    "R"
)

print(
    "Loser average MFE:",
    round(
        trade_stats.loser_average_mfe_r,
        4
    ),
    "R"
)

print()
print(
    "Max winning streak:",
    trade_stats.max_winning_streak
)

print(
    "Max losing streak:",
    trade_stats.max_losing_streak
)

print()
print("DRAWDOWN STATISTICS")
print("-------------------------------------------------------")


# ============================================================
# MAXIMUM ABSOLUTE DRAWDOWN
# ============================================================

print()
print("MAXIMUM ABSOLUTE DRAWDOWN")
print("-------------------------------------------------------")

print(
    "Amount:",
    round(
        trade_stats.max_drawdown_amount,
        2
    )
)

print(
    "Percent:",
    round(
        trade_stats.max_drawdown_amount_pct * 100,
        2
    ),
    "%"
)

print(
    "Peak:",
    trade_stats.max_drawdown_amount_peak_time
)

print(
    "Trough:",
    trade_stats.max_drawdown_amount_trough_time
)

print(
    "Recovery:",
    trade_stats.max_drawdown_amount_recovery_time
)

print(
    "Recovered:",
    trade_stats.max_drawdown_amount_recovered
)

print(
    "Duration:",
    trade_stats.max_drawdown_amount_duration
)


# ============================================================
# MAXIMUM PERCENTAGE DRAWDOWN
# ============================================================

print()
print("MAXIMUM PERCENTAGE DRAWDOWN")
print("-------------------------------------------------------")

print(
    "Percent:",
    round(
        trade_stats.max_drawdown_pct * 100,
        2
    ),
    "%"
)

print(
    "Amount:",
    round(
        trade_stats.max_drawdown_pct_amount,
        2
    )
)

print(
    "Peak:",
    trade_stats.max_drawdown_pct_peak_time
)

print(
    "Trough:",
    trade_stats.max_drawdown_pct_trough_time
)

print(
    "Recovery:",
    trade_stats.max_drawdown_pct_recovery_time
)

print(
    "Recovered:",
    trade_stats.max_drawdown_pct_recovered
)

print(
    "Duration:",
    trade_stats.max_drawdown_pct_duration
)


# ============================================================
# UNDERWATER PERIOD
# ============================================================

print()
print("UNDERWATER PERIOD")
print("-------------------------------------------------------")

print(
    "Longest underwater:",
    trade_stats.longest_underwater_duration
)

print("-------------------------------------------------------")

print()
print("ACCOUNT EVENT LEDGER")
print("-------------------------------------------------------")

print(
    "Events recorded:",
    len(
        backtest_result.account_events
    )
)

print()
print("FIRST 10 ACCOUNT EVENTS")

for event in (
    backtest_result.account_events[:10]
):

    print(
        event.timestamp,
        "|",
        event.event_type,
        "| amount:",
        round(
            event.amount,
            6
        ),
        "| balance:",
        round(
            event.balance_after,
            6
        ),
    )

print("-------------------------------------------------------")

# ============================================================
# INTRABAR RISK CURVE DIAGNOSTICS
# ============================================================

print()
print("INTRABAR RISK CURVE")
print("-------------------------------------------------------")

print(
    "Equity points:",
    len(
        backtest_result.equity_curve
    )
)

print(
    "Risk points:",
    len(
        backtest_result.risk_curve
    )
)


# ------------------------------------------------------------
# Count bars where intrabar equity was lower than
# bar-close equity
# ------------------------------------------------------------

intrabar_lower_count = sum(
    1
    for point in backtest_result.risk_curve
    if (
        point.intrabar_min_equity
        < point.bar_close_equity
    )
)

print(
    "Bars where intrabar equity < close equity:",
    intrabar_lower_count
)


# ------------------------------------------------------------
# Find lowest intrabar equity in entire backtest
# ------------------------------------------------------------

lowest_risk_point = min(
    backtest_result.risk_curve,
    key=lambda point: (
        point.intrabar_min_equity
    ),
)


print()
print(
    "Lowest intrabar equity:",
    lowest_risk_point.intrabar_min_equity
)

print(
    "Timestamp:",
    lowest_risk_point.timestamp
)

print(
    "Bar-close equity:",
    lowest_risk_point.bar_close_equity
)

print("-------------------------------------------------------")


# ============================================================
# RISK CURVE CONTRACT TESTS
# ============================================================

assert (
    len(
        backtest_result.risk_curve
    )
    ==
    len(
        backtest_result.equity_curve
    )
), (
    "Risk curve length does not match "
    "equity curve length."
)


assert all(
    point.intrabar_min_equity
    <= point.bar_close_equity + 1e-9
    for point
    in backtest_result.risk_curve
), (
    "Found a RiskPoint where intrabar minimum equity "
    "is greater than bar-close equity."
)


print()
print(
    "INTRABAR RISK CURVE CONTRACT: PASS"
)


###################################################################################
#                    PROP FIRM DIAGNOSTICS
###################################################################################

prop_daily_states = (
    build_prop_daily_states(
        backtest_result=(
            backtest_result
        ),
        config=prop_config,
    )
)

prop_daily_states = (
    evaluate_daily_loss_limits(
        backtest_result=backtest_result,
        daily_states=prop_daily_states,
        config=prop_config,
    )
)

prop_total_loss_state = (
    evaluate_total_loss_limit(
        backtest_result=backtest_result,
        config=prop_config,
    )
)

(
    first_prop_breach_rule,
    first_prop_breach_time,
    first_prop_breach_value,
) = get_first_prop_breach(
    daily_states=prop_daily_states,
    total_loss_state=prop_total_loss_state,
)
    
prop_trading_days_to_breach = (
    get_prop_trading_days_up_to(
        backtest_result=backtest_result,
        config=prop_config,
        cutoff_time=first_prop_breach_time,
    )
)
    
prop_trading_days = (
    get_prop_trading_days(
        backtest_result=backtest_result,
        config=prop_config,
    )
)

prop_evaluation = (
    evaluate_prop_firm(
        backtest_result=backtest_result,
        config=prop_config,
    )
)

# ============================================================
# TOTAL LOSS DIAGNOSTICS
# ============================================================

print()
print("TOTAL LOSS DIAGNOSTICS")
print("-------------------------------------------------------")

print(
    "Model:",
    prop_config.total_loss_model
)

print(
    "Measure:",
    prop_config.total_loss_measure
)

print(
    "Loss floor:",
    (
        round(
            prop_total_loss_state.loss_floor,
            2
        )
        if prop_total_loss_state.loss_floor
        is not None
        else None
    )
)

print(
    "Lowest observed value:",
    round(
        prop_total_loss_state.lowest_value,
        2
    )
)

print(
    "Lowest value time:",
    prop_total_loss_state.lowest_value_time
)

print(
    "Breached:",
    prop_total_loss_state.breached
)

print(
    "First breach value:",
    (
        round(
            prop_total_loss_state.breach_value,
            2
        )
        if prop_total_loss_state.breach_value
        is not None
        else None
    )
)

print(
    "First breach time:",
    prop_total_loss_state.breach_time
)

print("-------------------------------------------------------")

print()
print("PROP DAILY STATE DIAGNOSTICS")
print("-------------------------------------------------------")

print(
    "Prop days observed:",
    len(
        prop_daily_states
    )
)

# ============================================================
# EXACT PROP RESET EQUITY CHECK
# ============================================================

exact_reset_count = 0
missing_reset_count = 0


for state in prop_daily_states:

    exact_match = any(
        point.timestamp
        == state.reset_time
        for point
        in backtest_result.equity_curve
    )

    if exact_match:

        exact_reset_count += 1

    else:

        missing_reset_count += 1


print()
print("PROP RESET EQUITY COVERAGE")
print("-------------------------------------------------------")

print(
    "Prop days:",
    len(
        prop_daily_states
    )
)

print(
    "Exact reset observations:",
    exact_reset_count
)

print(
    "Missing exact reset observations:",
    missing_reset_count
)

print("-------------------------------------------------------")

print()
print("FIRST 5 PROP DAYS")
print("-------------------------------------------------------")

for state in prop_daily_states[:5]:

    print()

    print(
        "Trading day:",
        state.trading_day
    )

    print(
        "Reset:",
        state.reset_time
    )

    print(
        "Start balance:",
        round(
            state.start_balance,
            2
        )
    )

    print(
        "Start equity:",
        round(
            state.start_equity,
            2
        )
    )

    print(
        "Lowest balance:",
        round(
            state.lowest_balance,
            2
        ),
        "@",
        state.lowest_balance_time,
    )

    print(
        "Lowest equity:",
        round(
            state.lowest_equity,
            2
        ),
        "@",
        state.lowest_equity_time,
    )

    print(
        "Lowest intrabar equity:",
        round(
            state.lowest_intrabar_equity,
            2
        ),
        "@",
        state.lowest_intrabar_equity_time,
    )

    print(
        "Daily loss floor:",
        (
            round(
                state.daily_loss_floor,
                2
            )
            if state.daily_loss_floor
            is not None
            else None
        )
    )


print()
print("-------------------------------------------------------")

# ============================================================
# DAILY LOSS BREACH DIAGNOSTICS
# ============================================================

daily_breaches = [
    state
    for state in prop_daily_states
    if state.breached
]


print()
print("DAILY LOSS BREACH DIAGNOSTICS")
print("-------------------------------------------------------")

print(
    "Prop days observed:",
    len(prop_daily_states)
)

print(
    "Daily-loss breaches:",
    len(daily_breaches)
)

print()


for state in daily_breaches[:10]:

    print(
        state.trading_day,
        "| floor:",
        round(
            state.daily_loss_floor,
            2
        ),
        "| first breach value:",
        round(
            state.breach_value,
            2
        ),
        "| first breach time:",
        state.breach_time,
    )


print("-------------------------------------------------------")

# ============================================================
# FIRST PROP BREACH
# ============================================================

print()
print("FIRST PROP RULE BREACH")
print("-------------------------------------------------------")

print(
    "Rule:",
    first_prop_breach_rule
)

print(
    "Time:",
    first_prop_breach_time
)

print(
    "Value:",
    (
        round(
            first_prop_breach_value,
            2
        )
        if first_prop_breach_value
        is not None
        else None
    )
)

print("-------------------------------------------------------")

# ============================================================
# PROP TRADING-DAY DIAGNOSTICS
# ============================================================

print()
print("PROP TRADING-DAY DIAGNOSTICS")
print("-------------------------------------------------------")

print(
    "Prop periods observed:",
    len(
        prop_daily_states
    )
)

print(
    "Actual trading days:",
    len(
        prop_trading_days
    )
)

print(
    "Minimum required:",
    prop_config.minimum_trading_days
)

print(
    "Minimum satisfied:",
    (
        len(
            prop_trading_days
        )
        >= prop_config.minimum_trading_days
    )
)

print()
print("FIRST 10 TRADING DAYS")

for trading_day in (
    prop_trading_days[:10]
):

    print(
        trading_day
    )

print("-------------------------------------------------------")

# ============================================================
# SUNDAY TRADING-DAY DIAGNOSTIC
# ============================================================

print()
print("SUNDAY TRADING-DAY DIAGNOSTIC")
print("-------------------------------------------------------")

sunday_trades = []


for trade in backtest_result.trades:

    prop_day = (
        get_prop_trading_day(
            timestamp=trade.entry_time,
            config=prop_config,
        )
    )

    if prop_day.weekday() == 6:

        sunday_trades.append(
            (
                prop_day,
                trade.entry_time,
                trade.exit_time,
                trade.direction,
            )
        )


print(
    "Sunday trades:",
    len(
        sunday_trades
    )
)

print()
print("FIRST 10 SUNDAY TRADES")

for (
    prop_day,
    entry_time,
    exit_time,
    direction,
) in sunday_trades[:10]:

    print(
        prop_day,
        "| entry:",
        entry_time,
        "| exit:",
        exit_time,
        "| direction:",
        direction,
    )


print("-------------------------------------------------------")

# ============================================================
# TRADING DAYS TO FIRST BREACH
# ============================================================

print()
print("TRADING DAYS TO FIRST PROP BREACH")
print("-------------------------------------------------------")

print(
    "First breach:",
    first_prop_breach_time
)

print(
    "Trading days completed:",
    len(
        prop_trading_days_to_breach
    )
)

print(
    "Minimum required:",
    prop_config.minimum_trading_days
)

print(
    "Minimum satisfied at breach:",
    (
        len(
            prop_trading_days_to_breach
        )
        >= prop_config.minimum_trading_days
    )
)

print()
print("TRADING DAYS TO BREACH")

for trading_day in (
    prop_trading_days_to_breach
):

    print(
        trading_day
    )

print("-------------------------------------------------------")

# ============================================================
# FINAL GENERIC PROP EVALUATION
# ============================================================

print()
print("FINAL GENERIC PROP EVALUATION")
print("=======================================================")

print(
    "Provider:",
    prop_evaluation.provider_name
)

print(
    "Programme:",
    prop_evaluation.programme_name
)

print(
    "Phase:",
    prop_evaluation.phase_name
)

print()
print(
    "STATUS:",
    prop_evaluation.status
)

print(
    "Outcome time:",
    prop_evaluation.outcome_time
)

print(
    "Trading days at outcome:",
    prop_evaluation.trading_days
)

print()
print(
    "Profit target amount:",
    prop_evaluation.profit_target_amount
)

print(
    "Profit target balance:",
    prop_evaluation.profit_target_balance
)

print(
    "Valid profit target achieved:",
    prop_evaluation.profit_target_hit
)

print(
    "Profit target time:",
    prop_evaluation.profit_target_time
)

print()
print(
    "Total loss floor:",
    prop_evaluation.total_loss_floor
)

print(
    "Breach rule:",
    prop_evaluation.breach_rule
)

print(
    "Breach time:",
    prop_evaluation.breach_time
)

print(
    "Breach value:",
    prop_evaluation.breach_value
)

print("=======================================================")
    
#>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
#<<<<<<<<<<<<<<<<<<<<<<<<<<<< TEMPORARY CODE END  >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
#>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>

# ============================================================
# FINALISE RUN MANIFEST
# ============================================================

results_summary = {

    "backtest": {

        "rows_processed": (
            backtest_result.rows_processed
        ),

        "signals_generated": (
            signals_generated
        ),

        "closed_trades": (
            len(
                backtest_result.trades
            )
        ),

        "open_position_present": (
            backtest_result.open_position
            is not None
        ),

        "equity_points": (
            len(
                backtest_result.equity_curve
            )
        ),

        "risk_points": (
            len(
                backtest_result.risk_curve
            )
        ),

        "account_events": (
            len(
                backtest_result.account_events
            )
        ),
    },

    # --------------------------------------------------------
    # Architecture-aware execution summary.
    #
    # These fields deliberately describe the current engine
    # model and can later be extended with OrderBook /
    # PositionBook statistics.
    # --------------------------------------------------------

    "execution": {

        "position_model": (
            POSITION_MODEL
        ),

        "order_model": (
            ORDER_MODEL
        ),

        "completed_trade_records": (
            len(
                backtest_result.trades
            )
        ),
    },
}


final_manifest_path = (
    finalise_run_manifest(
        context=(
            run_context
        ),

        results_summary=(
            results_summary
        ),
    )
)


print()
print("RUN MANIFEST FINALISATION")
print("-------------------------------------------------------")

print(
    "Status: COMPLETED"
)

print(
    "Manifest:",
    final_manifest_path
)

print("-------------------------------------------------------")