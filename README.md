## SCRIPT : qc_daily_final.py


### Arguments : L2A D-1 ;  L2A D ; L2A D+1 ;  config_file ;  L2B D 


### Rôle
Apply quality control on L2A to produce L2B


### Functions comments

Most of the thresholds and values defined in the quality control are empirical after the analysis of the MLH derived from STRATfinder. 

Time thresholds are defined relatively to sunrise and sunset 

Massive increases/decreases at nights differentiate residual and nocturnal layers, in which case, the lower layer is considered as the nocturnal layer and the higher one is flaggued.

The residual layers are identified by comparing the values with the maximum daytime MLH, or by comparing the MLH with empirical values  

The stuck_mlh filter is not applied in ```LERWICK,UK``` because of the climatological conditions of this site : oceanic and cold, so the MLH is often considered as 'stuck' by the filter. 

=> might add a criteria in the config file for every site to avoid writing the complete name in the code 


## SCRIPT : run_plot_sites_jason.sh

### Arguments : path_all_years, rep

path_all_years = path of directory containing annual L2B (RELEASE)

rep = output directory

### Rôle

Produce json files for climatology 

A json file contains median values relative to time relative to sunrise, first and third quartiles, for one month and one site. 

## SCRIPT : plot_sites_json.py

### Arguments : site ; month ; outfile.json
month = int (1,...,12)

### Rôle 
Plot the median cycle


