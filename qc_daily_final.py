#!/usr/bin/env python

import os
import sys
import click 
import pathlib
import json
import git

from datetime import date, timedelta

import xarray as xr
import pandas as pd 
import numpy as np
import netCDF4 as nc

from solartime import SolarTime               ## to be replaced by pvlib if more problems encountered, works for now

pd.options.mode.chained_assignment = None     ## Warning avoid : ' SettingWithCopyWarning ' 



##ARGUMENTS

day_1 = sys.argv[1]          ## fichier netcdf L2A du jour J-1
day_2 = sys.argv[2]          ## fichier netcdf L2A du jour J
day_3 = sys.argv[3]          ## fichier netcdf L2A du jour J+1
config_file = sys.argv[4]    ## configuration file 
output_day2 = sys.argv[5]    ## fichier netcdf L2B du jour J



## CHECK IF ARGUMENTS ARE READABLE/WRITABLE

@click.command()
@click.argument(
    "day_1a",
    nargs=1,
    type=click.Path(
        exists = False, readable = True, file_okay = True, dir_okay = False, resolve_path = True
    ),
)

@click.argument(
    "day_2a",
    nargs=1,
    type=click.Path(
        exists=True , readable = True, file_okay = True, dir_okay = False,  resolve_path = True
    ),
)

@click.argument(
    "day_3a",
    nargs=1,
    type=click.Path(
        exists = False, readable = True, file_okay = True, dir_okay = False, resolve_path = True
    ),
)

@click.argument(
    "config_filea",
    nargs=1,
    type=click.Path(
        exists = True, readable = True, file_okay = True, dir_okay = False, resolve_path = True
    ),    
)

@click.argument(
    "output_day2a",
    nargs = 1,
    type=click.Path(
        exists=False, writable = True, file_okay=True, dir_okay = False, resolve_path = True
    ),
)


def main(day_1a, day_2a, day_3a, config_filea, output_day2a):
    click.echo(click.format_filename(day_1a))
    click.echo(click.format_filename(day_2a))
    click.echo(click.format_filename(day_3a))
    click.echo(config_filea)
    click.echo(click.format_filename(output_day2a))

if __name__ == "__main__":
    main(standalone_mode=False)



## CONFIGURATION : WHAT DEPENDS ON THE SITE


with open(sys.argv[4], "r") as jsonfile:         ## configuration file : climatological limit of MLH
    data = json.load(jsonfile)
    maxmlh = data["MLHsettings"]    
    maxmlh = maxmlh[0]['dayMax']

ds = nc.Dataset(day_2)
site = ds.__dict__['site_location']              ## site name given in J file 


isFile1, isFile2, isFile3 = os.path.isfile(day_1), os.path.isfile(day_2), os.path.isfile(day_3)


## DATAFRAME PREPARED FOR THE END

df_day_2 = xr.open_dataset(day_2).to_dataframe() 
df_day_2 = df_day_2.reset_index(level=0, drop=True) 
df_day_2 = df_day_2[~df_day_2.index.duplicated(keep='first')]
df_day_2 = df_day_2.loc[df_day_2.index.dropna()]

## AVERAGE 15 MIN (IN THE END : ADD THE FLAG COLUMN TO 1MIN DS AND FILL NAN WITH LAST VALID FLAG VALUE)

df2 = df_day_2.resample("15min").mean()
df2 = df2[df2.index.date == df2.index.date[0]]
df2.index = pd.to_datetime(df2.index.values) + timedelta(minutes=15)
df2.index = df2.index.set_names(['time'])


## CONSTRUCT DATAFRAME OF 3 DAYS (J-1, J, J+1) IF MISSING VALUES

day1 = df2.index.date[0] - timedelta(days=1)
df_id = pd.date_range(day1, day1 + timedelta(days=3), freq="15min").to_frame(index=True, name=None)
df_id.index.names = ["time"]
df_id.drop(index=df_id.index[0], axis=0, inplace=True)

