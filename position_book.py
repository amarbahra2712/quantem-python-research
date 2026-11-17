# -*- coding: utf-8 -*-
"""
Created on Tue Sep 22 10:56:25 2026

@author: quant
"""

"""
NEXUS Position Book
===================

Purpose
-------
Store and manage multiple simultaneously live Position objects
belonging to one NEXUS backtest run.

Responsibilities
----------------
- Create positions with deterministic IDs.
- Store multiple independent live positions.
- Retrieve positions by position_id.
- Return all live positions.
- Return long and short positions separately.
- Calculate long, short, gross, and net open exposure.
- Support simultaneous long and short positions.

Does Not
--------
- Generate orders or fills.
- Validate that a source Order or Fill exists.
- Execute entries or exits.
- Close or partially close positions.
- Calculate P&L.
- Evaluate stops or targets.
- Contain strategy logic.

Architecture
------------
The PositionBook represents currently live exposure.

Example:

    POS000001
        LONG
        100,000 units

    POS000002
        SHORT
        40,000 units

This is valid.

The resulting unit exposures are:

    Long exposure:      100,000
    Short exposure:      40,000
    Gross exposure:     140,000
    Net exposure:       +60,000

This explicitly supports hedging rather than automatically
netting opposing positions.

Closed-position history will be handled separately later.
"""


from typing import (
    Dict,
    List,
    Optional,
)

import pandas as pd

from id_generator import IdGenerator
from position_models import (
    Position,
    PositionClose,
)


# ============================================================
# POSITION BOOK
# ============================================================

