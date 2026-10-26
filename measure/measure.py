"""Measurement harness for Project 5.

Drives a real browser (Microsoft Edge through Playwright) to a page while
sampling, at a fixed interval:

  * CPU and RSS of the whole browser process tree (psutil)
  * per-page JS execution time and JS heap (Chrome DevTools Protocol)
  * machine-wide network throughput, plus the browser's socket table on a
    slower tick
  * every HTTP request/response (Playwright HAR export)

Two modes:
  --mode lab    controlled comparison against the local lab server, sweeping
                condition x threads x trial repeats
  --mode live   the same probes applied to arbitrary URLs (e.g. the pages
                collected by collect/crawl_pages.py)

Examples:
  python measure.py --mode lab --conditions clean,busy,mining --threads 1,2,4 --duration 30 --trials 2
  python measure.py --mode live --urls ../config/target_urls.txt --duration 25
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import platform
import socket
import statistics
import re
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import psutil
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(HERE.parent / "analyze"))
try:
    import sanitize_har
except ImportError:  # the scrub step is optional, not a dependency
    sanitize_har = None

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
RESULTS = Path(os.environ.get("P5_RESULTS", PROJECT / "results")) / "measure"

TIME_COLUMNS = [
    "t_s", "cond", "threads", "trial",
    "tree_cpu_pct", "tree_cpu_machine_pct", "tree_rss_mb", "n_tree_procs",
    "js_heap_mb", "js_heap_total_mb", "script_pct_core", "task_pct_core",
    "page_dom_nodes", "worker_count",
    "net_up_kbps", "net_down_kbps", "estab_tcp", "persistent_tcp", "tcp_created_by_page",
    "persistent_tcp_all", "persistent_peers",
    "page_ws_open", "page_ws_total", "page_ws_frames_up", "page_ws_frames_down",
    "page_ws_bytes_up", "page_ws_bytes_down", "page_ws_urls",
    "lab_hashrate_hps", "lab_shares", "lab_ws_bytes_out", "lab_ws_bytes_in",
]

SUMMARY_KEYS = [
    "tree_cpu_machine_pct", "tree_cpu_pct", "tree_rss_mb", "n_tree_procs",
    "js_heap_mb", "script_pct_core", "task_pct_core",
    "net_up_kbps", "net_down_kbps", "estab_tcp", "persistent_tcp", "tcp_created_by_page",
    "persistent_tcp_all", "persistent_peers",
    "page_ws_open", "page_ws_total", "page_ws_frames_up", "page_ws_frames_down",
    "page_ws_bytes_up", "page_ws_bytes_down", "page_ws_urls",
    "lab_hashrate_hps", "lab_shares", "lab_ws_bytes_out", "lab_ws_bytes_in",
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class TreeSampler:
    """CPU accounting over the browser process tree.

    psutil reports CPU percent since the previous call per process, so the
    sampler must be called at a steady interval; new child processes are
    re-enumerated each tick because Chrome/Edge spawns them lazily.
    """

    def __init__(self, root_pid: int, cpu_count: int):
        self.cpu_count = max(1, cpu_count)
        self.roles: dict[int, str] = {}
        try:
            self.root = psutil.Process(root_pid)
        except psutil.NoSuchProcess:
            self.root = None
        # psutil caches the previous cpu_times sample on the Process object, so
        # the objects must be reused across ticks or every reading is 0.
        self.cache: dict[int, psutil.Process] = {}
        self.procs: list[psutil.Process] = []
        self.refresh()

    def refresh(self) -> None:
        if self.root is None:
            return
        try:
            live = self.root.children(recursive=True) + [self.root]
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            live = []
        procs = []
        for p in live:
            cached = self.cache.get(p.pid)
            if cached is None:
                p.cpu_percent(None)  # prime the baseline sample for new children
                self.cache[p.pid] = p
                self.roles[p.pid] = role_of(p)
                procs.append(p)
            else:
                procs.append(cached)
        self.procs = procs

    def sample(self) -> dict:
        cpu = rss = 0.0
        n = 0
        for p in list(self.procs):
            try:
                cpu += p.cpu_percent(None)
                rss += p.memory_info().rss
                n += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                self.cache.pop(p.pid, None)
                continue
        return {"tree_cpu_pct": round(cpu, 2),
                "tree_cpu_machine_pct": round(cpu / self.cpu_count, 2),
                "tree_rss_mb": round(rss / 1048576.0, 1),
                "n_tree_procs": n}

    def established(self) -> list[tuple]:
        """(pid, role, laddr, lport, raddr, rport) for every socket the tree has open.

        Role matters: Edge keeps its own long-lived telemetry connections from the
        browser and utility processes, so a raw socket count says nothing about the
        page. Sockets from a --type=renderer process are the page's own.
        """
        out = set()
        for p in list(self.procs):
            try:
                role = self.roles.get(p.pid) or role_of(p)
                self.roles[p.pid] = role
                for c in p.net_connections(kind="inet"):
                    if c.status == psutil.CONN_ESTABLISHED and c.raddr:
                        out.add((p.pid, role, c.laddr[0], c.laddr[1], c.raddr[0], c.raddr[1]))
            except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
                self.cache.pop(p.pid, None)
                self.roles.pop(p.pid, None)
                continue
        return sorted(out)


def role_of(proc: psutil.Process) -> str:
    """Chromium process role from its command line."""
    try:
        cmd = " ".join(proc.cmdline())
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return "unknown"
    for kind in ("renderer", "gpu-process", "utility", "broker", "zygote"):
        if f"--type={kind}" in cmd:
            return kind
    return "browser"


class SocketTracker:
    """Separates sockets the *page* opened from the browser's own background keepalives.

    A mining pool connection is created during the visit and stays established for
    the whole window, whereas page-load connections are short-lived. Counting raw
    sockets does not work: Edge keeps its own sync/telemetry connections open, so
    the absolute number is dominated by traffic unrelated to the page.
    """

    def __init__(self, min_age_s: float = 4.0):
        self.min_age_s = min_age_s
        self.first: dict[tuple, float] = {}
        self.seen_ticks: dict[tuple, int] = {}
        self.tick = 0

    def update(self, t_s: float, conns: list[tuple]) -> dict:
        self.tick += 1
        alive = set()
        for c in conns:
            alive.add(c)
            self.first.setdefault(c, t_s)
            self.seen_ticks[c] = self.seen_ticks.get(c, 0) + 1
        def persistent(pred) -> list[tuple]:
            return [c for c in alive if t_s - self.first[c] >= self.min_age_s
                    and self.first[c] > 1.0 and pred(c)]
        page = persistent(lambda c: c[1] == "renderer")
        everything = persistent(lambda c: True)
        return {"persistent_tcp": len(page),
                "tcp_created_by_page": len([c for c in self.first
                                            if self.first[c] > 1.0 and c[1] == "renderer"]),
                "persistent_tcp_all": len(everything),
                "persistent_peers": "; ".join(sorted({f"{c[4]}:{c[5]}" for c in page}))}


class NetSampler:
    def __init__(self):
        self.prev = psutil.net_io_counters()
        self.prev_t = time.perf_counter()

    def sample(self) -> dict:
        cur = psutil.net_io_counters()
        dt = max(1e-6, time.perf_counter() - self.prev_t)
        up = (cur.bytes_sent - self.prev.bytes_sent) * 8 / dt / 1000.0
        down = (cur.bytes_recv - self.prev.bytes_recv) * 8 / dt / 1000.0
        self.prev, self.prev_t = cur, time.perf_counter()
        return {"net_up_kbps": round(max(0.0, up), 2), "net_down_kbps": round(max(0.0, down), 2)}


CDP_INSTANT = {"JSHeapUsedSize": "js_heap_mb", "JSHeapTotalSize": "js_heap_total_mb"}
CDP_CUMULATIVE = {"ScriptDuration": "script_pct_core", "TaskDuration": "task_pct_core"}


class PageProbe:
    """CDP-backed per-page metrics. Performance and Network both live on the
    page's own session; a browser-level session supports neither.

    Network is used only for WebSockets: HAR exports carry no WS frames, and the
    pool connection is the network signature under study. The loader keeps the
    socket on the page's own network stack, which is what makes it attributable
    to the page - the shared browser network service is not."""

    def __init__(self, page, browser_session=None):
        self.page = page
        self.session = page.context.new_cdp_session(page)
        self.session.send("Performance.enable")
        self.sockets: dict[str, dict] = {}
        self.net_events: list[list] = []
        self.t0 = time.perf_counter()
        self.prev_ws = {"page_ws_frames_sent": 0, "page_ws_frames_recv": 0,
                        "page_ws_bytes_sent": 0, "page_ws_bytes_recv": 0}
        try:
            self.session.send("Network.enable")
            self.session.on("Network.webSocketCreated", self._ws_created)
            self.session.on("Network.webSocketFrameSent", lambda e: self._ws_frame(e, True))
            self.session.on("Network.webSocketFrameReceived", lambda e: self._ws_frame(e, False))
            self.session.on("Network.webSocketClosed", self._ws_closed)
        except Exception:
            pass
        self.prev_cum: dict[str, float] = {}
        self.prev_t = time.perf_counter()
        self.browser_session = browser_session
        self.worker_count = 0

    def _rel(self) -> float:
        return round(time.perf_counter() - self.t0, 3)

    def _slot(self, rid):
        return self.sockets.setdefault(rid, {"url": "", "created": self._rel(), "closed": None,
                                             "sent": 0, "recv": 0, "sent_bytes": 0, "recv_bytes": 0})

    def _ws_created(self, e):
        rid = e["requestId"]
        self.sockets[rid] = {"url": e.get("url", ""), "created": self._rel(), "closed": None,
                             "sent": 0, "recv": 0, "sent_bytes": 0, "recv_bytes": 0}
        self.net_events.append([self._rel(), "ws_created", rid, e.get("url", ""), "", "", ""])

    def _ws_frame(self, e, sent: bool) -> None:
        rid = e["requestId"]
        # CDP calls the payload "response" on both sent and received frames;
        # the direction has to come from which event fired.
        frame = e.get("response") or e.get("wsFrameSent") or e.get("wsFrameReceived") or {}
        # Edge/Chromium builds differ: some omit byteLength, so fall back to the
        # payload text plus the WebSocket framing overhead (2 + 4 mask bytes).
        size = frame.get("byteLength")
        if size is None:
            size = len(frame.get("payloadData", "").encode("utf8", errors="replace")) + (6 if frame.get("mask") else 2)
        s = self._slot(rid)
        key = "sent" if sent else "recv"
        s[key] += 1
        s[key + "_bytes"] += size
        self.net_events.append([self._rel(), "ws_frame_" + key, rid, frame.get("opcode", ""),
                                size, int(bool(frame.get("masked", False))), ""])

    def _ws_closed(self, e):
        rid = e["requestId"]
        if rid in self.sockets:
            self.sockets[rid]["closed"] = self._rel()
        self.net_events.append([self._rel(), "ws_closed", rid, "", "", "", ""])

    def ws_summary(self) -> dict:
        open_now = [v for v in self.sockets.values() if v["closed"] is None]
        return {"page_ws_open": len(open_now), "page_ws_total": len(self.sockets),
                "page_ws_frames_sent": sum(v["sent"] for v in self.sockets.values()),
                "page_ws_frames_recv": sum(v["recv"] for v in self.sockets.values()),
                "page_ws_bytes_sent": sum(v["sent_bytes"] for v in self.sockets.values()),
                "page_ws_bytes_recv": sum(v["recv_bytes"] for v in self.sockets.values()),
                "page_ws_urls": "; ".join(sorted({v["url"] for v in self.sockets.values() if v["url"]}))}

    def sample(self) -> dict:
        try:
            metrics = {m["name"]: m["value"] for m in self.session.send("Performance.getMetrics")["metrics"]}
        except Exception:
            return {}
        now = time.perf_counter()
        dt = max(1e-6, now - self.prev_t)
        self.prev_t = now
        out: dict = {}
        for key, name in CDP_INSTANT.items():
            out[name] = round(metrics.get(key, 0.0) / 1048576.0, 2)
        for key, name in CDP_CUMULATIVE.items():
            v = metrics.get(key, 0.0)
            prev = self.prev_cum.get(key, v)
            self.prev_cum[key] = v
            out[name] = round(max(0.0, (v - prev) / dt) * 100.0, 2)
        try:
            out["page_dom_nodes"] = self.page.evaluate("() => document.getElementsByTagName('*').length")
        except Exception:
            out["page_dom_nodes"] = ""
        if self.browser_session is not None:
            try:
                targets = self.browser_session.send("Target.getTargets")["targetInfos"]
                self.worker_count = sum(1 for t in targets if t.get("type") in ("worker", "shared_worker"))
            except Exception:
                pass
        out["worker_count"] = self.worker_count
        ws = self.ws_summary()
        prev, self.prev_ws = self.prev_ws, ws
        out["page_ws_open"] = ws["page_ws_open"]
        out["page_ws_total"] = ws["page_ws_total"]
        out["page_ws_frames_up"] = ws["page_ws_frames_sent"] - prev["page_ws_frames_sent"]
        out["page_ws_frames_down"] = ws["page_ws_frames_recv"] - prev["page_ws_frames_recv"]
        out["page_ws_bytes_up"] = ws["page_ws_bytes_sent"] - prev["page_ws_bytes_sent"]
        out["page_ws_bytes_down"] = ws["page_ws_bytes_recv"] - prev["page_ws_bytes_recv"]
        return out


class LabStatsProbe:
    """Ground truth: the page's own self-reported mining statistics."""

    def __init__(self, page):
        self.page = page

    def sample(self) -> dict:
        try:
            s = self.page.evaluate("() => (window.__lab && window.__lab.stats) ? window.__lab.stats() : null")
        except Exception:
            return {}
        if not s:
            return {}
        return {
            "lab_hashrate_hps": round(s.get("hashrate", 0), 1),
            "lab_shares": s.get("shares", 0),
            "lab_ws_bytes_out": s.get("bytesSent", 0),
            "lab_ws_bytes_in": s.get("bytesReceived", 0),
        }


