cd ${WORKING_DIR}
echo ${WORKING_DIR}

timeout 30s ./fullexecution.sh "$@" 2>&1 | tee ${LOGS_DIR}/log_run${1}_fragment${2}_typeis${3}.log
