#!/usr/bin/env python

import os
import sys
import click
import json
import git
import pwd
import grp
import toml
from datetime import date, timedelta, time, datetime

import xarray as xr
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
from pathlib import Path
from pvlib.location import Location

pd.options.mode.chained_assignment = None  ## Warning avoid : ' SettingWithCopyWarning '


__version__ = "2025.09"
__author__ = "Melania Van Hove"


################################### FUNCTIONS ###################################################


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
    """Extract the maxmlh from the json configuration file

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
    """Remove the nan in the time index,remove the duplicates and
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
    ds["time"] = ds["time"].dt.floor("min")
    _, index = np.unique(ds["time"], return_index=True)
    ds = ds.isel(time=index)
    ds = ds.sortby("time")
    return ds


def Get_coverage(ds: xr.Dataset, var: str):
    """Get the min and maximum coverage for some variable such as time, latitude
    or longitude

    Args:
        ds (xr.Dataset): xarray dataset
        var (str): variable to chose

    Returns:
        min and max values of the variable
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


def rain_filter(df: pd.DataFrame, time_step_thresh: int) -> pd.DataFrame:
    """Remove day (or night) if more than 10% of rain more than 3h in the day (or night)

    Args:
        df (pd.dataframe): dataframe
        time_step_thresh (int): integer representing how many time steps to consider rain can affect MLH detection

    Returns:
        pd.dataframe: flaggued dataframe
    """

    all_rain = 0
    if all_rain :
        df2 = (
            df[df["time_relSR"] < 1]
            .groupby("day", as_index=False)
            .agg(profn=("prof", lambda x: (pd.to_numeric(x) == 1).sum())) 
        )  ## profn = number of times prof == 1, grouped by night
        df3 = (
            df[df["time_relSR"] > -1]
            .groupby("day", as_index=False)
            .agg(profd=("prof", lambda x: (pd.to_numeric(x) == 1).sum())) 
        )  ## profd = number of times prof == 1, grouped by day
        df = (
            df.reset_index().merge(df2, how="left").set_index("time")
        )  ## profn added to main dataframe
        df = (
            df.reset_index().merge(df3, how="left").set_index("time")
        )  ## profd added to main dataframe
        df.FLAG_QC[(df.profd >= time_step_thresh) & (df.time_relSR > -1)] = (
            df.FLAG_QC + 1
        )  ## if profd >= 12 (=3h) in one day, the day is flaggued
        df.FLAG_QC[
            (df.profn >= time_step_thresh) & (df.time_relSR < 1) & (df.FLAG_QC < 1)
        ] = (
            df.FLAG_QC + 1
        )  ## if profn >= 12 (=3h) in one night, the night is flaggued

    
    ### flag around the times when prof > 0
    
    list_ind_rain = df[(df["prof"] > 0) & ((df["day"] == 2) | (df["day"] == 3))].index.to_list()
    ind = [] 

    for el in list_ind_rain:
        before = el - timedelta(minutes=15)
        after = el + timedelta(minutes=15)
        ind.append(before)
        ind.append(after)

    ind = sorted(ind + list_ind_rain)
    df.FLAG_QC[ind] = df.FLAG_QC[ind] + 1

    return df


def stuck_mlh(
    df: pd.DataFrame,
    threshold_day: float,
    threshold_afternoon: float,
    threshold_fraction_mlh: float,
) -> pd.DataFrame:
    """remove stuck low MLH during daytime in warm seasons;
        conditions to remove the day :
        if more than 50% of MLH is lower than 300m during daytime
        or
        if the maximum MLH in the morning is higher than 300m but
        more than 50% of the afternoon MLH is lower than 500m

    Args:
        df (dataframe): dataframe
        threshold_day (float) : float MLH upper limit to consider stuck MLH in the morning
        threshold_afternoon (float) : float MLH upper limit to consider stuck MLH in the afternoon
        threshold_fraction_mlh (float): float fraction of the total MLH to consider it stucked

    Returns:
        pd.dataframe: flaggued dataframe

    Comments :
        occurs if morning growth is not detected by STRATFinder
        (not strong enough gradient) or if overlap model not good
        enough
    """
    
    # stuck MLH relative to morning 
    
    d = (df.day == 2)
    daytime = (df.time_relSR > 5) & d
    n_inf_300 = (daytime & (df.MLH < threshold_day)).sum()
    val_mlh1 = (daytime & (df.MLH > 0)).sum()
   
    if val_mlh1 != 0:
        rap1 = n_inf_300 / val_mlh1
    else:
        rap1 = np.nan

    morning = (df.time_relSR > 0) & (df.time_relSR <= 5) & d
    max_morn = df.MLH[morning].max()
    afternoon = (df.time_relSR > 7) & d
    n_inf_500 = (afternoon & (df.MLH < threshold_afternoon)).sum()
    val_mlh2 = (afternoon & (df.MLH > 0)).sum()

    if val_mlh2 != 0:
        rap2 = n_inf_500 / val_mlh2
    else:
        rap2 = np.nan

    if (rap1 > threshold_fraction_mlh) | (
        (max_morn > threshold_day) & (rap2 > threshold_fraction_mlh)
    ):
        print("relative STUCK MLH")
        min_mlh = df["MLH"][(df.time_relSR > 5) & d].min()
        day = (df.time_relSR > 5) | (df.time_relSS < 3)
        real_day = df.index.day[100]
        df.FLAG_QC[(df.MLH < min_mlh + 300) & day & (df.index.day == real_day)] = df.FLAG_QC[(df.MLH < min_mlh + 300) & day & (df.index.day == real_day)] + 10
      
    return df


def absolute_stuck_mlh (
    df: pd.DataFrame)-> pd.DataFrame:
    
    """remove stuck ;
        conditions to remove the day :
        if more than 2.5h of MLH is stuck at the same value

    Args:
        df (dataframe): dataframe

    Returns:
        pd.dataframe: flaggued dataframe

    Comments :
        occurs by night mostly if no NL is detected and/or is lower than low limit
    """
    
    # Identifier les zones où diff = 0
    is_constant = (df['diff'] == 0)
    print(is_constant)
    
    # Créer des groupes pour les séquences consécutives
    group_changes = (is_constant != is_constant.shift()).cumsum()
    print(group_changes)
    
    # Identifier les groupes qui correspondent à des séquences constantes ≥ min_duration_steps
    group_sizes = df.groupby(group_changes).size()
    valid_groups = group_sizes[
        (group_sizes >= 10) & 
        (df.groupby(group_changes)['diff'].first() == 0)
    ].index  # 10 = 2.5 hours 
    
    # Marquer flag=1 pour tous les timestamps de ces groupes valides
    df.loc[group_changes.isin(valid_groups), 'FLAG_QC'] = 10
    print(df[df["FLAG_QC"] == 10])
    

    # indices où FLAG_QC == 10
    idx_flagged = df.index[df['FLAG_QC'] == 10]

    # construire avant/après en décalant
    idx_before = idx_flagged - 2*pd.Timedelta(df.index.freq)   # un pas avant
    idx_after  = idx_flagged + 2*pd.Timedelta(df.index.freq)   # un pas après

    # concaténer
    idx_extended = idx_flagged.union(idx_before).union(idx_after)

    # appliquer le flag
    df.loc[df.index.intersection(idx_extended), 'FLAG_QC'] = 10

    print(df[df["FLAG_QC"]==10]["MLH"])

    return df

def massive_inc_night(
    df: pd.DataFrame, thresh: float, time_thresh: int, nl_mlh: float
) -> pd.DataFrame:
    """remove following layer after a massive increase at night
        the following layer is considered as a residual layer
        while the lower one is considered as the real noctural layer

    Args:
        df (pd.DataFrame): dataframe
        thresh (float): float threshold (in m) typical of a strong increase
        time_thresh (int) : integer time steps considered to identify a decrease (in time steps)
        nl_mlh (float) : float MLH considered valid after increase, if previous MLH if lower

    Returns:
        pd.DataFrame: flaggued dataframe
    """
    d = (df.day == 2) | (df.day == 3)
    print("start massive_inc_night with thresh = ", thresh)
    mov_sum = df["diff"][d].rolling(time_thresh).sum()
    cond_increase = mov_sum > thresh
    df2 = df[(df.time_relSR <= 1) & d & cond_increase]
    t = df["time_relSR"] < 4
    ind = []

    if df2.index.size > 0:
        print("massive_inc_night activated with thresh = ", thresh)
        for idx in df2.index:
            d = df.day == df2.day[idx]
            nl_mlh = df["MLH"][idx] - mov_sum[idx]
            if nl_mlh < 300:
                nl_mlh = 300
            l = df["MLH"] <= nl_mlh + 200
            print("nl_mlh = ", nl_mlh, " and  df['MLH'][idx] = ", df["MLH"][idx])

            idx_last = df[(df.time_relSR == 4) & d].index.to_list()
            if (
                df[d & t & l & (df.index > idx)].index.min() is not pd.NaT
            ):  # increase followed by decrease
                print("increase followed by decrease")
                a = df[d & t & l & (df.index > idx)].index.min()
                ind += df[idx:a].index.to_list()
            else:  # all layer is overestimated
                ind = ind + df[idx : idx_last[0]].index.to_list()

    ind = pd.unique(ind)
    ind = df["FLAG_QC"][ind][df.FLAG_QC == 0].index.to_list()
    #df["FLAG_QC"][ind] = df["FLAG_QC"][ind] + 100
    df.loc[ind, "FLAG_QC"] = 100
    return df


def massive_dec_night(
    df: pd.DataFrame, thresh: float, time_thresh: int, nl_mlh: float
) -> pd.DataFrame:
    """remove preceding layer after a massive decrease at night
        the preceding layer is considered as a residual layer
        while the lower one is considered as the real noctural layer

    Args:
        df (dataframe): dataframe
        thresh (float): float threshold typical of a strong decrease (absolute value in m)
        time_thresh (int) : int time steps considered to identify a decrease
        nl_mlh (float) : foat value of MLH considered valid before decrease, if following MLH if lower

    Returns:
        pd.dataframe: flaggued dataframe
    """
    d = (df.day == 2) | (df.day == 3)
    mov_sum = df["diff"][d].rolling(time_thresh).sum()
    cond_decrease = mov_sum < thresh
    df2 = df[(df.time_relSR <= 1) & (df.time_relSS >= 3) & d & cond_decrease]
    ind = []

    if df2.index.size > 0:
        print("massive_dec_night activated with thresh = ", thresh)
        for idx in df2.index:
            d = df.day == df2.day[idx]
            if df["MLH"][idx] < 300:
                nl_mlh = 300
            else:
                nl_mlh = df["MLH"][idx]

            print("idx = ", idx, "nl_mlh = ", nl_mlh, " and  df['MLH'][idx] = ", df["MLH"][idx])

            ss = df.time_relSR[d].idxmin() + timedelta(hours=3)

            print("removing from ss+3 to idx")
            ind += df[ss:idx].index.to_list()

    ind = pd.unique(ind)
    ind = df["FLAG_QC"][ind][df.FLAG_QC == 0].index.to_list()
    #df["FLAG_QC"][ind] = df["FLAG_QC"][ind] + 100
    df.loc[ind, "FLAG_QC"] = 100

    return df


def day_peaks(
    df: pd.DataFrame, thresh: float, time_range: int, mov_sum_step: int, when: str
) -> pd.DataFrame:
    """remove sharp increases followed by decreases during daytime or end of afternoon
        which are often local overestimations ; if the increase is higher than 2*thresh,
        it is considered as a real growth

    Args:
        df (dataframe): dataframe
        thresh (float): float threshold (in m) typical of a strong increase
        time_range (int) : integer time steps considered to detect a decrease
        mov_sum_step (int): integer time steps considered to define an increase
        when (str): str 'day time' or 'end afternoon'; end of afternoon being selected for summer
            and massive peaks, to avoid removing peaks occuring during heat waves
            in the middle of the afternon (ex : 19/07/22 at Palaiseau, France)

    Returns:
        pd.dataframe: flaggued dataframe
    """
    
    day = (df.time_relSR > 0) | (df.time_relSS < 1)
    real_day = df.index.day[100]
    mov_sum = df["diff"][day & (df.index.day == real_day)].rolling(mov_sum_step).sum()
    cond_increase = mov_sum > thresh * 0.75 
    cond_decrease = mov_sum < -thresh + 100

    ind = []
    
    if (len(cond_decrease.index[cond_decrease.values]) > 0) & (len(cond_increase.index[cond_increase.values]) > 0) :  
        increase_first_index = cond_increase.index[cond_increase.values][0]
        increase_last_index = cond_increase.index[cond_increase.values][-1]
        decrease_first_index = cond_decrease.index[cond_decrease.values][0] 
        decrease_last_index = cond_decrease.index[cond_decrease.values][-1] 
        
        if (when == "warm") & (decrease_first_index < increase_last_index) :
            ind = df[decrease_first_index - timedelta(minutes=60) : increase_last_index].index.to_list()
        elif (when == "cold") & (decrease_first_index > increase_last_index) :
            ind = df[increase_first_index - timedelta(minutes=60) : decrease_last_index].index.to_list()
        
    ind = pd.unique(ind)
    ind = df["FLAG_QC"][ind][df.FLAG_QC == 0].index.to_list()
    #df.FLAG_QC[ind] = df.FLAG_QC[ind] + 100
    df.loc[ind, "FLAG_QC"] = 100

    return df


def create_df3day(day_1a: Path, day_2a: Path, day_3a: Path) -> pd.DataFrame:
    """create a merged dataframe of the J-1,J and J+1 file ;
        if J-1 or J+1 doesnt exist, it is replaced by en empty df


    Args:
        day_1a (str): Path of the J-1 L2A file
        day_2a (str): Path of the J L2A file
        day_3a (str): Path of the J+1 L2A file

    Returns:
        pd.dataframe : merged dataframe of these 3 files
    """
    isFile1, isFile3 = (
        os.path.isfile(day_1a),
        os.path.isfile(day_3a),
    )

    ############### DATAFRAME PREPARED FOR THE END ####################

    df_day_2 = clean_time_array(xr.open_dataset(day_2a)).to_dataframe()
    df_day_2 = df_day_2.reset_index(level=1, drop=True)
    df_day_2 = df_day_2.drop(columns=['platform_id', 'station_name'])
    ############### AVERAGE 15 MIN ################
    
    df2 = df_day_2.resample("15min").mean()
    df2 = df2[df2.index.date == df2.index.date[0]]
    df2.index = pd.to_datetime(df2.index.values) + timedelta(minutes=15)
    df2.index = df2.index.set_names(["time"])
    
    ############### CONSTRUCT DATAFRAME OF 3 DAYS (J-1, J, J+1) IF MISSING VALUES ####################
    print("CONSTRUCT DATAFRAME OF 3 DAYS (J-1, J, J+1) IF MISSING VALUES")

    day1 = df2.index.date[0] - timedelta(days=1)
    df_id = pd.date_range(day1, day1 + timedelta(days=3), freq="15min").to_frame(
        index=True, name=None
    )
    df_id.index.names = ["time"]
    df_id.drop(index=df_id.index[0], axis=0, inplace=True)

    if isFile1:
        df1 = clean_time_array(xr.open_dataset(day_1a)).to_dataframe()
        df1 = df1.reset_index(level=1, drop=True)
        df1 = df1[df1.index.date == df1.index.date[0]]
        df1 = df1.drop(columns=['platform_id', 'station_name'])
        df1 = df1.resample("15min").mean()
        df1.index = pd.to_datetime(df1.index.values) + timedelta(minutes=15)
        df1.index = df1.index.set_names(["time"])
    else:
        df1 = None
        print(f"{day_1a} n'existe pas et est remplacé par un dataframe vide")

    if isFile3:
        df3 = clean_time_array(xr.open_dataset(day_3a)).to_dataframe()
        df3 = df3.reset_index(level=1, drop=True)
        df3 = df3.drop(columns=['platform_id', 'station_name'])
        df3 = df3.resample("15min").mean()
        df3.index = pd.to_datetime(df3.index.values) + timedelta(minutes=15)
        df3.index = df3.index.set_names(["time"])
    else:
        df3 = None
        print(f"{day_3a} n'existe pas et est remplacé par un dataframe vide")



    df = pd.concat([df1, df2, df3])
    df = pd.merge(df, df_id, how="right", right_index=True, left_index=True)
    print("dataframe created, end of function")
    return df


def extreme(df: pd.DataFrame, frac_maxmlh: float, maxmlh: float) -> pd.DataFrame:
    """Remove extreme points in winter

    Args:
        df (pd.dataframe): dataframe
        frac_maxmlh (float): float fraction of the maxmlh considered as the threshold (float between 0 and 1)
        maxmlh (float) : float maximum MLH set in config file

    Returns:
        pd.dataframe: flaggued dataframe
    """
    df.FLAG_QC[(df.MLH > (frac_maxmlh * maxmlh)) & (df.FLAG_QC == 0)] = (
        df.FLAG_QC[(df.MLH > (frac_maxmlh * maxmlh)) & (df.FLAG_QC == 0)] + 100
    )
    return df


def residual_layer(
    df: pd.DataFrame, thresh1: float, thresh2: float, thresh3: float
) -> pd.DataFrame:
    """Remove residual layer (night) with absolute values

    Args:
        df (pd.dataframe): dataframe
        thresh1 (float) : float threshold above which MLH is detected
        thresh2 (float) : float amount needed of MLH above thresh1 to be considered as residual layer (between 0 and 1)
        thresh3 (float) : float threshold above which MLH is removed

    Returns:
        pd.dataframe: flaggued dataframe
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
            df.FLAG_QC[(df.time_relSS > 3) & (df.time_relSR < 3) & (df.day == d) & (df.MLH > thresh3)] = (
                df.FLAG_QC[(df.time_relSS > 3) & (df.time_relSR < 3) & (df.day == d) & (df.MLH > thresh3)]
                + 10000
            )


    return df


