> **Note:** This repository is a fork of [gitlab.in2p3.fr/ipsl/sirta/mld/stratfinder/qc-sf-python](https://gitlab.in2p3.fr/ipsl/sirta/mld/stratfinder/qc-sf-python.git).

## Installation

Install in development mode:
```bash
pip install -e .
```

The package must be installed; importing or running CLI entrypoints without installation will fail.

## Usage

### CLI Entrypoint

After installation, use the `qc-sf` command:

```bash
qc-sf L2A_D-1.nc L2A_D.nc L2A_D+1.nc config.json values_qc.toml STRATFINDER_metadata.toml L2B_output.nc
```

Arguments:
- L2A D-1: L2A file for day D-1 (required)
- L2A D: L2A file for day D (required)
- L2A D+1: L2A file for day D+1 (optional, can be omitted if D is today)
- config.json: Site configuration file (required)
- values_qc.toml: QC threshold values (required)
- STRATFINDER_metadata.toml: Global attributes (required)
- L2B output: Output L2B file path (required)

### Programmatic Usage

```python
from qc_sf_python.qc_daily_final import qc_daily_final

qc_daily_final(
    day_1a="L2A_D-1.nc",
    day_2a="L2A_D.nc", 
    day_3a="L2A_D+1.nc",
    config_filea="config.json",
    file_values_qca="values_qc.toml",
    config_attributes_file="STRATFINDER_metadata.toml",
    output_day2a="L2B_output.nc"
)
```

## Quality Control

Applies adaptive filters to flag and remove erroneous MLH values. Thresholds are empirically determined from STRATfinder MLH analysis and are defined relative to sunrise/sunset times.

### Filters

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
This function removes values that are above the maximum climatological MLH in warm and intermediate seasons (March to November), and above 0.75 times the maximum climatological MLH in winter (DJF).

## CLI Utilities

### plot-daily
Generates comparison plots of L2A (original) vs L2B (quality-controlled) MLH.

```bash
plot-daily L2A.nc L2B.nc output.png
```

### plot-sites-json
Produces climatological JSON profiles (median, Q1, Q3) of MLH by month and site.

```bash
plot-sites-json file.nc output.json
```


