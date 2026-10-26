"""Stage 4a: compare resource profiles with and without browser mining.

Reads results/measure/trials.csv (one row per trial) plus the per-sample
time series, and produces:

  results/analysis/resources/resource_table.md   human-readable summary
  results/analysis/resources/resource_stats.csv  every statistic, machine-readable
  results/analysis/resources/fig_*.tiff|png      300 dpi figures

Usage:
  python analyze_resources.py
  python analyze_resources.py --baseline clean --alpha 0.01
"""

from __future__ import annotations

import argparse
import os
import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy import stats as sps

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
RESULTS = Path(os.environ.get("P5_RESULTS", PROJECT / "results"))
MEASURE = RESULTS / "measure"
OUT = RESULTS / "analysis" / "resources"

# (column prefix, display name, unit)
METRICS = [
    ("tree_cpu_pct", "browser CPU (sum of cores)", "%"),
    ("tree_cpu_machine_pct", "browser CPU (% of machine)", "%"),
    ("tree_rss_mb", "browser RSS", "MB"),
    ("js_heap_mb", "page JS heap", "MB"),
    ("script_pct_core", "main-thread JS time", "% of core"),
    ("net_up_kbps", "uplink throughput", "kbps"),
    ("net_down_kbps", "downlink throughput", "kbps"),
    ("estab_tcp", "established TCP sockets", "count"),
    ("page_ws_open", "page-owned WebSockets open", "count"),
    ("page_ws_bytes_up", "pool bytes sent by the page", "B/sample"),
    ("persistent_tcp", "persistent sockets created by the page", "count"),
    ("tcp_created_by_page", "sockets created during the visit", "count"),
    ("lab_hashrate_hps", "hashrate (ground truth)", "H/s"),
    ("lab_shares", "shares submitted (cumulative)", "count"),
    ("lab_ws_bytes_out", "pool bytes sent (cumulative)", "B"),
]


def read_trials() -> list[dict]:
    path = MEASURE / "trials.csv"
    if not path.exists():
        raise SystemExit(f"{path} missing - run measure/measure.py first")
    rows = []
    for r in csv.DictReader(open(path, encoding="utf8")):
        if r.get("error"):
            continue
        rows.append(r)
    if not rows:
        raise SystemExit("no successful trials in trials.csv")
    return rows


def group_key(row: dict) -> str:
    if row["cond"] == "live":
        # live mode measures arbitrary URLs; group by site, not by the dummy label
        from urllib.parse import urlparse
        return "live:" + (urlparse(row.get("url", "")).netloc or "?").replace("127.0.0.1", "lab")
    t = row.get("threads") or "0"
    return f"{row['cond']}{'' if row['cond'] == 'clean' or t == '0' else '-w' + t}"


def num(row: dict, col: str) -> float | None:
    v = row.get(col)
    if v in (None, "", "None"):
        return None
    try:
        return float(v)
    except ValueError:
        return None


def sample_column(groups: dict, key: str, col: str) -> list[float]:
    """All per-sample values of `col` across every trial in a group.

    Sample-level testing gives usable power (n is in the hundreds), but samples
    are autocorrelated; the trial-level means are reported alongside.
    """
    vals: list[float] = []
    for r in groups[key]:
        for row in load_series(r["cond"], str(r.get("threads") or "0"), str(r.get("trial") or "1")):
            v = row.get(col)
            if isinstance(v, (int, float)):
                vals.append(float(v))
    return vals


def load_series(cond: str, threads: str, trial: str, slug: str = "") -> list[dict]:
    stem = f"{cond}_{slug}_t{threads}_r{trial}" if slug else f"{cond}_t{threads}_r{trial}"
    p = MEASURE / "timeseries" / f"{stem}.csv"
    if not p.exists():
        return []
    rows = []
    for r in csv.DictReader(open(p, encoding="utf8")):
        rows.append({k: (float(v) if v not in ("", None) and _isnum(v) else v) for k, v in r.items()})
    return rows


def _isnum(v) -> bool:
    try:
        float(v)
        return True
    except (TypeError, ValueError):
        return False