def rel_residual_layer(df: pd.DataFrame, frac_max: float) -> pd.DataFrame:
    """Remove residual layer (night) with relative values
        in winter, a higher nocturnal layer is allowed relatively to daytime
        in other seasons, the maximum MLH at daytime is considered the maximum
            allowed for night time

    Args:
        df (pd.dataframe): dataframe
        frac_max (float) : float fraction considered of the maximum of daytime (float between 0 and 1)

    Returns:
        pd.dataframe: flaggued dataframe
    """
    d1 = df.day == 1
    d2 = df.day == 2
    d3 = df.day == 3
    max_d1 = df.MLH[d1 & (df.time_relSR > 4)].max()
    df.FLAG_QC[
        (df.time_relSR < 0) & d2 & (df.MLH > frac_max * max_d1) & (df.FLAG_QC < 10000)
    ] = (
        df.FLAG_QC[
            (df.time_relSR < 0)
            & d2
            & (df.MLH > frac_max * max_d1)
            & (df.FLAG_QC < 10000)
        ]
        + 10000
    )

    max_d2 = df.MLH[d2 & (df.time_relSR > 4)].max()
    df.FLAG_QC[
        (df.time_relSR < 0) & (df.time_relSS > 2) & d3 & (df.MLH > frac_max * max_d2) & (df.FLAG_QC < 10000)
    ] = (
        df.FLAG_QC[
            (df.time_relSR < 0)
            & (df.time_relSS > 2)
            & d3
            & (df.MLH > frac_max * max_d2)
            & (df.FLAG_QC < 10000)
        ]
        + 10000
    )

    return df


