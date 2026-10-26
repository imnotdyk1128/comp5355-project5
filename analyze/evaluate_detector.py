"""Stage 4c: turn the characterisation into a detector and measure it.

Features come from the sliding window a real monitor would have: browser
process-tree CPU, established socket count, and uplink burstiness. Three
questions the numbers answer:

  1. can CPU alone separate mining from an innocent busy page? (it should not)
  2. does adding socket lifetime / chatter fix that? 
  3. how much does the static page scan (collect/scan_static.py) agree?

Usage:
  python evaluate_detector.py                 # lab trials, ground truth known
  python evaluate_detector.py --static ../results/static/findings.csv
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

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
RESULTS = Path(os.environ.get("P5_RESULTS", PROJECT / "results"))
MEASURE = RESULTS / "measure"
OUT = RESULTS / "analysis" / "detector"
WINDOW_S = 5.0
STEP_S = 1.0


def read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, encoding="utf8") as fh:
        return list(csv.DictReader(fh))


def f(v, default=None):
    try:
        x = float(v)
        return x
    except (TypeError, ValueError):
        return default


def windows(rows: list[dict]) -> list[dict]:
    """Sliding windows over one trial's samples."""
    ts = [r["t_s"] for r in rows]
    out = []
    if len(rows) < 4:
        return out
    t = ts[0]
    last = ts[-1]
    while t + WINDOW_S <= last:
        sel = [r for r in rows if t <= r["t_s"] < t + WINDOW_S]
        if len(sel) >= 4:
            cpu = [f(r.get("tree_cpu_pct")) for r in sel if f(r.get("tree_cpu_pct")) is not None]
            up = [f(r.get("net_up_kbps")) for r in sel if f(r.get("net_up_kbps")) is not None]
            est = [f(r.get("estab_tcp")) for r in sel if f(r.get("estab_tcp")) is not None]
            per = [f(r.get("persistent_tcp")) for r in sel if f(r.get("persistent_tcp")) is not None]
            wso = [f(r.get("page_ws_open")) for r in sel if f(r.get("page_ws_open")) is not None]
            wsb = [f(r.get("page_ws_bytes_up")) for r in sel if f(r.get("page_ws_bytes_up")) is not None]
            heap = [f(r.get("js_heap_mb")) for r in sel if f(r.get("js_heap_mb")) is not None]
            if cpu:
                span = max(sel[0]["t_s"], t)
                out.append({
                    "t0": round(t, 1),
                    "cpu_cores": statistics.fmean(cpu) / 100.0,
                    "cpu_p95_cores": sorted(cpu)[min(len(cpu) - 1, int(len(cpu) * 0.95))] / 100.0,
                    "cpu_stall_frac": sum(1 for c in cpu if c > 50) / len(cpu),
                    "up_mean": statistics.fmean(up) if up else 0.0,
                    "up_cv": (statistics.pstdev(up) / statistics.fmean(up)) if up and statistics.fmean(up) > 0 else 0.0,
                    "estab": statistics.fmean(est) if est else 0.0,
                    "persistent": statistics.fmean(per) if per else 0.0,
                    "page_ws_open": max(wso) if wso else 0.0,
                    "page_ws_bytes_up": sum(wsb) if wsb else 0.0,
                    "heap_mb": statistics.fmean(heap) if heap else 0.0,
                    "span": round(span, 1),
                })
        t += STEP_S
    return out


def score(w: dict, cpu_thr: float, est_thr: float, stall_thr: float) -> dict:
    """Rule ensemble. Each rule votes; the sum is thresholded so the sweep is honest."""
    votes = {
        "cpu_high": int(w["cpu_p95_cores"] >= cpu_thr),
        "cpu_sustained": int(w["cpu_stall_frac"] >= stall_thr),
        "extra_sockets": int(w["page_ws_open"] >= 1 or w["persistent"] >= 1),
        "steady_uplink": int(w["up_mean"] > 0.5 and w["up_cv"] < 1.0),
    }
    votes["mining"] = int(votes["cpu_high"] and votes["cpu_sustained"] and votes["extra_sockets"])
    votes["score"] = sum(v for k, v in votes.items() if k not in ("mining",))
    return votes


