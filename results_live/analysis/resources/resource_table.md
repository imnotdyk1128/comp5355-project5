# Resource profile: with vs without browser-based mining

- platform: Windows 11 AMD64, 20 logical cores, 15.7 GB RAM
- browser: 156.0.4314.42 (headless), sample interval 300 ms, window 20.0 s, 2 trials per condition
- captured: 2026-10-26T09:06:26.306+00:00

## live:example.com  (2 trials)

| metric | mean | median | sd | p95 | max | vs baseline (Welch p, Mann-Whitney p, Cohen d) |
|---|---|---|---|---|---|---|
| browser CPU (sum of cores) (%) | 0.86 | 0.86 | 0.44 | 1.30 | 1.30 | - |
| browser CPU (% of machine) (%) | 0.05 | 0.05 | 0.03 | 0.07 | 0.07 | - |
| browser RSS (MB) | 530.41 | 530.41 | 2.67 | 533.08 | 533.08 | - |
| page JS heap (MB) | 1.49 | 1.49 | 0.00 | 1.49 | 1.49 | - |
| main-thread JS time (% of core) | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | - |
| uplink throughput (kbps) | 90.01 | 90.01 | 40.12 | 130.14 | 130.14 | - |
| downlink throughput (kbps) | 89.44 | 89.44 | 13.03 | 102.47 | 102.47 | - |
| established TCP sockets (count) | 15.50 | 15.50 | 0.50 | 16.00 | 16.00 | - |
| page-owned WebSockets open (count) | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | - |
| pool bytes sent by the page (B/sample) | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | - |
| persistent sockets created by the page (count) | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | - |
| sockets created during the visit (count) | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | - |

## live:httpbin.org  (2 trials)

| metric | mean | median | sd | p95 | max | vs baseline (Welch p, Mann-Whitney p, Cohen d) |
|---|---|---|---|---|---|---|
| browser CPU (sum of cores) (%) | 0.39 | 0.39 | 0.21 | 0.60 | 0.60 |  |
| browser CPU (% of machine) (%) | 0.02 | 0.02 | 0.01 | 0.03 | 0.03 |  |
| browser RSS (MB) | 532.05 | 532.05 | 0.44 | 532.49 | 532.49 |  |
| page JS heap (MB) | 1.37 | 1.37 | 0.00 | 1.37 | 1.37 |  |
| main-thread JS time (% of core) | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |  |
| uplink throughput (kbps) | 43.25 | 43.25 | 28.26 | 71.51 | 71.51 |  |
| downlink throughput (kbps) | 43.17 | 43.17 | 10.85 | 54.02 | 54.02 |  |
| established TCP sockets (count) | 7.96 | 7.96 | 0.96 | 8.93 | 8.93 |  |
| page-owned WebSockets open (count) | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |  |
| pool bytes sent by the page (B/sample) | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |  |
| persistent sockets created by the page (count) | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |  |
| sockets created during the visit (count) | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |  |

## live:lab:8080  (6 trials)

| metric | mean | median | sd | p95 | max | vs baseline (Welch p, Mann-Whitney p, Cohen d) |
|---|---|---|---|---|---|---|
| browser CPU (sum of cores) (%) | 133.41 | 199.22 | 93.85 | 200.47 | 200.47 | - |
| browser CPU (% of machine) (%) | 6.67 | 9.96 | 4.69 | 10.02 | 10.02 | - |
| browser RSS (MB) | 543.81 | 545.99 | 6.98 | 551.88 | 551.88 | - |
| page JS heap (MB) | 1.74 | 1.77 | 0.05 | 1.77 | 1.77 | - |
| main-thread JS time (% of core) | 0.06 | 0.06 | 0.01 | 0.07 | 0.07 | - |
| uplink throughput (kbps) | 374.64 | 42.45 | 735.91 | 2017.87 | 2017.87 | - |
| downlink throughput (kbps) | 35.34 | 18.94 | 31.22 | 95.04 | 95.04 | - |
| established TCP sockets (count) | 4.17 | 4.00 | 1.07 | 6.00 | 6.00 | - |
| page-owned WebSockets open (count) | 0.33 | 0.00 | 0.47 | 1.00 | 1.00 | - |
| pool bytes sent by the page (B/sample) | 6.23 | 0.00 | 9.51 | 24.89 | 24.89 | - |
| persistent sockets created by the page (count) | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | - |
| sockets created during the visit (count) | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | - |
| hashrate (ground truth) (H/s) | 5233924.33 | 5268829.34 | 96935.45 | 5326907.70 | 5326907.70 | - |
| shares submitted (cumulative) (count) | 5.47 | 4.33 | 5.70 | 13.20 | 13.20 | - |
| pool bytes sent (cumulative) (B) | 871.30 | 706.16 | 902.05 | 2072.87 | 2072.87 | - |

## live:www.python.org  (2 trials)

| metric | mean | median | sd | p95 | max | vs baseline (Welch p, Mann-Whitney p, Cohen d) |
|---|---|---|---|---|---|---|
| browser CPU (sum of cores) (%) | 2.52 | 2.52 | 0.62 | 3.15 | 3.15 | - |
| browser CPU (% of machine) (%) | 0.13 | 0.13 | 0.03 | 0.16 | 0.16 | - |
| browser RSS (MB) | 585.34 | 585.34 | 12.59 | 597.93 | 597.93 | - |
| page JS heap (MB) | 3.46 | 3.46 | 0.04 | 3.50 | 3.50 | - |
| main-thread JS time (% of core) | 0.07 | 0.07 | 0.00 | 0.07 | 0.07 | - |
| uplink throughput (kbps) | 25.32 | 25.32 | 5.11 | 30.43 | 30.43 | - |
| downlink throughput (kbps) | 49.68 | 49.68 | 26.66 | 76.34 | 76.34 | - |
| established TCP sockets (count) | 9.50 | 9.50 | 1.10 | 10.60 | 10.60 | - |
| page-owned WebSockets open (count) | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | - |
| pool bytes sent by the page (B/sample) | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | - |
| persistent sockets created by the page (count) | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | - |
| sockets created during the visit (count) | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | - |

## live:www.wikipedia.org  (2 trials)

| metric | mean | median | sd | p95 | max | vs baseline (Welch p, Mann-Whitney p, Cohen d) |
|---|---|---|---|---|---|---|
| browser CPU (sum of cores) (%) | 0.78 | 0.78 | 0.52 | 1.29 | 1.29 | - |
| browser CPU (% of machine) (%) | 0.04 | 0.04 | 0.03 | 0.07 | 0.07 | - |
| browser RSS (MB) | 574.78 | 574.78 | 1.30 | 576.07 | 576.07 | - |
| page JS heap (MB) | 1.20 | 1.20 | 0.00 | 1.20 | 1.20 | - |
| main-thread JS time (% of core) | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | - |
| uplink throughput (kbps) | 85.50 | 85.50 | 64.83 | 150.33 | 150.33 | - |
| downlink throughput (kbps) | 100.21 | 100.21 | 40.07 | 140.27 | 140.27 | - |
| established TCP sockets (count) | 17.13 | 17.13 | 1.87 | 19.00 | 19.00 | - |
| page-owned WebSockets open (count) | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | - |
| pool bytes sent by the page (B/sample) | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | - |
| persistent sockets created by the page (count) | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | - |
| sockets created during the visit (count) | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | - |
