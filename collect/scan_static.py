"""Stage 1b: static detection of in-browser miners in an archived corpus.

Three layers, following the content / code / currency split used in the
Project 5 readings (arXiv:1809.02152):

  1. named-platform indicators (Coinhive, CoinImp, JSEcoin, DeepBit, ...)
  2. generic behavioural indicators that survive renaming (worker + wasm +
     stratum-style messages), plus obfuscation metrics per script
  3. extracted indicators of compromise: pool endpoints (ws/wss), wallet
     addresses, miner script URLs

Usage:
  python scan_static.py                      # scan results/pages
  python scan_static.py --dir ../lab/web     # sanity check: our own lab pages
  python scan_static.py --corpus ../results/pages --min-score 3
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent

WEIGHTS = {"loader": 3.0, "api": 1.5, "pool": 2.0, "strong": 2.0, "weak": 0.5}
WS_URL = re.compile(r"""(?:wss?|https?)://[^\s'"`<>()]+""", re.I)


def shannon_entropy(text: str) -> float:
    if not text:
        return 0.0
    counts = Counter(text)
    n = len(text)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def code_features(text: str) -> dict:
    if not text:
        return {}
    lines = text.splitlines()
    longest = max((len(l) for l in lines), default=0)
    hex_escapes = len(re.findall(r"\\x[0-9a-fA-F]{2}", text))
    unicode_escapes = len(re.findall(r"\\u[0-9a-fA-F]{4}", text))
    strings = re.findall(r"""(['"`])(?:\\.|(?!\1)[^\\]){4,}\1""", text)
    literals = [s for s in re.findall(r"""(['"`])(?:\\.|(?!\1)[^\\])*\1""", text) if len(s) > 40]
    idents = re.findall(r"\b([A-Za-z_$][A-Za-z0-9_$]{18,})\b", text)
    counts = {
        "eval": len(re.findall(r"\beval\s*\(", text, re.I)),
        "function_ctor": len(re.findall(r"new\s+Function\s*\(", text, re.I)),
        "atob": len(re.findall(r"\batob\s*\(", text, re.I)),
        "from_char_code": len(re.findall(r"String\.fromCharCode", text)),
        "document_write": len(re.findall(r"document\.write", text, re.I)),
        "worker": len(re.findall(r"new\s+(?:Worker|SharedWorker)", text, re.I)),
        "object_url_blob": len(re.findall(r"createObjectURL\s*\(\s*new\s+Blob", text, re.I)),
        "webassembly": len(re.findall(r"WebAssembly\.(?:instantiate|compile)", text)),
        "websocket": len(re.findall(r"new\s+WebSocket", text, re.I)),
        "ws_urls": len(re.findall(r"wss?://", text, re.I)),
        "setinterval": len(re.findall(r"setInterval|requestAnimationFrame", text)),
    }
    return {
        "bytes": len(text.encode("utf8", errors="replace")),
        "lines": len(lines),
        "avg_line_len": round(len(text) / max(1, len(lines)), 1),
        "longest_line": longest,
        "minified": longest > 400,
        "hex_escapes": hex_escapes,
        "unicode_escapes": unicode_escapes,
        "escape_density": round((hex_escapes + unicode_escapes) / max(1, len(text)) * 1000, 2),
        "entropy": round(shannon_entropy(text), 3),
        "long_string_literals": len(literals),
        "long_identifiers": len(set(idents)),
        "counts_json": json.dumps(counts),
        **{f"c_{k}": v for k, v in counts.items()},
    }


def match_indicators(text_lower: str, indicators: list[str], name: str, fname: str, text: str) -> list[dict]:
    hits = []
    for ind in indicators:
        needle = ind.lower()
        pos = text_lower.find(needle)
        if pos >= 0:
            n = text_lower.count(needle)
            start = max(0, pos - 40)
            hits.append({
                "kind": name,
                "indicator": ind,
                "file": fname,
                "occurrences": n,
                "context": re.sub(r"\s+", " ", text[start:pos + len(ind) + 40])[:160],
            })
    return hits


def scan_file(path: Path, sigs: dict) -> dict:
    text = path.read_text(encoding="utf8", errors="replace")
    low = text.lower()
    out = {"file": path.name, "path": str(path), "features": code_features(text), "hits": []}
    for platform in sigs["platforms"]:
        for key, weight in (("loader_indicators", "loader"), ("api_indicators", "api"), ("pool_indicators", "pool")):
            for hit in match_indicators(low, platform.get(key, []), weight, path.name, text):
                hit["platform"] = platform["platform"]
                out["hits"].append(hit)
    generic = sigs["generic"]
    for key, weight in (("strong", "strong"), ("weak", "weak")):
        for hit in match_indicators(low, generic[key], weight, path.name, text):
            hit["platform"] = "generic"
            out["hits"].append(hit)
    out["iocs"] = extract_iocs(text, sigs)
    return out


