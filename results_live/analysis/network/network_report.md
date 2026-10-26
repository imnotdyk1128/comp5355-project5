# Network characterisation of browser-based mining

## Emulated pool (server side)

- connections opened: 2 (2 open / 2 close events)
- mean connection lifetime: 23.59 s
- mean frames per connection: 38.5
- message mix: {'auth': 2, 'job': 19, 'share': 27, 'ack': 27, 'set_diff': 2}
- total bytes: 7960.0 (up 4292.0, down 3668.0) = 0.718 kbps mean uplink per connection

| conn | worker | lifetime s | frames | bytes up | mean frame up | up kbps | shares | share interval s | job interval s |
|---|---|---|---|---|---|---|---|---|---|
| 1 | LabWalletLab0.labvisitor | 24.8 | 48 | 2811.0 | 147.9 | 0.907 | 18 | 1.19 | 2.76 |
| 2 | LabWalletLab0.labvisitor | 22.39 | 29 | 1481.0 | 148.1 | 0.529 | 9 | 1.36 | 2.8 |

## Ordinary page traffic (same server, HTTP)

- requests: 50, unique paths: 11
- total bytes: 85924.0, mean response: 1718.5 B
- burst window: 129.61 s -> 0.39 req/s, mean gap between requests 2.645 s
- top paths: [('/js/sha256.js', 8), ('/css/site.css', 6), ('/js/page_common.js', 6), ('/img/banner1.svg', 6), ('/img/banner0.svg', 6), ('/js/miner_loader.js', 4), ('/js/miner_worker.js', 4), ('/js/busy_worker.js', 4)]

Reading: mining adds a *persistent* socket carrying ~100-byte messages every couple of seconds, while page loads are a *transient* burst of kilobyte responses. A flow-level detector sees both; the discriminator is flow lifetime and message size, not volume.

## Per trial (pool connections grouped by the URL worker tag)

| trial tag | sockets | window s | frames | bytes up | up kbps | mean frame up | shares | shares/s | mean socket lifetime s |
|---|---|---|---|---|---|---|---|---|---|
| labvisitor | 2 | 48.9 | 77 | 4292.0 | 0.703 | 148.0 | 27 | 0.552 | 23.59 |

Reading: socket count tracks the worker/thread count exactly, lifetime spans the whole visit, and each socket carries ~100-byte messages at a fixed cadence. No ordinary page does this.

## Client side, per trial (HAR)

| trial | requests | bytes | mean resp KB | hosts | unfinished |
|---|---|---|---|---|---|
| live_127_0_0_1_8080_busy_t0_r1 | 10 | 15883 | 1.6 | 127.0.0.1:8080 | 0 |
| live_127_0_0_1_8080_busy_t0_r2 | 10 | 15883 | 1.6 | 127.0.0.1:8080 | 0 |
| live_127_0_0_1_8080_clean_t0_r1 | 5 | 3448 | 0.7 | 127.0.0.1:8080 | 0 |
| live_127_0_0_1_8080_clean_t0_r2 | 5 | 3448 | 0.7 | 127.0.0.1:8080 | 0 |
| live_127_0_0_1_8080_mining_t0_r1 | 11 | 15887 | 1.4 | 127.0.0.1:8080, 127.0.0.1:8777 | 0 |
| live_127_0_0_1_8080_mining_t0_r2 | 11 | 15887 | 1.4 | 127.0.0.1:8080, 127.0.0.1:8777 | 0 |
| live_example_com_t0_r1 | 2 | 2021 | 1.0 | example.com | 0 |
| live_example_com_t0_r2 | 2 | 2021 | 1.0 | example.com | 0 |
| live_httpbin_org_html_t0_r1 | 1 | 3890 | 3.8 | httpbin.org | 0 |
| live_httpbin_org_html_t0_r2 | 1 | 3890 | 3.8 | httpbin.org | 0 |
| live_www_python_org_t0_r1 | 29 | 479037 | 16.1 | www.python.org, ajax.googleapis.com, analytics.python.org | 0 |
| live_www_python_org_t0_r2 | 29 | 478481 | 16.1 | www.python.org, ajax.googleapis.com, analytics.python.org | 0 |
| live_www_wikipedia_org_t0_r1 | 8 | 82048 | 10.0 | www.wikipedia.org | 0 |
| live_www_wikipedia_org_t0_r2 | 8 | 82047 | 10.0 | www.wikipedia.org | 0 |

## Page-owned WebSockets (CDP, client side)

| condition | threads | trial | url | lifetime s | frames up | frames down | bytes up | mean frame B | mean gap s |
|---|---|---|---|---|---|---|---|---|---|
| live | 0 | 1 | ws://127.0.0.1:8777/stratum | 24.8 | 19 | 29 | 2887.0 | 151.9 | 0.92 |
| live | 0 | 2 | ws://127.0.0.1:8777/stratum | 22.4 | 10 | 19 | 1521.0 | 152.1 | 0.93 |

These are visible to any browser-resident monitor without knowing the pool: the page itself opened the socket and kept it alive for the whole visit.

## Client-side sockets: peers kept open for >= 5 s

| peer | trials seeing it | conditions | mean lifetime s | mean samples |
|---|---|---|---|---|
| 127.0.0.1:7892 | 14 | live | 19.2 | 131.0 |
| 127.0.0.1:8080 | 6 | live | 19.2 | 45.3 |
| 127.0.0.1:8777 | 2 | live | 19.2 | 17.0 |

A loopback peer on the pool port that persists for the whole visit is the mining signature; ordinary page peers disappear within a second or two.

## Socket table sampled inside the browser

| group | estab TCP mean | estab TCP p95 | uplink kbps | browser CPU % | har entries |
|---|---|---|---|---|---|
| live-w0 | 15.0 | 15.0 | 49.9 | 1.3 | 2 |
| live-w0 | 16.0 | 16.0 | 130.1 | 0.4 | 2 |
| live-w0 | 19.0 | 19.0 | 150.3 | 1.3 | 8 |
| live-w0 | 15.3 | 19.0 | 20.7 | 0.3 | 8 |
| live-w0 | 8.9 | 11.0 | 15.0 | 0.6 | 1 |
| live-w0 | 7.0 | 7.0 | 71.5 | 0.2 | 1 |
| live-w0 | 10.6 | 11.0 | 30.4 | 3.1 | 29 |
| live-w0 | 8.4 | 9.0 | 20.2 | 1.9 | 29 |
| live-w0 | 6.0 | 6.0 | 7.1 | 200.5 | 11 |
| live-w0 | 5.0 | 5.0 | 17.4 | 199.8 | 11 |
| live-w0 | 4.0 | 4.0 | 2017.9 | 198.7 | 10 |
| live-w0 | 4.0 | 4.0 | 120.6 | 200.2 | 10 |
| live-w0 | 3.0 | 3.0 | 67.0 | 0.5 | 5 |
| live-w0 | 3.0 | 3.0 | 17.9 | 0.9 | 5 |