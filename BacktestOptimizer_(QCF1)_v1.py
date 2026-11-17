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
from tqdm import tqdm
from multiprocessing import Pool


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
    df2['TKS_delta'] = abs(df2['ITS_9'] - df2['IKS_26'])
    df2.ta.rsi(length=rsi_period[sim_no], scalar=100, drift=None, append=True)
    df2.ta.stochrsi(length=3, rsi_length=3, k=5, d=3, append=True)
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
    df2['S1'] = np.where((df2['Hour'] >= 3) & (df2['Hour'] < 20), 1, 0)
    
    ### S2 ### long break of Ichimoku Cloud  
    df2['S2'] = 0
    df2['S2L'] = 0
    df2['S2S'] = 0
    df2['S2L'] = np.where((df2['Open'] <= df2[['ISA_9', 'ISB_26']].max(axis=1)) & (df2['Close'] > df2[['ISA_9', 'ISB_26']].max(axis=1)), 1, 0)
    df2['S2S'] = np.where((df2['Open'] >= df2[['ISA_9', 'ISB_26']].min(axis=1)) & (df2['Close'] < df2[['ISA_9', 'ISB_26']].min(axis=1)), -1, 0)
    df2['S2'] = df2['S2L'] + df2['S2S']
    
    ### S3 ### Tenkan crossed Kijin                                                                                             
    df2['S3'] = 0
    df2['S3'] = np.where((df2['ITS_9'] >= df2['IKS_26']) & (df2['S2'] == 1) |\
                         (df2['ITS_9'] <= df2['IKS_26']) & (df2['S2'] == -1), 1, 0)
            
    ### S4 ### Chikou above/below min/max Cloud(-26 periods???)    ### CHECK ###                                                                                   
    df2['S4'] = 0
    df2['MaxAB_L'] = np.where(df2['ISA_9'] >= df2['ISB_26'], df2['ISA_9'], df2['ISB_26'])
    df2['MinAB_S'] = np.where(df2['ISA_9'] <= df2['ISB_26'], df2['ISA_9'], df2['ISB_26'])
    df2['S4'] = np.where((df2['ICS_26'].shift(kijun[sim_no]) > df2['MaxAB_L'].shift(kijun[sim_no])) & (df2['S2'] == 1) |\
                         (df2['ICS_26'].shift(kijun[sim_no]) < df2['MinAB_S'].shift(kijun[sim_no])) & (df2['S2'] == -1), 1, 0)
    
    ### S5 ### RSI (u<x<l)
    df2['S5'] = 0
    df2['S5'] = np.where((df2['sK'] > rsi_ubound[sim_no]) & (df2['S2'] == 1) |\
                         (df2['sK'] < rsi_lbound[sim_no]) & (df2['S2'] == -1), 0, 1)
    
    ### S6 ### ADX (>x)
    df2['S6'] = 0
    df2['S6'] = np.where((df2['ADX_7'] > adx_ubound[sim_no]), 1, 0)
    
    ### S7 ### where Stoch slowK > Stoch D for long (vice versa for short)
    df2['S7'] = 0
    df2['S7'] = np.where((df2['sK'] > df2['D']) & (df2['S2'] == 1) |\
                         (df2['sK'] < df2['D']) & (df2['S2'] == -1), 1, 0)
    
    ### S8 ### RSI is above/below bounds for long/short (60/40 hardcoded)
    df2['S8'] = 0
    df2['S8'] = np.where((df2['RSI_14'] >= 60) & (df2['S2'] == 1) |\
                         (df2['RSI_14'] <= 40) & (df2['S2'] == -1), 1, 0)
    
    ### S9 ### (additional condition on Tenkan/Kijun) where absolute delta !> (hardcoded factor) x ATR
    df2['S9'] = 0
    df2['S9'] = np.where((df2['TKS_delta'] <= (2.0 * abs(df2['Open'] - df2['Close']))), 1, 0)
    
    ### S10 ### to avoid entering on large 'spikes', limit entry to where candle body moved < (hardcoded factor) x ATR
    df2['S10'] = 0
    df2['S10'] = np.where(abs(df2['Open'] - df2['Close']) > (2.0 * df2['ATRr_7']), 0, 1)
    
    ### S11 ### Chikou above/below price for L/S entry respectively
    df2['S11'] = 0
    df2['S11'] = np.where((df2['ICS_26'].shift(kijun[sim_no]) > df2['High'].shift(kijun[sim_no])) & (df2['S2'] == 1) |\
                         (df2['ICS_26'].shift(kijun[sim_no]) < df2['Low'].shift(kijun[sim_no])) & (df2['S2'] == -1), 1, 0)

    
    ### Entry signal when all above conditions are met (-1 for short position; +1 for long position; dependant on RSI)
    df2['entry_flag'] = df2['S1'] * df2['S2'] * df2['S3'] * df2['S4'] * df2['S5'] * df2['S6'] * df2['S7'] * df2['S8'] * df2['S9'] * df2['S10'] * df2['S11']
