#!/usr/bin/env python

import os
import sys
import click
import pathlib
import json
import git
import pwd
import grp
from datetime import date, timedelta, time, datetime

import xarray as xr
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
from pathlib import Path
from solartime import (
    SolarTime,
)  ## to be replaced by pvlib if more problems encountered, works for now

pd.options.mode.chained_assignment = None  ## Warning avoid : ' SettingWithCopyWarning '


__version__ = "1.0.0"
__author__ = "Melania Van Hove"

#################################################################################################################################
#############################################FUNCTIONS############################################################################
#################################################################################################################################


def read_global_attribute_json(json_file: str) -> Dict:
    """Read the json file 

    Args:
        json_file (str): json file to read

    Returns:
        Dict: Contain of the json file 
    """
    with open(json_file, "r") as jsonfile:
        data = json.load(jsonfile)
    return data


def add_to_dict(dict_json: Dict, dict_nc: Dict, list_filt: List) -> Dict:
    """Get the dictionary issued from the json file and add these metadatas 
    into the dict_nc who represents the actuall metadata contains into with 
    the 

    Args:
        dict_json (Dict): dictionary representing the json file contain
        dict_nc (Dict): dictionary representing the nnetcdf contain regarding global attributes 
        list_filt (List): List of attributes to not be picked 

    Returns:
        Dict: The dict_nc with the added global attributes
    """

    for key in dict_json.keys():
        if key not in list_filt:
            dict_nc[key] = dict_json[key]
    return dict_nc


def get_maxmlh(json_file: str) -> str:

    """ Extract the maxmlh from the json configuration file 

    Args:
        json_file (str): json configuration file 

    Returns:
        str : Get the maxmlh from the json file 
    """
    with open(
        json_file, "r"
    ) as jsonfile:  ## configuration file : climatological limit of MLH
        data = json.load(jsonfile)
        maxmlh = data["MLHsettings"]
        maxmlh = maxmlh[0]["dayMax"]
    return maxmlh


def clean_time_array(ds: xr.Dataset) -> xr.Dataset:
    """ Remove the nan in the time index,remove the duplicates and 
    then sort the time dimension in the ascending order, and floor
    the time in minute

    Args:
        ds (xr.dataset): Dataset 

    Returns:
        xr.dataset : cleaned dataset 
    """
    x = ~np.isnan(ds["time"])
    new_time = {"time": x}
    ds = ds.isel(new_time)

    #_, index = np.unique(ds["time"], return_index=True)
    #ds = ds.isel(time=index)
    #ds = ds.sortby("time")
    ds["time"] = ds["time"].dt.floor("min")
    _, index = np.unique(ds["time"], return_index=True)
    ds = ds.isel(time=index)
    ds = ds.sortby("time")
    return ds


def Get_coverage(ds: xr.Dataset, var: str):
    """Get the min and maximum coverage for some variable such as time,latitude 
    or longitude 

    Args:
        ds (xr.Dataset): xarray dataset 
        var (str): variable to chose 

    Returns:
        _type_: min and max values of the variable
    """
    list_var = list(ds.keys())
    list_dim = list(ds.coords)
    list_var_dim = list_var + list_dim
    if var in list_var_dim:
        list_var = list(ds[str(var)])
    else:
        print(
            f"the variable {var} is not in the list_var_dim whose elements are {list_var_dim}"
        )
    return list_var[0], list_var[-1]



def rain_filter(df: pd.DataFrame) -> pd.DataFrame:
    """Remove day (or night) if more than 10% of rain more than 3h in the day (or night)

    Args:
        df (_type_): dataframe

    Returns:
        _type_: flaggued dataframe
    """

    df2 = (
        df[df["time_relSR"] < 1]
        .groupby("day", as_index=False)
        .agg(profn=("prof", lambda x: (pd.to_numeric(x) > 0.1).sum()))
    )  ## profn = number of times prof > 10, grouped by night
    df3 = (
        df[df["time_relSR"] > -1]
        .groupby("day", as_index=False)
        .agg(profd=("prof", lambda x: (pd.to_numeric(x) > 0.1).sum()))
    )  ## profd = number of times prof > 10, grouped by day
    df = (
        df.reset_index().merge(df2, how="left").set_index("time")
    )  ## profn added to main dataframe
    df = (
        df.reset_index().merge(df3, how="left").set_index("time")
    )  ## profn added to main dataframe
    df.FLAG_QC[(df.profd >= 12) & (df.time_relSR > -1)] = (
        df.FLAG_QC + 1
    )  ## if profd >= 12 (=3h) in one day, the day is flaggued
    df.FLAG_QC[(df.profn >= 12) & (df.time_relSR < 1)] = (
        df.FLAG_QC + 1
    )  ## if profn >= 12 (=3h) in one night, the night is flaggued
    
    return df




def day_peaks(df: pd.DataFrame, thresh, time_range, mov_sum_step) -> pd.DataFrame:
    """remove massive increases during daytime in cold seasons

    Args:
        df (_type_): dataframe
        thresh (_type_): threshold (in m) typical of a strong increase

    Returns:
        _type_: flaggued dataframe
    """
    d = df.day == 2
    mov_sum = df['diff'].rolling(mov_sum_step).sum()
    print('day_peaks function with mov_sum_step = ', mov_sum_step)
    cond_increase = (mov_sum > thresh) & (mov_sum < thresh*2)
    cond_decrease = mov_sum < -thresh + 100
    if when == 'end afternoon' :
        df2 = df[(df.time_relSR > 0) & (cond_increase == True) & d & (df.time_relSS >= -3)]
    else :
        df2 = df[(df.time_relSR > 0) & (cond_increase == True) & d]

    l = cond_decrease == True
    t = df["time_relSR"] > 0
    ind = []

    if df2.index.size != 0:
        print('day_peaks activated')
        for idx in df2.index:
            if (df[l & (df.index >= idx) & (df.index <= idx+timedelta(minutes=time_range))].index.min() is not pd.NaT) : #& (df["MLH"][idx] < 2500):
                print('increase during day then decrease within time_range defined')
                a = df[l & (df.index >= idx) & (df.index <= idx+timedelta(minutes=time_range))].index.min()
                ind = ind + df[idx : a + timedelta(minutes=15)].index.to_list()

    df.FLAG_QC[ind] = df.FLAG_QC[ind] + 100
    print(ind)

    return df



