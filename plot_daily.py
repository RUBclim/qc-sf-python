#!/usr/bin/env python

import os
import sys
import click
import grp
import pwd

import xarray as xr
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd

from matplotlib import figure
from datetime import date
from typing import Tuple, List
from pathlib import Path

#from solartime import SolarTime
from pvlib.location import Location

__version__ = "1.0.0"
__author__ = "Melania Van Hove"


## -----------------------------------------------DESCRIPTION----------------------------------------------
## Script creating the figure showing the flaggued MLH at day D (L2B) over the original MLH (L2A)
## --------------------------------------------------------------------------------------------------------


@click.command()
# L2A file
@click.argument(
    "l2a",
    nargs=1,
    type=click.Path(
        exists=False, readable=True, file_okay=True, dir_okay=False, resolve_path=True
    ),
)
# L2B file
@click.argument(
    "l2b",
    nargs=1,
    type=click.Path(
        exists=False, readable=True, file_okay=True, dir_okay=False, resolve_path=True
    ),
)
# output file
@click.argument(
    "output",
    nargs=1,
    type=click.Path(
        exists=False, readable=True, file_okay=True, dir_okay=False, resolve_path=True
    ),
)
def main(l2a: Path, l2b: Path, output: Path) -> None:
    """Creates the figure showing the flaggued MLH at day D

    Args:
        l2a (click.argument): L2A file of the d day
        l2b (click.argument): L2B file of the d day
        output (click.argument): Output of the quicklooks files
    Returns:
        figure : figure of the flaggued MLH
    """
    # Check if the file
    click.echo(click.format_filename(l2a))
    click.echo(click.format_filename(l2b))
    click.echo(click.format_filename(output))

    ## CONFIGURATION
    with xr.open_dataset(l2a) as dsa, xr.open_dataset(l2b) as dsb:
        site = dsa.attrs["site_location"]

        ## PLOT
        plt.figure(figsize=(20, 10))
        ax = plt.gca()
        df1 = dsa.to_dataframe()
        df1 = df1.reset_index(level=1, drop=True)
        df2 = dsb.to_dataframe()
        df2 = df2.reset_index(level=1, drop=True)
        lat = df1.station_latitude[0]
        lon = df1.station_longitude[0]
        #sun = SolarTime()

        location = Location(lat, lon, tz='UTC')
        date_ = date(
            int(df1.index.year[0]), int(df1.index.month[0]), int(df1.index.day[0])
        )
        date_range = pd.date_range(start=date_, periods=1, freq='D')

        df_test = pd.DataFrame(index=date_range)
        #schedule = sun.sun_utc(date_, lat, lon)
        # Calcul des heures de lever, coucher et transit du soleil
        sun_times = location.get_sun_rise_set_transit(df_test.index.tz_localize('UTC'))
        schedule = {'sunrise':pd.Timestamp(sun_times["sunrise"].values[0]), 'sunset':pd.Timestamp(sun_times["sunset"].values[0])}

        ss = schedule["sunset"]
        sr = schedule["sunrise"]

        x = df2.index.to_list()

        df1["MLH"].plot(
            x_compat=True,
            ax=ax,
            style=".",
            markersize=10,
            color="grey",
            label="Data removed",
        )
        df2["MLH"].plot(
            x_compat=True,
            ax=ax,
            style=".",
            markersize=10,
            color="limegreen",
            label="Data kept",
        )

        ax.xaxis.set_major_locator(mdates.DayLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m/%y"))
        ax.xaxis.set_minor_locator(mdates.HourLocator((0, 3, 6, 9, 12, 15, 18, 21)))
        ax.xaxis.set_minor_formatter(mdates.DateFormatter("%H:%M"))
        ax.xaxis.grid(True, which="minor")

        for tick in ax.xaxis.get_major_ticks():
            tick.label.set_fontsize(20)
        for tick in ax.xaxis.get_minor_ticks():
            tick.label.set_fontsize(20)

        plt.vlines(sr, 0, 4000, "orange", label="Sunrise")
        plt.vlines(ss, 0, 4000, "k", label="Sunset")

        plt.yticks(fontsize=20)
        plt.ylabel("MLH (m)", fontsize=20)
        plt.title(
            f"Mixed layer height after quality control - STRATfinder - {site}",
            fontsize=20,
            y=1.1,
        )
        plt.fill_betweenx([0, 4000], x[0], sr, alpha=0.1, color="skyblue")
        plt.fill_betweenx([0, 4000], ss, x[len(x) - 1], alpha=0.1, color="skyblue")

        plt.ylim([0, 4000])
        legend1 = plt.legend(
            fontsize=18,
            loc="upper right",
            shadow=True,
            facecolor="ghostwhite",
            ncol=2,
            borderaxespad=4.0,
        )

        plt.tight_layout()
        plt.grid()
        plt.savefig(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
