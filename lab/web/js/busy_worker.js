/* Control workload: the same proof-of-work loop and thread model as the miner,
   but the page never opens a socket. Lets the analysis separate "this page
   burns CPU" from "this page burns CPU *and* talks to a mining pool". */

importScripts('sha256.js');
const sha = self.__sha256;

const out = new Uint32Array(8);
const msg = new Uint8Array(36);

let hashes = 0;
let running = false;
let t0 = 0;
let slice = null;
let reporter = null;

self.onmessage = (ev) => {
  const m = ev.data;
  if (m.cmd === 'start') {
    running = true;
    t0 = performance.now();
    msg.set(sha.hexToBytes(m.seed || ('00'.repeat(32))), 0);
    slice = setInterval(() => {
      if (!running) return;
      const end = performance.now() + 60;
      do {
        for (let i = 0; i < 4096; i++) {
          const n = (hashes + i) >>> 0;
          msg[32] = n & 255;
          msg[33] = (n >>> 8) & 255;
          msg[34] = (n >>> 16) & 255;
          msg[35] = (n >>> 24) & 255;
          sha.sha256Short(msg, out);
        }
        hashes += 4096;
      } while (performance.now() < end);
    }, 60);
    reporter = setInterval(() => {
      const elapsed = (performance.now() - t0) / 1000;
      self.postMessage({ cmd: 'stats', hashes: hashes, hashrate: elapsed > 0 ? hashes / elapsed : 0 });
    }, 1000);
  } else if (m.cmd === 'stop') {
    running = false;
    clearInterval(slice);
    clearInterval(reporter);
  }
};
