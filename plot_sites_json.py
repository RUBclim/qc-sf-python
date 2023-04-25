#!/usr/bin/env python

import os
import sys
import click
import pathlib
import json
import git
import glob
from typing import Tuple, List
from pathlib import Path
from datetime import date, timedelta
import pwd
import grp
import xarray as xr
import pandas as pd
import numpy as np

from solartime import (
    SolarTime,
)  ## to be replaced by pvlib if more problems encountered, works for now

pd.options.mode.chained_assignment = None  ## Warning avoid : ' SettingWithCopyWarning '

__version__ = "1.0.0"
__author__ = "Melania Van Hove"


####################################################################################################
#############################################  FUNCTIONS  ##########################################
####################################################################################################


def list_files(dir: str, filtre: str) -> List:
    """[list the files inside the directory with a choosen filter]

    Args:
        dir ([str]): [directory to list file inside of it ]
        filtre ([list]) : filters
    Returns:
        [list]: [list of files inside of directory ]
    """
    file_list = []
    for dirs, subdirs, files in os.walk(dir):
        for file in files:
            if all(filt in file for filt in filtre):
                print(file)
                file_list.append(os.path.join(dirs, file))
    return file_list


def average_dataframe(
    list_files: List,
) -> Tuple[float, float, pd.DatetimeIndex, pd.DatetimeIndex, pd.DataFrame]:
    """Creates a 15min averaged dataframe of all annual L2B concatenated

    Args:
        list_files (List,): list of input files

    Returns:
        float : latitude
        float : longitude
        pd.DatetimeIndex : first date of the dataframe
        pd.DatetimeIndex : last date of the dataframe
        pd.DataFrame : averaged dataframe
    """
    with xr.open_mfdataset(list_files) as ds:
        df = ds.to_dataframe()
        df.reset_index(drop=True, level=0, inplace=True)
        df = df[df.index.duplicated() == False]
        lat, lon = df["station_latitude"][0], df["station_longitude"][0]

        ave_df = df.copy()

        start_date = ave_df.index.date[0]
        end_date = ave_df.index.date[len(ave_df) - 2]

        ## AVERAGING OVER 15 MIN AND FILL TIME MISSING

        ave_df = ave_df.resample("15min").mean()
        ave_df.index = pd.to_datetime(ave_df.index.values) + timedelta(minutes=15)
        ave_df.index = ave_df.index.set_names(["time"])

        df2 = pd.date_range(start_date, end_date + timedelta(days=1), freq="15min")
        df2 = df2.to_frame(index=True, name=None)
        df2.index.names = ["time"]
        ave_df = pd.merge(ave_df, df2, how="right", right_index=True, left_index=True)
        ave_df.drop(index=ave_df.index[0], axis=0, inplace=True)

        ## IN CASE DATAFRAME DOESNT START/END AT MIDNIGHT
        df2 = pd.date_range(start_date, end_date, freq="15min")
        df2 = df2.to_frame(index=True, name=None)
        df2.index.names = ["time"]
        ave_df = pd.merge(ave_df, df2, how="right", right_index=True, left_index=True)
        ave_df.drop(index=ave_df.index[0], axis=0, inplace=True)
        return lat, lon, start_date, end_date, ave_df


#################################################################################################################################
#############################################ARGUMENT############################################################################
#################################################################################################################################


@click.command()
# name of the instrument's site
@click.argument(
    "site_name",
    nargs=1,
)
# Path of the Release files
@click.argument(
    "path_all_years",
    nargs=1,
)
# Month of the json files
@click.argument(
    "month",
    nargs=1,
)
# Output directory
@click.argument(
    "site_o",
    nargs=1,
)
# instrument's type
@click.argument(
    "inst",
    nargs=1,
)
# Instrument id
@click.argument(
    "inst_id",
    nargs=1,
)
# Version of the Release
@click.argument(
    "vl2b",
    nargs=1,
)

######################################################################
############################### MAIN #################################
######################################################################


