# -*- coding: utf-8 -*-
"""
Created on Mon Sep 21 12:14:35 2026

@author: quant
"""

"""
NEXUS Run Logger
================

Purpose
-------
Duplicate NEXUS console output into the dedicated results
directory belonging to the current run.

Responsibilities
----------------
- Preserve normal Spyder / console output.
- Write identical output to run_log.txt.
- Flush output continuously.
- Avoid nested logging streams across repeated Spyder runs.
- Keep each log together with its run manifest and future
  outputs.

Does Not
--------
- Calculate model results.
- Generate tear sheets.
- Modify backtest behaviour.
- Contain strategy or model parameters.
"""


from pathlib import Path

import sys


# ============================================================
# BASE STREAMS
# ============================================================

_BASE_STDOUT = sys.stdout
_BASE_STDERR = sys.stderr

_ACTIVE_LOG_FILE = None


# ============================================================
# TEE STREAM
# ============================================================

class TeeStream:
    """
    Write output to both the console and the active log file.
    """

    def __init__(
        self,
        original_stream,
        log_file,
    ):

        self.original_stream = (
            original_stream
        )

        self.log_file = (
            log_file
        )


    def write(
        self,
        message,
    ):

        self.original_stream.write(
            message
        )

        self.log_file.write(
            message
        )

        self.flush()


    def flush(
        self,
    ):

        self.original_stream.flush()
        self.log_file.flush()


# ============================================================
# STOP RUN LOG
# ============================================================

def stop_run_log() -> None:
    """
    Restore normal console streams and close any active log.
    """

    global _ACTIVE_LOG_FILE

    sys.stdout = (
        _BASE_STDOUT
    )

    sys.stderr = (
        _BASE_STDERR
    )

    if (
        _ACTIVE_LOG_FILE
        is not None
    ):

        try:

            _ACTIVE_LOG_FILE.flush()
            _ACTIVE_LOG_FILE.close()

        finally:

            _ACTIVE_LOG_FILE = None


# ============================================================
# START RUN LOG
# ============================================================

def start_run_log(
    run_dir: Path,
):
    """
    Start duplicating stdout and stderr into the current run's
    log file.
    """

    global _ACTIVE_LOG_FILE

    # --------------------------------------------------------
    # Prevent nested TeeStreams during repeated Spyder runs.
    # --------------------------------------------------------

    stop_run_log()

    run_dir = Path(
        run_dir
    )

    run_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    log_path = (
        run_dir
        / "run_log.txt"
    )

    log_file = open(
        log_path,
        mode="w",
        encoding="utf-8",
    )

    _ACTIVE_LOG_FILE = (
        log_file
    )

    sys.stdout = TeeStream(
        original_stream=(
            _BASE_STDOUT
        ),
        log_file=(
            log_file
        ),
    )

    sys.stderr = TeeStream(
        original_stream=(
            _BASE_STDERR
        ),
        log_file=(
            log_file
        ),
    )

    return (
        log_path,
        log_file,
        _BASE_STDOUT,
        _BASE_STDERR,
    )