def cold_day_dec(df: pd.DataFrame, thresh) -> pd.DataFrame:
    """remove massive increases during daytime in cold seasons

    Args:
        df (_type_): dataframe
        thresh (_type_): threshold (in m) typical of a strong increase

    Returns:
        _type_: flaggued dataframe

    Comments :
        made for 17/03/22 at Lindenberg
    """
    d = df.day == 2
    mov_sum = df['diff'].rolling(2).sum()
    print('cold_day_dec function')
    cond_decrease = mov_sum < thresh
    df2 = df[(df.time_relSR > 0) & (df.time_relSS < -2) & (cond_decrease == True) & d]
    t = df["time_relSR"] > 0
    ind = []
    if df2.index.size != 0:
        print('cold_day_dec activated')
        for idx in df2.index:
            d = df.day == df2.day[idx]
            #definition of the real_mlh = real mlh, ie before the increase 
            if df["MLH"][idx] < 500 :
                real_mlh = 500
            else :
                real_mlh = df["MLH"][idx]
            
            l = df["MLH"] <= real_mlh
            print("real_mlh = ", real_mlh)

            sr = df[df.time_relSR == 0].index.to_list()
            idx_prec = idx - timedelta(minutes=60)
            if df[t & d & l & (df.index < idx_prec)].index.max() is not pd.NaT:
                print('removing from mlh is low enough to idx')
                a = df[d & l & (df.index < idx_prec)].index.max()
                a = a + timedelta(minutes=15)
                ind += df[a:idx].index.to_list()
            else:
                print('removing from sr to idx')
                ind += df[sr:idx].index.to_list()

    df.FLAG_QC[ind] = df.FLAG_QC[ind] + 100
    print(ind)

    return df



def stuck_mlh(df: pd.DataFrame) -> pd.DataFrame:
    """remove stuck low MLH during daytime in warm seasons

    Args:
        df (_type_): dataframe

    Returns:
        _type_: flaggued dataframe
    """
    d = df.day == 2
    daytime = (df.time_relSR > 5) & d
    n_inf_300 = (daytime & (df.MLH < 300)).sum()
    val_mlh1 = (daytime & (df.MLH > 0)).sum()
    if val_mlh1 != 0:
        rap1 = n_inf_300 / val_mlh1
    else:
        rap1 = np.nan

    morning = (df.time_relSR > 0) & (df.time_relSR <= 5) & d
    max_morn = df.MLH[morning].max()
    afternoon = (df.time_relSR > 7) & d
    n_inf_500 = (afternoon & (df.MLH < 500)).sum()
    val_mlh2 = (afternoon & (df.MLH > 0)).sum()
    if val_mlh2 != 0:
        rap2 = n_inf_500 / val_mlh2
    else:
        rap2 = np.nan

    if (rap1 > 0.5) | ((max_morn > 300) & (rap2 > 0.5)):
        df.FLAG_QC[daytime & (df.MLH < 500)] = (
            df.FLAG_QC[daytime & (df.MLH < 500)] + 10
        )  
    return df


def create_df3day(day_1a: Path, day_2a: Path, day_3a: Path) -> pd.DataFrame:
    """create a merged dataframe of the J-1,J and J+1 file 3 cases can happen 


    Args:
        day_1a (str): Path of the J-1 L2A file 
        day_2a (str): Path of the J L2A file 
        day_3a (str): Path of the J+1 L2A file 

    Returns:
        pd.dataframe : merged dataframe of these 3 files 
    """
    isFile1, isFile2, isFile3 = (
        os.path.isfile(day_1a),
        os.path.isfile(day_2a),
        os.path.isfile(day_3a),
    )

    ############### DATAFRAME PREPARED FOR THE END ####################

    df_day_2 = clean_time_array(xr.open_dataset(day_2a)).to_dataframe()
    df_day_2 = df_day_2.reset_index(level=0, drop=True)
    
    ############### AVERAGE 15 MIN ################

    df2 = df_day_2.resample("15min").mean()
    df2 = df2[df2.index.date == df2.index.date[0]]
    df2.index = pd.to_datetime(df2.index.values) + timedelta(minutes=15)
    df2.index = df2.index.set_names(["time"])

    ############### CONSTRUCT DATAFRAME OF 3 DAYS (J-1, J, J+1) IF MISSING VALUES ####################

    day1 = df2.index.date[0] - timedelta(days=1)
    df_id = pd.date_range(day1, day1 + timedelta(days=3), freq="15min").to_frame(
        index=True, name=None
    )
    df_id.index.names = ["time"]
    df_id.drop(index=df_id.index[0], axis=0, inplace=True)

    if isFile1 == True:
        df1 = clean_time_array(xr.open_dataset(day_1a)).to_dataframe()
        df1 = df1.reset_index(level=0, drop=True)
        df1 = df1[df1.index.date == df1.index.date[0]]
        df1 = df1.resample("15min").mean()
        df1.index = pd.to_datetime(df1.index.values) + timedelta(minutes=15)
        df1.index = df1.index.set_names(["time"])
    else:
        df1 = None
        print(f"{day_1a} n'existe pas et est remplacé par un dataframe vide")
    if isFile3 == True:
        df3 = clean_time_array(xr.open_dataset(day_3a)).to_dataframe()
        df3 = df3.reset_index(level=0, drop=True)
        df3 = df3.resample("15min").mean()
        df3.index = pd.to_datetime(df3.index.values) + timedelta(minutes=15)
        df3.index = df3.index.set_names(["time"])
    else:
        df3 = None
        print(f"{day_3a} n'existe pas et est remplacé par un dataframe vide")

    df = pd.concat([df1, df2, df3])
    df = pd.merge(df, df_id, how="right", right_index=True, left_index=True)
    return df




def residual_layer(df: pd.DataFrame, thresh1, thresh2, thresh3) -> pd.DataFrame:
    """Remove residual layer (night)

    Args:
        df (_type_): dataframe
        thresh1 : threshold above which MLH is detected 
        thresh2 : amount needed of MLH above thresh1 to be considered as residual layer (between 0 and 1)
        thresh3 : threshold above which MLH is removed

    Returns:
        _type_: flaggued dataframe
    """
    ii = (df.time_relSS > 2) & (df.time_relSR < 2)
    df2 = (
        df[ii]
        .groupby("day", as_index=False)
        .agg(
            mM=(
               "MLH",
                lambda x: (x > thresh1).sum() / (x > 0).sum()
                if (x > 0).sum() != 0
                else None,
            )
        )
    )
    llcheck = list(df2.day[df2.mM > thresh2])
    if llcheck != []:
        for d in llcheck:
            df.FLAG_QC[(df.time_relSR < 3) & (df.day == d) & (df.MLH > thresh3)] = (
                df.FLAG_QC[(df.time_relSR < 3) & (df.day == d) & (df.MLH > thresh3)]
                + 10000
            )
    return df



