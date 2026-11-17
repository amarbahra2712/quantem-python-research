# -*- coding: utf-8 -*-
"""
Created on Tue Sep 22 10:51:39 2026

@author: quant
"""

"""
NEXUS Position Models
=====================

Purpose
-------
Define the canonical live Position object for the future
multi-position NEXUS architecture.

Responsibilities
----------------
- Represent one independently managed live position.
- Retain deterministic position identity.
- Retain the source entry-order relationship.
- Store current open quantity.
- Store executable entry and risk-management prices.
- Store excursion, financing, and commission state.
- Preserve future basket / role relationships.

Does Not
--------
- Store collections of positions.
- Generate orders or fills.
- Execute entries or exits.
- Calculate whether stops or targets have been hit.
- Calculate account-level P&L.
- Contain strategy logic.

Architecture
------------
The intended lifecycle is:

    Order
      ↓
    Fill(s)
      ↓
    Position
      ↓
    partial / full exits
      ↓
    closed trade records

One entry Order may eventually receive several Fill objects.
Those fills can contribute to one Position.

The current Base V1 Position inside nexus_engine.py remains
untouched while this new model is developed and tested
independently.
"""


from dataclasses import dataclass

import math

from numbers import Real

from typing import Optional

import pandas as pd


# ============================================================
# MODEL CONTRACTS
# ============================================================

VALID_DIRECTIONS = (
    1,
    -1,
)


# ============================================================
# POSITION
# ============================================================