if isFile1 == True :
    df1 = xr.open_dataset(day_1).to_dataframe()
    df1 = df1.reset_index(level=0, drop=True)
    df1 = df1[df1.index.date == df1.index.date[0]]
    df1 = df1.resample("15min").mean()
    df1.index = pd.to_datetime(df1.index.values) + timedelta(minutes=15)
    df1.index = df1.index.set_names(['time'])
else :
    df1 = None
    print(f"{day_1} n'existe pas et est remplacé par un dataframe vide") 
if isFile3 == True :
    df3 = xr.open_dataset(day_3).to_dataframe()
    df3 = df3.reset_index(level=0, drop=True)
    df3 = df3.resample("15min").mean()
    df3.index = pd.to_datetime(df3.index.values) + timedelta(minutes=15)
    df3.index = df3.index.set_names(['time'])
else :
    df3 = None
    print(f"{day_3} n'existe pas et est remplacé par un dataframe vide")

df = pd.concat([df1, df2, df3])
df = pd.merge(df, df_id, how = "right", right_index=True, left_index = True)
print('complete dataframe created')



## VARIABLES

ndata_day2 = int(len(df)/3)
month2 = df2.index.month[0]
warm = (month2 > 2) & (month2 < 10)
lat = df2.station_latitude[0]
lon = df2.station_longitude[0]

## DATASET FOR OUTPUT FILE 

ds = xr.open_dataset(day_2)


## REMOVE NAN AND DUPLICATED TIMES IN DATASET

x = ~np.isnan(ds['time'])
new_time = {'time' : x}
ds = ds.isel(new_time)

_, index = np.unique(ds['time'], return_index=True)
ds = ds.isel(time=index)


## INFORMATION MESSAGE 

day0 = df2.index.date[0] - timedelta(days=2)
day1 = (df2.index.date[0] - timedelta(days=1)).isoformat() 
day2 = df2.index.date[0].isoformat()
day3 = (df2.index.date[0] + timedelta(days=1)).isoformat()
day4 = (df2.index.date[0] + timedelta(days=2)).isoformat()

#print("Site = ", site, ", lat = ", lat[site], ", lon = ", lon[site], ", JourJ = ", day2, ", Jour J-1 = ", day1, ", Jour J+1 = ", day3)
print("Site = ", site, ", lat = ", lat, ", lon = ", lon, ", JourJ = ", day2, ", Jour J-1 = ", day1, ", Jour J+1 = ", day3)



## RENAME COLUMNS TO SIMPLIFY
 
df = df.rename(columns = {'FLAG':'prof'})
df = df.rename(columns = {'cloud_base_altitude':'CBH'})


## TIME RELATIVE TO SUNRISE/SUNSET   

sun = SolarTime()
date = date(day0.year, day0.month, day0.day)
sunrise, sunset = [], []

for i in range(5):                                                                                                 ## 5 : because we need SR & SS at day J-2, J-1, J, J+1 et J+2 
    schedule = sun.sun_utc(date, lat, lon)                                                             
    
    sunrise1 = (schedule['sunrise'].second + 60*schedule['sunrise'].minute + 3600*schedule['sunrise'].hour)/3600.  ## sunrise in hour
    sunrise1 = 0.25 * (round(4.0 * sunrise1))                                                                      ## rounded to closer quarter hour
    
    sunset1 = (schedule['sunset'].second + 60*schedule['sunset'].minute + 3600*schedule['sunset'].hour)/3600.      ## same for sunset
    sunset1 = 0.25 * (round(4.0 * sunset1))
    
    sunrise.append(sunrise1)
    sunset.append(sunset1)
    date = date + timedelta(days=1)


													       	## mettre les ss et sr dans df et créer des slices pour 
														##rajouter time_relSR et SS dans ces slices 


Time = [i/4. for i in range(1, ndata_day2+1)]
dt=[]

