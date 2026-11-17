# -*- coding: utf-8 -*-
"""
Created on Fri Sep 11 16:19:23 2026

@author: quant
"""

# -*- coding: utf-8 -*-

# =========================================================
# LEGACY REGRESSION BASELINE
#
# USDJPY 5M 2021
# Starting balance: 30,000
# Final balance:    60,728.70643705743
# Total P&L:        30,728.70643705743
# Return:           102.4290214568581%
# Closed trades:    59
# Raw signal bars:  108
#
# DO NOT MODIFY LEGACY BEHAVIOUR.
# =========================================================

import pandas as pd

from position_sizing import calculate_position_size


class LegacyBacktestEngine:
    """
    Faithful reconstruction of the original iterative
    portfolio simulation.

    This intentionally preserves legacy execution behaviour,
    including same-bar breakeven/stop sequencing.
    """

    def __init__(
        self,
        account_config,
        strategy_config,
        backtest_config
    ):
        self.account_config = account_config
        self.strategy_config = strategy_config
        self.backtest_config = backtest_config

    def run(self, df):

        df = df.copy()

        # --------------------------------------------------
        # Legacy output columns
        # --------------------------------------------------

        df["max_lvg"] = 0.0
        df["trd_lvg"] = 0.0
        df["position"] = 0.0
        df["trade_pl"] = 0.0
        df["total_pl"] = 0.0
        df["total_fund"] = (
            self.account_config.starting_balance
        )
        df["sl_adj"] = float("nan")

        # --------------------------------------------------
        # Legacy state variables
        # --------------------------------------------------

        trade = 0

        sl_st = 0.0
        lmt_st = 0.0
        atr_st = 0.0
        tlvg_st = 0.0
        dfb_st = 0.0

        sl_adj = 0.0
        count = 0

        trades = []

        # --------------------------------------------------
        # Main legacy loop
        # --------------------------------------------------

        for i in range(1, len(df)):

            close = df.iloc[i]["close"]
            eflag = df.iloc[i]["entry_signal"]

            low = df.iloc[i]["low"]
            high = df.iloc[i]["high"]

            atr = df.iloc[i]["atr"]

            spread = df.iloc[i]["spread"] / 10.0

            previous_fund = df.iloc[i - 1]["total_fund"]

            # ----------------------------------------------
            # Position sizing
            # ----------------------------------------------

            max_lvg = (
                previous_fund
                * self.account_config.max_margin_fraction
            ) / (
                self.account_config.margin_requirement
                * close
            )

            trd_lvg = calculate_position_size(
                balance=previous_fund,
                entry_price=close,
                atr=atr,
                stop_atr=self.strategy_config.stop_atr,
                risk_per_trade=(
                    self.account_config.risk_per_trade
                ),
                margin_requirement=(
                    self.account_config.margin_requirement
                ),
                max_margin_fraction=(
                    self.account_config.max_margin_fraction
                )
            )

            df.at[df.index[i], "max_lvg"] = max_lvg
            df.at[df.index[i], "trd_lvg"] = trd_lvg

            # ----------------------------------------------
            # ENTRY
            # ----------------------------------------------

            if trade == 0 and eflag != 0:

                direction = int(eflag)

                if direction == 1:
                    entry_price = close + spread / 2.0
                else:
                    entry_price = close - spread / 2.0

                df.at[
                    df.index[i],
                    "position"
                ] = direction * entry_price

                dfb_st = direction * entry_price

                # Recreate stop/target directly from
                # signal-bar close and ATR.
                if direction == 1:

                    sl_st = (
                        close
                        - atr
                        * self.strategy_config.stop_atr
                    )

                    lmt_st = (
                        close
                        + atr
                        * self.strategy_config.target_atr
                    )

                else:

                    sl_st = (
                        close
                        + atr
                        * self.strategy_config.stop_atr
                    )

                    lmt_st = (
                        close
                        - atr
                        * self.strategy_config.target_atr
                    )

                atr_st = atr
                tlvg_st = trd_lvg

                trade = direction
                count = 1

                current_trade = {
                    "entry_index": i,
                    "entry_time": df.iloc[i]["timestamp"],
                    "direction": direction,
                    "entry_price": entry_price,
                    "signal_close": close,
                    "atr": atr_st,
                    "initial_stop": sl_st,
                    "target": lmt_st,
                    "quantity": tlvg_st,
                    "balance_before": previous_fund
                }

            # ----------------------------------------------
            # MANAGE OPEN TRADE
            # ----------------------------------------------

            elif trade != 0:

                # ------------------------------------------
                # Legacy breakeven adjustment
                # ------------------------------------------

                if count == 1:
                    sl_adj = sl_st

                if trade == 1:

                    if (
                        high
                        >= sl_st
                        + atr_st
                        * (
                            self.strategy_config.stop_atr
                            + self.strategy_config.breakeven_atr
                        )
                    ):

                        sl_adj = (
                            sl_st
                            + atr_st
                            * self.strategy_config.stop_atr
                            + spread
                        )

                    else:
                        sl_adj = max(sl_st, sl_adj)

                elif trade == -1:

                    if (
                        low
                        <= sl_st
                        - atr_st
                        * (
                            self.strategy_config.stop_atr
                            + self.strategy_config.breakeven_atr
                        )
                    ):

                        sl_adj = (
                            sl_st
                            - atr_st
                            * self.strategy_config.stop_atr
                            - spread
                        )

                    else:
                        sl_adj = min(sl_st, sl_adj)

                count += 1

                df.at[
                    df.index[i],
                    "sl_adj"
                ] = sl_adj

                # ------------------------------------------
                # STOP TEST FIRST
                # ------------------------------------------

                if low <= sl_adj <= high:

                    exit_price = sl_adj

                    if trade == 1:
                        exit_price -= spread / 2.0
                    else:
                        exit_price += spread / 2.0

                    df.at[
                        df.index[i],
                        "position"
                    ] = exit_price * trade

                    dfb_end = exit_price * trade

                    trade_pl = (
                        dfb_end - dfb_st
                    ) * tlvg_st

                    df.at[
                        df.index[i],
                        "trade_pl"
                    ] = trade_pl

                    current_trade.update(
                        {
                            "exit_index": i,
                            "exit_time": df.iloc[i]["timestamp"],
                            "exit_price": exit_price,
                            "exit_reason": "stop",
                            "pnl": trade_pl
                        }
                    )

                    trades.append(current_trade)

                    trade = 0
                    count = 0

                # ------------------------------------------
                # TARGET TEST SECOND
                # ------------------------------------------

                elif low <= lmt_st <= high:

                    exit_price = lmt_st

                    if trade == 1:
                        exit_price -= spread / 2.0
                    else:
                        exit_price += spread / 2.0

                    df.at[
                        df.index[i],
                        "position"
                    ] = exit_price * trade

                    dfb_end = exit_price * trade

                    trade_pl = (
                        dfb_end - dfb_st
                    ) * tlvg_st

                    df.at[
                        df.index[i],
                        "trade_pl"
                    ] = trade_pl

                    current_trade.update(
                        {
                            "exit_index": i,
                            "exit_time": df.iloc[i]["timestamp"],
                            "exit_price": exit_price,
                            "exit_reason": "target",
                            "pnl": trade_pl
                        }
                    )

                    trades.append(current_trade)

                    trade = 0
                    count = 0

            # ----------------------------------------------
            # Legacy realised P&L accounting
            # ----------------------------------------------

            df.at[
                df.index[i],
                "total_pl"
            ] = (
                df.iloc[i]["trade_pl"]
                + df.iloc[i - 1]["total_pl"]
            )

            df.at[
                df.index[i],
                "total_fund"
            ] = (
                df.iloc[i]["trade_pl"]
                + df.iloc[i - 1]["total_fund"]
            )

        trades_df = pd.DataFrame(trades)

        return {
            "data": df,
            "trades": trades_df,
            "final_balance": df.iloc[-1]["total_fund"],
            "total_profit": df.iloc[-1]["total_pl"]
        }