#    df2['entry_flag'] = df2['S1'] * df2['S2'] * df2['S3'] * df2['S5'] * df2['S6'] * df2['S7'] * df2['S8'] * df2['S9'] * df2['S10'] * df2['S11']
    
    ### Calculate stop loss and limit to apply
    df2['stop_loss'] = abs(df2['entry_flag']) * (df2['Close'] - df2['entry_flag'] * df2['ATRr_7'] * sl_fctr[sim_no])
#    df2['stop_loss'] = np.where((df2['entry_flag'] == 1), df2['Close'] - df2['ATRr_7'] * sl_fctr[sim_no], 0)
#    df2['stop_loss'] = np.where((df2['entry_flag'] == -1), df2['Close'] + df2['ATRr_7'] * sl_fctr[sim_no], 0)
    df2['target'] = abs(df2['entry_flag']) * (df2['Close'] + df2['entry_flag'] * df2['ATRr_7'] * tgt_fctr[sim_no])
#    df2['target'] = np.where((df2['entry_flag'] == 1), df2['Close'] + df2['ATRr_7'] * tgt_fctr[sim_no], 0)
#    df2['target'] = np.where((df2['entry_flag'] == -1), df2['Close'] - df2['ATRr_7'] * tgt_fctr[sim_no], 0)
    
#def bt_setup():
    
#@jit(nopython=True, nogil=True)
def backtest(sim_no):
    df2['ATRr_7'] = df2['ATRr_7'].fillna(0.00001)
    df2['max_lvg'] = 0.00
    df2['trd_lvg'] = 0.00
    df2['position'] = 0.00
    df2['sl_adj'] = 0.00
    df2['trade_pl'] = 0
    df2['total_pl'] = 0
    df2['total_fund'] = fund_st
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
    eDay_fltr = np.array(df2['EndDay_fltr'])
    span_a = np.array(df2['ISA_9'])
    span_b = np.array(df2['ISB_26'])
    chikou = np.array(df2['ICS_26'])
    
    for i in range(0, len(high)):
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
            spread_st = spread[i]
            trade = eflag[i]
            count = 1
        #exit
        elif (trade != 0):
            #adjust stop loss for breakeven (+bps on large move) when possible
            if count == 1:
                sl_adj = sl_st
                sl_max = sl_st
                sl_min = sl_st
            if trade == 1:
                if high[i] >= sl_st + atr_st * (sl_fctr[sim_no] + 10):
                    sl_adj = sl_st + atr_st * sl_fctr[sim_no] + 4 + spread_st
                    sl_max = max(sl_adj, sl_max)
#                elif high[i] >= sl_st + atr_st * (sl_fctr[sim_no] + 10):
#                    sl_adj = sl_st + atr_st * sl_fctr[sim_no] + 3 + spread_st
#                    sl_max = max(sl_adj, sl_max)
                elif high[i] >= sl_st + atr_st * (sl_fctr[sim_no] + brkeven_fctr[sim_no]):
                    sl_adj = sl_st + atr_st * sl_fctr[sim_no] + spread_st
                    sl_max = max(sl_adj, sl_max)
                else:
                    sl_adj = max(sl_st, sl_max)
            elif trade == -1:
                if low[i] <= sl_st - atr_st * (sl_fctr[sim_no] + 10):
                    sl_adj = sl_st - atr_st * sl_fctr[sim_no] - 4 - spread_st
                    sl_min = min(sl_adj, sl_min)
#                elif low[i] <= sl_st - atr_st * (sl_fctr[sim_no] + 10):
#                    sl_adj = sl_st - atr_st * sl_fctr[sim_no] - 3 - spread_st
#                    sl_min = min(sl_adj, sl_min)
                elif low[i] <= sl_st - atr_st * (sl_fctr[sim_no] + brkeven_fctr[sim_no]):
                    sl_adj = sl_st - atr_st * sl_fctr[sim_no] - spread_st
                    sl_min = min(sl_adj, sl_min)
                else:
                    sl_adj = min(sl_st, sl_min)
            count += 1
            sl_trailing[i] = sl_adj
            #check if stop loss triggered
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
            #check if Chikou broken the opposite cloud resistance
#            elif (trade == 1) & (chikou[i-26] <= min(span_a[i-26], span_b[i-26])):
#                    lmt_st = close[i] - spread[i]/2
#                    position[i] = lmt_st * trade
#                    dfb_end = lmt_st * trade
#                    trade_pl[i] = (dfb_end - dfb_st) * tlvg_st
#                    trade = 0
#                    count = 0
#            elif (trade == -1) & (chikou[i-26] >= max(span_a[i-26], span_b[i-26])):
#                    lmt_st = close[i] + spread[i]/2
#                    position[i] = lmt_st * trade
#                    dfb_end = lmt_st * trade
#                    trade_pl[i] = (dfb_end - dfb_st) * tlvg_st
#                    trade = 0
#                    count = 0
            #check if limit triggered
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
        
    
    #write all 'updated' arrays back to dataframe
    df2['max_lvg'] = mxl
    df2['trd_lvg'] = trdlvg
    df2['position'] = position
    df2['trade_pl'] = trade_pl
    df2['total_fund'] = total_fund
    df2['total_pl'] = total_pl
    df2['sl_adj'] = sl_trailing
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
    
