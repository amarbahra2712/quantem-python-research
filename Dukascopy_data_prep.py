# -*- coding: utf-8 -*-
"""
Created on Sat Feb 12 11:43:00 2022

DATA PREP - FROM DUKASCOPY SWISS BANK

@author: quant
"""

import pandas as pd
import numpy as np

sprd = 0.6 

#-----------------------> Load raw data files (bid & offer prices)
df_ask = pd.read_csv('USDJPY_5M_ASK_2019_2021.csv')
df_bid = pd.read_csv('USDJPY_5M_BID_2019_2021.csv')

#-----------------------> Merge data; calc mid prices; calc spread; restate b/o close
df_mid = pd.merge(df_ask, df_bid, on='Gmt time', how='inner', suffixes=("_ask", "_bid"))
df_mid['Open'] = (df_mid['Open_ask'] + df_mid['Open_bid']) / 2 * 100
df_mid['High'] = (df_mid['High_ask'] + df_mid['High_bid']) / 2 * 100
df_mid['Low'] = (df_mid['Low_ask'] + df_mid['Low_bid']) / 2 * 100
df_mid['Close'] = (df_mid['Close_ask'] + df_mid['Close_bid']) / 2 * 100
df_mid['implied_spread'] = (df_mid['Close_ask'] - df_mid['Close_bid']) * 100
df_mid['IG_spread'] = np.where(df_mid['implied_spread'] > sprd, df_mid['implied_spread'], sprd)
df_mid['bid_c'] = df_mid['Close'] - df_mid['IG_spread'] / 2
df_mid['ask_c'] = df_mid['Close'] + df_mid['IG_spread'] / 2
df_mid.drop('Open_ask', inplace=True, axis=1)
df_mid.drop('High_ask', inplace=True, axis=1)
df_mid.drop('Low_ask', inplace=True, axis=1)
df_mid.drop('Close_ask', inplace=True, axis=1)
df_mid.drop('Volume_ask', inplace=True, axis=1)
df_mid.drop('Open_bid', inplace=True, axis=1)
df_mid.drop('High_bid', inplace=True, axis=1)
df_mid.drop('Low_bid', inplace=True, axis=1)
df_mid.drop('Close_bid', inplace=True, axis=1)
df_mid.drop('Volume_bid', inplace=True, axis=1)
df_mid.drop('implied_spread', inplace=True, axis=1)

#----------------------> format data for export
df_mid.insert(1, 'Hour', pd.to_datetime(df_mid['Gmt time']).dt.strftime('%H'))
df_mid.insert(2, 'Min', pd.to_datetime(df_mid['Gmt time']).dt.strftime('%M'))
df_mid['Day'] = df_mid['Gmt time'].astype('string')
df_mid['Day'] = df_mid['Day'].str[:-4]
df_mid['Day'] = pd.to_datetime(df_mid['Day'],format='%d.%m.%Y %H:%M:%S')
df_mid['Day'] = df_mid['Day'].dt.day_name()
df_mid = df_mid[df_mid.Day != 'Saturday']
df_mid = df_mid[df_mid.Day != 'Sunday']
#df_mid = df_mid.drop(['Day'], axis=1)
df_mid.reset_index(inplace = True)
df_mid.drop('index', inplace=True, axis=1)
df_mid['Hour'] = df_mid['Hour'].astype(int)
df_mid['Min'] = df_mid['Min'].astype(int)

#--------------------> export amended data to csv
df_mid.to_csv('USDJPY_5M_MID_2019_2021.csv')
