#!/usr/bin/env python

import os
import sys
import click 
import pathlib
import json
import git
import glob

from datetime import date, timedelta

import xarray as xr
import pandas as pd 
import numpy as np
import netCDF4 as nc

from solartime import SolarTime               ## to be replaced by pvlib if more problems encountered, works for now

pd.options.mode.chained_assignment = None     ## Warning avoid : ' SettingWithCopyWarning ' 



##ARGUMENTS
site = sys.argv[1]
print('site in python script = ', site)

path_all_years = sys.argv[2] #/homedata/mvanhove/STRATfinder/2*/{site}/ANNUAL/stratfinder_2b_{site}PmlhF1min_v01_*_V2022a.nc

df = xr.open_mfdataset(glob.glob(f"{path_all_years}")).to_dataframe()
df.reset_index(drop=True, level=0, inplace=True)
df = df[df.index.duplicated() == False]

month = sys.argv[3]
output = sys.argv[4]    ## fichier contenant la donnée saisonnière json 



## CHECK IF ARGUMENTS ARE READABLE/WRITABLE

@click.command()

@click.argument(
    "site_name",
    nargs=1,
)

@click.argument(
    "path_all_years",
    nargs=1,
)

@click.argument(
    "month",
    nargs=1,
)

@click.argument(
    "site_o",
    nargs=1,
    type=click.Path(
       exists = False, readable = True, file_okay = True, dir_okay = False, resolve_path = True
    ),
)


def main(site_name, path_all_years, month, site_o):
    click.echo(click.format_filename(site_name))
    click.echo(click.format_filename(path_all_years))
    click.echo(click.format_filename(month))
    click.echo(click.format_filename(site_o))
    

if __name__ == "__main__":
    main(standalone_mode=False)



## CONFIGURATION


#ds = nc.Dataset(globals()['input_%s' % site])
lat, lon =df['station_latitude'][0], df['station_longitude'][0]

ave_df = df.copy()

start_date = ave_df.index.date[0]
end_date = ave_df.index.date[len(ave_df)-2]


## AVERAGING OVER 15 MIN AND FILL TIME MISSING

ave_df = ave_df.resample("15min").mean()
ave_df.index = pd.to_datetime(ave_df.index.values) + timedelta(minutes=15)
ave_df.index = ave_df.index.set_names(['time'])
    
df2 = pd.date_range(start_date, end_date + timedelta(days=1), freq="15min")
df2 = df2.to_frame(index=True, name=None)
df2.index.names = ["time"]
ave_df = pd.merge(ave_df, df2, how = "right", right_index=True, left_index = True)
ave_df.drop(index=ave_df.index[0], axis=0, inplace=True)

## IN CASE DATAFRAME DOESNT START/END AT MIDNIGHT
df2 = pd.date_range(start_date, end_date, freq="15min")
df2 = df2.to_frame(index=True, name=None)
df2.index.names = ["time"]
ave_df = pd.merge(ave_df, df2, how = "right", right_index=True, left_index = True)
ave_df.drop(index=ave_df.index[0], axis=0, inplace=True)



## TIME RELATIVE TO SUNRISE DEFINITION



sun = SolarTime()

date = start_date - timedelta(days=1)
sunrise = []
sunset = []

while date <= (end_date): # + timedelta(days=1)) :
        schedule = sun.sun_utc(date, lat, lon)
        sunrise1 = (schedule['sunrise'].second + 60*schedule['sunrise'].minute + 3600*schedule['sunrise'].hour)/3600. #en heure
        sunrise1 = 0.25 * (round(4.0 * sunrise1))  #en heure arrondie au quart d'heure le plus proche
        sunset1 = (schedule['sunset'].second + 60*schedule['sunset'].minute + 3600*schedule['sunset'].hour)/3600.
        sunset1 = 0.25 * (round(4.0 * sunset1))
        sunrise.append(sunrise1)
        sunset.append(sunset1)
        date = date + timedelta(days=1)
        
print(schedule, sunrise1, sunset1)


time = [i/4. for i in range(1, 97)]#*(end_date - start_date).days
dt=[]

for j in range(1, len(sunrise)-1):
    for i in range(96):
        if time[i] < sunset[j] :
            dt.append(time[i]-sunrise[j])
        else :
            dt.append(-(24-time[i] + sunrise[j+1]))
            

ave_df.insert(2,'time_relSR', dt)


ss = []
for j in range(len(sunset)-2):
    for i in range(96):
        if time[i] < sunrise[j+1] :
            ss.append((24-sunset[j] + time[i]))
        else:
            ss.append(time[i]-sunset[j+1])
            

ave_df.insert(3,'time_relSS', ss)

# OTHER INDEXES

n=1
day=[1]

for i in range(1, len(ave_df)):
    if dt[i-1]>0 and dt[i]<0 :
        day.append(n+1)
        n=n+1
    else :
        day.append(n)           #day relative to sunrise/sunset


ave_df.insert(4, 'day', day)



## MEDIAN VALUES

lim = int(len(ave_df)/2500)


df_final = ave_df[ave_df.index.month == int(month)].groupby('time_relSR', as_index=False).agg(mlh_med = ("MLH" , lambda x : x.median() if ((np.isnan(x)==False).sum() > lim) else None), mlh_q1 = ("MLH" , lambda x : x.quantile(0.25) if ((np.isnan(x)==False).sum() > lim) else None), mlh_q3 = ("MLH" , lambda x : x.quantile(0.75) if ((np.isnan(x)==False).sum() > lim) else None))


df_final.set_index('time_relSR', inplace=True)

month_lab_list = [' ', 'jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']
month_lab = month_lab_list[int(month)]

data = {'title' : f'MLH_{month_lab}_{site}_Stratfinder', 'time' : list(df_final.index), 'mlh_med': list(df_final.mlh_med), 'mlh_q1': list(df_final.mlh_q1), 'mlh_q3': list(df_final.mlh_q3), 'label_x' : 'time relative to SR [h]', 'label_y' : 'MLH median [magl]'}


## JSON FILE


with open(f"{globals()['output_%s' % site]}", 'w') as f:
    json.dump(data, f)

























