#!/usr/bin/env python

import os
import sys
from matplotlib import figure
from datetime import date, timedelta 
import xarray as xr
from solartime import SolarTime
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

## ARGUMENTS : L2A,  L2B, SITE, FICHIER DE SORTIE QL 

isFile1 = os.path.isfile(sys.argv[1])
isFile2 = os.path.isfile(sys.argv[2])   ## vérif de si fichier existe ok, mais est-il lisible, etc.. ? => module click : créer fonction qui prend en argument les 
					#+ ajouter décorateur (@) qui décrivent arguments de la fonction : voir lien slack 
site = str(sys.argv[3])
output = sys.argv[4]




## CONFIGURATION

lat = {"palaiseau": 48.714509, "payerne": 46.8220266, "libus" : 50.0755381, 
           "karlov" : 49.384900, "helsinki" : 60.2058, "vuosaari" : 60.2058, "lerwick" : 60.152988,
             "orly" :  48.7145, "roissy" :  48.7145, "universitedeparis" :  48.7145, "cdg" :  48.7145}

lon = {"palaiseau": 2.245748, "payerne": 6.9405663, "libus" : 14.4378005, 
           "karlov" : 15.545200, "helsinki" : 24.9542, "vuosaari" : 24.9542, "lerwick" : -1.149293,
              "orly" : 2.245748, "roissy" : 2.245748, "universitedeparis" : 2.245748, "cdg" : 2.245748}




## PLOT

if (isFile1 == True) & (isFile2 == True) :

    #fig, ax = plt.subplots(1, 1)	
    plt.figure(figsize=(20, 10))
    ax = plt.gca()
    df1 = xr.open_dataset(sys.argv[1]).to_dataframe()
    df1 = df1.reset_index(level=0, drop=True) 
    df2 = xr.open_dataset(sys.argv[2]).to_dataframe()
    df2 = df2.reset_index(level=0, drop=True) 
    sun = SolarTime()

    date = date(df1.index.year[0], df1.index.month[0], df1.index.day[0])
    schedule = sun.sun_utc(date, lat[site], lon[site]) 
    ss = schedule['sunset']
    sr = schedule['sunrise']

    #print(sr)
    			
    
    x = df1.index.to_list()
    #xday = df1.index.date[0]
    y = df1.MLH
    y2 = df2.MLH
  

    #plt.plot(x, y,  'co', markersize = 4, label = "Data removed")
    df1['MLH'].plot(x_compat=True, ax=ax, marker = '.', markersize = 10, color = 'grey', label = "Data removed")
    #plt.plot(x, y2, 'yo',  markersize = 4, label = "Data kept")
    df2['MLH'].plot(x_compat=True, ax=ax, marker = '.', markersize = 10, color = 'limegreen', label = "Data kept")

    ax.xaxis.set_major_locator(mdates.DayLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m/%y'))
    ax.xaxis.set_minor_locator(mdates.HourLocator((0,3,6,9,12,15,18,21)))
    ax.xaxis.set_minor_formatter(mdates.DateFormatter('%H:%M'))
    ax.xaxis.grid(True, which='minor')
    
    for tick in ax.xaxis.get_major_ticks():
        tick.label.set_fontsize(20) 
    for tick in ax.xaxis.get_minor_ticks():
        tick.label.set_fontsize(20) 

    plt.vlines(sr, 0, 4000, 'orange', label = 'Sunrise')
    plt.vlines(ss, 0, 4000, 'k', label = 'Sunset')

    plt.yticks(fontsize = 20)
    #plt.xlabel("Date", fontsize = 20)
    plt.ylabel("MLH (m)", fontsize = 20)
    plt.title(f"Mixed layer height after quality control - STRATfinder - {site}" , fontsize = 20, y = 1.1)

    plt.fill_betweenx([0,4000], x[0], sr, alpha=0.1, color = 'skyblue')
    plt.fill_betweenx([0,4000], ss, x[len(x)-1], alpha=0.1, color = 'skyblue')

    plt.ylim([0,4000])
    legend1 = plt.legend(fontsize=18, loc = "upper right", shadow = True, facecolor = 'ghostwhite',
              ncol=2,  borderaxespad= 4.)#, bbox_to_anchor=(-0.0, 1.16, 1.10, .102) )

    plt.tight_layout()
    plt.grid()
    plt.savefig(output)

else :
    print('error with files')