def main(
    site_name: str,
    path_all_years: str,
    month: str,
    site_o: str,
    inst: str,
    inst_id: str,
    vl2b: str,
) -> None:
    """Creates the figure of climatological MLH

    Args:
        site_name (str): Instrument's site name
        path_all_years (str): Path of the L2B concatenated files
        month (str): Chosen month to create the json files
        site_o (str): Output path for the json files
        inst (Path): Instrument's name
        inst_id (Path): Instrument id's name
        VL2B (Path): Version of the L2B files

    Returns:
        _type_: _description_
    """
    # List all th concatenated L2B files
    list_concat_L2B = list_files(path_all_years, ["STRATFINDER", "1min"])
    # Get an averaged dataframe
    lat, lon, start_date, end_date, ave_df = average_dataframe(list_concat_L2B)
    ## TIME RELATIVE TO SUNRISE DEFINITION
    sun = SolarTime()

    date = start_date - timedelta(days=1)
    sunrise = []
    sunset = []

    while date <= (end_date):  # + timedelta(days=1)) :
        schedule = sun.sun_utc(date, lat, lon)
        sunrise1 = (
            schedule["sunrise"].second
            + 60 * schedule["sunrise"].minute
            + 3600 * schedule["sunrise"].hour
        ) / 3600.0  # en heure
        sunrise1 = 0.25 * (
            round(4.0 * sunrise1)
        )  # en heure arrondie au quart d'heure le plus proche
        sunset1 = (
            schedule["sunset"].second
            + 60 * schedule["sunset"].minute
            + 3600 * schedule["sunset"].hour
        ) / 3600.0
        sunset1 = 0.25 * (round(4.0 * sunset1))
        sunrise.append(sunrise1)
        sunset.append(sunset1)
        date = date + timedelta(days=1)

    print(schedule, sunrise1, sunset1)

    time = [i / 4.0 for i in range(1, 97)]  # *(end_date - start_date).days
    dt = []

    for j in range(1, len(sunrise) - 1):
        for i in range(96):
            if time[i] < sunset[j]:
                dt.append(time[i] - sunrise[j])
            else:
                dt.append(-(24 - time[i] + sunrise[j + 1]))

    ave_df.insert(2, "time_relSR", dt)

    ss = []
    for j in range(len(sunset) - 2):
        for i in range(96):
            if time[i] < sunrise[j + 1]:
                ss.append((24 - sunset[j] + time[i]))
            else:
                ss.append(time[i] - sunset[j + 1])

    ave_df.insert(3, "time_relSS", ss)

    # OTHER INDEXES

    n = 1
    day = [1]

    for i in range(1, len(ave_df)):
        if dt[i - 1] > 0 and dt[i] < 0:
            day.append(n + 1)
            n = n + 1
        else:
            day.append(n)  # day relative to sunrise/sunset

    ave_df.insert(4, "day", day)

    ## MEDIAN VALUES

    lim = int(len(ave_df) / 1000)


    df_final = (
        ave_df[ave_df.index.month == int(month)]
        .groupby("time_relSR", as_index=False)
        .agg(
            mlh_med=(
                "MLH",
                lambda x: x.median() if ((np.isnan(x) == False).sum() > lim) else None,
            ),
            mlh_q1=(
                "MLH",
                lambda x: x.quantile(0.25)
                if ((np.isnan(x) == False).sum() > lim)
                else None,
            ),
            mlh_q3=(
                "MLH",
                lambda x: x.quantile(0.75)
                if ((np.isnan(x) == False).sum() > lim)
                else None,
            ),
        )
    )

    df_final.set_index("time_relSR", inplace=True)

    month_lab_list = [
        " ",
        "jan",
        "feb",
        "mar",
        "apr",
        "may",
        "jun",
        "jul",
        "aug",
        "sep",
        "oct",
        "nov",
        "dec",
    ]
    month_lab = month_lab_list[int(month)]

    data = {
        "title": f"MLH_{month_lab}_{site_name}_Stratfinder",
        "time": list(df_final.index),
        "mlh_med": list(df_final.mlh_med),
        "mlh_q1": list(df_final.mlh_q1),
        "mlh_q3": list(df_final.mlh_q3),
        "label_x": "time relative to SR [h]",
        "label_y": "MLH median [magl]",
    }

    ## JSON FILE
    if int(month) < 10:
        outfile = f"eprofile_cycle_STRATFINDER_{site_name}_{inst}_{inst_id}_{vl2b}_0{month}.json"
    else:
        outfile = f"eprofile_cycle_STRATFINDER_{site_name}_{inst}_{inst_id}_{vl2b}_{month}.json"
    # json file loacation
    output = f"{site_o}/{outfile}"
    print(f"output written : {output}")
    with open(f"{output}", "w") as f:
        json.dump(data, f)

    return 0


if __name__ == "__main__":
    sys.exit(main())
