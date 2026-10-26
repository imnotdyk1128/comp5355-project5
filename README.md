# Project 5 — Characterising browser-based crypto mining

**English summary** (the operating instructions below are in Chinese).

Browser-based cryptojacking is measured, not guessed: a controlled lab, a real
browser, and four simultaneous probes.

**Design.** Coinhive shut down in 2019, so live mining pages are no longer a
sampleable population. The project therefore runs two complementary tracks: a
controlled lab with designed ground truth, and the same probes applied to real
collected pages. The lab serves three pages that differ in exactly one variable:

| page | what it does | why it exists |
|---|---|---|
| `clean` | identical article, DOM and timers | idle baseline |
| `busy` | the same SHA-256 work loop and the same worker count, **no pool connection** | matched-CPU control |
| `mining` | same loop **plus** a long-lived pool socket submitting shares | the condition under study |

The miner is a hand-written emulation (pure-JS SHA-256 proof of work in Web
Workers, JSON stratum-style `auth`/`job`/`share`/`ack`/`set_diff`, pool-side
difficulty retargeting). It follows Coinhive's three-layer shape: the page's
main thread holds the pool WebSocket, the workers only hash. It connects to a
local fake pool on `127.0.0.1` and to nothing else.

**Measurement.** Microsoft Edge driven by Playwright; process-tree CPU/RSS from
psutil; per-page JS time and heap from the Chrome DevTools Protocol `Performance`
domain; page-owned WebSocket frames from CDP `Network`; HTTP detail from HAR;
machine-wide counters and the socket table as context. 250 ms sampling, 30 s
windows, 2 trials per condition, 7 conditions.

**Findings.**
- Each worker pins 0.99-1.00 of a core; hashrate scales linearly (2.2-2.9 MH/s per thread).
- `mining` and `busy` are indistinguishable on CPU (within 1%) and on memory
  (+4% RSS); they differ only in the network signature.
- Mining sockets live for the whole visit (mean 34 s), carry ~148-byte messages
  every 1-2 s, and use 0.66-1.19 kbps uplink. Page loads are a short burst of
  kilobyte responses. Lifetime and message size discriminate; volume does not.
- Detector on designed ground truth: CPU alone gives precision 0.50 and a 0.75
  false-alarm rate (it flags the innocent control every time). Adding "the page
  owns a persistent WebSocket" gives precision 1.00, recall 1.00, held-out F1 1.00.
- Machine-wide throughput and raw socket counts are useless as features: browser
  telemetry dominates them (a mining trial showed *fewer* established sockets than
  an idle one). This is why the loader keeps the socket on the page's own network
  stack, where CDP can attribute it.
- Static and dynamic detection disagree by design: `busy` and `mining` ship the
  same loader, so a content scan labels both as miners while traffic shows only
  one is mining. Static answers "is mining code present", dynamic answers "is this
  machine being mined right now".

**Layout.** `config/` signatures and seeds - `lab/` pages, miner, fake pool -
`collect/` crawl + static scan + scanner fixtures - `measure/` the probe -
`analyze/` statistics, network characterisation, detector evaluation -
`results/` lab dataset, `results_live/` real-page dataset. Each results tree holds
its own `analysis/*/fig_*.tiff` (300 dpi) and markdown reports.

**Reproduce.**

```bash
python -m pip install -r requirements.txt
python run_all.py --profile standard      # ~9 min: measure + analyse + SUMMARY.md
python collect/scan_static.py --dir collect/samples --per-file   # scanner fixtures, offline
```

Coursework for COMP5355 (Cyber and Internet Security). No real mining pools,
wallets or third-party sites are involved; exported HAR files are scrubbed of
cookies and GeoIP values by `analyze/sanitize_har.py`.

---

## 中文操作说明（设计、安装、运行、局限）

浏览器挖矿（cryptojacking）特征研究：采集含挖矿脚本的网页 → 在真实浏览器里访问 → 同步记录
CPU / 内存 / 网络 → 对比"有挖矿"和"无挖矿"的差异 → 分析这些页面产生的网络连接。
对应作业里列的五个步骤，每一步都有可运行的脚本和产出文件。

作业要求里提到的四篇参考文献的方法被拆成了本项目的两条分析主线：
静态（内容 / 币种 / 代码特征，arXiv:1809.02152）＋ 动态（资源指纹与连接指纹，arXiv:1808.00811、
CCS'18 #3243858、arXiv:1901.00846）。

