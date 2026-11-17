# -*- coding: utf-8 -*-
"""
Created on Sat Apr  9 21:22:41 2022

@author: quant
"""

import pandas as pd
import numpy as np
import pandas_ta as ta
#import datetime as dt
#import quantstats as qs
import time
#from numba import jit
#from tqdm import tqdm
#from multiprocessing import Pool


#############################################
#------------> HyperParameters
#############################################
fund_st = 30000
mgn_rq = 0.0334
fund_mgn = 0.9
#################  --->  spread = 0.6 note; spread is set in the data prep via recalc'd bid/offer close prices
#fnd_loss_cap = 0.02
cndl_t = 5
#tgt_fctr = 15
#sl_fctr = 3
#brkeven_fctr = 3
#global sl_adj
daily_bps_tgt = 2

#############################################
#--------> Optimization Parameter Grid
#############################################
df1 = pd.read_csv('PGrid_csv_out_sample20.csv')

sim_id = np.array(df1['sim_id'])
fnd_loss_cap = np.array(df1['fnd_loss_cap'])
tgt_fctr = np.array(df1['tgt_fctr'])
sl_fctr = np.array(df1['sl_fctr'])
brkeven_fctr = np.array(df1['brkeven_fctr'])
tenkan = np.array(df1['tenkan'])
kijun = np.array(df1['kijun'])
senkou = np.array(df1['senkou'])
rsi_period = np.array(df1['rsi_period'])
rsi_ubound = np.array(df1['rsi_ubound'])
rsi_lbound = np.array(df1['rsi_lbound'])
adx_period = np.array(df1['adx_period'])
adx_ubound = np.array(df1['adx_ubound'])
atr_period = np.array(df1['atr_period'])
stoch_k = np.array(df1['stoch_k'])
stoch_d = np.array(df1['stoch_d'])
stoch_slowp = np.array(df1['stoch_slowp'])
stoch_ma_type = np.array(df1['stoch_ma_type'])
stoch_ubound = np.array(df1['stoch_ubound'])
stoch_lbound = np.array(df1['stoch_lbound'])


############################################
#--------------> Load Data:
############################################
def load_data(csv):
    df2 = pd.read_csv(csv)
    df2 = pd.read_csv('USDJPY_1M_MID_mt5_200622_240622.csv')
    del df2[df2.columns[0]]
    return df2


############################################
#---------> Calculate Indicators:
############################################
def calc_inds(sim_no):
#    sim_no = 0
    df2.ta.ema(close='Close', length=6, append=True)
    df2.ta.ema(close='Close', length=7, append=True)
    df2['MACD'] = df2['EMA_6'] - df2['EMA_7']
    df2.ta.sma(close='MACD', length=7, append=True)
    df2['SMA_7'] = df2['SMA_7'] / 100
    df2['grad_t1'] = (df2['SMA_7'] - df2['SMA_7'].shift(1)) * 1000
    
#    df2.ta.macd(close='Close', fast=6, slow=7, signal=7, append=True)
    df2.ta.rsi(length=14, scalar=100, drift=None, append=True)
#    df2.ta.stochrsi(length=3, rsi_length=3, k=5, d=3, append=True)
    df2.ta.atr(length=7, drift=1, append=True)

    df2['Daily_Window'] = 0
    df2['Daily_Window'] = 60 * df2['Hour'] + df2['Min']  

############################################
#-----------> Generate Signals:
############################################
### S1 ### limit hours of trading [+adjustment for London to Moscow time]
#/////////////////////// NEED TO ACCOUNT FOR DAYLIGHT SAVING ??????????????????????????

