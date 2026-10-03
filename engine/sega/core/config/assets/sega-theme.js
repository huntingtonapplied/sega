/* SEGA dashboard theme + settings popover (Dash config page).
   Shares the 'sega-theme' localStorage key with the live-status landing so the
   light/dark choice follows the user across both pages. Dash renders its layout
   asynchronously, so everything here is event-delegated and the initial sync
   retries until the header mounts. The auto-refresh segmented control is wired
   to live-interval by a Dash callback (dashboard.py); this file only handles the
   theme control, the gear open/close, and the environment readout. */
(function () {
  function apply(t) {
    document.documentElement.dataset.theme = t;
    try { localStorage.setItem('sega-theme', t); } catch (e) {}
    var logo = document.getElementById('logo');
    if (logo) logo.src = t === 'light' ? '/assets/sega-icon-dark.png' : '/assets/sega-icon-light.png';
    document.querySelectorAll('[data-theme-set]').forEach(function (b) {
      b.classList.toggle('active', b.dataset.themeSet === t);
    });
  }

  var t;
  try { t = localStorage.getItem('sega-theme'); } catch (e) {}
  if (!t) t = (window.matchMedia && matchMedia('(prefers-color-scheme: light)').matches) ? 'light' : 'dark';
  apply(t);

  document.addEventListener('click', function (e) {
    var closest = e.target && e.target.closest ? e.target.closest.bind(e.target) : null;
    if (!closest) return;
    var pop = document.getElementById('settings-pop');
    if (closest('#settings-toggle')) { e.stopPropagation(); if (pop) pop.classList.toggle('show'); return; }
    var seg = closest('[data-theme-set]');
    if (seg) { apply(seg.dataset.themeSet); return; }
    // Click outside the popover closes it.
    if (pop && pop.classList.contains('show') && !closest('.settings-wrap')) pop.classList.remove('show');
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') { var p = document.getElementById('settings-pop'); if (p) p.classList.remove('show'); }
  });

  function syncEnv(caps) {
    var el = document.getElementById('env-readout');
    if (!el) return false;
    var rt = caps.in_container ? 'container' : 'host';
    var act = caps.auth === 'disabled' ? 'read-only' : (caps.actions_enabled ? 'enabled' : 'locked');
    el.innerHTML = 'Runtime: <b>' + rt + '</b><br>Actions: <b>' + act + '</b>';
    return true;
  }
  fetch('/v1/capabilities').then(function (r) { return r.json(); }).then(function (caps) {
    var n = 0, iv = setInterval(function () { n++; if (syncEnv(caps) || n > 50) clearInterval(iv); }, 200);
  }).catch(function () {});

  /* Sync theme once Dash mounts the header (retry up to ~10s). */
  var tries = 0;
  var iv = setInterval(function () {
    tries++;
    if (document.getElementById('settings-toggle') || tries > 50) {
      apply(document.documentElement.dataset.theme);
      clearInterval(iv);
    }
  }, 200);
})();
