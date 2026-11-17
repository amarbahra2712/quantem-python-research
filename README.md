# Quantem Python Research Portfolio

A work-in-progress portfolio of actuarial automation and quantitative research code. The projects are presented for software and modelling review; strategy results are experimental and do not represent investment performance.

## Projects

### NEXUS
A modular historical research and backtesting engine under active development. Its pipeline separates data loading and validation, indicators, strategy signals, execution, risk, analysis, prop-firm evaluation, configuration and run reporting.

The current engine integration supports one simultaneous position. Order and position components are being developed toward multi-position support. A recorded pipeline run processed 374,280 one-minute observations and generated 5,123 signals. This is a processing-scale example, not evidence of profitable performance; a recorded prop-firm evaluation failed its total-loss rule. Historical market data and generated run outputs are intentionally not included.

The author defines scope and milestones, integrates and reviews code changes, and runs scenario and regression checks against a baseline. AI tools assist with development.

### Earlier algorithmic trading tools
A selection of independently authored Python tools for historical data preparation, backtesting, parameter optimisation and performance analysis. The selected files also include a MetaTrader 5 script for live market-data processing, order placement, stop amendments and logging.

## Repository contents

- `NEXUS/` - modular engine, data, strategy, risk, analysis, configuration and runner source files.
- `Earlier_Algo_Tools/` - selected scripts from earlier research work.

## Data and setup

Market data, generated workbooks, run logs, environment files and Python bytecode are excluded. The source scripts have not been packaged as a turnkey application; file locations and dependencies may require local configuration. The older research scripts use libraries including pandas, NumPy, pandas-ta, Numba, QuantStats and tqdm. MetaTrader 5 data access requires its Python package and a configured local terminal.

## Development roadmap

The roadmap follows the order below so reporting and strategy research build on stable engine and results interfaces. Items describe planned work; they are not all implemented.

1. **Multi-order and multi-position architecture** - complete the separation and integration of order, fill, position and execution-lifecycle components; extend the engine from its current single-simultaneous-position behaviour.
2. **Structured reporting** - define generic results objects and a reporting layer for a tear sheet, prop-firm report and run comparison. The tear sheet is planned to cover account growth, drawdown, win/loss and R statistics, MAE/MFE, costs, holding time, long/short splits and session/time analysis. A separate prop-firm section is planned for status, first breach, daily-loss utilisation, trading days and target progress. Presentation will consume results objects rather than contain calculation logic.
3. **Interactive trade analysis** - add trade selection and filtering with executable bid/ask candles, entry, initial stop, target, breakeven changes, exit, MAE/MFE, spread, commission, R outcome and post-exit excursion. Planned filters include outcome, direction, hour and exit reason.
4. **First real strategy and strategy API** - establish a simple, clean strategy interface, then develop strategy features progressively. The intended research loop is strategy change, NEXUS run, tear sheet and prop report, suspicious-trade review and run-manifest comparison.
5. **Model documentation** - complete architecture and process-flow descriptions, input dictionary, module guides, calculation assumptions, outputs and diagnostics, limitations and future improvements. Planned dedicated chapters cover data lineage and accounting from executable bid/ask prices through trades, account events, equity/risk and prop evaluation, plus reproducibility and run-manifest versioning.
6. **Excel control dashboard** - after the parameter schema and reporting interface stabilise, use Excel as a thin control and record-keeping layer: select inputs, run Python, and write an input snapshot and tear-sheet summary to the workbook while retaining detailed machine-readable run outputs. Model calculations remain in Python.
7. **Generic Monte Carlo analysis** - after a real strategy provides a meaningful return series, build a strategy-independent analysis module for trade-order shuffling, bootstrap/resampling, parameter uncertainty, streaks, drawdown distributions, prop-rule breach and target-before-breach probabilities, time-to-target, ruin analysis and alternative risk levels.

## Current status

NEXUS remains in development. The current engine integration supports one simultaneous position; multi-position engine integration is the first roadmap milestone. Recorded runs demonstrate pipeline processing scale, not profitable trading performance.