---

## 0. 一分钟看懂设计

难点在于：**Coinhive 2019 年 9 月就关了**，公网上现存的浏览器挖矿页面极少，
"抓一批在挖的页面"这件事本身不可复现。所以本项目用两条路互相对照：

| 路线 | 目的 | 脚本 |
|---|---|---|
| 受控实验台（known positive/negative） | 拿到干净的"挖矿 vs 不挖矿"对比数据 | `lab/` + `measure/` + `analyze/` |
| 真实网页采集 + 静态扫描 | 在公网上找挖矿脚本，验证检测规则在真实页面上的表现 | `collect/` |

实验台三种条件，是唯一能把"挖矿"从"页面很忙"里剥离出来的做法：

- `clean` — 同一篇文章、同一套 DOM 和定时器，不开 worker，不连矿池（空白对照）
- `busy` — **和矿工完全相同的 SHA-256 工作量循环和线程数，但不连矿池**（CPU 对照）
- `mining` — 相同的循环 ＋ 长连接上报 share（真实挖矿条件）

`busy` 与 `mining` 的 CPU 应当几乎相同，差异只在网络连接数与小报文上——这正是"特征刻画"要证明的东西：
**只看 CPU 会把合法的重计算页面误判成挖矿**。

实验台矿工是自写的，明确声明为模拟物而非真实恶意样本：纯 JS 单轮 SHA-256(32 B job blob ‖ 4 B nonce)、
按前导零比特判定 share ＋ Web Worker ＋ JSON stratum 风格报文（`auth`/`job`/`share`/`ack`/`set_diff`）
＋ 矿池按客户端上报算力做难度自适应。结构完全照 Coinhive 的三层：**主线程 loader 持有矿池 WebSocket
并负责收发，worker 只做哈希**（只换了算法：真实 Coinhive 用 WASM CryptoNight，算力低约三个数量级，
但"每线程占满一核 + 一条长连接小报文"的指纹一致）。把 socket 放在页面主线程不是偷懒——Chromium 的
**全部**网络流量都走同一个 network utility 进程，按进程归属连接无法区分"页面产生的"与"浏览器自己的
遥测"，只有走页面自己的网络栈才能被 CDP 精确归属。**全程只连本机 `127.0.0.1` 的模拟矿池，不接触任何真实矿池、
不注入任何第三方站点。**

---

## 1. 安装

```bash
cd "E:/Master assignment/semester1/cyber and Internet security/myproject"
python -m pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/
# 驱动本机已装的 Edge，不需要再下载 Chromium
python -c "from playwright.sync_api import sync_playwright; \
  p=sync_playwright().start(); p.chromium.launch(channel='msedge', headless=True).close(); p.stop()"
```

国内网络提示：清华镜像缺 `playwright` 的 wheel，用阿里云镜像；PyPI 官方源直连容易超时。
第二行是一次性自检，能启动 Edge 就说明环境可用。

要求：Windows/macOS/Linux 均可，Python ≥3.10，本机浏览器（Edge 或 Chrome）。
**不需要管理员权限**，不需要 Npcap/Wireshark——网络侧用三类无特权数据源：
浏览器进程的连接表（psutil）、页面 HAR（Playwright）、模拟矿池的服务端逐帧日志。

## 2. 一键跑完

```bash
python run_all.py                    # 标准：3 条件 × 线程 1/2/4 × 2 次，窗口 30 s，约 9 分钟
python run_all.py --profile quick    # 快速自检，约 2 分钟
python run_all.py --profile long     # 交报告用的正式数据：窗口 90 s × 5 次，线程含 8
python run_all.py --with-collect     # 顺便跑阶段 1 的抓取 + 静态扫描
python run_all.py --headed           # 用可见浏览器窗口跑（更接近"人开着浏览器挖矿"的真实场景）
```

结果全在 `results/`，看图最快：`results/analysis/*/fig_*.png`（`.tiff` 是 300 dpi，交作业用）。

## 3. 分步运行

### 阶段 1 — 收集含挖矿脚本的网页

```bash
python collect/crawl_pages.py --follow-external      # 抓 config/target_urls.txt 里的 URL，存 HTML+JS
python collect/scan_static.py                        # 静态扫描，输出 results/static/findings.csv
python collect/scan_static.py --dir lab/web          # 已知阳性自检：实验台页面必须被判成 miner
```

