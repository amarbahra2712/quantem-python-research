# -*- coding: utf-8 -*-
import os
"""
Created on Tue Mar 22 21:40:34 2022

DATA PREP - FROM MT5 Terminal

@author: quant
"""

import pandas as pd
import MetaTrader5 as mt5
import datetime as dt
import numpy as np



#-----------------------> declare variables and parameters
acc = os.getenv("MT5_LOGIN", "")
pwd = os.getenv("MT5_PASSWORD", "")

fx_symbol = "USDJPY_SB"
num_bars = 30000

#-----------------------> define functions
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

connect(acc)
    
#----------------------> create initial data table
bars = mt5.copy_rates_from_pos(fx_symbol, mt5.TIMEFRAME_M1, 1, num_bars)
df = pd.DataFrame(bars)
df['time']=pd.to_datetime(df['time'], unit='s')


#-----------------------> Load raw data files from mt5 data dump
#df = pd.read_csv('MT5_test_data_1102_2303.csv')

#-----------------------> Merge data; calc mid prices; calc spread; restate b/o close
df['bid_c'] = df['close'] - df['spread'] / 2000
df['ask_c'] = df['close'] + df['spread'] / 2000
df.drop('real_volume', inplace=True, axis=1)
df.drop('tick_volume', inplace=True, axis=1)
#del df[df.columns[0]]


#----------------------> format data for export
df.insert(1, 'MoscowDateTime', df['time'].astype('string'))
df['MoscowDateTime'] = pd.to_datetime(df['MoscowDateTime'],format='%Y-%m-%d %H:%M:%S')
df.insert(2, 'LondonTimeDLS', 0)
df['LondonTimeDLS'] = np.where((df['MoscowDateTime'].dt.month >= 4) & (df['MoscowDateTime'].dt.month <= 10), 2, 3)
df['time'] = np.where((df['LondonTimeDLS'] == 3), df['MoscowDateTime'] - dt.timedelta(hours=3), df['MoscowDateTime'] - dt.timedelta(hours=2))
df.insert(3, 'Hour', pd.to_datetime(df['time']).dt.strftime('%H'))
df.insert(4, 'Min', pd.to_datetime(df['time']).dt.strftime('%M'))
df['Day'] = df['time'].astype('string')
df['Day'] = df['Day'].str[:-3]
df['Day'] = pd.to_datetime(df['Day'],format='%Y.%m.%d %H:%M')
df['Day'] = df['Day'].dt.day_name()
df = df[df.Day != 'Saturday']
df = df[df.Day != 'Sunday']
df.reset_index(inplace = True)
df.drop('index', inplace=True, axis=1)
df['Hour'] = df['Hour'].astype(int)
df['Min'] = df['Min'].astype(int)
df.rename(columns={'time': 'Gmt time'}, inplace=True)
df.rename(columns={'open': 'Open'}, inplace=True)
df.rename(columns={'high': 'High'}, inplace=True)
df.rename(columns={'low': 'Low'}, inplace=True)
df.rename(columns={'close': 'Close'}, inplace=True) 
df['Open'] = df['Open'] * 100
df['High'] = df['High'] * 100
df['Low'] = df['Low'] * 100
df['Close'] = df['Close'] * 100
df['bid_c'] = df['bid_c'] * 100
df['ask_c'] = df['ask_c'] * 100

df['EndDay_fltr'] = np.where((df['Hour'] == 0) & (df['Min'] == 0), 1, 0)

if (df.iloc[-1,1] != 0) & (df.iloc[-1, 2] != 0):
    df.iloc[-1,-1] = 1
else:
    pass

#--------------------> export amended data to csv
df.to_csv('USDJPY_1M_MID_mt5_xyz_080722.csv')
