# -*- coding: utf-8 -*-
"""
Created on Thu Sep 10 16:17:09 2026

Work in progress - INTERMEDIATE TEST VERSION

@author: quant
"""

# 09_backtester/run_backtest.py

from pathlib import Path
import sys

import pandas as pd


# ============================================================
# PROJECT PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATA_MODULES = PROJECT_ROOT / "01_data"
INDICATOR_MODULES = PROJECT_ROOT / "02_indicators"
STRATEGY_MODULES = PROJECT_ROOT / "03_strategies" / "ichimoku_v1"
ENGINE_MODULES = PROJECT_ROOT / "04_engine"
RISK_MODULES = PROJECT_ROOT / "05_risk"
ANALYSIS_MODULES = PROJECT_ROOT / "06_analysis"
REPORTING_MODULES = PROJECT_ROOT / "07_reporting"
CONFIG_MODULES = PROJECT_ROOT / "08_config"


# Add project module folders to Python's import path
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
    sys.path.insert(0, str(module_path))


# ============================================================
# IMPORT PROJECT MODULES
# ============================================================

from data_loader import load_price_data
from data_preprocessor import preprocess_price_data
from data_validation import (
    validate_price_data,
    print_validation_report,
)

from strategy import Strategy
from config import StrategyConfig

from account_config import AccountConfig
from backtest_config import BacktestConfig
from ftmo_config import FTMOConfig

from legacy_engine import LegacyBacktestEngine

# ============================================================
# HISTORICAL DATA FILE
# ============================================================

DATA_FILE = (
    PROJECT_ROOT
    / "01_data"
    / "raw"
    / "USDJPY_5M_MID_mt5_040121_311221_ServerTime.csv"
)


# ============================================================
# CONFIGURATION
# ============================================================

strategy_config = StrategyConfig()

account_config = AccountConfig()

backtest_config = BacktestConfig()

ftmo_config = FTMOConfig()


# ============================================================
# LOAD DATA
# ============================================================

df = load_price_data(
    DATA_FILE
)


# ============================================================
# PREPROCESS DATA
# ============================================================

df = preprocess_price_data(
    df,
    legacy_mode=True
)


# ============================================================
# VALIDATE DATA
# ============================================================

validation_report = validate_price_data(
    df,
    expected_bar_minutes=5
)

print_validation_report(
    validation_report
)


# ============================================================
# CREATE STRATEGY
# ============================================================

strategy = Strategy(config=strategy_config)


# ============================================================
# RUN STRATEGY PIPELINE
# - calculate strategy indicators
# - generate entry signals
# ============================================================

signal_data = strategy.run(df)

from s4_diagnostics import (
    add_s4_diagnostic_features,
    build_no_s4_candidates,
    summarise_legacy_selection,
    add_forward_outcomes,
    add_26_bar_mfe_mae,
    summarise_feature_bins,
    add_path_outcomes,
    summarise_plus5_vs_minus5,
    calculate_feature_auc
)

diagnostic_data = add_s4_diagnostic_features(signal_data)

candidates = build_no_s4_candidates(diagnostic_data)

candidates = add_forward_outcomes(
    candidates,
    diagnostic_data
)

candidates = add_path_outcomes(
    candidates,
    diagnostic_data,
    stop_atr=5.0,
    breakeven_atr=5.0,
    target_atr=30.0,
    max_bars=500
)

print("\nCAUSAL FEATURE AUC")
print("----------------------------------------")

auc_results = calculate_feature_auc(candidates)

print(
    auc_results.to_string(
        index=False
    )
)

print("\n+5 FIRST vs -5 FIRST")
print("----------------------------------------")

print(
    summarise_plus5_vs_minus5(candidates)
    .round(3)
)

candidates = add_26_bar_mfe_mae(
    candidates,
    diagnostic_data
)

summary = summarise_legacy_selection(candidates)

features = [
    "dir_momentum_13_atr",
    "dir_momentum_26_atr",
    "dir_momentum_52_atr",
    "dir_range_position_26",
    "dir_range_break_atr",
    "adx",
    "adx_change_3",
    "adx_change_6"
]

outcomes = [
    "fwd_13_close_atr",
    "fwd_26_close_atr",
    "fwd_52_close_atr",
    "mfe_26_atr",
    "mae_26_atr"
]

features_to_test = [
    "dir_momentum_13_atr",
    "dir_momentum_26_atr",
    "dir_momentum_52_atr",
    "dir_range_position_26",
    "dir_range_break_atr",
    "adx",
    "adx_change_3",
    "adx_change_6"
]

print("\nCANDIDATE PATH OUTCOMES")
print("----------------------------------------")

print("Candidates:", len(candidates))

print(
    "+5 ATR first:",
    candidates["hit_plus_5_first"].sum()
)

print(
    "-5 ATR first:",
    candidates["hit_minus_5_first"].sum()
)

print(
    "Ambiguous ±5:",
    candidates["ambiguous_5_event"].sum()
)

print(
    "+30 ATR reached:",
    candidates["hit_plus_30"].sum()
)

print(
    "\nMean maximum favourable excursion:",
    round(candidates["max_favourable_atr"].mean(), 2),
    "ATR"
)

print(
    "Median maximum favourable excursion:",
    round(candidates["max_favourable_atr"].median(), 2),
    "ATR"
)

print("\nLEGACY S4 vs PATH OUTCOMES")
print("----------------------------------------")

comparison = candidates.groupby(
    "legacy_s4_selected"
).agg(
    candidates=("candidate_signal", "size"),
    plus5_first=("hit_plus_5_first", "mean"),
    minus5_first=("hit_minus_5_first", "mean"),
    hit_30=("hit_plus_30", "mean"),
    mean_mfe=("max_favourable_atr", "mean"),
    median_mfe=("max_favourable_atr", "median")
)