def describe(values: list[float]) -> dict:
    values = [v for v in values if v is not None]
    if not values:
        return {}
    out = {"n": len(values), "mean": statistics.fmean(values), "median": statistics.median(values),
           "sd": statistics.pstdev(values) if len(values) > 1 else 0.0,
           "min": min(values), "max": max(values)}
    out["p95"] = sorted(values)[min(len(values) - 1, int(len(values) * 0.95))]
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--baseline", default="clean", help="condition used as the no-mining reference")
    ap.add_argument("--alpha", type=float, default=0.05)
    ap.add_argument("--dpi", type=int, default=300)
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    rows = read_trials()
    meta = {}
    meta_path = MEASURE / "meta.json"
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf8"))

    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        groups[group_key(r)].append(r)

    baseline_key = next((k for k in groups if k.startswith(args.baseline)), None)
    if baseline_key is None:
        # live-mode runs have no lab control page; use the quietest group instead
        baseline_key = min(groups, key=lambda k: statistics.fmean(
            [num(r, "tree_cpu_pct_mean") or 0 for r in groups[k]]))
        print(f"note: baseline '{args.baseline}' absent; using the quietest group '{baseline_key}' as reference")

    stats_rows: list[dict] = []
    table_lines = [
        f"# Resource profile: with vs without browser-based mining",
        "",
        f"- platform: {meta.get('platform', 'n/a')}, {meta.get('cpu_count_logical', '?')} logical cores, "
        f"{meta.get('ram_total_gb', '?')} GB RAM",
        f"- browser: {meta.get('browser', 'n/a')} ({'headed' if meta.get('headed') else 'headless'}), "
        f"sample interval {meta.get('sample_ms', '?')} ms, window {meta.get('duration_s', '?')} s, "
        f"{meta.get('trials_per_condition', '?')} trials per condition",
        f"- captured: {meta.get('captured_at', 'n/a')}",
        "",
    ]

    for key in sorted(groups, key=lambda k: (not k.startswith(args.baseline), k)):
        g = groups[key]
        table_lines.append(f"## {key}  ({len(g)} trial{'s' if len(g) != 1 else ''})")
        table_lines.append("")
        table_lines.append("| metric | mean | median | sd | p95 | max | vs baseline (Welch p, Mann-Whitney p, Cohen d) |")
        table_lines.append("|---|---|---|---|---|---|---|")
        for col, label, unit in METRICS:
            vals = [num(r, col + "_mean") for r in g]
            vals = [v for v in vals if v is not None]
            if not vals:
                continue
            d = describe(vals)
            cell = ""
            if key != baseline_key:
                base_trials = [num(r, col + "_mean") for r in groups[baseline_key]]
                base_trials = [v for v in base_trials if v is not None]
                a = sample_column(groups, key, col)
                b = sample_column(groups, baseline_key, col)
                if len(a) > 2 and len(b) > 2 and statistics.fmean(a) != statistics.fmean(b):
                    try:
                        t_p = sps.ttest_ind(a, b, equal_var=False).pvalue
                    except Exception:
                        t_p = float("nan")
                    try:
                        u_p = sps.mannwhitneyu(a, b, alternative="two-sided").pvalue
                    except Exception:
                        u_p = float("nan")
                    pooled = statistics.pstdev(a + b) or 0.0
                    cd = (statistics.fmean(a) - statistics.fmean(b)) / pooled if pooled else float("nan")
                    ratio = statistics.fmean(a) / statistics.fmean(b) if statistics.fmean(b) else float("inf")
                    flag = "*" if min(t_p, u_p) < args.alpha else ""
                    cell = f"p={t_p:.3g}/{u_p:.3g}{flag}, d={cd:.2f}, x{ratio:.2f} (n={len(a)}/{len(b)})"
                    stats_rows.append({"group": key, "metric": col, "sample_mean": statistics.fmean(a),
                                       "sample_sd": statistics.pstdev(a), "n_samples": len(a),
                                       "baseline_sample_mean": statistics.fmean(b), "baseline_n": len(b),
                                       "trial_mean": d["mean"], "trial_sd": d["sd"],
                                       "welch_p": t_p, "mannwhitney_p": u_p, "cohens_d": cd, "ratio": ratio})
                else:
                    cell = "-"
            table_lines.append(f"| {label} ({unit}) | {d['mean']:.2f} | {d['median']:.2f} | {d['sd']:.2f} | "
                               f"{d['p95']:.2f} | {d['max']:.2f} | {cell} |")
        table_lines.append("")

    # how many cores each worker actually pins
    scaling = []
    for key, g in sorted(groups.items()):
        if key.startswith(args.baseline):
            continue
        for r in g:
            threads = float(r.get("threads") or 0)
            cpu = num(r, "tree_cpu_pct_mean")
            rate = num(r, "lab_hashrate_hps_mean")
            if cpu is None or not threads:
                continue
            scaling.append({"group": key, "threads": threads, "cores_used": cpu / 100.0,
                            "cores_per_thread": cpu / 100.0 / threads,
                            "hashes_per_s_per_thread": (rate or 0) / threads})
    if scaling:
        table_lines.append("## Scaling with worker count")
        table_lines.append("")
        table_lines.append("| condition | threads | cores held busy | cores per thread | H/s per thread |")
        table_lines.append("|---|---|---|---|---|")
        for s in sorted(scaling, key=lambda x: (x["group"], x["threads"])):
            table_lines.append(f"| {s['group']} | {s['threads']:.0f} | {s['cores_used']:.2f} | "
                               f"{s['cores_per_thread']:.2f} | {s['hashes_per_s_per_thread']:.3g} |")
        table_lines.append("")

    # mining vs the matched-CPU control: what the pool traffic adds
    mining_keys = [k for k in groups if k.startswith("mining")]
    busy_keys = [k for k in groups if k.startswith("busy")]
    if mining_keys and busy_keys:
        table_lines.append("## Mining vs matched-CPU control (same workers, no pool)")
        table_lines.append("")
        table_lines.append("| threads | CPU% mining | CPU% busy | page WebSockets (mining vs busy) | "
                           "machine uplink kbps delta (noise) | shares/s |")
        table_lines.append("|---|---|---|---|---|---|")
        for bk in sorted(busy_keys):
            t = bk.split("-w")[-1]
            mk = f"mining-w{t}"
            if mk not in groups:
                continue
            mb, bb = groups[mk], groups[bk]
            cpu_m = statistics.fmean([num(r, "tree_cpu_pct_mean") for r in mb if num(r, "tree_cpu_pct_mean") is not None])
            cpu_b = statistics.fmean([num(r, "tree_cpu_pct_mean") for r in bb if num(r, "tree_cpu_pct_mean") is not None])
            est_m = statistics.fmean([num(r, "page_ws_open_mean") if num(r, "page_ws_open_mean") is not None
                                      else num(r, "estab_tcp_mean") or 0 for r in mb])
            est_b = statistics.fmean([num(r, "page_ws_open_mean") if num(r, "page_ws_open_mean") is not None
                                      else num(r, "estab_tcp_mean") or 0 for r in bb])
            up_m = statistics.fmean([num(r, "net_up_kbps_mean") or 0 for r in mb])
            up_b = statistics.fmean([num(r, "net_up_kbps_mean") or 0 for r in bb])
            dur = float(meta.get("duration_s") or 1)
            sh = statistics.fmean([num(r, "lab_shares_max") or 0 for r in mb]) / dur
            table_lines.append(f"| {t} | {cpu_m:.1f} | {cpu_b:.1f} | {est_m - est_b:+.1f} | {up_m - up_b:+.2f} | {sh:.2f} |")
        table_lines.append("")

    (OUT / "resource_table.md").write_text("\n".join(table_lines), encoding="utf8")
    if stats_rows:
        with open(OUT / "resource_stats.csv", "w", newline="", encoding="utf8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(stats_rows[0].keys()))
            w.writeheader()
            w.writerows(stats_rows)

    make_figures(groups, meta, args.dpi)
    print(f"wrote {OUT / 'resource_table.md'}")
    print(f"wrote {OUT / 'resource_stats.csv'}" if stats_rows else "no comparative statistics available")
    print(f"figures: {OUT}")


def make_figures(groups: dict, meta: dict, dpi: int) -> None:
    keys = sorted(groups)
    if not keys:
        return
    colors = plt.get_cmap("tab10")

    # figure 1: CPU time series, one representative trial per group
    series = {}
    for k in keys:
        r0 = groups[k][0]
        s = load_series(r0["cond"], str(r0.get("threads") or "0"), str(r0.get("trial") or "1"),
                        r0.get("slug", ""))
        if s:
            series[k] = s
    if series:
        fig, ax = plt.subplots(figsize=(8, 4.2))
        for i, (k, s) in enumerate(series.items()):
            t = [r["t_s"] for r in s]
            ax.plot(t, [r.get("tree_cpu_pct", 0) for r in s], label=k, color=colors(i % 10), lw=1.2)
        ax.set_xlabel("time since navigation start (s)")
        ax.set_ylabel("browser process-tree CPU (% of one core)")
        ax.set_title("CPU signature: idle page vs CPU-only control vs in-browser mining")
        ax.legend(fontsize=8)
        ax.grid(alpha=.3)
        _save(fig, "fig_cpu_timeseries", dpi)

    # figure 2: box plot of CPU per group
    pairs = [(k, [num(r, "tree_cpu_pct_mean") for r in groups[k]
                  if num(r, "tree_cpu_pct_mean") is not None]) for k in keys]
    pairs = [(k, d) for k, d in pairs if d]
    if pairs:
        keys = [k for k, _ in pairs]
        data = [d for _, d in pairs]
        fig, ax = plt.subplots(figsize=(7, 4))
        try:
            ax.boxplot(data, tick_labels=keys, showfliers=False)
        except TypeError:
            ax.boxplot(data, labels=keys, showfliers=False)
        ax.set_ylabel("browser CPU per trial (% of one core)")
        ax.set_title("Distribution of CPU load by condition")
        ax.grid(alpha=.3)
        _save(fig, "fig_cpu_boxplot", dpi)

    # figure 3: memory and network side by side
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.8))
    rss = [statistics.fmean([num(r, "tree_rss_mb_mean") or 0 for r in groups[k]]) for k in keys]
    net = [statistics.fmean([num(r, "net_up_kbps_mean") or 0 for r in groups[k]]) for k in keys]
    axes[0].bar(keys, rss, color=[colors(i % 10) for i in range(len(keys))])
    axes[0].set_ylabel("mean RSS (MB)")
    axes[0].set_title("Memory")
    axes[0].tick_params(axis="x", rotation=45, labelsize=7)
    axes[1].bar(keys, net, color=[colors(i % 10) for i in range(len(keys))])
    axes[1].set_ylabel("mean uplink (kbps)")
    axes[1].set_title("Network throughput")
    axes[1].tick_params(axis="x", rotation=45, labelsize=7)
    fig.tight_layout()
    _save(fig, "fig_memory_network", dpi)

    # figure 4: CPU vs uplink scatter - the classifier's feature space
    pts = []
    for k, g in groups.items():
        for r in g:
            x, y = num(r, "tree_cpu_pct_mean"), num(r, "net_up_kbps_mean")
            if x is not None and y is not None:
                pts.append((x, y, k))
    if pts:
        fig, ax = plt.subplots(figsize=(6.5, 4.5))
        for i, k in enumerate(keys):
            sub = [(x, y) for x, y, kk in pts if kk == k]
            if sub:
                ax.scatter([p[0] for p in sub], [p[1] for p in sub], label=k, color=colors(i % 10), s=28)
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xlabel("browser CPU (% of one core, log)")
        ax.set_ylabel("uplink throughput (kbps, log)")
        ax.set_title("CPU scales with worker count; machine-wide throughput "
                     "does not identify mining (see page WebSocket count instead)")
        ax.legend(fontsize=8)
        ax.grid(alpha=.3, which="both")
        _save(fig, "fig_feature_space", dpi)


def _save(fig, name: str, dpi: int) -> None:
    fig.savefig(OUT / f"{name}.tiff", dpi=dpi, format="tiff", pil_kwargs={"compression": "tiff_lzw"})
    fig.savefig(OUT / f"{name}.png", dpi=min(dpi, 150))
    plt.close(fig)


if __name__ == "__main__":
    main()