def find_browser_pid(marker: str, names: set[str]) -> int | None:
    """Chromium's root process is the only one carrying our launch marker."""
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            if (proc.info["name"] or "").lower() in names and marker in (proc.info["cmdline"] or []):
                return proc.pid
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            continue
    return None


def launch_browser(p, args):
    marker = f"--p5-marker={uuid.uuid4().hex[:8]}"
    kwargs = {"headless": not args.headed}
    if args.browser_exec:
        kwargs["executable_path"] = args.browser_exec
    else:
        kwargs["channel"] = args.channel
    browser = p.chromium.launch(**kwargs, args=[marker, "--disable-extensions", "--no-first-run"])
    names = {os.path.basename(kwargs.get("executable_path", "")).lower()} if args.browser_exec \
        else {"msedge.exe", "chrome.exe"}
    for _ in range(50):
        pid = find_browser_pid(marker, names)
        if pid:
            return browser, pid
        time.sleep(0.1)
    raise SystemExit("could not identify the browser process for CPU accounting")


def url_slug(url: str) -> str:
    """A filesystem-safe per-target name; without this every live-mode URL would
    overwrite the same timeseries/HAR/socket files."""
    tail = re.sub(r"[^A-Za-z0-9]+", "_", urlparse(url).netloc + urlparse(url).path).strip("_")
    return (tail or "root")[:40]


