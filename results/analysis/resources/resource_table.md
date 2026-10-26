# Resource profile: with vs without browser-based mining

- platform: Windows 11 AMD64, 20 logical cores, 15.7 GB RAM
- browser: 156.0.4314.42 (headless), sample interval 250 ms, window 30.0 s, 2 trials per condition
- captured: 2026-10-26T08:57:39.902+00:00

## clean  (2 trials)

| metric | mean | median | sd | p95 | max | vs baseline (Welch p, Mann-Whitney p, Cohen d) |
|---|---|---|---|---|---|---|
| browser CPU (sum of cores) (%) | 0.70 | 0.70 | 0.17 | 0.87 | 0.87 |  |
| browser CPU (% of machine) (%) | 0.04 | 0.04 | 0.01 | 0.04 | 0.04 |  |
| browser RSS (MB) | 523.31 | 523.31 | 4.48 | 527.79 | 527.79 |  |
| page JS heap (MB) | 1.69 | 1.69 | 0.01 | 1.69 | 1.69 |  |
| main-thread JS time (% of core) | 0.04 | 0.04 | 0.01 | 0.04 | 0.04 |  |
| uplink throughput (kbps) | 1245.44 | 1245.44 | 1049.35 | 2294.79 | 2294.79 |  |
| downlink throughput (kbps) | 43050.63 | 43050.63 | 37942.69 | 80993.32 | 80993.32 |  |
| established TCP sockets (count) | 14.96 | 14.96 | 0.78 | 15.74 | 15.74 |  |
| page-owned WebSockets open (count) | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |  |
| pool bytes sent by the page (B/sample) | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |  |
| persistent sockets created by the page (count) | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |  |
| sockets created during the visit (count) | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |  |

## busy-w1  (2 trials)

| metric | mean | median | sd | p95 | max | vs baseline (Welch p, Mann-Whitney p, Cohen d) |
|---|---|---|---|---|---|---|
| browser CPU (sum of cores) (%) | 99.94 | 99.94 | 0.23 | 100.17 | 100.17 | p=0/2.41e-91*, d=1.99, x91.81 (n=240/240) |
| browser CPU (% of machine) (%) | 5.00 | 5.00 | 0.01 | 5.01 | 5.01 | p=0/1.06e-91*, d=1.99, x91.88 (n=240/240) |
| browser RSS (MB) | 525.30 | 525.30 | 0.04 | 525.33 | 525.33 | p=0.0216/0.396*, d=-0.21, x0.99 (n=240/240) |
| page JS heap (MB) | 1.80 | 1.80 | 0.00 | 1.80 | 1.80 | p=0.000119/3.36e-06*, d=0.35, x1.05 (n=240/240) |
| main-thread JS time (% of core) | 0.05 | 0.05 | 0.00 | 0.05 | 0.05 | p=0.000455/0.293*, d=-0.32, x0.68 (n=240/240) |
| uplink throughput (kbps) | 57.08 | 57.08 | 47.41 | 104.48 | 104.48 | p=0.00472/0.0145*, d=-0.26, x0.35 (n=240/240) |
| downlink throughput (kbps) | 39.47 | 39.47 | 30.01 | 69.48 | 69.48 | p=0.861/0.0709, d=-0.02, x0.93 (n=240/240) |
| established TCP sockets (count) | 14.87 | 14.87 | 3.13 | 18.00 | 18.00 | p=0.00661/0.35*, d=-0.50, x0.91 (n=60/60) |
| page-owned WebSockets open (count) | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | - |
| pool bytes sent by the page (B/sample) | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | - |
| persistent sockets created by the page (count) | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | - |
| sockets created during the visit (count) | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | - |
| hashrate (ground truth) (H/s) | 2767151.23 | 2767151.23 | 28703.98 | 2795855.20 | 2795855.20 | - |
| shares submitted (cumulative) (count) | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | - |
| pool bytes sent (cumulative) (B) | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | - |

## busy-w2  (2 trials)