def rel_residual_layer(df: pd.DataFrame, frac_max) -> pd.DataFrame:
    """Remove residual layer (night)

    Args:
        df (_type_): dataframe
        frac_max (_type_) : fraction considered of the maximum of daytime (scalar between 0 and 1) 
       
    Returns:
        _type_: flaggued dataframe
    """
    d1 = df.day == 1
    d2 = df.day == 2
    d3 = df.day == 3
    max_d1 = df.MLH[d1 & (df.time_relSR > 4)].max() 
    df.FLAG_QC[(df.time_relSR < 0) & d2 & (df.MLH > frac_max*max_d1)] = (
        df.FLAG_QC[(df.time_relSR < 0) & d2 & (df.MLH > frac_max*max_d1)]
        + 10000
        )

    max_d2 = df.MLH[d2 & (df.time_relSR > 4)].max() 
    df.FLAG_QC[(df.time_relSR < 0) & d3 & (df.MLH > frac_max*max_d2)] = (
        df.FLAG_QC[(df.time_relSR < 0) & d3 & (df.MLH > frac_max*max_d2)]
        + 10000
        )

    return df






def extreme(df: pd.DataFrame, frac_maxmlh, maxmlh) -> pd.DataFrame:
    """Remove extreme points in winter 

    Args:
        df (_type_): dataframe
        frac_maxmlh : fraction of the maxmlh considered as the threshold (scalar between 0 and 1)
        maxmlh : maximum MLH set in config file (scalar)

    Returns:
        _type_: flaggued dataframe
    """
    df.FLAG_QC[(df.MLH > (frac_maxmlh * maxmlh))] = (
            df.FLAG_QC[(df.MLH > (frac_maxmlh * maxmlh))]
            + 100
        )
    return df



def massive_dec_night(df: pd.DataFrame, thresh, time_thresh) -> pd.DataFrame:
    """remove preceding layer after a massive decrease at night

    Args:
        df (_type_): dataframe
        thresh (_type_): threshold typical of a strong decrease (absolute value in m) (scalar)
        time_thresh (_type_) : time range considered to identify a decrease (in time steps) (scalar)

    Returns:
        _type_: flaggued dataframe
    """
    d = (df.day == 2) | (df.day == 3)
    mov_sum = df['diff'][d].rolling(time_thresh).sum()
    cond_decrease = mov_sum < thresh
    df2 = df[(df.time_relSR <= 1) & d & (cond_decrease==True)]
    t = df["time_relSS"] > 2
    ind = []

    if df2.index.size > 0:
        print('massive_dec_night activated with thresh = ', thresh)
        for idx in df2.index:
            d = df.day == df2.day[idx]
            if df["MLH"][idx] < 300 :
                nl_mlh = 300
            else :
                nl_mlh = df["MLH"][idx]
            
            l = df["MLH"] <= nl_mlh + 100
            print("nl_mlh = ", nl_mlh, " and  df['MLH'][idx] = ", df["MLH"][idx])

            ss = df.time_relSR[d].idxmin()
            idx_prec = idx - timedelta(minutes=60)
            if df[t & d & l & (df.index < idx_prec)].index.max() is not pd.NaT:
                print('removing from mlh is low enough to idx')
                a = df[d & l & (df.index < idx_prec)].index.max()
                a = a + timedelta(minutes=15)
                ind += df[a:idx].index.to_list()

            else:
                print('removing from ss to idx')
                ind += df[ss:idx].index.to_list()

    df["FLAG_QC"][ind] = df["FLAG_QC"][ind] + 100
    print(ind)

    return df




def massive_inc_night(df: pd.DataFrame, thresh, time_thresh) -> pd.DataFrame:
    """remove following layer after a massive increase at night

    Args:
        df (pd.DataFrame): dataframe
        thresh (_type_): threshold (in m) typical of a strong increase
        time_thresh (_type_) : time range considered to identify a decrease (in time steps) (scalar)

    Returns:
        pd.DataFrame: flaggued dataframe
    """
    d = (df.day == 2) | (df.day == 3)
    print("start massive_inc_night with thresh = ", thresh)
    mov_sum = df['diff'][d].rolling(time_thresh).sum()
    cond_increase = mov_sum > thresh
    df2 = df[(df.time_relSR <= 1) & d & (cond_increase==True)]
    t = df["time_relSR"] < 4
    ind = []

    if df2.index.size > 0:
        print('massive_inc_night activated with thresh = ', thresh)
        for idx in df2.index:
            d = df.day == df2.day[idx]
            nl_mlh = df["MLH"][idx] - mov_sum[idx]
            if nl_mlh < 300 :
                nl_mlh = 300
            l = df["MLH"] <= nl_mlh
            print("nl_mlh = ", nl_mlh, " and  df['MLH'][idx] = ", df["MLH"][idx])

            idx_last = df[(df.time_relSR == 4) & d].index.to_list()

            if (
                df[d & t & l & (df.index > idx)].index.min() is not pd.NaT
            ):  # increase followed by decrease
                print("increase followed by decrease")
                a = df[d & t & l & (df.index > idx)].index.min()
                #a = a - timedelta(minutes=15)
                ind += df[idx:a].index.to_list()

            else:  # all layer is overestimated
                ind = ind + df[idx : idx_last[0]].index.to_list()

    df["FLAG_QC"][ind] = df["FLAG_QC"][ind] + 100
    print(ind)

    return df




def dip_afternoon(df, thresh, time_thresh):
    """remove following layer after a massive increase at night

    Args:
        df (pd.DataFrame): dataframe
        thresh (_type_): threshold (in m) typical of a increase/decrease
        time_thresh (_type_) : time range considered to identify an increase/decrease (in time steps) (scalar)

    Returns:
        pd.DataFrame: flaggued dataframe
    """
    d = df.day == 2
    mov_sum = df['diff'][d].rolling(time_thresh).sum()
    cond_increase = mov_sum > thresh*.5
    cond_decrease = mov_sum < -thresh
    df2 = df[(df.time_relSR > 4) & (cond_decrease==True) & d]
    t = df["time_relSR"] > 0

    ind = []
    if df2.index.size != 0:
        print('dip afternoon activated')
        for idx in df2.index:
            if (
                df[d & t & ((cond_increase)==True) & (df.index > idx)].index.max() is not pd.NaT   # decrease followed by increase
            ):  
                a = df[d & t & (cond_increase)==True & (df.index > idx)].index.max()
                ind += df[idx:a + timedelta(minutes=15)].index.to_list()
                print('decrease followed by increase')
    
    mov_sum = df['diff'][d].rolling(1).sum()
    test = mov_sum[(mov_sum.shift(-1) > 0) & (mov_sum.shift(0) < 0)]    
    test_index = test[(df.time_relSR > 4) & d].index.to_list()

    for idx in test_index :
        if (
            ~mov_sum[(mov_sum.index > idx) & (mov_sum.index < idx+timedelta(minutes=120)) & (mov_sum.values < -100)].any() & 
            ~mov_sum[(mov_sum.index < idx) & (mov_sum.index > idx-timedelta(minutes=120)) & (mov_sum.values > 100)].any() &
            (mov_sum[(mov_sum.index > idx) & (mov_sum.index < idx+timedelta(minutes=120))].sum() > thresh*.5) &
            (mov_sum[(mov_sum.index <= idx) & (mov_sum.index > idx-timedelta(minutes=120))].sum() < -thresh*.5)
        ) :
            ind += df[idx-timedelta(minutes=180):idx+timedelta(minutes=180)].index.to_list()
            print('local minimum detected')
    
    df.FLAG_QC[ind] = df.FLAG_QC[ind] + 100
    print(ind)
    return df


