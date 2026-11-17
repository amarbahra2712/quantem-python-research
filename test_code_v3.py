# -*- coding: utf-8 -*-
"""
Created on Sat Apr  9 21:22:41 2022

@author: quant
"""

import pandas as pd
import numpy as np
import pandas_ta as ta
import datetime as dt
import quantstats as qs
import time
from numba import jit



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

#############################################
#--------> Optimization Parameter Grid
#############################################
df1 = pd.read_csv('PGrid_csv_out.csv')

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
    del df2[df2.columns[0]]
    return df2

#load_data('USDJPY_5M_MID_mt5_040121_010422.csv')
############################################
#---------> Calculate Indicators:
############################################
def calc_inds(sim_no):
#    sim_no = 0
    df2.ta.ichimoku(tenkan=tenkan[sim_no], kijun=kijun[sim_no], senkou=senkou[sim_no], include_chikou=True, offset=None, append=True)
    #df2.ta.macd(fast=6, slow=7, signal=7, append=True)
    df2.ta.rsi(length=rsi_period[sim_no], scalar=100, drift=1, append=True)
#    df2.ta.stochrsi(length=3, rsi_length=3, k=5, d=3, append=True)
    df2.ta.atr(length=atr_period[sim_no], drift=1, append=True)
    df2.ta.adx(length=adx_period[sim_no], drift=1, append=True)
    
    df2['fK'] = (df2['Close'] - (df2['Low'].rolling(stoch_k[sim_no]).min()))/(df2['High'].rolling(stoch_k[sim_no]).max() - df2['Low'].rolling(stoch_k[sim_no]).min()) * 100
    df2['sK'] = ta.sma(df2.fK, length=stoch_slowp[sim_no])
    df2['D'] = ta.sma(df2.sK, length=stoch_d[sim_no])
    
    
############################################
#-----------> Generate Signals:
############################################
### S1 ### limit hours of trading [+adjustment for London to Moscow time]
#/////////////////////// NEED TO ACCOUNT FOR DAYLIGHT SAVING ??????????????????????????

def signals(sim_no):    
    df2['S1'] = np.where((df2['Hour'] >= 6+3) & (df2['Hour'] < 20+3), 1, 0)
    
    ### S2 ### long break of Ichimoku Cloud  
    df2['S2'] = 0
    df2['S2'] = np.where((df2['Open'] <= df2[['ISA_9', 'ISB_26']].max(axis=1)) & (df2['Close'] > df2[['ISA_9', 'ISB_26']].max(axis=1)), 1, 0)
    df2['S2'] = np.where((df2['Open'] >= df2[['ISA_9', 'ISB_26']].min(axis=1)) & (df2['Close'] < df2[['ISA_9', 'ISB_26']].min(axis=1)), -1, 0)
    
    ### S3 ### Tenkan crossed Kijin                                                                                             
    df2['S3'] = 0
    df2['S3'] = np.where((df2['ITS_9'] >= df2['IKS_26']) & (df2['S2'] == 1), 1, 0)
    df2['S3'] = np.where((df2['ITS_9'] <= df2['IKS_26']) & (df2['S2'] == -1), 1, 0)
            
    ### S4 ### Chikou above/below price(-26 periods???)    ### CHECK ###                                                                                   
    df2['S4'] = 0
    df2['S4'] = np.where((df2['ICS_26'] > df2['High'].shift(kijun[sim_no])) & (df2['S2'] == 1), 1, 0)
    df2['S4'] = np.where((df2['ICS_26'] < df2['Low'].shift(kijun[sim_no])) & (df2['S2'] == -1), 1, 0)
    
    ### S5 ### RSI (u<x<l)
    df2['S5'] = 0
    df2['S5'] = np.where((df2['sK'] > rsi_ubound[sim_no]) & (df2['S2'] == 1), 0, 1)
    df2['S5'] = np.where((df2['sK'] < rsi_lbound[sim_no]) & (df2['S2'] == -1), 0, 1)
    
    ### S6 ### ADX (>x)
    df2['S6'] = 0
    df2['S6'] = np.where((df2['ADX_7'] > adx_ubound[sim_no]), 1, 0)
    
    ### Entry signal when all above conditions are met (-1 for short position; +1 for long position; dependant on RSI)
    df2['entry_flag'] = df2['S1'] * df2['S2'] * df2['S3'] * df2['S4'] * df2['S5'] * df2['S6']
    
    ### Calculate stop loss and limit to apply
    df2['stop_loss'] = np.where((df2['entry_flag'] == 1), df2['Close'] - df2['ATRr_7'] * sl_fctr[sim_no], 0)
    df2['stop_loss'] = np.where((df2['entry_flag'] == -1), df2['Close'] + df2['ATRr_7'] * sl_fctr[sim_no], 0)
    df2['target'] = np.where((df2['entry_flag'] == 1), df2['Close'] + df2['ATRr_7'] * tgt_fctr[sim_no], 0)
    df2['target'] = np.where((df2['entry_flag'] == -1), df2['Close'] - df2['ATRr_7'] * tgt_fctr[sim_no], 0)
    
