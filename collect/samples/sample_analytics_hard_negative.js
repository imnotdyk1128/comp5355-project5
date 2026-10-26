/* Scanner validation sample - a hard negative.
   An ordinary analytics/ads-style script that uses the same browser APIs a
   miner uses (dedicated worker, WebAssembly, WebSocket, long polling) without
   any mining semantics. The static scanner must NOT label this a miner; if it
   does, the generic indicators are too loose. */

(function () {
  "use strict";
  var ENDPOINT = "https://analytics.example.com/collect";
  var socket = null;

  function boot() {
    var worker = new Worker("/static/worker/chart-decoder.js");
    worker.onmessage = function (ev) {
      if (ev.data && ev.data.type === "series") { render(ev.data.points); }
    };
    if (typeof WebAssembly !== "undefined") {
      fetch("/static/wasm/decoder.wasm").then(function (r) { return r.arrayBuffer(); })
        .then(function (buf) { return WebAssembly.instantiate(buf, {}); })
        .then(function (m) { worker.postMessage({ wasm: m.instance }); });
    }
    setInterval(function () {
      try {
        socket = socket || new WebSocket("wss://realtime.example.com/live");
        socket.send(JSON.stringify({ v: 3, sid: sessionId(), t: Date.now() }));
      } catch (e) { /* offline */ }
    }, 15000);
  }

  function render(points) {
    var host = document.getElementById("chart");
    if (!host) return;
    host.innerHTML = points.map(function (p) { return "<b>" + p + "</b>"; }).join(" ");
  }

  function sessionId() {
    return (Math.random().toString(36) + Math.random().toString(36)).slice(2, 18);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