for j in range(1, len(sunrise)-1):
    for i in range(ndata_day2):
        if Time[i] < sunset[j] :
            dt.append(Time[i]-sunrise[j])
        else :
            dt.append(-(24-Time[i] + sunrise[j+1]))

df.insert(2,'time_relSR', dt)

ss = []
for j in range(len(sunset)-2):
    for i in range(ndata_day2):
        if Time[i] < sunrise[j] :
            ss.append((24-sunset[j] + Time[i]))
        else:
            ss.append(Time[i]-sunset[j+1])

df.insert(3,'time_relSS', ss)
        


## DAY RELATIVE FROM SUNSET TO SUNSET  

n=1
df.insert(4, 'day', 0)
for i in df.index:
    if df.at[i, 'time_relSS'] == 0 :
        df.at[i, 'day'] = n+1
        n = n+1
    else :
        df.at[i, 'day'] = n

print("Time relative to SR, SS, and day relative to SS done")



## FLAG INIT

df.insert(5, 'FLAG_QC', 0) 



## INIT FILTERS

## RAIN

df['MLH'] = np.where(df.prof > 0,np.nan,df.MLH)
prof = (df.prof > 0).sum()

df2 = df[df['time_relSR']<1].groupby('day', as_index=False).agg(profn = ("prof",  lambda x : (pd.to_numeric(x)>0.1).sum()))   ## profn = nombre de fois où prof est > 10, par nuit
df3 = df[df['time_relSR']>-1].groupby('day', as_index=False).agg(profd = ("prof",  lambda x : (pd.to_numeric(x)>0.1).sum()))  ## profd = nombre de fois où prof est > 10, par jour
df = df.reset_index().merge(df2, how="left").set_index('time')                                                               ## les valeurs de profn sont rajoutées à df
df = df.reset_index().merge(df3, how="left").set_index('time')                                                               ## les valeurs de profd sont rajoutées à df
df.FLAG_QC[(df.profd >= 12) & (df.time_relSR>-1)] = df.FLAG_QC + 1                                                                 ## si profd >= 12 dans un même jour, le jour est flaggué
df.FLAG_QC[(df.profn >= 12) & (df.time_relSR<1)] = df.FLAG_QC + 1                                                                  ## si profn >= 12 dans une même nuit, la nuit est flagguée

print('filter Rain done')





##REMOVE STUCK MLH AT DAY/WARM SEASONS

if  ((site != "LERWICK,UK") & (warm == True))  :
    
    def stuck_mlh(df, var_atmo) :
        
        d = (df.day==2)
        afternoon = (df.time_relSR > 5) & d

        day_time1 = (df.time_relSR >= 5) & d
        n_inf_300 = (day_time1 & (var_atmo < 300)).sum() 
        val_mlh1 = (day_time1 & (var_atmo > 0)).sum()
        if val_mlh1 != 0 :
            rap1 = n_inf_300/val_mlh1
        else :
            rap1 = np.nan  


        morn_time = (df.time_relSR >0) & (df.time_relSR < 5) & d 
        max_morn = var_atmo[morn_time].max()  
    
        day_time2 = (df.time_relSR > 7) & d  
        n_inf_500 = (day_time2 & (var_atmo < 500)).sum() 
        val_mlh2 = (day_time2 & (var_atmo > 0)).sum()
        if val_mlh2 != 0 :
            rap2 = n_inf_300/val_mlh2
        else :
            rap2 = np.nan

        if ( (rap1 > 0.5) | ((max_morn > 300 ) & (rap2 > 0.5)) ) :
            df.FLAG_QC[afternoon & (var_atmo < 500)] = df.FLAG_QC[ afternoon & (var_atmo < 500) ] + 10                 ## valeurs constantes style 500, 300 etc. conf json (avec click c'est possible)
      
        return df

    df = stuck_mlh(df, df.MLH)
  
 
print('filter Stuck MLH done')





## CHECK FOR MASSIVE INCREASE