def overestimation(df: pd.DataFrame) -> pd.DataFrame:

    print("OVERESTIMATION FUNCTION STARTS ------ ")
    d2 = df.day == 2
    df["diff_MLH_ABLH"] = df.ABLH - df.MLH

    #mov_diff = df["diff"].rolling(2).sum()
    #cond_inc = (mov_diff > 2000)
    #cond_dec = (mov_diff < -2000)

    max_yesterday = df["MLH"][(df.day == 1) & (df.time_relSR > 0)].max()
    max_today = df["MLH"][(df.day == 2) & (df.time_relSR > 0)].max()
    cond_max = (max_today - max_yesterday > 1000)
    print("cond_max = ", cond_max)

    df2 = df[(df.time_relSR > 0) & d2 & (df.MLH > 2300) & (df.MLH <= 3000)]

    # Création d'une série booléenne
    is_zero = df2["diff_MLH_ABLH"] == 0

    # Trouver les groupes consécutifs
    group_id = (is_zero != is_zero.shift()).cumsum()  # identifie les groupes changés
    group_sizes = is_zero.groupby(group_id).transform('sum')  # taille du groupe

    # Masque pour les séquences de zéros consécutifs > 8
    long_zero_sequences = is_zero & (group_sizes >= 6)

    # Extraire les indices ou les valeurs concernées
    indices_consecutifs = df2.index[long_zero_sequences]
    print(indices_consecutifs)

    if (len(indices_consecutifs) > 0) & cond_max :

        #if df[96:192][(df.index <= indices_consecutifs[0]) & cond_inc]["diff"].any() | df[96:192][(df.index >= indices_consecutifs[0]) & cond_dec]["diff"].any() : 

        print("FLAG SHOULD BE CHANGED NOW ")

        df.loc[indices_consecutifs, "FLAG_QC"] += 100

        print(df[indices_consecutifs[0]:indices_consecutifs[-1]]["FLAG_QC"])

    return df