- `crawl_pages.py` 每个页面存成 `results/pages/<sha1>/document.html` ＋ `scripts/*.js` ＋ `manifest.csv`。
  离线主机（历史上的挖矿服务商大多已关停）会记录 `error` 而不是中断整轮抓取。
- `scan_static.py` 三层匹配：具名平台特征（Coinhive / Crypto-Loot / JSEcoin / Project Poi / DeepBit /
  CoinImp / Minero / WebXMR 等，见 `config/miner_signatures.json`）→ 通用行为特征
  （`stratum`、`hashrate`、`jobId`、`submitShare`、worker+blob+`createObjectURL`）→ 混淆度指标
  （行最长、熵、`eval`/`atob`/`fromCharCode` 次数、十六进制转义密度）。同时抽取 IOC：矿池地址（ws/wss）
  与钱包字符串（Monero/BTC/ETH 正则）。
- 想扩大样本，把 URL 列表换成这些来源即可（脚本对格式无要求，一行一个）：
  - URLhaus `csv_recent`，按 `crypto`/`mine` 标签筛
  - Common Crawl WARC，`grep` 挖矿关键字
  - Wayback：`https://web.archive.org/web/2018*/<域名>`，抓历史快照
  - 在虚拟机里用浏览器真实访问过的页面：另存为文件夹后用 `python collect/crawl_pages.py --ingest-dir <目录>`

### 特征库自测（离线样本，不联网）

`collect/samples/` 放了三份**手写重建**的样本（不是从恶意样本还原的代码），用来验证特征库本身：

```bash
python collect/scan_static.py --dir collect/samples --per-file --out results/static_samples
```

| 样本 | 期望 | 实测结果 |
|---|---|---|
| `sample_coinhive_style_loader.js` | 判成 Coinhive | `miner:Coinhive`，score 24 |
| `sample_obfuscated_packer.js` | 至少可疑 | `suspicious`，score 3 |
| `sample_analytics_hard_negative.js` | 不能误报 | `clean`，score 1 |

两个值得写进报告的负面结论：

1. **十六进制转义的字符串数组能绕过子串匹配**——packer 样本里 `stratum`/`submitShare`/`cryptonight`
   全部以 `\x73\x74\x72...` 形式存在，明文匹配不到，只能靠熵、转义密度、`eval`/`atob` 计数这些
   代码特征降级判成 suspicious。要做实需要加解码预处理。
2. **`WebAssembly.instantiate` + Worker + WebSocket 不是挖矿的充分证据**——普通图表/分析脚本同样
   三样齐全（早期版本把它误判成 `miner_candidate`，已把这两个 token 从 strong 降到 weak）。
   静态层因此只能给候选，最终判定必须靠动态测量。

### 阶段 2/3 — 在浏览器里访问并采集数据

```bash
python measure/measure.py --mode lab --conditions clean,busy,mining --threads 1,2,4 \
       --trials 3 --duration 60 --warmup 5 --sample-ms 250
python measure/measure.py --mode live --urls ../config/target_urls.txt --duration 25   # 同一套探针跑真实页面
```

探针同时采集四路数据：

| 数据 | 来源 | 输出 |
|---|---|---|
| 浏览器进程树 CPU / RSS（psutil，含所有渲染与 worker 进程） | 每 250 ms | `results/measure/timeseries/*.csv` |
| 页面级 JS 执行时间、JS 堆（CDP `Performance.getMetrics`，必须用 page 级 session） | 每 250 ms | 同上 |
| **页面自己的 WebSocket**：开闭、逐帧字节、存活时长（CDP `Network.webSocket*`） | 每 250 ms 汇总 | 同上 + `results/measure/netevents/*.csv` |
| 系统吞吐（`net_io_counters`）、浏览器全量 ESTABLISHED 连接表 | 每 250 ms / 每 4 tick | 同上 + `results/measure/sockets/*.csv` |
| 页面自报算力/share（ground truth） | 每 4 tick | 同上 |
| 每个 HTTP 请求（含大小、发起者） | HAR | `results/measure/har/*.har` |
| 矿池侧逐帧报文（方向、字节、类型、难度） | 模拟矿池日志 | `results/lab/pool_frames.csv` |
| 页面访问日志、连接开闭 | 模拟服务器 | `results/lab/http_access.csv`、`pool_events.csv` |

