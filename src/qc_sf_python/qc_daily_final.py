#!/usr/bin/env python

import sys
import click
import qc_sf_python.functions as funcs
from datetime import date, timedelta, time

import xarray as xr
import pandas as pd
import numpy as np
from pathlib import Path
from pvlib.location import Location


__author__ = "Melania Van Hove"

def qc_daily_final(
        day_1a: Path,
        day_2a: Path,
        day_3a: Path,
        config_filea: Path,
        file_values_qca: Path,
        config_attributes_file: Path,
        output_day2a: Path):
    # Read the values into the toml configuration file related to the values
    values_qc = funcs.Read_toml(file_values_qca)
    # Read the values of the toml configuration files related to the global and variable's attributes
    attrs_dict = funcs.Read_toml(config_attributes_file)
    # Define the datetime
    # today = date.today()
    # date_today = today.strftime("%B %d, %Y")
    maxmlh = funcs.get_maxmlh(config_filea)
    print(f"Read the file {config_filea}")
    df = funcs.create_df3day(day_1a, day_2a, day_3a)

    print("complete dataframe created")
    ndata_day2 = int(len(df) / 3)

    with xr.open_dataset(day_2a) as ds:
        site = ds.attrs["site_location"]  ## site name given in L2A by E-PROFILE
        month2 = ds["time"].dt.month[0].values
        # warm = (month2 > 3) and (month2 < 10)
        # summer = (month2 > 5) and (month2 < 9)
        lat = ds["station_latitude"][0].values
        lon = ds["station_longitude"][0].values
        ds = funcs.clean_time_array(ds)
        df_day_2 = ds.to_dataframe()
        df_day_2 = df_day_2.reset_index(level=0, drop=True)
        df_day_2 = df_day_2[~df_day_2.index.duplicated(keep="first")]
        df_day_2 = df_day_2.loc[df_day_2.index.dropna()]
        day_today = funcs.conv_np64dt_to_dt(ds["time"][0].values)
        day0 = day_today - timedelta(days=2)
        day1 = (day_today - timedelta(days=1)).isoformat()[0:10]
        day2 = day_today.isoformat()[0:10]
        day3 = (day_today + timedelta(days=1)).isoformat()[0:10]

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

        df = df.rename(columns={"FLAG": "rain"})
        df = df.rename(columns={"cloud_base_altitude": "CBH"})

        ## TIME RELATIVE TO SUNRISE/SUNSET
        print("TIME RELATIVE TO SUNRISE")
        location = Location(lat, lon, tz='UTC')
        date_ = date(day0.year, day0.month, day0.day)

        sunrise, sunset = [], []

        for i in range(
                5
        ):  ## 5 : because we need SR & SS at day J-2, J-1, J, J+1 et J+2
            date_range = pd.date_range(start=date_, periods=1, freq='D')
            df_test = pd.DataFrame(index=date_range)

            # Calcul des heures de lever, coucher et transit du soleil
            sun_times = location.get_sun_rise_set_transit(df_test.index.tz_localize('UTC'))
            schedule = {
                'sunrise': pd.Timestamp(sun_times["sunrise"].dt.tz_convert(None).to_numpy()[0]),
                'sunset': pd.Timestamp(sun_times["sunset"].dt.tz_convert(None).to_numpy()[0]),
            }

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

        ## FLAG COLUMN

        df.insert(5, "FLAG_QC", 0)

        print("DF.COLUMNS = ", df.columns)

        ######## FILTERS #########

        ## RAIN

        df = funcs.rain_filter(df)

        print("filter Rain done")

        ## CHECK FOR MASSIVE INCREASE/DECREASE AT NIGHT IN 9H MAX

        # differences between consecutive mlh (taking NaN into account)
        df["diff"] = df["MLH"].diff()
        d = (df.day == 2) | (df.day == 3)
        df.loc[d, "diff"] = df.loc[d, "MLH"].diff()
        idx = df[np.isnan(df["diff"])].index.to_list()
        for i in idx:
            idx2 = df[df.index < i].MLH.last_valid_index()
            if idx2 is not None:
                if (i - idx2) < timedelta(hours=9):
                    # df["diff"][i] = df.MLH[i] - df.MLH[idx2]
                    df.loc[i, "diff"] = df.MLH[i] - df.MLH[idx2]

        df = funcs.massive_inc_night(
            df,
            values_qc["massive_inc_night"]["threshold_increase"],
            values_qc["massive_inc_night"]["time_steps_to_define_rolling_diff"],
        )

        print("filter Massive increase done")

        df = funcs.massive_dec_night(
            df,
            values_qc["massive_dec_night"]["threshold_decrease"],
            values_qc["massive_dec_night"]["time_steps_to_define_rolling_diff"],
        )

        print("filter Massive decrease done")

        ## REMOVE STUCK MLH AT DAY/WARM SEASONS

        df = funcs.absolute_stuck_mlh(df)

        print("filter Stuck MLH done")

        ## EXTREME POINTS

        if (month2 < 3) | (month2 > 11):
            df = funcs.extreme(
                df,
                values_qc["extreme"]["fraction_of_the_max_mlh_cold"],
                maxmlh,
            )
        else:
            df = funcs.extreme(
                df,
                values_qc["extreme"]["fraction_of_the_max_mlh_warm"],
                maxmlh,
            )

        print("filter Extreme points done")

        # TO BE UNCOMMENTED WHEN FUNCTION IS IMPROVED
        # MADE IN THE FIRST FOR CL51
        # SOME FIGURES OF TIME SERIES AT KARLOV CAN BE FOUND IN GIT REPO
        # print("artifical noise starts...")
        # df = artificial_noise (df)

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
        df = df.rename(index={a: b})

        for i in range(1, len(df)):
            df_day_2.loc[
                (
                        (df_day_2.index.time <= df.index.time[i])
                        & (df_day_2.index.time >= df.index.time[i - 1])
                ),
                "FLAG_QC",
            ] = df.FLAG_QC.iloc[i]

        ######## PREPARE L2A DATAFRAME TO BE FILLED WITH NEW FLAG_QC AND THEREFORE NEW MLH #########

        df2 = funcs.clean_time_array(xr.open_dataset(day_2a)).to_dataframe()

        df2["FLAG_QC"] = list(df_day_2["FLAG_QC"].astype(np.int32))
        df2["FLAG_QC"] = df2["FLAG_QC"][~np.isnan(df2["MLH"])]
        df2["MLH"] = df2[df2.FLAG_QC == 0]["MLH"]

        df2["MLH"] = df2["MLH"].fillna(-999)
        df2["FLAG_QC"] = df2["FLAG_QC"].fillna(-9)

        MLH = df2["MLH"].to_xarray()
        ds["MLH"] = MLH.transpose("time", "station")

        ds = ds.rename({"FLAG": "precip_FLAG"})

        FLAG_QC = df2["FLAG_QC"].astype(np.int32).to_xarray()
        ds["quality_FLAG"] = FLAG_QC.transpose("time", "station")
        print("MLH replaced, FLAG added")

        ######## PREPARE L2A DATASET TO BE FILLED WITH NEW VARIABLES #########
        # make sure that time is on just one day

        ds = ds.sel(time=slice(day2, day2))
        # Do some modifications on the dimensions
        ds = funcs.Change_dims(ds)
        # add attributes
        ds = funcs.Get_gloabal_attrs(ds, attrs_dict)
        ds = funcs.Get_vars_attr_enc(ds, attrs_dict)
        # Remove the attribute units to make it work
        ds["time"].attrs.pop("units")
        ds_enco = funcs.get_encoding(ds)
        ds.to_netcdf(
            output_day2a,
            encoding=ds_enco,
            mode="w",
            engine="netcdf4",
            unlimited_dims=["time", "station_name"],
        )

        print(f"output file created : {output_day2a}")

        ## CLOSE FILES
    return 0


