# -*- coding: utf-8 -*-
"""
Created on Sat Sep 12 08:55:02 2026
@author: quant
04_engine/nexus_engine.py
"""

"""
NEXUS Backtest Execution Engine
===============================

Purpose
-------
Provide the core event-driven execution, position-management,
accounting and account-state simulation used by the NEXUS
backtesting framework.

Responsibilities
----------------
- Consume strategy instructions against historical market data.
- Execute entries using executable BID / ASK prices.
- Manage the currently open position.
- Process stop-loss, target and breakeven events.
- Apply deterministic same-bar execution rules.
- Calculate realised and unrealised P&L.
- Convert quote-currency P&L into account currency.
- Apply commission costs.
- Apply FX rollover / swap charges.
- Enforce configured overnight-position behaviour.
- Maintain realised account balance.
- Maintain bar-close account equity.
- Maintain intrabar worst-equity risk observations.
- Maintain a chronological account-event ledger.
- Record trade MAE / MFE.
- Produce completed Trade records.
- Produce EquityPoint and RiskPoint histories.
- Return a BacktestResult for downstream analysis.

Does Not
--------
- Generate trading signals.
- Define strategy logic.
- Contain prop-firm-specific rules.
- Decide which prop firm or programme is active.
- Produce reports or tear sheets.
- Perform Monte Carlo analysis.
- Model slippage in the current implementation.
- Support multiple simultaneous positions in the current
  single-position architecture.
- Support a general pending-order book in the current
  implementation.

Execution Model
---------------
Market analysis may use MID prices, while executable trading
uses BID / ASK prices.

Long positions:
    enter on ASK
    exit on BID

Short positions:
    enter on BID
    exit on ASK

The engine uses explicit same-bar event-resolution rules where
OHLC data cannot reveal the true intrabar price path.

Accounting Model
----------------
Commission and swap are posted to account balance when their
events occur.

Realised trade P&L is posted when the position closes.

Trade net P&L is therefore:

    gross P&L
    + swap
    + commission

but previously posted costs are not charged to account balance
again at trade close.

Account Event Ledger
--------------------
Timestamped balance-changing events are recorded separately for
items such as:

    entry commission
    exit commission
    swap / rollover
    realised trade P&L

This provides an auditable account timeline for downstream
risk and prop-firm evaluation.

Risk Model
----------
EquityPoint records bar-close mark-to-market account state.

RiskPoint records conservative intrabar minimum equity while
the simulated position could have been exposed during that bar.

This distinction is important for drawdown and prop-firm loss
rules, because an account can breach a limit intrabar and
recover before the candle closes.

Current Architecture
--------------------
The current engine supports one open position at a time.

Future development is expected to generalise this into:

    OrderBook
    PositionBook
    multiple market positions
    pending orders
    hedged positions
    partial closes
    basket management

The existing single-position behaviour should remain available
as a regression baseline during that migration.
"""


from dataclasses import dataclass
from typing import List, Optional, Tuple

import pandas as pd

from account_config import AccountConfig
from execution_config import ExecutionConfig
from backtest_config import BacktestConfig
from instrument_config import InstrumentConfig
from position_sizing import calculate_position_size

from trading_window_config import TradingWindowConfig
from trade_eligibility import evaluate_entry_eligibility

from id_generator import IdGenerator
from order_book import OrderBook
from position_book import PositionBook
from execution_lifecycle import ExecutionLifecycle
from position_models import Position as BookPosition

# ============================================================
# ENGINE METADATA
# ============================================================

ENGINE_NAME = "NEXUS"

ENGINE_VERSION = "base_v1"

POSITION_MODEL = "single_active_position"

ORDER_MODEL = "single_direct_entry"

# ============================================================
# COMPLETED TRADE
# ============================================================

@dataclass
class Trade:
    """
    Represents one completed NEXUS trade.
    """

    signal_time: pd.Timestamp
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp

    direction: int
    size: float

    entry_price: float
    exit_price: float

    initial_stop_price: Optional[float]
    target_price: Optional[float]

    initial_risk_distance: float

    # ---------------------------------------------------------
    # Excursion statistics
    # ---------------------------------------------------------

    mae_price_distance: float
    mfe_price_distance: float

    mae_r: float
    mfe_r: float

    # ---------------------------------------------------------
    # Exit
    # ---------------------------------------------------------

    exit_reason: str

    # ---------------------------------------------------------
    # P&L
    # ---------------------------------------------------------

    gross_pnl_quote: float
    gross_pnl_account: float

    swap_pnl_account: float
    rollover_events: int
    rollover_units: float
    
    commission_pnl_account: float

    net_pnl_account: float


# ============================================================
# EQUITY POINT
# ============================================================

@dataclass
class EquityPoint:
    """
    Represents account state at one historical timestamp.

    Equity includes unrealised P&L from any open position.
    """

    timestamp: pd.Timestamp

    balance: float
    equity: float

    unrealised_pnl_account: float
    
# ============================================================
# RISK POINT
# ============================================================

@dataclass
class RiskPoint:
    """
    Represents the worst simulated account equity observed
    during one historical bar.

    This is separate from EquityPoint.

    EquityPoint:
        bar-close mark-to-market account state

    RiskPoint:
        conservative minimum equity while the position could
        actually have been alive during the bar

    RiskPoint is intended for:

        prop-firm loss-limit evaluation
        intrabar drawdown analysis
        risk diagnostics

    It does not modify trading behaviour.
    """

    timestamp: pd.Timestamp

    balance: float

    intrabar_min_equity: float

    bar_close_equity: float

# ============================================================
# ACCOUNT EVENT
# ============================================================

@dataclass
class AccountEvent:
    """
    Represents one timestamped realised account-balance event.

    Examples:

        entry commission
        exit commission
        swap / rollover
        realised trade P&L

    The event ledger provides an exact chronological audit
    trail of changes to realised account balance.
    """

    timestamp: pd.Timestamp

    event_type: str

    amount: float

    balance_after: float

# ============================================================
# BACKTEST RESULT
# ============================================================

@dataclass
class BacktestResult:
    """
    Summary of one completed NEXUS backtest run.
    """

    starting_balance: float
    ending_balance: float
    ending_equity: float

    trades: List[Trade]
    
    equity_curve: List[EquityPoint]
    risk_curve: List[RiskPoint]
    
    account_events: List[AccountEvent]

    open_position: Optional[BookPosition]

    rows_processed: int

# ============================================================
# NEXUS ENGINE
# ============================================================

