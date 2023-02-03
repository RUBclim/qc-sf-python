#!/usr/bin/env python

import os
import sys

from matplotlib import figure
from datetime import date
import click
import xarray as xr
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import grp
import pwd
from typing import Tuple, List
from pathlib import Path

from solartime import SolarTime

__version__ = "1.0.0"
__author__ = "Melania Van Hove"
## ARGUMENTS : L2A,  L2B, SITE, FICHIER DE SORTIE QL


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
    """ 

    Args:
        l2a (click.argument): L2A file of the d day 
        l2b (click.argument): L2B file of the d day 
        output (click.argument): Output of the quicklooks files
    """
    # Check if the file
    click.echo(click.format_filename(l2a))
    click.echo(click.format_filename(l2b))
    click.echo(click.format_filename(output))
    isFile1 = os.path.isfile(l2a)
    isFile2 = os.path.isfile(l2b)

    ## CONFIGURATION
    with xr.open_dataset(l2a) as dsa, xr.open_dataset(l2b) as dsb:
        site = dsa.attrs["site_location"]

        ## PLOT

        if (isFile1 == True) & (isFile2 == True):

            plt.figure(figsize=(20, 10))
            ax = plt.gca()
            df1 = dsa.to_dataframe()
            df1 = df1.reset_index(level=0, drop=True)
            df2 = dsb.to_dataframe()
            df2 = df2.reset_index(level=0, drop=True)
            lat = df1.station_latitude[0]
            lon = df1.station_longitude[0]
            sun = SolarTime()

            date = date(
                int(df1.index.year[0]), int(df1.index.month[0]), int(df1.index.day[0])
            )
            schedule = sun.sun_utc(date, lat, lon)
            ss = schedule["sunset"]
            sr = schedule["sunrise"]

            x = df2.index.to_list()
            y = df1.MLH
            y2 = df2.MLH

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
            # print('x[0] = ', x[0], 'SR =', sr)
            plt.fill_betweenx([0, 4000], x[0], sr, alpha=0.1, color="skyblue")
            # print('x = ', x, ' x[len(x)-1] = ',  x[len(x)-1], 'SS =', ss)
            plt.fill_betweenx([0, 4000], ss, x[len(x) - 1], alpha=0.1, color="skyblue")

            plt.ylim([0, 4000])
            legend1 = plt.legend(
                fontsize=18,
                loc="upper right",
                shadow=True,
                facecolor="ghostwhite",
                ncol=2,
                borderaxespad=4.0,
            )  # , bbox_to_anchor=(-0.0, 1.16, 1.10, .102) )

            plt.tight_layout()
            plt.grid()
            plt.savefig(output)
            uid = pwd.getpwnam("eprofile").pw_uid
            gid = grp.getgrnam("eprofile").gr_gid
            os.chmod(output, 0o644)
            os.chown(output, uid, gid)

        else:
            print("error with the files")
    return 0


if __name__ == "__main__":
    sys.exit(main())

