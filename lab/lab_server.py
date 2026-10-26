"""Lab server for Project 5: serves the three experimental pages and emulates a
mining pool so that every byte of cryptojacking traffic is observable locally.

Run standalone:
    python lab_server.py --http-port 8080 --pool-port 8777

The measurement runner starts and stops this automatically.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import math
import os
import secrets
import signal
import time
from datetime import datetime, timezone
from pathlib import Path

from aiohttp import web

LAB_DIR = Path(__file__).resolve().parent
WEB_ROOT = LAB_DIR / "web"
RESULTS_DIR = Path(os.environ.get("P5_RESULTS", LAB_DIR.parent / "results")) / "lab"

PAGES = {
    "/": "pages/clean.html",
    "/clean": "pages/clean.html",
    "/busy": "pages/busy.html",
    "/mining": "pages/mining.html",
}

MIME = {
    ".html": ("text/html", "utf-8"),
    ".js": ("application/javascript", "utf-8"),
    ".css": ("text/css", "utf-8"),
    ".svg": ("image/svg+xml", "utf-8"),
    ".json": ("application/json", "utf-8"),
    ".png": ("image/png", None),
}


def respond(body: bytes, suffix: str, **kw) -> web.Response:
    ct, charset = MIME.get(suffix, ("application/octet-stream", None))
    return web.Response(body=body, content_type=ct, charset=charset, **kw)


class TrafficLog:
    """Append-only CSV writers; kept flush-per-record so a killed run still has data."""

    def __init__(self, directory: Path):
        directory.mkdir(parents=True, exist_ok=True)
        self.files = {}
        self.handles = {}
        for name, header in (
            ("http_access", ["ts", "elapsed_s", "path", "method", "status", "bytes_out", "ua"]),
            ("pool_frames", ["ts", "elapsed_s", "conn_id", "dir", "frame_bytes", "msg_type", "detail", "worker", "difficulty"]),
            ("pool_events", ["ts", "elapsed_s", "conn_id", "event", "worker", "payload_bytes_total"]),
        ):
            path = directory / f"{name}.csv"
            fh = open(path, "w", newline="", encoding="utf8")
            w = csv.writer(fh)
            w.writerow(header)
            fh.flush()
            self.files[name] = w
            self.handles[name] = fh

    def write(self, name: str, row: list) -> None:
        self.files[name].writerow(row)
        self.handles[name].flush()

    def close(self) -> None:
        for fh in self.handles.values():
            fh.close()


def svg_banner(seed: int) -> bytes:
    hue = (seed * 67) % 360
    return (
        f"<svg xmlns='http://www.w3.org/2000/svg' width='640' height='180'>"
        f"<rect width='640' height='180' fill='hsl({hue},40%,70%)'/>"
        f"<text x='20' y='100' font-size='34' font-family='sans-serif' fill='#222'>"
        f"Advertisement block {seed}</text></svg>"
    ).encode()


class Pool:
    """Minimal stratum-style pool: periodic jobs, submitted shares, dynamic difficulty."""

    def __init__(self, log: TrafficLog, start: float, pool_cfg: dict):
        self.log = log
        self.start = start
        self.pool_cfg = pool_cfg
        self.job_interval = pool_cfg["job_interval"]
        self.target_share_s = pool_cfg["target_share_interval"]
        self.retarget_every = pool_cfg.get("retarget_every", 4)
        self.min_difficulty = pool_cfg.get("min_difficulty", 12)
        self.start_difficulty = pool_cfg.get("start_difficulty", 22)
        self.conns: dict[int, dict] = {}
        self.next_id = 1
        self.job_id = 0
        self.blob = secrets.token_bytes(32)
        self.wallet_shares = 0

    @staticmethod
    def _num(v, default=0.0) -> float:
        try:
            return float(v)
        except (TypeError, ValueError):
            return default

    def _ts(self) -> tuple[str, float]:
        now = time.time()
        return datetime.fromtimestamp(now, timezone.utc).isoformat(timespec="milliseconds"), now - self.start

    def touch(self, ws: web.WebSocketResponse, text: str, direction: str, conn: dict, msg_type: str = "", detail: str = "") -> None:
        ts, el = self._ts()
        frame_bytes = len(text.encode()) + 2  # websocket framing overhead, approximated
        self.log.write("pool_frames", [ts, round(el, 3), conn["id"], direction, frame_bytes, msg_type, detail, conn.get("worker", ""), conn.get("difficulty", "")])
        conn["bytes_" + ("in" if direction == "in" else "out")] += frame_bytes

    async def register(self, request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse(heartbeat=None)
        await ws.prepare(request)
        cid = self.next_id
        self.next_id += 1
        conn = {"id": cid, "ws": ws, "worker": "", "difficulty": self.start_difficulty,
                "bytes_in": 0, "bytes_out": 0, "last_share": time.time(), "shares": 0, "window": []}
        self.conns[cid] = conn
        ts, el = self._ts()
        self.log.write("pool_events", [ts, round(el, 3), cid, "open", "", 0])
        try:
            async for msg in ws:
                if msg.type is not web.WSMsgType.TEXT:
                    continue
                self.handle_message(conn, msg.data)
        finally:
            ts, el = self._ts()
            self.log.write("pool_events", [ts, round(el, 3), cid, "close", conn["worker"], conn["bytes_in"] + conn["bytes_out"]])
            self.conns.pop(cid, None)
        return ws

    def handle_message(self, conn: dict, text: str) -> None:
        try:
            msg = json.loads(text)
        except json.JSONDecodeError:
            return
        mtype = msg.get("type", "")
        if mtype == "auth":
            conn["worker"] = msg.get("login", "")
            conn["difficulty"] = int(msg.get("difficulty", conn["difficulty"]))
            conn["last_share"] = time.time()
            conn["window"] = []
            self.touch(conn["ws"], text, "in", conn, mtype, conn["worker"])
            asyncio.ensure_future(self._send(conn, {"type": "job", "jobId": self.job_id, "blob": self.blob.hex(),
                                                    "difficulty": conn["difficulty"]}))
            return
        if mtype == "share":
            now = time.time()
            interval = max(0.05, now - conn["last_share"])
            conn["last_share"] = now
            conn["shares"] += 1
            self.wallet_shares += 1
            old = conn["difficulty"]
            conn["window"].append(interval)
            if len(conn["window"]) >= self.retarget_every:
                # Retarget a bit at a time so one slow round cannot collapse the
                # difficulty. When the client reports its hashrate, aim for a
                # share every target_share_s seconds *per connection*, which may
                # carry several workers.
                avg = sum(conn["window"]) / len(conn["window"])
                conn["window"] = []
                hashrate = self._num(msg.get("hashrate"))
                if hashrate and hashrate > 0:
                    want = int(round(math.log2(max(2.0, hashrate * self.target_share_s))))
                    step = max(-2, min(2, want - old))
                else:
                    step = max(-1, min(1, int(round(math.log2(max(1e-6, avg / self.target_share_s))))))
                conn["difficulty"] = max(self.min_difficulty, min(31, old + step))
            self.touch(conn["ws"], text, "in", conn, mtype, f"nonce={msg.get('nonce')} job={msg.get('jobId')}")
            asyncio.ensure_future(self._send(conn, {"type": "ack", "ok": True, "shareId": conn["shares"]}))
            if conn["difficulty"] != old:
                asyncio.ensure_future(self._send(conn, {"type": "set_diff", "difficulty": conn["difficulty"],
                                                        "measuredShareInterval": round(interval, 2)}))
            return
        self.touch(conn["ws"], text, "in", conn, mtype, "")

    async def _send(self, conn: dict, payload: dict) -> None:
        text = json.dumps(payload)
        ws: web.WebSocketResponse = conn["ws"]
        if ws.closed:
            return
        await ws.send_str(text)
        self.touch(ws, text, "out", conn, payload.get("type", ""), "")

    async def rotate_jobs(self) -> None:
        while True:
            await asyncio.sleep(self.job_interval)
            self.job_id += 1
            self.blob = secrets.token_bytes(32)
            for conn in list(self.conns.values()):
                if conn["ws"].closed:
                    continue
                await self._send(conn, {"type": "job", "jobId": self.job_id, "blob": self.blob.hex(),
                                         "difficulty": conn["difficulty"]})


def make_apps(pool_cfg: dict) -> tuple[web.Application, web.Application, TrafficLog, Pool]:
    start = time.time()
    log = TrafficLog(RESULTS_DIR)
    pool = Pool(log, start, pool_cfg)

    http_app = web.Application()

    async def serve_page(request: web.Request) -> web.Response:
        rel = PAGES.get(request.path)
        if rel:
            body = (WEB_ROOT / rel).read_bytes()
            ts, el = datetime.now(timezone.utc).isoformat(timespec="milliseconds"), time.time() - start
            log.write("http_access", [ts, round(el, 3), request.path, "GET", 200, len(body), request.headers.get("User-Agent", "")])
            return respond(body, ".html")
        path = (WEB_ROOT / request.path.lstrip("/")).resolve()
        if not str(path).startswith(str(WEB_ROOT.resolve())) or not path.is_file():
            if request.path.startswith("/img/banner"):
                body = svg_banner(int(request.path.rstrip(".svg").split("banner")[-1] or 0))
                ts, el = datetime.now(timezone.utc).isoformat(timespec="milliseconds"), time.time() - start
                log.write("http_access", [ts, round(el, 3), request.path, "GET", 200, len(body), request.headers.get("User-Agent", "")])
                return respond(body, ".svg")
            return web.Response(status=404, text="not found")
        body = path.read_bytes()
        ts, el = datetime.now(timezone.utc).isoformat(timespec="milliseconds"), time.time() - start
        log.write("http_access", [ts, round(el, 3), request.path, "GET", 200, len(body), request.headers.get("User-Agent", "")])
        return respond(body, path.suffix)

    http_app.add_routes([web.get("/{tail:.*}", serve_page)])

    pool_app = web.Application()
    pool_app.add_routes([web.get("/stratum", pool.register)])
    pool_app["pool"] = pool
    pool_app["log"] = log
    pool_app["start"] = start
    return http_app, pool_app, log, pool


async def main_async(args: argparse.Namespace) -> None:
    cfg = {"job_interval": args.job_interval, "target_share_interval": args.target_share_interval,
           "retarget_every": args.retarget_every, "min_difficulty": args.min_difficulty,
           "start_difficulty": args.start_difficulty}
    http_app, pool_app, log, pool = make_apps(cfg)

    runner_http = web.AppRunner(http_app)
    runner_pool = web.AppRunner(pool_app)
    await runner_http.setup()
    await runner_pool.setup()
    site_http = web.TCPSite(runner_http, args.host, args.http_port)
    site_pool = web.TCPSite(runner_pool, args.host, args.pool_port)
    await site_http.start()
    await site_pool.start()

    rotator = asyncio.ensure_future(pool.rotate_jobs())
    print(json.dumps({"status": "lab-ready", "http": f"http://{args.host}:{args.http_port}",
                      "pool": f"ws://{args.host}:{args.pool_port}/stratum", "results": str(RESULTS_DIR)}), flush=True)

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:
            pass  # Windows: the runner terminates us directly

    await stop.wait()
    rotator.cancel()
    for conn in list(pool.conns.values()):
        await conn["ws"].close()
    await runner_http.cleanup()
    await runner_pool.cleanup()
    log.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Project 5 lab server (pages + emulated mining pool)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--http-port", type=int, default=8080)
    parser.add_argument("--pool-port", type=int, default=8777)
    parser.add_argument("--job-interval", type=float, default=3.0, help="seconds between stratum job broadcasts")
    parser.add_argument("--target-share-interval", type=float, default=2.0, help="pool retargets difficulty to this share spacing")
    parser.add_argument("--start-difficulty", type=int, default=22, help="initial leading-zero-bit target")
    parser.add_argument("--min-difficulty", type=int, default=12, help="floor, keeps share chatter realistic")
    parser.add_argument("--retarget-every", type=int, default=4, help="shares averaged per difficulty retarget")
    args = parser.parse_args()
    try:
        asyncio.run(main_async(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
