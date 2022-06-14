# SCRIPT : qc_daily_final.py

## Arguments : L2A J-1 ;  L2A J ; L2A J+1 ;  config_file ;  L2B J 

### Rôle
Applique le contrôle de qualité sur le L2A et ainsi produit les L2B



# SCRIPT : run_plot_sites_jason.sh

## Arguments : nrep
rep = dossier contenant les fichiers L2B annuels

### Rôle
Lance le script de production des json files pour la climatologie


# SCRIPT : plot_sites_json.py

## Arguments : site ; month ; outfile.json
month = int (1,...,12)

### Rôle 
Script de production des json files de climatologie : 1 fichier par mois et par site
Le json file contient la mediane, le premier quartile et le troisième quartile, le tout en fonction du temps relatif au lever du soleil (en h)