def extract_iocs(text: str, sigs: dict) -> dict:
    urls = set()
    for m in WS_URL.finditer(text):
        u = m.group(0).rstrip(".,;)]}'\"")
        host = urlparse(u).netloc.lower()
        if host and ("pool" in host or "min" in host or "coin" in host or "mine" in host
                     or urlparse(u).scheme in ("ws", "wss") or ":" in host):
            urls.add(u[:200])
    wallets = {}
    for name, pattern in sigs.get("wallet_patterns", {}).items():
        found = set(re.findall(pattern, text))
        if found:
            wallets[name] = sorted(found)[:5]
    return {"endpoints": sorted(urls)[:20], "wallets": wallets}


def score_and_label(files: list[dict]) -> tuple[float, str, list[str]]:
    platforms = Counter()
    score = 0.0
    reasons = []
    for f in files:
        for hit in f["hits"]:
            w = WEIGHTS[hit["kind"]] * (1 + 0.1 * min(9, hit["occurrences"] - 1))
            score += w
            if hit["platform"] != "generic":
                platforms[hit["platform"]] += w
    feat = {"worker": sum(f["features"].get("c_worker", 0) for f in files),
            "webassembly": sum(f["features"].get("c_webassembly", 0) for f in files),
            "websocket": sum(f["features"].get("c_websocket", 0) for f in files),
            "eval": sum(f["features"].get("c_eval", 0) for f in files),
            "atob": sum(f["features"].get("c_atob", 0) for f in files)}
    strong_generic = sum(1 for f in files for h in f["hits"] if h["kind"] == "strong")
    if platforms:
        label = "miner:" + ", ".join(p for p, _ in platforms.most_common(3))
    elif strong_generic >= 2 and feat["worker"] and feat["websocket"]:
        label = "miner_candidate"
    elif strong_generic >= 2 or (strong_generic >= 1 and feat["worker"] and feat["webassembly"]
                                 and feat["websocket"]):
        # worker + wasm + websocket alone is what an ordinary analytics or chart
        # script looks like; a mining token has to appear as well
        label = "miner_candidate"
    elif score >= 2.0:
        label = "suspicious"
    else:
        label = "clean"
    if feat["worker"] and feat["webassembly"]:
        reasons.append("dedicated worker instantiates WebAssembly")
    if strong_generic:
        reasons.append(f"{strong_generic} generic mining token(s) matched")
    if feat["atob"] + feat["eval"] >= 3:
        reasons.append("decoding/eval heavy script")
    for p, s in platforms.most_common(3):
        reasons.append(f"platform {p} score {s:.1f}")
    return round(score, 2), label, reasons