def massive_inc_afternoon(df, thresh, time_thresh, time_bef_ss):
    """remove following layer after a massive increase at night

    Args:
        df (pd.DataFrame): dataframe
        thresh (_type_): threshold (in m) typical of a strong increase
        time_thresh (_type_) : time relative to sunset from which to consider increase (in hour) (scalar) 

    Returns:
        pd.DataFrame: flaggued dataframe
    """
    d = df.day == 2
    mov_sum = df['diff'].rolling(time_thresh).sum()
    cond_increase = mov_sum > thresh
    cond_decrease = mov_sum < -thresh
    cond_stag = mov_sum < 200
    t = (df.time_relSS > -time_bef_ss) & ((df.time_relSR >= 0))
    df2 = df[t & (cond_increase==True) & d]
    ind = []
    if df2.index.size != 0:
        print('massive increase in end of afternoon activated')
        for idx in df2.index:
            if (
                (df[(df.index <= idx) & (df.index >= idx - timedelta(minutes=180)) & (cond_stag == False)].any() == False)
                & (df[(df.index <= idx) & (df.index >= idx - timedelta(minutes=180)) & (cond_stag == False)].index.max() is not pd.NaT)         
            ) :
                print('strong increase preceded by stagnation or decrease')
                a = df[(df.index <= idx) & (df.index >= idx - timedelta(minutes=300)) & (cond_decrease == True)].index.max()
                a = a - timedelta(minutes=60)
                ind += df[a:idx].index.to_list()


            elif df[(df.index >= idx) & (cond_decrease == True) & d].index.min() is not pd.NaT :
                print('strong increase followed by decrease')
                a = df[(df.index >= idx) & (cond_decrease == True) & d].index.min()
                a = a + timedelta(minutes=60)
                ind += df[idx:a].index.to_list()


            elif df[(time_bef_ss == 2) & (df.time_relSS == 0.5) & (df.index > idx)].index.min() is not pd.NaT :
                print('strong increase at the very end of the day, only considered in summer')
                idx = df2.index[0]
                a = df[(df.time_relSS == 0.5) & (df.index > idx)].index.min()
                ind += df[idx:a].index.to_list()

    df.FLAG_QC[ind] = df.FLAG_QC[ind] + 100
    print(ind)

    return df
<<<<<<< HEAD




def get_encoding(ds: xr.Dataset) -> Dict:
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
        encoded[elem] = ds[elem].encoding
    return encoded
=======




def get_encoding(ds: xr.Dataset) -> Dict:
    """[get the encoding dictionary ]

    Args:
        ds ([xr.dataset]): [dataset opened ]

    Returns:
        [dict]: [dictionary containing the encoding]
    """
>>>>>>> develop

    list_var = list(ds.keys())
    list_dim = list(ds.coords)
    list_var_dim = list_var + list_dim
    encoded = {}
    for elem in list_var_dim:
        encoded[elem] = ds[elem].encoding
    return encoded

def conv_np64dt_to_dt(time_np64: np.datetime64) -> datetime.utcfromtimestamp:
    """" Convert np.datetime64 to datetime.

<<<<<<< HEAD
    Args:
        time_np64 (np.datetime64): 

    Returns:
        datetime.datetime: Converted time to the datetime.datetime class
    """
    ts = (time_np64 - np.datetime64("1970-01-01T00:00:00Z")) / np.timedelta64(1, "s")
    ts = datetime.utcfromtimestamp(ts)
    return ts

def Change_dims(ds:xr.Dataset) -> xr.Dataset :
    """Change the type of station_name and platform_id from char to string, and
        erase the station dimension and replace it by station_name. 

    Args:
        ds (xr.Dataset): dataset to read

    Returns:
        xr.Dataset: _dataset with naw dimension 
    """    
    ds["station_name"] = ds["station_name"].astype(str)
    ds["platform_id"] = ds["platform_id"].astype(str)
    ds = ds.squeeze(dim="station")
    ds = ds.drop_vars("station")
    ds = ds.expand_dims(dim="station_name")
    ds = ds.assign_coords({"station_name":ds["station_name"]})
    ds = ds.transpose()
    return ds 

=======
def conv_np64dt_to_dt(time_np64: np.datetime64) -> datetime.utcfromtimestamp:
    """" Convert np.datetime64 to datetime.

    Args:
        time_np64 (np.datetime64): 

    Returns:
        datetime.datetime: Converted time to the datetime.datetime class
    """
    ts = (time_np64 - np.datetime64("1970-01-01T00:00:00Z")) / np.timedelta64(1, "s")
    ts = datetime.utcfromtimestamp(ts)
    return ts

def Change_dims(ds:xr.Dataset) -> xr.Dataset :
    """Change the type of station_name and platform_id from char to string, and
        erase the station dimension and replace it by station_name. 

    Args:
        ds (xr.Dataset): dataset to read

    Returns:
        xr.Dataset: _dataset with naw dimension 
    """    
    ds["station_name"] = ds["station_name"].astype(str)
    ds["platform_id"] = ds["platform_id"].astype(str)
    ds = ds.squeeze(dim="station")
    ds = ds.drop_vars("station")
    ds = ds.expand_dims(dim="station_name")
    ds = ds.assign_coords({"station_name":ds["station_name"]})
    ds = ds.transpose()
    return ds 
>>>>>>> develop

    #################################################################################################################################
    ############################################# END FUNCTIONS######################################################################
    #################################################################################################################################

    #################################################################################################################################
    ############################################# END FUNCTIONS######################################################################
    #################################################################################################################################





<<<<<<< HEAD
############### CHECK IF ARGUMENTS ARE READABLE/WRITABLE ################
=======
>>>>>>> develop

############### CHECK IF ARGUMENTS ARE READABLE/WRITABLE ################

