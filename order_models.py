# -*- coding: utf-8 -*-
"""
Created on Tue Sep 22 08:42:10 2026

@author: quant
"""

"""
NEXUS Order Models
==================

Purpose
-------
Define the execution objects that exist before and during
the creation of a live position.

Responsibilities
----------------
- Represent an order submitted to the execution engine.
- Represent an individual execution fill.
- Maintain deterministic identifiers and execution metadata.
- Provide the foundation for future pending orders,
  partial fills, OCO relationships, hedges, and baskets.

Does Not
--------
- Store or manage collections of orders.
- Execute orders.
- Manage live positions.
- Calculate account P&L.
- Contain strategy logic.

Architecture
------------
The intended execution lifecycle is:

    Strategy
        ↓
      Order
        ↓
       Fill
        ↓
     Position

One Order may eventually generate multiple Fill objects.

The current Base V1 engine does not yet use these models.
They are introduced independently so that existing engine
behaviour remains unchanged during the refactor.
"""


from dataclasses import dataclass
from typing import Optional

import pandas as pd

import math
from numbers import Real

# ============================================================
# MODEL CONTRACTS
# ============================================================

VALID_DIRECTIONS = (
    1,
    -1,
)

VALID_ORDER_TYPES = (
    "market",
    "stop",
    "limit",
)

VALID_ORDER_STATUSES = (
    "pending",
    "partially_filled",
    "filled",
    "cancelled",
    "rejected",
)


# ============================================================
# ORDER
# ============================================================

@dataclass
class Order:
    """
    Represents an instruction to create or modify exposure.

    An Order is not itself a Position.

    It may be pending, filled, cancelled, or rejected without
    ever creating live exposure.
    """

    order_id: str

    signal_time: pd.Timestamp
    submitted_time: pd.Timestamp

    direction: int
    size: float

    order_type: str = "market"
    status: str = "pending"

    # --------------------------------------------------------
    # Pending-order execution price
    # --------------------------------------------------------

    # Used by future stop / limit orders.
    #
    # Market orders normally leave this as None.
    trigger_price: Optional[float] = None

    # --------------------------------------------------------
    # Future relationship metadata
    # --------------------------------------------------------

    # Allows an order to identify the order that created it
    # or with which it is associated.
    parent_order_id: Optional[str] = None

    # Future One-Cancels-Other relationship.
    oco_group_id: Optional[str] = None

    # Future hedge / basket grouping.
    basket_id: Optional[str] = None

    # Human-readable purpose such as:
    #
    #     primary
    #     hedge
    #     scale_in
    #     protective_exit
    #
    role: Optional[str] = None

    # --------------------------------------------------------
    # Validation
    # --------------------------------------------------------

    def __post_init__(
        self,
    ):
        """
        Validate the internal consistency of the Order.
        """

        if (
            not isinstance(
                self.order_id,
                str,
            )
            or not self.order_id.strip()
        ):

            raise ValueError(
                "order_id must be a non-empty string."
            )

        if not isinstance(
            self.signal_time,
            pd.Timestamp,
        ):

            raise TypeError(
                "signal_time must be a pandas Timestamp."
            )

        if not isinstance(
            self.submitted_time,
            pd.Timestamp,
        ):

            raise TypeError(
                "submitted_time must be a pandas Timestamp."
            )

        if (
            self.signal_time.tz
            is None
        ):

            raise ValueError(
                "signal_time must be timezone-aware."
            )

        if (
            self.submitted_time.tz
            is None
        ):

            raise ValueError(
                "submitted_time must be timezone-aware."
            )

        if (
            self.submitted_time
            < self.signal_time
        ):

            raise ValueError(
                "submitted_time cannot be earlier "
                "than signal_time."
            )

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

        if (
            self.order_type
            not in VALID_ORDER_TYPES
        ):

            raise ValueError(
                "Unsupported order_type: "
                f"{self.order_type}"
            )

        if (
            self.status
            not in VALID_ORDER_STATUSES
        ):

            raise ValueError(
                "Unsupported order status: "
                f"{self.status}"
            )

        # ----------------------------------------------------
        # Entry trigger rules
        # ----------------------------------------------------

        if (
            self.order_type
            == "market"
        ):

            if (
                self.trigger_price
                is not None
            ):

                raise ValueError(
                    "Market orders must not have "
                    "a trigger_price."
                )

        else:

            if (
                self.trigger_price
                is None
            ):

                raise ValueError(
                    f"{self.order_type} orders require "
                    "a trigger_price."
                )

            if (
                not isinstance(
                    self.trigger_price,
                    Real,
                )
                or isinstance(
                    self.trigger_price,
                    bool,
                )
                or not math.isfinite(
                    float(
                        self.trigger_price
                    )
                )
                or self.trigger_price <= 0
            ):

                raise ValueError(
                    "trigger_price must be a positive "
                    "finite number."
                )

        # ----------------------------------------------------
        # Optional relationship identifiers
        # ----------------------------------------------------

        for field_name in (
            "parent_order_id",
            "oco_group_id",
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
                    f"{field_name} must be None or "
                    "a non-empty string."
                )

# ============================================================
# FILL
# ============================================================

@dataclass
class Fill:
    """
    Represents one actual execution against an Order.

    One Order may eventually have multiple Fill objects.
    """

    fill_id: str
    order_id: str

    fill_time: pd.Timestamp

    direction: int
    size: float

    fill_price: float

    # Commission posted specifically because of this fill.
    #
    # Costs are negative.
    commission_pnl_account: float = 0.0
    
    # --------------------------------------------------------
    # Validation
    # --------------------------------------------------------

    def __post_init__(
        self,
    ):
        """
        Validate the internal consistency of the Fill.
        """

        if (
            not isinstance(
                self.fill_id,
                str,
            )
            or not self.fill_id.strip()
        ):

            raise ValueError(
                "fill_id must be a non-empty string."
            )

        if (
            not isinstance(
                self.order_id,
                str,
            )
            or not self.order_id.strip()
        ):

            raise ValueError(
                "order_id must be a non-empty string."
            )

        if not isinstance(
            self.fill_time,
            pd.Timestamp,
        ):

            raise TypeError(
                "fill_time must be a pandas Timestamp."
            )

        if (
            self.fill_time.tz
            is None
        ):

            raise ValueError(
                "fill_time must be timezone-aware."
            )

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

        if (
            not isinstance(
                self.fill_price,
                Real,
            )
            or isinstance(
                self.fill_price,
                bool,
            )
            or not math.isfinite(
                float(
                    self.fill_price
                )
            )
            or self.fill_price <= 0
        ):

            raise ValueError(
                "fill_price must be a positive "
                "finite number."
            )

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