#!/bin/bash -l

#run QC on L2A to create L2B

#SBATCH --mem=15g
#SBATCH --time=01:00:00



#rep='/home/mvanhove/STRATfinder/scripts/qc-sf-python/qc_daily_final.py'
#config_file='/home/eprofile/eprofile/script/stratfinder/config/settings_STRATfinder_falkenberg_chm15k_0.json'

rep='/home/mvanhove/STRATfinder/qc-sf-python-develop/qc_daily_final.py'
#config_file='/home/mvanhove/STRATfinder/scripts/v2022c_cl61_berlin/settings_STRATfinder_cl61_urbi_tempelhof.json'
#config_file='/home/mvanhove/STRATfinder/conf_files/settings_STRATfinder_hdv_cl61_temp.json'
config_file='/home/mvanhove/STRATfinder/stratfinder/config/settings_STRATfinder_magurele-rado_chm15k_B.json'
values_qc='/home/mvanhove/STRATfinder/qc-sf-python-develop/values_qc.toml'

module load nco/4.9.3
module load git/2.31.0
module load python/3.8-anaconda
source activate /home/jupyterweb/python_envs/pangeo/

#site='hdv'
#site='falkenberg'
#site='berlin'
site='magurele-rado'

#liste_2022_falkenberg=`ls /homedata/mvanhove/STRATfinder/2022/falkenberg/v2022c/eprofile_1a_LfalkenbergIchm15k_v01_202?????_000011_L2A_v2022c_2weights_os.nc` 
liste_2022_rado=`ls /homedata/mvanhove/L2A/rado/eprofile_L2A_STRATFINDER_magurele-rado_chm15k-B_v01_20210*.nc`
#liste_2022_hdv=`ls /homedata/mvanhove/CL61/HDV/stratfinder_v2022c/cl61_1a_LHdVPpr2R5mF30s_v01_20220???_000000_L2A_180m_v2022c_2weights_os.nc`


arr=($liste_2022_rado)

day1='nothing'
day1='/homedata/mvanhove/L2A/rado/eprofile_L2A_STRATFINDER_magurele-rado_chm15k-B_v01_20210214.nc'
day3='/homedata/mvanhove/L2A/rado/eprofile_L2A_STRATFINDER_magurele-rado_chm15k-B_v01_20210216.nc'
#day3='/homedata/mvanhove/CL61/HDV/stratfinder_v2022c/cl61_1a_LHdVPpr2R5mF30s_v01_20220602_000000_L2A_180m_v2022c_2weights_os.nc'
#day3='nothing'

iter=1

#for file in /homedata/mvanhove/STRATfinder/2022/falkenberg/v2022c/eprofile_1a_LfalkenbergIchm15k_v01_202*_000011_L2A_v2022c_2weights_os.nc
#do
#for file in /homedata/mvanhove/CL61_urbisphere/CL61_Berlin/new_data/raw2l1_set\(de.berlin.BETEMP\,ALC_T*\,20220729T000000_20220730T000000\)_version\(v1.0.1_L2A_120m_v2022a.nc
#do
for file in /homedata/mvanhove/L2A/rado/eprofile_L2A_STRATFINDER_magurele-rado_chm15k-B_v01_20210215.nc
do
#for file in /homedata/mvanhove/CL61/HDV/stratfinder_v2022c/cl61_1a_LHdVPpr2R5mF30s_v01_20220*_000000_L2A_180m_v2022c_2weights_os.nc
#do
#for file in /homedata/mvanhove/STRATfinder/2020/palaiseau/v2022c_572bc947/eprofile_1a_LpalaiseauIchm15k_v01_20200424_000011_L2A_v2022c_572bc947_noise_5_c1_p2_w14.nc
#do
 output_day2=${file%.nc}_L2B_develop.nc
 echo $day1
 echo $file
 echo $day3
 echo $output_day2

 python ${rep} ${day1} ${file} ${day3} ${config_file} ${values_qc} ${output_day2} 

 day1=$file
 file=$day3
 iter=$iter+1
 day3=${arr[$iter]}
 
 #mv /homedata/mvanhove/L2A/rado/eprofile_L2A_STRATFINDER_magurele-rado_chm15k-B_v01_2022????_L2B_develop.nc /homedata/mvanhove/L2B/rado
done