def artificial_noise(
    df: pd.DataFrame
) -> pd.DataFrame:
    """remove artificial noise generated by STRATFINDER 

    Args:
        df (dataframe): dataframe

    Returns:
        pd.dataframe: flaggued dataframe
    """

    window_size = "1H"

    time_condition = ((df.day == 2) & (df.time_relSR > 6)) | ((df.day == 3) & (df.time_relSS < 4))

    #    Appliquer la détection des minima et maxima dans chaque fenêtre de 2H
    df["MLH_min_2H"] = df[time_condition]["MLH"].rolling(window=window_size).apply(np.min)
    df["MLH_max_2H"] = df[time_condition]["MLH"].rolling(window=window_size).apply(np.max)

    #    Cherche la difference
    df["minima_diffs"] = df["MLH_min_2H"].diff()
    df["maxima_diffs"] = df["MLH_max_2H"].diff()

    ## list of consecutive minima

    list_index_diff_0_min = df["minima_diffs"][abs(df["minima_diffs"]) < 5].index.to_list()

    n=0
    ind_flag_min = []
    for i in range(len(list_index_diff_0_min[:-1])):
        if list_index_diff_0_min[i] == (list_index_diff_0_min[i+1] - timedelta(minutes = 15 )):
            n+=1
            if n > 5:
                for j in range(5):
                    ind_flag_min.append(list_index_diff_0_min[i-(5-j)])
        else:
            n=0
    ind_flag_min = pd.unique(ind_flag_min)
    print("ind_flag_min = ", ind_flag_min)

    ## list of consecutive maxima

    list_index_diff_0_max = df["maxima_diffs"][abs(df["maxima_diffs"] < 5)].index.to_list()
    n=0
    ind_flag_max = []
    for i in range(len(list_index_diff_0_max[:-1])):
        if list_index_diff_0_max[i] == (list_index_diff_0_max[i+1] - timedelta(minutes = 15)):
            n+=1
            if n > 3:
                for j in range(4):
                    ind_flag_max.append(list_index_diff_0_max[i-(4-j)])
        else:
            n=0

    ind_flag_max = pd.unique(ind_flag_max)
    print("ind_flag_max = ", ind_flag_max)

    for el in ind_flag_min:
        if (el in ind_flag_max) & (abs(df.loc[el, ["MLH_min_2H"]].values[0] - df.loc[el, ["MLH_max_2H"]].values[0]) > 5) :
             df.FLAG_QC[(df.index <= (el + timedelta(hours=2))) & (df.index >= (el - timedelta(hours=2)))] = df.FLAG_QC[(df.index <= (el + timedelta(hours=2))) & (df.index >= (el - timedelta(hours=2)))] + 100000

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
    """ " Convert np.datetime64 to datetime.

    Args:
        time_np64 (np.datetime64):

    Returns:
        datetime.datetime: Converted time to the datetime.datetime class
    """
    ts = (time_np64 - np.datetime64("1970-01-01T00:00:00Z")) / np.timedelta64(1, "s")
    ts = datetime.utcfromtimestamp(ts)
    return ts