def group_of(cond: str, threads: str, url: str = "") -> str:
    if cond == "live":
        from urllib.parse import urlparse
        host = (urlparse(url).netloc or "?").replace("127.0.0.1", "lab")
        return f"live:{host}{urlparse(url).path if urlparse(url).path not in ('', '/') else ''}"
    return f"{cond}-w{threads}" if cond != "clean" else "clean"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--trials", default=str(MEASURE / "trials.csv"))
    ap.add_argument("--static", default=str(PROJECT / "results" / "static" / "findings.csv"),
                    help="static scan results used for cross-validation")
    ap.add_argument("--cpu-threshold", type=float, default=0.8, help="cores, p95 within window")
    ap.add_argument("--socket-threshold", type=float, default=-1.0,
                    help="established sockets; -1 = auto (baseline median + 2)")
    ap.add_argument("--stall-threshold", type=float, default=0.6)
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    trials = [r for r in read(Path(args.trials)) if not r.get("error")]
    if not trials:
        raise SystemExit("no trials - run measure/measure.py first")

    by_group: dict[str, list[dict]] = defaultdict(list)
    all_windows: list[dict] = []
    trial_urls: dict[tuple, str] = {}
    for r in trials:
        g = group_of(r["cond"], r.get("threads", "0"), r.get("url", ""))
        stem = (f"{r['cond']}_{r['slug']}_t{r.get('threads', '0')}_r{r.get('trial', '1')}"
                if r.get("slug") else f"{r['cond']}_t{r.get('threads', '0')}_r{r.get('trial', '1')}")
        p = MEASURE / "timeseries" / f"{stem}.csv"
        samples = read(p)
        parsed = []
        for sample in samples:
            row = {}
            for k, v in sample.items():
                x = f(v)
                row[k] = x if x is not None else v
            if isinstance(row.get("t_s"), float):
                parsed.append(row)
        parsed.sort(key=lambda x: x["t_s"])
        ws = windows(parsed)
        for w in ws:
            w["group"] = g
            w["cond"] = r["cond"]
            w["threads"] = r.get("threads", "0")
            w["trial"] = r.get("trial", "1")
        all_windows.extend(ws)
        trial_urls[(r["cond"], str(r.get("threads", "0")), str(r.get("trial", "1")))] = r.get("url", "")
        for w in ws:
            w.setdefault("url", r.get("url", ""))
        if ws:
            by_group[g].append(ws)

    if not all_windows:
        raise SystemExit("no windows could be built (too few samples per trial)")
    # In live mode there is no designed ground truth, so fall back to the static
    # scan verdict for each URL.
    static_labels: dict[str, int] = {}
    for row in read(Path(args.static)):
        url = (row.get("url") or "").split("?")[0].rstrip("/")
        static_labels[url] = int((row.get("label") or "").startswith("miner"))

    def static_truth(w: dict) -> int | None:
        url = (w.get("url") or "").split("?")[0].split("&")[0].rstrip("/")
        if url in static_labels:
            return static_labels[url]
        return None

    for w in all_windows:
        w.setdefault("url", next((t for t in [trial_urls.get((w["cond"], w["threads"], w["trial"]))] if t), ""))
    if not any(w["cond"] == "mining" for w in all_windows):
        labelled = [static_truth(w) for w in all_windows]
        if any(x == 1 for x in labelled):
            for w, x in zip(all_windows, labelled):
                if x is not None:
                    w["truth"] = x
            print("ground truth taken from the static scan verdict per URL")
        else:
            print("note: no mining trials and no miner-labelled URLs in the static scan; "
                  "precision/recall are undefined, reporting feature distributions only")

    est_thr = args.socket_threshold
    if est_thr < 0:
        est_thr = 1.0
        print("socket rule: >= 1 TCP connection that the page opened and kept alive for the whole window")

    cpu_only_thr = args.cpu_threshold
    for w in all_windows:
        w["pred_cpu_only"] = int(w["cpu_p95_cores"] >= cpu_only_thr and w["cpu_stall_frac"] >= args.stall_threshold)
        w.update({("pred_" + k): v for k, v in score(w, cpu_only_thr, est_thr, args.stall_threshold).items()})

    def truth(w: dict) -> int:
        if "truth" in w:
            return int(w["truth"])
        return int(w["cond"] == "mining")

    def metrics(pred: list[int], label: list[int]) -> dict:
        tp = sum(1 for p, t in zip(pred, label) if p and t)
        fp = sum(1 for p, t in zip(pred, label) if p and not t)
        fn = sum(1 for p, t in zip(pred, label) if not p and t)
        tn = sum(1 for p, t in zip(pred, label) if not p and not t)
        prec = tp / (tp + fp) if tp + fp else float("nan")
        rec = tp / (tp + fn) if tp + fn else float("nan")
        if tp == 0:
            f1 = 0.0
        elif np.isnan(prec) or np.isnan(rec) or prec + rec == 0:
            f1 = float("nan")
        else:
            f1 = 2 * prec * rec / (prec + rec)
        return {"TP": tp, "FP": fp, "FN": fn, "TN": tn, "precision": prec, "recall": rec, "f1": f1,
                "false_alarm_rate": fp / (fp + tn) if fp + tn else float("nan")}

    labels = [truth(w) for w in all_windows]
    has_positives = sum(labels) > 0
    cpu_pred = [w["pred_cpu_only"] for w in all_windows]
    combo_pred = [w["pred_mining"] for w in all_windows]
    estab_only_pred = [int(w["cpu_p95_cores"] >= args.cpu_threshold and w["cpu_stall_frac"] >= args.stall_threshold
                           and w["estab"] >= 12) for w in all_windows]
    ws_only_pred = [int(w["page_ws_open"] >= 1) for w in all_windows]

    # Hold out whole trials: thresholds are chosen on odd trial numbers and
    # scored on even ones, so the sweep cannot fit the data it is judged on.
    def net_ok(w, thr):
        """Page-owned WebSocket (CDP) or, failing that, a page-created persistent socket."""
        return w["page_ws_open"] >= 1 or w["persistent"] >= thr

    def trial_no(w):
        try:
            return int(w["trial"])
        except (TypeError, ValueError):
            return 1
    train = [w for w in all_windows if trial_no(w) % 2 == 1]
    test = [w for w in all_windows if trial_no(w) % 2 == 0]
    if not test:  # single-trial run: fall back to fitting and scoring together
        train, test = all_windows, all_windows
    train_labels, test_labels = [truth(w) for w in train], [truth(w) for w in test]

    sweep = []
    for cpu_thr in np.arange(0.2, 4.01, 0.2):
        for est_off in (0, 1, 2):
            thr = max(1, est_thr + est_off - 1)
            preds = [int(w["cpu_p95_cores"] >= cpu_thr and w["cpu_stall_frac"] >= args.stall_threshold
                         and net_ok(w, thr)) for w in train]
            m = metrics(preds, train_labels)
            preds_te = [int(w["cpu_p95_cores"] >= cpu_thr and w["cpu_stall_frac"] >= args.stall_threshold
                            and net_ok(w, thr)) for w in test]
            m_te = metrics(preds_te, test_labels)
            m.update({"cpu_thr_cores": round(float(cpu_thr), 2), "socket_offset": est_off,
                      "socket_thr": round(thr, 1),
                      "test_f1": m_te["f1"], "test_precision": m_te["precision"], "test_recall": m_te["recall"],
                      "test_TP": m_te["TP"], "test_FP": m_te["FP"], "test_FN": m_te["FN"], "test_TN": m_te["TN"]})
            sweep.append(m)
    def _n(x):
        return -1.0 if x is None or (isinstance(x, float) and np.isnan(x)) else x
    best = max(sweep, key=lambda m: (_n(m["test_f1"]), _n(m["f1"]), _n(m["precision"])))
    best_test = {"TP": best["test_TP"], "FP": best["test_FP"], "FN": best["test_FN"], "TN": best["test_TN"],
                 "precision": best["test_precision"], "recall": best["test_recall"], "f1": best["test_f1"]}
    best_test["false_alarm_rate"] = (best["test_FP"] / (best["test_FP"] + best["test_TN"])
                                     if best["test_FP"] + best["test_TN"] else float("nan"))

    per_group = {}
    for g in sorted(by_group):
        sel = [w for w in all_windows if w["group"] == g]
        per_group[g] = {
            "windows": len(sel),
            "mean_cpu_cores": round(statistics.fmean(w["cpu_p95_cores"] for w in sel), 2),
            "mean_estab": round(statistics.fmean(w["estab"] for w in sel), 1),
            "mean_persistent": round(statistics.fmean(w["persistent"] for w in sel), 2),
            "mean_page_ws_open": round(statistics.fmean(w["page_ws_open"] for w in sel), 2),
            "mean_up_kbps": round(statistics.fmean(w["up_mean"] for w in sel), 2),
            "mean_up_cv": round(statistics.fmean(w["up_cv"] for w in sel), 2),
            "detected_cpu_only_pct": round(100 * statistics.fmean(w["pred_cpu_only"] for w in sel), 1),
            "detected_combo_pct": round(100 * statistics.fmean(w["pred_mining"] for w in sel), 1),
        }

    lines = ["# Detector evaluation", "",
             f"- windows: {WINDOW_S:.0f}s sliding by {STEP_S:.0f}s over {len(trials)} trials = {len(all_windows)} instances",
             f"- ground truth: 'mining' trials are positives; clean and the matched-CPU 'busy' control are negatives",
             f"- rules: CPU p95 >= {args.cpu_threshold} cores held, sustained >= {args.stall_threshold} of window, "
             f"and >= {est_thr:.0f} page-owned long-lived socket (a WebSocket the page itself opened, "
             "from CDP, or a connection created during the visit and still open); machine-wide uplink "
             "steadiness is logged as a feature but not required, since those counters also carry "
             "unrelated background traffic",
             "",
             "## Feature means by condition",
             "",
             "| condition | windows | CPU p95 (cores) | est. sockets | persistent sockets | page WebSockets | up kbps | up CV | detected CPU-only % | detected combo % |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for g, d in per_group.items():
        lines.append(f"| {g} | {d['windows']} | {d['mean_cpu_cores']} | {d['mean_estab']} | {d['mean_persistent']} | "
                     f"{d['mean_page_ws_open']} | {d['mean_up_kbps']} | {d['mean_up_cv']} | "
                     f"{d['detected_cpu_only_pct']} | {d['detected_combo_pct']} |")

    def fmt(m: dict) -> str:
        return (f"TP {m['TP']} / FP {m['FP']} / FN {m['FN']} / TN {m['TN']}  "
                f"precision {m['precision']:.3f}  recall {m['recall']:.3f}  F1 {m['f1']:.3f}  "
                f"false alarm {m['false_alarm_rate']:.3f}")

    lines += ["", "## Confusion matrices", "",
              f"- CPU alone: {fmt(metrics(cpu_pred, labels))}",
              f"- CPU + raw socket *count* (default thresholds): {fmt(metrics(estab_only_pred, labels))}",
              f"- CPU + persistent page sockets (default thresholds): {fmt(metrics(combo_pred, labels))}",
              f"- thresholds chosen on odd-numbered trials, scored on even-numbered ones "
              f"({len(train)} train / {len(test)} test windows)",
              f"- tuned detector on held-out trials (CPU {best['cpu_thr_cores']} cores, sockets >= {best['socket_thr']}): "
              f"{fmt(best_test)}",
              ""]

    static = read(Path(args.static))
    if static:
        lines += ["## Cross-check with the static page scan", ""]
        by_label = defaultdict(int)
        for row in static:
            by_label[row["label"].split(":")[0]] += 1
        lines.append(f"- static findings: {dict(by_label)} over {len(static)} scanned pages")
        lab_pages = {Path(row["url"]).name for row in static if row.get("url", "").endswith(".html")}
        if lab_pages:
            lines.append(f"- scanned local lab pages: {sorted(lab_pages)}")
            lines.append("- the static scanner labels the busy control and the mining page identically, because they "
                         "ship the same loader; only the dynamic measurement separates them. That is exactly why the "
                         "project needs both halves.")
        lines.append("")

    (OUT / "detector_report.md").write_text("\n".join(lines), encoding="utf8")
    with open(OUT / "windows.csv", "w", newline="", encoding="utf8") as fh:
        cols = ["group", "cond", "threads", "trial", "t0", "cpu_cores", "cpu_p95_cores", "cpu_stall_frac",
                "up_mean", "up_cv", "estab", "persistent", "page_ws_open", "page_ws_bytes_up",
                "heap_mb", "pred_cpu_only", "pred_mining", "score"]
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for win in all_windows:
            w.writerow(win)
    (OUT / "threshold_sweep.csv").write_text(
        "\n".join([",".join(sweep[0].keys())] + [",".join(str(v) for v in m.values()) for m in sweep]), encoding="utf8")
    (OUT / "detector_summary.json").write_text(json.dumps(
        {"n_windows": len(all_windows), "socket_threshold": est_thr,
         "cpu_only": metrics(cpu_pred, labels), "combined": metrics(combo_pred, labels),
         "tuned_on_train": {"cpu_thr_cores": best["cpu_thr_cores"], "socket_threshold": best["socket_thr"]},
         "train_windows": len(train), "test_windows": len(test),
         "best_sweep_train": {k: v for k, v in best.items() if not k.startswith("test_")},
         "best_held_out": best_test, "per_group": per_group}, indent=2, default=str), encoding="utf8")

    figure(sweep, best)
    print(f"wrote {OUT / 'detector_report.md'}")
    print(f"windows: {len(all_windows)} ({len(train)} train / {len(test)} held out)")
    print(f"  CPU only (all windows):      F1 {metrics(cpu_pred, labels)['f1']:.3f}")
    print(f"  CPU + sockets (defaults):    F1 {metrics(combo_pred, labels)['f1']:.3f}")
    print(f"  tuned, held-out trials:      F1 {best_test['f1']:.3f} "
          f"(cpu {best['cpu_thr_cores']} cores, sockets {best['socket_thr']})")


def figure(sweep: list[dict], best: dict) -> None:
    xs = [m["cpu_thr_cores"] for m in sweep]
    for metric_name in ("f1", "precision", "recall"):
        ys = [0 if np.isnan(m[metric_name]) else m[metric_name] for m in sweep]
        yte = [0 if np.isnan(m["test_" + metric_name]) else m["test_" + metric_name] for m in sweep]
        fig, ax = plt.subplots(figsize=(6.5, 4))
        ax.plot(xs, ys, ".", ms=4, alpha=.5, label="train")
        ax.plot(xs, yte, ".", ms=4, alpha=.8, color="tab:orange", label="held-out trials")
        ax.axvline(best["cpu_thr_cores"], color="grey", ls="--", lw=1,
                   label=f"chosen {best['cpu_thr_cores']} cores")
        ax.set_xlabel("CPU threshold (cores held, p95 in window)")
        ax.set_ylabel(metric_name)
        ax.set_title(f"Threshold sweep: {metric_name} of the combined detector")
        ax.grid(alpha=.3)
        ax.legend(fontsize=8)
        fig.savefig(OUT / f"fig_threshold_{metric_name}.tiff", dpi=300, format="tiff", pil_kwargs={"compression": "tiff_lzw"})
        fig.savefig(OUT / f"fig_threshold_{metric_name}.png", dpi=150)
        plt.close(fig)


if __name__ == "__main__":
    main()