@dataclass
class Position:
    """
    Represents one independently managed position.

    A position may remain stored after full closure with:

    open_size = 0

    initial_size
        Total quantity originally opened into the position.

    open_size
        Quantity that remains live.

        This distinction is required for future partial closes.

    entry_price
        Executable weighted-average entry price of the live
        position.

    Price levels are stored as absolute executable prices.
    """

    # --------------------------------------------------------
    # Identity
    # --------------------------------------------------------

    position_id: str

    source_order_id: str

    # --------------------------------------------------------
    # Timing
    # --------------------------------------------------------

    signal_time: pd.Timestamp

    entry_time: pd.Timestamp

    # --------------------------------------------------------
    # Exposure
    # --------------------------------------------------------

    direction: int

    initial_size: float

    open_size: float

    entry_price: float

    # --------------------------------------------------------
    # Relationship metadata
    # --------------------------------------------------------

    basket_id: Optional[str] = None

    role: Optional[str] = None

    # --------------------------------------------------------
    # Risk-management prices
    # --------------------------------------------------------

    initial_stop_price: Optional[float] = None

    stop_price: Optional[float] = None

    target_price: Optional[float] = None

    breakeven_trigger_price: Optional[float] = None

    breakeven_applied: bool = False

    # --------------------------------------------------------
    # Original trade risk
    # --------------------------------------------------------

    initial_risk_distance: float = 0.0

    # --------------------------------------------------------
    # Excursion tracking
    # --------------------------------------------------------

    mae_price_distance: float = 0.0

    mfe_price_distance: float = 0.0

    # --------------------------------------------------------
    # Rollover / financing state
    # --------------------------------------------------------

    accrued_swap_pnl_account: float = 0.0

    rollover_events: int = 0

    rollover_units: float = 0.0

    # --------------------------------------------------------
    # Commission state
    # --------------------------------------------------------

    accrued_commission_pnl_account: float = 0.0

    entry_commission_pnl_account: float = 0.0

    exit_commission_pnl_account: float = 0.0


    # ========================================================
    # COMPATIBILITY SIZE VIEW
    # ========================================================

    @property
    def size(
        self,
    ) -> float:
        """
        Return current live position quantity.

        Compatibility bridge
        --------------------
        Base V1 engine logic historically accesses:

            position.size

        The multi-position architecture distinguishes:

            initial_size
            open_size

        During migration, size therefore represents the
        currently live quantity.

        Future partial-close-aware logic should use
        open_size explicitly.
        """

        return float(
            self.open_size
        )


    # ========================================================
    # VALIDATION
    # ========================================================

    def __post_init__(
        self,
    ):
        """
        Validate the internal consistency of the Position.
        """

        # ----------------------------------------------------
        # Identity
        # ----------------------------------------------------

        for field_name in (
            "position_id",
            "source_order_id",
        ):

            value = getattr(
                self,
                field_name,
            )

            if (
                not isinstance(
                    value,
                    str,
                )
                or not value.strip()
            ):

                raise ValueError(
                    f"{field_name} must be "
                    "a non-empty string."
                )

        # ----------------------------------------------------
        # Timestamps
        # ----------------------------------------------------

        if not isinstance(
            self.signal_time,
            pd.Timestamp,
        ):

            raise TypeError(
                "signal_time must be a pandas Timestamp."
            )

        if not isinstance(
            self.entry_time,
            pd.Timestamp,
        ):

            raise TypeError(
                "entry_time must be a pandas Timestamp."
            )

        if (
            self.signal_time.tz
            is None
        ):

            raise ValueError(
                "signal_time must be timezone-aware."
            )

        if (
            self.entry_time.tz
            is None
        ):

            raise ValueError(
                "entry_time must be timezone-aware."
            )

        if (
            self.entry_time
            < self.signal_time
        ):

            raise ValueError(
                "entry_time cannot be earlier "
                "than signal_time."
            )

        # ----------------------------------------------------
        # Direction
        # ----------------------------------------------------

        if (
            isinstance(
                self.direction,
                bool,
            )
            or self.direction
            not in VALID_DIRECTIONS
        ):

            raise ValueError(
                "direction must be 1 or -1."
            )

        
        # ----------------------------------------------------
        # Initial size
        # ----------------------------------------------------

        if (
            not isinstance(
                self.initial_size,
                Real,
            )
            or isinstance(
                self.initial_size,
                bool,
            )
            or not math.isfinite(
                float(
                    self.initial_size
                )
            )
            or self.initial_size <= 0
        ):

            raise ValueError(
                "initial_size must be "
                "a positive finite number."
            )

        # ----------------------------------------------------
        # Open size
        #
        # open_size may be zero once a position has been
        # completely closed.
        # ----------------------------------------------------

        if (
            not isinstance(
                self.open_size,
                Real,
            )
            or isinstance(
                self.open_size,
                bool,
            )
            or not math.isfinite(
                float(
                    self.open_size
                )
            )
            or self.open_size < 0
        ):

            raise ValueError(
                "open_size must be "
                "a non-negative finite number."
            )

        if (
            self.open_size
            > self.initial_size
        ):

            raise ValueError(
                "open_size cannot exceed "
                "initial_size."
            )        

        if (
            self.open_size
            > self.initial_size
        ):

            raise ValueError(
                "open_size cannot exceed "
                "initial_size."
            )

        # ----------------------------------------------------
        # Entry price
        # ----------------------------------------------------

        if (
            not isinstance(
                self.entry_price,
                Real,
            )
            or isinstance(
                self.entry_price,
                bool,
            )
            or not math.isfinite(
                float(
                    self.entry_price
                )
            )
            or self.entry_price <= 0
        ):

            raise ValueError(
                "entry_price must be a positive "
                "finite number."
            )

        # ----------------------------------------------------
        # Optional executable price levels
        # ----------------------------------------------------

        for field_name in (
            "initial_stop_price",
            "stop_price",
            "target_price",
            "breakeven_trigger_price",
        ):

            value = getattr(
                self,
                field_name,
            )

            if value is None:

                continue

            if (
                not isinstance(
                    value,
                    Real,
                )
                or isinstance(
                    value,
                    bool,
                )
                or not math.isfinite(
                    float(
                        value
                    )
                )
                or value <= 0
            ):

                raise ValueError(
                    f"{field_name} must be None "
                    "or a positive finite number."
                )

        # ----------------------------------------------------
        # Non-negative state values
        # ----------------------------------------------------

        for field_name in (
            "initial_risk_distance",
            "mae_price_distance",
            "mfe_price_distance",
            "rollover_units",
        ):

            value = getattr(
                self,
                field_name,
            )

            if (
                not isinstance(
                    value,
                    Real,
                )
                or isinstance(
                    value,
                    bool,
                )
                or not math.isfinite(
                    float(
                        value
                    )
                )
                or value < 0
            ):

                raise ValueError(
                    f"{field_name} must be "
                    "a non-negative finite number."
                )

        # ----------------------------------------------------
        # Rollover event count
        # ----------------------------------------------------

        if (
            isinstance(
                self.rollover_events,
                bool,
            )
            or not isinstance(
                self.rollover_events,
                int,
            )
            or self.rollover_events < 0
        ):

            raise ValueError(
                "rollover_events must be "
                "a non-negative integer."
            )

        # ----------------------------------------------------
        # Signed accounting values
        # ----------------------------------------------------

        for field_name in (
            "accrued_swap_pnl_account",
            "accrued_commission_pnl_account",
            "entry_commission_pnl_account",
            "exit_commission_pnl_account",
        ):

            value = getattr(
                self,
                field_name,
            )

            if (
                not isinstance(
                    value,
                    Real,
                )
                or isinstance(
                    value,
                    bool,
                )
                or not math.isfinite(
                    float(
                        value
                    )
                )
            ):

                raise ValueError(
                    f"{field_name} must be "
                    "a finite number."
                )

        # ----------------------------------------------------
        # Optional relationship metadata
        # ----------------------------------------------------

        for field_name in (
            "basket_id",
            "role",
        ):

            value = getattr(
                self,
                field_name,
            )

            if (
                value is not None
                and (
                    not isinstance(
                        value,
                        str,
                    )
                    or not value.strip()
                )
            ):

                raise ValueError(
                    f"{field_name} must be None "
                    "or a non-empty string."
                )
                