<<<<<<< HEAD
@click.command()
# File of day -1 L2A file
@click.argument(
    "day_1a",
    nargs=1,
    type=click.Path(
        exists=False, readable=True, file_okay=True, dir_okay=False, resolve_path=True
    ),
)
# File of d day  L2A file
@click.argument(
    "day_2a",
    nargs=1,
    type=click.Path(
        exists=True, readable=True, file_okay=True, dir_okay=False, resolve_path=True
    ),
)
# File of day + 1 L2A file
@click.argument(
    "day_3a",
    nargs=1,
    type=click.Path(
        exists=False, readable=True, file_okay=True, dir_okay=False, resolve_path=True
    ),
)
# Configuration of the configuration json file
@click.argument(
    "config_filea",
    nargs=1,
    type=click.Path(
        exists=True, readable=True, file_okay=True, dir_okay=False, resolve_path=True
    ),
)
# Output file to create the L2B files
@click.argument(
    "output_day2a",
    nargs=1,
    type=click.Path(
        exists=False, writable=True, file_okay=True, dir_okay=False, resolve_path=True
    ),
)



################ MAIN FUNCTION ###################

def main(
    day_1a: click.Path,
    day_2a: click.Path,
    day_3a: click.Path,
    config_filea: click.Path,
    output_day2a: click.Path,
) -> None:

    ## CHECK IF FILES 
    click.echo(click.format_filename(day_1a))
    click.echo(click.format_filename(day_2a))
    click.echo(click.format_filename(day_3a))
    click.echo(config_filea)
    click.echo(click.format_filename(output_day2a))

    ## CONFIGURATION
    today = date.today()
    date_today = today.strftime("%B %d, %Y")
    maxmlh = get_maxmlh(config_filea)
    print(f"Read the file {config_filea}")
    df = create_df3day(day_1a, day_2a, day_3a)
    print("complete dataframe created")
    ndata_day2 = int(len(df) / 3)

    with xr.open_dataset(day_2a) as ds:
        site = ds.attrs["site_location"]  ## site name given in L2A by E-PROFILE
        month2 = ds["time"].dt.month[0].values
        warm = (month2 > 3) & (month2 < 10)
        summer = (month2 > 5) & (month2 < 9)
        lat = ds["station_latitude"][0].values
        lon = ds["station_longitude"][0].values
        ds = clean_time_array(ds)
        df_day_2 = ds.to_dataframe()
        df_day_2 = df_day_2.reset_index(level=0, drop=True)
        df_day_2 = df_day_2[~df_day_2.index.duplicated(keep="first")]
        df_day_2 = df_day_2.loc[df_day_2.index.dropna()]

        day_today = conv_np64dt_to_dt(ds["time"][0].values)
        day0 = day_today - timedelta(days=2) 
        day1 = (day_today - timedelta(days=1)).isoformat()[0:10]
        day2 = day_today.isoformat()[0:10]
        day3 = (day_today + timedelta(days=1)).isoformat()[0:10]
        day4 = (day_today + timedelta(days=2)).isoformat()[0:10]

        print(
            "Site = ",
            site,
            ", lat = ",
            lat,
            ", lon = ",
            lon,
            ", JourJ = ",
            day2,
            ", Jour J-1 = ",
            day1,
            ", Jour J+1 = ",
            day3,
        )

        ## RENAME COLUMNS TO SIMPLIFY

        df = df.rename(columns={"FLAG": "prof"})
        df = df.rename(columns={"cloud_base_altitude": "CBH"})


        ## TIME RELATIVE TO SUNRISE/SUNSET

        sun = SolarTime()
        date_ = date(day0.year, day0.month, day0.day)
        sunrise, sunset = [], []

        for i in range(
            5
        ):  ## 5 : because we need SR & SS at day J-2, J-1, J, J+1 et J+2
            schedule = sun.sun_utc(date_, lat, lon)

            sunrise1 = (
                schedule["sunrise"].second
                + 60 * schedule["sunrise"].minute
                + 3600 * schedule["sunrise"].hour
            ) / 3600.0  ## sunrise in hour
            sunrise1 = 0.25 * (round(4.0 * sunrise1))  ## round to closer quarter hour

            sunset1 = (
                schedule["sunset"].second
                + 60 * schedule["sunset"].minute
                + 3600 * schedule["sunset"].hour
            ) / 3600.0  ## sunset in hour
            sunset1 = 0.25 * (round(4.0 * sunset1))  ## round to closer quarter hour

            sunrise.append(sunrise1)
            sunset.append(sunset1)
            date_ = date_ + timedelta(days=1)
=======

@click.command()
# File of day -1 L2A file
@click.argument(
    "day_1a",
    nargs=1,
    type=click.Path(
        exists=False, readable=True, file_okay=True, dir_okay=False, resolve_path=True
    ),
)
# File of d day  L2A file
@click.argument(
    "day_2a",
    nargs=1,
    type=click.Path(
        exists=True, readable=True, file_okay=True, dir_okay=False, resolve_path=True
    ),
)
# File of day + 1 L2A file
@click.argument(
    "day_3a",
    nargs=1,
    type=click.Path(
        exists=False, readable=True, file_okay=True, dir_okay=False, resolve_path=True
    ),
)
# Configuration of the configuration json file
@click.argument(
    "config_filea",
    nargs=1,
    type=click.Path(
        exists=True, readable=True, file_okay=True, dir_okay=False, resolve_path=True
    ),
)
# Output file to create the L2B files
@click.argument(
    "output_day2a",
    nargs=1,
    type=click.Path(
        exists=False, writable=True, file_okay=True, dir_okay=False, resolve_path=True
    ),
)



################ MAIN FUNCTION ###################

