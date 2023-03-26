#!/bin/bash -l

#run QC on L2A to create L2B

#SBATCH --mem=15g
#SBATCH --time=01:00:00



rep='/home/mvanhove/STRATfinder/qc-sf-python/qc_daily_final.py'
#config_file='/home/mvanhove/STRATfinder/scripts/v2022c_cl61_berlin/settings_STRATfinder_cl61_urbi_tempelhof.json'
#config_file='/home/mvanhove/STRATfinder/stratfinder/config/settings_STRATfinder_granada_chm15k_A.json'
config_file='/home/mvanhove/STRATfinder/stratfinder/config/settings_STRATfinder_palaiseau_chm15k_B.json'
values_qc='/home/mvanhove/STRATfinder/qc-sf-python/values_qc.toml'
config_attributes_file='/home/mvanhove/STRATfinder/qc-sf-python/STRATFINDER_metadata.toml'
module load nco/4.9.3
module load git/2.31.0
module load python/3.8-anaconda
source activate /home/jupyterweb/python_envs/pangeo/



#liste_2022_falkenberg=`ls /homedata/mvanhove/STRATfinder/2022/falkenberg/v2022c/eprofile_1a_LfalkenbergIchm15k_v01_202?????_000011_L2A_v2022c_2weights_os.nc` 
liste_2022_rado=`ls /homedata/mvanhove/L2A/rado/eprofile_L2A_STRATFINDER_magurele-rado_chm15k-B_v01_20210*.nc`
#liste_2022_hdv=`ls /homedata/mvanhove/CL61/HDV/stratfinder_v2022c/cl61_1a_LHdVPpr2R5mF30s_v01_20220???_000000_L2A_180m_v2022c_2weights_os.nc`


arr=($liste_2022_rado)

day1='nothing'
day1='/homedata/mvanhove/L2A/palaiseau/eprofile_L2A_STRATFINDER_palaiseau_chm15k-B_v01_20220718.nc'
day3='/homedata/mvanhove/L2A/palaiseau/eprofile_L2A_STRATFINDER_palaiseau_chm15k-B_v01_20220720.nc'
#day3='/homedata/mvanhove/CL61/HDV/stratfinder_v2022c/cl61_1a_LHdVPpr2R5mF30s_v01_20220602_000000_L2A_180m_v2022c_2weights_os.nc'
#day3='nothing'

iter=1

#for file in /homedata/mvanhove/STRATfinder/2022/falkenberg/v2022c/eprofile_1a_LfalkenbergIchm15k_v01_202*_000011_L2A_v2022c_2weights_os.nc
#do
#for file in /homedata/mvanhove/CL61_urbisphere/CL61_Berlin/new_data/raw2l1_set\(de.berlin.BETEMP\,ALC_T*\,20220729T000000_20220730T000000\)_version\(v1.0.1_L2A_120m_v2022a.nc
#do
for file in /homedata/mvanhove/L2A/palaiseau/eprofile_L2A_STRATFINDER_palaiseau_chm15k-B_v01_20220719.nc
#for file in /homedata/mvanhove/L2A/granada/eprofile_L2A_STRATFINDER_granada_chm15k-A_v01_20220823.nc
do

 output_day2=${file%.nc}_L2B.nc
 echo $day1
 echo $file
 echo $day3
 echo $output_day2

 python ${rep} ${day1} ${file} ${day3} ${config_file} ${values_qc} ${config_attributes_file} ${output_day2} 

 day1=$file
 file=$day3
 iter=$iter+1
 day3=${arr[$iter]}
 
 #mv /homedata/mvanhove/L2A/rado/eprofile_L2A_STRATFINDER_magurele-rado_chm15k-B_v01_2022????_L2B_develop.nc /homedata/mvanhove/L2B/rado
done