def load_corpus(args) -> list[tuple[str, list[Path]]]:
    root = Path(args.dir) if (args.dir or args.per_file) else Path(args.corpus)
    if args.per_file:
        # one unit per artefact: how the collect/samples fixtures get validated
        return [(str(f), [f]) for f in sorted(root.rglob("*"))
                if f.is_file() and f.suffix.lower() in (".html", ".htm", ".js")]
    if args.dir:
        all_js = {p.name: p for p in sorted(root.rglob("*.js"))}
        referenced: set[Path] = set()
        pages = []
        for html in sorted(root.rglob("*.html")):
            files = [html]
            text = html.read_text(encoding="utf8", errors="replace")
            for src in re.findall(r"""<script[^>]+src\s*=\s*["']([^"']+)["']""", text, re.I):
                name = src.split("/")[-1].split("?")[0]
                if src.startswith("http"):
                    continue
                picked = None
                for cand in (root / src.lstrip("/"), html.parent / src):
                    if cand.is_file():
                        picked = cand
                        break
                if picked is None and name in all_js:
                    picked = all_js[name]
                if picked is not None and picked not in files:
                    files.append(picked)
            pages.append((str(html), files))
            for f in files:
                referenced.add(f)
        # unreferenced scripts are scanned as their own unit, which is what makes
        # the collect/samples fixtures test per-artifact behaviour
        for name, js in all_js.items():
            if js not in referenced:
                pages.append((str(js), [js]))
        return pages
    manifest = root / "manifest.csv"
    if not manifest.exists():
        raise SystemExit(f"{manifest} not found - run crawl_pages.py first, or pass --dir")
    pages = []
    for row in csv.DictReader(open(manifest, encoding="utf8")):
        files: list[Path] = []
        if row.get("html_file"):
            p = root / row["html_file"]
            if p.is_file():
                files.append(p)
        d = root / row["page_id"] / "scripts"
        if d.is_dir():
            files.extend(sorted(d.glob("*.js")))
        pages.append((row["requested_url"], files))
    return pages


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus", default=str(PROJECT / "results" / "pages"))
    ap.add_argument("--dir", default="", help="scan an arbitrary folder of html/js instead of the corpus")
    ap.add_argument("--per-file", action="store_true", help="with --dir: score each file separately")
    ap.add_argument("--signatures", default=str(PROJECT / "config" / "miner_signatures.json"))
    ap.add_argument("--out", default=str(PROJECT / "results" / "static"))
    ap.add_argument("--min-score", type=float, default=0.0, help="only report pages scoring at least this")
    args = ap.parse_args()

    sigs = json.loads(Path(args.signatures).read_text(encoding="utf8"))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    rows = []
    for url, files in load_corpus(args):
        scanned = [scan_file(f, sigs) for f in files if f.is_file()]
        score, label, reasons = score_and_label(scanned)
        endpoints = sorted({u for s in scanned for u in s["iocs"]["endpoints"]})
        wallets = {}
        for s in scanned:
            for k, v in s["iocs"]["wallets"].items():
                wallets.setdefault(k, []).extend(v)
        if score < args.min_score:
            continue
        pid = re.sub(r"\W+", "_", url)[-60:] or "page"
        evidence = {"url": url, "score": score, "label": label, "reasons": reasons,
                    "endpoints": endpoints, "wallets": {k: sorted(set(v))[:5] for k, v in wallets.items()},
                    "files": [{k: v for k, v in s.items() if k != "path"} for s in scanned]}
        (out / f"evidence_{pid[:48]}.json").write_text(json.dumps(evidence, indent=2, default=str), encoding="utf8")
        best_file = max(scanned, key=lambda s: sum(WEIGHTS[h["kind"]] for h in s["hits"]), default=None)
        rows.append({
            "url": url, "label": label, "score": score,
            "platforms": "; ".join(sorted({h["platform"] for s in scanned for h in s["hits"] if h["platform"] != "generic"})),
            "n_files": len(scanned),
            "html_bytes": sum(s["features"].get("bytes", 0) for s in scanned if s["file"] == "document.html"),
            "js_bytes": sum(s["features"].get("bytes", 0) for s in scanned if s["file"].endswith(".js")),
            "workers": sum(s["features"].get("c_worker", 0) for s in scanned),
            "webassembly": sum(s["features"].get("c_webassembly", 0) for s in scanned),
            "websockets": sum(s["features"].get("c_websocket", 0) for s in scanned),
            "eval_calls": sum(s["features"].get("c_eval", 0) for s in scanned),
            "atob_calls": sum(s["features"].get("c_atob", 0) for s in scanned),
            "max_entropy": max([s["features"].get("entropy", 0) for s in scanned] or [0]),
            "minified": any(s["features"].get("minified") for s in scanned),
            "n_strong_hits": sum(1 for s in scanned for h in s["hits"] if h["kind"] == "strong"),
            "endpoints": " | ".join(endpoints[:5]),
            "wallets": " | ".join(f"{k}:{v[0][:16]}.." for k, v in wallets.items()),
            "top_indicator": (best_file or {"hits": [{}]} )["hits"][0].get("indicator", "") if best_file and best_file["hits"] else "",
            "evidence_file": f"evidence_{pid[:48]}.json",
        })

    rows.sort(key=lambda r: -r["score"])
    findings = out / "findings.csv"
    with open(findings, "w", newline="", encoding="utf8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()) if rows else ["url"])
        w.writeheader()
        for r in rows:
            w.writerow(r)

    labels = Counter(r["label"] for r in rows)
    print(f"scanned {len(rows)} pages -> {findings}")
    for label, n in labels.most_common():
        print(f"  {n:4d}  {label}")
    positives = [r for r in rows if r["label"].startswith("miner")]
    print(f"\nminer positives: {len(positives)}")
    for r in positives[:10]:
        print(f"  score={r['score']:<6} {r['url'][:70]}  [{r['platforms'] or r['label']}]")


if __name__ == "__main__":
    main()
