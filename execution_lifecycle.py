# -*- coding: utf-8 -*-
"""
Created on Tue Sep 22 11:37:54 2026

@author: quant
"""

"""
NEXUS Execution Lifecycle
=========================

Purpose
-------
Coordinate the transition from an entry Order and its Fill
records into a live Position.

Responsibilities
----------------
- Record entry fills through the OrderBook.
- Create a Position from the first fill of an entry Order.
- Apply subsequent partial fills to the same Position.
- Calculate weighted-average entry price.
- Accumulate entry commission.
- Preserve Order -> Fill -> Position relationships.

Does Not
--------
- Decide when an order should execute.
- Evaluate market prices.
- Trigger stop or limit orders.
- Close positions.
- Calculate realised P&L.
- Manage account balance.
- Contain strategy logic.

Architecture
------------
First fill:

    ORD000001
        ↓
    FILL000001
        ↓
    POS000001

Subsequent fill of the same Order:

    ORD000001
        ↓
    FILL000002
        ↓
    POS000001 updated

One entry Order therefore maps to at most one Position.
"""


import math

from numbers import Real

from typing import Optional

import pandas as pd

from order_book import OrderBook
from position_book import PositionBook
from position_models import Position


# ============================================================
# EXECUTION LIFECYCLE
# ============================================================

class ExecutionLifecycle:
    """
    Coordinate OrderBook fills with PositionBook state.
    """

    def __init__(
        self,
        order_book: OrderBook,
        position_book: PositionBook,
    ):

        if not isinstance(
            order_book,
            OrderBook,
        ):

            raise TypeError(
                "order_book must be an OrderBook."
            )

        if not isinstance(
            position_book,
            PositionBook,
        ):

            raise TypeError(
                "position_book must be a PositionBook."
            )

        # ----------------------------------------------------
        # Both books must belong to the same NEXUS run-level
        # ID generator.
        # ----------------------------------------------------

        if (
            order_book.id_generator
            is not position_book.id_generator
        ):

            raise ValueError(
                "OrderBook and PositionBook must share "
                "the same IdGenerator instance."
            )

        self.order_book = (
            order_book
        )

        self.position_book = (
            position_book
        )


    # ========================================================
    # RECORD ENTRY FILL
    # ========================================================

    def record_entry_fill(
        self,
        order_id: str,
        fill_time: pd.Timestamp,
        size: float,
        fill_price: float,
        commission_pnl_account: float = 0.0,
        initial_stop_price: Optional[float] = None,
        stop_price: Optional[float] = None,
        target_price: Optional[float] = None,
        breakeven_trigger_price: Optional[float] = None,
        initial_risk_distance: float = 0.0,
    ) -> Position:
        """
        Record one entry Fill and create or update its Position.

        First Fill
        ----------
        Creates a new Position.

        Later Fill
        ----------
        Increases the same Position and recalculates its
        weighted-average entry price.

        Returns
        -------
        Position
            The newly created or updated Position.
        """

        order = (
            self.order_book.get_order(
                order_id
            )
        )

        existing_position = (
            self.position_book
            .position_for_source_order(
                order_id
            )
        )

        # ----------------------------------------------------
        # For this first implementation, additional entry
        # fills are only permitted before the Position has
        # begun closing.
        # ----------------------------------------------------

        if (
            existing_position
            is not None
            and len(
                self.position_book
                .closes_for_position(
                    existing_position.position_id
                )
            )
            > 0
        ):

            raise ValueError(
                "Cannot apply additional entry fills "
                "after a Position has begun closing."
            )

        # ----------------------------------------------------
        # Record Fill in OrderBook.
        # ----------------------------------------------------

        fill = (
            self.order_book.record_fill(
                order_id=(
                    order_id
                ),

                fill_time=(
                    fill_time
                ),

                size=(
                    size
                ),

                fill_price=(
                    fill_price
                ),

                commission_pnl_account=(
                    commission_pnl_account
                ),
            )
        )

        # ----------------------------------------------------
        # FIRST FILL -> CREATE POSITION
        # ----------------------------------------------------

        if (
            existing_position
            is None
        ):

            position = (
                self.position_book
                .create_position(
                    source_order_id=(
                        order.order_id
                    ),

                    signal_time=(
                        order.signal_time
                    ),

                    entry_time=(
                        fill.fill_time
                    ),

                    direction=(
                        order.direction
                    ),

                    size=(
                        fill.size
                    ),

                    entry_price=(
                        fill.fill_price
                    ),

                    basket_id=(
                        order.basket_id
                    ),

                    role=(
                        order.role
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
                        fill.commission_pnl_account
                    ),
                )
            )

            return position

        # ----------------------------------------------------
        # SUBSEQUENT FILL -> UPDATE EXISTING POSITION
        # ----------------------------------------------------

        old_size = float(
            existing_position.initial_size
        )

        additional_size = float(
            fill.size
        )

        new_size = (
            old_size
            + additional_size
        )

        weighted_entry_price = (
            (
                existing_position.entry_price
                * old_size
            )
            + (
                fill.fill_price
                * additional_size
            )
        ) / new_size

        existing_position.entry_price = (
            weighted_entry_price
        )

        existing_position.initial_size = (
            new_size
        )

        existing_position.open_size += (
            additional_size
        )

        existing_position.entry_commission_pnl_account += (
            fill.commission_pnl_account
        )

        existing_position.accrued_commission_pnl_account += (
            fill.commission_pnl_account
        )

        return (
            existing_position
        )