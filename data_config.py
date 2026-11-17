# -*- coding: utf-8 -*-
"""
Created on Mon Sep 21 10:55:51 2026

@author: quant
"""

"""
NEXUS Data Configuration
========================

Purpose
-------
Define the active historical market-data source used by NEXUS.

Responsibilities
----------------
- Define the active instrument and timeframe.
- Define BID and ASK source filenames.
- Resolve data paths relative to the NEXUS project root.
- Validate that configured source files exist.
- Keep data-source parameters out of run_backtest.py.

Does Not
--------
- Load market data.
- Validate market-data contents.
- Preprocess market data.
- Generate indicators.
- Generate strategy signals.
- Execute trades.

Architecture
------------
run_backtest.py
        |
        v
get_active_data_config()
        |
        v
DataConfig
        |
        v
data_loader.py

Paths are resolved relative to this project's directory rather
than using machine-specific absolute paths.

Notes
-----
Only data selection belongs here.

Data loading logic remains in:

    01_data/data_loader.py

Data validation logic remains in:

    01_data/data_validation.py

Data preprocessing remains in:

    01_data/data_preprocessor.py
"""


from dataclasses import dataclass
from pathlib import Path


# ============================================================
# PROJECT PATHS
# ============================================================

PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[1]
)

RAW_DATA_DIR = (
    PROJECT_ROOT
    / "01_data"
    / "raw"
)


# ============================================================
# DATA CONFIGURATION
# ============================================================

@dataclass(frozen=True)
class DataConfig:
    """
    Configuration for one historical market-data set.
    """

    instrument: str

    timeframe: str

    bid_filename: str

    ask_filename: str


    @property
    def bid_path(self) -> Path:
        """
        Return complete BID data-file path.
        """

        return (
            RAW_DATA_DIR
            / self.bid_filename
        )


    @property
    def ask_path(self) -> Path:
        """
        Return complete ASK data-file path.
        """

        return (
            RAW_DATA_DIR
            / self.ask_filename
        )


    def validate(self) -> None:
        """
        Validate configured historical data paths.
        """

        if not self.bid_path.exists():

            raise FileNotFoundError(
                "Configured BID data file does not exist:\n"
                f"{self.bid_path}"
            )

        if not self.ask_path.exists():

            raise FileNotFoundError(
                "Configured ASK data file does not exist:\n"
                f"{self.ask_path}"
            )


# ============================================================
# ACTIVE DATA SET
# ============================================================

def get_active_data_config() -> DataConfig:
    """
    Return the historical data set used by the current
    NEXUS run.

    Change data-selection parameters here rather than in
    run_backtest.py.
    
    INCLUDE THE FILE EXTENSION
    """

    return DataConfig(
        instrument="GBPUSD",

        timeframe="1m",

        bid_filename=(
            "GBPUSD_1 Min_Bid_2021.01.04_2021.12.31_UTC.csv"
        ),

        ask_filename=(
            "GBPUSD_1 Min_Ask_2021.01.04_2021.12.31_UTC.csv"
        ),
    )