# -*- coding: utf-8 -*-
"""
Created on Fri Sep 11 16:13:20 2026

@author: quant
"""

# -*- coding: utf-8 -*-

def calculate_position_size(
    balance,
    entry_price,
    atr,
    stop_atr,
    risk_per_trade,
    margin_requirement,
    max_margin_fraction
):
    """
    Two limits are calculated:

    1. Risk-based quantity
       balance * risk_per_trade / stop_distance

    2. Margin-based maximum quantity
       balance * max_margin_fraction
       / (margin_requirement * entry_price)

    Final quantity is the smaller of the two.
    """

    stop_distance = atr * stop_atr

    if stop_distance <= 0:
        return 0.0

    risk_quantity = (
        balance * risk_per_trade
    ) / stop_distance

    margin_quantity = (
        balance * max_margin_fraction
    ) / (
        margin_requirement * entry_price
    )

    quantity = min(
        risk_quantity,
        margin_quantity
    )

    return quantity