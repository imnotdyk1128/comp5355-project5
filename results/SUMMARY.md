# Project 5 - characterising browser-based crypto mining: summary

- captured 2026-10-26T08:57:39.902+00:00 on Windows 11 AMD64, 20 logical cores, 15.7 GB RAM, 156.0.4314.42 (headless)
- experiment: lab mode, window 30.0 s x 2 trials, threads [1, 2, 4], sample 250 ms

## Detection

- windows evaluated: 350, socket threshold 1.0
- CPU-only rule: {"TP": 150, "FP": 150, "FN": 0, "TN": 50, "precision": 0.5, "recall": 1.0, "f1": 0.6666666666666666, "false_alarm_rate": 0.75}
- CPU + sockets: {"TP": 150, "FP": 0, "FN": 0, "TN": 200, "precision": 1.0, "recall": 1.0, "f1": 1.0, "false_alarm_rate": 0.0}
- tuned, held-out trials: {"TP": 75, "FP": 0, "FN": 0, "TN": 100, "precision": 1.0, "recall": 1.0, "f1": 1.0, "false_alarm_rate": 0.0}

## Network profile

- mining sockets: 6, mean lifetime 33.75 s, 62.5 frames each
- message mix: {'auth': 6, 'job': 75, 'share': 145, 'ack': 145, 'set_diff': 4}
- mean uplink per mining socket: 0.886 kbps (total 38394.0 bytes)

## Deliverable documents

- results/analysis/resources/resource_table.md - with/without mining resource comparison
- results/analysis/network/network_report.md - connection and message analysis
- results/analysis/detector/detector_report.md - detector confusion matrices and thresholds
- figures: results/analysis/*/fig_*.tiff (300 dpi) and .png previews
- method notes and how to rerun: README.md