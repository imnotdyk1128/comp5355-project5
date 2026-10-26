/* Identical page furniture for every experimental condition: same DOM size,
   same images, same timers, so only the script under test differs. */

(function () {
  const root = document.getElementById('content');
  const paragraphs = 14;
  const lorem = 'Campus network traffic shows the same diurnal pattern every week, and the measurement notes collected for this course describe how a shared link becomes a bottleneck shortly after midnight. ';
  let html = '<h1>Weekly report: traffic shaping on the dorm network</h1>';
  html += '<p class="byline">Published by the student computing group &middot; read time 6 min</p>';

  for (let i = 0; i < paragraphs; i++) {
    html += '<p>' + lorem.repeat(3) + '</p>';
    if (i === 4 || i === 9) {
      html += '<figure><img src="/img/banner' + (i % 3) + '.svg" width="640" height="180" alt="banner">' +
              '<figcaption>Figure ' + (i / 5 | 0) + ': throughput sample</figcaption></figure>';
    }
    html += '<ul><li>queue discipline: HTB with three classes</li><li>peak measured at 23:41</li>' +
            '<li>drop tail probability tuned to 0.02</li></ul>';
  }

  html += '<div class="widget" id="rotator"></div>';
  html += '<div class="comments">';
  for (let i = 0; i < 25; i++) {
    html += '<div class="comment"><b>user' + i + '</b><span> ' + lorem.slice(0, 120) + '</span></div>';
  }
  html += '</div>';
  root.innerHTML = html;

  const widget = document.getElementById('rotator');
  const items = ['Sponsored: hostel deal', 'Sponsored: VPN plan', 'Sponsored: course bundle'];
  let idx = 0;
  setInterval(() => {
    widget.textContent = items[idx % items.length];
    idx++;
  }, 2000);

  let acc = 0;
  setInterval(() => {
    for (let i = 0; i < 20000; i++) acc += Math.sqrt(i % 997);
    widget.dataset.tick = String(acc | 0);
  }, 500);
})();
