# -*- coding: utf-8 -*-
"""
Created on Tue Sep 22 10:41:38 2026

@author: quant
"""

"""
NEXUS Order Book
================

Purpose
-------
Store and manage orders belonging to one NEXUS backtest run.

Responsibilities
----------------
- Create orders with deterministic IDs.
- Store orders by order_id.
- Retrieve individual orders.
- Return all orders.
- Return currently active orders.
- Cancel cancellable orders.

Does Not
--------
- Determine whether market prices trigger orders.
- Generate fills.
- Create positions.
- Calculate P&L.
- Contain strategy logic.

Architecture
------------
The OrderBook owns the collection of Order objects.

For now:

    Strategy intent
        ↓
    OrderBook.create_order()
        ↓
      Order

Later:

      Order
        ↓
    execution logic
        ↓
       Fill
        ↓
     Position

The OrderBook receives a shared IdGenerator so that the same
run-level ID infrastructure can later also generate Fill,
Position, and Basket identifiers.
"""


from typing import (
    Dict,
    List,
    Optional,
)

import pandas as pd
import math

from id_generator import IdGenerator
from order_models import (
    Order,
    Fill,
)


# ============================================================
# ACTIVE ORDER STATES
# ============================================================

ACTIVE_ORDER_STATUSES = (
    "pending",
    "partially_filled",
)


# ============================================================
# ORDER BOOK
# ============================================================