def run_trial(browser, browser_session, cond: str, threads: int, trial: int, url: str, args, browser_pid: int) -> dict:
    slug = url_slug(url)
    started = time.perf_counter()
    started_iso = now_iso()
    page_url = tag_url(url, cond, threads, trial, enabled=(args.mode == "lab"))
    RESULTS.mkdir(parents=True, exist_ok=True)
    ctx_kwargs = {}
    if not args.no_har:
        har_dir = RESULTS / "har"
        har_dir.mkdir(parents=True, exist_ok=True)
        ctx_kwargs["record_har_path"] = str(har_dir / f"{cond}_{slug}_t{threads}_r{trial}.har")
    context = browser.new_context(**ctx_kwargs)
    page = context.new_page()

    probe = PageProbe(page, browser_session)
    lab = LabStatsProbe(page)
    tree = TreeSampler(browser_pid, args.cpu_count)
    net = NetSampler()
    sock = SocketTracker(min_age_s=args.persist_s)
    sock_log = RESULTS / "sockets"
    sock_log.mkdir(parents=True, exist_ok=True)
    sock_rows: list[list] = []

    page.goto(page_url, wait_until="domcontentloaded", timeout=args.nav_timeout * 1000)
    time.sleep(args.warmup)

    rows = []
    interval = args.sample_ms / 1000.0
    tick = 0
    next_at = time.perf_counter()
    # the observation window starts after navigation completes, so a slow site
    # cannot eat the sampling time
    deadline = next_at + args.duration
    while time.perf_counter() < deadline:
        next_at += interval
        tree.refresh()
        row = {"t_s": round(time.perf_counter() - started, 3), "cond": cond, "threads": threads, "trial": trial}
        row.update(tree.sample())
        row.update(probe.sample())
        row.update(net.sample())
        slow = tick % max(1, args.slow_every) == 0
        if slow:
            conns = tree.established()
            row["estab_tcp"] = len(conns)
            row.update(sock.update(row["t_s"], conns))
            for c in conns:
                sock_rows.append([row["t_s"], *c])
            row.update(lab.sample())
        rows.append(row)
        tick += 1
        remaining = next_at - time.perf_counter()
        if remaining > 0:
            time.sleep(remaining)

    net_dir = RESULTS / "netevents"
    net_dir.mkdir(parents=True, exist_ok=True)
    with open(net_dir / f"{cond}_{slug}_t{threads}_r{trial}.csv", "w", newline="", encoding="utf8") as fh:
        w = csv.writer(fh)
        w.writerow(["t_s", "event", "request_id", "url_or_opcode", "bytes", "masked", "extra"])
        w.writerows(probe.net_events)
    ws_sum = probe.ws_summary()
    summary_ws = dict(ws_sum)
    summary_ws["page_ws_lifetimes"] = "; ".join(
        f"{v['url'].split('//')[-1]}:{v['created']}->{v['closed'] if v['closed'] is not None else 'open'}"
        for v in list(probe.sockets.values())[:12])

    if sock_rows:
        with open(sock_log / f"{cond}_{slug}_t{threads}_r{trial}.csv", "w", newline="", encoding="utf8") as fh:
            w = csv.writer(fh)
            w.writerow(["t_s", "pid", "role", "laddr", "lport", "raddr", "rport"])
            w.writerows(sock_rows)

    ts_dir = RESULTS / "timeseries"
    ts_dir.mkdir(parents=True, exist_ok=True)
    out_path = ts_dir / f"{cond}_{slug}_t{threads}_r{trial}.csv"
    with open(out_path, "w", newline="", encoding="utf8") as fh:
        writer = csv.DictWriter(fh, fieldnames=TIME_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

    summary = summarise(rows, cond, threads, trial, url)
    summary["slug"] = slug
    peers = set()
    for r in rows:
        peers.update(x for x in str(r.get("persistent_peers", "")).split("; ") if x)
    summary["persistent_peers"] = "; ".join(sorted(peers))
    summary["start_iso"] = started_iso
    summary["end_iso"] = now_iso()
    summary["tagged_url"] = page_url
    try:
        context.close()  # flushes the HAR
    except Exception:
        pass
    har_file = (RESULTS / "har" / f"{cond}_{slug}_t{threads}_r{trial}.har")
    if har_file.exists():
        if sanitize_har:
            sanitize_har.scrub_file(har_file)  # cookies / GeoIP must not leave the machine
        summary["har"] = str(har_file.relative_to(PROJECT))
        summary["har_bytes_total"] = har_bytes(har_file)
        summary["har_entries"] = har_entry_count(har_file)
    return summary


def har_bytes(path: Path) -> int:
    try:
        har = json.loads(path.read_text(encoding="utf8"))
        return sum(max(0, e["response"].get("bodySize", 0)) for e in har["log"]["entries"])
    except Exception:
        return -1


def har_entry_count(path: Path) -> int:
    try:
        return len(json.loads(path.read_text(encoding="utf8"))["log"]["entries"])
    except Exception:
        return -1


def summarise(rows, cond, threads, trial, url) -> dict:
    skip = max(1, int(len(rows) * 0.1))  # discard the ramp-up samples
    out = {"cond": cond, "threads": threads, "trial": trial, "url": url,
           "samples": len(rows),
           "duration_s": round(rows[-1]["t_s"] - rows[0]["t_s"], 2) if rows else 0}
    for key in SUMMARY_KEYS:
        vals = [r[key] for r in rows[skip:] if isinstance(r.get(key), (int, float))]
        if not vals:
            continue
        out[key + "_mean"] = round(statistics.fmean(vals), 2)
        out[key + "_p95"] = round(sorted(vals)[min(len(vals) - 1, int(len(vals) * 0.95))], 2)
        out[key + "_max"] = round(max(vals), 2)
        if len(vals) > 2:
            out[key + "_sd"] = round(statistics.pstdev(vals), 2)
    return out


def lab_conditions(args) -> list[tuple[str, int, str]]:
    """Condition -> URL. The pool endpoint and a per-trial worker tag are passed
    in the query string so the pool log can attribute connections to conditions."""
    base = f"http://127.0.0.1:{args.http_port}"
    pool = f"ws://127.0.0.1:{args.pool_port}/stratum"
    out: list[tuple[str, int, str]] = []
    for cond in args.condition_list:
        if cond == "clean":
            out.append(("clean", 0, f"{base}/clean?pool={pool}"))
        elif cond == "busy":
            for t in args.thread_list:
                out.append(("busy", t, f"{base}/busy?mode=busy&threads={t}&pool={pool}"))
        elif cond == "mining":
            for t in args.thread_list:
                out.append(("mining", t, f"{base}/mining?mode=mine&threads={t}&pool={pool}"))
    return out


def tag_url(url: str, cond: str, threads: int, trial: int, enabled: bool = True) -> str:
    """Lab pages carry a worker tag so the pool log can attribute connections."""
    if not enabled or "127.0.0.1" not in url:
        return url
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}user={cond}{threads}w{trial}&bust={time.time()}"