print(comparison.round(3))

for feature in features_to_test:

    print("\n")
    print("=" * 80)
    print("FEATURE:", feature)
    print("=" * 80)

    print(
        summarise_feature_bins(
            candidates,
            feature,
            bins=5
        ).round(3)
    )

print("\nFEATURE / FUTURE OUTCOME CORRELATIONS")
print("----------------------------------------")

print(
    candidates[features + outcomes]
    .corr()
    .loc[features, outcomes]
    .round(3)
)

print("\nS4 DIAGNOSTIC")
print("----------------------------------------")
print("No-S4 candidates:", len(candidates))
print(
    "Selected by legacy S4:",
    candidates["legacy_s4_selected"].sum()
)
print(
    "Rejected by legacy S4:",
    (~candidates["legacy_s4_selected"]).sum()
)

print("\nFEATURE COMPARISON")
print(summary)

# ---------------------------------------------------------
# Run legacy backtest engine
# ---------------------------------------------------------

engine = LegacyBacktestEngine(
    account_config=account_config,
    strategy_config=strategy_config,
    backtest_config=backtest_config
)

results = engine.run(signal_data)


# ---------------------------------------------------------
# Backtest results
# ---------------------------------------------------------

print("\nBACKTEST RESULTS")
print("----------------")
print("Final balance:", results["final_balance"])
print("Total profit:", results["total_profit"])
print("Closed trades:", len(results["trades"]))

print("\nFIRST TRADES")
print(results["trades"].head(10))

print(
    signal_data[
        [
            "timestamp",
            "close",
            "atr",
            "adx",
            "stoch_k",
            "tenkan",
            "kijun",
            "senkou_a",
            "senkou_b",
        ]
    ].tail(10)
)

# ============================================================
# SIGNAL COUNTS
# ============================================================

long_signals = int(
    signal_data["long_signal"].sum()
)

short_signals = int(
    signal_data["short_signal"].sum()
)

total_signals = int(
    (signal_data["entry_signal"] != 0).sum()
)


print("\nSTRATEGY SIGNAL REPORT")
print("-" * 50)

print(f"Rows:            {len(signal_data):,}")
print(f"Long signals:    {long_signals:,}")
print(f"Short signals:   {short_signals:,}")
print(f"Total signals:   {total_signals:,}")

print("-" * 50)


# ============================================================
# FILTER DIAGNOSTICS
# ============================================================

print("\nFILTER DIAGNOSTICS")
print("-" * 50)

print(
    f"S1 session bars:        "
    f"{signal_data['s1_session'].sum():,.0f}"
)

print(
    f"S2 long breakouts:       "
    f"{signal_data['s2_long'].sum():,.0f}"
)

print(
    f"S2 short breakouts:      "
    f"{signal_data['s2_short'].sum():,.0f}"
)

print(
    f"S3 long confirmations:   "
    f"{signal_data['s3_long'].sum():,.0f}"
)

print(
    f"S3 short confirmations:  "
    f"{signal_data['s3_short'].sum():,.0f}"
)

print(
    f"S4 long confirmations:   "
    f"{signal_data['s4_long'].sum():,.0f}"
)

print(
    f"S4 short confirmations:  "
    f"{signal_data['s4_short'].sum():,.0f}"
)

print(
    f"S5 long confirmations:   "
    f"{signal_data['s5_long'].sum():,.0f}"
)

print(
    f"S5 short confirmations:  "
    f"{signal_data['s5_short'].sum():,.0f}"
)

print(
    f"S6 ADX confirmations:     "
    f"{signal_data['s6_adx'].sum():,.0f}"
)

print("-" * 50)


# ============================================================
# SHOW FIRST 20 SIGNALS
# ============================================================

signal_rows = signal_data.loc[
    signal_data["entry_signal"] != 0,
    [
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        "atr",
        "adx",
        "stoch_k",
        "tenkan",
        "kijun",
        "senkou_a",
        "senkou_b",
        "entry_signal",
    ]
]


print("\nFIRST 20 SIGNALS")

print(
    signal_rows.head(20).to_string(
        index=False
    )
)

# ============================================================
# SAVE DIAGNOSTIC RESULTS TO EXCEL
# ============================================================

RESULTS_DIR = (
    PROJECT_ROOT
    / "10_results"
    / "signals"
)

RESULTS_DIR.mkdir(
    parents=True,
    exist_ok=True
)

OUTPUT_FILE = (
    RESULTS_DIR
    / "ichimoku_v1_signal_diagnostics.xlsx"
)


# All rows containing an entry signal
signal_export = signal_data.loc[
    signal_data["entry_signal"] != 0
].copy()


# Selected useful columns for easier inspection
signal_summary = signal_export[
    [
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        "spread",
        "atr",
        "adx",
        "stoch_k",
        "tenkan",
        "kijun",
        "senkou_a",
        "senkou_b",
        "chikou",
        "s1_session",
        "s2_long",
        "s2_short",
        "s3_long",
        "s3_short",
        "s4_long",
        "s4_short",
        "s5_long",
        "s5_short",
        "s6_adx",
        "long_signal",
        "short_signal",
        "entry_signal",
    ]
].copy()


with pd.ExcelWriter(
    OUTPUT_FILE,
    engine="openpyxl"
) as writer:

    # Every price bar + indicators + signal calculations
    signal_data.to_excel(
        writer,
        sheet_name="All_Data",
        index=False
    )

    # Only actual signal bars
    signal_summary.to_excel(
        writer,
        sheet_name="Signals",
        index=False
    )


print(
    f"\nDiagnostic workbook saved to:\n"
    f"{OUTPUT_FILE}"
)