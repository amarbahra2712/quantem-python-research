# -*- coding: utf-8 -*-
"""
Created on Sat Sep 12 09:32:25 2026
@author: quant


NEXUS position-sizing module.

Purpose
-------
Calculates trade quantity from:

- account balance
- risk per trade
- distance between entry and stop
- instrument base and quote currencies
- account currency

An optional margin constraint can also be applied.

The module is deliberately independent of how the stop
distance was calculated. The stop may be based on:

- ATR
- fixed price distance
- pips
- market structure
- swing highs/lows
- indicators
- volatility measures
- any other strategy rule

Responsibilities
----------------
- calculate risk-based position size
- account for FX currency relationships
- optionally calculate a margin-based maximum position size
- return the permitted trade quantity in base-currency units

Does not
--------
- determine where the stop should be placed
- calculate indicators
- generate trading signals
- execute trades
- manage open positions
- manage account equity
- apply prop-firm or FTMO rules
- perform general cross-currency conversion

How to use
----------
1. Determine the executable entry price and stop price.
2. Calculate the absolute price distance between them.
3. Pass that distance as `stop_distance`.
4. Supply account balance and risk per trade.
5. Supply the account, base and quote currencies.
6. Set `use_margin_limit=True` when margin should restrict
   position size.

Notes
-----
Position quantity is expressed in units of the instrument's
base currency.

NEXUS V1 directly supports:

1. account currency = quote currency

   Example:

       GBPUSD with USD account

2. account currency = base currency

   Example:

       USDJPY with USD account

If the account currency is neither the base nor quote
currency, an additional FX conversion rate is required.
That case is intentionally deferred to a later version.
"""

from typing import Optional


def calculate_position_size(
    balance: float,
    entry_price: float,
    stop_distance: float,
    risk_per_trade: float,
    account_currency: str,
    base_currency: str,
    quote_currency: str,
    use_margin_limit: bool = True,
    margin_requirement: Optional[float] = None,
    max_margin_fraction: Optional[float] = None,
) -> float:
    """
    Calculate permitted position quantity in base-currency
    units.
    """

    # ---------------------------------------------------------
    # Basic validation
    # ---------------------------------------------------------

    if balance <= 0:
        return 0.0

    if entry_price <= 0:
        return 0.0

    if stop_distance <= 0:
        return 0.0

    if risk_per_trade <= 0:
        return 0.0

    account_currency = account_currency.upper()
    base_currency = base_currency.upper()
    quote_currency = quote_currency.upper()

    # ---------------------------------------------------------
    # Account risk amount
    # ---------------------------------------------------------

    risk_amount = (
        balance
        * risk_per_trade
    )

    # ---------------------------------------------------------
    # Risk per base-currency unit
    # ---------------------------------------------------------

    if account_currency == quote_currency:

        # Example:
        #
        # GBPUSD with USD account
        #
        # A 0.0020 price movement on one GBP unit produces
        # 0.0020 USD of P&L.
        risk_per_unit = stop_distance

    elif account_currency == base_currency:

        # Example:
        #
        # USDJPY with USD account
        #
        # The stop distance is initially denominated in JPY.
        # Convert that value back into USD using the current
        # instrument price.
        risk_per_unit = (
            stop_distance
            / entry_price
        )

    else:
        raise ValueError(
            "NEXUS V1 cannot calculate position size when "
            "the account currency is neither the instrument's "
            "base nor quote currency. "
            f"Base={base_currency}, "
            f"quote={quote_currency}, "
            f"account={account_currency}."
        )

    # ---------------------------------------------------------
    # Risk-based position size
    # ---------------------------------------------------------

    risk_quantity = (
        risk_amount
        / risk_per_unit
    )

    # ---------------------------------------------------------
    # No margin constraint
    # ---------------------------------------------------------

    if not use_margin_limit:
        return float(risk_quantity)

    # ---------------------------------------------------------
    # Validate margin inputs
    # ---------------------------------------------------------

    if margin_requirement is None:
        raise ValueError(
            "margin_requirement is required when "
            "use_margin_limit=True"
        )

    if max_margin_fraction is None:
        raise ValueError(
            "max_margin_fraction is required when "
            "use_margin_limit=True"
        )

    if margin_requirement <= 0:
        raise ValueError(
            "margin_requirement must be greater than zero"
        )

    if not 0 < max_margin_fraction <= 1:
        raise ValueError(
            "max_margin_fraction must be between 0 and 1"
        )

    # ---------------------------------------------------------
    # Available account capital for margin
    # ---------------------------------------------------------

    available_margin_capital = (
        balance
        * max_margin_fraction
    )

    # ---------------------------------------------------------
    # Margin-based maximum quantity
    # ---------------------------------------------------------

    if account_currency == quote_currency:

        # Example:
        #
        # GBPUSD with USD account.
        #
        # One GBP of notional is worth `entry_price` USD.
        margin_quantity = (
            available_margin_capital
            / (
                margin_requirement
                * entry_price
            )
        )

    else:

        # Account currency equals base currency.
        #
        # Example:
        #
        # USDJPY with USD account.
        #
        # One unit of base currency is already one unit of
        # account currency.
        margin_quantity = (
            available_margin_capital
            / margin_requirement
        )

    # ---------------------------------------------------------
    # Final permitted quantity
    # ---------------------------------------------------------

    quantity = min(
        risk_quantity,
        margin_quantity,
    )

    return float(quantity)