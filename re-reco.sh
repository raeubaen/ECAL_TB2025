RUN=$1

echo Run: $RUN

RECO_FOLDER="${RECO_UNPACKED_OUTDIR}/reco_dqm/"
LOGS_FOLDER="${RECO_UNPACKED_OUTDIR}/re-reco/re-reco-logs/"

DONE_FILE="/tmp/done_files.txt"

mkdir -p $LOGS_FOLDER

echo "LOGS in " ${LOGS_FOLDER}

echo > $DONE_FILE


for fragment_str in $(ls -1 "$RECO_FOLDER/run_$RUN/${RUN}_"*.root | awk -F "_" '{print $(NF-1)}'); do

    # Convert fragment number safely (leading zeros → decimal)
    fragment=$((10#$fragment_str))

    #if (( fragment % $FRAGMENT_LASER == 0 )); then
    #    echo "Skipping fragment $fragment (divisible by $FRAGMENT_LASER)"
    #    continue
    #fi

    RECO_FOLDER="${RECO_UNPACKED_OUTDIR}/reco_dqm_treso/"
    echo $RECO_FOLDER/run_$RUN/${RUN}_$(printf "%04d" $((10#$fragment)))_reco.root >> $DONE_FILE

    echo "Processing fragment $fragment"

    mkdir -p $LOGS_FOLDER/log_${RUN}

    cd $WORKING_DIR

    # Launch background job for this actual fragment
    bash -c "./process_fragment.sh $RUN $fragment electrons noplots nounpack >  $LOGS_FOLDER/log_${RUN}/log_${RUN}_${fragment}.log 2>&1 &"

    while true; do
        running=$(ps aux | grep "bash -c ./process_fragment.sh" | grep -v grep | wc -l)
        if (( running < 12 )); then
            break
        fi
        sleep 1
    done

done

echo list of files re-recoed in $DONE_FILE
