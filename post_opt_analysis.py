# -*- coding: utf-8 -*-
"""
Created on Mon Apr 18 15:54:37 2022

@author: quant
"""

import pandas as pd
from optimizer_tqdm import result
from test_code_v2 import df2
import numpy as np
#import plotly.express as px


df = pd.DataFrame(result)
df = pd.DataFrame(df[1].to_list())
#df_rtn = df.iloc[:, -1:]
#df_rtn = df_rtn.rename(columns={df_rtn.columns[0]: 'total_fund'})

df = df.transpose()
df = pd.read_csv('opt_output_1_54500.csv')
#df.to_csv('opt_output_1_54500.csv')
df2 = df2[['Gmt time', 'EndDay_fltr']]
df2 = df2.loc[df2['EndDay_fltr'] == 1]
df2.reset_index(drop = True, inplace = True)

df.insert(0, 'Gmt time', df2['Gmt time'])
#df.insert(1, 'Hour', df2['Hour'])
#df.insert(2, 'Min', df2['Min'])

df['Dtime'] = pd.to_datetime(df['Gmt time'],format='%d/%m/%Y %H:%M')
df['Date'] = df['Dtime'].dt.date
#df['Time'] = df['Dtime'].dt.time
#df['Time'] = df['Time'].astype('string')
#df_rtn = df.loc[df['Time'] == "00:00:00"]
#df_rtn = df_rtn.append(df.iloc[-1], ignore_index = True)
#df_rtn = df_rtn.drop(['Time'], axis=1)
df = df.drop(['Dtime'], axis=1)
df = df.drop(['Gmt time'], axis=1)
#df_rtn = df_rtn.drop(['Hour'], axis=1)
#df_rtn = df_rtn.drop(['Min'], axis=1)
df = df.set_index('Date')

df_pct = df.pct_change()

def sharpe_ratio(return_series, N, rf):
    mean = return_series.mean() * N -rf
    sigma = return_series.std() * np.sqrt(N)
    return mean / sigma

def sortino_ratio(series, N,rf):
    mean = series.mean() * N -rf
    std_neg = series[series<0].std()*np.sqrt(N)
    return mean/std_neg

def max_drawdown(return_series):
    comp_ret = (return_series+1).cumprod()
    peak = comp_ret.expanding(min_periods=1).max()
    dd = (comp_ret/peak)-1
    return dd.min()


N = 255 #255 trading days in a year
rf =0.00 #1% risk free rate

sharpe = df_pct.apply(sharpe_ratio, args=(N,rf,),axis=0)
sortino = df_pct.apply(sortino_ratio, args=(N,rf,), axis=0 )
max_drawdown = df_pct.apply(max_drawdown,axis=0)
calmar = df_pct.mean()*255/abs(max_drawdown)
ROC = (df_pct+1).cumprod()[-1:]

btstats = pd.DataFrame()
btstats['RoC'] = (df_pct+1).cumprod()[-1:].transpose()
btstats['sortino'] = sortino
btstats['sharpe'] = sharpe
btstats['maxdd'] = max_drawdown
btstats['calmar'] = calmar

####### Plotly Scatter
#fig = px.scatter(btstats, x="sharpe", y="RoC", color='maxdd')
#fig.write_html("file.html")
