#!/bin/bash
# run jason files for median cycles
#PBS -j oe
#PBS -o /home/mvanhove/STRATfinder/scripts/qc-sf-python/example.out
#PBS -q std



rep='/home/mvanhove/STRATfinder/scripts/qc-sf-python/qc_daily_final.py'
config_file='/home/eprofile/eprofile/script/stratfinder/config/settings_STRATfinder_palaiseau_chm15k_B.json'

module load nco/4.9.3

module load python/3.8-anaconda
source activate /home/jupyterweb/python_envs/pangeo/


for site in 'palaiseau'   #'qualair' 'palaiseau' 'granada' 'magurele' 'saint-christophe-aosta' 'lerwick' 'lindenberg' #'qualair'
do
 echo "what? ${site}"
 #for day in 19                        #1 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 
 day1='/homedata/mvanhove/STRATFINDER/outfiles/palaiseau_18_12_2020.nc'
 day2='/homedata/mvanhove/STRATFINDER/outfiles/palaiseau_19_12_2020.nc'
 day3='/homedata/mvanhove/STRATFINDER/outfiles/palaiseau_20_12_2020.nc'
 output_day2='/homedata/mvanhove/STRATFINDER/outfiles/palaiseau_19_12_2020_l2b.nc'
 #cd /home/mvanhove/STRATfinder/scripts/qc-sf-python
 python ${rep} ${day1} ${day2} ${day3} ${config_file} ${output_day2} 
  
 echo "${site} done"
 #done
done