def main(
    day_1a: click.Path,
    day_2a: click.Path,
    day_3a: click.Path,
    config_filea: click.Path,
    output_day2a: click.Path,
) -> None:

    ## CHECK IF FILES 
    click.echo(click.format_filename(day_1a))
    click.echo(click.format_filename(day_2a))
    click.echo(click.format_filename(day_3a))
    click.echo(config_filea)
    click.echo(click.format_filename(output_day2a))

    ## CONFIGURATION
    today = date.today()
    date_today = today.strftime("%B %d, %Y")
    maxmlh = get_maxmlh(config_filea)
    print(f"Read the file {config_filea}")
    df = create_df3day(day_1a, day_2a, day_3a)
    print("complete dataframe created")
    ndata_day2 = int(len(df) / 3)

    with xr.open_dataset(day_2a) as ds:
        site = ds.attrs["site_location"]  ## site name given in L2A by E-PROFILE
        month2 = ds["time"].dt.month[0].values
        warm = (month2 > 3) & (month2 < 10)
        summer = (month2 > 5) & (month2 < 9)
        lat = ds["station_latitude"][0].values
        lon = ds["station_longitude"][0].values
        ds = clean_time_array(ds)
        df_day_2 = ds.to_dataframe()
        df_day_2 = df_day_2.reset_index(level=0, drop=True)
        df_day_2 = df_day_2[~df_day_2.index.duplicated(keep="first")]
        df_day_2 = df_day_2.loc[df_day_2.index.dropna()]

        day_today = conv_np64dt_to_dt(ds["time"][0].values)
        day0 = day_today - timedelta(days=2) 
        day1 = (day_today - timedelta(days=1)).isoformat()[0:10]
        day2 = day_today.isoformat()[0:10]
        day3 = (day_today + timedelta(days=1)).isoformat()[0:10]
        day4 = (day_today + timedelta(days=2)).isoformat()[0:10]

        print(
            "Site = ",
            site,
            ", lat = ",
            lat,
            ", lon = ",
            lon,
            ", JourJ = ",
            day2,
            ", Jour J-1 = ",
            day1,
            ", Jour J+1 = ",
            day3,
        )

        ## RENAME COLUMNS TO SIMPLIFY

        df = df.rename(columns={"FLAG": "prof"})
        df = df.rename(columns={"cloud_base_altitude": "CBH"})


        ## TIME RELATIVE TO SUNRISE/SUNSET

        sun = SolarTime()
        date_ = date(day0.year, day0.month, day0.day)
        sunrise, sunset = [], []

        for i in range(
            5
        ):  ## 5 : because we need SR & SS at day J-2, J-1, J, J+1 et J+2
            schedule = sun.sun_utc(date_, lat, lon)

            sunrise1 = (
                schedule["sunrise"].second
                + 60 * schedule["sunrise"].minute
                + 3600 * schedule["sunrise"].hour
            ) / 3600.0  ## sunrise in hour
            sunrise1 = 0.25 * (round(4.0 * sunrise1))  ## round to closer quarter hour

            sunset1 = (
                schedule["sunset"].second
                + 60 * schedule["sunset"].minute
                + 3600 * schedule["sunset"].hour
            ) / 3600.0  ## sunset in hour
            sunset1 = 0.25 * (round(4.0 * sunset1))  ## round to closer quarter hour
>>>>>>> develop

            sunrise.append(sunrise1)
            sunset.append(sunset1)
            date_ = date_ + timedelta(days=1)


        ## COLUMNS 'time_relSR' : time relative to sunrise; 'time_relSS' : time relative to sunset; 'day' : from sunset to sunset

<<<<<<< HEAD
        Time = [i / 4.0 for i in range(1, ndata_day2 + 1)]
        dt = []

        for j in range(1, len(sunrise) - 1):
            for i in range(ndata_day2):
                if Time[i] < sunset[j]:
                    dt.append(Time[i] - sunrise[j])
                else:
                    dt.append(-(24 - Time[i] + sunrise[j + 1]))

        df.insert(2, "time_relSR", dt)

        ss = []
        for j in range(len(sunset) - 2):
            for i in range(ndata_day2):
                if Time[i] < sunrise[j]:
                    ss.append((24 - sunset[j] + Time[i]))
                else:
                    ss.append(Time[i] - sunset[j + 1])

        df.insert(3, "time_relSS", ss)

        n = 1
        df.insert(4, "day", 0)
        for i in df.index:
            if df.at[i, "time_relSS"] == 0:
                df.at[i, "day"] = n + 1
                n = n + 1
            else:
                df.at[i, "day"] = n

        print("Time relative to SR, SS, and day relative to SS done")

=======
        ## COLUMNS 'time_relSR' : time relative to sunrise; 'time_relSS' : time relative to sunset; 'day' : from sunset to sunset

        Time = [i / 4.0 for i in range(1, ndata_day2 + 1)]
        dt = []

        for j in range(1, len(sunrise) - 1):
            for i in range(ndata_day2):
                if Time[i] < sunset[j]:
                    dt.append(Time[i] - sunrise[j])
                else:
                    dt.append(-(24 - Time[i] + sunrise[j + 1]))

        df.insert(2, "time_relSR", dt)

        ss = []
        for j in range(len(sunset) - 2):
            for i in range(ndata_day2):
                if Time[i] < sunrise[j]:
                    ss.append((24 - sunset[j] + Time[i]))
                else:
                    ss.append(Time[i] - sunset[j + 1])

        df.insert(3, "time_relSS", ss)

        n = 1
        df.insert(4, "day", 0)
        for i in df.index:
            if df.at[i, "time_relSS"] == 0:
                df.at[i, "day"] = n + 1
                n = n + 1
            else:
                df.at[i, "day"] = n

        print("Time relative to SR, SS, and day relative to SS done")
>>>>>>> develop

        ## FLAG COLUMN

<<<<<<< HEAD
        df.insert(5, "FLAG_QC", 0)
=======
        ## FLAG COLUMN
>>>>>>> develop

        df.insert(5, "FLAG_QC", 0)




<<<<<<< HEAD
        ######## FILTERS #########


        ## RAIN

        # df['MLH'] = np.where(df.prof > 0,np.nan,df.MLH) #useless because MLH already NaN where prof > 0 ; moreover, with 15min averaging, some existing MLH might become NaN and therefore 'invisible' for next filters (case for 19/12/20)
        df[(df.index.day == 15)][60:90]["MLH"]
        df = rain_filter(df)
        df[(df.index.day == 15)][60:90]["MLH"]
        print("filter Rain done")
=======

        ######## FILTERS #########


        ## RAIN
>>>>>>> develop

        # df['MLH'] = np.where(df.prof > 0,np.nan,df.MLH) #useless because MLH already NaN where prof > 0 ; moreover, with 15min averaging, some existing MLH might become NaN and therefore 'invisible' for next filters (case for 19/12/20)
        df[(df.index.day == 15)][60:90]["MLH"]
        df = rain_filter(df)
        df[(df.index.day == 15)][60:90]["MLH"]
        print("filter Rain done")

        ##REMOVE STUCK MLH AT DAY/WARM SEASONS