class PositionBook:
    """
    Store and manage live positions for one NEXUS run.
    """

    def __init__(
        self,
        id_generator: IdGenerator,
    ):

        if not isinstance(
            id_generator,
            IdGenerator,
        ):

            raise TypeError(
                "id_generator must be an IdGenerator."
            )

        self.id_generator = (
            id_generator
        )

        self._positions: Dict[
            str,
            Position,
        ] = {}
        
        self._position_closes: Dict[
            str,
            PositionClose,
        ] = {} 


    # ========================================================
    # CREATE POSITION
    # ========================================================

    def create_position(
        self,
        source_order_id: str,
        signal_time: pd.Timestamp,
        entry_time: pd.Timestamp,
        direction: int,
        size: float,
        entry_price: float,
        basket_id: Optional[str] = None,
        role: Optional[str] = None,
        initial_stop_price: Optional[float] = None,
        stop_price: Optional[float] = None,
        target_price: Optional[float] = None,
        breakeven_trigger_price: Optional[float] = None,
        initial_risk_distance: float = 0.0,
        entry_commission_pnl_account: float = 0.0,
    ) -> Position:
        """
        Create and store one new live Position.

        At initial creation:

            initial_size == open_size

        Future partial-close logic will reduce open_size while
        preserving initial_size.
        """
        existing_position = (
            self.position_for_source_order(
                source_order_id
            )
        )

        if (
            existing_position
            is not None
        ):

            raise ValueError(
                "source_order_id already has "
                "a Position: "
                f"{existing_position.position_id}"
            )

        position_id = (
            self.id_generator
            .next_position_id()
        )

        position = Position(
            position_id=(
                position_id
            ),

            source_order_id=(
                source_order_id
            ),

            signal_time=(
                signal_time
            ),

            entry_time=(
                entry_time
            ),

            direction=(
                direction
            ),

            initial_size=(
                size
            ),

            open_size=(
                size
            ),

            entry_price=(
                entry_price
            ),

            basket_id=(
                basket_id
            ),

            role=(
                role
            ),

            initial_stop_price=(
                initial_stop_price
            ),

            stop_price=(
                stop_price
            ),

            target_price=(
                target_price
            ),

            breakeven_trigger_price=(
                breakeven_trigger_price
            ),

            initial_risk_distance=(
                initial_risk_distance
            ),

            entry_commission_pnl_account=(
                entry_commission_pnl_account
            ),

            accrued_commission_pnl_account=(
                entry_commission_pnl_account
            ),
        )

        self._positions[
            position_id
        ] = position

        return position


    # ========================================================
    # GET POSITION
    # ========================================================

    def get_position(
        self,
        position_id: str,
    ) -> Position:
        """
        Retrieve one live Position by ID.
        """

        if (
            position_id
            not in self._positions
        ):

            raise KeyError(
                "Unknown position_id: "
                f"{position_id}"
            )

        return (
            self._positions[
                position_id
            ]
        )

    # ========================================================
    # POSITION FOR SOURCE ORDER
    # ========================================================

    def position_for_source_order(
        self,
        source_order_id: str,
    ) -> Optional[Position]:
        """
        Return the Position created from one entry Order.

        Returns None when the Order has not yet created a
        Position.

        NEXUS currently defines one entry Order as mapping to
        at most one Position, even when that Order receives
        multiple partial fills.
        """

        for position in (
            self._positions.values()
        ):

            if (
                position.source_order_id
                == source_order_id
            ):

                return position

        return None

    # ========================================================
    # ALL POSITIONS
    # ========================================================

    def all_positions(
        self,
    ) -> List[Position]:
        """
        Return all positions ever created, including positions
        that have subsequently been fully closed.
        """

        return list(
            self._positions.values()
        )

    # ========================================================
    # ACTIVE POSITIONS
    # ========================================================

    def active_positions(
        self,
    ) -> List[Position]:
        """
        Return positions that still have live exposure.
        """

        return [
            position
            for position
            in self._positions.values()
            if position.open_size > 0
        ]

    # ========================================================
    # LONG POSITIONS
    # ========================================================

    def long_positions(
        self,
    ) -> List[Position]:
        """
        Return all currently live long positions.
        """

        return [
            position
            for position
            in self.active_positions()
            if position.direction
            == 1
        ]


    # ========================================================
    # SHORT POSITIONS
    # ========================================================

    def short_positions(
        self,
    ) -> List[Position]:
        """
        Return all currently live short positions.
        """

        return [
            position
            for position
            in self.active_positions()
            if position.direction
            == -1
        ]


    # ========================================================
    # LONG OPEN SIZE
    # ========================================================

    def long_open_size(
        self,
    ) -> float:
        """
        Return total open long quantity.
        """

        return float(
            sum(
                position.open_size
                for position
                in self.long_positions()
            )
        )


    # ========================================================
    # SHORT OPEN SIZE
    # ========================================================

    def short_open_size(
        self,
    ) -> float:
        """
        Return total open short quantity as a positive number.
        """

        return float(
            sum(
                position.open_size
                for position
                in self.short_positions()
            )
        )


    # ========================================================
    # GROSS OPEN SIZE
    # ========================================================

    def gross_open_size(
        self,
    ) -> float:
        """
        Return total absolute open quantity across both sides.
        """

        return (
            self.long_open_size()
            + self.short_open_size()
        )


    # ========================================================
    # NET OPEN SIZE
    # ========================================================

    def net_open_size(
        self,
    ) -> float:
        """
        Return signed net open quantity.

        Positive = net long.
        Negative = net short.
        Zero     = directionally flat, even if gross exposure
                   remains live.
        """

        return (
            self.long_open_size()
            - self.short_open_size()
        )


    # ========================================================
    # POSITION CLOSE HISTORY
    # ========================================================

    def all_position_closes(
        self,
    ) -> List[PositionClose]:
        """
        Return all partial and full close records in creation
        order.
        """

        return list(
            self._position_closes.values()
        )


    def closes_for_position(
        self,
        position_id: str,
    ) -> List[PositionClose]:
        """
        Return all close records belonging to one Position.
        """

        self.get_position(
            position_id
        )

        return [
            position_close
            for position_close
            in self._position_closes.values()
            if position_close.position_id
            == position_id
        ]


    # ========================================================
    # CLOSE POSITION
    # ========================================================

    def close_position(
        self,
        position_id: str,
        close_time: pd.Timestamp,
        size: float,
        exit_price: float,
        reason: str,
        commission_pnl_account: float = 0.0,
        exit_order_id: Optional[str] = None,
        exit_fill_id: Optional[str] = None,
        commission_already_applied: bool = False,
    ) -> PositionClose:
        """
        Reduce an existing Position by the requested quantity.

        The reduction may be either:

            partial close
            full close

        The Position itself remains stored permanently.

        A PositionClose record provides the immutable audit
        history of each reduction.
        """

        position = (
            self.get_position(
                position_id
            )
        )

        # ----------------------------------------------------
        # Position must still contain live exposure.
        # ----------------------------------------------------

        if (
            position.open_size
            <= 0
        ):

            raise ValueError(
                "Position is already fully closed."
            )

        # ----------------------------------------------------
        # Close cannot occur before position entry.
        # ----------------------------------------------------

        if not isinstance(
            close_time,
            pd.Timestamp,
        ):

            raise TypeError(
                "close_time must be a pandas Timestamp."
            )

        if (
            close_time.tz
            is None
        ):

            raise ValueError(
                "close_time must be timezone-aware."
            )

        if (
            close_time
            < position.entry_time
        ):

            raise ValueError(
                "close_time cannot be earlier "
                "than entry_time."
            )

        # ----------------------------------------------------
        # PositionClose performs the basic size / price /
        # commission validation.
        # ----------------------------------------------------

        position_close_id = (
            self.id_generator
            .next_position_close_id()
        )

        position_close = PositionClose(
            position_close_id=(
                position_close_id
            ),

            position_id=(
                position.position_id
            ),

            close_time=(
                close_time
            ),

            size=(
                size
            ),

            exit_price=(
                exit_price
            ),

            reason=(
                reason
            ),

            exit_order_id=(
                exit_order_id
            ),

            exit_fill_id=(
                exit_fill_id
            ),

            commission_pnl_account=(
                commission_pnl_account
            ),
        )

        # ----------------------------------------------------
        # Cannot close more than remains open.
        # ----------------------------------------------------

        if (
            position_close.size
            > position.open_size
        ):

            raise ValueError(
                "Close size exceeds current "
                "open position size."
            )

        # ----------------------------------------------------
        # Mutate live position state.
        # ----------------------------------------------------

        new_open_size = (
            float(
                position.open_size
            )
            - float(
                position_close.size
            )
        )

        if abs(
            new_open_size
        ) < 1e-12:

            new_open_size = 0.0

        position.open_size = (
            new_open_size
        )

        # ----------------------------------------------------
        # Accumulate exit commission on the Position.
        # ----------------------------------------------------

        if not isinstance(
            commission_already_applied,
            bool,
        ):

            raise TypeError(
                "commission_already_applied must be a bool."
            )

        # ----------------------------------------------------
        # Accumulate close commission only when it has not
        # already been applied by the execution/accounting
        # layer.
        #
        # This distinction is required as PositionBook becomes
        # authoritative inside NexusEngine.
        # ----------------------------------------------------

        if not commission_already_applied:

            position.exit_commission_pnl_account += (
                position_close.commission_pnl_account
            )

            position.accrued_commission_pnl_account += (
                position_close.commission_pnl_account
            )

        # ----------------------------------------------------
        # Store immutable close history.
        # ----------------------------------------------------

        self._position_closes[
            position_close_id
        ] = (
            position_close
        )

        return position_close

    # ========================================================
    # COUNT
    # ========================================================

    def __len__(
        self,
    ) -> int:
        """
        Return total number of positions ever created.

        This includes positions that are now fully closed.
        """

        return len(
            self._positions
        )