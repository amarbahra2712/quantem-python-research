# -*- coding: utf-8 -*-
import os
"""
Created on Sun Mar 13 12:16:56 2022

MetaTrader 5 - Pepperstone Integration

Ichimoku Strategy - 5MC - USDJPY

@author: quant
"""

import MetaTrader5 as mt5
import pandas as pd
import pandas_ta as ta
import datetime as dt
import time
import numpy as np
import schedule
import logging


############################################
#---> declare variables & parameters:
############################################
acc = os.getenv("MT5_LOGIN", "")
pwd = os.getenv("MT5_PASSWORD", "")
fx_symbol = "USDJPY_SB"
#cndl_time = "M5"
num_bars = 200
mgn_rq = 0.0334
fund_mgn = 0.9
fnd_loss_cap = 0.02
#cndl_t = 5
tgt_fctr = 30
sl_fctr = 5
brkeven_fctr = 5


############################################
#-------> Logging Set Up:
############################################
logging.basicConfig(
    format='%(asctime)s %(levelname)-8s %(message)s',
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S')

############################################
#-------> Define Admin functions:
############################################
def connect(acc):
    acc = int(acc)
    
    if not if not mt5.initialize(login=acc, password=pwd, server=os.getenv("MT5_SERVER", "")):
        print("Failed to connect at account #{}, error code: {}".format(acc, mt5.last_error()))
        quit()
    else:
        print("MetaTrader5 package author: ",mt5.__author__)
        print("MetaTrader5 package version: ",mt5.__version__)
        print("Authorized: Connected to MT5 Client")

def shutdown():
    mt5.shutdown()
    print("MT5 Client successfully shutdown")
    
def get_fund_bal():
    account_info=mt5.account_info()
    if account_info!=None:
        fund_bal = getattr(account_info, 'balance')
#        print('Balance: ', fund_bal)
        return fund_bal
    else:
        pass
#        print("failed to connect to trade account, error code =",mt5.last_error())
        


############################################
#----------> Execute Order:
############################################
def open_position(pair, order_type, size, tp_distance=None, stop_distance=None):
    symbol_info = mt5.symbol_info(pair)
    if symbol_info is None:
        print(pair, "not found")
        return

    if not symbol_info.visible:
        print(pair, "is not visible, trying to switch on")
        if not mt5.symbol_select(pair, True):
            print("symbol_select({}}) failed, exit",pair)
            return
    print(pair, "found!")

#    point = symbol_info.point
    
    if(order_type == "BUY"):
        order = mt5.ORDER_TYPE_BUY
        price = mt5.symbol_info_tick(pair).ask
        if(stop_distance):
            sl = stop_distance / 100
        if(tp_distance):
            tp = tp_distance / 100
            
    if(order_type == "SELL"):
        order = mt5.ORDER_TYPE_SELL
        price = mt5.symbol_info_tick(pair).bid
        if(stop_distance):
            sl = stop_distance / 100
        if(tp_distance):
            tp = tp_distance * 100

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": pair,
        "volume": float(size),
        "type": order,
        "price": price,
        "sl": sl,
        "tp": tp,
        "magic": 234000,
        "comment": "PythonAlgo - QC Beta Fund",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(request)

    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print("Failed to send order :(")
    else:
        print('time: ', dt.now())
        print ("Order successfully executed!")
        print('----------\n')
        print("1. order_send(): by {} {} lots at {} with deviation={} points".format(pair,float(size),price,0));
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            print("2. order_send failed, retcode={}".format(result.retcode))
            # request the result as a dictionary and display it element by element
            result_dict=result._asdict()
            for field in result_dict.keys():
                print("   {}={}".format(field,result_dict[field]))
                # if this is a trading request structure, display it element by element as well
                if field=="request":
                    traderequest_dict=result_dict[field]._asdict()
                    for tradereq_filed in traderequest_dict:
                        print("       traderequest: {}={}".format(tradereq_filed,traderequest_dict[tradereq_filed]))



############################################
#-------> Get Open Ticket ID:
############################################
def ticketID_get():
    res = mt5.positions_get()
    if (res is not None and res !=()):
        res_df = pd.DataFrame(list(res),columns=res[0]._asdict().keys())
        res_df['time'] = pd.to_datetime(res_df['time'], unit='s')
        ticketID = res_df['ticket'].iat[-1]
        return int(ticketID)
    return pd.DataFrame()



############################################
#-------> Amend Stop Loss Level:
############################################
def amend_sl(pair, ID, new_sl):
    pos_info = mt5.positions_total()
    if pos_info == 0:
        print(pos_info, "open position not found")
        return
    else:
        print(pos_info, "position found")

#    point = symbol_info.point

    request = {
        "action": mt5.TRADE_ACTION_SLTP,
        "position": ID,
        "symbol": pair,
        "sl": new_sl / 100,
        "magic": 234000,
        "comment": "PythonAlgo - QC Beta Fund",
    }

    result = mt5.order_send(request)

    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print("Failed to amend stop loss :(")
    else:
        print('time: ', dt.now())
        print ("Stop successfully amended!")
        print('----------\n')
        print("1. order_send(): by {} with ticket {} SL adjusted to {} with deviation={} points".format(pair,ID,new_sl/100,0));
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            print("2. order_send failed, retcode={}".format(result.retcode))
            # request the result as a dictionary and display it element by element
            result_dict=result._asdict()
            for field in result_dict.keys():
                print("   {}={}".format(field,result_dict[field]))
                # if this is a trading request structure, display it element by element as well
                if field=="request":
                    traderequest_dict=result_dict[field]._asdict()
                    for tradereq_filed in traderequest_dict:
                        print("       traderequest: {}={}".format(tradereq_filed,traderequest_dict[tradereq_filed]))



############################################
#-----------> Read OHLC Data:
############################################
def dSTREAM(symbol, num_bars):
    
    bars = mt5.copy_rates_from_pos(fx_symbol, mt5.TIMEFRAME_M5, 1, num_bars)
    # create DataFrame out of the obtained data
    df_bars = pd.DataFrame(bars)
    # convert time in seconds into the datetime format
    df_bars['time']=pd.to_datetime(df_bars['time'], unit='s')
    
    #insert hour/min columns and reformatting of dataframe
    df_bars.insert(1, 'MoscowDateTime', df_bars['time'].astype('string'))
    df_bars['MoscowDateTime'] = pd.to_datetime(df_bars['MoscowDateTime'],format='%Y-%m-%d %H:%M:%S')
    df_bars.insert(2, 'LondonTimeDLS', 0)
    df_bars['LondonTimeDLS'] = np.where((df_bars['MoscowDateTime'].dt.month >= 4) & (df_bars['MoscowDateTime'].dt.month <= 10), 2, 3)
    df_bars['time'] = np.where((df_bars['LondonTimeDLS'] == 3), df_bars['MoscowDateTime'] - dt.timedelta(hours=3), df_bars['MoscowDateTime'] - dt.timedelta(hours=2))
    df_bars.insert(3, 'Hour', pd.to_datetime(df_bars['time']).dt.strftime('%H'))
    df_bars.insert(4, 'Min', pd.to_datetime(df_bars['time']).dt.strftime('%M'))
    df_bars['Hour'] = df_bars['Hour'].astype(int)
    df_bars['Min'] = df_bars['Min'].astype(int)
    df_bars.insert(5, 'Day', df_bars['time'].astype('string'))
    df_bars['Day'] = df_bars['Day'].str[:-3]
    df_bars['Day'] = pd.to_datetime(df_bars['Day'],format='%Y.%m.%d %H:%M')
    df_bars['Day'] = df_bars['Day'].dt.day_name()
    df_bars.rename(columns={'open': 'Open'}, inplace=True)
    df_bars.rename(columns={'high': 'High'}, inplace=True)
    df_bars.rename(columns={'low': 'Low'}, inplace=True)
    df_bars.rename(columns={'close': 'Close'}, inplace=True)
    df_bars['Open'] = df_bars['Open'] * 100
    df_bars['High'] = df_bars['High'] * 100
    df_bars['Low'] = df_bars['Low'] * 100
    df_bars['Close'] = df_bars['Close'] * 100



############################################
#---------> Calculate Indicators:
############################################
    df_bars.ta.ichimoku(tenkan=9, kijun=26, senkou=52, include_chikou=True, offset=None, append=True)
    df_bars['TKS_delta'] = abs(df_bars['ITS_9'] - df_bars['IKS_26'])
    
    df_bars.ta.rsi(length=14, scalar=100, drift=None, append=True)
    df_bars.ta.stochrsi(length=3, rsi_length=3, k=5, d=3, append=True)
    df_bars.ta.atr(length=7, drift=1, append=True)
    df_bars.ta.adx(length=7, drift=1, append=True)
    
    df_bars['fK'] = (df_bars['Close'] - (df_bars['Low'].rolling(5).min()))/(df_bars['High'].rolling(5).max() - df_bars['Low'].rolling(5).min()) * 100
    df_bars['sK'] = ta.sma(df_bars.fK, length=3)
    df_bars['D'] = ta.sma(df_bars.sK, length=3)



############################################
#-----------> Generate Signals:
############################################
    
    df_bars['S1'] = np.where((df_bars['Hour'] >= 3) & (df_bars['Hour'] < 20) & (df_bars['Day'] != "S?"), 1, 0)
    
    ### S2 ### long break of Ichimoku Cloud  
    df_bars['S2'] = 0
    df_bars['S2L'] = np.where((df_bars['Open'] <= df_bars[['ISA_9', 'ISB_26']].max(axis=1)) & (df_bars['Close'] > df_bars[['ISA_9', 'ISB_26']].max(axis=1)), 1, 0)
    df_bars['S2S'] = np.where((df_bars['Open'] >= df_bars[['ISA_9', 'ISB_26']].min(axis=1)) & (df_bars['Close'] < df_bars[['ISA_9', 'ISB_26']].min(axis=1)), -1, 0)
    df_bars['S2'] = df_bars['S2L'] + df_bars['S2S']
    
    ### S3 ### Tenkan crossed Kijin
    df_bars['S3'] = np.where((df_bars['ITS_9'] >= df_bars['IKS_26']) & (df_bars['S2'] == 1) |\
                         (df_bars['ITS_9'] <= df_bars['IKS_26']) & (df_bars['S2'] == -1), 1, 0)
            
    ### S4 ### Chikou above/below min/max Cloud(-26 periods???)    ### CHECK ##
    df_bars['S4'] = 0
    df_bars['MaxAB_L'] = np.where(df_bars['ISA_9'] >= df_bars['ISB_26'], df_bars['ISA_9'], df_bars['ISB_26'])
    df_bars['MinAB_S'] = np.where(df_bars['ISA_9'] <= df_bars['ISB_26'], df_bars['ISA_9'], df_bars['ISB_26'])
    df_bars['S4'] = np.where((df_bars['ICS_26'].shift(26) > df_bars['MaxAB_L'].shift(26)) & (df_bars['S2'] == 1) |\
                         (df_bars['ICS_26'].shift(26) < df_bars['MinAB_S'].shift(26)) & (df_bars['S2'] == -1), 1, 0)
    
    ### S5 ### RSI (u<x<l)
    df_bars['S5'] = np.where((df_bars['sK'] > 70) & (df_bars['S2'] == 1) |\
                         (df_bars['sK'] < 30) & (df_bars['S2'] == -1), 0, 1)
    
    ### S6 ### ADX (>x)
    df_bars['S6'] = np.where((df_bars['ADX_7'] > 25), 1, 0)
    
    ### S7 ### where Stoch slowK > Stoch D for long (vice versa for short)
    df_bars['S7'] = np.where((df_bars['sK'] > df_bars['D']) & (df_bars['S2'] == 1) |\
                         (df_bars['sK'] < df_bars['D']) & (df_bars['S2'] == -1), 1, 0)
    
    ### S8 ### RSI is above/below bounds for long/short (60/40 hardcoded)
    df_bars['S8'] = np.where((df_bars['RSI_14'] >= 60) & (df_bars['S2'] == 1) |\
                         (df_bars['RSI_14'] <= 40) & (df_bars['S2'] == -1), 1, 0)
    
    ### S9 ### (additional condition on Tenkan/Kijun) where absolute delta !> (hardcoded factor) x ATR
    df_bars['S9'] = np.where((df_bars['TKS_delta'] <= (2.0 * abs(df_bars['Open'] - df_bars['Close']))), 1, 0)
    
    ### S10 ### to avoid entering on large 'spikes', limit entry to where candle body moved < (hardcoded factor) x ATR
    df_bars['S10'] = np.where(abs(df_bars['Open'] - df_bars['Close']) > (2.0 * df_bars['ATRr_7']), 0, 1)
    
    ### S11 ### Chikou above/below price for L/S entry respectively
    df_bars['S11'] = np.where((df_bars['ICS_26'].shift(26) > df_bars['High'].shift(26)) & (df_bars['S2'] == 1) |\
                         (df_bars['ICS_26'].shift(26) < df_bars['Low'].shift(26)) & (df_bars['S2'] == -1), 1, 0)

    
    ### Entry signal when all above conditions are met (-1 for short position; +1 for long position; dependant on RSI)
    df_bars['entry_flag'] = df_bars['S1'] * df_bars['S2'] * df_bars['S3'] * df_bars['S4'] * df_bars['S5'] * df_bars['S6'] * df_bars['S7'] * df_bars['S8'] * df_bars['S9'] * df_bars['S10'] * df_bars['S11']


    
#########################################
#-----> Calculate SL and Target
#########################################

    df_bars['stop_loss'] = abs(df_bars['entry_flag']) * (df_bars['Close'] - df_bars['entry_flag'] * df_bars['ATRr_7'] * 5)
    df_bars['target'] = abs(df_bars['entry_flag']) * (df_bars['Close'] + df_bars['entry_flag'] * df_bars['ATRr_7'] * 30)
    
    df_bars = pd.DataFrame(df_bars)
    return df_bars
    
#########################################
#--------> Write to log file
#########################################
def log_df():
    df_bars.iloc[-1:].to_csv('signal_log.csv', index=False, header=False, mode='a')
    logging.info('LOG: Created;  STATUS: Running...')
#    terminal_out = df_bars.iloc[-1:]
#    print(terminal_out)
        

def algo_trader():
    
    eflag = df_bars['entry_flag'].iat[-1]
    low = df_bars['Low'].iat[-1]
    high = df_bars['High'].iat[-1]
    sl = df_bars['stop_loss'].iat[-1]
    lmt = df_bars['target'].iat[-1]
    atr = df_bars['ATRr_7'].iat[-1]
    spread = df_bars['spread'].iat[-1] / 10
    close = df_bars['Close'].iat[-1]

    
    #calculate max and trade leverage
    mxl = get_fund_bal() * fund_mgn / (mgn_rq * close * 100)
    trdlvg = min((get_fund_bal() * fnd_loss_cap) / (atr * 100 * sl_fctr), mxl)
    lot_size = max(int(trdlvg), 0.01)
    
    #check if position open and set trade variable
    if mt5.positions_total() == 0:
        trade = 0
        count = 0
        SL1 = 0
        SL2 = 0
#        pos_eflag = 0
    else:
        pass
        
    #entry
    if (trade == 0) & (eflag != 0):
        if eflag == 1:
            open_position(fx_symbol, 'BUY', lot_size, tp_distance=lmt, stop_distance=sl)
        else:
            open_position(fx_symbol, 'SELL', lot_size, tp_distance=lmt, stop_distance=sl)
#        lmt_st = lmt
        sl_st = sl
        atr_st = atr
#        tlvg_st = trdlvg
        spread_st = spread
        trade = eflag
        count = 1
    #exit
    elif (trade != 0):
        #adjust stop loss for breakeven (+bps on large move) when possible
        if count == 1:
            sl_adj = sl_st
            sl_max = sl_st
            sl_min = sl_st
            SL1 = 0
            SL2 = 0
        if trade == 1:
            if high >= sl_st + atr_st * (sl_fctr + 10):
                sl_adj = sl_st + atr_st * sl_fctr + 4 + spread_st
                sl_max = max(sl_adj, sl_max)
                SL2 += 1
            elif high >= sl_st + atr_st * (sl_fctr + brkeven_fctr):
                sl_adj = sl_st + atr_st * sl_fctr + spread_st
                sl_max = max(sl_adj, sl_max)
                SL1 += 1
            else:
                sl_adj = max(sl_st, sl_max)
        elif trade == -1:
            if low <= sl_st - atr_st * (sl_fctr + 10):
                sl_adj = sl_st - atr_st * sl_fctr - 4 - spread_st
                sl_min = min(sl_adj, sl_min)
                SL2 += 1
            elif low <= sl_st - atr_st * (sl_fctr + brkeven_fctr):
                sl_adj = sl_st - atr_st * sl_fctr - spread_st
                sl_min = min(sl_adj, sl_min)
                SL1 += 1
            else:
                sl_adj = min(sl_st, sl_min)
        count += 1
        
        if SL1 == 1 or SL2 == 1:
            amend_sl(fx_symbol, ticketID_get(), sl_adj)
        else:
            pass
    logging.info(f'POSITION STATUS: {trade}')
        
def cerebro():
    global df_bars
    df_bars = dSTREAM(fx_symbol, num_bars)
    log_df()
    algo_trader()

    
connect(acc)
schedule.every(5).minutes.at(":02").do(cerebro)
while True:
    schedule.run_pending()
    time.sleep(1)
