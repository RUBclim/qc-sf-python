#!/bin/bash
# run jason files for median cycles
#PBS -j oe
#PBS -o /home/mvanhove/STRATfinder/scripts/qc-sf-python/example.out
#PBS -q std



rep=$1  #/homedata/mvanhove/STRATfinder/climato
path_all_years=$2 #/homedata/mvanhove/STRATfinder/2*/{site}/ANNUAL/stratfinder_2b_{site}PmlhF1min_v01_*_V2022a.nc

module load nco/4.9.3

module load python/3.8-anaconda
source activate /home/jupyterweb/python_envs/pangeo/


for site in 'palaiseau' 'granada' 'magurele' 'saint-christophe-aosta' 'lerwick' 'lindenberg' 'qualair'
do
 echo "what? ${site}"

 for month in 1 2 3 4 5 6 7 8 9 10 11 12
 do
  #cd /home/mvanhove/STRATfinder/scripts/qc-sf-python
  python /home/mvanhove/STRATfinder/scripts/qc-sf-python/plot_sites_json.py ${site} ${path_all_years} ${month} ${rep}/${site}_${month}_SF.json
  
  echo "${site} done"
 done
done
