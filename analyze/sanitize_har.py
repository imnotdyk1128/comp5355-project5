"""Strip identifying values from exported HAR files before publishing.

HAR captures request/response headers verbatim, which for a real browsing
session includes cookies, authorization headers, and - as found while preparing
this project for a public repository - site-set GeoIP cookies that disclose the
approximate location of the egress IP, plus session identifiers.

Header *names* are kept (the analysis uses them); only values are replaced.

Usage:
  python sanitize_har.py                 # scrub results/ and results_live/
  python sanitize_har.py --dir results/measure/har
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent

SCRUB_NAMES = {"cookie", "set-cookie", "authorization", "proxy-authorization", "x-api-key"}
# GeoIP-style cookies leak the egress IP's coarse location even after scrubbing,
# so the whole entry is dropped rather than blanked.
DROP_PREFIXES = ("geoip", "wmf-uniq", "networkprobelimit")


def scrub_entry(entry: dict) -> int:
    n = 0
    for section in ("request", "response"):
        headers = entry.get(section, {}).get("headers", [])
        kept = []
        for h in headers:
            name = (h.get("name") or "").lower()
            if name.startswith(DROP_PREFIXES):
                n += 1
                continue
            if name in SCRUB_NAMES and (h.get("value") or "").strip():
                h["value"] = "[scrubbed]"
                n += 1
            kept.append(h)
        entry[section]["headers"] = kept
        cookies = entry.get(section, {}).get("cookies")
        if cookies:
            n += len(cookies)
            entry[section]["cookies"] = []
    # page/content text can echo cookies inside captured bodies
    content = entry.get("response", {}).get("content", {})
    if "text" in content and isinstance(content["text"], str) and len(content["text"]) > 2_000_000:
        content["text"] = content["text"][:2_000_000]
    return n


def scrub_file(path: Path) -> tuple[int, int]:
    try:
        har = json.loads(path.read_text(encoding="utf8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        print(f"  skip {path}: {exc}")
        return 0, 0
    total = 0
    entries = har.get("log", {}).get("entries", [])
    for e in entries:
        total += scrub_entry(e)
    if total:
        path.write_text(json.dumps(har), encoding="utf8")
    return total, len(entries)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", default="", help="single har directory; default: both result sets")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    roots = [Path(args.dir)] if args.dir else [PROJECT / "results" / "measure" / "har",
                                               PROJECT / "results_live" / "measure" / "har"]
    files: list[Path] = []
    for r in roots:
        if r.is_dir():
            files.extend(sorted(r.glob("*.har")))
    if not files:
        print("no HAR files found")
        return

    scrubbed = 0
    for f in files:
        if args.dry_run:
            data = json.loads(f.read_text(encoding="utf8"))
            n = sum(scrub_entry(dict(e)) for e in data.get("log", {}).get("entries", []))
            print(f"  {f.name}: {n} values would be removed")
            scrubbed += n
            continue
        n, m = scrub_file(f)
        scrubbed += n
        if n:
            print(f"  {f.name}: {n} identifying values removed from {m} entries")
    print(f"{'would scrub' if args.dry_run else 'scrubbed'} {scrubbed} values across {len(files)} files")


if __name__ == "__main__":
    main()