class NexusEngine:
    """
    Generic NEXUS historical execution engine.

    Version 1 supports one open position at a time.

    The execution loop and trade-management behaviour will be
    added incrementally.
    """

    def __init__(
        self,
        instrument_config: InstrumentConfig,
        account_config: AccountConfig,
        execution_config: ExecutionConfig,
        backtest_config: BacktestConfig,
        trading_window_config: TradingWindowConfig,
    ):
        self.instrument_config = instrument_config
        self.account_config = account_config
        self.execution_config = execution_config
        self.backtest_config = backtest_config
        self.trading_window_config = trading_window_config

        self.balance = account_config.starting_balance
        self.equity = account_config.starting_balance

        self.trades: List[Trade] = []
        self.equity_history: List[EquityPoint] = []
        self.risk_history: List[RiskPoint] = []
        self.account_events: List[AccountEvent] = []
        
        # ----------------------------------------------------
        # Order / execution / position infrastructure.
        # ----------------------------------------------------

        self._initialise_execution_architecture()        
        
    # ========================================================
    # MULTI-POSITION ARCHITECTURE
    # ========================================================

    def _initialise_execution_architecture(
        self,
    ) -> None:
        """
        Initialise the OrderBook / PositionBook execution
        infrastructure.
        
        Fresh objects are created whenever the engine is reset,
        ensuring a clean execution state for each backtest run.
        """

        self.id_generator = (
            IdGenerator()
        )

        self.order_book = (
            OrderBook(
                id_generator=(
                    self.id_generator
                )
            )
        )

        self.position_book = (
            PositionBook(
                id_generator=(
                    self.id_generator
                )
            )
        )

        self.execution_lifecycle = (
            ExecutionLifecycle(
                order_book=(
                    self.order_book
                ),

                position_book=(
                    self.position_book
                ),
            )
        )
        
        
    # ========================================================
    # OPEN-POSITION STATE
    # ========================================================

    def _has_open_position(
        self,
    ) -> bool:
        """
        Return whether live position exposure currently exists.

        PositionBook is authoritative for open-position state.
        """

        return (
            len(
                self.position_book.active_positions()
            )
            > 0
        )    

   

    # ========================================================
    # OPTIONAL ACTIVE POSITION ACCESS
    # ========================================================

    def _get_optional_active_position(
        self,
    ):
        """
        Return the active PositionBook Position when one exists.

        Returns None when no live position exists.

        The current engine mode permits at most one active
        position.
        """

        active_positions = (
            self.position_book.active_positions()
        )

        if (
            len(
                active_positions
            )
            == 0
        ):

            return None

        if (
            len(
                active_positions
            )
            != 1
        ):

            raise RuntimeError(
                "Compatibility mode requires at most one "
                "active PositionBook position."
            )

        return (
            active_positions[
                0
            ]
        )

    def reset(self) -> None:
        """
        Reset the engine to its initial account state.
        """

        self.balance = self.account_config.starting_balance
        self.equity = self.account_config.starting_balance

        self.trades = []
        self.equity_history = []
        self.risk_history = []
        self.account_events = []
        
        self._initialise_execution_architecture()
        
    # ========================================================
    # ACCOUNT EVENT LEDGER
    # ========================================================

    def _record_account_event(
        self,
        timestamp: pd.Timestamp,
        event_type: str,
        amount: float,
    ) -> None:
        """
        Record one realised account-balance event.

        The balance must already have been updated before this
        method is called.
        """

        timestamp = pd.Timestamp(
            timestamp
        )

        if timestamp.tzinfo is None:

            raise ValueError(
                "Account-event timestamp must be "
                "timezone-aware."
            )

        if not event_type:

            raise ValueError(
                "Account-event type cannot be empty."
            )

        event = AccountEvent(
            timestamp=timestamp,
            event_type=event_type,
            amount=float(amount),
            balance_after=float(
                self.balance
            ),
        )

        self.account_events.append(
            event
        )
                
    def _get_entry_price(
        self,
        execution_bar: pd.Series,
        direction: int,
    ) -> float:
        """
        Return the executable market price for a new position.

        Parameters
        ----------
        execution_bar : pd.Series
            The historical bar on which the trade is executed.

        direction : int
            Trade direction:

                1  = long
               -1  = short

        Returns
        -------
        float
            Executable entry price.

        Notes
        -----
        Long positions are opened by buying at the ask.

        Short positions are opened by selling at the bid.

        Under `entry_timing="next_open"`, the execution bar is
        the bar immediately following the signal bar.
        """

        if direction == 1:
            price_column = "ask_open"

        elif direction == -1:
            price_column = "bid_open"

        else:
            raise ValueError(
                "Entry direction must be 1 for long "
                "or -1 for short."
            )

        if price_column not in execution_bar.index:
            raise ValueError(
                f"Required execution price column missing: "
                f"{price_column}"
            )

        entry_price = execution_bar[price_column]

        if pd.isna(entry_price):
            raise ValueError(
                f"Missing entry price in {price_column}."
            )

        if entry_price <= 0:
            raise ValueError(
                f"Invalid entry price in {price_column}: "
                f"{entry_price}"
            )

        return float(entry_price)
    
    def _get_entry_execution(
        self,
        df: pd.DataFrame,
        signal_index: int,
        direction: int,
    ) -> Tuple[pd.Timestamp, float]:
        """
        Resolve the execution time and price for an entry signal.
    
        A signal generated on bar i is executed at the opening
        executable price of bar i + 1.
        """
    
        if self.backtest_config.entry_timing != "next_open":
            raise ValueError(
                "NEXUS engine V1 currently supports only "
                "entry_timing='next_open'."
            )
    
        execution_index = signal_index + 1
    
        if execution_index >= len(df):
            raise ValueError(
                "Cannot execute signal because there is no "
                "following bar in the dataset."
            )
    
        execution_bar = df.iloc[execution_index]
    
        if "timestamp" not in execution_bar.index:
            raise ValueError(
                "Required timestamp column is missing."
            )
    
        execution_time = execution_bar["timestamp"]
    
        if pd.isna(execution_time):
            raise ValueError(
                "Execution bar contains a missing timestamp."
            )
    
        entry_price = self._get_entry_price(
            execution_bar=execution_bar,
            direction=direction,
        )
    
        return execution_time, entry_price
    
    
    def _resolve_price_level(
        self,
        entry_price: float,
        direction: int,
        level_type: str,
        absolute_price: Optional[float] = None,
        distance: Optional[float] = None,
    ) -> Optional[float]:
        """
        Resolve a trade-management instruction into an absolute
        market price.
    
        Parameters
        ----------
        entry_price : float
            Actual executable trade entry price.
    
        direction : int
            Trade direction:
    
                1  = long
               -1  = short
    
        level_type : str
            Type of price level being resolved:
    
                "stop"
                "target"
                "breakeven_trigger"
    
        absolute_price : float, optional
            Explicit market price supplied by the strategy.
    
        distance : float, optional
            Price distance from the actual executable entry.
    
            This must already be expressed in raw price units,
            not pips or ATR multiples.
    
        Returns
        -------
        float or None
            Resolved absolute price level.
    
            Returns None when neither an absolute price nor a
            distance has been supplied.
    
        Notes
        -----
        A strategy may supply either:
    
            absolute_price
    
        or:
    
            distance
    
        but not both for the same level.
    
        Examples:
    
            fixed-pip stop
                -> converted to price distance before reaching
                   this method
    
            ATR stop
                -> converted to price distance before reaching
                   this method
    
            liquidity-based stop
                -> supplied directly as absolute_price
        """
    
        if direction not in (1, -1):
            raise ValueError(
                "Direction must be 1 for long or -1 for short."
            )
    
        valid_level_types = (
            "stop",
            "target",
            "breakeven_trigger",
        )
    
        if level_type not in valid_level_types:
            raise ValueError(
                f"Unsupported level_type: {level_type}"
            )
    
        if entry_price <= 0:
            raise ValueError(
                f"Invalid entry price: {entry_price}"
            )
    
        if absolute_price is not None and distance is not None:
            raise ValueError(
                "Provide either absolute_price or distance, "
                "not both."
            )
    
        if absolute_price is None and distance is None:
            return None
    
        # -----------------------------------------------------
        # Explicit absolute price
        # -----------------------------------------------------
    
        if absolute_price is not None:
    
            if absolute_price <= 0:
                raise ValueError(
                    f"Invalid absolute price: {absolute_price}"
                )
    
            resolved_price = float(absolute_price)
    
        # -----------------------------------------------------
        # Distance from executable entry
        # -----------------------------------------------------
    
        else:
    
            if distance <= 0:
                raise ValueError(
                    f"Distance must be positive: {distance}"
                )
    
            if level_type == "stop":
                resolved_price = (
                    entry_price - direction * distance
                )
    
            else:
                resolved_price = (
                    entry_price + direction * distance
                )
    
        # -----------------------------------------------------
        # Validate level position relative to entry
        # -----------------------------------------------------
    
        if level_type == "stop":
    
            if direction == 1 and resolved_price >= entry_price:
                raise ValueError(
                    "Long stop must be below entry price."
                )
    
            if direction == -1 and resolved_price <= entry_price:
                raise ValueError(
                    "Short stop must be above entry price."
                )
    
        else:
    
            if direction == 1 and resolved_price <= entry_price:
                raise ValueError(
                    f"Long {level_type} must be above "
                    f"entry price."
                )
    
            if direction == -1 and resolved_price >= entry_price:
                raise ValueError(
                    f"Short {level_type} must be below "
                    f"entry price."
                )
    
        return float(resolved_price)
    
    
    def _open_position(
        self,
        df: pd.DataFrame,
        signal_index: int,
        direction: int,
        stop_price: Optional[float] = None,
        stop_distance: Optional[float] = None,
        target_price: Optional[float] = None,
        target_distance: Optional[float] = None,
        breakeven_trigger_price: Optional[float] = None,
        breakeven_trigger_distance: Optional[float] = None,
    ):
        """
        Open a new position from a strategy entry signal.
    
        Parameters
        ----------
        df : pd.DataFrame
            Prepared historical market data.
    
        signal_index : int
            Positional index of the bar on which the strategy
            generated the entry signal.
    
        direction : int
            Trade direction:
    
                1  = long
               -1  = short
    
        size : float
            Position size supplied by the risk layer.
    
        stop_price : float, optional
            Explicit absolute stop price.
    
        stop_distance : float, optional
            Stop distance from the actual executable entry.
    
        target_price : float, optional
            Explicit absolute profit-target price.
    
        target_distance : float, optional
            Target distance from the actual executable entry.
    
        breakeven_trigger_price : float, optional
            Explicit absolute price at which the stop should
            later be moved to breakeven.
    
        breakeven_trigger_distance : float, optional
            Distance from entry at which the breakeven rule
            should later become active.
    
        Returns
        -------
        Position
            Newly opened position.
    
        Notes
        -----
        Only one position may be open at a time in NEXUS V1.
    
        For each stop, target or breakeven trigger, the strategy
        may supply either an absolute price or a price distance,
        but not both.
    
        Distance-based instructions are resolved from the
        actual executable entry price.
    
        Absolute structural levels are preserved exactly,
        provided they remain valid relative to the actual entry.
        """
    
        if (
            self._has_open_position()
        ):

            raise ValueError(
                "Cannot open a new position while another "
                "position is already open."
            )
    
        if direction not in (1, -1):
            raise ValueError(
                "Direction must be 1 for long or -1 for short."
            )
    
            
        if signal_index < 0 or signal_index >= len(df):
            raise ValueError(
                f"Invalid signal_index: {signal_index}"
            )
    
        signal_bar = df.iloc[signal_index]
    
        if "timestamp" not in signal_bar.index:
            raise ValueError(
                "Required timestamp column is missing."
            )
    
        signal_time = signal_bar["timestamp"]
    
        if pd.isna(signal_time):
            raise ValueError(
                "Signal bar contains a missing timestamp."
            )
    
        # -----------------------------------------------------
        # Resolve actual executable entry
        # -----------------------------------------------------
    
        entry_time, entry_price = self._get_entry_execution(
            df=df,
            signal_index=signal_index,
            direction=direction,
        )
    
        # -----------------------------------------------------
        # Resolve stop
        # -----------------------------------------------------
    
        resolved_stop_price = self._resolve_price_level(
            entry_price=entry_price,
            direction=direction,
            level_type="stop",
            absolute_price=stop_price,
            distance=stop_distance,
        )
    
        # -----------------------------------------------------
        # Calculate position size
        # -----------------------------------------------------
        
        if resolved_stop_price is None:
            raise ValueError(
                "NEXUS V1 requires a stop price in order to "
                "calculate risk-based position size."
            )
        
        actual_stop_distance = abs(
            entry_price - resolved_stop_price
        )
        
        size = calculate_position_size(
            balance=self.balance,
            entry_price=entry_price,
            stop_distance=actual_stop_distance,
            risk_per_trade=self.account_config.risk_per_trade,
            account_currency=self.account_config.account_currency,
            base_currency=self.instrument_config.base_currency,
            quote_currency=self.instrument_config.quote_currency,
            use_margin_limit=self.account_config.use_margin_limit,
            margin_requirement=self.account_config.margin_requirement,
            max_margin_fraction=self.account_config.max_margin_fraction,
        )
        
        if size <= 0:
            raise ValueError(
                f"Calculated position size is invalid: {size}"
            )
    
        # -----------------------------------------------------
        # Resolve target
        # -----------------------------------------------------
    
        resolved_target_price = self._resolve_price_level(
            entry_price=entry_price,
            direction=direction,
            level_type="target",
            absolute_price=target_price,
            distance=target_distance,
        )
    
        # -----------------------------------------------------
        # Resolve breakeven trigger
        # -----------------------------------------------------
    
        resolved_breakeven_trigger = self._resolve_price_level(
            entry_price=entry_price,
            direction=direction,
            level_type="breakeven_trigger",
            absolute_price=breakeven_trigger_price,
            distance=breakeven_trigger_distance,
        )
    
        # -----------------------------------------------------
        # Create authoritative market Order
        # -----------------------------------------------------

        order = (
            self.order_book.create_order(
                signal_time=(
                    signal_time
                ),

                submitted_time=(
                    signal_time
                ),

                direction=(
                    direction
                ),

                size=(
                    float(size)
                ),

                order_type="market",

                role="primary",
            )
        )

        # -----------------------------------------------------
        # Calculate entry-side commission
        #
        # Calculation is independent of Position creation.
        # -----------------------------------------------------

        entry_commission_account = (
            self._calculate_commission_account(
                position_size=(
                    float(size)
                ),

                execution_price=(
                    entry_price
                ),
            )
        )

        # -----------------------------------------------------
        # Record executable Fill and create the authoritative
        # PositionBook Position.
        # -----------------------------------------------------

        position = (
            self.execution_lifecycle.record_entry_fill(
                order_id=(
                    order.order_id
                ),

                fill_time=(
                    entry_time
                ),

                size=(
                    float(size)
                ),

                fill_price=(
                    entry_price
                ),

                commission_pnl_account=(
                    entry_commission_account
                ),

                initial_stop_price=(
                    resolved_stop_price
                ),

                stop_price=(
                    resolved_stop_price
                ),

                target_price=(
                    resolved_target_price
                ),

                breakeven_trigger_price=(
                    resolved_breakeven_trigger
                ),

                initial_risk_distance=(
                    actual_stop_distance
                ),
            )
        )

        # -----------------------------------------------------
        # Post entry commission to the account exactly once.
        #
        # The commission has already been stored on the Fill
        # and Position by ExecutionLifecycle.
        # -----------------------------------------------------

        self._post_commission_to_account(
            commission_account=(
                entry_commission_account
            ),

            side="entry",

            event_time=(
                entry_time
            ),
        )

        return position
    
    # --------------------------------------------------------
    #
    # --------------------------------------------------------

    def _record_position_close(
        self,
        position,
        exit_time: pd.Timestamp,
        exit_price: float,
        exit_reason: str,
    ) -> None:
        """
        Record a completed position close in PositionBook.

        The supplied position is the authoritative
        PositionBook Position.

        Account balance, commission posting and trade-record
        calculations are handled before this method
        records the PositionClose.
        """

        # ----------------------------------------------------
        # Current engine mode closes the complete remaining
        # open position.
        # ----------------------------------------------------

        self.position_book.close_position(
            position_id=(
                position.position_id
            ),

            close_time=(
                exit_time
            ),

            size=(
                position.open_size
            ),

            exit_price=(
                exit_price
            ),

            reason=(
                exit_reason
            ),

            commission_pnl_account=(
                position.exit_commission_pnl_account
            ),

            commission_already_applied=True,
        )

    # ========================================================
    # POSITION EXCURSION TRACKING
    # ========================================================

    def _update_position_excursions(
        self,
        position: BookPosition,
        bar: pd.Series,
        event: Optional[str] = None,
    ) -> None:
        """
        Update MAE and MFE for the current open position.

        Parameters
        ----------
        bar : pd.Series
            Historical market-data bar.

        event : str, optional
            Resolved event for the current bar.

            Supported values:

                None
                "stop"
                "target"
                "breakeven_stop"

        Notes
        -----
        MAE and MFE are measured using executable exit-side
        prices.

        Long positions use BID prices.

        Short positions use ASK prices.

        On bars where the trade remains open, the full bar
        high and low are used.

        On an exit bar, only the excursion guaranteed by the
        resolved exit event is added. This avoids counting
        price movement that may have occurred after the trade
        had already closed.
        """

        

        # -----------------------------------------------------
        # Select executable market side
        # -----------------------------------------------------

        if position.direction == 1:
            high_column = "bid_high"
            low_column = "bid_low"

        elif position.direction == -1:
            high_column = "ask_high"
            low_column = "ask_low"

        else:
            raise ValueError(
                f"Invalid position direction: "
                f"{position.direction}"
            )

        for column in (high_column, low_column):

            if column not in bar.index:
                raise ValueError(
                    f"Required excursion price column missing: "
                    f"{column}"
                )

            if pd.isna(bar[column]):
                raise ValueError(
                    f"Missing excursion price in {column}."
                )

        bar_high = float(bar[high_column])
        bar_low = float(bar[low_column])

        # -----------------------------------------------------
        # Normal bar - position survives the bar
        # -----------------------------------------------------

        if event is None:

            if position.direction == 1:

                adverse_distance = max(
                    0.0,
                    position.entry_price - bar_low,
                )

                favorable_distance = max(
                    0.0,
                    bar_high - position.entry_price,
                )

            else:

                adverse_distance = max(
                    0.0,
                    bar_high - position.entry_price,
                )

                favorable_distance = max(
                    0.0,
                    position.entry_price - bar_low,
                )

            position.mae_price_distance = max(
                position.mae_price_distance,
                adverse_distance,
            )

            position.mfe_price_distance = max(
                position.mfe_price_distance,
                favorable_distance,
            )

            return

        # -----------------------------------------------------
        # Stop exit
        # -----------------------------------------------------

        if event == "stop":

            if position.stop_price is None:
                raise ValueError(
                    "Cannot update stop excursion because "
                    "stop_price is missing."
                )

            adverse_distance = abs(
                position.entry_price
                - position.stop_price
            )

            position.mae_price_distance = max(
                position.mae_price_distance,
                adverse_distance,
            )

            return

        # -----------------------------------------------------
        # Target exit
        # -----------------------------------------------------

        if event == "target":

            if position.target_price is None:
                raise ValueError(
                    "Cannot update target excursion because "
                    "target_price is missing."
                )

            favorable_distance = abs(
                position.target_price
                - position.entry_price
            )

            position.mfe_price_distance = max(
                position.mfe_price_distance,
                favorable_distance,
            )

            return

        # -----------------------------------------------------
        # Same-bar breakeven exit
        # -----------------------------------------------------

        if event == "breakeven_stop":

            if position.breakeven_trigger_price is not None:

                favorable_distance = abs(
                    position.breakeven_trigger_price
                    - position.entry_price
                )

                position.mfe_price_distance = max(
                    position.mfe_price_distance,
                    favorable_distance,
                )

            return

        raise ValueError(
            f"Unsupported excursion event: {event}"
        )
        
    def _get_position_bar_events(
        self,
        position: BookPosition,
        bar: pd.Series,
    ) -> dict:
        """
        Determine which active position levels were touched by
        a historical bar.

        Parameters
        ----------
        bar : pd.Series
            Historical market-data bar.

        Returns
        -------
        dict
            Boolean flags indicating whether the current bar
            touched:

                stop
                target
                breakeven_trigger

        Notes
        -----
        Long positions are closed by selling at the bid.
        Therefore long stop, target and breakeven conditions
        are evaluated using bid prices.

        Short positions are closed by buying at the ask.
        Therefore short stop, target and breakeven conditions
        are evaluated using ask prices.

        This method only detects events. It does not decide
        event ordering when multiple levels are touched within
        the same bar.
        """


        events = {
            "stop": False,
            "target": False,
            "breakeven_trigger": False,
        }

        # -----------------------------------------------------
        # Select executable exit side
        # -----------------------------------------------------

        if position.direction == 1:
            high_column = "bid_high"
            low_column = "bid_low"

        elif position.direction == -1:
            high_column = "ask_high"
            low_column = "ask_low"

        else:
            raise ValueError(
                f"Invalid position direction: "
                f"{position.direction}"
            )

        for column in (high_column, low_column):
            if column not in bar.index:
                raise ValueError(
                    f"Required execution price column missing: "
                    f"{column}"
                )

            if pd.isna(bar[column]):
                raise ValueError(
                    f"Missing execution price in {column}."
                )

        bar_high = float(bar[high_column])
        bar_low = float(bar[low_column])

        # -----------------------------------------------------
        # Long position
        # -----------------------------------------------------

        if position.direction == 1:

            if (
                position.stop_price is not None
                and bar_low <= position.stop_price
            ):
                events["stop"] = True

            if (
                position.target_price is not None
                and bar_high >= position.target_price
            ):
                events["target"] = True

            if (
                position.breakeven_trigger_price is not None
                and not position.breakeven_applied
                and bar_high >= position.breakeven_trigger_price
            ):
                events["breakeven_trigger"] = True

        # -----------------------------------------------------
        # Short position
        # -----------------------------------------------------

        else:

            if (
                position.stop_price is not None
                and bar_high >= position.stop_price
            ):
                events["stop"] = True

            if (
                position.target_price is not None
                and bar_low <= position.target_price
            ):
                events["target"] = True

            if (
                position.breakeven_trigger_price is not None
                and not position.breakeven_applied
                and bar_low <= position.breakeven_trigger_price
            ):
                events["breakeven_trigger"] = True

        return events

    def _resolve_position_bar_event(
        self,
        events: dict,
    ) -> Optional[str]:
        """
        Resolve detected same-bar position events according to
        the configured backtest policy.

        Parameters
        ----------
        events : dict
            Boolean event flags returned by
            `_get_position_bar_events`.

        Returns
        -------
        str or None
            One of:

                "stop"
                "target"
                "breakeven_trigger"
                None

        Notes
        -----
        NEXUS V1 currently supports:

            same_bar_policy = "stop_first"

        Under this conservative policy, a stop takes priority
        whenever the same OHLC bar also touches another active
        trade-management level.

        If target and breakeven trigger are both touched, but
        the stop is not touched, the target takes priority
        because the position is closed at the target.
        """

        required_events = (
            "stop",
            "target",
            "breakeven_trigger",
        )

        for event_name in required_events:
            if event_name not in events:
                raise ValueError(
                    f"Missing position event flag: "
                    f"{event_name}"
                )

        if self.backtest_config.same_bar_policy != "stop_first":
            raise ValueError(
                "NEXUS engine V1 currently supports only "
                "same_bar_policy='stop_first'."
            )

        # -----------------------------------------------------
        # Conservative same-bar priority
        # -----------------------------------------------------

        if events["stop"]:
            return "stop"

        if events["target"]:
            return "target"

        if events["breakeven_trigger"]:
            return "breakeven_trigger"

        return None

    def _apply_breakeven(
        self,
        position: BookPosition
    ) -> None:
        """
        Move the active stop of the current position to its
        executable entry price.

        Notes
        -----
        The original stop is preserved in
        `initial_stop_price`.

        Only `stop_price` is changed.

        This means later analysis can still recover the
        position's original risk while the live simulation
        uses the updated breakeven stop.
        """

        
        if (
            position.breakeven_trigger_price
            is None
        ):
        
            raise ValueError(
                "Cannot apply breakeven because this position "
                "has no breakeven trigger."
            )
        
        if (
            position.breakeven_applied
        ):
        
            return
        
        position.stop_price = (
            position.entry_price
        )
        
        position.breakeven_applied = True
    
    def _convert_quote_pnl_to_account(
        self,
        pnl_quote: float,
        conversion_price: float,
    ) -> float:
        """
        Convert trade P&L from the instrument's quote currency
        into the account currency.

        NEXUS V1 supports:

        - account currency = quote currency
        - account currency = base currency

        More complex cross-currency conversion can be added
        later.
        """

        account_currency = (
            self.account_config.account_currency.upper()
        )

        base_currency = (
            self.instrument_config.base_currency.upper()
        )

        quote_currency = (
            self.instrument_config.quote_currency.upper()
        )

        # Quote currency already equals account currency.
        if account_currency == quote_currency:
            return float(pnl_quote)

        # Account currency equals base currency.
        if account_currency == base_currency:

            if conversion_price <= 0:
                raise ValueError(
                    f"Invalid conversion price: "
                    f"{conversion_price}"
                )

            return float(
                pnl_quote / conversion_price
            )

        raise ValueError(
            "NEXUS V1 cannot convert trade P&L when the "
            "account currency is neither the instrument's "
            "base nor quote currency. "
            f"Instrument={self.instrument_config.symbol}, "
            f"base={base_currency}, "
            f"quote={quote_currency}, "
            f"account={account_currency}."
        )        
    
    # ========================================================
    # ROLLOVER BOUNDARY DETECTION
    # ========================================================

    def _get_rollover_boundaries_between(
        self,
        start_time: pd.Timestamp,
        end_time: pd.Timestamp,
    ) -> List[pd.Timestamp]:
        """
        Return all applicable FX rollover boundaries crossed
        between two historical timestamps.

        A rollover is included when:

            start_time < rollover_time <= end_time

        The rollover time and timezone come from
        ExecutionConfig.

        Saturday and Sunday rollover boundaries are skipped.

        This method detects rollover events only. It does not
        close positions or apply financing.
        """

        start_time = pd.Timestamp(
            start_time
        )

        end_time = pd.Timestamp(
            end_time
        )

        # ----------------------------------------------------
        # Validate timestamps
        # ----------------------------------------------------

        if start_time.tzinfo is None:
            raise ValueError(
                "start_time must be timezone-aware."
            )

        if end_time.tzinfo is None:
            raise ValueError(
                "end_time must be timezone-aware."
            )

        if end_time <= start_time:
            raise ValueError(
                "end_time must be later than start_time."
            )

        timezone = (
            self.execution_config
            .swap_rollover_timezone
        )

        rollover_hour = (
            self.execution_config
            .swap_rollover_hour
        )

        rollover_minute = (
            self.execution_config
            .swap_rollover_minute
        )

        # ----------------------------------------------------
        # Convert interval into rollover timezone
        # ----------------------------------------------------

        start_local = (
            start_time.tz_convert(
                timezone
            )
        )

        end_local = (
            end_time.tz_convert(
                timezone
            )
        )

        candidate_date = (
            start_local.date()
        )

        final_date = (
            end_local.date()
        )

        rollover_boundaries = []

        # ----------------------------------------------------
        # Check each local calendar date crossed by interval
        # ----------------------------------------------------

        while candidate_date <= final_date:

            rollover_naive = pd.Timestamp(
                year=candidate_date.year,
                month=candidate_date.month,
                day=candidate_date.day,
                hour=rollover_hour,
                minute=rollover_minute,
            )

            rollover_local = (
                rollover_naive.tz_localize(
                    timezone
                )
            )

            # ------------------------------------------------
            # Monday-Friday only
            # ------------------------------------------------

            valid_weekday = (
                rollover_local.weekday()
                <= 4
            )

            # ------------------------------------------------
            # Boundary belongs to interval when:
            #
            # start < rollover <= end
            # ------------------------------------------------

            if (
                valid_weekday
                and start_local
                < rollover_local
                <= end_local
            ):

                rollover_boundaries.append(
                    rollover_local.tz_convert(
                        start_time.tz
                    )
                )

            candidate_date = (
                pd.Timestamp(
                    candidate_date
                )
                + pd.Timedelta(days=1)
            ).date()

        return rollover_boundaries
    
    def _rollover_crossed_between(
        self,
        start_time: pd.Timestamp,
        end_time: pd.Timestamp,
    ) -> bool:
        """
        Return True when at least one applicable rollover
        boundary occurs between two timestamps.
        """

        boundaries = (
            self._get_rollover_boundaries_between(
                start_time=start_time,
                end_time=end_time,
            )
        )

        return bool(
            boundaries
        )
    
    # ========================================================
    # ROLLOVER MULTIPLIER
    # ========================================================

    def _get_rollover_multiplier(
        self,
        rollover_time: pd.Timestamp,
    ) -> float:
        """
        Return the financing multiplier for one rollover event.

        The rollover timestamp is interpreted in the configured
        rollover timezone.

        Normal rollover:
            1.0

        Configured triple-rollover weekday:
            swap_triple_multiplier

        Default FX convention:
            Wednesday = weekday 2
            multiplier = 3.0
        """

        rollover_time = pd.Timestamp(
            rollover_time
        )

        if rollover_time.tzinfo is None:
            raise ValueError(
                "rollover_time must be timezone-aware."
            )

        rollover_local = (
            rollover_time.tz_convert(
                self.execution_config
                .swap_rollover_timezone
            )
        )

        triple_weekday = (
            self.execution_config
            .swap_triple_weekday
        )

        if rollover_local.weekday() == triple_weekday:

            return float(
                self.execution_config
                .swap_triple_multiplier
            )

        return 1.0
    
    # ========================================================
    # ROLLOVER SWAP CALCULATION
    # ========================================================

    def _calculate_rollover_swap_quote(
        self,
        position: BookPosition,
        rollover_time: pd.Timestamp,
    ) -> float:
        """
        Calculate the signed swap amount for one rollover event
        in the instrument's quote currency.

        Swap rates are defined in ExecutionConfig as:

            quote-currency amount
            per base-currency unit
            per normal rollover

        Example
        -------
        GBPUSD position:

            size = 100,000 GBP
            swap_long_per_unit = -0.00007 USD

        Normal rollover:

            100,000 * -0.00007 * 1
            = -7 USD

        Wednesday triple rollover:

            100,000 * -0.00007 * 3
            = -21 USD

        This method performs calculation only.

        It does NOT:
            - modify account balance
            - modify the Position
            - record rollover counts
        """

        rollover_time = pd.Timestamp(
            rollover_time
        )

        if rollover_time.tzinfo is None:
            raise ValueError(
                "rollover_time must be timezone-aware."
            )

        if position.size <= 0.0:
            raise ValueError(
                "Position size must be positive."
            )

        # ----------------------------------------------------
        # Swap disabled
        # ----------------------------------------------------

        if not self.execution_config.include_swap:

            return 0.0

        # ----------------------------------------------------
        # Direction-specific rate
        # ----------------------------------------------------

        if position.direction == 1:

            swap_per_unit = (
                self.execution_config
                .swap_long_per_unit
            )

        elif position.direction == -1:

            swap_per_unit = (
                self.execution_config
                .swap_short_per_unit
            )

        else:

            raise ValueError(
                "Unsupported position direction: "
                f"{position.direction}"
            )

        # ----------------------------------------------------
        # Rollover multiplier
        # ----------------------------------------------------

        multiplier = (
            self._get_rollover_multiplier(
                rollover_time
            )
        )

        # ----------------------------------------------------
        # Quote-currency financing amount
        # ----------------------------------------------------

        swap_quote = (
            position.size
            * swap_per_unit
            * multiplier
        )

        return float(
            swap_quote
        )
    
    def _calculate_rollover_swap_account(
        self,
        position: BookPosition,
        rollover_time: pd.Timestamp,
        conversion_price: float,
    ) -> float:
        """
        Calculate one rollover financing adjustment in the
        account currency.

        The underlying swap rate is first calculated in the
        instrument's quote currency.

        It is then converted using the engine's existing
        quote-P&L-to-account-currency conversion logic.

        Parameters
        ----------
        position : Position
            Open position being carried through rollover.

        rollover_time : pd.Timestamp
            Time of the rollover event.

        conversion_price : float
            Instrument price used when conversion from quote
            currency to account currency is required.

            Example:

                GBPUSD quote P&L = -7 USD
                account currency = GBP
                conversion_price = 1.3500

                account swap =
                    -7 / 1.3500
                    = -5.185185 GBP

        Returns
        -------
        float
            Signed swap P&L in account currency.

        Notes
        -----
        This method performs calculation only.

        It does NOT:
            - modify account balance
            - modify Position
            - increment rollover counters
        """

        if conversion_price <= 0.0:
            raise ValueError(
                "conversion_price must be positive."
            )

        # ----------------------------------------------------
        # Calculate financing in quote currency
        # ----------------------------------------------------

        swap_quote = (
            self._calculate_rollover_swap_quote(
                position=position,
                rollover_time=rollover_time,
            )
        )

        # ----------------------------------------------------
        # Nothing to convert
        # ----------------------------------------------------

        if swap_quote == 0.0:

            return 0.0

        # ----------------------------------------------------
        # Convert using the same currency logic as trade P&L
        # ----------------------------------------------------

        swap_account = (
            self._convert_quote_pnl_to_account(
                swap_quote,
                conversion_price,
            )
        )

        return float(
            swap_account
        )
    
    # ========================================================
    # APPLY ROLLOVER TO OPEN POSITION
    # ========================================================

    def _apply_rollover_to_position(
        self,
        position: BookPosition,
        rollover_time: pd.Timestamp,
        conversion_price: float,
    ) -> float:
        """
        Apply one rollover event to an open position.

        The rollover event:

            1. determines the rollover multiplier
            2. calculates signed swap in account currency
            3. accumulates swap on the Position
            4. increments rollover counters
            5. immediately posts the swap to account balance

        Parameters
        ----------
        position : Position
            Open position crossing the rollover boundary.

        rollover_time : pd.Timestamp
            Time of the rollover event.

        conversion_price : float
            Market price used to convert quote-currency swap
            into account currency when required.

        Returns
        -------
        float
            Signed swap amount posted to account balance.

        Notes
        -----
        Swap is posted immediately to balance.

        Therefore, when the trade later closes, accumulated
        swap must NOT be added to balance a second time.

        The Trade object will still report:

            net_pnl_account =
                gross_pnl_account
                + swap_pnl_account
                + commission_pnl_account
        """

        rollover_time = pd.Timestamp(
            rollover_time
        )

        if rollover_time.tzinfo is None:
            raise ValueError(
                "rollover_time must be timezone-aware."
            )

        if conversion_price <= 0.0:
            raise ValueError(
                "conversion_price must be positive."
            )

        # ----------------------------------------------------
        # Rollover multiplier
        # ----------------------------------------------------

        multiplier = (
            self._get_rollover_multiplier(
                rollover_time
            )
        )

        # ----------------------------------------------------
        # Calculate signed swap in account currency
        # ----------------------------------------------------

        swap_account = (
            self._calculate_rollover_swap_account(
                position=position,
                rollover_time=rollover_time,
                conversion_price=conversion_price,
            )
        )

        # ----------------------------------------------------
        # Update position financing state
        # ----------------------------------------------------

        position.accrued_swap_pnl_account += (
            swap_account
        )

        position.rollover_events += 1

        position.rollover_units += (
            multiplier
        )

        # ----------------------------------------------------
        # Post financing immediately to account balance
        # ----------------------------------------------------

        self.balance += (
            swap_account
        )

        self._record_account_event(
            timestamp=rollover_time,
            event_type="swap",
            amount=swap_account,
        )

        return float(
            swap_account
        )
    
    # ========================================================
    # PROCESS ROLLOVERS BETWEEN MARKET BARS
    # ========================================================

    def _process_rollovers_between_bars(
        self,
        position: BookPosition,
        current_bar: pd.Series,
        next_timestamp: pd.Timestamp,
    ) -> None:
        """
        Process all rollover boundaries crossed between the
        current market bar and the next market timestamp.

        Rollover is only processed when:

            - a position is currently open
            - overnight positions are allowed

        The position must already have survived the current
        bar's stop / target management before this method is
        called.

        For V1, the current bar midpoint close is used as the
        currency-conversion price for rollover financing.

        If a data gap crosses multiple rollover boundaries,
        each boundary is processed independently using the
        same last-known midpoint close.

        This method mutates:

            the current active Base V1 position
            self.balance
        """


        # ----------------------------------------------------
        # Overnight-disabled behaviour will be implemented
        # separately.
        # ----------------------------------------------------

        if not (
            self.backtest_config
            .allow_overnight_positions
        ):

            return

        current_time = pd.Timestamp(
            current_bar["timestamp"]
        )

        next_timestamp = pd.Timestamp(
            next_timestamp
        )

        # ----------------------------------------------------
        # Detect rollover boundaries
        # ----------------------------------------------------

        rollover_boundaries = (
            self._get_rollover_boundaries_between(
                start_time=current_time,
                end_time=next_timestamp,
            )
        )

        if not rollover_boundaries:

            return

        # ----------------------------------------------------
        # Midpoint is appropriate here because this price is
        # used for currency conversion, not trade execution.
        # ----------------------------------------------------

        conversion_price = float(
            current_bar["mid_close"]
        )

        if conversion_price <= 0.0:

            raise ValueError(
                "mid_close must be positive when applying "
                "rollover financing."
            )

        # ----------------------------------------------------
        # Process every boundary crossed
        # ----------------------------------------------------

        for rollover_time in rollover_boundaries:
        
            self._apply_rollover_to_position(
                position=position,
                rollover_time=rollover_time,
                conversion_price=conversion_price,
            )
            
    # ========================================================
    # CLOSE POSITION BEFORE ROLLOVER
    # ========================================================

    def _process_overnight_close_between_bars(
        self,
        position: BookPosition,
        current_bar: pd.Series,
        next_timestamp: pd.Timestamp,
    ) -> Optional[Trade]:
        """
        Close an open position when overnight holding is not
        permitted and a rollover boundary occurs before the
        next market bar.

        The position is closed using the executable close price
        of the final available bar before rollover:

            long  -> bid_close
            short -> ask_close

        The trade exit timestamp is the first rollover boundary
        crossed.

        No swap is applied because the position is closed
        before it is carried through rollover.

        Returns
        -------
        Trade or None
            Completed Trade when an overnight close occurs.

            None when:
                - no position is open
                - overnight positions are allowed
                - no rollover boundary is crossed
        """


        # ----------------------------------------------------
        # This helper only handles overnight-disabled mode
        # ----------------------------------------------------

        if (
            self.backtest_config
            .allow_overnight_positions
        ):

            return None

        current_time = pd.Timestamp(
            current_bar["timestamp"]
        )

        next_timestamp = pd.Timestamp(
            next_timestamp
        )

        # ----------------------------------------------------
        # Detect rollover boundaries
        # ----------------------------------------------------

        rollover_boundaries = (
            self._get_rollover_boundaries_between(
                start_time=current_time,
                end_time=next_timestamp,
            )
        )

        if not rollover_boundaries:

            return None

        # ----------------------------------------------------
        # With overnight holding disabled, only the first
        # crossed boundary matters because the position is
        # closed there.
        # ----------------------------------------------------

        rollover_time = (
            rollover_boundaries[0]
        )


        # ----------------------------------------------------
        # Executable close side
        # ----------------------------------------------------

        if position.direction == 1:

            exit_column = "bid_close"

        elif position.direction == -1:

            exit_column = "ask_close"

        else:

            raise ValueError(
                "Unsupported position direction: "
                f"{position.direction}"
            )

        if exit_column not in current_bar.index:

            raise ValueError(
                "Required overnight-close price column "
                f"missing: {exit_column}"
            )

        exit_price = current_bar[
            exit_column
        ]

        if pd.isna(exit_price):

            raise ValueError(
                "Missing overnight-close price in "
                f"{exit_column}."
            )

        exit_price = float(
            exit_price
        )

        if exit_price <= 0.0:

            raise ValueError(
                "Overnight-close price must be positive."
            )

        # ----------------------------------------------------
        # Close before rollover.
        #
        # No financing is applied.
        # ----------------------------------------------------

        return self._close_position(
            position=position,
            exit_time=rollover_time,
            exit_price=exit_price,
            exit_reason="overnight_close",
        )
    
    # ========================================================
    # COMMISSION CALCULATION
    # ========================================================

    def _calculate_commission_account(
        self,
        position_size: float,
        execution_price: float,
    ) -> float:
        """
        Calculate commission for one transaction side in
        account currency.

        Supported models
        ----------------
        none
            No commission.

        per_lot
            Fixed cash commission per standard lot.

            Example:

                size = 100,000
                lot size = 100,000
                rate = 2.50 per lot per side

                commission = -2.50

        percentage_notional
            Percentage applied to quote-currency notional.

            Example:

                size = 100,000 GBP
                GBPUSD = 1.3500

                quote notional =
                    100,000 * 1.3500
                    = 135,000 USD

                commission_rate = 0.0002

                commission =
                    135,000 * 0.0002
                    = 27 USD

        commission_scope
        ----------------
        per_side
            Full configured rate is charged on entry and again
            on exit.

        round_trip
            Half the configured rate is charged on entry and
            half on exit.

        Returns
        -------
        float
            Signed commission P&L in account currency.

            A commission cost is returned as a negative value.

        Notes
        -----
        This method performs calculation only.

        It does NOT:
            - modify account balance
            - require or modify a Position object
        """

        if execution_price <= 0.0:

            raise ValueError(
                "execution_price must be positive."
            )

        if position_size <= 0.0:

            raise ValueError(
                "Position size must be positive."
            )

        # ----------------------------------------------------
        # Commission disabled
        # ----------------------------------------------------

        if not self.execution_config.include_commission:

            return 0.0

        model = (
            self.execution_config
            .commission_model
        )

        scope = (
            self.execution_config
            .commission_scope
        )

        rate = float(
            self.execution_config
            .commission_rate
        )

        if rate < 0.0:

            raise ValueError(
                "commission_rate cannot be negative."
            )

        # ----------------------------------------------------
        # Determine one-side rate
        # ----------------------------------------------------

        if scope == "per_side":

            side_rate = rate

        elif scope == "round_trip":

            side_rate = (
                rate / 2.0
            )

        else:

            raise ValueError(
                "Unsupported commission_scope: "
                f"{scope}"
            )

        # ----------------------------------------------------
        # No commission model
        # ----------------------------------------------------

        if model == "none":

            return 0.0

        # ----------------------------------------------------
        # Fixed cash fee per standard lot
        #
        # V1 convention:
        # per-lot commission is denominated directly in the
        # account currency.
        # ----------------------------------------------------

        if model == "per_lot":

            lot_size = float(
                self.execution_config
                .commission_lot_size
            )

            if lot_size <= 0.0:

                raise ValueError(
                    "commission_lot_size must be positive."
                )

            lots = (
                position_size
                / lot_size
            )

            commission_account = (
                lots
                * side_rate
            )

            return float(
                -commission_account
            )

        # ----------------------------------------------------
        # Percentage of quote-currency notional
        # ----------------------------------------------------

        if model == "percentage_notional":

            notional_quote = (
                position_size
                * execution_price
            )

            commission_quote = (
                notional_quote
                * side_rate
            )

            commission_account = (
                self._convert_quote_pnl_to_account(
                    -commission_quote,
                    execution_price,
                )
            )

            return float(
                commission_account
            )

        raise ValueError(
            "Unsupported commission_model: "
            f"{model}"
        )    

    def _post_commission_to_account(
        self,
        commission_account: float,
        side: str,
        event_time: pd.Timestamp,
    ) -> None:
        """
        Post an already-calculated transaction-side
        commission to account balance and account events.

        This method does not calculate commission and does
        not modify a Position object.
        """

        if side not in (
            "entry",
            "exit",
        ):

            raise ValueError(
                "Commission side must be "
                "'entry' or 'exit'."
            )

        event_time = pd.Timestamp(
            event_time
        )

        if event_time.tzinfo is None:

            raise ValueError(
                "Commission event_time must be "
                "timezone-aware."
            )

        commission_account = float(
            commission_account
        )

        # ----------------------------------------------------
        # Post immediately to account balance
        # ----------------------------------------------------

        self.balance += (
            commission_account
        )

        self._record_account_event(
            timestamp=event_time,
            event_type=(
                "entry_commission"
                if side == "entry"
                else "exit_commission"
            ),
            amount=commission_account,
        )
    
    # ========================================================
    # APPLY COMMISSION TO POSITION
    # ========================================================

    def _apply_commission_to_position(
        self,
        position: BookPosition,
        execution_price: float,
        side: str,
        event_time: pd.Timestamp,
    ) -> float:
        """
        Apply one transaction-side commission to an open
        position and post it immediately to account balance.

        Parameters
        ----------
        position : Position
            Position being charged.

        execution_price : float
            Executable entry or exit price.

        side : str
            Transaction side being charged:

                "entry"
                "exit"

        Returns
        -------
        float
            Signed commission P&L posted to account balance.

            Commission costs are negative.

        Notes
        -----
        Commission is posted immediately to balance.

        Therefore it must NOT be posted to balance again when
        the completed trade is recorded.
        """

        if side not in (
            "entry",
            "exit",
        ):

            raise ValueError(
                "Commission side must be "
                "'entry' or 'exit'."
            )

        if execution_price <= 0.0:

            raise ValueError(
                "execution_price must be positive."
            )
            
        
        event_time = pd.Timestamp(
            event_time
        )

        if event_time.tzinfo is None:

            raise ValueError(
                "Commission event_time must be "
                "timezone-aware."
            )

        # ----------------------------------------------------
        # Calculate commission
        # ----------------------------------------------------

        commission_account = (
            self._calculate_commission_account(
                position_size=(
                    position.size
                ),
                execution_price=(
                    execution_price
                ),
            )
        )        

        # ----------------------------------------------------
        # Accumulate on position
        # ----------------------------------------------------

        position.accrued_commission_pnl_account += (
            commission_account
        )

        if side == "entry":

            position.entry_commission_pnl_account += (
                commission_account
            )

        else:

            position.exit_commission_pnl_account += (
                commission_account
            )

        # ----------------------------------------------------
        # Post immediately to account balance
        # ----------------------------------------------------

        self._post_commission_to_account(
            commission_account=(
                commission_account
            ),
            side=(
                side
            ),
            event_time=(
                event_time
            ),
        )         
    
    # ========================================================
    # UNREALISED P&L
    # ========================================================

    def _calculate_unrealised_pnl_account(
        self,
        position: BookPosition,
        bar: pd.Series,
    ) -> float:
        """
        Calculate current unrealised P&L in account currency.

        Long positions are marked using bid_close.

        Short positions are marked using ask_close.

        If no position is open, unrealised P&L is zero.
        """


        if position.direction == 1:
            price_column = "bid_close"

        elif position.direction == -1:
            price_column = "ask_close"

        else:
            raise ValueError(
                f"Invalid position direction: "
                f"{position.direction}"
            )

        if price_column not in bar.index:
            raise ValueError(
                f"Required mark-to-market column missing: "
                f"{price_column}"
            )

        mark_price = bar[price_column]

        if pd.isna(mark_price):
            raise ValueError(
                f"Missing mark-to-market price: "
                f"{price_column}"
            )

        mark_price = float(mark_price)

        pnl_quote = (
            position.direction
            * (mark_price - position.entry_price)
            * position.size
        )

        pnl_account = (
            self._convert_quote_pnl_to_account(
                pnl_quote=pnl_quote,
                conversion_price=mark_price,
            )
        )

        return float(pnl_account)

    # ============================================================
    # INTRABAR WORST EQUITY
    # ============================================================
    
    def _calculate_intrabar_worst_equity(
        self,
        position: BookPosition,
        bar: pd.Series,
    ) -> float:
        """
        Calculate conservative minimum equity for the current bar.
    
        When flat:
    
            worst equity = current balance
    
        When long:
    
            adverse executable price = BID low
    
        When short:
    
            adverse executable price = ASK high
    
        If an active stop is touched, adverse movement is capped
        at the simulated stop execution price because NEXUS exits
        the position there under the current execution model.
    
        A hypothetical exit commission is included when the
        resolved bar event closes at a stop or same-bar
        breakeven stop.
    
        Target bars use the adverse executable extreme because,
        provided the stop was not touched, that adverse movement
        could have occurred before the target within the OHLC bar.
    
        Notes
        -----
        This method does not mutate:
    
            balance
            position
            trades
            commission state
            equity history
        """
    
            
        # --------------------------------------------------------
        # Detect resolved bar event using existing engine rules
        # --------------------------------------------------------
    
        events = (
            self._get_position_bar_events(
                position=position,
                bar=bar,
            )
        )
    
        event = (
            self._resolve_position_bar_event(
                events=events
            )
        )
    
        # --------------------------------------------------------
        # Select adverse executable market price
        # --------------------------------------------------------
    
        if position.direction == 1:
    
            if "bid_low" not in bar.index:
    
                raise ValueError(
                    "Required intrabar risk column missing: "
                    "bid_low"
                )
    
            adverse_price = float(
                bar["bid_low"]
            )
    
        elif position.direction == -1:
    
            if "ask_high" not in bar.index:
    
                raise ValueError(
                    "Required intrabar risk column missing: "
                    "ask_high"
                )
    
            adverse_price = float(
                bar["ask_high"]
            )
    
        else:
    
            raise ValueError(
                "Position direction must be 1 or -1."
            )
    
        if adverse_price <= 0.0:
    
            raise ValueError(
                "Intrabar adverse price must be positive."
            )
    
        # --------------------------------------------------------
        # Exit commission is only included where the simulated
        # adverse event itself closes the position.
        # --------------------------------------------------------
    
        hypothetical_exit_commission = 0.0
    
        # ========================================================
        # STOP EVENT
        # ========================================================
    
        if event == "stop":
    
            if position.stop_price is None:
    
                raise ValueError(
                    "Stop event detected without stop_price."
                )
    
            adverse_price = float(
                position.stop_price
            )
    
            hypothetical_exit_commission = (
                self._calculate_commission_account(
                    position_size=position.size,
                    execution_price=adverse_price,
                )
            )
    
        # ========================================================
        # BREAKEVEN TRIGGER
        # ========================================================
    
        elif event == "breakeven_trigger":
    
            # ----------------------------------------------------
            # Determine whether the existing NEXUS same-bar
            # breakeven policy would close at entry.
            # ----------------------------------------------------
    
            if position.direction == 1:
    
                breakeven_stop_touched = (
                    float(
                        bar["bid_low"]
                    )
                    <= position.entry_price
                )
    
            else:
    
                breakeven_stop_touched = (
                    float(
                        bar["ask_high"]
                    )
                    >= position.entry_price
                )
    
            if breakeven_stop_touched:
    
                adverse_price = float(
                    position.entry_price
                )
    
                hypothetical_exit_commission = (
                    self._calculate_commission_account(
                        position_size=position.size,
                        execution_price=adverse_price,
                    )
                )
    
        # --------------------------------------------------------
        # For:
        #
        #     event is None
        #     event == "target"
        #
        # retain the full adverse executable bar extreme.
        # --------------------------------------------------------
    
        # --------------------------------------------------------
        # Unrealised / hypothetical gross P&L
        # --------------------------------------------------------
    
        pnl_quote = (
            position.direction
            * (
                adverse_price
                - position.entry_price
            )
            * position.size
        )
    
        pnl_account = (
            self._convert_quote_pnl_to_account(
                pnl_quote=pnl_quote,
                conversion_price=adverse_price,
            )
        )
    
        intrabar_min_equity = (
            self.balance
            + pnl_account
            + hypothetical_exit_commission
        )
    
        return float(
            intrabar_min_equity
        )
    
    # ============================================================
    # RISK HISTORY
    # ============================================================
    
    def _record_risk_point(
        self,
        bar: pd.Series,
        intrabar_min_equity: float,
    ) -> None:
        """
        Record one intrabar account-risk observation.
    
        The normal EquityPoint for this bar must already have been
        recorded before this method is called.
        """
    
        if not self.equity_history:
    
            raise ValueError(
                "Cannot record RiskPoint before EquityPoint."
            )
    
        timestamp = pd.Timestamp(
            bar["timestamp"]
        )
    
        if timestamp.tzinfo is None:
    
            raise ValueError(
                "RiskPoint timestamp must be timezone-aware."
            )
    
        bar_close_equity = float(
            self.equity_history[
                -1
            ].equity
        )
    
        # --------------------------------------------------------
        # The post-management account state can itself be lower,
        # for example because an exit commission has just been
        # posted.
        # --------------------------------------------------------
    
        final_min_equity = min(
            float(
                intrabar_min_equity
            ),
            bar_close_equity,
        )
    
        risk_point = RiskPoint(
            timestamp=timestamp,
    
            balance=float(
                self.balance
            ),
    
            intrabar_min_equity=float(
                final_min_equity
            ),
    
            bar_close_equity=(
                bar_close_equity
            ),
        )
    
        self.risk_history.append(
            risk_point
        )

    # ========================================================
    # EQUITY HISTORY
    # ========================================================

    def _record_equity_point(
        self,
        bar: pd.Series,
    ) -> None:
        """
        Record balance and mark-to-market equity for one bar.

        Equity is:

            balance + unrealised P&L

        When no position is open:

            equity = balance
        """

        if "timestamp" not in bar.index:
            raise ValueError(
                "Required timestamp column is missing."
            )

        timestamp = bar["timestamp"]

        if pd.isna(timestamp):
            raise ValueError(
                "Cannot record equity with a missing timestamp."
            )

        active_positions = (
            self.position_book.active_positions()
        )
        
        # -----------------------------------------------------
        # Current engine mode still permits at most one active
        # position.
        #
        # The summation structure prepares equity calculation
        # for genuine multi-position support later.
        # -----------------------------------------------------
        
        if (
            len(
                active_positions
            )
            > 1
        ):
        
            raise RuntimeError(
                "Current engine mode permits at most one "
                "active position."
            )
        
        unrealised_pnl_account = 0.0
        
        for position in active_positions:
        
            unrealised_pnl_account += (
                self._calculate_unrealised_pnl_account(
                    position=position,
                    bar=bar,
                )
            )

        self.equity = (
            self.balance
            + unrealised_pnl_account
        )

        equity_point = EquityPoint(
            timestamp=timestamp,
            balance=float(self.balance),
            equity=float(self.equity),
            unrealised_pnl_account=float(
                unrealised_pnl_account
            ),
        )

        self.equity_history.append(
            equity_point
        )    
    
    def _close_position(
        self,
        position: BookPosition,
        exit_time: pd.Timestamp,
        exit_price: float,
        exit_reason: str,
    ) -> Trade:
        """
        Close the current position and record the completed trade.

        Parameters
        ----------
        exit_time : pd.Timestamp
            Timestamp at which the position is closed.

        exit_price : float
            Executable market price at which the position is
            closed.

        exit_reason : str
            Reason for closing the position.

            Examples:

                "stop"
                "target"
                "breakeven_stop"
                "end_of_test"

        Returns
        -------
        Trade
            Completed trade record.

        Notes
        -----
        Gross P&L is calculated in the instrument's quote
        currency.

        For example:

            GBPUSD -> USD P&L
            USDJPY -> JPY P&L

        Account-currency conversion and trading costs are
        intentionally handled separately.
        """

        if pd.isna(exit_time):
            raise ValueError(
                "Exit time cannot be missing."
            )

        if exit_price <= 0:
            raise ValueError(
                f"Invalid exit price: {exit_price}"
            )

        if not exit_reason:
            raise ValueError(
                "Exit reason cannot be empty."
            )


        # -----------------------------------------------------
        # Gross P&L in quote currency
        # -----------------------------------------------------

        gross_pnl_quote = (
            position.direction
            * (exit_price - position.entry_price)
            * position.size
        )
        
        gross_pnl_account = (
            self._convert_quote_pnl_to_account(
                pnl_quote=gross_pnl_quote,
                conversion_price=exit_price,
            )
        )

        # -----------------------------------------------------
        # Apply exit-side commission immediately
        # -----------------------------------------------------

        self._apply_commission_to_position(
            position=position,
            execution_price=exit_price,
            side="exit",
            event_time=exit_time,
        )

        # -----------------------------------------------------
        # Excursion statistics
        # -----------------------------------------------------

        mae_r = (
            position.mae_price_distance
            / position.initial_risk_distance
        )

        mfe_r = (
            position.mfe_price_distance
            / position.initial_risk_distance
        )

        # -----------------------------------------------------
        # Trading costs
        # -----------------------------------------------------
        #
        # Swap and commission calculation will be added later.
        # For now they are explicitly recorded as zero rather
        # than being hidden inside gross P&L.
        # -----------------------------------------------------

        swap_pnl_account = (position.accrued_swap_pnl_account)
        commission_pnl_account = (
            position.accrued_commission_pnl_account
        )        


        net_pnl_account = (
            gross_pnl_account
            + swap_pnl_account
            + commission_pnl_account
        )

        # -----------------------------------------------------
        # Create completed trade record
        # -----------------------------------------------------

        trade = Trade(
            signal_time=position.signal_time,
            entry_time=position.entry_time,
            exit_time=exit_time,
            direction=position.direction,
            size=position.size,
            entry_price=position.entry_price,
            exit_price=float(exit_price),
            initial_stop_price=position.initial_stop_price,
            target_price=position.target_price,
            initial_risk_distance=(position.initial_risk_distance),
            mae_price_distance=(position.mae_price_distance),
            mfe_price_distance=(position.mfe_price_distance),
            mae_r=float(mae_r),
            mfe_r=float(mfe_r),
            exit_reason=exit_reason,
            gross_pnl_quote=float(gross_pnl_quote),
            gross_pnl_account=float(gross_pnl_account),
            swap_pnl_account=float(swap_pnl_account),
            rollover_events=(position.rollover_events),
            rollover_units=float(position.rollover_units),
            commission_pnl_account=float(commission_pnl_account),
            net_pnl_account=float(net_pnl_account),
        )

        # -----------------------------------------------------
        # Store trade and clear open position
        # -----------------------------------------------------

        self.trades.append(trade)

        # Swap has already been posted to balance at each
        # rollover event, so it must not be posted again here.
        
        # -----------------------------------------------------
        # Realise gross trade P&L
        #
        # Swap and commission have already been posted to
        # balance when they occurred, so they must NOT be
        # posted again here.
        # -----------------------------------------------------

        close_balance_change = (
            gross_pnl_account
        )

        self.balance += (
            close_balance_change
        )
        
        self._record_account_event(
            timestamp=exit_time,
            event_type="realised_pnl",
            amount=gross_pnl_account,
        )
        
        self.equity = self.balance

        # -----------------------------------------------------
        # Record the completed close in PositionBook.
        # -----------------------------------------------------

        self._record_position_close(
            position=position,
            exit_time=exit_time,
            exit_price=exit_price,
            exit_reason=exit_reason,
        )

        return trade
    
    def _manage_open_position_on_bar(
        self,
        position: BookPosition,
        bar: pd.Series,
    ) -> Optional[Trade]:
        """
        Manage the current open position using one historical
        market-data bar.

        Parameters
        ----------
        bar : pd.Series
            Historical bar currently being processed.

        Returns
        -------
        Trade or None
            Completed Trade if the position is closed.

            None if the position remains open.

        Notes
        -----
        Event detection and same-bar ordering are handled by
        dedicated helper methods.

        NEXUS V1 assumes stop and target orders are filled at
        their configured price level once that level is touched.

        Gap-aware stop execution can be added later.
        """


        if "timestamp" not in bar.index:
            raise ValueError(
                "Required timestamp column is missing."
            )

        bar_time = bar["timestamp"]

        if pd.isna(bar_time):
            raise ValueError(
                "Position-management bar contains a missing "
                "timestamp."
            )

        # -----------------------------------------------------
        # Detect events
        # -----------------------------------------------------

        events = self._get_position_bar_events(
            position=position,
            bar=bar,
        )

        event = self._resolve_position_bar_event(
            events=events
        )

        # -----------------------------------------------------
        # Nothing happened
        # -----------------------------------------------------

        if event is None:

            self._update_position_excursions(
                position=position,
                bar=bar,
                event=None,
            )

            return None

        # -----------------------------------------------------
        # Stop
        # -----------------------------------------------------

        if event == "stop":

            exit_price = position.stop_price

            if exit_price is None:
                raise ValueError(
                    "Stop event detected but position has "
                    "no active stop price."
                )

            if position.breakeven_applied:
                exit_reason = "breakeven_stop"
            else:
                exit_reason = "stop"
                
            self._update_position_excursions(
                position=position,
                bar=bar,
                event="stop",
            )

            return self._close_position(
                position=position,
                exit_time=bar_time,
                exit_price=exit_price,
                exit_reason=exit_reason,
            )

        # -----------------------------------------------------
        # Target
        # -----------------------------------------------------

        if event == "target":

            exit_price = position.target_price

            if exit_price is None:
                raise ValueError(
                    "Target event detected but position has "
                    "no target price."
                )

            self._update_position_excursions(
                position=position,
                bar=bar,
                event="target",
            )

            return self._close_position(
                position=position,
                exit_time=bar_time,
                exit_price=exit_price,
                exit_reason="target",
            )

        # -----------------------------------------------------
        # Breakeven trigger
        # -----------------------------------------------------

        if event == "breakeven_trigger":


            # -------------------------------------------------
            # Same-bar BE ambiguity
            # -------------------------------------------------
            #
            # If the same bar reaches the BE trigger and also
            # trades back through the entry price, OHLC data
            # cannot reveal which happened first.
            #
            # Under the conservative V1 policy, assume the BE
            # trigger occurred first and the subsequent
            # retracement stopped the trade at breakeven.
            # -------------------------------------------------

            if position.direction == 1:

                if "bid_low" not in bar.index:
                    raise ValueError(
                        "Required execution price column "
                        "missing: bid_low"
                    )

                breakeven_stop_touched = (
                    float(bar["bid_low"])
                    <= position.entry_price
                )

            else:

                if "ask_high" not in bar.index:
                    raise ValueError(
                        "Required execution price column "
                        "missing: ask_high"
                    )

                breakeven_stop_touched = (
                    float(bar["ask_high"])
                    >= position.entry_price
                )

            if breakeven_stop_touched:

                self._update_position_excursions(
                    position=position,
                    bar=bar,
                    event="breakeven_stop",
                )

                self._apply_breakeven(
                    position=position,
                )

                return self._close_position(
                    position=position,
                    exit_time=bar_time,
                    exit_price=position.entry_price,
                    exit_reason="breakeven_stop",
                )

            # -------------------------------------------------
            # BE triggered but trade survives this bar
            # -------------------------------------------------

            self._update_position_excursions(
                position=position,
                bar=bar,
                event=None,
            )

            self._apply_breakeven(
                position=position
            )

            return None

        raise ValueError(
            f"Unsupported resolved position event: {event}"
        )
        
    # ========================================================
    # OPTIONAL STRATEGY INSTRUCTIONS
    # ========================================================

    def _get_optional_instruction(
        self,
        row: pd.Series,
        column: str,
    ) -> Optional[float]:
        """
        Read an optional numeric strategy instruction from a row.

        Missing columns and NaN values are treated as None.
        """

        if column not in row.index:
            return None

        value = row[column]

        if pd.isna(value):
            return None

        return float(value)
    
    
    # ========================================================
    # MAIN BACKTEST LOOP
    # ========================================================

    def run(
        self,
        df: pd.DataFrame,
    ) -> BacktestResult:
        """
        Run the NEXUS historical execution engine.

        Parameters
        ----------
        df : pd.DataFrame
            Prepared historical market data containing strategy
            signals and optional trade instructions.

        Returns
        -------
        BacktestResult
            Structured result of the completed simulation.

        Notes
        -----
        Required strategy output:

            entry_signal

        Optional trade instructions:

            stop_price
            stop_distance

            target_price
            target_distance

            breakeven_trigger_price
            breakeven_trigger_distance

        A signal generated on bar i is executed at the
        executable opening price of bar i + 1.
        """

        # -----------------------------------------------------
        # Reset engine state
        # -----------------------------------------------------

        self.reset()

        # -----------------------------------------------------
        # Basic validation
        # -----------------------------------------------------

        if len(df) == 0:
            raise ValueError(
                "Cannot run NEXUS engine on an empty dataframe."
            )

        if "timestamp" not in df.columns:
            raise ValueError(
                "Required column missing: timestamp"
            )

        if "entry_signal" not in df.columns:
            raise ValueError(
                "Required column missing: entry_signal"
            )

        
        # -----------------------------------------------------
        # Process historical bars
        # -----------------------------------------------------

        for i in range(len(df)):

            bar = df.iloc[i]

            # -------------------------------------------------
            # Calculate intrabar risk before current-bar
            # management potentially closes the position.
            # -------------------------------------------------

            intrabar_min_equity = float(
                self.balance
            )
            
            active_positions = (
                self.position_book.active_positions()
            )
            
            # -------------------------------------------------
            # Current engine mode still permits at most one
            # active position.
            #
            # The loop structure is introduced now so position
            # management can later support multiple positions
            # without changing today's trading behaviour.
            # -------------------------------------------------
            
            if (
                len(
                    active_positions
                )
                > 1
            ):
            
                raise RuntimeError(
                    "Current engine mode permits at most one "
                    "active position."
                )
            
            for position in list(
                active_positions
            ):
            
                intrabar_min_equity = (
                    self._calculate_intrabar_worst_equity(
                        position=position,
                        bar=bar,
                    )
                )
            
                self._manage_open_position_on_bar(
                    position=position,
                    bar=bar,
                )


            # -------------------------------------------------
            # Record CURRENT BAR account state.
            #
            # Important:
            # This happens before rollover / overnight events
            # occurring between this bar and the next bar.
            # -------------------------------------------------

            self._record_equity_point(
                bar=bar
            )

            self._record_risk_point(
                bar=bar,
                intrabar_min_equity=(
                    intrabar_min_equity
                ),
            )


            # -------------------------------------------------
            # If the position survived the current bar,
            # process the interval between this bar and the
            # next market bar.
            # -------------------------------------------------

            if (
                self._has_open_position()
                and i < len(df) - 1
            ):
            
                next_timestamp = pd.Timestamp(
                    df.iloc[i + 1][
                        "timestamp"
                    ]
                )
            
                between_bar_positions = (
                    self.position_book.active_positions()
                )
            
                # -------------------------------------------------
                # Current engine mode still permits at most one
                # active position.
                #
                # The loop structure prepares this section for
                # genuine multi-position processing later.
                # -------------------------------------------------
            
                if (
                    len(
                        between_bar_positions
                    )
                    > 1
                ):
            
                    raise RuntimeError(
                        "Current engine mode permits at most one "
                        "active position."
                    )
            
                for position in list(
                    between_bar_positions
                ):
            
                    if (
                        self.backtest_config
                        .allow_overnight_positions
                    ):
            
                        self._process_rollovers_between_bars(
                            position=position,
                            current_bar=bar,
                            next_timestamp=next_timestamp,
                        )
            
                    else:
            
                        self._process_overnight_close_between_bars(
                            position=position,
                            current_bar=bar,
                            next_timestamp=next_timestamp,
                        )


            # -------------------------------------------------
            # Read strategy signal
            # -------------------------------------------------  

            signal = bar["entry_signal"]

            if pd.isna(signal):
                signal = 0

            signal = int(signal)

            if signal not in (-1, 0, 1):
                raise ValueError(
                    f"Invalid entry_signal at row {i}: "
                    f"{signal}"
                )

            # -------------------------------------------------
            # Open new position
            # -------------------------------------------------
            
            if (
                not self._has_open_position()
                and signal in (1, -1)
                and i < len(df) - 1
            ):

                # ---------------------------------------------
                # Resolve the actual candidate execution time.
                #
                # With entry_timing="next_open", this will be
                # the timestamp of bar i + 1 rather than the
                # current signal-bar timestamp.
                # ---------------------------------------------

                (
                    candidate_entry_time,
                    _candidate_entry_price,
                ) = self._get_entry_execution(
                    df=df,
                    signal_index=i,
                    direction=signal,
                )

                # ---------------------------------------------
                # Apply generic entry-eligibility rules.
                # ---------------------------------------------

                eligibility = (
                    evaluate_entry_eligibility(
                        timestamp=(
                            candidate_entry_time
                        ),
                        config=(
                            self.trading_window_config
                        ),
                    )
                )

                # ---------------------------------------------
                # Open only if the ACTUAL candidate entry time
                # is permitted.
                # ---------------------------------------------

                if eligibility.allowed:

                    self._open_position(
                        df=df,
                        signal_index=i,
                        direction=signal,

                        stop_price=(
                            self._get_optional_instruction(
                                row=bar,
                                column="stop_price",
                            )
                        ),

                        stop_distance=(
                            self._get_optional_instruction(
                                row=bar,
                                column="stop_distance",
                            )
                        ),

                        target_price=(
                            self._get_optional_instruction(
                                row=bar,
                                column="target_price",
                            )
                        ),

                        target_distance=(
                            self._get_optional_instruction(
                                row=bar,
                                column="target_distance",
                            )
                        ),

                        breakeven_trigger_price=(
                            self._get_optional_instruction(
                                row=bar,
                                column=(
                                    "breakeven_trigger_price"
                                ),
                            )
                        ),

                        breakeven_trigger_distance=(
                            self._get_optional_instruction(
                                row=bar,
                                column=(
                                    "breakeven_trigger_distance"
                                ),
                            )
                        ),
                    )            

        # -----------------------------------------------------
        # Force-close final open position
        # -----------------------------------------------------

        if (
            self._has_open_position()
            and self.backtest_config.force_close_at_end
        ):
        
            final_bar = df.iloc[-1]
        
            final_positions = (
                self.position_book.active_positions()
            )
        
            # -------------------------------------------------
            # Current engine mode still permits at most one
            # active position.
            #
            # The loop structure prepares final liquidation for
            # genuine multi-position support later.
            # -------------------------------------------------
        
            if (
                len(
                    final_positions
                )
                > 1
            ):
        
                raise RuntimeError(
                    "Current engine mode permits at most one "
                    "active position."
                )
        
            for position in list(
                final_positions
            ):
        
                if position.direction == 1:
                    exit_column = "bid_close"
        
                elif position.direction == -1:
                    exit_column = "ask_close"
        
                else:
                    raise ValueError(
                        "Position direction must be 1 or -1."
                    )
        
                if exit_column not in final_bar.index:
                    raise ValueError(
                        f"Required final exit column missing: "
                        f"{exit_column}"
                    )
        
                exit_price = final_bar[
                    exit_column
                ]
        
                if pd.isna(
                    exit_price
                ):
                    raise ValueError(
                        f"Missing final exit price: "
                        f"{exit_column}"
                    )
        
                self._close_position(
                    position=position,
                    exit_time=final_bar["timestamp"],
                    exit_price=float(
                        exit_price
                    ),
                    exit_reason="end_of_test",
                )

            self._close_position(
                position=position,
                exit_time=final_bar["timestamp"],
                exit_price=float(exit_price),
                exit_reason="end_of_test",
            )

        # -----------------------------------------------------
        # Return result
        # -----------------------------------------------------

        return BacktestResult(
            starting_balance=(
                self.account_config.starting_balance
            ),
            ending_balance=self.balance,
            ending_equity=self.equity,
            trades=list(self.trades),
            equity_curve=list(self.equity_history),
            risk_curve=list(self.risk_history),
            account_events=list(self.account_events),            
            open_position=self._get_optional_active_position(),
            rows_processed=len(df),
        )