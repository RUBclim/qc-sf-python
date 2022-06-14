#!/bin/bash

for site in 'karlov' # 'roissy' 'cdg' 'uinversitedeparis' 'orly' 'payerne' 'libus' 'karlov' 'helsinki' 'vuosaari' 'lerwick' 
do
 qsub /home/mvanhove/STRATfinder/scripts/qc-sf-python/run_plot_sites_jason.sh -v site=${site}
done
