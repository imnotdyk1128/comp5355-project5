/* Emulated in-browser miner: hashing worker.

   Architecture follows Coinhive: the *page* (main thread) owns the pool
   connection and the workers only burn CPU. That keeps the CPU load in worker
   threads and makes the page's own traffic observable to an endpoint monitor
   through the page's network stack.

   The worker receives {cmd:'job', blob, difficulty} and searches nonces until
   it finds a hash below the target, then reports the share. */

importScripts('sha256.js');

const sha = self.__sha256;
const out = new Uint32Array(8);
const msg = new Uint8Array(36);

let hashes = 0;
let job = null;
let running = false;
let t0 = 0;

function targetMask(bits) {
  return bits >= 32 ? 0 : (0xFFFFFFFF >>> bits);
}

function search(budgetMs) {
  if (!job) return;
  const end = performance.now() + budgetMs;
  // Report a share and keep scanning: returning early would idle the thread
  // whenever difficulty is low, which is not how a miner behaves.
  do {
    const mask = targetMask(job.difficulty);
    msg.set(job.blob, 0);
    let found = -1;
    for (let i = 0; i < 4096; i++) {
      const n = (job.nextNonce + i) >>> 0;
      msg[32] = n & 255;
      msg[33] = (n >>> 8) & 255;
      msg[34] = (n >>> 16) & 255;
      msg[35] = (n >>> 24) & 255;
      sha.sha256Short(msg, out);
      hashes++;
      if ((out[0] & ~mask) === 0) {
        found = n;
        job.nextNonce = (n + 1) >>> 0;
        break;
      }
    }
    if (found < 0) {
      job.nextNonce = (job.nextNonce + 4096) >>> 0;
    } else {
      self.postMessage({ cmd: 'share', jobId: job.jobId, nonce: found,
                         hash: sha.toHex(out), diff: job.difficulty });
    }
  } while (performance.now() < end && job);
}

let slice = null;
let reporter = null;

self.onmessage = (ev) => {
  const m = ev.data;
  if (m.cmd === 'start') {
    running = true;
    t0 = performance.now();
    slice = setInterval(() => { if (running) search(60); }, 60);
    reporter = setInterval(() => {
      const elapsed = (performance.now() - t0) / 1000;
      self.postMessage({
        cmd: 'stats',
        hashes: hashes,
        hashrate: elapsed > 0 ? hashes / elapsed : 0,
        mining: !!job
      });
    }, 1000);
  } else if (m.cmd === 'job') {
    job = { jobId: m.jobId, blob: sha.hexToBytes(m.blob), difficulty: m.difficulty || 22, nextNonce: 0 };
  } else if (m.cmd === 'stop') {
    running = false;
    clearInterval(slice);
    clearInterval(reporter);
  }
};
