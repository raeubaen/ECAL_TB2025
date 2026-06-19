#!/bin/bash

set -e

if [ -z "$1" ] || [ -z "$2" ]; then
    echo "Error: Missing arguments."
    echo "Usage: $0 <run_number> <energy>"
    exit 1
fi
RUN=$1
ENERGY=$2

MAP_CSV="maps/tb_map.csv"
GAIN_CSV="plotter/resgainratios_3x3scan.csv"
RERECO_SCRIPT="ferrari_core/offline-scripts/re-reco.sh"
PLOTTER_SCRIPT="plotter/plotter_resolution_singlecrystal.py"
RECO_DIR="/eos/cms/store/group/dpg_ecal/comm_ecal/upgrade/testbeam/ECALTB_H4_Oct2025/re-reco/"
FIT_OUTPUT_DIR="/eos/user/l/lfaiella/www/h4dqm/ECAL_TB_2026_latestDQM/GainRatio/FitPlots3x3"

echo "gain_ratio,resolution,resolution_error,chi_squared" > "$GAIN_CSV"

START=0.96
STEP=0.0015
END=1.02

CURRENT=$START
while [ "$(echo "$CURRENT <= $END + 0.0001" | bc)" -eq 1 ]; do

    GAIN_RATIO=$(echo "scale=4; 10.2 * $CURRENT" | bc)
    echo "--------------------------------------------------"
    echo "Factor: $CURRENT | Gain Ratio: $GAIN_RATIO"
    echo "--------------------------------------------------"

    python3 -c "
import pandas as pd
df = pd.read_csv('$MAP_CSV')
df.loc[239, 'high_over_low_gain_ratio'] = $GAIN_RATIO
df.to_csv('$MAP_CSV', index=False)
"

    echo "Running re-reco for run $RUN..."
    bash "$RERECO_SCRIPT" "$RUN"

    echo "Running resolution plotter..."
    read RESOLUTION RESOLUTION_ERROR CHI_SQUARED < <(python3 "$PLOTTER_SCRIPT" -i $RECO_DIR -r $RUN -e $ENERGY -g $GAIN_RATIO -f $FIT_OUTPUT_DIR | grep "^RESULT" | awk '{print $2, $3, $4}')

    if [ -z "$RESOLUTION" ]; then
        echo "ERROR: Failed to extract resolution" >&2
        exit 1
    fi

    echo "Gain ratio: $GAIN_RATIO, Res: $RESOLUTION, eRes: $RESOLUTION_ERROR, chi: $CHI_SQUARED"
    echo "Writing in $GAIN_CSV"
    echo "${GAIN_RATIO},${RESOLUTION},${RESOLUTION_ERROR},${CHI_SQUARED}" >> "$GAIN_CSV"


    CURRENT=$(echo "scale=2; $CURRENT + $STEP" | bc)
done

echo "--------------------------------------------------"
echo "All iterations finished. Data saved to $GAIN_CSV"
