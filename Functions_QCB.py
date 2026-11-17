# -*- coding: utf-8 -*-
"""
Algo Backtesting script
Strategy C --> Ichimoku Cloud + Technicals
TimeFrames --> 5MC only

entry - Ichi/RSI/ADX/Stoch; exit - ATR factors; high R-R ratio; low SL; breakeven trailing sl
24/03/2022
v1.0
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
#spread = 0.6 note; spread is set in the data prep via recalc'd bid/offer close prices
fnd_loss_cap = 0.02
cndl_t = 5
tgt_fctr = 10
sl_fctr = 3
brkeven_fctr = 3
#global sl_adj

#############################################
#--------> Optimization Parameters
#############################################





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
def calc_inds():
    df2.ta.ichimoku(tenkan=9, kijun=26, senkou=52, include_chikou=True, offset=None, append=True)
    #df2.ta.macd(fast=6, slow=7, signal=7, append=True)
    df2.ta.rsi(length=14, scalar=100, drift=1, append=True)
    df2.ta.stochrsi(length=3, rsi_length=3, k=5, d=3, append=True)
    df2.ta.atr(length=7, drift=1, append=True)
    df2.ta.adx(length=7, drift=1, append=True)
    
    kperiod = 5
    dperiod = 3
    slowperiod = 3
    
    df2['fK'] = (df2['Close'] - (df2['Low'].rolling(kperiod).min()))/(df2['High'].rolling(kperiod).max() - df2['Low'].rolling(kperiod).min()) * 100
    df2['sK'] = ta.sma(df2.fK, length=slowperiod)
    df2['D'] = ta.sma(df2.sK, length=dperiod)
    
    
    ############################################
    #-----------> Generate Signals:
    ############################################
    ### S1 ### limit hours of trading [+adjustment for London to Moscow time]
    #/////////////////////// NEED TO ACCOUNT FOR DAYLIGHT SAVING ??????????????????????????
def signals():    
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
    df2['S4'] = np.where((df2['ICS_26'] > df2['High'].shift(26)) & (df2['S2'] == 1), 1, 0)
    df2['S4'] = np.where((df2['ICS_26'] < df2['Low'].shift(26)) & (df2['S2'] == -1), 1, 0)
    
    ### S5 ### RSI (u<x<l)
    df2['S5'] = 0
    df2['S5'] = np.where((df2['sK'] > 70) & (df2['S2'] == 1), 0, 1)
    df2['S5'] = np.where((df2['sK'] < 30) & (df2['S2'] == -1), 0, 1)
    
    ### S6 ### ADX (>x)
    df2['S6'] = 0
    df2['S6'] = np.where((df2['ADX_7'] > 25), 1, 0)
    
    ### Entry signal when all above conditions are met (-1 for short position; +1 for long position; dependant on RSI)
    df2['entry_flag'] = df2['S1'] * df2['S2'] * df2['S3'] * df2['S4'] * df2['S5'] * df2['S6']
    
    ### Calculate stop loss and limit to apply
    df2['stop_loss'] = np.where((df2['entry_flag'] == 1), df2['Close'] - df2['ATRr_7'] * sl_fctr, 0)
    df2['stop_loss'] = np.where((df2['entry_flag'] == -1), df2['Close'] + df2['ATRr_7'] * sl_fctr, 0)
    df2['target'] = np.where((df2['entry_flag'] == 1), df2['Close'] + df2['ATRr_7'] * tgt_fctr, 0)
    df2['target'] = np.where((df2['entry_flag'] == -1), df2['Close'] - df2['ATRr_7'] * tgt_fctr, 0)
    
#    return df2
df2 = load_data('USDJPY_5M_MID_mt5_040121_010422.csv')
calc_inds()
signals()

        
############################################
#-----> iterative portfolio simulation
############################################
#@jit(nopython=True)
def backtest():
    df2['max_lvg'] = 0
    df2['trd_lvg'] = 0
    df2['position'] = 0
    df2['trade_pl'] = 0
    df2['total_pl'] = 0
    df2['total_fund'] = fund_st
    trade = 0
    sl_st = 0

    
    for i in range(1, len(df2)):
        
        close = df2.loc[i, 'Close']
        bid = df2.loc[i, 'bid_c']
        ask = df2.loc[i, 'ask_c']
        eflag = df2.loc[i, 'entry_flag']
        low = df2.loc[i, 'Low']                                                                                             
        high = df2.loc[i, 'High']
        sl = df2.loc[i, 'stop_loss']
        lmt = df2.loc[i, 'target']
        atr = df2.loc[i, 'ATRr_7']
        tenkan = df2.loc[i, 'ITS_9']
        kinjun = df2.loc[i, 'IKS_26']
        spread = df2.loc[i, 'spread'] / 10
        
        df2.loc[i, 'max_lvg'] = (df2.loc[i - 1, 'total_fund'] * fund_mgn) / (mgn_rq * close) 
        df2.loc[i, 'trd_lvg'] = min((df2.loc[i - 1, 'total_fund'] * fnd_loss_cap) / (atr * sl_fctr), df2.loc[i, 'max_lvg'])
        
    
        #adjust stop loss for trailing loss
#        def breakeven_adj():
#            global sl_adj
#            if count == 1:
#                sl_adj = sl_st
#            if trade == 1:
#                if high >= sl_st + atr_st * (sl_fctr + brkeven_fctr):
#                    sl_adj = sl_st + atr_st * sl_fctr + spread
#                    return sl_adj
#                else:
#                   sl_adj = max(sl_st, sl_adj)
#                    return sl_adj
#            elif trade == -1:
#                if low <= sl_st - atr_st * (sl_fctr + brkeven_fctr):
#                    sl_adj = sl_st - atr_st * sl_fctr - spread
#                    return sl_adj
#                else:
#                    sl_adj = min(sl_st, sl_adj)
#                    return sl_adj
    
        #entry
        if (trade == 0) & (eflag != 0):
            if eflag == 1:
                close = close + spread/2
            else:
                close = close - spread/2
            df2.loc[i, 'position'] = eflag * close 
            dfb_st = eflag * close
            lmt_st = lmt
            sl_st = sl
            atr_st = atr
            tlvg_st = df2.loc[i, 'trd_lvg']
            trade = eflag
            count = 1
        elif (trade != 0):
#            sl_adj = breakeven_adj()
#            global sl_adj
            if count == 1:
                sl_adj = sl_st
            if trade == 1:
                if high >= sl_st + atr_st * (sl_fctr + brkeven_fctr):
                    sl_adj = sl_st + atr_st * sl_fctr + spread
                else:
                    sl_adj = max(sl_st, sl_adj)
            elif trade == -1:
                if low <= sl_st - atr_st * (sl_fctr + brkeven_fctr):
                    sl_adj = sl_st - atr_st * sl_fctr - spread
                else:
                    sl_adj = min(sl_st, sl_adj)
            count += 1
            df2.loc[i, 'sl_adj'] = sl_adj
            if (sl_adj >= low) & (sl_adj <= high):
                if trade == 1:
                    sl_adj = sl_adj - spread/2
                else:
                    sl_adj = sl_adj + spread/2
                df2.loc[i, 'position'] = sl_adj * trade
                dfb_end = sl_adj * trade
                df2.loc[i, 'trade_pl'] = (dfb_end - dfb_st) * tlvg_st
                trade = 0
                sl_dfb = 0
                lmt_dfb = 0
                count = 0
            elif (lmt_st >= low) & (lmt_st <= high):
                if trade == 1:
                    lmt_st = lmt_st - spread/2
                else:
                    lmt_st = lmt_st + spread/2
                df2.loc[i, 'position'] = lmt_st * trade
                dfb_end = lmt_st * trade
                df2.loc[i, 'trade_pl'] = (dfb_end - dfb_st) * tlvg_st
                trade = 0
                sl_dfb = 0
                lmt_dfb = 0
                count = 0
    #        elif (trade == -1) & (tenkan >= kinjun):
    #            df2.loc[i, 'position'] = ask * trade
    #            dfb_end = ask * trade
    #            df2.loc[i, 'trade_pl'] = (dfb_end - dfb_st) * tlvg_st
    #            trade = 0
    #            sl_dfb = 0
    #            lmt_dfb = 0
    #        elif (trade == 1) & (tenkan <= kinjun):
    #            df2.loc[i, 'position'] = bid * trade
    #            dfb_end = bid * trade
    #            df2.loc[i, 'trade_pl'] = (dfb_end - dfb_st) * tlvg_st
    #            trade = 0
    #            sl_dfb = 0
    #            lmt_dfb = 0
            
    #    df2.loc[i, 'atr_st'] = atr_st
        df2.loc[i, 'total_pl'] = df2.loc[i, 'trade_pl'] + df2.loc[i-1, 'total_pl']
        df2.loc[i, 'total_fund'] = df2.loc[i, 'trade_pl'] + df2.loc[i-1, 'total_fund']

    df3 = df2[df2['position'] != 0]
        
    return df3

startTime = time.time()
df3 = backtest()
executionTime = (time.time() - startTime)
print('Execution time in seconds: ' + str(executionTime))


##############################################
#------> Create tear sheet (Quantstats)
##############################################
df_rtn = pd.DataFrame(df2['Gmt time']).astype('string')
#df_rtn['Gmt time'] = df_rtn['Gmt time'].str[:-6]
df_rtn['Dtime'] = pd.to_datetime(df_rtn['Gmt time'],format='%d/%m/%Y %H:%M')
df_rtn['Date'] = df_rtn['Dtime'].dt.normalize()
df_rtn['Time'] = df_rtn['Dtime'].dt.time
df_rtn['portfolio'] = df2['total_fund']
df_rtn['Time'] = df_rtn['Time'].astype('string')
df_rtn = df_rtn.loc[df_rtn['Time'] == "00:00:00"]
df_rtn = df_rtn.drop(['Time'], axis=1)
df_rtn = df_rtn.drop(['Dtime'], axis=1)
df_rtn = df_rtn.drop(['Gmt time'], axis=1)
df_rtn['pct_rtn'] = df_rtn['portfolio'].pct_change()
df_rtn = df_rtn.drop(['portfolio'], axis=1)
df_rtn = df_rtn.set_index('Date')
qs.extend_pandas()
qs.reports.html(df_rtn['pct_rtn'], benchmark=None, title='Quantem Capital B', output='QC_B_tearsheet_MT5_opt1.html')