def signals(sim_no):    
    ### S1 ### trading hours limit
    df2['S1'] = np.where((df2['Hour'] >= 3) & (df2['Hour'] < 20), 1, 0)
                        
    ### S2 ### change in signal line gradient
    df2['S2'] = 0
    df2['S2'] = np.where(((df2['grad_t1'].shift(1) <= 0) & (df2['grad_t1'] > 0)), 1, 0)
    df2['S2'] = np.where(((df2['grad_t1'].shift(1) >= 0) & (df2['grad_t1'] < 0)), -1, df2['S2'])
    
    ### S3 ### RSI is above/below 50 (hardcoded)
    df2['S3'] = 0
    df2['S3'] = np.where((df2['RSI_14'] >= 60) & (df2['S2'] == 1) |\
                         (df2['RSI_14'] <= 40) & (df2['S2'] == -1), 1, 0)
    
    ### S4 ### absolute signal line > 0.002
    df2['S4'] = 0
    df2['S4'] = np.where(abs(df2['SMA_7']) >= 0.002, 1, 0)
        
        ### S10 ### to avoid entering on large 'spikes', limit entry to where candle body moved < (hardcoded factor) x ATR
#    df2['S10'] = 0
#    df2['S10'] = np.where(abs(df2['Open'] - df2['Close']) > (2.0 * df2['ATRr_7']), 0, 1)
    
    
    ### Entry signal when all above conditions are met (-1 for short position; +1 for long position; dependant on RSI)
    df2['entry_flag'] = df2['S1'] * df2['S2'] * df2['S4']
    
    ### Calculate stop loss and limit to apply
#    df2['stop_loss'] = abs(df2['entry_flag']) * (df2['Close'] - df2['entry_flag'] * df2['ATRr_7'] * sl_fctr[sim_no])
#    df2['target'] = abs(df2['entry_flag']) * (df2['Close'] + df2['entry_flag'] * df2['ATRr_7'] * tgt_fctr[sim_no])
    df2['stop_loss_bps'] = 0    
    df2['stop_loss'] = 0
    df2['stop_loss_bps'] = np.where((df2['entry_flag'] == 1), df2['Close'] - df2['Low'], df2['stop_loss'])
    df2['stop_loss_bps'] = np.where((df2['entry_flag'] == -1), df2['High'] - df2['Close'], df2['stop_loss'])
    df2['stop_loss'] = np.where((df2['entry_flag'] == 1), df2['Low'], df2['stop_loss'])
    df2['stop_loss'] = np.where((df2['entry_flag'] == -1), df2['High'], df2['stop_loss'])
    df2['target_bps'] = 0
    df2['target'] = 0
    df2['target_bps'] = np.where((df2['entry_flag'] == 1), (df2['Close'] - df2['Low']) * 2.5, df2['target'])
    df2['target_bps'] = np.where((df2['entry_flag'] == -1), (df2['High'] - df2['Close']) * 2.5, df2['target'])
    df2['target'] = np.where((df2['entry_flag'] == 1), (df2['Close'] - df2['Low']) * 2.5 + df2['Close'], df2['target'])
    df2['target'] = np.where((df2['entry_flag'] == -1), df2['Close'] - (df2['High'] - df2['Close']) * 2.5, df2['target'])
                             
                             
def backtest(sim_no):
#    df2['ATRr_7'] = df2['ATRr_7'].fillna(0.00001)
    df2['max_lvg'] = 0.00
    df2['trd_lvg'] = 0.00
    df2['position'] = 0.00
    df2['sl_adj'] = 0.00
    df2['trade_pl'] = 0
    df2['trade_bps'] = 0
    df2['total_pl'] = 0
    df2['cum_dpl_bps'] = 0
    df2['total_fund'] = fund_st
    trade = 0
    sl_st = 0
    
    
    eflag = np.array(df2['entry_flag'])
    low = np.array(df2['Low'])
    high = np.array(df2['High'])
    sl = np.array(df2['stop_loss'])
    sl_bps = np.array(df2['stop_loss_bps'])
    lmt = np.array(df2['target'])
#    atr = np.array(df2['ATRr_7'])
    spread = np.array(df2['spread']) / 10
    close = np.array(df2['Close'])
    total_fund = np.array(df2['total_fund'])
    total_pl = np.array(df2['total_pl'])
    mxl = np.array(df2['max_lvg'])
    trdlvg = np.array(df2['trd_lvg'])
    position = np.array(df2['position'])