| metric | mean | median | sd | p95 | max | vs baseline (Welch p, Mann-Whitney p, Cohen d) |
|---|---|---|---|---|---|---|
| browser CPU (sum of cores) (%) | 198.85 | 198.85 | 0.40 | 199.25 | 199.25 | p=0/1.43e-89*, d=2.00, x182.98 (n=240/240) |
| browser CPU (% of machine) (%) | 9.94 | 9.94 | 0.02 | 9.96 | 9.96 | p=0/1.43e-89*, d=2.00, x183.11 (n=240/240) |
| browser RSS (MB) | 529.10 | 529.10 | 0.48 | 529.58 | 529.58 | p=0.00443/4.42e-11*, d=0.26, x1.01 (n=240/240) |
| page JS heap (MB) | 1.79 | 1.79 | 0.01 | 1.80 | 1.80 | p=5.03e-05/4.56e-06*, d=0.37, x1.06 (n=240/240) |
| main-thread JS time (% of core) | 0.06 | 0.06 | 0.00 | 0.06 | 0.06 | p=0.00756/0.174*, d=-0.24, x0.74 (n=240/240) |
| uplink throughput (kbps) | 27.95 | 27.95 | 25.34 | 53.30 | 53.30 | p=0.000653/2.68e-12*, d=-0.31, x0.23 (n=240/240) |
| downlink throughput (kbps) | 20.73 | 20.73 | 12.67 | 33.40 | 33.40 | p=0.11/1.34e-11*, d=-0.15, x0.62 (n=240/240) |
| established TCP sockets (count) | 5.61 | 5.61 | 1.54 | 7.15 | 7.15 | p=1.37e-109/1.54e-22*, d=-1.99, x0.45 (n=60/60) |
| page-owned WebSockets open (count) | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | - |
| pool bytes sent by the page (B/sample) | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | - |
| persistent sockets created by the page (count) | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | - |
| sockets created during the visit (count) | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | - |
| hashrate (ground truth) (H/s) | 5259368.29 | 5259368.29 | 12236.57 | 5271604.86 | 5271604.86 | - |
| shares submitted (cumulative) (count) | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | - |
| pool bytes sent (cumulative) (B) | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | - |

## busy-w4  (2 trials)

| metric | mean | median | sd | p95 | max | vs baseline (Welch p, Mann-Whitney p, Cohen d) |
|---|---|---|---|---|---|---|
| browser CPU (sum of cores) (%) | 398.36 | 398.36 | 0.15 | 398.50 | 398.50 | p=1.26e-249/1.34e-88*, d=1.98, x359.12 (n=240/240) |
| browser CPU (% of machine) (%) | 19.92 | 19.92 | 0.01 | 19.93 | 19.93 | p=1.2e-249/1.34e-88*, d=1.98, x359.39 (n=240/240) |
| browser RSS (MB) | 546.65 | 546.65 | 0.33 | 546.99 | 546.99 | p=9.33e-28/2.18e-31*, d=0.96, x1.03 (n=240/240) |
| page JS heap (MB) | 1.80 | 1.80 | 0.01 | 1.81 | 1.81 | p=1.89e-06/1.63e-06*, d=0.43, x1.07 (n=240/240) |
| main-thread JS time (% of core) | 0.08 | 0.08 | 0.00 | 0.08 | 0.08 | p=0.281/0.0646, d=-0.10, x0.89 (n=240/240) |
| uplink throughput (kbps) | 638.86 | 638.86 | 602.32 | 1241.18 | 1241.18 | p=0.939/7.12e-08*, d=-0.01, x0.96 (n=240/240) |
| downlink throughput (kbps) | 70.90 | 70.90 | 9.04 | 79.93 | 79.93 | p=0.827/2.76e-05*, d=-0.02, x0.92 (n=240/240) |
| established TCP sockets (count) | 4.00 | 4.00 | 0.00 | 4.00 | 4.00 | p=5.83e-75/7.2e-25*, d=-1.99, x0.41 (n=60/60) |
| page-owned WebSockets open (count) | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | - |
| pool bytes sent by the page (B/sample) | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | - |
| persistent sockets created by the page (count) | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | - |
| sockets created during the visit (count) | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | - |
| hashrate (ground truth) (H/s) | 8992058.21 | 8992058.21 | 193635.30 | 9185693.51 | 9185693.51 | - |
| shares submitted (cumulative) (count) | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | - |
| pool bytes sent (cumulative) (B) | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | - |

## mining-w1  (2 trials)