## DURING NIGHT                                                                                         

# differences between consecutive mlh (taking NaN into account)
df['diff'] = df['MLH'].diff() 
d = (df.day == 2) | (df.day == 3)
df[d]['diff'] = df[d]['MLH'].diff() 

idx = df[np.isnan(df['diff']) == True].index.to_list()

for i in idx:
    idx2 = df[df.index < i].MLH.last_valid_index()
    if idx2 is not None :
        if (i - idx2) < timedelta(hours = 9) :
            df['diff'][i] = df.MLH[i] - df.MLH[idx2]





## MASSIVE INCREASE AT NIGHT

## fonction qui prend en argument le df, la colonne df.MLH, le seuil caractéristique d'une augmentation, et qui renvoit un df flaggué  

def massive_inc_night(df, var_atmo, thresh) :
    d = ((df.day == 2) | (df.day == 3))
    df2 = df[(df.time_relSR <= 1) & d & (df['diff'] > 300)]

    h = (df['diff']>thresh)
    l = (df['diff']<-thresh)
    t = (df['time_relSR'] < 2)
    ind = []

    if df2.index.size > 0 :
        for idx in df2.index : 
            d = (df.day == df2.day[idx])
            idx_last = df[(df.time_relSR == 5) & d].index.to_list() 
             
            if df[d & t & l & (df.index > idx)].index.min() is not pd.NaT :    # increase followed by decrease
                a = df[d & t & l & (df.index > idx)].index.min()
                a = a - timedelta(minutes = 15)   
                ind += df[idx:a].index.to_list()

            elif df[t & d & (var_atmo < 500) & (df.index > idx)].index.min() is not pd.NaT :    # MLH lower than 500m after increase
                a = df[t & d & (var_atmo < 500) & (df.index > idx)].index.min()                
                a = a - timedelta(minutes = 15)
                ind += df[idx:a].index.to_list()

            elif df['time_relSR'][idx] > -1 :    
                ind += df[d & (df['time_relSR'] < 4 ) & (df.index >= idx)].index.to_list()   
            else : 
                ind = ind + df[idx:idx_last[0]].index.to_list()

    df['FLAG_QC'][ind] = df['FLAG_QC'][ind] + 100
    return(df)

df = massive_inc_night(df, df.MLH, 300)


## MASSIVE DECREASE AT NIGHT 

def massive_dec_night(df, var_atmo, thresh) :
    d = ((df.day == 2) | (df.day == 3))
    df2 = df[(df.time_relSR < 0.25) & d & (df['diff'] < thresh)]
    l = (df['diff']<thresh)
    t = (df['time_relSR'] < 0.25) & (df['time_relSS']> 2 )
    ind = []

    if df2.index.size > 0 :
        for idx in df2.index :
            d = (df.day == df2.day[idx])
            s = df.time_relSR[d].idxmin() 
            if df[t & d & (df.MLH < 500) & (df.index < idx)].index.max() is not pd.NaT :   
                a = df[t & d & (df.MLH < 500) & (df.index < idx)].index.max()
                a = a + timedelta(minutes=15)
                idx = idx - timedelta(minutes=15)
                ind += df[a:idx].index.to_list()
           
            else :  
                idx = idx - timedelta(minutes=15)
                ind += df[s:idx].index.to_list()
                print(ind)
            

    df['FLAG_QC'][ind] = df['FLAG_QC'][ind] + 100 
    return(df)
    

df = massive_dec_night(df, df.MLH, -300)

print('filter Massive decrease/increase at night done')


## DAY MASSIVE INCREASE/ DECREASE IN TWO HOURS MAXIMUM 


# differences between consecutive mlh (taking NaN into account)
df['diff'] = df['MLH'].diff() 
idx = df[np.isnan(df['diff']) == True].index.to_list()
for i in idx:
    idx2 = df[df.index < i].MLH.last_valid_index()
    if idx2 is not None :
        if (i - idx2) <= timedelta(minutes = 120) :
            df['diff'][i] = df.MLH[i] - df.MLH[idx2]






