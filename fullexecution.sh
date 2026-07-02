#!/bin/bash

# --- launch settings with beam|laser as input parameter ---
if [ "$#" -lt 3 ]; then
    echo "Usage: $0 <run_number> <fragment_number> <beam|laser|beam+laser> [noplots] [nounpack]"
    exit 1
fi
RUN=$1
FRAGMENT=$(printf "%04d" $((10#$2)))
FRAGMENT_NO=$((10#$FRAGMENT))
mode=$3

if [ "$4" == "noplots" ]; then
  doplots="0"
else
  doplots="1"
fi

echo '$#: ' $#

dounpack=1
if [ $# -ge 4 ]; then
  echo '$# -ge 4 true'
  if [ $4 == "nounpack" ]; then
   echo  '$4 == "nounpack" true'
    dounpack=0
  elif [ $# -ge 5 ]; then
    echo '$# -ge 5 true'
    echo '$4 == "nounpack" false'
    if [ $5 == "nounpack" ]; then
      echo '$5 == "nounpack" true'
      dounpack=0
    fi
  fi
fi

echo '$4 $5: ' $4 $5

echo "unpack?" $dounpack
echo "plot?" $doplots

if [ "$mode" == "laser" ]; then
    option="laser"
elif [[ "$mode" == *"+laser" ]]; then
    # extract the part before +laser
    other="${mode%%+laser}"
    OPT=$(($FRAGMENT_NO % $FRAGMENT_LASER))
    if [ "$OPT" -eq 0 ]; then
        option="laser"
    else
        option="$other"
    fi
else
    option=$mode
fi

echo "fragment type is: " $option


FRAGMENT_STR="${FRAGMENT}_${option}"


# --- Start global timer ---
start_time=$(date +%s)


UNPACKED_FILE="${RECO_UNPACKED_OUTDIR}/DataTree_dqm/$RUN/${FRAGMENT}.root"

if [ "$dounpack" -ne 0 ]; then

  mkdir -p ${RECO_UNPACKED_OUTDIR}/DataTree_dqm/$RUN/

  if [ $UNPACKER_ROUTINE == "DANTE" ]; then

    cd ${DANTE_DIR}

    export LD_LIBRARY_PATH="${DANTE_DIR}/build:$LD_LIBRARY_PATH"

    echo "Unpacking run $RUN fragment $FRAGMENT with DANTE..."

    echo "./h4_raw2root ${RAW_DIR}/$RUN/$FRAGMENT.raw ${UNPACKED_FILE}"
    ./h4_raw2root ${RAW_DIR}/$RUN/$FRAGMENT.raw ${UNPACKED_FILE} > ${RECO_UNPACKED_OUTDIR}/DataTree_dqm/$RUN/${FRAGMENT}.txt

    echo "Unpacked DONE for run $RUN fragment $FRAGMENT with DANTE..."
  elif [ $UNPACKER_ROUTINE == "NUMPY" ]; then

    export PYTHONPATH=$PYTHONPATH:${NUMPY_UNPACKED_DIR}

    cd ${NUMPY_UNPACKED_DIR}
    echo "Unpacking run $RUN fragment $FRAGMENT with NUMPY..."

    echo "python3 test/unpack_fragment.py ${RAW_DIR}/$RUN/$FRAGMENT.raw ${UNPACKED_FILE}"

    python3 -m test.unpack_fragment ${RAW_DIR}/$RUN/$FRAGMENT.raw ${UNPACKED_FILE}

    echo "Unpacked DONE for run $RUN fragment $FRAGMENT with NUMPY..."
  else
    echo "Check your unpacking routind in the define .sh"
  fi
fi

cd ${WORKING_DIR}
mkdir -p ${RECO_UNPACKED_OUTDIR}/reco_dqm/run_$RUN/

PLOT_CURRENT_FOLDER=$PLOT_MAIN_FOLDER/run_$RUN/fragment_$FRAGMENT_STR/

if [ "$doplots" == "1" ]; then

  echo ${PLOT_MAIN_FOLDER}
  mkdir ${PLOT_MAIN_FOLDER}/run_${RUN}/
  mkdir ${PLOT_CURRENT_FOLDER}

  /bin/cp ${PHP_FILES_DIR}/*.php $PLOT_MAIN_FOLDER
  /bin/cp ${PHP_FILES_DIR}/*.php $PLOT_MAIN_FOLDER/run_$RUN/
  /bin/cp ${PHP_FILES_DIR}/*.php $PLOT_CURRENT_FOLDER
  echo "plotting in: $PLOT_CURRENT_FOLDER"

  plots_options="-po $PLOT_CURRENT_FOLDER"
else
  plots_options=""
fi

echo "Starting reconstruction..."

echo "doplots: " $doplots


cd ${WORKING_DIR}
cmd="python3 -m ferrari_core.reco -i ${UNPACKED_FILE} \
    -r "$RUN" \
    -s "$FRAGMENT" \
    -ro ${RECO_UNPACKED_OUTDIR}/reco_dqm_e-reso-tuned-origin/run_$RUN/ \
    -j ${JSON_CONF} \
    -opt $option \
    --do-plots $doplots $plots_options"

echo $cmd

eval $cmd

end_time=$(date +%s)
total_time=$((end_time - start_time))
echo "Total elapsed time: $total_time seconds."

if [ "$doplots" == "1" ]; then
  cp -rT "$PLOT_MAIN_FOLDER/run_$RUN/fragment_$FRAGMENT_STR" "$PLOT_MAIN_FOLDER/run_$RUN/${option}_current_fragment"

  if [ "$option" != "laser" ]; then
    echo "writing folder path to hadd buffer: $PLOT_MAIN_FOLDER/to_hadd_buffer.txt"
    echo $PLOT_CURRENT_FOLDER >> $PLOT_MAIN_FOLDER/to_hadd_buffer.txt
  fi

  if [ "$option" != "laser" ] && [ $((FRAGMENT_NO % FRAGMENT_HADD_INTERVAL)) -eq $((FRAGMENT_HADD_INTERVAL - 1)) ]; then
    cp $PLOT_MAIN_FOLDER/to_hadd_buffer.txt $PLOT_MAIN_FOLDER/to_hadd_now.txt
     echo "copying to hadd-now buffer"
  fi
fi
