#!/bin/bash
# Final authoritative run: lab experiment, then the same probes on the collected
# real-page corpus, then all analyses for both datasets.
set -u
cd "/e/Master assignment/semester1/cyber and Internet security/myproject" || exit 1
ROOT="$PWD"

echo "=== [1/3] lab experiment (standard profile) ==="
python run_all.py --profile standard

echo "=== [2/3] live measurement on the collected corpus ==="
rm -rf results_live
mkdir -p results_live
P5_RESULTS="$ROOT/results_live" python lab/lab_server.py > results_live/server.log 2>&1 &
SRV=$!
sleep 4
P5_RESULTS="$ROOT/results_live" python measure/measure.py --mode live \
    --urls config/target_urls.txt --max-live 7 --duration 20 --warmup 5 --sample-ms 300
kill $SRV 2>/dev/null
sleep 1

echo "=== [3/3] analyses ==="
for script in analyze_resources.py analyze_network.py evaluate_detector.py; do
    P5_RESULTS="$ROOT/results_live" python "analyze/$script"
done

echo "=== done ==="