<<<<<<< HEAD
        if (site != "LERWICK,UK") & (warm == True):
            df = stuck_mlh(df)
        print("filter Stuck MLH done")


        ## CHECK FOR MASSIVE INCREASE/DECREASE AT NIGHT IN 9H MAX

        # differences between consecutive mlh (taking NaN into account)
        df["diff"] = df["MLH"].diff()
        d = (df.day == 2) | (df.day == 3)
        df[d]["diff"] = df[d]["MLH"].diff()
        idx = df[np.isnan(df["diff"]) == True].index.to_list()
        for i in idx:
            idx2 = df[df.index < i].MLH.last_valid_index()
            if idx2 is not None:
                if (i - idx2) < timedelta(hours=9):
                    df["diff"][i] = df.MLH[i] - df.MLH[idx2]

        
        df = massive_inc_night(df, 250, 1)  
        df = massive_inc_night(df, 400, 4)  
        df = massive_dec_night(df, -250, 1)     
        df = massive_dec_night(df, -400, 4)
        
        print("filter Massive decrease/increase at night done")

        ## CHECK FOR MASSIVE INCREASE/DECREASE AT DAY IN 2H MAX

        # differences between consecutive mlh (taking NaN into account)
        df["diff"] = df["MLH"].diff()
=======
        ##REMOVE STUCK MLH AT DAY/WARM SEASONS

        if (site != "LERWICK,UK") & (warm == True):
            df = stuck_mlh(df)
        print("filter Stuck MLH done")


        ## CHECK FOR MASSIVE INCREASE/DECREASE AT NIGHT IN 9H MAX

        # differences between consecutive mlh (taking NaN into account)
        df["diff"] = df["MLH"].diff()
        d = (df.day == 2) | (df.day == 3)
        df[d]["diff"] = df[d]["MLH"].diff()
>>>>>>> develop
        idx = df[np.isnan(df["diff"]) == True].index.to_list()
        for i in idx:
            idx2 = df[df.index < i].MLH.last_valid_index()
            if idx2 is not None:
<<<<<<< HEAD
                if (i - idx2) <= timedelta(minutes=120):
                    df["diff"][i] = df.MLH[i] - df.MLH[idx2]

        if warm == False:
            df = day_peaks(df, 1000, 180, 4, 'all day')
            df = day_peaks(df, 400, 120, 3, 'all day')
            df = cold_day_dec(df, -1500)
        else:  
            df = day_peaks(df, 500, 180, 'end afternoon') # 1000m instead of 500m because was removing 06/02/22 in Granada 
            df = day_peaks(df, 400, 120, 'all day')

        if summer == True :
            df = massive_inc_afternoon(df, 500, 2, 2) #2 or 4 ? might apply this in winter because of 13/02/22 Granada, 06/03/22,  
        else :
            df = massive_inc_afternoon(df, 500, 4, 4)
        
        print("filter Massive Increase/decrease at day done")

       
        df = dip_afternoon(df, 1000, 4)
        
    
        ## EXTREME POINTS

        if (month2 < 3) | (month2 > 11):
            df = extreme(df,0.75,maxmlh)
        else :
            df = extreme(df,1,maxmlh)
        print("filter Extreme points done")

=======
                if (i - idx2) < timedelta(hours=9):
                    df["diff"][i] = df.MLH[i] - df.MLH[idx2]

        
        df = massive_inc_night(df, 250, 1)  
        df = massive_inc_night(df, 400, 4)  
        df = massive_dec_night(df, -250, 1)     
        df = massive_dec_night(df, -400, 4)
        
        print("filter Massive decrease/increase at night done")

        ## CHECK FOR MASSIVE INCREASE/DECREASE AT DAY IN 2H MAX

        # differences between consecutive mlh (taking NaN into account)
        df["diff"] = df["MLH"].diff()
        idx = df[np.isnan(df["diff"]) == True].index.to_list()
        for i in idx:
            idx2 = df[df.index < i].MLH.last_valid_index()
            if idx2 is not None:
                if (i - idx2) <= timedelta(minutes=120):
                    df["diff"][i] = df.MLH[i] - df.MLH[idx2]

        if warm == False:
            df = day_peaks(df, 1000, 180, 4)
            df = day_peaks(df, 400, 120, 3)
            df = cold_day_dec(df, -1500)
        else:  
            df = day_peaks(df, 500, 180, 4) # 1000m instead of 500m because was removing 06/02/22 in Granada 
            df = day_peaks(df, 400, 120, 3)

        if summer == True :
            df = massive_inc_afternoon(df, 500, 2, 2) #2 or 4 ? might apply this in winter because of 13/02/22 Granada, 06/03/22,  
        else :
            df = massive_inc_afternoon(df, 500, 4, 4)
        
        print("filter Massive Increase/decrease at day done")

       
        df = dip_afternoon(df, 1000, 4)
        
    
        ## EXTREME POINTS

        if (month2 < 3) | (month2 > 11):
            df = extreme(df,0.75,maxmlh)
        else :
            df = extreme(df,1,maxmlh)
        print("filter Extreme points done")
>>>>>>> develop

        ## RESIDUAL LAYER

