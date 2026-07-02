#!/bin/bash

#DRAFT COPIED FROM CRILIN CODE - REDO!!! FAST BUT COMPULSORY!

#folder=$(ls -1 local/rawdata | sort -V | tail -n 1)

#lastfile=$(ls -1 local/rawdata/$folder | sort -V | tail -n 2 | head -n 1)

rm -f /tmp/current_file.txt

orig=$(pwd)

while true; do

        sleep 0.1
        xrdcp -f "/eos/cms/store/group/dpg_ecal/comm_ecal/upgrade/testbeam/ECALTB_H4_Jun2026/run_list.txt" /tmp/last_file.txt

        echo "last: $(cat /tmp/last_file.txt), current: $(cat /tmp/current_file.txt)"

	if [ ! -e /tmp/current_file.txt ]; then
	    /bin/cp /tmp/last_file.txt /tmp/current_file.txt;
	elif ! cmp -s /tmp/last_file.txt /tmp/current_file.txt; then
            echo "è cambiato..."
	    /bin/cp /tmp/last_file.txt /tmp/current_file.txt;
	else
            echo "non è cambiato"
	    continue
        fi

        echo reco starting

  #TOCCA MANDA PROCESS_RUN QUA!!
#  
#	filename=$(cat /tmp/last_file.txt | awk '{print $1}')
	run=$(cat /tmp/last_file.txt | awk '{print $1}')
	fragment=$(cat /tmp/last_file.txt | awk '{print $2}')
	filename=$(cat /tmp/last_file.txt | awk '{print $3}')
	mode=$(cat /tmp/last_file.txt | awk '{print $4}')
	

	echo $run
	echo $fragment
	echo $mode
	echo './fullexecution.sh ${run} $fragment $mode'
	./fullexecution.sh $run $fragment $mode 
#	conf=$(cat /tmp/last_file.txt | awk '{print $2}')
#
#	run_name=$(echo $filename | awk -F '_' '{print $(NF-3)}')
#	n_fragment=$(echo $filename | awk -F '/' '{print $NF}' | awk -F '_' '{print $NF}' | awk -F '.' '{print $1}')
#
#	echo "--------------- runname,fragment: $run_name, $n_fragment"
#
#	unpacked_xrd="root://eospublic.cern.ch/$filename"
#	reco_xrd="root://eospublic.cern.ch//eos/experiment/muoncollider/data/crilin/h2-2025/gpu_reco_files/reco_${run_name}_${n_fragment}.root"
#
#	mkdir -p /root/reco_files/${run_name}
#
#	#source /cvmfs/sft.cern.ch/lcg/views/LCG_107/x86_64-el9-gcc11-opt/setup.sh
#
#	mkdir -p /root/plot_files/$run_name/current_fragment/
#
#        echo "----------------------- /root/plot_files/$run_name/current_fragment/ -----------------------"
#	python3 -m ferrari_core.reco -ro /root/reco_files/${run_name}/ -i $filename -po /eos/user/r/rgargiul/www/test_ferrari_on_crilin_from_gpu/ -j /root/crilin_reco_from_padme_daq/confs/$conf.json -opt electrons -r ${run_name} -s ${n_fragment}
#
#	xrdcp -f /root/reco_files/$run_name/reco_$n_fragment.root $reco_xrd &
#        break

done

cd $orig