def Change_dims(ds: xr.Dataset) -> xr.Dataset:
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
    #ds = ds.assign_coords({"station_name": ds["station_name"]})
    ds = ds.transpose()
    return ds


def Read_toml(file: str) -> Dict:
    """Read the toml file

    Args:
        file (str): file to read

    Returns:
        Dict: toml file's content_
    """
    with open(file, mode="r") as fp:
        cont_toml = toml.load(fp)
    return cont_toml


def Transform_list_type(list_to_trans: list, type_to: str) -> list:
    """Transform the list's element into a new type for example transform int64 to int32

    Args:
        list_to_trans (list): List to be transformed
        type_to (str  |  type): Type for the transformation

    Returns:
        list: Transformed list
    """
    return list(np.array(list_to_trans).astype(type_to))


def Get_gloabal_attrs(ds: xr.Dataset, config_meta: Dict, dir_path: str) -> xr.Dataset:
    """Add the global attributes contains into the toml configuration file
    into the

    Args:
        ds (xr.Dataset): xarray dataset
        config_meta (Dict): Dictionary containing the global attributes
        dir_path (str) : Path of the executed program
    Returns:
        xr.Dataset : xarray dataset with added global attributes
    """

    Global_attrs = config_meta["Global_attributes"]
    dict_attrs = ds.attrs
    ds.attrs = Global_attrs
    ds.attrs["contributor_name"] = dict_attrs["institution"] + ", "+ Global_attrs["contributor_name"]
    ds.attrs["contributor_institution"] = dict_attrs["institution"] + ", "+ Global_attrs["contributor_name"]
    ds.attrs["contributor_role"] = dict_attrs["institution"] +" operate the Lidar measurements, "+ Global_attrs["contributor_role"]
    ds.attrs["site_location"] = dict_attrs["site_location"]
    ds.attrs["instrument_id"] = dict_attrs["instrument_id"]
    ds.attrs["instrument_type"] = dict_attrs["instrument_type"]
    ds.attrs["wmo_id"] = dict_attrs["wmo_id"]
    ds.attrs["instrument_serial_number"] = dict_attrs["instrument_serial_number"]
    ds.attrs["optical_module_id"] = dict_attrs["optical_module_id"]
    ds.attrs["instrument_firmware_version"] = dict_attrs["instrument_firmware_version"]
    ds.attrs["overlap_function"] = dict_attrs["overlap_function"]
    ds.attrs["overlap_is_corrected"] = dict_attrs["overlap_is_corrected"]
    ds.attrs["time_coverage_start"] = str(ds["time"].values[0])
    ds.attrs["time_coverage_end"] = str(ds["time"].values[-1])
    ds.attrs["geospatial_lat_min"] = ds["station_latitude"].values[0]
    ds.attrs["geospatial_lat_max"] = ds["station_latitude"].values[0]
    ds.attrs["geospatial_lon_min"] = ds["station_longitude"].values[0]
    ds.attrs["geospatial_lon_max"] = ds["station_longitude"].values[0]
    ds.attrs["geospatial_lat_min"] = np.float64(ds.attrs["geospatial_lat_min"])
    ds.attrs["geospatial_lat_max"] = np.float64(ds.attrs["geospatial_lat_max"])
    ds.attrs["geospatial_lon_min"] = np.float64(ds.attrs["geospatial_lon_min"])
    ds.attrs["geospatial_lon_max"] = np.float64(ds.attrs["geospatial_lon_max"])

    # write product version
    r = subprocess.check_output(['git', '-C', dir_path, 'describe', '--tags', '--always'],text=True).strip()
    ds.attrs["product_version"] = f"Quality control version : {r}"

    STRATfinder_version = dict_attrs["history"][104:111]  # pour avoir la version de STRATfinder qui est sous la forme : v2025.09-5-g1a2b3c4
    quality_control_version = r[:7]
    product_version = max(datetime.strptime(STRATfinder_version, "%Y.%m"), datetime.strptime(quality_control_version, "%Y.%m"))
    product_version = product_version.strftime("%Y-%m")
    ds.attrs["product_version"] = product_version
    ds.attrs["source"] = f"Automatic Lidar Ceilometer (ALC); STRATFINDER vesion : {STRATfinder_version} ; Quality control version : {quality_control_version}"
    # end product versions


    inst = dict_attrs["instrument_type"].lower()
    city = dict_attrs["site_location"].lower()
    ds.attrs["title"] = f"STRATfinder applied on {inst}; quality controlled; {city}"
    return ds


def Get_vars_attr_enc(ds: xr.Dataset, config_meta: Dict) -> xr.Dataset:
    """Add the attributes and encoding contains into the toml configuration file
    for each variable into the xarray dataset

    Args:
        ds (xr.Dataset): xarray dataset
        config_meta (Dict): Dictionary containing the attributes and encoding for each variable
    Returns:
        xr.Dataset : xarray dataset with added encoding and attributes
    """
    Vars_attrs = config_meta["Variables"]
    for key in Vars_attrs.keys():
        ds[key].attrs = Vars_attrs[key]["Attributes"]
        ds[key].encoding = Vars_attrs[key]["Encoding"]
    ds["time"].encoding["_FillValue"] = None
    ds["station_name"].attrs["platform_id"] = (
        ds["platform_id"].values[0].replace("?", "")
    ).strip()
    ds["quality_FLAG"].attrs["flag_values"] = Transform_list_type(
        ds["quality_FLAG"].attrs["flag_values"], np.int32
    )
    ds["precip_FLAG"].attrs["flag_values"] = Transform_list_type(
        ds["precip_FLAG"].attrs["flag_values"], np.int32
    )
    ds = ds.drop_vars("platform_id")
    return ds


################################# END FUNCTIONS #################################################