<<<<<<< HEAD
      

        if warm == True:
            df = residual_layer(df,800,0.75,600)
            df = rel_residual_layer(df, 1)
        else:
            df = residual_layer(df,600,0.5,500)
            df = rel_residual_layer(df, 1.5)

        print("filter Residual layer done")

        ######## END FILTERS #########

        ######## CHANGE FLAG_QC IN 1MIN FREQUENCE #########

        df_day_2["FLAG_QC"] = 0
        df = df[
            (df.index.date == date.fromisoformat(day2))
            | (df.index.time == time(0, 0, 0))
        ]
        df = df[: len(df) - 1]
        a = df.index[len(df) - 1]
        b = a - timedelta(milliseconds=1)
        df.rename(index={a: b}, inplace=True)

        for i in range(1, len(df)):
            df_day_2.loc[
                (
                    (df_day_2.index.time <= df.index.time[i])
                    & (df_day_2.index.time >= df.index.time[i - 1])
                ),
                "FLAG_QC",
            ] = df.FLAG_QC[i]

        ######## PREPARE L2A DATAFRAME TO BE FILLED WITH NEW FLAG_QC AND THEREFORE NEW MLH #########

        df2 = clean_time_array(xr.open_dataset(day_2a)).to_dataframe()
     
        df2["FLAG_QC"] = list(df_day_2["FLAG_QC"].astype(int))
        df2["FLAG_QC"] = df2["FLAG_QC"][np.isnan(df2["MLH"]) == False]
        df2["MLH"] = df2[df2.FLAG_QC == 0]["MLH"]
        df2["MLH"].fillna(-999, inplace=True)
        df2["FLAG_QC"].fillna(-999, inplace=True)

        MLH = df2["MLH"].to_xarray()
        MLH.attrs["units"] = "m"
        MLH.attrs["long_name"] = "mixed layer height"
        MLH.attrs["comment"] = "After quality control ; above ground level"
        ds["MLH"] = MLH.transpose("time", "station")
        
        ds = ds.rename({"FLAG": "precip_FLAG"})
        ds.precip_FLAG.attrs["units"] = "range between 0 and 1"

        FLAG_QC = df2["FLAG_QC"].astype(np.int32).to_xarray()
        FLAG_QC.attrs["units"] = "1"
        FLAG_QC.attrs["long_name"] = "flag for MLH after quality control"
        ds["FLAG"] = FLAG_QC.transpose("time", "station")

        ds.attrs["comment"] = "Mixed layer height after quality control; Git repository : git@gitlab.in2p3.fr:ipsl/sirta/mld/stratfinder/qc-sf-python.git"
        
        ## add history in output file 
        dir_path = os.path.dirname(os.path.realpath(f"{sys.argv[0]}"))
        repo = git.Repo(f"{dir_path}")
        sha = repo.head.commit.hexsha
        ds.attrs[
            "history"
        ] = f"Version of quality control code : {sha} ; date of creation : {date_today}"

        print("MLH replaced, FLAG added, History added")

        
        ######## PREPARE L2A DATASET TO BE FILLED WITH NEW VARIABLES #########
        
        ds2 = xr.open_dataset(day_2a)
        ds2_enco = get_encoding(ds2)
        ds2_enco["time"] = {
            "calendar": "standard",
            "dtype": "double",
            "_FillValue": None,
        }  
        
        ds2_enco["MLH"] = {"dtype": ds2["MLH"].encoding["dtype"], "_FillValue": "-999"}
        ds2_enco["FLAG"] = {"_FillValue": -999}
        del ds2_enco["station"]

        uid = pwd.getpwnam("eprofile").pw_uid
        gid = grp.getgrnam("eprofile").gr_gid
        ds = ds.sel(time=slice(day2, day2))
        ds = Change_dims(ds)
        ds2_enco["platform_id"] = ds["platform_id"].encoding
        ds2_enco["station_name"] = ds["station_name"].encoding
        ds.time.encoding["units"] = ds2["time"].encoding["units"] + "UTC"
        ds.time.attrs["long_name"] = "time"
        ds.to_netcdf(output_day2a, encoding=ds2_enco, mode="w", engine="netcdf4", unlimited_dims=["time","station_name"])

        os.chmod(output_day2a, 0o644)
        os.chown(output_day2a, uid, gid)
        print(f"output file created : {output_day2a}")

        ## CLOSE FILES
    return 0
=======
        ## RESIDUAL LAYER

      

        if warm == True:
            df = residual_layer(df,800,0.75,600)
            df = rel_residual_layer(df, 1)
        else:
            df = residual_layer(df,600,0.5,500)
            df = rel_residual_layer(df, 1.5)

        print("filter Residual layer done")

        ######## END FILTERS #########

        ######## CHANGE FLAG_QC IN 1MIN FREQUENCE #########

        df_day_2["FLAG_QC"] = 0
        df = df[
            (df.index.date == date.fromisoformat(day2))
            | (df.index.time == time(0, 0, 0))
        ]
        df = df[: len(df) - 1]
        a = df.index[len(df) - 1]
        b = a - timedelta(milliseconds=1)
        df.rename(index={a: b}, inplace=True)

        for i in range(1, len(df)):
            df_day_2.loc[
                (
                    (df_day_2.index.time <= df.index.time[i])
                    & (df_day_2.index.time >= df.index.time[i - 1])
                ),
                "FLAG_QC",
            ] = df.FLAG_QC[i]

        ######## PREPARE L2A DATAFRAME TO BE FILLED WITH NEW FLAG_QC AND THEREFORE NEW MLH #########

        df2 = clean_time_array(xr.open_dataset(day_2a)).to_dataframe()
     
        df2["FLAG_QC"] = list(df_day_2["FLAG_QC"].astype(int))
        df2["FLAG_QC"] = df2["FLAG_QC"][np.isnan(df2["MLH"]) == False]
        df2["MLH"] = df2[df2.FLAG_QC == 0]["MLH"]
        df2["MLH"].fillna(-999, inplace=True)
        df2["FLAG_QC"].fillna(-999, inplace=True)

        MLH = df2["MLH"].to_xarray()
        MLH.attrs["units"] = "m"
        MLH.attrs["long_name"] = "mixed layer height"
        MLH.attrs["comment"] = "After quality control ; above ground level"
        ds["MLH"] = MLH.transpose("time", "station")
        
        ds = ds.rename({"FLAG": "precip_FLAG"})
        ds.precip_FLAG.attrs["units"] = "range between 0 and 1"

        FLAG_QC = df2["FLAG_QC"].astype(np.int32).to_xarray()
        FLAG_QC.attrs["units"] = "1"
        FLAG_QC.attrs["long_name"] = "flag for MLH after quality control"
        ds["FLAG"] = FLAG_QC.transpose("time", "station")

        ds.attrs["comment"] = "Mixed layer height after quality control; Git repository : git@gitlab.in2p3.fr:ipsl/sirta/mld/stratfinder/qc-sf-python.git"
        
        ## add history in output file 
        dir_path = os.path.dirname(os.path.realpath(f"{sys.argv[0]}"))
        repo = git.Repo(f"{dir_path}")
        sha = repo.head.commit.hexsha
        ds.attrs[
            "history"
        ] = f"Version of quality control code : {sha} ; date of creation : {date_today}"

        print("MLH replaced, FLAG added, History added")

        
        ######## PREPARE L2A DATASET TO BE FILLED WITH NEW VARIABLES #########
        
        ds2 = xr.open_dataset(day_2a)
        ds2_enco = get_encoding(ds2)
        ds2_enco["time"] = {
            "calendar": "standard",
            "dtype": "double",
            "_FillValue": None,
        }  
        
        ds2_enco["MLH"] = {"dtype": ds2["MLH"].encoding["dtype"], "_FillValue": "-999"}
        ds2_enco["FLAG"] = {"_FillValue": -999}
        del ds2_enco["station"]

        uid = pwd.getpwnam("eprofile").pw_uid
        gid = grp.getgrnam("eprofile").gr_gid
        ds = ds.sel(time=slice(day2, day2))
        ds = Change_dims(ds)
        ds2_enco["platform_id"] = ds["platform_id"].encoding
        ds2_enco["station_name"] = ds["station_name"].encoding
        ds.time.encoding["units"] = ds2["time"].encoding["units"] + "UTC"
        ds.time.attrs["long_name"] = "time"
        ds.to_netcdf(output_day2a, encoding=ds2_enco, mode="w", engine="netcdf4", unlimited_dims=["time","station_name"])

        os.chmod(output_day2a, 0o644)
        os.chown(output_day2a, uid, gid)
        print(f"output file created : {output_day2a}")
>>>>>>> develop

        ## CLOSE FILES
    return 0

if __name__ == "__main__":
    sys.exit(main())

if __name__ == "__main__":
    sys.exit(main())