| metric | mean | median | sd | p95 | max | vs baseline (Welch p, Mann-Whitney p, Cohen d) |
|---|---|---|---|---|---|---|
| browser CPU (sum of cores) (%) | 99.88 | 99.88 | 0.17 | 100.05 | 100.05 | p=0/6.13e-94*, d=1.99, x91.05 (n=240/240) |
| browser CPU (% of machine) (%) | 5.00 | 5.00 | 0.00 | 5.00 | 5.00 | p=0/6.13e-94*, d=1.99, x91.12 (n=240/240) |
| browser RSS (MB) | 528.56 | 528.56 | 1.10 | 529.66 | 529.66 | p=0.000768/3.4e-06*, d=0.31, x1.01 (n=240/240) |
| page JS heap (MB) | 1.82 | 1.82 | 0.00 | 1.82 | 1.82 | p=3.48e-06/2.12e-06*, d=0.42, x1.07 (n=240/240) |
| main-thread JS time (% of core) | 0.07 | 0.07 | 0.01 | 0.07 | 0.07 | p=0.0217/0.115*, d=-0.21, x0.78 (n=240/240) |
| uplink throughput (kbps) | 17.37 | 17.37 | 8.74 | 26.11 | 26.11 | p=0.425/3.7e-08*, d=0.07, x1.49 (n=240/240) |
| downlink throughput (kbps) | 24.20 | 24.20 | 12.98 | 37.19 | 37.19 | p=0.899/2.51e-06*, d=-0.01, x0.95 (n=240/240) |
| established TCP sockets (count) | 5.00 | 5.00 | 0.00 | 5.00 | 5.00 | p=8.47e-72/7.2e-25*, d=-1.99, x0.48 (n=60/60) |
| page-owned WebSockets open (count) | 1.00 | 1.00 | 0.00 | 1.00 | 1.00 | p=0/3.56e-106*, d=2.00, xinf (n=240/240) |
| pool bytes sent by the page (B/sample) | 27.54 | 27.54 | 0.66 | 28.20 | 28.20 | p=0.000263/2.94e-07*, d=0.33, xinf (n=240/240) |
| persistent sockets created by the page (count) | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | - |
| sockets created during the visit (count) | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | - |
| hashrate (ground truth) (H/s) | 2851114.17 | 2851114.17 | 5773.65 | 2856887.81 | 2856887.81 | - |
| shares submitted (cumulative) (count) | 13.70 | 13.70 | 1.26 | 14.96 | 14.96 | - |
| pool bytes sent (cumulative) (B) | 2144.43 | 2144.43 | 186.98 | 2331.41 | 2331.41 | - |

## mining-w2  (2 trials)

| metric | mean | median | sd | p95 | max | vs baseline (Welch p, Mann-Whitney p, Cohen d) |
|---|---|---|---|---|---|---|
| browser CPU (sum of cores) (%) | 200.16 | 200.16 | 0.75 | 200.92 | 200.92 | p=0/9.46e-95*, d=1.99, x180.38 (n=240/240) |
| browser CPU (% of machine) (%) | 10.01 | 10.01 | 0.04 | 10.05 | 10.05 | p=0/9.46e-95*, d=1.99, x180.52 (n=240/240) |
| browser RSS (MB) | 537.33 | 537.33 | 0.25 | 537.58 | 537.58 | p=8.34e-14/3.01e-25*, d=0.67, x1.02 (n=240/240) |
| page JS heap (MB) | 1.81 | 1.81 | 0.01 | 1.81 | 1.81 | p=2.76e-06/2.04e-06*, d=0.42, x1.07 (n=240/240) |
| main-thread JS time (% of core) | 0.07 | 0.07 | 0.00 | 0.07 | 0.07 | p=0.052/0.0962, d=-0.18, x0.81 (n=240/240) |
| uplink throughput (kbps) | 29.42 | 29.42 | 3.69 | 33.11 | 33.11 | p=0.000109/2.84e-07*, d=-0.35, x0.14 (n=240/240) |
| downlink throughput (kbps) | 25.18 | 25.18 | 0.97 | 26.15 | 26.15 | p=0.00268/7.77e-05*, d=-0.27, x0.40 (n=240/240) |
| established TCP sockets (count) | 5.00 | 5.00 | 0.00 | 5.00 | 5.00 | p=8.47e-72/7.2e-25*, d=-1.99, x0.48 (n=60/60) |
| page-owned WebSockets open (count) | 1.00 | 1.00 | 0.00 | 1.00 | 1.00 | p=0/3.56e-106*, d=2.00, xinf (n=240/240) |
| pool bytes sent by the page (B/sample) | 19.12 | 19.12 | 3.56 | 22.67 | 22.67 | p=0.000154/2.88e-06*, d=0.35, xinf (n=240/240) |
| persistent sockets created by the page (count) | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | - |
| sockets created during the visit (count) | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | - |
| hashrate (ground truth) (H/s) | 5291041.91 | 5291041.91 | 44906.58 | 5335948.49 | 5335948.49 | - |
| shares submitted (cumulative) (count) | 12.04 | 12.04 | 0.33 | 12.37 | 12.37 | - |
| pool bytes sent (cumulative) (B) | 1900.04 | 1900.04 | 47.60 | 1947.63 | 1947.63 | - |

