# -*- coding: utf-8 -*-
"""
Created on Sat Sep 12 11:31:49 2026
@author: quant
08_config/prop_config.py
"""

"""
Generic Prop-Firm Configuration
===============================

Purpose
-------
Define the provider-neutral configuration schema used by the
NEXUS prop-firm evaluation framework.

Responsibilities
----------------
- Describe profit-target requirements.
- Describe daily-loss rules.
- Describe total-loss rules.
- Describe reset timezone and reset time.
- Describe trading-day requirements.
- Describe supported boundary behaviour.
- Validate supplied prop-rule parameters.
- Provide a common interface for all provider presets.

Does Not
--------
- Contain FTMO-specific or other provider-specific values.
- Select the active provider.
- Evaluate prop rules.
- Execute trades.
- Modify NexusEngine.
- Calculate commission, swap or account P&L.

Architecture
------------
Provider-specific preset modules construct PropFirmConfig
instances.

Examples may include:

    ftmo_config.py
    future provider preset modules

The generic prop evaluator consumes PropFirmConfig without
needing to know which provider produced it.

Notes
-----
Percentage values are represented as decimal fractions.

Examples:

    0.05 = 5%
    0.10 = 10%

Execution costs are not prop-rule parameters. Commission and
swap belong to ExecutionConfig and are already reflected in
NEXUS account balance and equity before prop rules are
evaluated.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class PropFirmConfig:
    """
    Generic configuration for one prop-firm evaluation phase.
    """

    # --------------------------------------------------------
    # Identity
    # --------------------------------------------------------

    provider_name: str
    programme_name: str
    phase_name: str

    # --------------------------------------------------------
    # Profit objective
    # --------------------------------------------------------

    profit_target_pct: Optional[float] = 0.10

    # Supported V1 value:
    #
    #     "balance"
    #
    # Future models could include other provider-specific
    # definitions if required.
    profit_target_measure: str = "balance"
    
    # If True, the account must have no open position when the
    # profit target is considered successfully achieved.
    #
    # Provider presets should explicitly set this where required.
    #
    profit_target_requires_flat: bool=False

    # --------------------------------------------------------
    # Maximum daily loss
    # --------------------------------------------------------

    # Allowed daily loss expressed as a percentage.
    #
    # Example:
    #
    #     0.05 = 5%
    #
    daily_loss_pct: Optional[float] = 0.05

    # Optional fixed cash loss allowance.
    #
    # When supplied, this can later override or supplement
    # percentage-based calculations.
    daily_loss_amount: Optional[float] = None

    # Defines what the percentage allowance is calculated from.
    #
    # Supported V1 values:
    #
    #     "initial_balance"
    #     "day_start_balance"
    #     "day_start_equity"
    #
    daily_loss_allowance_reference: str = (
        "initial_balance"
    )

    # Defines where the daily loss floor is anchored.
    #
    # Example:
    #
    #     day_start_balance - allowed_daily_loss
    #
    # Supported V1 values:
    #
    #     "day_start_balance"
    #     "day_start_equity"
    #
    daily_loss_anchor: str = (
        "day_start_balance"
    )

    # Defines the account measure compared with the daily floor.
    #
    # Supported V1 values:
    #
    #     "equity"
    #     "balance"
    #
    daily_loss_measure: str = "equity"

    # --------------------------------------------------------
    # Maximum total loss
    # --------------------------------------------------------

    total_loss_pct: Optional[float] = 0.10

    total_loss_amount: Optional[float] = None

    # Supported V1 model:
    #
    #     "static_initial"
    #
    # Future models can include:
    #
    #     "trailing_balance"
    #     "trailing_equity"
    #     "eod_trailing_balance"
    #
    total_loss_model: str = "static_initial"

    # Supported V1 values:
    #
    #     "equity"
    #     "balance"
    #
    total_loss_measure: str = "equity"

    # --------------------------------------------------------
    # Daily reset
    # --------------------------------------------------------

    # Generic default is UTC.
    #
    # Provider presets should override this where required.
    daily_reset_timezone: str = "Europe/Prague"

    daily_reset_hour: int = 0
    daily_reset_minute: int = 0

    # --------------------------------------------------------
    # Trading-day requirements
    # --------------------------------------------------------
    
    minimum_trading_days: int = 4
    
    maximum_trading_days: Optional[int] = None
    
    # Defines what constitutes a trading day.
    #
    # Supported V1 value:
    #
    #     "entry"
    #
    # A prop day counts when at least one position is opened
    # during that prop trading day.
    #
    trading_day_activity_basis: str = "entry"

    # --------------------------------------------------------
    # Boundary behaviour
    # --------------------------------------------------------

    # True means touching the loss floor is considered a
    # breach.
    breach_on_equal: bool = True

    # --------------------------------------------------------
    # Validation
    # --------------------------------------------------------

    def __post_init__(self) -> None:
        """
        Validate generic prop-firm configuration.
        """

        if not self.provider_name:
            raise ValueError(
                "provider_name cannot be empty."
            )

        if not self.programme_name:
            raise ValueError(
                "programme_name cannot be empty."
            )

        if not self.phase_name:
            raise ValueError(
                "phase_name cannot be empty."
            )

        percentage_fields = {
            "profit_target_pct":
                self.profit_target_pct,

            "daily_loss_pct":
                self.daily_loss_pct,

            "total_loss_pct":
                self.total_loss_pct,
        }

        for name, value in percentage_fields.items():

            if value is None:
                continue

            if value < 0.0:
                raise ValueError(
                    f"{name} cannot be negative."
                )

        amount_fields = {
            "daily_loss_amount":
                self.daily_loss_amount,

            "total_loss_amount":
                self.total_loss_amount,
        }

        for name, value in amount_fields.items():

            if value is None:
                continue

            if value < 0.0:
                raise ValueError(
                    f"{name} cannot be negative."
                )

        if self.daily_reset_hour not in range(
            0,
            24,
        ):
            raise ValueError(
                "daily_reset_hour must be between "
                "0 and 23."
            )

        if self.daily_reset_minute not in range(
            0,
            60,
        ):
            raise ValueError(
                "daily_reset_minute must be between "
                "0 and 59."
            )

        if self.minimum_trading_days < 0:
            raise ValueError(
                "minimum_trading_days cannot be negative."
            )

        if (
            self.maximum_trading_days is not None
            and self.maximum_trading_days < 1
        ):
            raise ValueError(
                "maximum_trading_days must be positive."
            )

        if (
            self.maximum_trading_days is not None
            and self.maximum_trading_days
            < self.minimum_trading_days
        ):
            raise ValueError(
                "maximum_trading_days cannot be less than "
                "minimum_trading_days."
            )

        valid_trading_day_activity_basis = (
            "entry",
        )

        if (
            self.trading_day_activity_basis
            not in valid_trading_day_activity_basis
        ):

            raise ValueError(
                "Unsupported trading_day_activity_basis: "
                f"{self.trading_day_activity_basis}"
            )


        valid_profit_measures = (
            "balance",
        )

        if (
            self.profit_target_measure
            not in valid_profit_measures
        ):
            raise ValueError(
                "Unsupported profit_target_measure: "
                f"{self.profit_target_measure}"
            )

        valid_allowance_references = (
            "initial_balance",
            "day_start_balance",
            "day_start_equity",
        )

        if (
            self.daily_loss_allowance_reference
            not in valid_allowance_references
        ):
            raise ValueError(
                "Unsupported "
                "daily_loss_allowance_reference: "
                f"{self.daily_loss_allowance_reference}"
            )

        valid_daily_anchors = (
            "day_start_balance",
            "day_start_equity",
        )

        if (
            self.daily_loss_anchor
            not in valid_daily_anchors
        ):
            raise ValueError(
                "Unsupported daily_loss_anchor: "
                f"{self.daily_loss_anchor}"
            )

        valid_loss_measures = (
            "equity",
            "balance",
        )

        if (
            self.daily_loss_measure
            not in valid_loss_measures
        ):
            raise ValueError(
                "Unsupported daily_loss_measure: "
                f"{self.daily_loss_measure}"
            )

        if (
            self.total_loss_measure
            not in valid_loss_measures
        ):
            raise ValueError(
                "Unsupported total_loss_measure: "
                f"{self.total_loss_measure}"
            )

        valid_total_loss_models = (
            "static_initial",
            "trailing_balance",
            "trailing_equity",
            "eod_trailing_balance",
        )

        if (
            self.total_loss_model
            not in valid_total_loss_models
        ):
            raise ValueError(
                "Unsupported total_loss_model: "
                f"{self.total_loss_model}"
            )