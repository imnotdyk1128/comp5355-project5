# Network characterisation of browser-based mining

## Emulated pool (server side)

- connections opened: 6 (6 open / 6 close events)
- mean connection lifetime: 33.75 s
- mean frames per connection: 62.5
- message mix: {'auth': 6, 'job': 75, 'share': 145, 'ack': 145, 'set_diff': 4}
- total bytes: 38394.0 (up 22415.0, down 15979.0) = 0.886 kbps mean uplink per connection

| conn | worker | lifetime s | frames | bytes up | mean frame up | up kbps | shares | share interval s | job interval s |
|---|---|---|---|---|---|---|---|---|---|
| 1 | tLabWalletLab0.mining1w1 | 32.65 | 61 | 3706.0 | 148.2 | 0.908 | 24 | 1.16 | 2.97 |
| 2 | tLabWalletLab0.mining1w2 | 34.7 | 64 | 3853.0 | 148.2 | 0.888 | 25 | 1.44 | 2.88 |
| 3 | tLabWalletLab0.mining2w1 | 34.95 | 59 | 3412.0 | 148.3 | 0.781 | 22 | 1.65 | 2.8 |
| 4 | tLabWalletLab0.mining2w2 | 32.33 | 48 | 2663.0 | 147.9 | 0.659 | 17 | 2.0 | 2.94 |
| 5 | tLabWalletLab0.mining4w1 | 34.8 | 65 | 3865.0 | 148.7 | 0.889 | 25 | 1.12 | 2.9 |
| 6 | tLabWalletLab0.mining4w2 | 33.09 | 78 | 4916.0 | 149.0 | 1.189 | 32 | 0.86 | 3.01 |

## Ordinary page traffic (same server, HTTP)

- requests: 138, unique paths: 11
- total bytes: 266476.0, mean response: 1931.0 B
- burst window: 472.7 s -> 0.29 req/s, mean gap between requests 3.45 s
- top paths: [('/js/sha256.js', 28), ('/css/site.css', 14), ('/js/page_common.js', 14), ('/img/banner1.svg', 14), ('/img/banner0.svg', 14), ('/js/busy_worker.js', 14), ('/js/miner_worker.js', 14), ('/js/miner_loader.js', 12)]

Reading: mining adds a *persistent* socket carrying ~100-byte messages every couple of seconds, while page loads are a *transient* burst of kilobyte responses. A flow-level detector sees both; the discriminator is flow lifetime and message size, not volume.

## Per trial (pool connections grouped by the URL worker tag)

| trial tag | sockets | window s | frames | bytes up | up kbps | mean frame up | shares | shares/s | mean socket lifetime s |
|---|---|---|---|---|---|---|---|---|---|
| mining1w1 | 1 | 32.6 | 61 | 3706.0 | 0.908 | 148.2 | 24 | 0.735 | 32.65 |
| mining1w2 | 1 | 34.7 | 64 | 3853.0 | 0.888 | 148.2 | 25 | 0.721 | 34.7 |
| mining2w1 | 1 | 35.0 | 59 | 3412.0 | 0.781 | 148.3 | 22 | 0.629 | 34.95 |
| mining2w2 | 1 | 32.3 | 48 | 2663.0 | 0.659 | 147.9 | 17 | 0.526 | 32.33 |
| mining4w1 | 1 | 34.8 | 65 | 3865.0 | 0.889 | 148.7 | 25 | 0.718 | 34.8 |
| mining4w2 | 1 | 33.1 | 78 | 4916.0 | 1.189 | 149.0 | 32 | 0.967 | 33.09 |

Reading: socket count tracks the worker/thread count exactly, lifetime spans the whole visit, and each socket carries ~100-byte messages at a fixed cadence. No ordinary page does this.

## Client side, per trial (HAR)

