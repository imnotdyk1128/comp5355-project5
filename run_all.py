"""One-command pipeline for Project 5.

  python run_all.py                 # standard lab experiment (~9 min)
  python run_all.py --profile quick # fast smoke run (~2 min)
  python run_all.py --profile long  # publication numbers (~40 min)
  python run_all.py --with-collect  # also crawl + statically scan the seed URLs
  python run_all.py --live          # measure the URLs in config/target_urls.txt instead

Steps: lab measurement -> resource analysis -> network analysis -> detector
evaluation -> combined summary in results/SUMMARY.md.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROFILES = {
    "quick": {"duration": 20, "trials": 1, "threads": "1,2"},
    "standard": {"duration": 30, "trials": 2, "threads": "1,2,4"},
    "long": {"duration": 90, "trials": 5, "threads": "1,2,4,8"},
}


def run(cmd: list[str]) -> int:
    print("\n$ " + " ".join(cmd), flush=True)
    return subprocess.call(cmd)


def collect(args) -> None:
    if run([sys.executable, str(HERE / "collect" / "crawl_pages.py"),
            "--urls", str(HERE / "config" / "target_urls.txt"),
            "--follow-external"]):
        print("crawl had failures (expected for offline hosts), continuing")
    run([sys.executable, str(HERE / "collect" / "scan_static.py")])


def measure(args, profile: dict) -> int:
    cmd = [sys.executable, str(HERE / "measure" / "measure.py"),
           "--mode", "live" if args.live else "lab",
           "--duration", str(args.duration or profile["duration"]),
           "--warmup", str(args.warmup),
           "--trials", str(args.trials or profile["trials"]),
           "--sample-ms", str(args.sample_ms)]
    if not args.live:
        cmd += ["--conditions", args.conditions, "--threads", args.threads or profile["threads"]]
    else:
        cmd += ["--urls", str(HERE / "config" / "target_urls.txt"), "--max-live", str(args.max_live)]
    if args.headed:
        cmd.append("--headed")
    if args.browser_exec:
        cmd += ["--browser-exec", args.browser_exec]
    return run(cmd)


def analyse() -> None:
    for script in ("analyze_resources.py", "analyze_network.py", "evaluate_detector.py"):
        run([sys.executable, str(HERE / "analyze" / script)])


def summary() -> None:
    res = {}
    paths = {
        "meta": HERE / "results" / "measure" / "meta.json",
        "detector": HERE / "results" / "analysis" / "detector" / "detector_summary.json",
        "network": HERE / "results" / "analysis" / "network" / "network_profile.json",
    }
    for k, p in paths.items():
        if p.exists():
            res[k] = json.loads(p.read_text(encoding="utf8"))

    lines = ["# Project 5 - characterising browser-based crypto mining: summary", ""]
    meta = res.get("meta", {})
    lines += [f"- captured {meta.get('captured_at', '?')} on {meta.get('platform', '?')}, "
              f"{meta.get('cpu_count_logical', '?')} logical cores, {meta.get('ram_total_gb', '?')} GB RAM, "
              f"{meta.get('browser', '?')} ({'headed' if meta.get('headed') else 'headless'})",
              f"- experiment: {meta.get('mode', 'lab')} mode, window {meta.get('duration_s')} s x "
              f"{meta.get('trials_per_condition')} trials, threads {meta.get('thread_sweep')}, "
              f"sample {meta.get('sample_ms')} ms", ""]

    det = res.get("detector", {})
    if det:
        lines += ["## Detection", "",
                  f"- windows evaluated: {det.get('n_windows')}, socket threshold {det.get('socket_threshold')}",
                  f"- CPU-only rule: {json.dumps(det.get('cpu_only'))}",
                  f"- CPU + sockets: {json.dumps(det.get('combined'))}",
                  f"- tuned, held-out trials: {json.dumps(det.get('best_held_out'))}", ""]

    pool = res.get("network", {}).get("pool", {}).get("aggregate", {})
    if pool:
        lines += ["## Network profile", "",
                  f"- mining sockets: {pool.get('connections')}, mean lifetime {pool.get('mean_lifetime_s')} s, "
                  f"{pool.get('mean_frames_per_conn')} frames each",
                  f"- message mix: {pool.get('message_mix')}",
                  f"- mean uplink per mining socket: {pool.get('mean_up_kbps')} kbps "
                  f"(total {pool.get('total_bytes')} bytes)", ""]

    lines += ["## Deliverable documents", "",
              "- results/analysis/resources/resource_table.md - with/without mining resource comparison",
              "- results/analysis/network/network_report.md - connection and message analysis",
              "- results/analysis/detector/detector_report.md - detector confusion matrices and thresholds",
              "- figures: results/analysis/*/fig_*.tiff (300 dpi) and .png previews",
              "- method notes and how to rerun: README.md"]
    out = HERE / "results" / "SUMMARY.md"
    out.write_text("\n".join(lines), encoding="utf8")
    print(f"wrote {out}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--profile", choices=sorted(PROFILES), default="standard")
    ap.add_argument("--conditions", default="clean,busy,mining")
    ap.add_argument("--threads", default="")
    ap.add_argument("--trials", type=int, default=0)
    ap.add_argument("--duration", type=float, default=0)
    ap.add_argument("--warmup", type=float, default=5.0)
    ap.add_argument("--sample-ms", type=int, default=250)
    ap.add_argument("--with-collect", action="store_true", help="crawl + static scan before measuring")
    ap.add_argument("--live", action="store_true", help="measure real URLs instead of the lab pages")
    ap.add_argument("--max-live", type=int, default=6)
    ap.add_argument("--headed", action="store_true")
    ap.add_argument("--browser-exec", default="")
    ap.add_argument("--skip-measure", action="store_true", help="re-run only the analysis on existing data")
    args = ap.parse_args()

    profile = PROFILES[args.profile]
    t0 = time.time()
    if args.with_collect:
        collect(args)
    if not args.skip_measure:
        if measure(args, profile) != 0:
            print("measurement returned non-zero; analysing whatever was recorded", flush=True)
    analyse()
    summary()
    print(f"\ndone in {time.time() - t0:.0f}s. Open results/SUMMARY.md")


if __name__ == "__main__":
    main()
