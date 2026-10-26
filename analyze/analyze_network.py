"""Stage 4b: characterise the network behaviour of browser-based mining.

Two independent vantage points are joined:

  * server side - the lab pool logs every WebSocket frame with size, direction,
    message type and difficulty (results/lab/pool_frames.csv)
  * client side - Playwright HAR exports for the page loads, plus the socket
    table sampled during each trial (results/measure/)

The point of the section is the contrast: an ordinary page is a short burst of
large HTTP responses, a mining page adds long-lived sockets carrying tiny
periodic messages while the CPU stays pinned.

Usage:
  python analyze_network.py
  python analyze_network.py --pool-log ../results/lab/pool_frames.csv
"""

from __future__ import annotations

import argparse
import os
import re
import csv
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlparse

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
RESULTS = Path(os.environ.get("P5_RESULTS", PROJECT / "results"))
OUT = RESULTS / "analysis" / "network"
DPI = 300


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, encoding="utf8") as fh:
        return list(csv.DictReader(fh))


def f(v, default=0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def describe(vals: list[float]) -> dict:
    vals = [v for v in vals if v is not None]
    if not vals:
        return {}
    s = sorted(vals)
    return {"n": len(s), "mean": statistics.fmean(s), "median": statistics.median(s),
             "p95": s[min(len(s) - 1, int(len(s) * 0.95))], "max": s[-1],
             "min": s[0], "sd": statistics.pstdev(s) if len(s) > 1 else 0.0}


def inter_arrival(times: list[float]) -> list[float]:
    t = sorted(times)
    return [b - a for a, b in zip(t, t[1:])]


def analyse_pool(frames: list[dict], events: list[dict]) -> dict:
    per_conn: dict[str, dict] = {}
    for row in frames:
        cid = row["conn_id"]
        c = per_conn.setdefault(cid, {"id": cid, "worker": row.get("worker", ""),
                                      "t": [], "in_bytes": [], "out_bytes": [],
                                      "share_times": [], "job_times": [], "types": Counter(),
                                      "difficulty": []})
        c["t"].append(f(row["elapsed_s"], 0))
        c["types"][row.get("msg_type", "") or "unknown"] += 1
        size = f(row["frame_bytes"], 0)
        c["in_bytes" if row["dir"] == "in" else "out_bytes"].append(size)
        if row.get("msg_type") == "share":
            c["share_times"].append(f(row["elapsed_s"], 0))
        if row.get("msg_type") == "job":
            c["job_times"].append(f(row["elapsed_s"], 0))
        if f(row.get("difficulty"), 0):
            c["difficulty"].append((f(row["elapsed_s"], 0), int(f(row["difficulty"], 0))))

    summary = {}
    def tag_of(worker: str) -> str:
        # pool login is "<wallet>.<condition><threads>w<trial>_<idx>" -> keep the tag
        tail = (worker or "").split(".")[-1]
        return tail.rsplit("_", 1)[0] or "untagged"

    for cid, c in per_conn.items():
        span = (max(c["t"]) - min(c["t"])) if c["t"] else 0
        total = sum(c["in_bytes"]) + sum(c["out_bytes"])
        share_iv = inter_arrival(c["share_times"])
        job_iv = inter_arrival(c["job_times"])
        summary[cid] = {
            "conn_id": cid,
            "trial_tag": tag_of(c["worker"]),
            "worker": c["worker"],
            "first_s": min(c["t"]) if c["t"] else 0,
            "last_s": max(c["t"]) if c["t"] else 0,
            "lifetime_s": round(span, 2),
            "frames": len(c["t"]),
            "frame_types": dict(c["types"]),
            "bytes_up": sum(c["in_bytes"]),
            "bytes_down": sum(c["out_bytes"]),
            "mean_frame_up": round(statistics.fmean(c["in_bytes"]), 1) if c["in_bytes"] else 0,
            "mean_frame_down": round(statistics.fmean(c["out_bytes"]), 1) if c["out_bytes"] else 0,
            "max_frame_up": max(c["in_bytes"]) if c["in_bytes"] else 0,
            "up_kbps": round(sum(c["in_bytes"]) * 8 / max(span, 1e-6) / 1000, 3),
            "down_kbps": round(sum(c["out_bytes"]) * 8 / max(span, 1e-6) / 1000, 3),
            "shares": len(c["share_times"]),
            "share_interval_mean_s": round(statistics.fmean(share_iv), 2) if share_iv else None,
            "share_interval_sd_s": round(statistics.pstdev(share_iv), 2) if len(share_iv) > 1 else None,
            "job_interval_mean_s": round(statistics.fmean(job_iv), 2) if job_iv else None,
            "difficulty_trace": c["difficulty"][:60],
            "total": total,
        }
    lifetimes = [s["lifetime_s"] for s in summary.values()]
    opens = [e for e in events if e.get("event") == "open"]
    closes = [e for e in events if e.get("event") == "close"]
    agg = {
        "connections": len(summary),
        "open_events": len(opens),
        "close_events": len(closes),
        "total_bytes": sum(s["total"] for s in summary.values()),
        "mean_lifetime_s": round(statistics.fmean(lifetimes), 2) if lifetimes else 0,
        "mean_frames_per_conn": round(statistics.fmean([s["frames"] for s in summary.values()]), 1) if summary else 0,
        "mean_up_kbps": round(statistics.fmean([s["up_kbps"] for s in summary.values()]), 3) if summary else 0,
        "message_mix": dict(sum((Counter(s["frame_types"]) for s in summary.values()), Counter())),
        "bytes_up_total": sum(s["bytes_up"] for s in summary.values()),
        "bytes_down_total": sum(s["bytes_down"] for s in summary.values()),
    }
    by_tag: dict[str, list[dict]] = {}
    for s in summary.values():
        by_tag.setdefault(s["trial_tag"], []).append(s)
    per_trial = {}
    for tag, items in sorted(by_tag.items()):
        span = max(i["last_s"] for i in items) - min(i["first_s"] for i in items)
        per_trial[tag] = {
            "trial_tag": tag,
            "sockets": len(items),
            "window_s": round(span, 1),
            "frames": sum(i["frames"] for i in items),
            "bytes_up": sum(i["bytes_up"] for i in items),
            "bytes_down": sum(i["bytes_down"] for i in items),
            "up_kbps": round(sum(i["bytes_up"] for i in items) * 8 / max(span, 1e-6) / 1000, 3),
            "mean_frame_up": round(statistics.fmean([i["mean_frame_up"] for i in items]), 1),
            "shares": sum(i["shares"] for i in items),
            "shares_per_s": round(sum(i["shares"] for i in items) / max(span, 1e-6), 3),
            "mean_lifetime_s": round(statistics.fmean([i["lifetime_s"] for i in items]), 2),
            "mean_share_interval_s": round(statistics.fmean(
                [i["share_interval_mean_s"] for i in items if i["share_interval_mean_s"]]), 2)
                if any(i["share_interval_mean_s"] for i in items) else None,
        }

    return {"per_connection": summary, "aggregate": agg, "per_trial": per_trial}


def analyse_http(http_log: list[dict]) -> dict:
    by_path = Counter()
    sizes = []
    for row in http_log:
        by_path[row["path"]] += 1
        sizes.append(f(row["bytes_out"], 0))
    times = sorted(f(r["elapsed_s"], 0) for r in http_log)
    iv = inter_arrival(times)
    return {
        "requests": len(http_log),
        "bytes_total": sum(sizes),
        "unique_paths": len(by_path),
        "top_paths": by_path.most_common(8),
        "mean_response_bytes": round(statistics.fmean(sizes), 1) if sizes else 0,
        "burst_window_s": round((times[-1] - times[0]), 2) if times else 0,
        "requests_per_s": round(len(times) / max((times[-1] - times[0]) if times else 1, 1e-6), 2),
        "inter_request_mean_s": round(statistics.fmean(iv), 3) if iv else 0,
        "note": "HTTP page traffic is a short burst of KB-scale responses",
    }


def analyse_hars(har_dir: Path) -> dict:
    """Client-side view, including live (non-lab) pages."""
    out = {}
    if not har_dir.is_dir():
        return out
    for har in sorted(har_dir.glob("*.har")):
        try:
            data = json.loads(har.read_text(encoding="utf8"))
        except Exception:
            continue
        entries = data.get("log", {}).get("entries", [])
        hosts = Counter(urlparse(e["request"]["url"]).netloc for e in entries)
        mime = Counter((e["response"].get("content", {}).get("mimeType", "") or "").split(";")[0] for e in entries)
        sizes = [max(0, e["response"].get("bodySize", 0)) for e in entries]
        durations = [f(e.get("time"), 0) for e in entries]
        pending = [e for e in entries if f(e.get("response", {}).get("status"), 0) == 0]
        out[har.stem] = {
            "requests": len(entries),
            "bytes": sum(sizes),
            "hosts": dict(hosts.most_common(10)),
            "mime": dict(mime),
            "mean_response_kbytes": round(statistics.fmean(sizes) / 1024, 1) if sizes else 0,
            "max_response_kbytes": round(max(sizes) / 1024, 1) if sizes else 0,
            "load_time_ms": round(sum(durations), 1),
            "unfinished_requests": len(pending),
        }
    return out


def parse_trial_stem(stem: str) -> tuple[str, str, str]:
    """`{cond}_{slug}_t{threads}_r{trial}` -> (cond, threads, trial); slug may hold underscores."""
    m = re.search(r"_t(\d+)_r(\d+)$", stem)
    if not m:
        return stem.split("_")[0], "0", "1"
    cond = stem.split("_", 1)[0]
    return cond, m.group(1), m.group(2)


def analyse_sockets(sock_dir: Path) -> list[dict]:
    """Client-side view: which peers each visited page kept a socket open to.

    This is the evidence that survives not knowing the pool's own logs - a
    monitoring agent on the endpoint can see exactly this much.
    """
    out = []
    if not sock_dir.is_dir():
        return out
    for path in sorted(sock_dir.glob("*.csv")):
        cond, threads, trial = parse_trial_stem(path.stem)
        peers: dict[str, dict] = {}
        for row in read_csv(path):
            peer = f"{row['raddr']}:{row['rport']}"
            t = f(row["t_s"], 0)
            e = peers.setdefault(peer, {"peer": peer, "first": t, "last": t, "ticks": 0,
                                        "pids": set(), "lports": set()})
            e["last"] = max(e["last"], t)
            e["ticks"] += 1
            e["pids"].add(row["pid"])
            e["lports"].add(row["lport"])
        for e in peers.values():
            e["lifetime_s"] = round(e["last"] - e["first"], 1)
            e["pids"] = sorted(e["pids"])
            e["local_ports"] = len(e.pop("lports"))
            e["cond"], e["threads"], e["trial"] = cond, threads, trial
            out.append(e)
    return out


def analyse_ws_events(ws_dir: Path) -> list[dict]:
    """Page-owned WebSockets from CDP - the client-side twin of the pool log.

    Available for any URL, including live pages with no pool we control, which is
    what makes this the transferable feature for detection.
    """
    out = []
    if not ws_dir.is_dir():
        return out
    for path in sorted(ws_dir.glob("*.csv")):
        cond, threads, trial = parse_trial_stem(path.stem)
        socks: dict[str, dict] = {}
        sizes_up, sizes_down = [], []
        for row in read_csv(path):
            rid = row["request_id"]
            t = f(row["t_s"], 0)
            ev = row["event"]
            e = socks.setdefault(rid, {"cond": cond, "threads": threads, "trial": trial,
                                       "url": row["url_or_opcode"] if ev == "ws_created" else "",
                                       "created": t, "last_seen": t, "closed": None,
                                       "frames_up": 0, "frames_down": 0,
                                       "bytes_up": 0, "bytes_down": 0, "sizes": []})
            e["last_seen"] = max(e["last_seen"], t)
            if ev == "ws_created":
                e["url"] = row["url_or_opcode"]
            elif ev == "ws_frame_sent":
                e["frames_up"] += 1
                e["bytes_up"] += f(row["bytes"], 0)
                sizes_up.append(f(row["bytes"], 0))
                e["sizes"].append(t)
            elif ev == "ws_frame_recv":
                e["frames_down"] += 1
                e["bytes_down"] += f(row["bytes"], 0)
                sizes_down.append(f(row["bytes"], 0))
            elif ev == "ws_closed":
                e["closed"] = t
        for e in socks.values():
            gaps = inter_arrival(e.pop("sizes"))
            e["lifetime_s"] = round((e["closed"] if e["closed"] is not None else e["last_seen"]) - e["created"], 1)
            e["mean_frame_gap_s"] = round(statistics.fmean(gaps), 2) if gaps else None
            e["mean_frame_up"] = round(statistics.fmean(sizes_up), 1) if sizes_up else 0
            e["open_at_end"] = e["closed"] is None
            out.append(e)
    return out


def compare_with_page_metrics(trials: list[dict]) -> list[dict]:
    rows = []
    for r in trials:
        rows.append({
            "group": f"{r['cond']}-w{r['threads']}" if r["cond"] != "clean" else "clean",
            "estab_tcp_p95": f(r.get("estab_tcp_p95"), 0),
            "estab_tcp_mean": f(r.get("estab_tcp_mean"), 0),
            "up_kbps_mean": f(r.get("net_up_kbps_mean"), 0),
            "cpu_mean": f(r.get("tree_cpu_pct_mean"), 0),
            "har_entries": f(r.get("har_entries"), 0),
            "har_bytes": f(r.get("har_bytes_total"), 0),
        })
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pool-log", default=str(RESULTS / "lab" / "pool_frames.csv"))
    ap.add_argument("--pool-events", default=str(RESULTS / "lab" / "pool_events.csv"))
    ap.add_argument("--http-log", default=str(RESULTS / "lab" / "http_access.csv"))
    ap.add_argument("--hars", default=str(RESULTS / "measure" / "har"))
    ap.add_argument("--sockets", default=str(RESULTS / "measure" / "sockets"))
    ap.add_argument("--wsevents", default=str(RESULTS / "measure" / "netevents"))
    ap.add_argument("--trials", default=str(RESULTS / "measure" / "trials.csv"))
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    frames = read_csv(Path(args.pool_log))
    events = read_csv(Path(args.pool_events))
    http_log = read_csv(Path(args.http_log))
    trials = read_csv(Path(args.trials))

    if not frames:
        print(f"WARNING: no pool frames in {args.pool_log} - run the lab measurement first")

    socks = analyse_sockets(Path(args.sockets))
    ws_events = analyse_ws_events(Path(args.wsevents))
    pool = analyse_pool(frames, events)
    http = analyse_http(http_log)
    hars = analyse_hars(Path(args.hars))
    page = compare_with_page_metrics(trials)

    if socks:
        with open(OUT / "client_sockets.csv", "w", newline="", encoding="utf8") as fh:
            cols = ["cond", "threads", "trial", "peer", "first", "last", "lifetime_s", "ticks",
                    "local_ports", "pids"]
            w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
            w.writeheader()
            for e in sorted(socks, key=lambda x: (-x["lifetime_s"], x["peer"])):
                w.writerow(e)

    if ws_events:
        with open(OUT / "page_websockets.csv", "w", newline="", encoding="utf8") as fh:
            cols = ["cond", "threads", "trial", "url", "created", "closed", "lifetime_s", "open_at_end",
                    "frames_up", "frames_down", "bytes_up", "bytes_down", "mean_frame_up", "mean_frame_gap_s"]
            w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
            w.writeheader()
            for e in ws_events:
                w.writerow(e)
        lines_ws = ["", "## Page-owned WebSockets (CDP, client side)", "",
                    "| condition | threads | trial | url | lifetime s | frames up | frames down | bytes up | mean frame B | mean gap s |",
                    "|---|---|---|---|---|---|---|---|---|---|"]
        for e in ws_events[:60]:
            lines_ws.append(f"| {e['cond']} | {e['threads']} | {e['trial']} | {e['url'][:44]} | {e['lifetime_s']} | "
                            f"{e['frames_up']} | {e['frames_down']} | {e['bytes_up']} | {e['mean_frame_up']} | "
                            f"{e['mean_frame_gap_s']} |")
        lines_ws.append("")
        lines_ws.append("These are visible to any browser-resident monitor without knowing the pool: the page "
                        "itself opened the socket and kept it alive for the whole visit.")

    payload = {"pool": pool, "http_page_traffic": http, "har_per_trial": hars,
               "page_websockets": ws_events,
               "client_sockets": socks,
               "client_side_socket_metrics": page,
               "generated_from": {"pool_frames": args.pool_log, "http_access": args.http_log}}
    (OUT / "network_profile.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf8")

    lines = ["# Network characterisation of browser-based mining", ""]
    agg = pool["aggregate"]
    lines += [
        "## Emulated pool (server side)",
        "",
        f"- connections opened: {agg['connections']} ({agg['open_events']} open / {agg['close_events']} close events)",
        f"- mean connection lifetime: {agg['mean_lifetime_s']} s",
        f"- mean frames per connection: {agg['mean_frames_per_conn']}",
        f"- message mix: {agg['message_mix']}",
        f"- total bytes: {agg['total_bytes']} (up {agg['bytes_up_total']}, down {agg['bytes_down_total']}) "
        f"= {agg['mean_up_kbps']} kbps mean uplink per connection",
        "",
        "| conn | worker | lifetime s | frames | bytes up | mean frame up | up kbps | shares | share interval s | job interval s |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for cid, s in sorted(pool["per_connection"].items(), key=lambda kv: int(kv[0])):
        lines.append(f"| {cid} | {(s['worker'] or '')[-24:]} | {s['lifetime_s']} | {s['frames']} | "
                     f"{s['bytes_up']} | {s['mean_frame_up']} | {s['up_kbps']} | {s['shares']} | "
                     f"{s['share_interval_mean_s']} | {s['job_interval_mean_s']} |")

    lines += ["", "## Ordinary page traffic (same server, HTTP)", "",
              f"- requests: {http['requests']}, unique paths: {http['unique_paths']}",
              f"- total bytes: {http['bytes_total']}, mean response: {http['mean_response_bytes']} B",
              f"- burst window: {http['burst_window_s']} s -> {http['requests_per_s']} req/s, "
              f"mean gap between requests {http['inter_request_mean_s']} s",
              f"- top paths: {http['top_paths']}",
              "",
              "Reading: mining adds a *persistent* socket carrying ~100-byte messages every couple of seconds, "
              "while page loads are a *transient* burst of kilobyte responses. A flow-level detector sees both; "
              "the discriminator is flow lifetime and message size, not volume."]

    per_trial = pool.get("per_trial", {})
    if per_trial:
        lines += ["", "## Per trial (pool connections grouped by the URL worker tag)", "",
                  "| trial tag | sockets | window s | frames | bytes up | up kbps | mean frame up | shares | shares/s | mean socket lifetime s |",
                  "|---|---|---|---|---|---|---|---|---|---|"]
        for tag, t in per_trial.items():
            lines.append(f"| {tag} | {t['sockets']} | {t['window_s']} | {t['frames']} | {t['bytes_up']} | "
                         f"{t['up_kbps']} | {t['mean_frame_up']} | {t['shares']} | {t['shares_per_s']} | "
                         f"{t['mean_lifetime_s']} |")
        lines += ["",
                  "Reading: socket count tracks the worker/thread count exactly, lifetime spans the whole visit, "
                  "and each socket carries ~100-byte messages at a fixed cadence. No ordinary page does this."]

    if hars:
        lines += ["", "## Client side, per trial (HAR)", "",
                  "| trial | requests | bytes | mean resp KB | hosts | unfinished |", "|---|---|---|---|---|---|"]
        for stem, h in list(hars.items())[:40]:
            hosts = ", ".join(list(h["hosts"].keys())[:3])
            lines.append(f"| {stem} | {h['requests']} | {h['bytes']} | {h['mean_response_kbytes']} | {hosts} | {h['unfinished_requests']} |")

    if ws_events:
        lines += lines_ws
    if socks:
        long_lived = [e for e in socks if e["lifetime_s"] >= 5]
        by_peer: dict[str, list[dict]] = {}
        for e in long_lived:
            by_peer.setdefault(e["peer"], []).append(e)
        lines += ["", "## Client-side sockets: peers kept open for >= 5 s", "",
                  "| peer | trials seeing it | conditions | mean lifetime s | mean samples |", "|---|---|---|---|---|"]
        for peer, items in sorted(by_peer.items(), key=lambda kv: -len(kv[1]))[:15]:
            conds = sorted({i["cond"] for i in items})
            lines.append(f"| {peer} | {len(items)} | {', '.join(conds)[:40]} | "
                         f"{statistics.fmean(i['lifetime_s'] for i in items):.1f} | "
                         f"{statistics.fmean(i['ticks'] for i in items):.1f} |")
        if not long_lived:
            lines.append("| (none) | 0 | - | - | - |")
        lines += ["", "A loopback peer on the pool port that persists for the whole visit is the mining "
                      "signature; ordinary page peers disappear within a second or two."]

    if page:
        lines += ["", "## Socket table sampled inside the browser", "",
                  "| group | estab TCP mean | estab TCP p95 | uplink kbps | browser CPU % | har entries |",
                  "|---|---|---|---|---|---|"]
        for r in page:
            lines.append(f"| {r['group']} | {r['estab_tcp_mean']:.1f} | {r['estab_tcp_p95']:.1f} | "
                         f"{r['up_kbps_mean']:.1f} | {r['cpu_mean']:.1f} | {r['har_entries']:.0f} |")

    (OUT / "network_report.md").write_text("\n".join(lines), encoding="utf8")

    with open(OUT / "per_trial.csv", "w", newline="", encoding="utf8") as fh:
        cols = ["trial_tag", "sockets", "window_s", "frames", "bytes_up", "bytes_down", "up_kbps",
                "mean_frame_up", "shares", "shares_per_s", "mean_lifetime_s", "mean_share_interval_s"]
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for t in pool.get("per_trial", {}).values():
            w.writerow(t)

    with open(OUT / "flows.csv", "w", newline="", encoding="utf8") as fh:
        cols = ["conn_id", "trial_tag", "worker", "first_s", "last_s", "lifetime_s", "frames", "bytes_up", "bytes_down",
                "mean_frame_up", "mean_frame_down", "max_frame_up", "up_kbps", "down_kbps", "shares",
                "share_interval_mean_s", "share_interval_sd_s", "job_interval_mean_s", "total"]
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for s in pool["per_connection"].values():
            w.writerow(s)

    figures(pool, frames, http_log)
    print(f"wrote {OUT / 'network_report.md'}")
    print(f"wrote {OUT / 'network_profile.json'} and {OUT / 'flows.csv'}")
    print(f"pool connections: {agg['connections']}, frames: {len(frames)}, http requests: {http['requests']}")


def figures(pool: dict, frames: list[dict], http_log: list[dict]) -> None:
    if frames:
        ups = [f(r["frame_bytes"], 0) for r in frames if r["dir"] == "in"]
        downs = [f(r["frame_bytes"], 0) for r in frames if r["dir"] == "out"]
        fig, ax = plt.subplots(figsize=(7, 4))
        bins = np.arange(0, max(max(ups, default=10), max(downs, default=10)) + 40, 10)
        ax.hist(ups, bins=bins, alpha=.65, label=f"client->pool (n={len(ups)})", color="tab:red")
        ax.hist(downs, bins=bins, alpha=.65, label=f"pool->client (n={len(downs)})", color="tab:blue")
        if http_log:
            hb = [f(r["bytes_out"], 0) / 10 for r in http_log]
            ax.hist(hb, bins=np.arange(0, max(max(hb, default=10) + 40, 100), 10), alpha=.4,
                    label=f"HTTP response KB/10 (n={len(hb)})", color="tab:green")
        ax.set_xlabel("message size (bytes)")
        ax.set_ylabel("count")
        ax.set_title("Mining chatter is tens of bytes; page objects are kilobytes")
        ax.legend(fontsize=8)
        _save(fig, "fig_message_sizes")

        ts = np.array([f(r["elapsed_s"], 0) for r in frames])
        cid = np.array([r["conn_id"] for r in frames])
        kinds = np.array([r["msg_type"] or "?" for r in frames])
        unique_kinds = sorted(set(kinds))
        fig, ax = plt.subplots(figsize=(8, 1.6 + 0.7 * len(unique_kinds)))
        for i, k in enumerate(unique_kinds):
            sel = kinds == k
            ax.scatter(ts[sel], np.full(int(sel.sum()), i + 1), s=14, label=k, alpha=.8)
        ax.set_yticks(range(1, len(unique_kinds) + 1))
        ax.set_yticklabels(unique_kinds, fontsize=8)
        ax.set_xlabel("time since pool start (s)")
        ax.set_title("Pool message timeline: periodic jobs + shares, no bursts")
        ax.grid(alpha=.3)
        ax.legend(fontsize=7)
        _save(fig, "fig_pool_timeline")

    if pool["per_connection"]:
        fig, ax = plt.subplots(figsize=(7.5, 3.4))
        for i, s in enumerate(sorted(pool["per_connection"].values(), key=lambda x: int(x["conn_id"]))):
            ax.barh(i, s["lifetime_s"], left=s["first_s"], height=.6,
                    color="tab:red" if s["shares"] else "tab:orange")
            ax.text(s["first_s"] + s["lifetime_s"] + 0.3, i, f"{s['frames']} frames, {s['bytes_up']}B up",
                    va="center", fontsize=7)
        ax.set_yticks(range(len(pool["per_connection"])))
        ax.set_yticklabels([c["worker"][-18:] or c["conn_id"] for c in pool["per_connection"].values()], fontsize=7)
        ax.set_xlabel("seconds since pool start")
        ax.set_title("Long-lived mining sockets (one per browser worker)")
        fig.tight_layout()
        _save(fig, "fig_flow_lifetime")


def _save(fig, name: str) -> None:
    fig.savefig(OUT / f"{name}.tiff", dpi=DPI, format="tiff", pil_kwargs={"compression": "tiff_lzw"})
    fig.savefig(OUT / f"{name}.png", dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    main()
