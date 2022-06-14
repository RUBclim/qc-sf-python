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

globals()['df_%s' % site] = xr.open_mfdataset(glob.glob(f"/homedata/mvanhove/STRATfinder/2*/{site}/ANNUAL/stratfinder_2b_{site}PmlhF1min_v01_*_V2022a.nc")).to_dataframe()


globals()['df_%s' % site].reset_index(drop=True, level=0, inplace=True)
globals()['df_%s' % site] = globals()['df_%s' % site][globals()['df_%s' % site].index.duplicated() == False]


month = sys.argv[2]



globals()['output_%s' % site] = sys.argv[3]    ## fichier contenant la donnée saisonnière json 




## CHECK IF ARGUMENTS ARE READABLE/WRITABLE

@click.command()

@click.argument(
    "site_name",
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


def main(site_name, month, site_o):
    click.echo(click.format_filename(site_name))
    click.echo(click.format_filename(month))
    click.echo(click.format_filename(site_o))
    

if __name__ == "__main__":
    main(standalone_mode=False)



## CONFIGURATION


#ds = nc.Dataset(globals()['input_%s' % site])
lat, lon = globals()['df_%s' % site]['station_latitude'][0], globals()['df_%s' % site]['station_longitude'][0]

globals()['ave_df%s' % site] = globals()['df_%s' % site].copy()

start_date = globals()['ave_df%s' % site].index.date[0]
end_date = globals()['ave_df%s' % site].index.date[len(globals()['ave_df%s' % site])-2]


## AVERAGING OVER 15 MIN AND FILL TIME MISSING

globals()['ave_df%s' % site] = globals()['ave_df%s' % site].resample("15min").mean()
globals()['ave_df%s' % site].index = pd.to_datetime(globals()['ave_df%s' % site].index.values) + timedelta(minutes=15)
globals()['ave_df%s' % site].index = globals()['ave_df%s' % site].index.set_names(['time'])
    
df2 = pd.date_range(start_date, end_date + timedelta(days=1), freq="15min")
df2 = df2.to_frame(index=True, name=None)
df2.index.names = ["time"]
globals()['ave_df%s' % site] = pd.merge(globals()['ave_df%s' % site], df2, how = "right", right_index=True, left_index = True)
globals()['ave_df%s' % site].drop(index=globals()['ave_df%s' % site].index[0], axis=0, inplace=True)

## IN CASE DATAFRAME DOESNT START/END AT MIDNIGHT
df2 = pd.date_range(start_date, end_date, freq="15min")
df2 = df2.to_frame(index=True, name=None)
df2.index.names = ["time"]
globals()['ave_df%s' % site] = pd.merge(globals()['ave_df%s' % site], df2, how = "right", right_index=True, left_index = True)
globals()['ave_df%s' % site].drop(index=globals()['ave_df%s' % site].index[0], axis=0, inplace=True)



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
            

globals()['ave_df%s' % site].insert(2,'time_relSR', dt)


ss = []
for j in range(len(sunset)-2):
    for i in range(96):
        if time[i] < sunrise[j+1] :
            ss.append((24-sunset[j] + time[i]))
        else:
            ss.append(time[i]-sunset[j+1])
            

globals()['ave_df%s' % site].insert(3,'time_relSS', ss)

# OTHER INDEXES

n=1
day=[1]

for i in range(1, len(globals()['ave_df%s' % site])):
    if dt[i-1]>0 and dt[i]<0 :
        day.append(n+1)
        n=n+1
    else :
        day.append(n)           #day relative to sunrise/sunset


globals()['ave_df%s' % site].insert(4, 'day', day)



## MEDIAN VALUES

lim = int(len(globals()['ave_df%s' % site])/2500)


df = globals()['ave_df%s' % site][globals()['ave_df%s' % site].index.month == int(month)].groupby('time_relSR', as_index=False).agg(mlh_med = ("MLH" , lambda x : x.median() if ((np.isnan(x)==False).sum() > lim) else None), mlh_q1 = ("MLH" , lambda x : x.quantile(0.25) if ((np.isnan(x)==False).sum() > lim) else None), mlh_q3 = ("MLH" , lambda x : x.quantile(0.75) if ((np.isnan(x)==False).sum() > lim) else None))


df.set_index('time_relSR', inplace=True)

month_lab_list = [' ', 'jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']
month_lab = month_lab_list[int(month)]

data = {'title' : f'MLH_{month_lab}_{site}_Stratfinder', 'time' : list(df.index), 'mlh_med': list(df.mlh_med), 'mlh_q1': list(df.mlh_q1), 'mlh_q3': list(df.mlh_q3), 'label_x' : 'time relative to SR [h]', 'label_y' : 'MLH median [magl]'}


## JSON FILE


with open(f"{globals()['output_%s' % site]}", 'w') as f:
    json.dump(data, f)

























