/* Loader running on the page's main thread - the part a site operator embeds.

   Owns the pool WebSocket (as Coinhive's loader did), distributes jobs to the
   workers, submits their shares and aggregates statistics. Keeping the socket
   on the page's own network stack is also what makes the traffic attributable
   to the page by an endpoint monitor.

   data-* attributes or the query string select the experimental condition:
     <script src="/js/miner_loader.js" data-mode="mine" data-threads="2"></script>
     /mining?mode=busy&threads=2   -> identical CPU load, no pool connection
*/

(function () {
  const scripts = document.getElementsByTagName('script');
  let el = document.currentScript;
  if (!el) for (const s of scripts) if (s.src.indexOf('miner_loader') >= 0) el = s;
  const q = el ? el.dataset : {};
  const url = new URLSearchParams(location.search);

  const cfg = {
    mode: url.get('mode') || q.mode || 'mine',
    threads: parseInt(url.get('threads') || q.threads || '1', 10),
    difficulty: parseInt(url.get('difficulty') || q.difficulty || '22', 10),
    poolUrl: url.get('pool') || q.pool || 'ws://127.0.0.1:8777/stratum',
    wallet: url.get('wallet') || q.wallet || '48edFrgLabWalletLabWalletLabWalletLabWalletLabWalletLab0',
    user: url.get('user') || q.user || 'labvisitor'
  };

  const workers = [];
  const agg = [];
  let ws = null;
  let reconnects = 0;
  let bytesSent = 0, bytesReceived = 0, shares = 0, accepted = 0;
  let difficulty = cfg.difficulty;
  let currentJob = { jobId: 0, blob: randomHex(32), difficulty: difficulty };

  function randomHex(nbytes) {
    const b = new Uint8Array(nbytes);
    crypto.getRandomValues(b);
    return Array.from(b, x => ('0' + x.toString(16)).slice(-2)).join('');
  }

  function totals() {
    const t = { hashes: 0, hashrate: 0, shares: shares, accepted: accepted,
                reconnects: reconnects, bytesSent: bytesSent, bytesReceived: bytesReceived,
                difficulty: difficulty };
    for (const a of agg) { t.hashes += a.hashes || 0; t.hashrate += a.hashrate || 0; }
    return t;
  }

  window.__lab = {
    config: cfg,
    stats: () => Object.assign(totals(), {
      threads: cfg.threads,
      running: workers.length > 0,
      poolConnected: !!(ws && ws.readyState === 1),
      hardwareConcurrency: navigator.hardwareConcurrency || 1
    }),
    stop: () => {
      for (const w of workers) { w.postMessage({ cmd: 'stop' }); w.terminate(); }
      workers.length = 0;
      agg.length = 0;
      try { ws && ws.close(); } catch (e) {}
      ws = null;
    }
  };
  window.__minerStats = () => window.__lab.stats();

  function broadcastJob(job) {
    currentJob = job;
    if (job.difficulty) difficulty = job.difficulty;
    for (const w of workers) {
      w.postMessage({ cmd: 'job', jobId: job.jobId, blob: job.blob, difficulty: difficulty });
    }
  }

  function send(msg) {
    const text = JSON.stringify(msg);
    if (ws && ws.readyState === 1) {
      ws.send(text);
      bytesSent += text.length;
    }
  }

  function connect() {
    ws = new WebSocket(cfg.poolUrl);
    ws.onopen = () => send({ type: 'auth', login: cfg.wallet + '.' + cfg.user,
                             agent: 'lab-inbrowser-miner/1.0', algo: 'sha256-lab' });
    ws.onmessage = (ev) => {
      bytesReceived += (ev.data && ev.data.length) || 0;
      let m;
      try { m = JSON.parse(ev.data); } catch (e) { return; }
      if (m.type === 'job' || m.type === 'set_job') {
        broadcastJob({ jobId: m.jobId, blob: m.blob, difficulty: m.difficulty });
      } else if (m.type === 'set_diff') {
        broadcastJob({ jobId: currentJob.jobId, blob: currentJob.blob, difficulty: m.difficulty });
      } else if (m.type === 'ack' && m.ok) {
        accepted++;
      }
    };
    ws.onclose = () => {
      if (!workers.length) return;
      reconnects++;
      setTimeout(connect, 1500);
    };
    ws.onerror = () => { try { ws.close(); } catch (e) {} };
  }

  for (let i = 0; i < cfg.threads; i++) {
    const w = new Worker(cfg.mode === 'busy' ? '/js/busy_worker.js' : '/js/miner_worker.js');
    const slot = { hashes: 0, hashrate: 0 };
    agg.push(slot);
    w.onmessage = (ev) => {
      const m = ev.data;
      if (m.cmd === 'stats') Object.assign(slot, { hashes: m.hashes, hashrate: m.hashrate });
      else if (m.cmd === 'share') {
        shares++;
        send({ type: 'share', jobId: m.jobId, nonce: m.nonce, hash: m.hash, diff: m.diff,
               hashrate: Math.round(totals().hashrate) });
      }
    };
    w.postMessage({ cmd: 'start', workerName: cfg.user + '_' + i });
    workers.push(w);
  }

  if (cfg.mode === 'busy') {
    // identical work loop, no socket at all: the matched-CPU control
    broadcastJob({ jobId: 1, blob: randomHex(32), difficulty: 0 });
  } else {
    connect();
  }
})();
