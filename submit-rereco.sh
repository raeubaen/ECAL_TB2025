runs=( 20332 20331 20614 20615 20617 20625 20626 20651 20652 20653 20654 20655 20656 20657 20658 20659 )
for run in ${runs[@]}; do
  source re-reco.sh $run;
  echo "CHANGING RUN!!!"
done