def start_lab_server(args):
    if args.mode != "lab":
        return None
    # the lab server's traffic logs belong to whichever run started it
    env = dict(os.environ, P5_RESULTS=str(Path(os.environ.get("P5_RESULTS", PROJECT / "results"))))
    cmd = [sys.executable, str(PROJECT / "lab" / "lab_server.py"),
           "--http-port", str(args.http_port), "--pool-port", str(args.pool_port),
           "--job-interval", str(args.job_interval),
           "--target-share-interval", str(args.share_interval),
           "--start-difficulty", str(args.start_difficulty),
           "--min-difficulty", str(args.min_difficulty),
           "--retarget-every", str(args.retarget_every)]
    popen_kwargs = {"env": env, "stdout": subprocess.PIPE, "stderr": subprocess.STDOUT, "text": True}
    if os.name == "nt":
        popen_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    proc = subprocess.Popen(cmd, **popen_kwargs)
    deadline = time.time() + 25
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", args.http_port), timeout=1):
                pass
            with socket.create_connection(("127.0.0.1", args.pool_port), timeout=1):
                pass
            return proc
        except OSError:
            if proc.poll() is not None:
                print(proc.stdout.read(), file=sys.stderr)
                raise SystemExit("lab server exited during startup")
            time.sleep(0.3)
    raise SystemExit("lab server did not become ready")