## INCREASE - COLD SEASONS MORNINGS


d = (df.day == 2)

if warm == False : 
    def cold_morn_inc(df, thresh) :
        df2 = df[(df.time_relSR > 0) & (df.index.hour < 12) & (df['diff'] > thresh) & d] 
        h = (df['diff']> thresh)
        l = (df['diff']< -thresh)
        t = (df['time_relSR'] > 0) 

        ind = []
        if df2.index.size != 0 : 
            for idx in df2.index : 
                if df[l & d & (df.index >= idx) & (df.index < idx + timedelta(minutes = 210))].index.max() is not pd.NaT :
                        a = df[l & d & (df.index >= idx) & (df.index < idx + timedelta(minutes = 210))].index.max()
                        ind = ind + df[idx : a - timedelta(minutes = 15)].index.to_list()
            
        df.FLAG_QC[ind] = df.FLAG_QC[ind] + 100
        return(df)

    df = cold_morn_inc(df, 400)



## INCREASE - COLD SEASONS DAYS

    def cold_day_inc(df, var_atmo, thresh) :
        df2 = df[(df.time_relSR > 0)  & (df['diff'] > thresh ) & d ]
        h = (df['diff']> thresh)
        l = (df['diff']< -(thresh - 200))
        t = (df['time_relSR'] > 0) 
        ind = []
     
        if df2.index.size != 0 :
            for idx in df2.index : 
                if df[(df.index >= idx) & (df.MLH < 500) & d].index.min() is not pd.NaT : 
                    a = df[(df.index >= idx) & (var_atmo < 500) & d].index.min()
                    ind = ind + df[idx : a - timedelta(minutes = 15)].index.to_list()
                                                                                        
                elif df[l & (df.index >= idx) & d].index.min() is not pd.NaT  :
                    a = df[l & (df.index >= idx) & d].index.min()
                    ind = ind + df[idx : a - timedelta(minutes = 15)].index.to_list()
            
        df.FLAG_QC[ind] = df.FLAG_QC[ind] + 100
        return(df)
    df = cold_day_inc(df, df.MLH, 1000)



## INCREASE - WARM SEASONS


else :                                                  # ie :   if per = (month2 < 10) & (month2 > 2)
    def warm_day_inc(df, thresh) :
        d = (df.day == 2) 
        df2 = df[(df.time_relSR > 0)  & (df['diff'] > thresh ) & d ]  ##thresh = 800
        h = (df['diff'] > thresh) 
        t = (df['time_relSR'] > 0) 
        l = (df['diff']< - (thresh - 100)) 
        ind = []

        if df2.index.size != 0 :
            for idx in df2.index :
                if df[t & d & l & (df.index >= idx) & (df.index <= idx + timedelta(minutes = 60))].index.min() is not pd.NaT  :
                    a = df[t & d & l & (df.index >= idx) & (df.index <= idx + timedelta(minutes = 60))].index.min()
                    a = a - timedelta(minutes = 15)
                    ind = ind + df[idx:a].index.to_list()
            
                
        df.FLAG_QC[ind] = df.FLAG_QC[ind] + 100
        return(df)
    df = warm_day_inc(df, 1000)


print('filter Massive Increase/decrease at day done')






## WINTER EXTREME POINTS

if ((month2 < 3) | (month2 > 11)) : 
    df.FLAG_QC[((month2 < 3) | (month2 > 11))  & (df.MLH > (0.75*maxmlh))] = df.FLAG_QC[((month2 < 3) | (month2 > 11)) & (df.MLH > (0.75*maxmlh))] + 100
    

## EXTREME POINTS

df.FLAG_QC[df.MLH > maxmlh] = df.FLAG_QC[df.MLH > maxmlh] + 100


print('filter Extreme points done')




