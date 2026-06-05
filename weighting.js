/* ============================================================================
   Civica — User Weighting Module  (Phase 1)
   ----------------------------------------------------------------------------
   Lets a visitor re-weight the six Civica dimensions and instantly re-rank all
   2,816 counties in the browser. No backend, no pipeline re-run: every county
   in output/index.json already carries its six dimension point contributions
   (dim1..dim6), so a re-weighting is just a normalized weighted average.

   KEY PROPERTY: the 'default' preset uses the published model weights
   (25/22/20/15/12/6), which reproduces each county's official Civica Score
   exactly. So nothing changes on screen until the user expresses a preference.

   Trust note: the federal *data* is immutable and uninfluenceable. Only the
   visitor's *priorities* change. The score still can't be bought — now the
   weighting is yours instead of ours.
   ========================================================================== */
(function (global) {
  'use strict';

  // Max points per dimension, from scoring_engine.py (sum = 100).
  var MAX  = { dim1: 25, dim2: 22, dim3: 20, dim4: 15, dim5: 12, dim6: 6 };
  var DIMS = ['dim1', 'dim2', 'dim3', 'dim4', 'dim5', 'dim6'];

  var DIM_LABELS = {
    dim1: 'Affordability',
    dim2: 'Economic Vitality',
    dim3: 'Market Dynamics',
    dim4: 'Quality of Place',
    dim5: 'Climate & Risk',
    dim6: 'Population Growth'
  };

  // Presets are *relative* weight vectors (normalized internally to sum=100).
  // 'default' === published model weights → reproduces the official score.
  // The non-default vectors are editorial starting points, not new science:
  // they simply tilt the same federal sub-scores toward one buyer's priorities.
  var PRESETS = {
    'default':       { emoji: '⚖️', label: 'Civica Default',  blurb: "Our 6-dimension composite — the published score.",            weights: { dim1: 25, dim2: 22, dim3: 20, dim4: 15, dim5: 12, dim6: 6 } },
    'affordability': { emoji: '🏠', label: 'Affordability',   blurb: "Price-to-rent, price-to-income and breakeven lead.",          weights: { dim1: 45, dim2: 12, dim3: 16, dim4: 10, dim5: 10, dim6: 7 } },
    'jobs':          { emoji: '💼', label: 'Jobs',            blurb: "Wages, sector quality and who's moving in lead.",             weights: { dim1: 13, dim2: 42, dim3: 14, dim4: 10, dim5: 6,  dim6: 15 } },
    'family':        { emoji: '🛡️', label: 'Family & Safety', blurb: "Crime, amenities and hazard exposure lead.",                  weights: { dim1: 14, dim2: 12, dim3: 8,  dim4: 38, dim5: 23, dim6: 5 } },
    'climate':       { emoji: '🌤️', label: 'Climate Safety',  blurb: "Flood, storm and wildfire risk lead.",                        weights: { dim1: 14, dim2: 12, dim3: 8,  dim4: 16, dim5: 45, dim6: 5 } },
    'investor':      { emoji: '📈', label: 'Investor',        blurb: "Appreciation, momentum and value lead.",                      weights: { dim1: 22, dim2: 15, dim3: 38, dim4: 5,  dim5: 6,  dim6: 14 } }
  };
  var PRESET_ORDER = ['default', 'affordability', 'jobs', 'family', 'climate', 'investor'];

  var STORAGE_KEY = 'civica_weighting';

  // ---- internal state -----------------------------------------------------
  var state = { preset: 'default', weights: cloneW(PRESETS['default'].weights) };
  var listeners = [];
  var mounts = [];   // mounted preset-bar root elements

  function cloneW(o) { var r = {}; for (var i = 0; i < DIMS.length; i++) r[DIMS[i]] = o[DIMS[i]]; return r; }

  // ---- scoring ------------------------------------------------------------
  // 0–100 sub-score for one dimension (raw points / dimension max).
  function subScore(county, dim) {
    var v = county[dim];
    if (v === null || v === undefined || isNaN(v)) return null;
    return (v / MAX[dim]) * 100;
  }

  // Weighted 0–100 composite under the active (or supplied) weights.
  // Missing dimensions are skipped and the denominator renormalized.
  function weightedScore(county, weights) {
    // Default path: return the published score verbatim. The weighted formula
    // reproduces it to within ~0.02 (2-decimal rounding in index.json), but the
    // default view should be pixel-identical to the official score.
    if (!weights && state.preset === 'default' && typeof county.score === 'number') return county.score;
    weights = weights || state.weights;
    var num = 0, den = 0;
    for (var i = 0; i < DIMS.length; i++) {
      var s = subScore(county, DIMS[i]);
      if (s === null) continue;
      var w = weights[DIMS[i]] || 0;
      num += s * w;
      den += w;
    }
    if (den === 0) return (typeof county.score === 'number') ? county.score : 0;
    return num / den;
  }

  // Fixed-band color for a 0–100 score (used only when a non-default
  // weighting is active; the default view keeps each county's signal color).
  function bandColor(score) {
    if (score >= 62) return '#16a34a';
    if (score >= 55) return '#22c55e';
    if (score >= 48) return '#1a7ff0';
    if (score >= 42) return '#8b5cf6';
    if (score >= 36) return '#f59e0b';
    if (score >= 30) return '#f97316';
    if (score >= 26) return '#ef4444';
    return '#dc2626';
  }

  // ---- persistence --------------------------------------------------------
  function persist() {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify({ preset: state.preset, weights: state.weights })); } catch (e) {}
  }

  function syncUrl() {
    try {
      var url = new URL(location.href);
      if (state.preset && state.preset !== 'default' && state.preset !== 'custom') {
        url.searchParams.set('preset', state.preset);
      } else {
        url.searchParams.delete('preset');
      }
      history.replaceState(null, '', url);
    } catch (e) {}
  }

  // URL ?preset= wins (so homepage deep-links work), then localStorage, else default.
  function init() {
    var p = null;
    try { p = new URLSearchParams(location.search).get('preset'); } catch (e) {}
    if (p && PRESETS[p]) { state.preset = p; state.weights = cloneW(PRESETS[p].weights); persist(); return api; }
    try {
      var raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        var saved = JSON.parse(raw);
        if (saved && saved.preset === 'custom' && saved.weights) { state.preset = 'custom'; state.weights = saved.weights; return api; }
        if (saved && saved.preset && PRESETS[saved.preset]) { state.preset = saved.preset; state.weights = cloneW(PRESETS[saved.preset].weights); return api; }
      }
    } catch (e) {}
    return api;
  }

  // ---- mutation -----------------------------------------------------------
  function setPreset(key) {
    if (!PRESETS[key]) return;
    state.preset = key;
    state.weights = cloneW(PRESETS[key].weights);
    syncUrl(); persist(); refresh(); emit();
  }

  function setWeight(dim, value) {
    state.weights[dim] = Math.max(0, Math.min(60, value | 0));
    state.preset = 'custom';
    syncUrl(); persist(); refresh(); emit();
  }

  function reset() { setPreset('default'); }

  // ---- events -------------------------------------------------------------
  function onChange(fn) { if (typeof fn === 'function') listeners.push(fn); }
  function emit() { for (var i = 0; i < listeners.length; i++) { try { listeners[i](state); } catch (e) {} } }

  // ---- query --------------------------------------------------------------
  function isDefault() { return state.preset === 'default'; }
  function activePresetKey() { return state.preset; }
  function activePresetMeta() {
    if (state.preset === 'custom') return { key: 'custom', emoji: '🎛️', label: 'Your custom mix', blurb: 'Weights you set yourself.' };
    return { key: state.preset, emoji: PRESETS[state.preset].emoji, label: PRESETS[state.preset].label, blurb: PRESETS[state.preset].blurb };
  }

  // ---- UI: preset bar -----------------------------------------------------
  var STYLE_ID = 'cw-style';
  function injectStyle() {
    if (document.getElementById(STYLE_ID)) return;
    var s = document.createElement('style');
    s.id = STYLE_ID;
    s.textContent =
      '.cw-wrap{max-width:1000px;margin:0 auto;}' +
      '.cw-head{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;margin-bottom:10px;}' +
      '.cw-title{font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:#98989d;}' +
      '.cw-blurb{font-size:12px;color:#6e6e73;}' +
      '.cw-chips{display:flex;gap:8px;flex-wrap:wrap;align-items:center;}' +
      '.cw-chip{padding:9px 16px;border-radius:100px;border:1.5px solid rgba(0,0,0,.08);background:#fff;font-size:13px;font-weight:600;color:#6e6e73;cursor:pointer;font-family:inherit;transition:all .15s;display:inline-flex;align-items:center;gap:6px;white-space:nowrap;}' +
      '.cw-chip:hover{border-color:#0d2d52;color:#0d2d52;}' +
      '.cw-chip.active{background:#0d2d52;color:#fff;border-color:#0d2d52;}' +
      '.cw-chip .cw-emoji{font-size:14px;}' +
      '.cw-custom{margin-left:2px;background:none;border:none;color:#1a7ff0;font-size:13px;font-weight:700;cursor:pointer;font-family:inherit;padding:9px 6px;white-space:nowrap;}' +
      '.cw-custom.on{color:#0d2d52;}' +
      '.cw-panel{margin-top:14px;padding:18px 20px;background:#f8fafc;border:1px solid rgba(0,0,0,.06);border-radius:12px;display:none;}' +
      '.cw-panel.open{display:block;}' +
      '.cw-row{display:flex;align-items:center;gap:14px;padding:6px 0;}' +
      '.cw-lbl{font-size:13px;font-weight:600;color:#0d2d52;width:150px;flex-shrink:0;}' +
      '.cw-row input[type=range]{flex:1;accent-color:#1a7ff0;height:4px;}' +
      '.cw-val{font-size:12px;font-weight:700;color:#6e6e73;width:30px;text-align:right;font-variant-numeric:tabular-nums;}' +
      '.cw-foot{display:flex;justify-content:space-between;align-items:center;margin-top:12px;}' +
      '.cw-note{font-size:11px;color:#98989d;}' +
      '.cw-reset{background:none;border:none;color:#6e6e73;font-size:12px;font-weight:600;cursor:pointer;text-decoration:underline;font-family:inherit;}' +
      '@media(max-width:660px){.cw-chips{flex-wrap:nowrap;overflow-x:auto;-webkit-overflow-scrolling:touch;scrollbar-width:none;padding-bottom:4px;}.cw-chips::-webkit-scrollbar{display:none;}.cw-chip{flex-shrink:0;font-size:12px;padding:8px 13px;}.cw-lbl{width:108px;font-size:12px;}}';
    document.head.appendChild(s);
  }

  function mountBar(target, opts) {
    opts = opts || {};
    var el = (typeof target === 'string') ? document.getElementById(target) : target;
    if (!el) return;
    injectStyle();
    el.classList.add('cw-wrap');
    el.dataset.cwTitle = opts.title || 'What matters to you?';
    el.dataset.cwSliders = (opts.sliders === false) ? '0' : '1';
    if (mounts.indexOf(el) === -1) mounts.push(el);
    render(el);
  }

  function render(el) {
    var showSliders = el.dataset.cwSliders !== '0';
    var meta = activePresetMeta();

    var chips = PRESET_ORDER.map(function (k) {
      var p = PRESETS[k];
      var active = (state.preset === k) ? ' active' : '';
      return '<button type="button" class="cw-chip' + active + '" data-cw-preset="' + k + '">' +
             '<span class="cw-emoji">' + p.emoji + '</span>' + p.label + '</button>';
    }).join('');

    var customChip = (state.preset === 'custom')
      ? '<button type="button" class="cw-chip active" data-cw-preset="custom"><span class="cw-emoji">🎛️</span>Your mix</button>'
      : '';

    var customizeBtn = showSliders
      ? '<button type="button" class="cw-custom' + (state.preset === 'custom' ? ' on' : '') + '" data-cw-toggle>Customize ▸</button>'
      : '';

    var sliders = '';
    if (showSliders) {
      var rows = DIMS.map(function (d) {
        return '<div class="cw-row">' +
                 '<span class="cw-lbl">' + DIM_LABELS[d] + '</span>' +
                 '<input type="range" min="0" max="50" step="1" value="' + (state.weights[d] | 0) + '" data-cw-dim="' + d + '">' +
                 '<span class="cw-val" data-cw-out="' + d + '">' + (state.weights[d] | 0) + '</span>' +
               '</div>';
      }).join('');
      sliders =
        '<div class="cw-panel" data-cw-panel>' +
          rows +
          '<div class="cw-foot">' +
            '<span class="cw-note">Weights are relative — Civica normalizes them. The data never changes, only your priorities.</span>' +
            '<button type="button" class="cw-reset" data-cw-reset>Reset to Civica default</button>' +
          '</div>' +
        '</div>';
    }

    el.innerHTML =
      '<div class="cw-head"><span class="cw-title">' + el.dataset.cwTitle + '</span>' +
        '<span class="cw-blurb">' + meta.emoji + ' ' + meta.label + ' — ' + meta.blurb + '</span></div>' +
      '<div class="cw-chips">' + chips + customChip + customizeBtn + '</div>' +
      sliders;

    wire(el);
  }

  function wire(el) {
    el.querySelectorAll('[data-cw-preset]').forEach(function (b) {
      b.addEventListener('click', function () {
        var k = b.getAttribute('data-cw-preset');
        if (k === 'custom') return; // the custom chip is just a status indicator
        setPreset(k);
      });
    });
    var toggle = el.querySelector('[data-cw-toggle]');
    var panel = el.querySelector('[data-cw-panel]');
    if (toggle && panel) {
      toggle.addEventListener('click', function () { panel.classList.toggle('open'); });
      if (state.preset === 'custom') panel.classList.add('open');
    }
    el.querySelectorAll('[data-cw-dim]').forEach(function (inp) {
      inp.addEventListener('input', function () {
        var d = inp.getAttribute('data-cw-dim');
        var out = el.querySelector('[data-cw-out="' + d + '"]');
        if (out) out.textContent = inp.value;
        setWeight(d, parseInt(inp.value, 10));
      });
    });
    var rst = el.querySelector('[data-cw-reset]');
    if (rst) rst.addEventListener('click', reset);
  }

  // Re-render every mounted bar (preserving any open slider panel).
  function refresh() {
    for (var i = 0; i < mounts.length; i++) {
      var wasOpen = !!mounts[i].querySelector('.cw-panel.open');
      render(mounts[i]);
      if (wasOpen) { var p = mounts[i].querySelector('[data-cw-panel]'); if (p) p.classList.add('open'); }
    }
  }

  // ---- public API ---------------------------------------------------------
  var api = {
    PRESETS: PRESETS, PRESET_ORDER: PRESET_ORDER, DIM_LABELS: DIM_LABELS, MAX: MAX,
    init: init, mountBar: mountBar, onChange: onChange,
    setPreset: setPreset, setWeight: setWeight, reset: reset,
    weightedScore: weightedScore, subScore: subScore, bandColor: bandColor,
    isDefault: isDefault, activePresetKey: activePresetKey, activePresetMeta: activePresetMeta
  };
  global.Weighting = api;
  init();

})(window);