| trial | requests | bytes | mean resp KB | hosts | unfinished |
|---|---|---|---|---|---|
| busy_127_0_0_1_8080_busy_t1_r1 | 8 | 12195 | 1.5 | 127.0.0.1:8080 | 0 |
| busy_127_0_0_1_8080_busy_t1_r2 | 8 | 12195 | 1.5 | 127.0.0.1:8080 | 0 |
| busy_127_0_0_1_8080_busy_t2_r1 | 10 | 15883 | 1.6 | 127.0.0.1:8080 | 0 |
| busy_127_0_0_1_8080_busy_t2_r2 | 10 | 15883 | 1.6 | 127.0.0.1:8080 | 0 |
| busy_127_0_0_1_8080_busy_t4_r1 | 14 | 23259 | 1.6 | 127.0.0.1:8080 | 0 |
| busy_127_0_0_1_8080_busy_t4_r2 | 14 | 23259 | 1.6 | 127.0.0.1:8080 | 0 |
| busy_t1_r1 | 8 | 12195 | 1.5 | 127.0.0.1:8080 | 0 |
| busy_t1_r2 | 8 | 12195 | 1.5 | 127.0.0.1:8080 | 0 |
| busy_t2_r1 | 10 | 15883 | 1.6 | 127.0.0.1:8080 | 0 |
| busy_t2_r2 | 10 | 15883 | 1.6 | 127.0.0.1:8080 | 0 |
| busy_t4_r1 | 14 | 23259 | 1.6 | 127.0.0.1:8080 | 0 |
| busy_t4_r2 | 14 | 23259 | 1.6 | 127.0.0.1:8080 | 0 |
| clean_127_0_0_1_8080_clean_t0_r1 | 5 | 3448 | 0.7 | 127.0.0.1:8080 | 0 |
| clean_127_0_0_1_8080_clean_t0_r2 | 5 | 3448 | 0.7 | 127.0.0.1:8080 | 0 |
| clean_t0_r1 | 5 | 3448 | 0.7 | 127.0.0.1:8080 | 0 |
| clean_t0_r2 | 5 | 3448 | 0.7 | 127.0.0.1:8080 | 0 |
| mining_127_0_0_1_8080_mining_t1_r1 | 9 | 12199 | 1.3 | 127.0.0.1:8080, 127.0.0.1:8777 | 0 |
| mining_127_0_0_1_8080_mining_t1_r2 | 9 | 12199 | 1.3 | 127.0.0.1:8080, 127.0.0.1:8777 | 0 |
| mining_127_0_0_1_8080_mining_t2_r1 | 11 | 15887 | 1.4 | 127.0.0.1:8080, 127.0.0.1:8777 | 0 |
| mining_127_0_0_1_8080_mining_t2_r2 | 11 | 15887 | 1.4 | 127.0.0.1:8080, 127.0.0.1:8777 | 0 |
| mining_127_0_0_1_8080_mining_t4_r1 | 15 | 23263 | 1.5 | 127.0.0.1:8080, 127.0.0.1:8777 | 0 |
| mining_127_0_0_1_8080_mining_t4_r2 | 15 | 23263 | 1.5 | 127.0.0.1:8080, 127.0.0.1:8777 | 0 |
| mining_t1_r1 | 9 | 12199 | 1.3 | 127.0.0.1:8080, 127.0.0.1:8777 | 0 |
| mining_t1_r2 | 9 | 12199 | 1.3 | 127.0.0.1:8080, 127.0.0.1:8777 | 0 |
| mining_t2_r1 | 11 | 15887 | 1.4 | 127.0.0.1:8080, 127.0.0.1:8777 | 0 |
| mining_t2_r2 | 11 | 15887 | 1.4 | 127.0.0.1:8080, 127.0.0.1:8777 | 0 |
| mining_t4_r1 | 15 | 23263 | 1.5 | 127.0.0.1:8080, 127.0.0.1:8777 | 0 |
| mining_t4_r2 | 15 | 23263 | 1.5 | 127.0.0.1:8080, 127.0.0.1:8777 | 0 |

## Page-owned WebSockets (CDP, client side)