## DEEP CONVECTION : SUMMER AND AFTERNOON : UNDERESTIMATION OF ABLH 


#if ((((48 <= lat[site] <= 49) & (2 <= lon[site] <= 3)) | ((50 <= lat[site] <= 51) & (14 <= lon[site] <= 15))) & (warm == True)) : 
if ((((48 <= lat <= 49) & (2 <= lon <= 3)) | ((50 <= lat <= 51) & (14 <= lon <= 15))) & (warm == True)) :  
 
    d = (df.day == 2)
    afternoon = (df.index.hour > 11) & (df.time_relSR > 0) 
    
    ux = (df.time_relSR > 2) & (df.time_relSS < -2)
    df2 = df[afternoon & d].groupby('day', as_index=False).agg(firstcloud = ("CBH" , lambda x : x.loc[x.first_valid_index()] if x.first_valid_index() is not None else None )) ## column of first CBH in the morning  
    
    df['ABLC'] = df2.firstcloud[0]+500 if df2.firstcloud[0] is not None  else None
    
    df['ABLC'] = df['ABLC'].fillna(3000)
    df['noise'] = np.where(d & ux & (df['MLH'] < (df['CBH'] - 200)) & (df.CBH <= df.ABLC) , 1, np.nan) 
    indexes = df[df.noise == 1].index.to_list()

    for idx in indexes :
        df.noise[idx - 2*timedelta(minutes = 15)] = 1 
        df.noise[idx - timedelta(minutes = 15)] = 1
        df.noise[idx + timedelta(minutes = 15)] = 1 
        df.noise[idx + 2*timedelta(minutes = 15)] = 1 

    indexes = df[df.noise == 1].index.to_list()

    df['FLAG_QC'][indexes] = df['FLAG_QC'][indexes] + 1000
        
    
    
    ux = (df.index.hour > 12) & (df.time_relSS < -2)
    mincloud = df[afternoon & d]['CBH'].min()

    minC = mincloud - 500 
    df['noise'] = np.where((df.MLH < minC) & ux, 1, np.nan) 
    indexes = df[df.noise == 1].index.to_list()

    for idx in indexes :
        df.noise[idx - 2*timedelta(minutes = 15)] = 1 
        df.noise[idx - timedelta(minutes = 15)] = 1 
        df.noise[idx + timedelta(minutes = 15)] = 1 
        df.noise[idx + 2*timedelta(minutes = 15)] = 1 

    indexes = df[df.noise == 1].index.to_list()
    df['FLAG_QC'][indexes] = df['FLAG_QC'][indexes] + 1000


    print('filter Deep convection done')



## RESIDUAL LAYER

# MAM JJA

if warm == True :
    ii = (df.time_relSS > 2 ) & ( df.time_relSR < 2)
    df2 = df[ii].groupby('day', as_index=False).agg(mM = ("MLH" , lambda x : (x>800).sum()/(x>0).sum() if (x>0).sum() != 0 else None))
    llcheck = list(df2.day[df2.mM > 0.75])

    if llcheck != [] :
        for d in llcheck :
            df.FLAG_QC[(df.time_relSR < 3 ) & (df.day == d) & (df.MLH > 600)] = df.FLAG_QC[(df.time_relSR < 3) & (df.day == d) & (df.MLH > 600)] + 10000
    

#SON DJF
per = ((month2 < 3) | (month2 > 9))
if per :
    ii =  ( df.time_relSS > 2) & (df.time_relSR < 2)  
    df2 = df[ii].groupby('day', as_index=False).agg(mMM = ("MLH" , lambda x :  (x>600).sum()/(x>0).sum() if (x>0).sum() != 0 else None))
    llcheck = list(df2.day[df2.mMM > 0.5])

    if llcheck != [] :
        for d in llcheck :
            df.FLAG_QC[(df.time_relSR < 2) & (df.day == d) & (df.MLH > 500)] = df.FLAG_QC[(df.time_relSR < 2) & (df.day == d) & (df.MLH > 500)] + 10000