噪声说明：全量连接表里浏览器自身的遥测长连接（Edge 同步、Bing 一类 `*:443`）比页面流量多一个数量级，
拿"连接数"当判据会被淹没（实测 clean 约 15 条、mining 反而只有 8–11 条）；真正可判的是 CDP 看到的
**页面自己建立、整场访问不关的 WebSocket**（clean/busy = 0，mining = 1）。

`measure.py` 会自己拉起并关闭 `lab/lab_server.py`（HTTP 8080 ＋ 矿池 WS 8777）。
端口被占用时用 `--http-port/--pool-port` 换。
挖矿强度、难度、任务下发周期可调：`--start-difficulty 22 --share-interval 2 --job-interval 3`。

想单独观察实验台：`python lab/lab_server.py`，然后用浏览器打开 `http://127.0.0.1:8080/mining?threads=4`，
按 F12 → Performance 就能看到 CPU 被钉住、Network 里两条长连接。

### 阶段 4 — 对比分析

```bash
python analyze/analyze_resources.py     # 有/无挖矿的资源占用对比 + 显著性检验 + 图
python analyze/analyze_network.py       # 连接与报文特征 + 与页面 HTTP 流量的对比
python analyze/evaluate_detector.py     # 组合特征检测器：混淆矩阵、阈值扫描、留出验证
```

- `analyze_resources.py` → `results/analysis/resources/resource_table.md`：每种条件的均值/中位数/p95，
  以及相对 `clean` 的 Welch t 检验、Mann-Whitney U、Cohen's d 与倍数；另有"线程数 → 占用的核数"线性表和
  "mining vs busy（CPU 相同）差异"表。检验用逐采样点做（n 上百），试验级均值同时给出。
- `analyze_network.py` → `network_report.md`：每条挖矿连接的存活时长、报文数、上行字节、share 间隔、
  job 周期、难度轨迹；与同端口的普通页面 HTTP 流量并排比较（页面＝短暂大块突发，挖矿＝长连接 + 每两秒
  上百字节的稳定小报文）。
- `evaluate_detector.py` → `detector_report.md`：5 s 滑动窗口特征（CPU p95 核数、持续占比、页面自有
  WebSocket、全量连接数、上行平稳度）。给出三种检测器的混淆矩阵与精确率/召回率/F1/误报率：
  ① 只看 CPU；② 只看页面 WebSocket；③ CPU ∧ 持续 ∧ 页面 WebSocket。阈值在奇数试验上选、偶数试验上测
  （留出验证），另给阈值扫描曲线。核心结论：**只用 CPU 会把 busy 对照 100% 误判成挖矿；
  加上"页面自己开的长连接"这条判据后误报消失。**

### 两套数据集

同一套探针跑两类目标，结果分开存放，互不覆盖：

```bash
python run_all.py --profile standard                 # -> results/        受控实验
P5_RESULTS="$PWD/results_live" python measure/measure.py --mode live \
    --urls config/target_urls.txt --max-live 7 --duration 20 --warmup 5   # -> results_live/  真实网页
P5_RESULTS="$PWD/results_live" python analyze/analyze_resources.py         # 三个分析脚本同理
```

`results_live/` 是"在浏览器里访问采集到的网页"这一步的实证：example.com、wikipedia、httpbin、
python.org 五个真实站点的 CPU p95 只有 0.05–0.17 核、页面自有 WebSocket 为 0；
把实验台的挖矿页面当普通 URL 访问时，CPU p95 2.17 核 + 1 条持续 socket，两条判据同时命中。

**静态结论与动态结论不一致的地方要写进报告**：以静态扫描的判定作为 live 数据集的 ground truth 时，
`busy` 页面被静态判成挖矿（它和 `mining` 共用同一个 loader），但动态看不到任何矿池流量——
于是"只看 CPU"反而 F1=1.0、"CPU+socket"降到 0.667。这不是 bug，是两种定义之争：
**静态检测回答"这页面上有没有挖矿代码"，动态检测回答"此刻这台机器有没有被拿去挖矿"**。
以设计真值（busy = 合法重计算对照）为准的 `results/` 那套评估里，CPU 单独判定的误报率是 0.75，
加上页面自有 socket 后为 0。报告里应同时给出这两张表。

