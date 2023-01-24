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
#############################################FUNCTION############################################################################
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

    _, index = np.unique(ds["time"], return_index=True)
    ds = ds.isel(time=index)
    ds = ds.sortby("time")
    ds["time"] = ds["time"].dt.floor("min")
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


def cold_day_inc(df: pd.DataFrame, thresh) -> pd.DataFrame:
    """_summary_

    Args:
        df (_type_): dataframe
        thresh (_type_): threshold (in m) typical of a strong increase

    Returns:
        _type_: flaggued dataframe
    """
    d = df.day == 2
    df2 = df[(df.time_relSR > 0) & (df["diff"] > thresh) & d]
    h = df["diff"] > thresh
    l = df["diff"] < -(thresh - 200)
    t = df["time_relSR"] > 0
    ind = []

    if df2.index.size != 0:
        for idx in df2.index:
            if df[(df.index >= idx) & (df.MLH < 500) & d].index.min() is not pd.NaT:
                a = df[(df.index >= idx) & (df.MLH < 500) & d].index.min()
                ind = ind + df[idx : a - timedelta(minutes=15)].index.to_list()

            elif df[l & (df.index >= idx) & d].index.min() is not pd.NaT:
                a = df[l & (df.index >= idx) & d].index.min()
                ind = ind + df[idx : a - timedelta(minutes=15)].index.to_list()

    df.FLAG_QC[ind] = df.FLAG_QC[ind] + 100
    return df


def cold_morn_inc(df: pd.DataFrame, thresh: int) -> pd.DataFrame:
    """_summary_

    Args:
        df (_type_): dataframe
        thresh (_type_): threshold (in m) typical of a strong increase

    Returns:
        _type_: _description_
    """
    d = df.day == 2
    df2 = df[(df.time_relSR > 0) & (df.index.hour < 12) & (df["diff"] > thresh) & d]
    h = df["diff"] > thresh
    l = df["diff"] < -thresh
    t = df["time_relSR"] > 0

    ind = []
    if df2.index.size != 0:
        for idx in df2.index:
            if (
                df[
                    l
                    & d
                    & (df.index >= idx)
                    & (df.index < idx + timedelta(minutes=210))
                ].index.max()
                is not pd.NaT
            ):
                a = df[
                    l
                    & d
                    & (df.index >= idx)
                    & (df.index < idx + timedelta(minutes=210))
                ].index.max()
                ind = ind + df[idx : a - timedelta(minutes=15)].index.to_list()

    df.FLAG_QC[ind] = df.FLAG_QC[ind] + 100
    return df


def massive_dec_night(df: pd.DataFrame, thresh) -> pd.DataFrame:
    """_summary_

    Args:
        df (_type_): dataframe
        thresh (_type_): threshold (in m) typical of a strong decrease (absolute value)

    Returns:
        _type_: flaggued dataframe
    """
    d = (df.day == 2) | (df.day == 3)
    df2 = df[(df.time_relSR < 0.25) & d & (df["diff"] < thresh)]
    l = df["diff"] < thresh
    t = (df["time_relSR"] < 0.25) & (df["time_relSS"] > 2)
    ind = []

    if df2.index.size > 0:
        for idx in df2.index:
            d = df.day == df2.day[idx]
            s = df.time_relSR[d].idxmin()
            if df[t & d & (df.MLH < 500) & (df.index < idx)].index.max() is not pd.NaT:
                a = df[t & d & (df.MLH < 500) & (df.index < idx)].index.max()
                a = a + timedelta(minutes=15)
                #idx = idx - timedelta(minutes=15)
                ind += df[a:idx].index.to_list()

            else:
                #idx = idx - timedelta(minutes=15)
                ind += df[s:idx].index.to_list()

    df["FLAG_QC"][ind] = df["FLAG_QC"][ind] + 100
    return df