# ============================================================
# POSITION CLOSE
# ============================================================

@dataclass
class PositionClose:
    """
    Represents one reduction of an existing Position.

    A PositionClose may represent either:

        - a partial close, or
        - the final close of the remaining position.

    It is an immutable historical execution record in concept,
    while the Position itself continues to represent the
    evolving position state.

    P&L is deliberately not calculated here. Account and
    instrument-specific P&L calculation remains the
    responsibility of the execution/accounting layer.
    """

    # --------------------------------------------------------
    # Identity
    # --------------------------------------------------------

    position_close_id: str

    position_id: str

    # --------------------------------------------------------
    # Execution
    # --------------------------------------------------------

    close_time: pd.Timestamp

    size: float

    exit_price: float

    # --------------------------------------------------------
    # Reason / execution relationships
    # --------------------------------------------------------

    reason: str

    exit_order_id: Optional[str] = None

    exit_fill_id: Optional[str] = None

    # --------------------------------------------------------
    # Accounting metadata
    # --------------------------------------------------------

    commission_pnl_account: float = 0.0


    # ========================================================
    # VALIDATION
    # ========================================================

    def __post_init__(
        self,
    ):
        """
        Validate the PositionClose record.
        """

        # ----------------------------------------------------
        # Required string identifiers
        # ----------------------------------------------------

        for field_name in (
            "position_close_id",
            "position_id",
            "reason",
        ):

            value = getattr(
                self,
                field_name,
            )

            if (
                not isinstance(
                    value,
                    str,
                )
                or not value.strip()
            ):

                raise ValueError(
                    f"{field_name} must be "
                    "a non-empty string."
                )

        # ----------------------------------------------------
        # Timestamp
        # ----------------------------------------------------

        if not isinstance(
            self.close_time,
            pd.Timestamp,
        ):

            raise TypeError(
                "close_time must be a pandas Timestamp."
            )

        if (
            self.close_time.tz
            is None
        ):

            raise ValueError(
                "close_time must be timezone-aware."
            )

        # ----------------------------------------------------
        # Close size
        # ----------------------------------------------------

        if (
            not isinstance(
                self.size,
                Real,
            )
            or isinstance(
                self.size,
                bool,
            )
            or not math.isfinite(
                float(
                    self.size
                )
            )
            or self.size <= 0
        ):

            raise ValueError(
                "size must be a positive finite number."
            )

        # ----------------------------------------------------
        # Exit price
        # ----------------------------------------------------

        if (
            not isinstance(
                self.exit_price,
                Real,
            )
            or isinstance(
                self.exit_price,
                bool,
            )
            or not math.isfinite(
                float(
                    self.exit_price
                )
            )
            or self.exit_price <= 0
        ):

            raise ValueError(
                "exit_price must be a positive "
                "finite number."
            )

        # ----------------------------------------------------
        # Optional execution identifiers
        # ----------------------------------------------------

        for field_name in (
            "exit_order_id",
            "exit_fill_id",
        ):

            value = getattr(
                self,
                field_name,
            )

            if (
                value is not None
                and (
                    not isinstance(
                        value,
                        str,
                    )
                    or not value.strip()
                )
            ):

                raise ValueError(
                    f"{field_name} must be None "
                    "or a non-empty string."
                )

        # ----------------------------------------------------
        # Commission
        # ----------------------------------------------------

        if (
            not isinstance(
                self.commission_pnl_account,
                Real,
            )
            or isinstance(
                self.commission_pnl_account,
                bool,
            )
            or not math.isfinite(
                float(
                    self.commission_pnl_account
                )
            )
        ):

            raise ValueError(
                "commission_pnl_account must be "
                "a finite number."
            )