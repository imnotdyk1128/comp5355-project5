"""Stage 1a: build a corpus of web pages to inspect for in-browser mining.

Fetches each URL, stores the HTML, then follows <script src> links so the
JavaScript (where miners actually live) is archived too. Everything is written
under results/pages with a manifest so scan_static.py can work offline.

Usage:
  python crawl_pages.py --urls ../config/target_urls.txt
  python crawl_pages.py --url https://example.com --out ../../results/pages
  python crawl_pages.py --ingest-dir D:/corpus/html   # archive existing files, no network

Network failures are expected (many historical mining hosts are offline); they
are recorded in the manifest instead of aborting the run.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

SCRIPT_SRC = re.compile(r"""<script[^>]+src\s*=\s*["']([^"']+)["']""", re.I)
MAX_HTML_BYTES = 3_000_000
MAX_JS_BYTES = 2_000_000


def page_id(url: str) -> str:
    return hashlib.sha1(url.encode()).hexdigest()[:16]


def read_urls(path: Path) -> list[str]:
    urls = []
    for line in path.read_text(encoding="utf8", errors="replace").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            urls.append(line.split(",")[0].strip() if "," in line else line)
    return urls


def slug(url: str) -> str:
    p = urlparse(url)
    return (p.netloc or "local").replace(":", "_") + p.path.replace("/", "_")[:60]


def fetch(session: requests.Session, url: str, timeout: float, cap: int) -> tuple[bytes | None, dict]:
    info = {"final_url": url, "status": None, "error": "", "bytes": 0, "content_type": ""}
    try:
        r = session.get(url, timeout=timeout, allow_redirects=True, stream=True)
        info["final_url"] = r.url
        info["status"] = r.status_code
        info["content_type"] = r.headers.get("Content-Type", "")
        body = r.raw.read(cap + 1, decode_content=True)
        info["bytes"] = len(body)
        if len(body) > cap:
            info["error"] = "truncated"
        return body, info
    except requests.RequestException as exc:
        info["error"] = f"{type(exc).__name__}: {exc}"[:200]
        return None, info


def crawl(url: str, session: requests.Session, out: Path, args) -> dict:
    pid = page_id(url)
    html, info = fetch(session, url, args.timeout, MAX_HTML_BYTES)
    row = {
        "page_id": pid,
        "requested_url": url,
        "final_url": info["final_url"],
        "http_status": info["status"],
        "html_bytes": info["bytes"],
        "content_type": info["content_type"],
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "n_scripts": 0,
        "js_bytes": 0,
        "js_fetched": 0,
        "js_failed": 0,
        "error": info["error"],
        "html_file": "",
        "script_index": "",
    }
    if html is None:
        return row

    d = out / pid
    d.mkdir(parents=True, exist_ok=True)
    html_file = d / "document.html"
    html_file.write_bytes(html)
    row["html_file"] = str(html_file.relative_to(out))

    text = html.decode("utf-8", errors="replace")
    srcs: list[str] = []
    try:
        soup = BeautifulSoup(text, "html.parser")
        for s in soup.find_all("script", src=True):
            srcs.append(s["src"])
    except Exception:
        pass
    srcs += [m for m in SCRIPT_SRC.findall(text) if m not in srcs]
    srcs = [s for s in srcs if not s.startswith("data:")][: args.max_scripts]

    index = []
    js_dir = d / "scripts"
    js_dir.mkdir(exist_ok=True)
    for src in srcs:
        absolute = urljoin(row["final_url"], src)
        if not absolute.startswith(("http://", "https://")):
            continue
        same_host = urlparse(absolute).netloc == urlparse(row["final_url"]).netloc
        if not same_host and not args.follow_external:
            index.append({"src": src, "url": absolute, "same_host": False, "skipped": True})
            continue
        jbytes, jinfo = fetch(session, absolute, args.timeout, MAX_JS_BYTES)
        entry = {"src": src, "url": absolute, "same_host": same_host, "status": jinfo["status"],
                 "bytes": jinfo["bytes"], "error": jinfo["error"]}
        if jbytes is not None:
            name = f"{page_id(absolute)}.js"
            (js_dir / name).write_bytes(jbytes)
            entry["file"] = str((js_dir / name).relative_to(out))
            row["js_bytes"] += jinfo["bytes"]
            row["js_fetched"] += 1
        else:
            row["js_failed"] += 1
        index.append(entry)
        if args.sleep:
            time.sleep(args.sleep)

    row["n_scripts"] = len(srcs)
    idx_file = d / "scripts.json"
    idx_file.write_text(json.dumps(index, indent=2), encoding="utf8")
    row["script_index"] = str(idx_file.relative_to(out))
    return row


def ingest_dir(src_dir: Path, out: Path, args) -> list[dict]:
    """Archive an existing corpus (e.g. pages saved inside the VM) without network."""
    rows = []
    for f in sorted(src_dir.rglob("*")):
        if not f.is_file() or f.suffix.lower() not in (".html", ".htm", ".js"):
            continue
        if args.max_files and len(rows) >= args.max_files:
            break
        pid = page_id(str(f))
        d = out / pid
        d.mkdir(parents=True, exist_ok=True)
        target = d / ("document.html" if f.suffix.lower() in (".html", ".htm") else f.stem + ".js")
        shutil.copyfile(f, target)
        rows.append({
            "page_id": pid, "requested_url": f.as_uri(), "final_url": f.as_uri(),
            "http_status": "local", "html_bytes": f.stat().st_size if target.name == "document.html" else 0,
            "content_type": "local/file", "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "n_scripts": 0, "js_bytes": 0 if target.name == "document.html" else f.stat().st_size,
            "js_fetched": 0 if target.name == "document.html" else 1, "js_failed": 0,
            "error": "", "html_file": str(target.relative_to(out)), "script_index": "",
        })
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--urls", default=str(PROJECT / "config" / "target_urls.txt"))
    ap.add_argument("--url", action="append", default=[], help="ad-hoc URL, repeatable")
    ap.add_argument("--out", default=str(PROJECT / "results" / "pages"))
    ap.add_argument("--ingest-dir", default="", help="archive a local folder instead of crawling")
    ap.add_argument("--max-scripts", type=int, default=25)
    ap.add_argument("--follow-external", action="store_true", help="also fetch third-party script hosts")
    ap.add_argument("--timeout", type=float, default=15.0)
    ap.add_argument("--sleep", type=float, default=0.3)
    ap.add_argument("--max-files", type=int, default=500, help="cap for --ingest-dir")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    if args.ingest_dir:
        rows = ingest_dir(Path(args.ingest_dir), out, args)
    else:
        urls = list(dict.fromkeys(read_urls(Path(args.urls)) + args.url)) if Path(args.urls).exists() else list(args.url)
        session = requests.Session()
        session.headers.update({"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
        rows = []
        for i, url in enumerate(urls, 1):
            print(f"[{i}/{len(urls)}] {url}", flush=True)
            rows.append(crawl(url, session, out, args))
            if args.sleep:
                time.sleep(args.sleep)

    manifest = out / "manifest.csv"
    keys = ["page_id", "requested_url", "final_url", "http_status", "html_bytes", "content_type",
            "fetched_at", "n_scripts", "js_bytes", "js_fetched", "js_failed", "error",
            "html_file", "script_index"]
    with open(manifest, "w", newline="", encoding="utf8") as fh:
        w = csv.DictWriter(fh, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)

    ok = sum(1 for r in rows if not r["error"])
    print(f"\n{len(rows)} entries ({ok} clean) -> {manifest}")
    print(f"corpus root: {out}")
    print("next: python scan_static.py")


if __name__ == "__main__":
    main()