######################### CHECK IF ARGUMENTS ARE READABLE/WRITABLE ##############################


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
# File of day + 1 L2A file (optional)
@click.argument(
    "day_3a",
    nargs=-1,
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
# Configuration of the quality control values toml file
@click.argument(
    "file_values_qca",
    nargs=1,
    type=click.Path(
        exists=True, readable=True, file_okay=True, dir_okay=False, resolve_path=True
    ),
)
# Configuration of the quality control values toml file
@click.argument(
    "config_attributes_file",
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


#################################### MAIN FUNCTION ##############################################


def main(
    day_1a: click.Path,
    day_2a: click.Path,
    day_3a: tuple[str, ...],
    config_filea: click.Path,
    file_values_qca: click.Path,
    config_attributes_file: click.Path,
    output_day2a: click.Path,
) -> None:
    ## CHECK IF FILES
    click.echo(click.format_filename(day_1a))
    click.echo(click.format_filename(day_2a))
    day_3a: str | None = day_3a[0] if day_3a else None
    click.echo(click.format_filename(day_3a) if day_3a else "None")
    click.echo(config_filea)
    click.echo(file_values_qca)
    click.echo(config_attributes_file)
    click.echo(click.format_filename(output_day2a))
    qc_daily_final(day_1a, day_2a, day_3a, config_filea, file_values_qca, config_attributes_file, output_day2a)


if __name__ == "__main__":
    sys.exit(main())
