# Detector evaluation

- windows: 5s sliding by 1s over 14 trials = 350 instances
- ground truth: 'mining' trials are positives; clean and the matched-CPU 'busy' control are negatives
- rules: CPU p95 >= 0.8 cores held, sustained >= 0.6 of window, and >= 1 page-owned long-lived socket (a WebSocket the page itself opened, from CDP, or a connection created during the visit and still open); machine-wide uplink steadiness is logged as a feature but not required, since those counters also carry unrelated background traffic

## Feature means by condition

| condition | windows | CPU p95 (cores) | est. sockets | persistent sockets | page WebSockets | up kbps | up CV | detected CPU-only % | detected combo % |
|---|---|---|---|---|---|---|---|---|---|
| busy-w1 | 50 | 1.07 | 15.1 | 0.0 | 0.0 | 62.18 | 1.87 | 100.0 | 0.0 |
| busy-w2 | 50 | 2.06 | 5.7 | 0.0 | 0.0 | 28.24 | 1.86 | 100.0 | 0.0 |
| busy-w4 | 50 | 4.1 | 4.0 | 0.0 | 0.0 | 685.24 | 2.18 | 100.0 | 0.0 |
| clean | 50 | 0.11 | 14.8 | 0.0 | 0.0 | 1402.86 | 0.88 | 0.0 | 0.0 |
| mining-w1 | 50 | 1.07 | 5.0 | 0.0 | 1.0 | 27.15 | 1.93 | 100.0 | 100.0 |
| mining-w2 | 50 | 2.15 | 5.0 | 0.0 | 1.0 | 30.59 | 2.28 | 100.0 | 100.0 |
| mining-w4 | 50 | 4.09 | 5.0 | 0.0 | 1.0 | 69.95 | 2.7 | 100.0 | 100.0 |

## Confusion matrices

- CPU alone: TP 150 / FP 150 / FN 0 / TN 50  precision 0.500  recall 1.000  F1 0.667  false alarm 0.750
- CPU + raw socket *count* (default thresholds): TP 0 / FP 41 / FN 150 / TN 159  precision 0.000  recall 0.000  F1 0.000  false alarm 0.205
- CPU + persistent page sockets (default thresholds): TP 150 / FP 0 / FN 0 / TN 200  precision 1.000  recall 1.000  F1 1.000  false alarm 0.000
- thresholds chosen on odd-numbered trials, scored on even-numbered ones (175 train / 175 test windows)
- tuned detector on held-out trials (CPU 0.2 cores, sockets >= 1): TP 75 / FP 0 / FN 0 / TN 100  precision 1.000  recall 1.000  F1 1.000  false alarm 0.000

## Cross-check with the static page scan

- static findings: {'miner': 2, 'clean': 5} over 7 scanned pages