| condition | threads | trial | url | lifetime s | frames up | frames down | bytes up | mean frame B | mean gap s |
|---|---|---|---|---|---|---|---|---|---|
| mining | 1 | 1 | ws://127.0.0.1:8777/stratum | 32.8 | 25 | 36 | 3806.0 | 152.2 | 1.1 |
| mining | 1 | 2 | ws://127.0.0.1:8777/stratum | 34.8 | 26 | 38 | 3957.0 | 152.2 | 1.19 |
| mining | 2 | 1 | ws://127.0.0.1:8777/stratum | 33.8 | 21 | 34 | 3198.0 | 152.3 | 1.25 |
| mining | 2 | 2 | ws://127.0.0.1:8777/stratum | 32.5 | 18 | 30 | 2735.0 | 151.9 | 1.62 |
| mining | 4 | 1 | ws://127.0.0.1:8777/stratum | 33.8 | 26 | 38 | 3969.0 | 152.7 | 1.15 |
| mining | 4 | 2 | ws://127.0.0.1:8777/stratum | 33.3 | 33 | 45 | 5048.0 | 153.0 | 0.73 |
| mining | 1 | 1 | ws://127.0.0.1:8777/stratum | 33.0 | 21 | 33 | 3192.0 | 152.0 | 1.37 |
| mining | 1 | 2 | ws://127.0.0.1:8777/stratum | 33.5 | 15 | 28 | 2286.0 | 152.4 | 1.66 |
| mining | 2 | 1 | ws://127.0.0.1:8777/stratum | 34.0 | 30 | 44 | 4569.0 | 152.3 | 0.9 |
| mining | 2 | 2 | ws://127.0.0.1:8777/stratum | 34.3 | 19 | 32 | 2898.0 | 152.5 | 1.35 |
| mining | 4 | 1 | ws://127.0.0.1:8777/stratum | 32.0 | 44 | 61 | 6647.0 | 151.1 | 0.48 |
| mining | 4 | 2 | ws://127.0.0.1:8777/stratum | 33.5 | 24 | 36 | 3690.0 | 153.8 | 1.24 |

These are visible to any browser-resident monitor without knowing the pool: the page itself opened the socket and kept it alive for the whole visit.

## Client-side sockets: peers kept open for >= 5 s

| peer | trials seeing it | conditions | mean lifetime s | mean samples |
|---|---|---|---|---|
| 127.0.0.1:8080 | 28 | busy, clean, mining | 29.0 | 85.7 |
| 127.0.0.1:7892 | 14 | busy, clean, mining | 29.0 | 136.4 |
| 40.99.33.146:443 | 14 | busy, clean, mining | 29.0 | 30.0 |
| 40.104.21.82:443 | 14 | busy, clean, mining | 29.0 | 30.0 |
| 202.89.233.100:443 | 13 | busy, clean, mining | 29.0 | 36.0 |
| 127.0.0.1:8777 | 12 | mining | 29.0 | 30.0 |
| 150.171.28.11:443 | 5 | busy, clean | 29.0 | 71.6 |
| 150.171.27.11:443 | 4 | busy, clean | 26.0 | 52.8 |
| 13.107.6.158:443 | 4 | busy, clean | 26.0 | 27.0 |
| 150.171.110.101:443 | 3 | busy, clean | 22.3 | 23.3 |
| 40.104.20.2:443 | 3 | busy, clean | 29.0 | 60.0 |
| 202.89.233.101:443 | 2 | clean, mining | 29.0 | 30.0 |

A loopback peer on the pool port that persists for the whole visit is the mining signature; ordinary page peers disappear within a second or two.

## Socket table sampled inside the browser

| group | estab TCP mean | estab TCP p95 | uplink kbps | browser CPU % | har entries |
|---|---|---|---|---|---|
| clean | 14.2 | 15.0 | 2294.8 | 0.5 | 5 |
| clean | 15.7 | 17.0 | 196.1 | 0.9 | 5 |
| busy-w1 | 18.0 | 18.0 | 104.5 | 99.7 | 8 |
| busy-w1 | 11.7 | 14.0 | 9.7 | 100.2 | 8 |
| busy-w2 | 7.2 | 9.0 | 2.6 | 199.2 | 10 |
| busy-w2 | 4.1 | 5.0 | 53.3 | 198.4 | 10 |
| busy-w4 | 4.0 | 4.0 | 36.5 | 398.2 | 14 |
| busy-w4 | 4.0 | 4.0 | 1241.2 | 398.5 | 14 |
| mining-w1 | 5.0 | 5.0 | 8.6 | 100.0 | 9 |
| mining-w1 | 5.0 | 5.0 | 26.1 | 99.7 | 9 |
| mining-w2 | 5.0 | 5.0 | 25.7 | 199.4 | 11 |
| mining-w2 | 5.0 | 5.0 | 33.1 | 200.9 | 11 |
| mining-w4 | 5.0 | 5.0 | 82.8 | 397.3 | 15 |
| mining-w4 | 5.0 | 5.0 | 47.3 | 398.4 | 15 |