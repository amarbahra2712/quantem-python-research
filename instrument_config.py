# -*- coding: utf-8 -*-
"""
Created on Mon Sep 14 09:39:48 2026

@author: quant


NEXUS instrument configuration.

Purpose
-------
Stores market-specific information required to interpret price
movements, pip values and trading calculations for different
financial instruments.

Responsibilities
----------------
- identify the traded instrument
- define base and quote currencies
- define pip size
- define minimum quoted price increment
- define standard contract size
- provide pip-to-price conversion
- provide price-to-pip conversion

Does not
--------
- define strategy logic
- define stop or target methodology
- generate trading signals
- size positions
- execute trades
- contain account-level risk settings
- contain prop-firm rules

How to use
----------
1. Select the instrument being tested.
2. Retrieve its InstrumentConfig.
3. Strategies may use the configuration when converting
   human-readable pip distances into price distances.
4. The execution and risk layers may use instrument metadata
   where market-specific calculations are required.

Notes
-----
A pip is not the same price increment for every FX pair.

For most non-JPY FX pairs:

    1 pip = 0.0001

For most JPY FX pairs:

    1 pip = 0.01

The minimum quoted price increment may be smaller than one
pip. For example, a five-decimal GBPUSD quote may move in
increments of 0.00001.
"""
######################################################################################
#
#     base currency              ***NEED TO ADD THIS FUNCTIONALITY***
#     quote currency
#
# GBPJPY --> base currency = GBP; quote currency = JPY
# most prop firms account currency is in USD
# conversion happens into P&L so with any pair that has a non-USD quote then there is
# additional currenct risk
#If the quote currency = your account currency, no extra risk
#(EURUSD, GBPUSD, AUDUSD, USDJPY, USDCHF, USDCAD)
#
#✔ If the quote currency ≠ your account currency, extra risk
#(GBPJPY, EURGBP, AUDNZD, CHFJPY, CADJPY, EURCHF, etc.)
#
#USDJPY is special because:
#
#Quote = JPY
#
#Account = USD
#
#Conversion uses USDJPY itself
#
#No second FX rate needed
#
#So it behaves like a USD‑quote pair.
#
######################################################################################

from dataclasses import dataclass


@dataclass(frozen=True)
class InstrumentConfig:
    """
    Market-specific instrument definition.
    """

    symbol: str

    base_currency: str
    quote_currency: str

    pip_size: float
    tick_size: float

    contract_size: float = 100000.0

    def pips_to_price(
        self,
        pips: float
    ) -> float:
        """
        Convert a pip distance into a raw price distance.
        """

        return pips * self.pip_size

    def price_to_pips(
        self,
        price_distance: float
    ) -> float:
        """
        Convert a raw price distance into pips.
        """

        return price_distance / self.pip_size


# ============================================================
# INSTRUMENT DEFINITIONS
# ============================================================

INSTRUMENTS = {

    "GBPUSD": InstrumentConfig(
        symbol="GBPUSD",
        base_currency="GBP",
        quote_currency="USD",
        pip_size=0.0001,
        tick_size=0.00001,
    ),

    "USDJPY": InstrumentConfig(
        symbol="USDJPY",
        base_currency="USD",
        quote_currency="JPY",
        pip_size=0.01,
        tick_size=0.001,
    ),
}


# ============================================================
# CONFIGURATION LOOKUP
# ============================================================

def get_instrument_config(
    symbol: str
) -> InstrumentConfig:
    """
    Return instrument configuration for the requested symbol.
    """

    symbol = symbol.upper()

    if symbol not in INSTRUMENTS:
        raise ValueError(
            f"Unsupported instrument: {symbol}"
        )

    return INSTRUMENTS[symbol]