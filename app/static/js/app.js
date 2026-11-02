/* Global JS: kept small. Page-specific scripts live inside their templates. */
(function () {
  'use strict';
  // Dismissible flash messages (+ gentle auto-dismiss for success).
  document.addEventListener('click', function (e) {
    var btn = e.target.closest('[data-dismiss-flash]');
    if (btn) btn.closest('.flash').remove();

    var copy = e.target.closest('[data-copy]');
    if (copy) {
      var text = copy.dataset.copy || window.location.href;
      var done = function () {
        var old = copy.innerHTML; copy.classList.add('is-done');
        copy.querySelector('.copy-label') && (copy.querySelector('.copy-label').textContent = 'Copied');
        setTimeout(function () { copy.classList.remove('is-done'); copy.innerHTML = old; }, 1600);
      };
      if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(text).then(done);
      else { var t = document.createElement('textarea'); t.value = text; document.body.appendChild(t); t.select(); try { document.execCommand('copy'); done(); } catch (x) {} t.remove(); }
    }
    if (e.target.closest('[data-print]')) window.print();

    var pw = e.target.closest('[data-toggle-password]');
    if (pw) {
      var input = document.getElementById(pw.dataset.togglePassword);
      var show = input.type === 'password';
      input.type = show ? 'text' : 'password';
      pw.textContent = show ? 'Hide' : 'Show';
    }
  });

  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('.flash-success').forEach(function (n) {
      setTimeout(function () { if (n.parentNode) n.remove(); }, 6000);
    });

    // Ctrl/⌘ + K focuses the page's search box.
    document.addEventListener('keydown', function (e) {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        var q = document.querySelector('[data-search-focus]');
        if (q) { e.preventDefault(); q.focus(); q.select(); }
      }
    });

    // Notification bell: fetched lazily the first time it is opened, count fetched shortly after load.
    var script = document.querySelector('script[data-attention-url]');
    var url = script && script.dataset.attentionUrl;
    var bell = document.getElementById('bellBtn');
    if (!url || !bell) return;
    var list = document.getElementById('bellList'), count = document.getElementById('bellCount'),
        dot = document.getElementById('bellDot'), loaded = false;
    function esc(s) { var d = document.createElement('div'); d.textContent = s == null ? '' : s; return d.innerHTML; }
    function load() {
      return fetch(url, {credentials: 'same-origin', headers: {'X-Requested-With': 'fetch'}})
        .then(function (r) { if (!r.ok) throw 0; return r.json(); })
        .then(function (d) {
          loaded = true;
          dot.hidden = !d.count;
          count.textContent = d.count ? d.count + ' open' : '';
          list.innerHTML = d.items.length ? d.items.map(function (i) {
            var m = i.margin == null ? 'N/A' : i.margin.toFixed(2) + '%';
            var neg = i.margin != null && i.margin < 0;
            return '<a class="bell-item" href="' + esc(i.url) + '"><span><strong>' + esc(i.name) + '</strong><small>' + esc(i.code) + ' · ' + esc(i.status) + '</small></span><span class="bell-m ' + (neg ? 'profit-neg' : '') + '">' + m + '</span></a>';
          }).join('') : '<div class="bell-empty">Nothing needs attention right now.</div>';
        }).catch(function () { list.innerHTML = '<div class="bell-empty">Could not load alerts.</div>'; });
    }
    setTimeout(load, 600);
    bell.addEventListener('show.bs.dropdown', function () { if (loaded) load(); });
  });

  // Wide tables: hover near a side edge to pan the table. Saves dragging the scrollbar.
  // Velocity eases in and out (px/second + exponential smoothing) so it never jerks.
  (function () {
    var box = null, target = 0, vel = 0, raf = 0, last = 0, down = false;
    var PEAK = 820;   // px/second at the very edge

    function stop() {
      if (raf) cancelAnimationFrame(raf);
      box = null; target = 0; vel = 0; last = 0; raf = 0;
    }
    function frame(now) {
      raf = 0;
      if (!box || !box.isConnected) { stop(); return; }
      var dt = last ? Math.min((now - last) / 1000, 0.05) : 1 / 60;
      last = now;
      vel += (target - vel) * (1 - Math.exp(-18 * dt));   // ~60 ms settle, frame-rate independent
      if (!target && Math.abs(vel) < 3) { stop(); return; }
      var at = box.scrollLeft;
      box.scrollLeft = at + vel * dt;
      if (box.scrollLeft === at) { stop(); return; }      // hit either end
      raf = requestAnimationFrame(frame);
    }
    function wake() { if (!raf) { last = 0; raf = requestAnimationFrame(frame); } }

    document.addEventListener('mousemove', function (e) {
      var t = e.target;
      var table = !down && t.closest && t.closest('.table-responsive');
      // Centre of the table (or off-table) is a dead zone: glide to a stop, no snap.
      // Pausing over controls keeps a click from sliding out from under the pointer.
      if (!table || table.scrollWidth <= table.clientWidth + 1 ||
          (t.closest && t.closest('a, button, input, select, textarea, label'))) {
        target = 0; wake(); return;
      }
      var r = table.getBoundingClientRect();
      var zone = Math.min(72, r.width / 4);
      var x = e.clientX - r.left;
      var dir = x > r.width - zone ? 1 : (x < zone ? -1 : 0);
      box = table;
      if (!dir) { target = 0; } else {
        var depth = dir > 0 ? (x - (r.width - zone)) / zone : (zone - x) / zone;
        target = dir * (110 + depth * depth * (PEAK - 110));   // gentle near the boundary, faster at the edge
      }
      wake();
    }, { passive: true });

    document.documentElement.addEventListener('mouseleave', function () { target = 0; wake(); });
    document.addEventListener('mousedown', function () { down = true; target = 0; vel = 0; wake(); });
    document.addEventListener('mouseup', function () { down = false; });
    window.addEventListener('blur', function () { down = false; stop(); });
  })();

  // Collapsible sidebar: desktop rail (persisted) + mobile off-canvas drawer.
  (function () {
    var shell = document.getElementById('appShell');
    if (!shell) return;
    var root = document.documentElement, KEY = 'wbe.sidebar';
    var mq = window.matchMedia('(min-width: 992px)');
    function remember() { try { localStorage.setItem(KEY, root.classList.contains('sidebar-collapsed') ? '1' : '0'); } catch (e) {} }
    function sync() {
      var open = shell.classList.contains('is-mobile-open');
      document.querySelectorAll('[data-sidebar-toggle]').forEach(function (b) {
        b.setAttribute('aria-expanded', String(mq.matches ? !root.classList.contains('sidebar-collapsed') : open));
      });
    }
    document.addEventListener('click', function (e) {
      var t = e.target;
      if (!t || !t.closest) return;
      if (t.closest('[data-sidebar-toggle]')) {
        if (mq.matches) { root.classList.toggle('sidebar-collapsed'); remember(); }
        else shell.classList.toggle('is-mobile-open');
        sync();
        return;
      }
      if (t.closest('[data-sidebar-scrim]')) { shell.classList.remove('is-mobile-open'); sync(); }
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && shell.classList.contains('is-mobile-open')) { shell.classList.remove('is-mobile-open'); sync(); }
    });
    function onBreak() {
      shell.classList.remove('is-mobile-open');
      if (mq.matches) { try { root.classList.toggle('sidebar-collapsed', localStorage.getItem(KEY) === '1'); } catch (e) {} }
      else root.classList.remove('sidebar-collapsed');
      sync();
    }
    if (mq.addEventListener) mq.addEventListener('change', onBreak); else if (mq.addListener) mq.addListener(onBreak);
    sync();
  })();
})();
