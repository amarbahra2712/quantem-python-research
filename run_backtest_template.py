# -*- coding: utf-8 -*-
"""
Created on Sat Sep 12 10:27:33 2026
@author: quant


NEXUS backtest runner.

Purpose
-------
Provides the main entry point for running a NEXUS historical
strategy backtest.

The runner connects the major NEXUS components together. It
does not contain trading logic, execution logic, risk formulas
or performance-analysis logic itself.

Responsibilities
----------------
- establish project module paths
- select the strategy package to be tested
- select the historical JForex bid and ask data files
- load NEXUS configuration objects
- load historical market data
- preprocess market data into canonical NEXUS format
- validate market-data structure and quality
- initialise the selected strategy
- generate strategy indicators and signals
- provide the connection point for the backtest engine
- provide the connection point for prop-firm evaluation
- display a basic strategy-pipeline summary

Does not
--------
- calculate strategy indicators directly
- define trading signals
- calculate position sizing directly
- implement trade execution rules
- contain strategy-specific diagnostics
- contain prop-firm evaluation logic
- calculate detailed performance analytics
- generate detailed reports or research workbooks

How to use
----------
1. Select the strategy package using `STRATEGY_NAME`.
2. Select matching Dukascopy/JForex Bid and Ask files.
3. Configure the strategy, account, execution and backtest
   settings.
4. Run this file.
5. The runner passes data and configuration through the
   NEXUS pipeline.

Current pipeline
----------------
JForex Bid CSV
        |
        +----> data_loader.py
        |
JForex Ask CSV
                |
                v
        data_preprocessor.py
                |
                v
        data_validation.py
                |
                v
            Strategy
                |
                v
        Signal dataframe

The generic NEXUS backtest engine will be connected after
`04_engine` has been rebuilt.

Notes
-----
The market-data pipeline is timeframe-independent. JForex
1-minute, 5-minute, 15-minute, hourly or other bar periods can
be used without changing the runner's validation logic.

The validator infers the normal bar interval from the supplied
timestamps.

Detailed analysis and reporting should be handled by modules
in `06_analysis` and `07_reporting`.

Prop-firm rules should be evaluated separately from the core
backtest engine.
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

BID_FILE = (
    PROJECT_ROOT
    / "01_data"
    / "raw"
    / "GBPUSD_1 Min_Bid_2021.01.04_2021.12.31_UTC.csv"
)

ASK_FILE = (
    PROJECT_ROOT
    / "01_data"
    / "raw"
    / "GBPUSD_1 Min_Ask_2021.01.04_2021.12.31_UTC.csv"
)


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
from prop_config import PropConfig


# ============================================================
# CONFIGURATION
# ============================================================

strategy_config = StrategyConfig()

account_config = AccountConfig()

execution_config = ExecutionConfig()

backtest_config = BacktestConfig()

prop_config = PropConfig()


# ============================================================
# LOAD HISTORICAL DATA
# ============================================================

df = load_price_data(
    bid_file=BID_FILE,
    ask_file=ASK_FILE
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

print(
    f"Signals generated:    "
    f"{int((signal_data['entry_signal'] != 0).sum()):,}"
)

print("-" * 55)