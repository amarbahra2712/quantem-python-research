# -*- coding: utf-8 -*-
"""
Created on Tue Sep 22 10:37:48 2026

@author: quant
"""

"""
NEXUS Deterministic ID Generator
================================

Purpose
-------
Generate deterministic sequential identifiers for execution
objects created during one NEXUS backtest run.

Responsibilities
----------------
- Generate sequential Order IDs.
- Generate sequential Fill IDs.
- Generate sequential Position IDs.
- Generate sequential Basket IDs.
- Reset all counters at the beginning of a run.
- Keep identifiers human-readable and easy to trace.

Does Not
--------
- Store orders or positions.
- Execute orders.
- Manage trading state.
- Generate globally unique identifiers.
- Persist counters between backtest runs.

Architecture
------------
Identifiers are deterministic within one NEXUS run:

    ORD000001
    ORD000002

    FILL000001
    FILL000002

    POS000001
    POS000002

    BASKET000001

The unique NEXUS run_id provides the higher-level identity
across different backtest runs.

This means:

    run_ABC / ORD000001

and:

    run_XYZ / ORD000001

are separate and unambiguous execution objects.
"""


from typing import Dict


# ============================================================
# ENTITY PREFIXES
# ============================================================

ID_PREFIXES = {
    "order": "ORD",
    "fill": "FILL",
    "position": "POS",
    "position_close": "PCLOSE",
    "basket": "BASKET",
}


# ============================================================
# ID GENERATOR
# ============================================================

class IdGenerator:
    """
    Generate deterministic sequential IDs for one NEXUS run.
    """

    def __init__(
        self,
        width: int = 6,
    ):

        if (
            isinstance(
                width,
                bool,
            )
            or not isinstance(
                width,
                int,
            )
            or width <= 0
        ):

            raise ValueError(
                "width must be a positive integer."
            )

        self.width = width

        self._counters = {
            entity_type: 0
            for entity_type
            in ID_PREFIXES
        }


    # ========================================================
    # GENERIC ID
    # ========================================================

    def next_id(
        self,
        entity_type: str,
    ) -> str:
        """
        Return the next sequential identifier for an entity.
        """

        if (
            entity_type
            not in ID_PREFIXES
        ):

            raise ValueError(
                "Unsupported entity_type: "
                f"{entity_type}"
            )

        self._counters[
            entity_type
        ] += 1

        prefix = (
            ID_PREFIXES[
                entity_type
            ]
        )

        counter = (
            self._counters[
                entity_type
            ]
        )

        return (
            f"{prefix}"
            f"{counter:0{self.width}d}"
        )


    # ========================================================
    # CONVENIENCE METHODS
    # ========================================================

    def next_order_id(
        self,
    ) -> str:

        return self.next_id(
            "order"
        )


    def next_fill_id(
        self,
    ) -> str:

        return self.next_id(
            "fill"
        )


    def next_position_id(
        self,
    ) -> str:

        return self.next_id(
            "position"
        )

    def next_position_close_id(
        self,
    ) -> str:

        return self.next_id(
            "position_close"
        )

    def next_basket_id(
        self,
    ) -> str:

        return self.next_id(
            "basket"
        )


    # ========================================================
    # COUNTER STATE
    # ========================================================

    @property
    def counters(
        self,
    ) -> Dict[str, int]:
        """
        Return a copy of the current counter state.
        """

        return dict(
            self._counters
        )


    # ========================================================
    # RESET
    # ========================================================

    def reset(
        self,
    ) -> None:
        """
        Reset all counters to zero.
        """

        for entity_type in (
            self._counters
        ):

            self._counters[
                entity_type
            ] = 0