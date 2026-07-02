#!/bin/bash

# --- launch settings with beam|laser as input parameter ---
if [ "$#" -lt 3 ]; then
    echo "Usage: $0 <run_number> <fragment_number> <fragment_type>"
    return
fi
RUN=$1
FRAGMENT=$(printf "%04d" $((10#$2)))
OPTION=$3

echo run: $RUN
echo fragment: $FRAGMENT
echo FRAGMENT_TYPE: $OPTION

FRAGMENT_STR="${FRAGMENT}_${OPTION}"

mkdir ${PLOT_MAIN_FOLDER}/run_$RUN/

RECO_FILE=${RECO_UNPACKED_OUTDIR}/reco_dqm/run_$RUN/${RUN}_${FRAGMENT}_reco.root
PLOT_FRAGMENT_FOLDER=${PLOT_MAIN_FOLDER}/run_$RUN/fragment_${FRAGMENT_STR}

python3 -m ferrari_core.offline-scripts.plot_uproot_numpysyntax -i ${RECO_FILE} -po ${PLOT_FRAGMENT_FOLDER} -j ${JSON_CONF} -opt $OPTION

