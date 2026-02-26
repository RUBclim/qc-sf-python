## SCRIPT : qc_daily_final.py


### Arguments : L2A D-1 ;  L2A D ; L2A D+1 ;  config_file ; values_qc ; values_attr ; L2B D 

L2A D-1 : path of file D-1

L2A D : path of file D

L2A D+1 : path of file D+1

config_file : path of the configuration file (there should be one for each site)

values_qc = path of file ```values_qc.toml```

values_attr = path of file ```STRATFINDER_metadata.toml```



### Rôle
Apply quality control on L2A to produce L2B


### Functions

Most of the thresholds and values defined in the quality control are empirical after the analysis of the MLH derived from STRATfinder. 

Time thresholds are defined relatively to sunrise and sunset 

Massive increases/decreases at nights differentiate residual and nocturnal layers, in which case, the lower layer is considered as the nocturnal layer and the higher one is considered as a residual layer, and flagged.

The absolute_stuck_mlh filter flags "stuck" MLH that occurs with STRATinder, if more than 2h30 of MLH is at the exact same value (no variation of 15m, which is considered physically unreasonable) 

#### rain_filter
Around periods where the variable FLAG of the L1 level file is > 0 (indicating rain):

For each index where FLAG > 0, it adds a flag 15 minutes before and after the rain event.
This ensures a wider time window around rain events is flagged to account for residual disturbances.

#### absolute_stuck_mlh
This function flags periods where the MLH (Mixed Layer Height) is "stuck" at the same value for more than 2.5 hours (10 consecutive time steps, assuming 15-minute intervals). This typically occurs at night when no nocturnal boundary layer (NL) is detected or when the MLH is below a low limit. The function adds a flag (FLAG_QC = 10) to these periods and extends the flag to ±2 time steps (30 minutes before/after) to account for residual effects.

#### massive_inc_night
This function detects and flags residual layers preceding a sharp increase in nocturnal boundary layer height (MLH) exceeding 200 meters in a time range of 30min. When such an increase is detected, the function assumes the true nocturnal layer is the lower layer and flags overestimated values in the subsequent hours, either until the end of the night or until a decrease is observed, which corresponds to a decrease of at least 200m in 30min. 

#### massive_dec_night
This function detects and flags residual layers preceding a sharp decrease in nocturnal boundary layer height (MLH) exceeding 200 meters in a time range of 30min. When such an decrease is detected, the function assumes the true nocturnal layer is the lower layer and flags overestimated values in the preceding hours, either until the beginning of the night (SS+3) or until a increase is observed. 

#### extreme
THis fuction removes values that are above the maximum climatological MLH in warm and intermediate seasons (March to November), and above 0.75 times the maximum climatological MLH in winter (DJF).


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