#    sl_trailing = np.array(df2['sl_adj'])
    trade_pl = np.array(df2['trade_pl'])
    trade_bps = np.array(df2['trade_bps'])
    cum_dpl_bps = np.array(df2['cum_dpl_bps'])
    d_window = np.array(df2['Daily_Window'])
    
    for i in range(0, len(high)):
        if i == 0:
            mxl[i] = fund_st * fund_mgn / (mgn_rq * close[i])
            trdlvg[i] = min((total_fund[i] * fnd_loss_cap[sim_no]) / (sl_bps[i]), mxl[i])
        else:
            mxl[i] = total_fund[i-1] * fund_mgn / (mgn_rq * close[i])
            trdlvg[i] = min((total_fund[i-1] * fnd_loss_cap[sim_no]) / (sl_bps[i]), mxl[i])
        
        #entry
        if (trade == 0) & (eflag[i] != 0):
            if eflag[i] == 1:
                close[i] = close[i] + spread[i]/2
            else:
                close[i] = close[i] - spread[i]/2
            position[i] = eflag[i] * close[i]
            dfb_st = eflag[i] * close[i]
            lmt_st = lmt[i]
            sl_st = sl[i]
#            atr_st = atr[i]
            tlvg_st = trdlvg[i]
#            spread_st = spread[i]
            trade = eflag[i]
#            count = 1
        #exit
        elif (trade != 0):  
            #check if stop loss triggered
            if (sl_st >= low[i]) & (sl_st <= high[i]):
                if trade == 1:
                    sl_st = sl_st - spread[i]/2
                else:
                    sl_st = sl_st + spread[i]/2
                position[i] = sl_st * trade
                dfb_end = sl_st * trade
                trade_pl[i] = (dfb_end - dfb_st) * tlvg_st
#                trade_bps[i] = (dfb_end - dfb_st) / tlvg_st
                trade = 0
#                sl_dfb = 0
#                lmt_dfb = 0
#                count = 0
            elif (lmt_st >= low[i]) & (lmt_st <= high[i]):
                if trade == 1:
                    lmt_st = lmt_st - spread[i]/2
                else:
                    lmt_st = lmt_st + spread[i]/2
                position[i] = lmt_st * trade
                dfb_end = lmt_st * trade
                trade_pl[i] = (dfb_end - dfb_st) * tlvg_st
#                trade_bps[i] = (dfb_end - dfb_st) / tlvg_st
                trade = 0
#                sl_dfb = 0
#                lmt_dfb = 0
#                count = 0
    
        if i == 0:
            total_pl[i] = 0
            total_fund[i] = fund_st
        else:
            total_pl[i] = trade_pl[i] + total_pl[i-1]
            total_fund[i] = trade_pl[i] + total_fund[i-1]
        
        if trade_pl[i] != 0:
            trade_bps[i] = trade_pl[i] / tlvg_st
        else:
            pass
        
        if d_window[i] == 0:
            cum_dpl_bps[i] = 0
        else:
            cum_dpl_bps[i] = cum_dpl_bps[i-1] + trade_bps[i]
        
    #write all 'updated' arrays back to dataframe
    df2['max_lvg'] = mxl
    df2['trd_lvg'] = trdlvg
    df2['position'] = position
    df2['trade_pl'] = trade_pl
    df2['trade_bps'] = trade_bps
    df2['total_fund'] = total_fund
    df2['total_pl'] = total_pl
    df2['cum_dpl_bps'] = cum_dpl_bps
    
#    df2['sl_adj'] = sl_trailing
#   df2.drop(index=df2.index[-1], axis=0, inplace=True)
#    df3 = df2[df2['position'] != 0]
#   return df3
#testar2 = np.stack((testar, total_fund), axis=1)
#    if sim_no == 0:
#        tf_arr = np.array(total_fund)
#        return tf_arr
#    else:
#        return tf_arr
    return df2  
    

#for i in tqdm (range (0, 10)):
#startTime = time.time()
df2 = load_data('USDJPY_5M_MID_mt5_130622_160622.csv')


def single_run(i):
#for i in range (0, 10):
#    df2 = df2.iloc[:, :10]
    calc_inds(i)
    signals(i)
    backtest(i)
    return df2

startTime = time.time()
single_run(10)
executionTime = (time.time() - startTime)
print('Execution time in seconds: ' + str(executionTime))

df3 = df2[df2['position'] != 0]
    
backtest(1)