def bt_prestep():
    df2['ATRr_7'] = df2['ATRr_7'].fillna(0.00001)
    df2['max_lvg'] = 0
    df2['trd_lvg'] = 0
    df2['position'] = 0
    df2['sl_adj'] = 0
    df2['trade_pl'] = 0
    df2['total_pl'] = 0
    df2['total_fund'] = fund_st
    
@jit(nopython=True, nogil=True)
def backtest(sim_no):
    trade = 0
    sl_st = 0
    
    eflag = np.array(df2['entry_flag'])
    low = np.array(df2['Low'])
    high = np.array(df2['High'])
    sl = np.array(df2['stop_loss'])
    lmt = np.array(df2['target'])
    atr = np.array(df2['ATRr_7'])
    spread = np.array(df2['spread']) / 10
    close = np.array(df2['Close'])
    total_fund = np.array(df2['total_fund'])
    total_pl = np.array(df2['total_pl'])
    mxl = np.array(df2['max_lvg'])
    trdlvg = np.array(df2['trd_lvg'])
    position = np.array(df2['position'])
    sl_trailing = np.array(df2['sl_adj'])
    trade_pl = np.array(df2['trade_pl'])
    for i in range(0, len(high)-1):
        if i == 0:
            mxl[i] = fund_st * fund_mgn / (mgn_rq * close[i])
            trdlvg[i] = min((total_fund[i] * fnd_loss_cap[sim_no]) / (atr[i] * sl_fctr[sim_no]), mxl[i])
        else:
            mxl[i] = total_fund[i-1] * fund_mgn / (mgn_rq * close[i])
            trdlvg[i] = min((total_fund[i-1] * fnd_loss_cap[sim_no]) / (atr[i] * sl_fctr[sim_no]), mxl[i])
        
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
            atr_st = atr[i]
            tlvg_st = trdlvg[i]
            trade = eflag[i]
            count = 1
        elif (trade != 0):
            if count == 1:
                sl_adj = sl_st
            if trade == 1:
                if high[i] >= sl_st + atr_st * (sl_fctr[sim_no] + brkeven_fctr[sim_no]):
                    sl_adj = sl_st + atr_st * sl_fctr[sim_no] + spread[i]
                else:
                    sl_adj = max(sl_st, sl_adj)
            elif trade == -1:
                if low[i] <= sl_st - atr_st * (sl_fctr[sim_no] + brkeven_fctr[sim_no]):
                    sl_adj = sl_st - atr_st * sl_fctr[sim_no] - spread[i]
                else:
                    sl_adj = min(sl_st, sl_adj)
            count += 1
            sl_trailing[i] = sl_adj
            if (sl_adj >= low[i]) & (sl_adj <= high[i]):
                if trade == 1:
                    sl_adj = sl_adj - spread[i]/2
                else:
                    sl_adj = sl_adj + spread[i]/2
                position[i] = sl_adj * trade
                dfb_end = sl_adj * trade
                trade_pl[i] = (dfb_end - dfb_st) * tlvg_st
                trade = 0
#                sl_dfb = 0
#                lmt_dfb = 0
                count = 0
            elif (lmt_st >= low[i]) & (lmt_st <= high[i]):
                if trade == 1:
                    lmt_st = lmt_st - spread[i]/2
                else:
                    lmt_st = lmt_st + spread[i]/2
                position[i] = lmt_st * trade
                dfb_end = lmt_st * trade
                trade_pl[i] = (dfb_end - dfb_st) * tlvg_st
                trade = 0
#                sl_dfb = 0
#                lmt_dfb = 0
                count = 0
    
        if i == 0:
            total_pl[i] = 0
            total_fund[i] = fund_st
        else:
            total_pl[i] = trade_pl[i] + total_pl[i-1]
            total_fund[i] = trade_pl[i] + total_fund[i-1]
    
    return mxl, trdlvg, position, trade_pl, total_pl
        

def bt_poststep():
    #write all 'updated' arrays back to dataframe
    df2['max_lvg'] = mxl
    df2['trd_lvg'] = trdlvg
    df2['position'] = position
    df2['trade_pl'] = trade_pl
    df2['total_fund'] = total_fund
    df2['total_pl'] = total_pl
    
    df3 = df2[df2['position'] != 0]


startTime = time.time()
#for i in range (0,10):
df2 = load_data('USDJPY_5M_MID_mt5_040121_010422.csv')
calc_inds(0)
signals(0)
bt_prestep()
df3 = backtest(0)
#bt_poststep()
executionTime = (time.time() - startTime)
print('Execution time in seconds: ' + str(executionTime))