# Detector evaluation

- windows: 5s sliding by 1s over 14 trials = 210 instances
- ground truth: 'mining' trials are positives; clean and the matched-CPU 'busy' control are negatives
- rules: CPU p95 >= 0.8 cores held, sustained >= 0.6 of window, and >= 1 page-owned long-lived socket (a WebSocket the page itself opened, from CDP, or a connection created during the visit and still open); machine-wide uplink steadiness is logged as a feature but not required, since those counters also carry unrelated background traffic

## Feature means by condition

| condition | windows | CPU p95 (cores) | est. sockets | persistent sockets | page WebSockets | up kbps | up CV | detected CPU-only % | detected combo % |
|---|---|---|---|---|---|---|---|---|---|
| live:example.com | 30 | 0.07 | 15.5 | 0.0 | 0.0 | 83.22 | 2.01 | 0.0 | 0.0 |
| live:httpbin.org/html | 30 | 0.05 | 8.1 | 0.0 | 0.0 | 31.37 | 1.75 | 0.0 | 0.0 |
| live:lab:8080/busy | 30 | 2.16 | 4.0 | 0.0 | 0.0 | 1109.0 | 2.4 | 100.0 | 0.0 |
| live:lab:8080/clean | 30 | 0.08 | 3.0 | 0.0 | 0.0 | 47.61 | 1.9 | 0.0 | 0.0 |
| live:lab:8080/mining | 30 | 2.17 | 5.5 | 0.0 | 1.0 | 11.71 | 1.9 | 100.0 | 100.0 |
| live:www.python.org | 30 | 0.17 | 9.6 | 0.0 | 0.0 | 40.98 | 2.07 | 0.0 | 0.0 |
| live:www.wikipedia.org | 30 | 0.06 | 17.5 | 0.0 | 0.0 | 73.1 | 2.1 | 0.0 | 0.0 |

## Confusion matrices

- CPU alone: TP 60 / FP 0 / FN 0 / TN 150  precision 1.000  recall 1.000  F1 1.000  false alarm 0.000
- CPU + raw socket *count* (default thresholds): TP 0 / FP 0 / FN 60 / TN 150  precision nan  recall 0.000  F1 0.000  false alarm 0.000
- CPU + persistent page sockets (default thresholds): TP 30 / FP 0 / FN 30 / TN 150  precision 1.000  recall 0.500  F1 0.667  false alarm 0.000
- thresholds chosen on odd-numbered trials, scored on even-numbered ones (105 train / 105 test windows)
- tuned detector on held-out trials (CPU 0.2 cores, sockets >= 1): TP 15 / FP 0 / FN 15 / TN 75  precision 1.000  recall 0.500  F1 0.667  false alarm 0.000

## Cross-check with the static page scan

- static findings: {'miner': 2, 'clean': 5} over 7 scanned pages