## 4. 在虚拟机里跑

作业写的是虚拟机，建议这样做（脚本无需改动）：

1. VM（VMware/VirtualBox，Windows，≥4 vCPU / 8 GB）里装 Python、Edge 或 Chrome，再按第 1 节装依赖。
2. 虚拟机用**宿主模式（NAT/bridged 都行）**，因为实验台和浏览器都在同一台机器内，不依赖外网。
3. 阶段 1 抓公网页面必须在能出网的虚拟机里跑（`--with-collect`）。
4. 报告里注明 VM 规格与 CPU 分配：容器/虚拟化的调度会让 CPU 数值偏低且抖动，同一台 VM 内部相对比较才有效。
5. 想在 VM 里抓包（可选，超出本项目必需）：装 Wireshark + Npcap 后，
   `results/lab/pool_frames.csv` 已经给出等价信息，不做也行。

## 5. 已知的测量局限（写报告时要诚实交代）

- **headless 与后台流量噪声**：系统级吞吐计数是全机器的，挖矿 socket 只有约 1.8 kbps，会被背景流量完全
  淹没，所以上行速率只作描述性统计、不进检测规则；判据用 CDP 的页面 WebSocket 事件与矿池侧逐帧日志。
  跑正式数据时请关闭网盘、更新、同步类程序，或用 `--headed` 在干净虚拟机里跑。
- **自算 SHA-256 的算力（每核约 2.2 MH/s）比 CryptoNight WASM（约 1–3 kH/s）高三个数量级**，
  因此 share 频率、报文尺寸与真实 Coinhive 不同；占核数量、连接生命周期、报文周期性这三项特征是可对齐的。
- **Coinhive 及其同类已下线**，公网阳性样本稀少，阶段 1 的检测结果以"零误报 + 已知阳性自检通过"为准，
  流行度结论需要外部数据集才能给出。
- Worker 的内存不计入页面 JS 堆（CDP 只报主框架），因此内存指标用进程树 RSS。
- 静态扫描无法区分 `busy` 与 `mining`（同一个 loader），这是设计与结论之一，不是缺陷。

## 6. 目录

```
myproject/
├── README.md                  本文件
├── requirements.txt
├── run_all.py                 一键流水线
├── config/
│   ├── miner_signatures.json  平台特征库、通用特征、钱包/矿池正则
│   └── target_urls.txt        种子 URL（含阴性对照与来源指引）
├── lab/
│   ├── lab_server.py          页面服务 + 模拟矿池 + 逐帧流量日志
│   └── web/
│       ├── pages/{clean,busy,mining}.html
│       └── js/{sha256,miner_loader,miner_worker,busy_worker,page_common}.js
│           —— loader 管 socket，worker 管哈希
├── collect/
│   ├── crawl_pages.py         阶段 1：网页与 JS 存档
│   ├── scan_static.py         阶段 1：静态挖矿检测 + IOC 抽取
│   └── samples/               三份手写样本，离线回归测试特征库（见"特征库自测"）
├── measure/
│   └── measure.py             阶段 2/3：浏览器驱动 + 四路探针采集
├── analyze/
│   ├── analyze_resources.py   阶段 4：资源对比与统计
│   ├── analyze_network.py     阶段 4：连接/报文分析
│   └── evaluate_detector.py   阶段 4：检测器评估
├── results/                   受控实验产出：pages / measure/{timeseries,har,sockets,netevents} /
│                              lab / static / analysis/{resources,network,detector} / SUMMARY.md
└── results_live/              同一套探针跑真实网页的产出（结构同上，由 P5_RESULTS 切换）
```

## 7. 常见问题

- `playwright` 装不上 → 换阿里云镜像（第 1 节），PyPI 官方源在国内易超时。
- `could not identify the browser process` → 用 `--browser-exec "C:/Program Files/Google/Chrome/Application/chrome.exe"`
  显式指定；或 `--channel chrome`。
- 端口被占 → `--http-port 18080 --pool-port 18777`，`measure.py` 会把新的矿池地址通过 URL 参数 `pool`
  传给页面，页面里的 loader 直接用该地址连，不用改代码。
- 想换 CPU 占用规模 → `--threads 1,2,4,8`，`--start-difficulty` 调大减少 share 频率。
- 数值不稳 → 增大 `--trials` 与 `--duration`，用 `--profile long`。