## mining-w4  (2 trials)

| metric | mean | median | sd | p95 | max | vs baseline (Welch p, Mann-Whitney p, Cohen d) |
|---|---|---|---|---|---|---|
| browser CPU (sum of cores) (%) | 397.84 | 397.84 | 0.54 | 398.38 | 398.38 | p=2.41e-251/1.42e-88*, d=1.98, x359.23 (n=240/240) |
| browser CPU (% of machine) (%) | 19.89 | 19.89 | 0.03 | 19.92 | 19.92 | p=2.42e-251/1.41e-88*, d=1.98, x359.50 (n=240/240) |
| browser RSS (MB) | 548.80 | 548.80 | 1.50 | 550.31 | 550.31 | p=2.77e-45/4.12e-42*, d=1.20, x1.04 (n=240/240) |
| page JS heap (MB) | 1.82 | 1.82 | 0.00 | 1.82 | 1.82 | p=3.97e-08/1.36e-06*, d=0.49, x1.08 (n=240/240) |
| main-thread JS time (% of core) | 0.08 | 0.08 | 0.00 | 0.09 | 0.09 | p=0.403/0.00158*, d=0.08, x1.09 (n=240/240) |
| uplink throughput (kbps) | 65.09 | 65.09 | 17.75 | 82.85 | 82.85 | p=0.605/1.37e-20*, d=-0.05, x0.75 (n=240/240) |
| downlink throughput (kbps) | 27.80 | 27.80 | 11.03 | 38.82 | 38.82 | p=0.000379/2.52e-14*, d=-0.32, x0.31 (n=240/240) |
| established TCP sockets (count) | 5.00 | 5.00 | 0.00 | 5.00 | 5.00 | p=8.47e-72/7.2e-25*, d=-1.99, x0.48 (n=60/60) |
| page-owned WebSockets open (count) | 1.00 | 1.00 | 0.00 | 1.00 | 1.00 | p=0/3.56e-106*, d=2.00, xinf (n=240/240) |
| pool bytes sent by the page (B/sample) | 29.00 | 29.00 | 0.68 | 29.68 | 29.68 | p=1.04e-06/2.93e-08*, d=0.45, xinf (n=240/240) |
| persistent sockets created by the page (count) | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | - |
| sockets created during the visit (count) | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | - |
| hashrate (ground truth) (H/s) | 9174375.09 | 9174375.09 | 291755.30 | 9466130.38 | 9466130.38 | - |
| shares submitted (cumulative) (count) | 17.96 | 17.96 | 4.07 | 22.04 | 22.04 | - |
| pool bytes sent (cumulative) (B) | 2783.37 | 2783.37 | 602.07 | 3385.44 | 3385.44 | - |

## Scaling with worker count

| condition | threads | cores held busy | cores per thread | H/s per thread |
|---|---|---|---|---|
| busy-w1 | 1 | 1.00 | 1.00 | 2.74e+06 |
| busy-w1 | 1 | 1.00 | 1.00 | 2.8e+06 |
| busy-w2 | 2 | 1.99 | 1.00 | 2.64e+06 |
| busy-w2 | 2 | 1.98 | 0.99 | 2.62e+06 |
| busy-w4 | 4 | 3.98 | 1.00 | 2.3e+06 |
| busy-w4 | 4 | 3.98 | 1.00 | 2.2e+06 |
| mining-w1 | 1 | 1.00 | 1.00 | 2.85e+06 |
| mining-w1 | 1 | 1.00 | 1.00 | 2.86e+06 |
| mining-w2 | 2 | 1.99 | 1.00 | 2.62e+06 |
| mining-w2 | 2 | 2.01 | 1.00 | 2.67e+06 |
| mining-w4 | 4 | 3.97 | 0.99 | 2.22e+06 |
| mining-w4 | 4 | 3.98 | 1.00 | 2.37e+06 |

## Mining vs matched-CPU control (same workers, no pool)

| threads | CPU% mining | CPU% busy | page WebSockets (mining vs busy) | machine uplink kbps delta (noise) | shares/s |
|---|---|---|---|---|---|
| 1 | 99.9 | 99.9 | +1.0 | -39.70 | 0.78 |
| 2 | 200.2 | 198.8 | +1.0 | +1.47 | 0.62 |
| 4 | 397.8 | 398.4 | +1.0 | -573.76 | 0.95 |