print('filter Residual layer done')






## REMERGE WITH 1MIN FREQUENCY

df_day_2['FLAG_QC'] = 0
df = df[df.index.date == date.fromisoformat(day2)]
for i in range(1, len(df)) :
    df_day_2.loc[((df_day_2.index.time < df.index.time[i]) & (df_day_2.index.time > df.index.time[i-1])) , 'FLAG_QC'] = df.FLAG_QC[i]


df2 = xr.open_dataset(day_2).to_dataframe()
df2 = df2.loc[df2.index.dropna()]
df2 = df2[~df2.index.duplicated(keep='first')]

print('len df_day_2 = ', len(df_day_2), 'len(df2) = ', len(df2))




## FINAL DATAFRAME

df2['FLAG_QC'] = list(df_day_2['FLAG_QC'].astype(int))
df2['FLAG_QC'] = df2['FLAG_QC'][np.isnan(df2['MLH']) == False]
df2['MLH'] = df2[df2.FLAG_QC==0]['MLH']
df2['MLH'].fillna(-999, inplace = True)
df2['FLAG_QC'].fillna(-999, inplace = True)

MLH = df2['MLH'].to_xarray()
MLH.attrs["units"] = "m"
MLH.attrs["long_name"] = "mixed layer height"
MLH.attrs["comment"] = "After quality control ; above ground level" 
ds["MLH"] = MLH
ds['MLH'] = ds['MLH'].transpose("time", "station")

ds = ds.rename({"FLAG" : "precip_FLAG"})
ds.precip_FLAG.attrs["units"] = 'range between 0 and 1'
#print(ds['precip_FLAG']) #= 100*np.array(ds['precip_FLAG'])
#print(ds.precip_FLAG.apply(lambda x : 100*x))
FLAG_QC = df2['FLAG_QC'].astype(np.int32).to_xarray()
FLAG_QC.attrs["units"] = '1'
FLAG_QC.attrs["long_name"] = "flag for MLH after quality control"
#ds["FLAG"] = FLAG_QC
ds['FLAG'] = FLAG_QC.transpose("time", "station")

ds.attrs['comment'] = "Mixed layer height after quality control"


repo = git.Repo('/home/mvanhove/STRATfinder/scripts/qc-sf-python/')
sha = repo.head.commit.hexsha
ds.attrs['history'] = f"Git repository : git@gitlab.in2p3.fr:mvanhove/qc-sf-python.git  ;  Version of quality control code : {sha}"
                                
print("MLH replaced, FLAG added, History added")




## CREATE NETCDF L2B

def get_encoding(ds):
    """[get the encoding dictionary ]

    Args:
        ds ([xr.dataset]): [dataset opened ]

    Returns:
        [dict]: [dictionary containing the encoding]
    """    
    
    list_var = list(ds.keys())
    list_dim = list(ds.coords)
    list_var_dim = list_var + list_dim
    encoded = {}
    for elem in list_var_dim:
        encoded[elem]=ds[elem].encoding
    return encoded

ds2 =  xr.open_dataset(day_2)
ds2_enco = get_encoding(ds2)
ds2_enco['time'] = {'calendar' : 'standard', "dtype": "double", '_FillValue': None, 'units' : ds2['time'].encoding['units'] + 'UTC'} # 'long_name' : 'time'}
ds['time'].attrs['long_name'] = 'time'
ds2_enco['MLH'] = {'dtype' : ds2['MLH'].encoding['dtype'], '_FillValue' : "-999"}
ds2_enco['FLAG'] = {'_FillValue' : -999}  
ds = ds.sel(time=slice(day2, day2))
ds = ds.transpose("time", "station") 
ds.to_netcdf(sys.argv[5], encoding=ds2_enco, mode = "w", engine='netcdf4') 

print("output file created")

## CLOSE FILES 

ds.close()

sys.exit(0) 