def write_meta(browser, args, browser_pid: int) -> dict:
    mem = psutil.virtual_memory()
    meta = {
        "captured_at": now_iso(),
        "mode": args.mode,
        "python": sys.version.split()[0],
        "platform": f"{platform.system()} {platform.release()} {platform.machine()}",
        "cpu_count_logical": psutil.cpu_count(logical=True),
        "cpu_count_physical": psutil.cpu_count(logical=False),
        "ram_total_gb": round(mem.total / 1073741824, 1),
        "browser": browser.version,
        "channel": args.channel or args.browser_exec,
        "headed": args.headed,
        "browser_pid": browser_pid,
        "sample_ms": args.sample_ms,
        "duration_s": args.duration,
        "warmup_s": args.warmup,
        "trials_per_condition": args.trials,
        "thread_sweep": args.thread_list,
        "conditions": args.condition_list,
        "lab_ports": {"http": args.http_port, "pool": args.pool_port},
        "job_interval_s": args.job_interval,
        "target_share_interval_s": args.share_interval,
        "start_difficulty_bits": args.start_difficulty,
        "min_difficulty_bits": args.min_difficulty,
        "retarget_every_shares": args.retarget_every,
        "caveat": "headless mode shares the host CPU; run --headed and close other apps for publication numbers",
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf8")
    return meta


def parse_args(argv=None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", choices=["lab", "live"], default="lab")
    ap.add_argument("--conditions", default="clean,busy,mining")
    ap.add_argument("--threads", default="1,2,4")
    ap.add_argument("--trials", type=int, default=2)
    ap.add_argument("--duration", type=float, default=30.0)
    ap.add_argument("--warmup", type=float, default=5.0)
    ap.add_argument("--sample-ms", type=int, default=250)
    ap.add_argument("--slow-every", type=int, default=4, help="read socket table + page stats every N samples")
    ap.add_argument("--persist-s", type=float, default=4.0,
                    help="a socket counts as page-created-and-persistent after this many seconds")
    ap.add_argument("--urls", default=str(PROJECT / "config" / "target_urls.txt"))
    ap.add_argument("--http-port", type=int, default=8080)
    ap.add_argument("--pool-port", type=int, default=8777)
    ap.add_argument("--job-interval", type=float, default=3.0)
    ap.add_argument("--share-interval", type=float, default=2.0)
    ap.add_argument("--start-difficulty", type=int, default=22, help="initial pool difficulty, leading zero bits")
    ap.add_argument("--min-difficulty", type=int, default=12)
    ap.add_argument("--retarget-every", type=int, default=4)
    ap.add_argument("--channel", default="msedge", help="msedge | chrome | chromium")
    ap.add_argument("--browser-exec", default="")
    ap.add_argument("--headed", action="store_true")
    ap.add_argument("--no-har", action="store_true")
    ap.add_argument("--nav-timeout", type=int, default=45)
    ap.add_argument("--max-live", type=int, default=8, help="cap on URLs measured in live mode")
    args = ap.parse_args(argv)
    args.condition_list = [c.strip() for c in args.conditions.split(",") if c.strip()]
    args.thread_list = [int(t) for t in args.threads.split(",") if t.strip()]
    args.cpu_count = psutil.cpu_count(logical=True) or 4
    return args


def main(argv=None) -> None:
    args = parse_args(argv)
    lab_proc = start_lab_server(args)
    summaries: list[dict] = []
    try:
        with sync_playwright() as p:
            browser, browser_pid = launch_browser(p, args)
            browser_session = browser.new_browser_cdp_session()
            write_meta(browser, args, browser_pid)

            if args.mode == "lab":
                targets = lab_conditions(args)
            else:
                urls = [u.strip() for u in Path(args.urls).read_text(encoding="utf8").splitlines()
                        if u.strip() and not u.startswith("#")]
                targets = [("live", 0, u) for u in urls[: args.max_live]]

            total = len(targets) * args.trials
            done = 0
            for cond, threads, url in targets:
                for trial in range(1, args.trials + 1):
                    done += 1
                    print(f"[{done}/{total}] {cond} threads={threads} trial={trial}  {url}", flush=True)
                    try:
                        summaries.append(run_trial(browser, browser_session, cond, threads, trial, url, args, browser_pid))
                    except Exception as exc:
                        print(f"    FAILED: {type(exc).__name__}: {exc}", flush=True)
                        summaries.append({"cond": cond, "threads": threads, "trial": trial, "url": url,
                                          "error": f"{type(exc).__name__}: {exc}"})
            browser.close()
    finally:
        if lab_proc:
            lab_proc.terminate()
            try:
                lab_proc.wait(10)
            except subprocess.TimeoutExpired:
                lab_proc.kill()

    keys: list[str] = []
    for s in summaries:
        for k in s:
            if k not in keys:
                keys.append(k)
    out = RESULTS / "trials.csv"
    RESULTS.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf8") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        for s in summaries:
            w.writerow(s)
    print(f"\nwrote {out} ({len(summaries)} trials)")
    print(f"timeseries: {RESULTS / 'timeseries'}")
    print(f"lab traffic: {RESULTS.parent / 'lab'}")


if __name__ == "__main__":
    main()