def stuck_mlh(df: pd.DataFrame) -> pd.DataFrame:
    """_summary_

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

    ## DATAFRAME PREPARED FOR THE END
    df_day_2 = clean_time_array(xr.open_dataset(day_2a)).to_dataframe()
    df_day_2 = df_day_2.reset_index(level=0, drop=True)
    df_day_2 = df_day_2[~df_day_2.index.duplicated(keep="first")]
    df_day_2 = df_day_2.loc[df_day_2.index.dropna()]

    ## AVERAGE 15 MIN (IN THE END : ADD THE FLAG COLUMN TO 1MIN DS AND FILL NAN WITH LAST VALID FLAG VALUE)

    df2 = df_day_2.resample("15min").mean()
    df2 = df2[df2.index.date == df2.index.date[0]]
    df2.index = pd.to_datetime(df2.index.values) + timedelta(minutes=15)
    df2.index = df2.index.set_names(["time"])

    ## CONSTRUCT DATAFRAME OF 3 DAYS (J-1, J, J+1) IF MISSING VALUES

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


def massive_inc_night(df: pd.DataFrame, thresh) -> pd.DataFrame:
    """_summary_

    Args:
        df (pd.DataFrame): dataframe
        thresh (_type_): threshold (in m) typical of a strong increase

    Returns:
        pd.DataFrame: flaggued dataframe
    """
    d = (df.day == 2) | (df.day == 3)
    df2 = df[(df.time_relSR <= 1) & d & (df["diff"] > 300)]

    h = df["diff"] > thresh
    l = df["diff"] < -thresh
    t = df["time_relSR"] < 2
    ind = []

    if df2.index.size > 0:
        for idx in df2.index:
            d = df.day == df2.day[idx]
            idx_last = df[(df.time_relSR == 5) & d].index.to_list()

            if (
                df[d & t & l & (df.index > idx)].index.min() is not pd.NaT
            ):  # increase followed by decrease
                a = df[d & t & l & (df.index > idx)].index.min()
                a = a - timedelta(minutes=15)
                ind += df[idx:a].index.to_list()

            elif (
                df[t & d & (df.MLH < 500) & (df.index > idx)].index.min()
                is not pd.NaT
            ):  # MLH lower than 500m after increase
                a = df[t & d & (df.MLH < 500) & (df.index > idx)].index.min()
                a = a - timedelta(minutes=15)
                ind += df[idx:a].index.to_list()

            elif df["time_relSR"][idx] > -1:  # increase in night end/ early morning
                ind += df[
                    d & (df["time_relSR"] < 4) & (df.index >= idx)
                ].index.to_list()

            else:  # all layer is overestimated
                ind = ind + df[idx : idx_last[0]].index.to_list()

    df["FLAG_QC"][ind] = df["FLAG_QC"][ind] + 100
    return df


def warm_day_inc(df: pd.DataFrame, thresh: int) -> pd.DataFrame:
    """_summary_

    Args:
        df (_type_): dataframe
        thresh (_type_): threshold (in m) typical of a strong increase

    Returns:
        _type_: flaggued dataframe
    """
    d = df.day == 2
    df2 = df[(df.time_relSR > 0) & (df["diff"] > thresh) & d]  
    h = df["diff"] > thresh
    t = df["time_relSR"] > 0
    l = df["diff"] < -(thresh - 100)
    ind = []

    if df2.index.size != 0:
        for idx in df2.index:
            if (
                df[
                    t
                    & d
                    & l
                    & (df.index >= idx)
                    & (df.index <= idx + timedelta(minutes=60))
                ].index.min()
                is not pd.NaT
            ):
                a = df[
                    t
                    & d
                    & l
                    & (df.index >= idx)
                    & (df.index <= idx + timedelta(minutes=60))
                ].index.min()
                a = a - timedelta(minutes=15)
                ind = ind + df[idx:a].index.to_list()

    df.FLAG_QC[ind] = df.FLAG_QC[ind] + 100
    return df


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

## CHECK IF ARGUMENTS ARE READABLE/WRITABLE


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
def main(
    day_1a: click.Path,
    day_2a: click.Path,
    day_3a: click.Path,
    config_filea: click.Path,
    output_day2a: click.Path,
) -> None:

    # Check if the file
    click.echo(click.format_filename(day_1a))
    click.echo(click.format_filename(day_2a))
    click.echo(click.format_filename(day_3a))
    click.echo(config_filea)
    click.echo(click.format_filename(output_day2a))

    ## CONFIGURATION
    today = date.today()
    #today = datetime.date.today()

    date_today = today.strftime("%B %d, %Y")
    maxmlh = get_maxmlh(config_filea)
    print(f"Read the file {config_filea}")
    df = create_df3day(day_1a, day_2a, day_3a)
    print("complete dataframe created")
    ndata_day2 = int(len(df) / 3)

    with xr.open_dataset(day_2a) as ds:
        site = ds.attrs["site_location"]  ## site name given in J file
        month2 = ds["time"].dt.month[0].values
        lat = ds["station_latitude"][0].values
        lon = ds["station_longitude"][0].values
        ds = clean_time_array(ds)
        warm = (month2 > 3) & (month2 < 10)

        # Get the encoding for the variable

        # from dataset to dataframe
        df_day_2 = ds.to_dataframe()
        df_day_2 = df_day_2.reset_index(level=0, drop=True)
        df_day_2 = df_day_2[~df_day_2.index.duplicated(keep="first")]
        df_day_2 = df_day_2.loc[df_day_2.index.dropna()]
        day_today = conv_np64dt_to_dt(ds["time"][0].values)
        day0 = day_today - timedelta(days=2) #.isoformat()[0:10]
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
            sunrise1 = 0.25 * (round(4.0 * sunrise1))  ## rounded to closer quarter hour

            sunset1 = (
                schedule["sunset"].second
                + 60 * schedule["sunset"].minute
                + 3600 * schedule["sunset"].hour
            ) / 3600.0  ## sunset in hour
            sunset1 = 0.25 * (round(4.0 * sunset1))

            sunrise.append(sunrise1)
            sunset.append(sunset1)
            date_ = date_ + timedelta(days=1)

        ## COLUMNS 'time relative to sunrise', 'time relative to sunset' AND 'day defined from sunset to sunset' 

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

        ## FLAG COLUMN

        df.insert(5, "FLAG_QC", 0)



        ## FILTERS

        ## RAIN

        # df['MLH'] = np.where(df.prof > 0,np.nan,df.MLH) #useless because MLH already NaN where prof > 0 ; moreover, with 15min averaging, some existing MLH might become NaN and therefore 'invisible' for next filters (case for 19/12/20)

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
        )  ## if profd >= 12 in one day, the day is flaggued
        df.FLAG_QC[(df.profn >= 12) & (df.time_relSR < 1)] = (
            df.FLAG_QC + 1
        )  ## if profn >= 12 in one night, the night is flaggued

        print("filter Rain done")

        ##REMOVE STUCK MLH AT DAY/WARM SEASONS

        if (site != "LERWICK,UK") & (warm == True):

            df = stuck_mlh(df, df.MLH, df.time_relSR)

        print("filter Stuck MLH done")

        ## CHECK FOR MASSIVE INCREASE

        ## DURING NIGHT

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

        ## MASSIVE INCREASE AT NIGHT

        ## fonction qui prend en argument le df, le seuil caractéristique d'une augmentation, et qui renvoit un df flaggué

        df = massive_inc_night(df, 250) #250 instead of 300 for CABAM because 15min averaging 

        ## MASSIVE DECREASE AT NIGHT

        df = massive_dec_night(df, -250)

        print("filter Massive decrease/increase at night done")

        ## DAY MASSIVE INCREASE/ DECREASE IN TWO HOURS MAXIMUM

        # differences between consecutive mlh (taking NaN into account)
        df["diff"] = df["MLH"].diff()
        idx = df[np.isnan(df["diff"]) == True].index.to_list()
        for i in idx:
            idx2 = df[df.index < i].MLH.last_valid_index()
            if idx2 is not None:
                if (i - idx2) <= timedelta(minutes=120):
                    df["diff"][i] = df.MLH[i] - df.MLH[idx2]


        ## INCREASE - MORNINGS & DAY

        if warm == False:

            df = cold_morn_inc(df, 400)

            ## INCREASE - COLD SEASONS DAYS

            df = cold_day_inc(df, 1000)

        ## INCREASE - WARM SEASONS

        else:  

            df = warm_day_inc(df, 1000)

        print("filter Massive Increase/decrease at day done")

        ## WINTER EXTREME POINTS

        if (month2 < 3) | (month2 > 11):
            df.FLAG_QC[((month2 < 3) | (month2 > 11)) & (df.MLH > (0.75 * maxmlh))] = (
                df.FLAG_QC[((month2 < 3) | (month2 > 11)) & (df.MLH > (0.75 * maxmlh))]
                + 100
            )

        ## GENERAL EXTREME POINTS

        df.FLAG_QC[df.MLH > maxmlh] = df.FLAG_QC[df.MLH > maxmlh] + 100

        print("filter Extreme points done")

        ## RESIDUAL LAYER

        # AM JJA S

        if warm == True:
            ii = (df.time_relSS > 2) & (df.time_relSR < 2)
            df2 = (
                df[ii]
                .groupby("day", as_index=False)
                .agg(
                    mM=(
                        "MLH",
                        lambda x: (x > 800).sum() / (x > 0).sum()
                        if (x > 0).sum() != 0
                        else None,
                    )
                )
            )
            llcheck = list(df2.day[df2.mM > 0.75])

            if llcheck != []:
                for d in llcheck:
                    df.FLAG_QC[(df.time_relSR < 3) & (df.day == d) & (df.MLH > 600)] = (
                        df.FLAG_QC[(df.time_relSR < 3) & (df.day == d) & (df.MLH > 600)]
                        + 10000
                    )

        # ON DJF M
        else:
            ii = (df.time_relSS > 2) & (df.time_relSR < 2)
            df2 = (
                df[ii]
                .groupby("day", as_index=False)
                .agg(
                    mM=(
                        "MLH",
                        lambda x: (x > 600).sum() / (x > 0).sum()
                        if (x > 0).sum() != 0
                        else None,
                    )
                )
            )
            llcheck = list(df2.day[df2.mM > 0.5])

            if llcheck != []:
                for d in llcheck:
                    df.FLAG_QC[(df.time_relSR < 3) & (df.day == d) & (df.MLH > 500)] = (
                        df.FLAG_QC[(df.time_relSR < 3) & (df.day == d) & (df.MLH > 500)]
                        + 10000
                    )

        print("filter Residual layer done")

        ## REMERGE WITH 1MIN FREQUENCY

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
                    (df_day_2.index.time < df.index.time[i])
                    & (df_day_2.index.time > df.index.time[i - 1])
                ),
                "FLAG_QC",
            ] = df.FLAG_QC[i]

        df2 = xr.open_dataset(day_2a).to_dataframe()
        df2 = df2.loc[df2.index.dropna()]
        df2 = df2[~df2.index.duplicated(keep="first")]

        print("len df_day_2 = ", len(df_day_2), "len(df2) = ", len(df2))

        ## FINAL DATAFRAME

        df2["FLAG_QC"] = list(df_day_2["FLAG_QC"].astype(int))
        df2["FLAG_QC"] = df2["FLAG_QC"][np.isnan(df2["MLH"]) == False]
        df2["MLH"] = df2[df2.FLAG_QC == 0]["MLH"]
        df2["MLH"].fillna(-999, inplace=True)
        df2["FLAG_QC"].fillna(-999, inplace=True)

        MLH = df2["MLH"].to_xarray()
        MLH.attrs["units"] = "m"
        MLH.attrs["long_name"] = "mixed layer height"
        MLH.attrs["comment"] = "After quality control ; above ground level"
        ds["MLH"] = MLH
        ds["MLH"] = ds["MLH"].transpose("time", "station")

        ds = ds.rename({"FLAG": "precip_FLAG"})
        ds.precip_FLAG.attrs["units"] = "range between 0 and 1"

        FLAG_QC = df2["FLAG_QC"].astype(np.int32).to_xarray()
        FLAG_QC.attrs["units"] = "1"
        FLAG_QC.attrs["long_name"] = "flag for MLH after quality control"

        ds["FLAG"] = FLAG_QC.transpose("time", "station")

        ds.attrs["comment"] = "Mixed layer height after quality control; Git repository : git@gitlab.in2p3.fr:mvanhove/qc-sf-python.git"

        dir_path = os.path.dirname(os.path.realpath(f"{sys.argv[0]}"))
        repo = git.Repo(f"{dir_path}")
        sha = repo.head.commit.hexsha
        ds.attrs[
            "history"
        ] = f"Version of quality control code : {sha} ; date of creation : {date_today}"

        print("MLH replaced, FLAG added, History added")

        ## CREATE NETCDF L2B
        
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

        #uid = pwd.getpwnam("eprofile").pw_uid
        #gid = grp.getgrnam("eprofile").gr_gid
        ds = ds.sel(time=slice(day2, day2))
        ds = Change_dims(ds)
        ds2_enco["platform_id"] = ds["platform_id"].encoding
        ds2_enco["station_name"] = ds["station_name"].encoding
        ds.time.encoding["units"] = ds2["time"].encoding["units"] + "UTC"
        ds.time.attrs["long_name"] = "time"
        ds.to_netcdf(output_day2a, encoding=ds2_enco, mode="w", engine="netcdf4", unlimited_dims=["time","station_name"])

        #os.chmod(output_day2a, 0o644)
        #os.chown(output_day2a, uid, gid)
        print(f"output file created : {output_day2a}")

        ## CLOSE FILES
    return 0


if __name__ == "__main__":
    sys.exit(main())