class OrderBook:
    """
    Store and manage orders for one NEXUS run.
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

        self._orders: Dict[
            str,
            Order,
        ] = {}

        self._fills: Dict[
            str,
            Fill,
        ] = {}

    # ========================================================
    # CREATE ORDER
    # ========================================================

    def create_order(
        self,
        signal_time: pd.Timestamp,
        submitted_time: pd.Timestamp,
        direction: int,
        size: float,
        order_type: str = "market",
        trigger_price: Optional[float] = None,
        parent_order_id: Optional[str] = None,
        oco_group_id: Optional[str] = None,
        basket_id: Optional[str] = None,
        role: Optional[str] = None,
    ) -> Order:
        """
        Create and store a new Order.
        """

        order_id = (
            self.id_generator
            .next_order_id()
        )

        order = Order(
            order_id=order_id,

            signal_time=(
                signal_time
            ),

            submitted_time=(
                submitted_time
            ),

            direction=(
                direction
            ),

            size=(
                size
            ),

            order_type=(
                order_type
            ),

            status="pending",

            trigger_price=(
                trigger_price
            ),

            parent_order_id=(
                parent_order_id
            ),

            oco_group_id=(
                oco_group_id
            ),

            basket_id=(
                basket_id
            ),

            role=(
                role
            ),
        )

        self._orders[
            order_id
        ] = order

        return order


    # ========================================================
    # GET ORDER
    # ========================================================

    def get_order(
        self,
        order_id: str,
    ) -> Order:
        """
        Retrieve one Order by ID.
        """

        if (
            order_id
            not in self._orders
        ):

            raise KeyError(
                "Unknown order_id: "
                f"{order_id}"
            )

        return (
            self._orders[
                order_id
            ]
        )


    # ========================================================
    # ALL ORDERS
    # ========================================================

    def all_orders(
        self,
    ) -> List[Order]:
        """
        Return all orders in creation order.
        """

        return list(
            self._orders.values()
        )


    # ========================================================
    # ACTIVE ORDERS
    # ========================================================

    def active_orders(
        self,
    ) -> List[Order]:
        """
        Return orders that remain executable.
        """

        return [
            order
            for order
            in self._orders.values()
            if order.status
            in ACTIVE_ORDER_STATUSES
        ]


    # ========================================================
    # CANCEL ORDER
    # ========================================================

    def cancel_order(
        self,
        order_id: str,
    ) -> Order:
        """
        Cancel an active Order.

        Filled, cancelled, and rejected orders cannot be
        cancelled.
        """

        order = self.get_order(
            order_id
        )

        if (
            order.status
            not in ACTIVE_ORDER_STATUSES
        ):

            raise ValueError(
                "Order cannot be cancelled from status: "
                f"{order.status}"
            )

        order.status = (
            "cancelled"
        )

        return order


    # ========================================================
    # FILLS FOR ORDER
    # ========================================================

    def fills_for_order(
        self,
        order_id: str,
    ) -> List[Fill]:
        """
        Return all fills belonging to one Order.
        """

        # Confirm that the order exists.
        self.get_order(
            order_id
        )

        return [
            fill
            for fill
            in self._fills.values()
            if fill.order_id
            == order_id
        ]


    # ========================================================
    # ALL FILLS
    # ========================================================

    def all_fills(
        self,
    ) -> List[Fill]:
        """
        Return all fills in creation order.
        """

        return list(
            self._fills.values()
        )


    # ========================================================
    # FILLED SIZE
    # ========================================================

    def filled_size(
        self,
        order_id: str,
    ) -> float:
        """
        Return cumulative quantity already filled for an Order.
        """

        fills = (
            self.fills_for_order(
                order_id
            )
        )

        return float(
            sum(
                fill.size
                for fill
                in fills
            )
        )


    # ========================================================
    # REMAINING SIZE
    # ========================================================

    def remaining_size(
        self,
        order_id: str,
    ) -> float:
        """
        Return quantity still available to fill.
        """

        order = (
            self.get_order(
                order_id
            )
        )

        remaining = (
            float(
                order.size
            )
            - self.filled_size(
                order_id
            )
        )

        # Protect against tiny floating-point residues.
        if math.isclose(
            remaining,
            0.0,
            rel_tol=1e-12,
            abs_tol=1e-12,
        ):

            return 0.0

        return remaining


    # ========================================================
    # RECORD FILL
    # ========================================================

    def record_fill(
        self,
        order_id: str,
        fill_time: pd.Timestamp,
        size: float,
        fill_price: float,
        commission_pnl_account: float = 0.0,
    ) -> Fill:
        """
        Record one execution Fill against an active Order.

        The OrderBook does not decide whether market conditions
        justify the execution. It only records an execution that
        has already been determined by the execution layer.

        Order status becomes:

            partially_filled

        when only part of the requested quantity has executed,
        and:

            filled

        when the complete requested quantity has executed.
        """

        order = (
            self.get_order(
                order_id
            )
        )

        # ----------------------------------------------------
        # Order must still be executable.
        # ----------------------------------------------------

        if (
            order.status
            not in ACTIVE_ORDER_STATUSES
        ):

            raise ValueError(
                "Cannot fill order from status: "
                f"{order.status}"
            )

        # ----------------------------------------------------
        # Fill cannot pre-date submission.
        # ----------------------------------------------------

        if not isinstance(
            fill_time,
            pd.Timestamp,
        ):

            raise TypeError(
                "fill_time must be a pandas Timestamp."
            )

        if (
            fill_time.tz
            is None
        ):

            raise ValueError(
                "fill_time must be timezone-aware."
            )

        if (
            fill_time
            < order.submitted_time
        ):

            raise ValueError(
                "fill_time cannot be earlier than "
                "submitted_time."
            )

        # ----------------------------------------------------
        # Quantity cannot exceed remaining order quantity.
        # ----------------------------------------------------

        remaining_before = (
            self.remaining_size(
                order_id
            )
        )

        if (
            size
            > remaining_before
        ):

            raise ValueError(
                "Fill size exceeds remaining "
                "order quantity."
            )

        # ----------------------------------------------------
        # Create execution record.
        #
        # Direction comes from the parent Order rather than
        # being supplied independently.
        # ----------------------------------------------------

        fill_id = (
            self.id_generator
            .next_fill_id()
        )

        fill = Fill(
            fill_id=fill_id,

            order_id=(
                order.order_id
            ),

            fill_time=(
                fill_time
            ),

            direction=(
                order.direction
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

        self._fills[
            fill_id
        ] = fill

        # ----------------------------------------------------
        # Determine new order state.
        # ----------------------------------------------------

        total_filled = (
            self.filled_size(
                order_id
            )
        )

        if math.isclose(
            total_filled,
            float(
                order.size
            ),
            rel_tol=1e-12,
            abs_tol=1e-12,
        ):

            order.status = (
                "filled"
            )

        else:

            order.status = (
                "partially_filled"
            )

        return fill

    # ========================================================
    # COUNT
    # ========================================================

    def __len__(
        self,
    ) -> int:
        """
        Return total number of orders stored.
        """

        return len(
            self._orders
        )