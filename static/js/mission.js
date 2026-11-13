/*
 * Nexa Pals — Mission engine.
 *
 * Replaces the old "Try It Live" widget (a single substring match) with a
 * multi-step mission that RUNS what the learner writes and tests the result.
 *
 * A mission is a list of steps. Step types:
 *   code     build something; tests inspect the real page the code produces
 *   fix      same as code, but the starter has a bug to find and fix
 *   predict  read code, type what it will show, then see it run
 *   order    put shuffled lines of code back in the right order
 *
 * Learner code runs inside a sandboxed iframe (allow-scripts only), so it
 * cannot touch the Nexa Pals page. Tests are declarative (no eval), so this
 * works under the site's Content-Security-Policy.
 *
 * Backwards compatible: an old practice_json with `checks` is converted to a
 * single step whose checks look at real code with comments stripped (so a
 * comment like "// alert(" no longer counts).
 */
(function (global) {
  'use strict';

  // ------------------------------------------------------------------ utils
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  // Remove comments so a hint like "// use alert(" in a starter can't pass a check.
  function stripComments(code, lang) {
    code = String(code || '');
    if (lang === 'html') return code.replace(/<!--[\s\S]*?-->/g, '');
    code = code.replace(/\/\*[\s\S]*?\*\//g, '');
    if (lang === 'css') return code;
    // JS: drop // comments but keep "https://..." style strings
    return code.replace(/(^|[^:'"\\])\/\/.*$/gm, '$1');
  }

  function norm(s) {
    return String(s == null ? '' : s).trim().toLowerCase().replace(/\s+/g, ' ')
      .replace(/^["'`]|["'`]$/g, '');
  }

  // Convert legacy {task, starter_*, checks:[{contains,min_count,hint}], success_msg}
  function normalize(p) {
    if (!p) return null;
    if (Array.isArray(p.steps) && p.steps.length) {
      return {
        title: p.title || 'Mission',
        task: p.task || '',
        steps: p.steps,
        worked: p.worked || null,
        words: p.words || null,
        skill: p.skill || '',
        success_msg: p.success_msg || 'Mission complete!'
      };
    }
    var tests = (p.checks || []).map(function (c, i) {
      return { id: 'legacy' + i, label: c.hint ? c.hint.replace(/<[^>]+>/g, '') : 'Your code uses ' + c.contains,
               kind: 'code_has', text: c.contains, min: c.min_count || 1, lang: 'any' };
    });
    return {
      title: p.title || 'Try It Live',
      task: p.task || '',
      success_msg: p.success_msg || 'Nice work!',
      steps: [{
        type: 'code', prompt: p.task || '', starter_html: p.starter_html, starter_css: p.starter_css,
        starter_js: p.starter_js, tests: tests, hints: (p.checks || []).map(function (c) { return c.hint; }),
        success_msg: p.success_msg
      }]
    };
  }

  // Turn raw browser errors into advice a 10-year-old can act on.
  function friendlyError(raw) {
    var m = String(raw || '');
    var q = m.match(/(\w+) is not defined/);
    if (q) return 'The computer does not know the name <code>' + esc(q[1]) + '</code>. Check the spelling and capital letters, and that you created it with <code>let</code>.';
    if (/Cannot (set|read) propert/.test(m)) return 'JavaScript could not find that element on the page. Check that the id inside <code>getElementById("...")</code> matches the id in the HTML exactly.';
    if (/is not a function/.test(m)) return 'You tried to use something like a function, but it is not one. Check the spelling and where the <code>( )</code> go.';
    if (/Assignment to constant/.test(m)) return 'You made this with <code>const</code>, which cannot change. Use <code>let</code> for things that change.';
    if (/already been declared/.test(m)) return 'You made the same variable twice. Use <code>let</code> only the first time, then just use the name.';
    if (/Unexpected (token|end|identifier)|Invalid or unexpected|missing \)/.test(m)) return 'Something is missing or extra, usually a bracket <code>) } ]</code> or a quote. Count your opening and closing ones.';
    return 'Your code reported: <code>' + esc(m) + '</code>';
  }

  // Robot levels: grid rows use R (start), G (goal), # (wall), . (floor).
  // A program is a list of 'up'|'down'|'left'|'right' or {r: n} meaning "repeat the next block n times".
  function parseGrid(rows) {
    var g = { H: rows.length, W: rows[0].length, walls: {}, start: null, goal: null };
    rows.forEach(function (row, y) { row.split('').forEach(function (ch, x) {
      if (ch === '#') g.walls[x + ',' + y] = 1; else if (ch === 'R') g.start = { x: x, y: y }; else if (ch === 'G') g.goal = { x: x, y: y };
    }); });
    return g;
  }
  function simulate(g, prog) {
    var d = { up: [0, -1], down: [0, 1], left: [-1, 0], right: [1, 0] };
    var pos = { x: g.start.x, y: g.start.y }, frames = [{ x: pos.x, y: pos.y, bump: false, block: -1 }], err = '';
    for (var i = 0; i < prog.length; i++) {
      var it = prog[i], times = 1, cmd = it, at = i;
      if (typeof it === 'object') {
        if (i + 1 >= prog.length || typeof prog[i + 1] === 'object') { err = 'A Repeat block needs a move block right after it.'; break; }
        times = it.r; cmd = prog[i + 1]; i++;
      }
      for (var t = 0; t < times; t++) {
        var nx = pos.x + d[cmd][0], ny = pos.y + d[cmd][1];
        var blocked = nx < 0 || ny < 0 || nx >= g.W || ny >= g.H || g.walls[nx + ',' + ny];
        if (!blocked) { pos.x = nx; pos.y = ny; }
        frames.push({ x: pos.x, y: pos.y, bump: !!blocked, block: at });
      }
    }
    return { frames: frames, end: pos, error: err, reached: !err && pos.x === g.goal.x && pos.y === g.goal.y };
  }

  // Same rule is mirrored in learning_analytics.py
  function masteryOf(assisted, attempts, steps) {
    if (assisted > 0) return 'practising';
    return attempts <= steps * 2 ? 'mastered' : 'solid';
  }

  // ----------------------------------------------------------- sandbox page
  // Runs inside the iframe. Kept as a function so it is stringified once.
  function harness() {
    var alerts = [], logs = [], errors = [];
    window.alert = function (m) { alerts.push(String(m)); };
    window.confirm = function (m) { alerts.push(String(m)); return true; };
    window.prompt = function (m, d) { alerts.push(String(m)); return d == null ? '' : d; };
    var origLog = console.log;
    console.log = function () {
      logs.push(Array.prototype.slice.call(arguments).map(String).join(' '));
      try { origLog.apply(console, arguments); } catch (e) {}
    };
    window.addEventListener('error', function (e) { errors.push(String(e.message || e)); });
    window.addEventListener('unhandledrejection', function (e) { errors.push(String(e.reason)); });

    function n(s) { return String(s == null ? '' : s).replace(/\s+/g, ' ').trim().toLowerCase(); }
    function first(sel) { try { return document.querySelector(sel); } catch (e) { return null; } }
    function all(sel) { try { return Array.prototype.slice.call(document.querySelectorAll(sel)); } catch (e) { return []; } }
    function matchText(actual, t) {
      var a = n(actual);
      if (t.equals !== undefined) return a === n(t.equals);
      if (t.contains !== undefined) return a.indexOf(n(t.contains)) !== -1;
      if (t.regex !== undefined) return new RegExp(t.regex, 'i').test(String(actual));
      if (t.not_contains !== undefined) return a.indexOf(n(t.not_contains)) === -1;
      if (t.not_empty) return a.length > 0;
      return false;
    }
    function snapshot(el, what) {
      if (!el) return null;
      if (what === 'text') return el.textContent;
      if (what === 'class') return el.className;
      if (what === 'color') return getComputedStyle(el).color;
      if (what === 'background') return getComputedStyle(el).backgroundColor;
      if (what === 'html') return el.innerHTML;
      return getComputedStyle(el)[what];
    }
    function evalTest(t) {
      var el, els, i, v;
      switch (t.kind) {
        case 'exists': return all(t.selector).length >= (t.min || 1);
        case 'count':
          v = all(t.selector).length;
          return (t.equals === undefined || v === t.equals) && (t.min === undefined || v >= t.min) && (t.max === undefined || v <= t.max);
        case 'text':
          els = all(t.selector);
          return els.some(function (e) { return matchText(e.textContent, t); });
        case 'style':
          el = first(t.selector); if (!el) return false;
          v = getComputedStyle(el)[t.prop];
          if (t.equals !== undefined) return n(v) === n(t.equals);
          if (t.not_equals !== undefined) return n(v) !== n(t.not_equals);
          if (t.contains !== undefined) return n(v).indexOf(n(t.contains)) !== -1;
          if (t.not_zero) return parseFloat(v) > 0;
          if (t.min_s !== undefined) return parseFloat(v) >= t.min_s;
          if (t.min_px !== undefined) return parseFloat(v) >= t.min_px;
          return false;
        case 'attr':
          els = all(t.selector);
          return els.some(function (e) {
            var a = e.getAttribute(t.attr);
            if (a === null) return false;
            if (t.equals !== undefined) return n(a) === n(t.equals);
            if (t.contains !== undefined) return n(a).indexOf(n(t.contains)) !== -1;
            if (t.not_empty) return n(a).length > 0 && n(a) !== '#';
            return true;
          });
        case 'alert':
          v = alerts.filter(function (a) { return (t.contains === undefined || n(a).indexOf(n(t.contains)) !== -1) && (t.not_contains === undefined || n(a).indexOf(n(t.not_contains)) === -1); });
          return v.length >= (t.min || 1);
        case 'log':
          v = logs.filter(function (a) { return (t.contains === undefined || n(a).indexOf(n(t.contains)) !== -1) && (t.not_contains === undefined || n(a).indexOf(n(t.not_contains)) === -1); });
          return v.length >= (t.min || 1);
        case 'focused': return !!document.activeElement && document.activeElement.matches && document.activeElement.matches(t.selector);
        case 'no_errors': return errors.length === 0;
        case 'call': {
          var fn = window[t.fn];
          if (typeof fn !== 'function') return false;
          v = fn.apply(null, t.args || []);
          if (t.returns !== undefined) return n(v) === n(t.returns);
          return true;
        }
        case 'click': {
          el = first(t.selector); if (!el) return false;
          if (t.fill) { var fe = first(t.fill.selector); if (fe) { fe.value = t.fill.value; fe.dispatchEvent(new Event('input', { bubbles: true })); } }
          for (i = 0; i < (t.times || 1); i++) el.click();
          return (t.then || []).every(evalTest);
        }
        case 'changes_on_click': {
          el = first(t.click); var w = first(t.watch || t.click);
          if (!el || !w) return false;
          var seen = {}; var before = snapshot(w, t.what || 'text'); seen[before] = 1;
          for (i = 0; i < (t.times || 2); i++) { el.click(); seen[snapshot(w, t.what || 'text')] = 1; }
          return Object.keys(seen).length >= (t.distinct || 2);
        }
        default: return false;
      }
    }
    window.addEventListener('message', function (ev) {
      var d = ev.data;
      if (!d || d.nexa !== 'run-tests') return;
      var res = [];
      // clicks change the page, so run passive tests first, interactive ones last
      var order = d.tests.map(function (t, idx) { return { t: t, idx: idx, late: t.kind === 'click' || t.kind === 'changes_on_click' }; });
      order.sort(function (a, b) { return (a.late - b.late) || (a.idx - b.idx); });
      order.forEach(function (o) {
        var ok = false;
        try { ok = !!evalTest(o.t); } catch (e) { ok = false; }
        res[o.idx] = { id: o.t.id, ok: ok };
      });
      parent.postMessage({ nexa: 'test-results', token: d.token, results: res, errors: errors.slice(0, 3), alerts: alerts.slice(0, 5), logs: logs.slice(0, 8) }, '*');
    });
    window.addEventListener('load', function () { parent.postMessage({ nexa: 'ready' }, '*'); });
  }

  function buildDoc(parts) {
    var css = parts.css || '', html = parts.html || '', js = parts.js || '';
    var base = 'body{font-family:system-ui,sans-serif;margin:12px;color:#1e3a5f}';
    return '<!DOCTYPE html><html><head><meta charset="utf-8"><style>' + base + css.replace(/<\/style/gi, '<\\/style') + '</style></head><body>' +
      html + '<script>(' + harness.toString() + ')();<\/script>' +
      (js ? '<script>' + js.replace(/<\/script/gi, '<\\/script') + '<\/script>' : '') + '</body></html>';
  }

  // Parent-side: tests that look at the learner's source code, comments removed.
  function evalCodeTest(t, fields) {
    var langs = t.lang && t.lang !== 'any' ? [t.lang] : ['html', 'css', 'js'];
    var src = langs.map(function (l) { return stripComments(fields[l] || '', l); }).join('\n');
    var count;
    if (t.regex) { var m = src.match(new RegExp(t.regex, 'gi')); count = m ? m.length : 0; }
    else { count = src.toLowerCase().split(String(t.text).toLowerCase()).length - 1; }
    return t.kind === 'code_hasnt' ? count === 0 : count >= (t.min || 1);
  }

  // Shows console.log / alert output on the page so a prediction can be compared with reality.
  var PRE = 'var __o=document.getElementById("out");function __w(p,a){__o.textContent+=(__o.textContent?"\\n":"")+p+Array.prototype.slice.call(a).join(" ");}' +
    'console.log=function(){__w("",arguments);};window.alert=function(){__w("alert: ",arguments);};';

  // ------------------------------------------------------------------ styles
  var CSS = [
    '.nm{background:#fff;border:3px solid var(--nm,#9B7EDE);border-radius:24px;padding:1.4rem 1.6rem;margin-bottom:1.5rem;font-family:inherit}',
    '.nm *{box-sizing:border-box}',
    '.nm-head{display:flex;align-items:center;gap:.8rem;flex-wrap:wrap;margin-bottom:.9rem}',
    '.nm-title{margin:0;font-size:1.2rem;color:#1e3a5f}',
    '.nm-badge{background:var(--nm,#9B7EDE);color:#fff;border-radius:20px;padding:.15rem .8rem;font-size:.75rem;font-weight:800;text-transform:uppercase;letter-spacing:.05em}',
    '.nm-dots{margin-left:auto;display:flex;gap:.35rem;align-items:center}',
    '.nm-dot{width:14px;height:14px;border-radius:50%;background:#e1e9f7;border:2px solid #c5d5e8}',
    '.nm-dot.now{border-color:var(--nm,#9B7EDE);background:#fff;transform:scale(1.15)}',
    '.nm-dot.done{background:#1e5f4b;border-color:#1e5f4b}',
    '.nm-prompt{font-size:.98rem;line-height:1.55;color:#1e3a5f;margin:0 0 .8rem}',
    '.nm-prompt code,.nm-hint code{background:#f0f5ff;padding:.05rem .35rem;border-radius:6px;font-size:.88em}',
    '.nm-lab{font-size:.72rem;font-weight:800;color:#55688a;margin:.2rem 0;text-transform:uppercase;letter-spacing:.05em}',
    '.nm-ed{width:100%;font-family:"Fira Code",ui-monospace,Menlo,Consolas,monospace;font-size:.86rem;line-height:1.5;padding:.7rem;border-radius:12px;border:2px solid var(--nm,#9B7EDE);background:#0f1a2e;color:#f8faff;resize:vertical;margin-bottom:.7rem;tab-size:2}',
    '.nm-ed:focus{outline:3px solid rgba(255,179,71,.6)}',
    '.nm-code{background:#0f1a2e;color:#f8faff;border-radius:12px;padding:.8rem 1rem;font-family:"Fira Code",ui-monospace,Menlo,Consolas,monospace;font-size:.88rem;line-height:1.55;white-space:pre-wrap;margin:0 0 .8rem;overflow:auto}',
    '.nm-btns{display:flex;gap:.55rem;flex-wrap:wrap;margin:.2rem 0 .8rem}',
    '.nm-btn{border:none;border-bottom:3px solid rgba(0,0,0,.2);border-radius:30px;padding:.55rem 1.1rem;font-weight:800;font-size:.88rem;cursor:pointer;font-family:inherit;color:#fff;background:var(--nm,#9B7EDE)}',
    '.nm-btn.go{background:#1e5f4b}.nm-btn.alt{background:#55688a}.nm-btn.warn{background:#a35f10}',
    '.nm-btn:disabled{opacity:.45;cursor:not-allowed}',
    '.nm-btn:focus-visible{outline:3px solid #FFB347;outline-offset:2px}',
    '.nm-frame{width:100%;height:170px;border:2px solid #e1e9f7;border-radius:12px;background:#fff;margin-bottom:.7rem}',
    '.nm-tests{list-style:none;margin:0 0 .7rem;padding:0;display:flex;flex-direction:column;gap:.3rem}',
    '.nm-tests li{display:flex;gap:.55rem;align-items:flex-start;font-size:.88rem;font-weight:600;color:#55688a;padding:.35rem .6rem;border-radius:10px;background:#f8faff}',
    '.nm-tests li.ok{background:#d4edda;color:#155724}.nm-tests li.no{background:#f8d7da;color:#721c24}',
    '.nm-tests i{margin-top:.15rem}',
    '.nm-hint{background:#fff6e6;border-left:5px solid #FFB347;border-radius:10px;padding:.55rem .8rem;margin:.4rem 0;font-size:.88rem;color:#7a4a00}',
    '.nm-msg{padding:.6rem .9rem;border-radius:10px;font-weight:700;font-size:.9rem;margin:.4rem 0}',
    '.nm-msg.good{background:#d4edda;color:#155724}.nm-msg.bad{background:#f8d7da;color:#721c24}.nm-msg.info{background:#e4efff;color:#1e3a5f}',
    '.nm-in{width:100%;padding:.6rem .9rem;border-radius:12px;border:2px solid var(--nm,#9B7EDE);font-family:inherit;font-size:1rem;margin-bottom:.7rem}',
    '.nm-lines{list-style:none;margin:0 0 .8rem;padding:0;display:flex;flex-direction:column;gap:.35rem}',
    '.nm-line{display:flex;align-items:center;gap:.5rem;background:#0f1a2e;color:#f8faff;border-radius:10px;padding:.35rem .5rem;border:2px solid transparent}',
    '.nm-line code{flex:1;font-family:"Fira Code",ui-monospace,Menlo,Consolas,monospace;font-size:.86rem;white-space:pre-wrap}',
    '.nm-line.ok{border-color:#2d8c6e}.nm-line.no{border-color:#e25c5c}',
    '.nm-mv{background:#2d3f5a;color:#fff;border:none;border-radius:8px;width:34px;height:34px;cursor:pointer;font-size:1rem}',
    '.nm-mv:disabled{opacity:.3;cursor:default}.nm-mv:focus-visible{outline:3px solid #FFB347}',
    '.nm-done{text-align:center;padding:1rem .5rem}',
    '.nm-done h3{margin:.3rem 0;color:#1e5f4b}',
    '.nm-stats{display:flex;gap:.6rem;justify-content:center;flex-wrap:wrap;margin-top:.6rem}',
    '.nm-gapcode{line-height:2.1}',
    '.nm-gap{font-family:"Fira Code",ui-monospace,Menlo,Consolas,monospace;font-size:.88rem;background:#fff;color:#1e3a5f;border:2px solid #FFB347;border-radius:8px;padding:.15rem .4rem;min-height:34px;max-width:100%}',
    '.nm-gap:focus{outline:3px solid #FFB347;outline-offset:1px}',
    '.nm-anat{line-height:2.2;font-size:1rem}',
    '.nm-part{font:inherit;font-weight:700;background:rgba(255,255,255,.08);color:#fff;border:2px solid var(--pc);border-radius:8px;padding:.05rem .35rem;margin:0 1px;cursor:pointer;min-height:36px}',
    '.nm-part.seen{background:var(--pc);color:#0f1a2e}.nm-part.on{outline:3px solid #FFB347;outline-offset:2px}.nm-part:focus-visible{outline:3px solid #FFB347;outline-offset:2px}',
    '.nm-explain{background:#f8faff;border-left:5px solid #6c4bb8;border-radius:10px;padding:.7rem .9rem;margin:.2rem 0 .6rem;min-height:3.2rem;color:#1e3a5f;line-height:1.5}',
    '.nm-grid{display:grid;gap:4px;margin:.4rem 0 .8rem;width:max-content;max-width:100%}',
    '.nm-cell{width:52px;height:52px;border-radius:10px;background:#eef3ff;display:flex;align-items:center;justify-content:center}',
    '.nm-cell.wall{background:#55688a}.nm-cell.goal{background:#fff6e6}.nm-cell.bump{background:#f8d7da}',
    '.nm-cell svg{width:34px;height:34px}',
    '.nm-pal{display:flex;gap:.4rem;flex-wrap:wrap;margin:.2rem 0 .5rem}',
    '.nm-blk{min-width:48px;min-height:44px;border-radius:12px;border:2px solid var(--nm,#9B7EDE);background:#fff;color:#1e3a5f;font-weight:800;font-size:1rem;font-family:inherit;cursor:pointer;padding:0 .7rem}',
    '.nm-blk.rep{background:#fff6e6;border-color:#a35f10}',
    '.nm-blk:focus-visible{outline:3px solid #FFB347}',
    '.nm-prog{display:flex;gap:.35rem;flex-wrap:wrap;min-height:50px;padding:.5rem;border:2px dashed #c5d5e8;border-radius:12px;margin-bottom:.6rem;background:#f8faff}',
    '.nm-chip{display:inline-flex;align-items:center;gap:.3rem;background:var(--nm,#9B7EDE);color:#fff;border-radius:10px;padding:.25rem .3rem .25rem .6rem;font-weight:800;border:none;cursor:pointer;font-family:inherit;min-height:40px}',
    '.nm-chip.rep{background:#a35f10}.nm-chip.now{outline:3px solid #FFB347}',
    '.nm-words{background:#f8faff;border-radius:12px;padding:.4rem .8rem;margin:0 0 .8rem;font-size:.9rem}',
    '.nm-words summary{cursor:pointer;font-weight:800;color:#1e3a5f}.nm-words dt{font-weight:800;margin-top:.4rem;color:#1e3a5f}.nm-words dd{margin:0 0 0 .2rem;color:#55688a}',
    '.nm-m-mastered{background:#d4edda!important;color:#155724!important}.nm-m-solid{background:#e4efff!important}.nm-m-practising{background:#fff6e6!important;color:#7a4a00!important}',
    '.nm-listen{border:2px solid var(--nm,#9B7EDE);background:#fff;color:var(--nm,#9B7EDE);border-radius:20px;padding:.2rem .75rem;font-weight:800;font-size:.78rem;cursor:pointer;font-family:inherit;min-height:32px}',
    '.nm-sym{display:flex;gap:.3rem;flex-wrap:wrap;margin:.2rem 0 .5rem}',
    '.nm-sym button{min-width:42px;min-height:42px;border-radius:10px;border:2px solid #c5d5e8;background:#f8faff;font:700 1rem "Fira Code",ui-monospace,monospace;color:#1e3a5f;cursor:pointer}',
    '.nm-sym button:focus-visible{outline:3px solid #FFB347}',
    '.nm-worked{background:#f8faff;border:2px dashed var(--nm,#9B7EDE);border-radius:16px;padding:1rem;margin-bottom:.8rem}',
    '.nm-worked h3{margin:.1rem 0 .4rem;color:#1e3a5f;font-size:1.05rem}',
    '@media(max-width:640px){.nm{padding:1rem}.nm-ed{font-size:16px}.nm-btn{min-height:44px}.nm-in{font-size:16px}}',
    '.nm-stat{background:#f0f5ff;border-radius:14px;padding:.4rem .9rem;font-weight:800;color:#1e3a5f;font-size:.85rem}'
  ].join('\n');

  function injectCss() {
    if (document.getElementById('nm-css')) return;
    var s = document.createElement('style'); s.id = 'nm-css'; s.textContent = CSS; document.head.appendChild(s);
  }

  // ------------------------------------------------------------------ mount
  function mount(root, practice, opts) {
    opts = opts || {};
    var mission = normalize(practice);
    if (!root || !mission) return null;
    injectCss();
    root.classList.add('nm');
    root.style.setProperty('--nm', opts.accent || '#9B7EDE');

    var storeKey = 'nexa-mission-' + (opts.lessonId || 'x');
    var draftKey = function (idx, f) { return storeKey + '-draft-' + idx + '-' + f; };
    function getDraft(idx, f, fallback) { try { var v = localStorage.getItem(draftKey(idx, f)); return v === null ? fallback : v; } catch (e) { return fallback; } }
    function setDraft(idx, f, v) { try { localStorage.setItem(draftKey(idx, f), v); } catch (e) {} }
    function clearDrafts(idx) { try { ['html', 'css', 'js'].forEach(function (f) { localStorage.removeItem(draftKey(idx, f)); }); } catch (e) {} }
    var wasDone = false;
    try { wasDone = localStorage.getItem(storeKey) === 'done'; } catch (e) {}

    var state = { i: 0, attempts: 0, hints: 0, assisted: 0, done: [], tokenN: 0, sChecks: 0, sHints: 0, sAssist: 0 };
    var level = opts.level || 1;
    var hintGate = level >= 4 ? 2 : (level >= 2 ? 1 : 0); // scaffolding fades as lessons progress
    var refreshHint = null;
    function promptFor(step) { return (step.prompt_i18n && step.prompt_i18n[opts.lang]) || step.prompt || ''; }
    function bumpCheck() { state.attempts++; state.sChecks++; if (refreshHint) refreshHint(); }
    var handlers = {};
    window.addEventListener('message', function (ev) {
      var d = ev.data;
      if (!d || d.nexa !== 'test-results') return;
      var h = handlers[d.token]; if (h) { delete handlers[d.token]; h(d); }
    });

    function sandboxTest(frame, tests, cb) {
      var token = ++state.tokenN;
      var timer = setTimeout(function () { delete handlers[token]; cb(null); }, 3000);
      handlers[token] = function (d) { clearTimeout(timer); cb(d); };
      frame.contentWindow.postMessage({ nexa: 'run-tests', token: token, tests: tests }, '*');
    }

    function loadFrame(frame, parts, cb) {
      var done = false;
      var onload = function () { if (done) return; done = true; frame.removeEventListener('load', onload); setTimeout(function () { cb && cb(); }, 40); };
      frame.addEventListener('load', onload);
      frame.srcdoc = buildDoc(parts);
    }

    function dots() {
      return mission.steps.map(function (_, k) {
        return '<span class="nm-dot ' + (state.done[k] ? 'done' : (k === state.i ? 'now' : '')) + '" aria-hidden="true"></span>';
      }).join('');
    }

    function shell(inner) {
      root.innerHTML =
        '<div class="nm-head"><span class="nm-badge"><i class="fas fa-rocket"></i> Mission</span>' +
        '<h2 class="nm-title">' + esc(mission.title) + '</h2>' +
        (('speechSynthesis' in window) ? '<button type="button" class="nm-listen" data-act="listen" aria-label="Read the instructions aloud"><i class="fas fa-volume-high"></i> Listen</button>' : '') +
        '<div class="nm-dots" role="img" aria-label="Step ' + (Math.min(state.i + 1, mission.steps.length)) + ' of ' + mission.steps.length + '">' + dots() + '</div></div>' +
        (mission.words && mission.words.length ? '<details class="nm-words"><summary>Code words in this mission (' + mission.words.length + ')</summary><dl>' +
          mission.words.map(function (w) { return '<dt>' + esc(w[0]) + '</dt><dd>' + w[1] + '</dd>'; }).join('') + '</dl></details>' : '') + inner;
      var lb = root.querySelector('[data-act=listen]');
      if (lb) lb.addEventListener('click', function () {
        try {
          window.speechSynthesis.cancel();
          var txt = (root.querySelector('.nm-prompt') || {}).textContent || '';
          var u = new SpeechSynthesisUtterance(txt); u.lang = opts.lang || 'en-ZA'; u.rate = 0.9;
          window.speechSynthesis.speak(u);
        } catch (e) {}
      });
    }

    function ok() { try { global.NexaSound && global.NexaSound.correct(); } catch (e) {} }
    function bad() { try { global.NexaSound && global.NexaSound.wrong(); } catch (e) {} }

    function finishMission() {
      try { localStorage.setItem(storeKey, 'done'); } catch (e) {}
      var detail = { steps: mission.steps.length, attempts: state.attempts, hints: state.hints, assisted: state.assisted };
      detail.mastery = masteryOf(detail.assisted, detail.attempts, detail.steps);
      shell('<div class="nm-done"><i class="fas fa-trophy" style="font-size:2.4rem;color:#FFB347"></i>' +
        '<h3>' + esc(mission.success_msg) + '</h3>' +
        '<p style="color:#55688a;margin:0">You finished every step. The quiz is unlocked below.</p>' +
        '<div class="nm-stats"><span class="nm-stat">' + detail.steps + ' steps</span><span class="nm-stat">' + detail.attempts + ' checks</span>' +
        '<span class="nm-stat">' + detail.hints + ' hints</span><span class="nm-stat nm-m-' + detail.mastery + '">' + ({ mastered: 'Mastered', solid: 'Solid', practising: 'Still practising' })[detail.mastery] + '</span></div>' +
        '<div class="nm-btns" style="justify-content:center;margin-top:.8rem"><button class="nm-btn alt" data-act="replay"><i class="fas fa-rotate-left"></i> Play again</button></div></div>');
      try { global.NexaSound && global.NexaSound.levelUp(); } catch (e) {}
      root.querySelector('[data-act=replay]').addEventListener('click', function () {
        state = { i: 0, attempts: 0, hints: 0, assisted: 0, done: [], tokenN: state.tokenN, sChecks: 0, sHints: 0, sAssist: 0 };
        render();
      });
      var ev = new CustomEvent('nexa:mission-complete', { detail: detail, bubbles: true });
      root.dispatchEvent(ev);
      if (opts.onComplete) opts.onComplete(detail);
    }

    function nextStep() {
      var cur = mission.steps[state.i];
      if (opts.onStep) opts.onStep({ index: state.i, skill: cur.skill || mission.skill || '', type: cur.type, checks: state.sChecks, hints: state.sHints, assisted: state.sAssist, stuck: false });
      state.done[state.i] = true;
      if (state.i + 1 >= mission.steps.length) { state.i = mission.steps.length; return finishMission(); }
      state.i++; render();
    }

    // ---- shared pieces
    function hintBox(step, box) {
      var hints = step.hints || [];
      return {
        reveal: function () {
          if (state.hintShown >= hints.length) return false;
          state.hintShown = (state.hintShown || 0) + 1; state.hints++; state.sHints++;
          var d = document.createElement('div'); d.className = 'nm-hint';
          d.innerHTML = '<i class="fas fa-lightbulb"></i> <strong>Hint ' + state.hintShown + ':</strong> ' + hints[state.hintShown - 1];
          box.appendChild(d); return true;
        },
        left: function () { return hints.length - (state.hintShown || 0); }
      };
    }

    function wireHints(step, btn, hintArea) {
      var hb = hintBox(step, hintArea);
      var hints = step.hints || [];
      if (!hints.length) { btn.style.display = 'none'; return hb; }
      var refresh = function () {
        var locked = state.sChecks < hintGate;
        btn.disabled = locked || hb.left() <= 0;
        btn.innerHTML = '<i class="fas fa-lightbulb"></i> ' + (locked ? 'Hint (try ' + (hintGate - state.sChecks) + ' more check' + (hintGate - state.sChecks > 1 ? 's' : '') + ' first)' : 'Hint (' + hb.left() + ' left)');
      };
      btn.addEventListener('click', function () { hb.reveal(); refresh(); });
      refreshHint = refresh; refresh(); return hb;
    }

    // ---- code / fix step
    function renderCode(step, idx) {
      state.hintShown = 0; var fails = 0;
      var isBlank = step.type === 'blank', tpl = step.template || {};
      var src = isBlank ? { html: tpl.html == null ? null : tpl.html.replace(/___/g, ''), css: tpl.css == null ? null : tpl.css.replace(/___/g, ''), js: tpl.js == null ? null : tpl.js.replace(/___/g, '') }
                        : { html: step.starter_html, css: step.starter_css, js: step.starter_js };
      var fields = [['html', 'HTML', src.html], ['css', 'CSS', src.css], ['js', 'JavaScript', src.js]]
        .filter(function (f) { return f[2] !== undefined && f[2] !== null; });
      var hasJs = src.js !== undefined && src.js !== null;
      var kind = step.type === 'fix' ? 'Fix the bug' : (isBlank ? 'Fill the gaps' : 'Build it');
      var html = '<p class="nm-prompt"><strong>Step ' + (idx + 1) + ' of ' + mission.steps.length + ' · ' + kind + '.</strong> ' + promptFor(step) + '</p>';
      fields.forEach(function (f) {
        html += (isBlank ? '' : '<div class="nm-lab">' + f[1] + '</div>') + '<textarea class="nm-ed" ' + (isBlank ? 'hidden aria-hidden="true" tabindex="-1" ' : '') + 'data-f="' + f[0] + '" rows="' + Math.min(10, Math.max(3, String(f[2]).split('\n').length + 1)) + '" spellcheck="false" aria-label="' + f[1] + ' code">' + esc(isBlank ? f[2] : getDraft(idx, f[0], f[2])) + '</textarea>';
      });
      html += '<div class="nm-btns"><button class="nm-btn alt" data-act="run"><i class="fas fa-play"></i> Run</button>' +
        '<button class="nm-btn go" data-act="check"><i class="fas fa-circle-check"></i> Check my code</button>' +
        '<button class="nm-btn warn" data-act="hint"></button>' +
        '<button class="nm-btn alt" data-act="show" disabled title="Unlocks after 3 checks"><i class="fas fa-eye"></i> Show me</button></div>' +
        '<iframe class="nm-frame" sandbox="allow-scripts" title="Your result"></iframe>' +
        '<ul class="nm-tests" aria-live="polite">' + (step.tests || []).map(function (t) {
          return '<li data-id="' + esc(t.id) + '"><i class="far fa-circle"></i><span>' + esc(t.label) + '</span></li>';
        }).join('') + '</ul><div data-area="hints"></div><div data-area="msg" aria-live="polite"></div><div data-area="next"></div>';
      shell(html);

      // symbol bar: brackets and quotes are slow to find on a phone keyboard
      var lastEd = null, symRow = document.createElement('div'); symRow.className = 'nm-sym'; symRow.setAttribute('role', 'group'); symRow.setAttribute('aria-label', 'Symbol keys');
      ['<', '>', '/', '=', '"', "'", '(', ')', '{', '}', '[', ']', ';', ':', '#', '.'].forEach(function (ch) {
        var b = document.createElement('button'); b.type = 'button'; b.textContent = ch; b.setAttribute('aria-label', 'Insert ' + ch);
        b.addEventListener('mousedown', function (ev) { ev.preventDefault(); });
        b.addEventListener('click', function () {
          var t = lastEd || root.querySelector('.nm-ed'); if (!t) return;
          var a = t.selectionStart; t.value = t.value.slice(0, a) + ch + t.value.slice(t.selectionEnd); t.selectionStart = t.selectionEnd = a + 1; t.focus();
          t.dispatchEvent(new Event('input', { bubbles: true }));
        });
        symRow.appendChild(b);
      });
      var firstEd = root.querySelector('.nm-ed'); if (firstEd && !isBlank) firstEd.parentNode.insertBefore(symRow, firstEd.previousElementSibling);
      var eds = {}; root.querySelectorAll('.nm-ed').forEach(function (e) { eds[e.dataset.f] = e; e.addEventListener('focus', function () { lastEd = e; });
        e.addEventListener('input', function () { setDraft(idx, e.dataset.f, e.value); });
        e.addEventListener('keydown', function (ev) { if ((ev.ctrlKey || ev.metaKey) && ev.key === 'Enter') { ev.preventDefault(); var cb = root.querySelector('[data-act=check]'); if (cb && !cb.disabled) cb.click(); } });
        e.addEventListener('keydown', function (ev) {
          if (ev.key === 'Tab' && !ev.shiftKey) { ev.preventDefault(); var s = e.selectionStart; e.value = e.value.slice(0, s) + '  ' + e.value.slice(e.selectionEnd); e.selectionStart = e.selectionEnd = s + 2; }
        });
      });
      var frame = root.querySelector('.nm-frame'), msg = root.querySelector('[data-area=msg]');
      var get = function () { var o = {}; Object.keys(eds).forEach(function (k) { o[k] = eds[k].value; }); return o; };
      var timer = null;
      if (!hasJs) Object.keys(eds).forEach(function (k) { eds[k].addEventListener('input', function () { clearTimeout(timer); timer = setTimeout(function () { loadFrame(frame, get()); }, 450); }); });
      loadFrame(frame, get());
      function composeGaps() {
        fields.forEach(function (f) {
          var box = root.querySelector('.nm-gapcode[data-f="' + f[0] + '"]'); if (!box) return;
          var out = ''; box.childNodes.forEach(function (n) { out += n.nodeType === 3 ? n.nodeValue : (n.classList && n.classList.contains('nm-gap') ? n.value : n.textContent); });
          eds[f[0]].value = out; eds[f[0]].dispatchEvent(new Event('input', { bubbles: true }));
        });
      }
      if (isBlank) {
        var holder = document.createElement('div'); holder.className = 'nm-gaps';
        fields.forEach(function (f) {
          var lab = document.createElement('div'); lab.className = 'nm-lab'; lab.textContent = f[1]; holder.appendChild(lab);
          var pre = document.createElement('pre'); pre.className = 'nm-code nm-gapcode'; pre.dataset.f = f[0];
          String(tpl[f[0]]).split('___').forEach(function (piece, k, arr) {
            pre.appendChild(document.createTextNode(piece));
            if (k < arr.length - 1) { var inp = document.createElement('input'); inp.type = 'text'; inp.className = 'nm-gap'; inp.size = 8; inp.spellcheck = false; inp.autocomplete = 'off'; inp.autocapitalize = 'off';
              inp.setAttribute('aria-label', 'Gap to fill in'); inp.addEventListener('input', composeGaps); pre.appendChild(inp); }
          });
          holder.appendChild(pre);
        });
        var firstTa = root.querySelector('.nm-ed'); firstTa.parentNode.insertBefore(holder, firstTa);
        composeGaps();
      }
      var hb = wireHints(step, root.querySelector('[data-act=hint]'), root.querySelector('[data-area=hints]'));
      var showBtn = root.querySelector('[data-act=show]');
      root.querySelector('[data-act=run]').addEventListener('click', function () { loadFrame(frame, get()); });
      showBtn.addEventListener('click', function () {
        var sol = step.solution || {}; state.assisted++; state.sAssist++;
        if (isBlank) { var gi = root.querySelectorAll('.nm-gap'); (step.gaps_solution || []).forEach(function (v, k) { if (gi[k]) gi[k].value = v; }); composeGaps(); }
        else Object.keys(eds).forEach(function (k) { if (sol[k] !== undefined) eds[k].value = sol[k]; });
        msg.innerHTML = '<div class="nm-msg info">Here is one way to do it. Read it, then press <strong>Check my code</strong> to continue.</div>';
        loadFrame(frame, get());
      });
      root.querySelector('[data-act=check]').addEventListener('click', function () {
        var f = get(); bumpCheck();
        loadFrame(frame, f, function () {
          var tests = step.tests || [];
          var codeTests = tests.filter(function (t) { return t.kind === 'code_has' || t.kind === 'code_hasnt'; });
          var domTests = tests.filter(function (t) { return !(t.kind === 'code_has' || t.kind === 'code_hasnt'); });
          var finish = function (d) {
            var byId = {}; if (d) d.results.forEach(function (r) { byId[r.id] = r.ok; });
            codeTests.forEach(function (t) { byId[t.id] = evalCodeTest(t, f); });
            var allOk = true;
            tests.forEach(function (t) {
              var li = root.querySelector('li[data-id="' + t.id + '"]'); var pass = !!byId[t.id];
              if (!pass) allOk = false;
              if (li) { li.className = pass ? 'ok' : 'no'; li.querySelector('i').className = pass ? 'fas fa-circle-check' : 'fas fa-circle-xmark'; }
            });
            if (domTests.length && !d) { allOk = false; msg.innerHTML = '<div class="nm-msg bad">Your code did not finish running. Check for a typo or a loop that never ends, then try again.</div>'; bad(); return; }
            if (allOk) {
              ok(); msg.innerHTML = '<div class="nm-msg good"><i class="fas fa-circle-check"></i> ' + (step.success_msg || 'Step complete!') + '</div>';
              root.querySelector('[data-act=check]').disabled = true;
              clearDrafts(idx);
              var nxt = root.querySelector('[data-area=next]');
              var last = state.i + 1 >= mission.steps.length;
              nxt.innerHTML = '<div class="nm-btns"><button class="nm-btn go" data-act="next">' + (last ? 'Finish mission' : 'Next step') + ' <i class="fas fa-arrow-right"></i></button></div>';
              nxt.querySelector('button').addEventListener('click', nextStep);
            } else {
              bad(); fails++;
              var extra = d && d.errors && d.errors.length ? ' ' + friendlyError(d.errors[0]) : '';
              msg.innerHTML = '<div class="nm-msg bad">Not quite yet. The red items show what is still missing.' + extra + '</div>';
              if (fails >= 3) {
                showBtn.disabled = false; showBtn.title = 'Show one way to solve it';
                if (!state.stuckSent && opts.onStep) { state.stuckSent = true; var cs = mission.steps[state.i]; opts.onStep({ index: state.i, skill: cs.skill || mission.skill || '', type: cs.type, checks: state.sChecks, hints: state.sHints, assisted: state.sAssist, stuck: true }); }
              }
              if (fails >= 2 && hb.left() > 0 && !state._autoHint) { /* gentle nudge */ msg.innerHTML += '<div class="nm-msg info">Stuck? Press <strong>Hint</strong>.</div>'; }
            }
          };
          if (domTests.length) sandboxTest(frame, domTests, finish); else finish({ results: [], errors: [] });
        });
      });
    }

    // ---- predict step
    function renderPredict(step, idx) {
      state.hintShown = 0;
      shell('<p class="nm-prompt"><strong>Step ' + (idx + 1) + ' of ' + mission.steps.length + ' · Predict.</strong> ' + (promptFor(step) || 'What will this show?') + '</p>' +
        '<pre class="nm-code">' + esc(step.code) + '</pre>' +
        '<label class="nm-lab" for="nmAns">Your prediction</label><input id="nmAns" class="nm-in" type="text" autocomplete="off" placeholder="Type what you think appears">' +
        '<div class="nm-btns"><button class="nm-btn go" data-act="check"><i class="fas fa-circle-check"></i> Lock in my answer</button><button class="nm-btn warn" data-act="hint"></button></div>' +
        '<div data-area="hints"></div><div data-area="msg" aria-live="polite"></div>' +
        '<iframe class="nm-frame" sandbox="allow-scripts" title="What really happens" style="display:none"></iframe><div data-area="next"></div>');
      wireHints(step, root.querySelector('[data-act=hint]'), root.querySelector('[data-area=hints]'));
      var input = root.querySelector('#nmAns'), msg = root.querySelector('[data-area=msg]'), frame = root.querySelector('.nm-frame');
      var go = function () {
        var guess = norm(input.value); if (!guess) { input.focus(); return; }
        bumpCheck();
        var answers = (Array.isArray(step.answer) ? step.answer : [step.answer]).map(norm);
        var right = answers.indexOf(guess) !== -1;
        var reveal = function () {
          frame.style.display = 'block';
          loadFrame(frame, { html: (step.lang === 'html' ? step.code : (step.html || '')) + '<pre id="out" style="background:#f0f5ff;padding:6px;border-radius:8px;margin:6px 0 0"></pre>', js: PRE + (step.setup || '') + (step.lang === 'js' || !step.lang ? step.code : ''), css: step.css });
          var last = state.i + 1 >= mission.steps.length;
          var nxt = root.querySelector('[data-area=next]');
          nxt.innerHTML = '<div class="nm-btns"><button class="nm-btn go">' + (last ? 'Finish mission' : 'Next step') + ' <i class="fas fa-arrow-right"></i></button></div>';
          nxt.querySelector('button').addEventListener('click', nextStep);
          input.disabled = true; root.querySelector('[data-act=check]').disabled = true;
        };
        if (right) { ok(); msg.innerHTML = '<div class="nm-msg good"><i class="fas fa-circle-check"></i> Yes! ' + (step.explain || '') + '</div>'; reveal(); }
        else {
          bad(); state.predictMiss = (state.predictMiss || 0) + 1;
          if (state.predictMiss >= 2) {
            msg.innerHTML = '<div class="nm-msg info">Not this time. ' + (step.explain || '') + ' Watch what really happens below.</div>'; state.assisted++; state.sAssist++; state.predictMiss = 0; reveal();
          } else msg.innerHTML = '<div class="nm-msg bad">Not quite. Read the code again, line by line, then try once more.</div>';
        }
      };
      root.querySelector('[data-act=check]').addEventListener('click', go);
      input.addEventListener('keydown', function (e) { if (e.key === 'Enter') go(); });
    }

    // ---- order step
    function renderOrder(step, idx) {
      state.hintShown = 0;
      var correct = step.lines.slice(), order = correct.map(function (_, k) { return k; });
      // deterministic shuffle that never starts solved
      var seed = 7 + idx * 13; var tries = 0;
      do {
        for (var k = order.length - 1; k > 0; k--) { seed = (seed * 9301 + 49297) % 233280; var j = seed % (k + 1); var t = order[k]; order[k] = order[j]; order[j] = t; }
        tries++;
      } while (order.every(function (v, p) { return v === p; }) && tries < 5);
      var status = [];
      function draw() {
        var ul = root.querySelector('.nm-lines'); ul.innerHTML = '';
        order.forEach(function (lineIdx, pos) {
          var li = document.createElement('li'); li.className = 'nm-line' + (status[pos] === true ? ' ok' : status[pos] === false ? ' no' : '');
          li.innerHTML = '<button class="nm-mv" aria-label="Move line up" ' + (pos === 0 ? 'disabled' : '') + '>&uarr;</button>' +
            '<button class="nm-mv" aria-label="Move line down" ' + (pos === order.length - 1 ? 'disabled' : '') + '>&darr;</button><code>' + esc(correct[lineIdx]) + '</code>';
          var b = li.querySelectorAll('button');
          b[0].addEventListener('click', function () { var x = order[pos]; order[pos] = order[pos - 1]; order[pos - 1] = x; status = []; draw(); });
          b[1].addEventListener('click', function () { var x = order[pos]; order[pos] = order[pos + 1]; order[pos + 1] = x; status = []; draw(); });
          ul.appendChild(li);
        });
      }
      shell('<p class="nm-prompt"><strong>Step ' + (idx + 1) + ' of ' + mission.steps.length + ' · Put it in order.</strong> ' + promptFor(step) + '</p>' +
        '<ul class="nm-lines"></ul><div class="nm-btns"><button class="nm-btn go" data-act="check"><i class="fas fa-circle-check"></i> Check the order</button><button class="nm-btn warn" data-act="hint"></button></div>' +
        '<div data-area="hints"></div><div data-area="msg" aria-live="polite"></div><div data-area="next"></div>');
      wireHints(step, root.querySelector('[data-act=hint]'), root.querySelector('[data-area=hints]'));
      draw();
      var msg = root.querySelector('[data-area=msg]');
      root.querySelector('[data-act=check]').addEventListener('click', function () {
        bumpCheck();
        // lines with identical text can swap places and still be right
        status = order.map(function (lineIdx, pos) { return correct[lineIdx] === correct[pos]; });
        draw();
        if (status.every(Boolean)) {
          ok(); msg.innerHTML = '<div class="nm-msg good"><i class="fas fa-circle-check"></i> ' + (step.explain || 'Perfect order!') + '</div>';
          root.querySelector('[data-act=check]').disabled = true;
          var last = state.i + 1 >= mission.steps.length; var nxt = root.querySelector('[data-area=next]');
          nxt.innerHTML = '<div class="nm-btns"><button class="nm-btn go">' + (last ? 'Finish mission' : 'Next step') + ' <i class="fas fa-arrow-right"></i></button></div>';
          nxt.querySelector('button').addEventListener('click', nextStep);
        } else { bad(); msg.innerHTML = '<div class="nm-msg bad">Green lines are in the right place. Move the red ones.</div>'; }
      });
    }



    // ---- anatomy step: tap each coloured part of a snippet to learn what it is
    function renderAnatomy(step, idx) {
      state.hintShown = 0; var seen = {}, total = step.parts.filter(function (p) { return p.k; }).length, count = 0;
      var code = step.parts.map(function (p, k) {
        return p.k ? '<button type="button" class="nm-part" data-k="' + k + '" style="--pc:' + (p.c || '#6c4bb8') + '">' + esc(p.t) + '</button>' : esc(p.t);
      }).join('');
      shell('<p class="nm-prompt"><strong>Step ' + (idx + 1) + ' of ' + mission.steps.length + ' · Explore.</strong> ' + promptFor(step) + '</p>' +
        '<pre class="nm-code nm-anat">' + code + '</pre>' +
        '<div class="nm-explain" aria-live="polite"><em>Tap a coloured part.</em></div>' +
        '<p class="nm-lab" data-area="count">Explored 0 of ' + total + '</p><div data-area="next"></div>');
      var box = root.querySelector('.nm-explain');
      root.querySelectorAll('.nm-part').forEach(function (b) {
        b.addEventListener('click', function () {
          var p = step.parts[b.dataset.k]; root.querySelectorAll('.nm-part').forEach(function (x) { x.classList.remove('on'); }); b.classList.add('on');
          box.style.borderLeftColor = p.c || '#6c4bb8'; box.innerHTML = '<strong>' + esc(p.k) + '</strong><br>' + p.e;
          if (!seen[b.dataset.k]) { seen[b.dataset.k] = 1; count++; b.classList.add('seen'); root.querySelector('[data-area=count]').textContent = 'Explored ' + count + ' of ' + total; }
          if (count === total && !root.querySelector('[data-area=next] button')) {
            ok(); var last = state.i + 1 >= mission.steps.length, nxt = root.querySelector('[data-area=next]');
            nxt.innerHTML = '<div class="nm-msg good">' + (step.success_msg || 'You know every part now.') + '</div><div class="nm-btns"><button class="nm-btn go">' + (last ? 'Finish mission' : 'Next') + ' <i class="fas fa-arrow-right"></i></button></div>';
            nxt.querySelector('button').addEventListener('click', nextStep);
          }
        });
      });
    }

    // ---- robot step: build a program with blocks, watch it run (no typing needed)
    var ROBOT_SVG = '<svg viewBox="0 0 34 34" aria-hidden="true"><rect x="5" y="9" width="24" height="19" rx="6" fill="#2f6fc0"/><rect x="9" y="13" width="16" height="9" rx="4" fill="#fff"/><circle cx="14" cy="17.5" r="2.2" fill="#1e3a5f"/><circle cx="20" cy="17.5" r="2.2" fill="#1e3a5f"/><rect x="16" y="3" width="2" height="6" fill="#2f6fc0"/><circle cx="17" cy="3" r="2.2" fill="#FFB347"/></svg>';
    var STAR_SVG = '<svg viewBox="0 0 34 34" aria-hidden="true"><polygon points="17,3 21,13 32,13 23,20 26,31 17,24 8,31 11,20 2,13 13,13" fill="#FFB347" stroke="#a35f10" stroke-width="1.5"/></svg>';
    var ARROW = { up: '↑ Up', down: '↓ Down', left: '← Left', right: '→ Right' };
    function blockLabel(it) { return typeof it === 'object' ? 'Repeat ' + it.r + '×' : ARROW[it]; }
    function renderRobot(step, idx) {
      state.hintShown = 0; var fails = 0, running = false;
      var g = parseGrid(step.grid), prog = [], cmds = step.commands || ['up', 'down', 'left', 'right'];
      var cells = '';
      for (var y = 0; y < g.H; y++) for (var x = 0; x < g.W; x++) {
        var cls = g.walls[x + ',' + y] ? 'wall' : (g.goal.x === x && g.goal.y === y ? 'goal' : '');
        cells += '<div class="nm-cell ' + cls + '" data-x="' + x + '" data-y="' + y + '">' + (cls === 'goal' ? STAR_SVG : '') + '</div>';
      }
      shell('<p class="nm-prompt"><strong>Step ' + (idx + 1) + ' of ' + mission.steps.length + ' · Program the robot.</strong> ' + promptFor(step) + '</p>' +
        '<div class="nm-grid" role="img" aria-label="A grid. The robot starts at column ' + (g.start.x + 1) + ', row ' + (g.start.y + 1) + '. The star is at column ' + (g.goal.x + 1) + ', row ' + (g.goal.y + 1) + '." style="grid-template-columns:repeat(' + g.W + ',52px)">' + cells + '</div>' +
        '<div class="nm-lab">Tap blocks to add them</div><div class="nm-pal">' +
        cmds.map(function (c) { return '<button type="button" class="nm-blk" data-c="' + c + '">' + ARROW[c] + '</button>'; }).join('') +
        (step.repeats || []).map(function (n) { return '<button type="button" class="nm-blk rep" data-r="' + n + '">Repeat ' + n + '×</button>'; }).join('') + '</div>' +
        '<div class="nm-lab">Your program' + (step.max_blocks ? ' (use at most ' + step.max_blocks + ' blocks)' : '') + ' — tap a block to remove it</div><div class="nm-prog" aria-live="polite"></div>' +
        '<div class="nm-btns"><button class="nm-btn go" data-act="run"><i class="fas fa-play"></i> Run program</button>' +
        '<button class="nm-btn alt" data-act="clear">Clear</button><button class="nm-btn warn" data-act="hint"></button>' +
        '<button class="nm-btn alt" data-act="show" disabled title="Unlocks after 3 tries"><i class="fas fa-eye"></i> Show me</button></div>' +
        '<div data-area="hints"></div><div data-area="msg" aria-live="polite"></div><div data-area="next"></div>');
      var hb = wireHints(step, root.querySelector('[data-act=hint]'), root.querySelector('[data-area=hints]'));
      var progEl = root.querySelector('.nm-prog'), msg = root.querySelector('[data-area=msg]'), showBtn = root.querySelector('[data-act=show]');
      function cell(x, y) { return root.querySelector('.nm-cell[data-x="' + x + '"][data-y="' + y + '"]'); }
      function placeRobot(x, y, bump) {
        root.querySelectorAll('.nm-cell').forEach(function (c) { c.classList.remove('bump'); var r = c.querySelector('.rb'); if (r) r.remove(); });
        var c = cell(x, y); if (!c) return;
        var s = document.createElement('span'); s.className = 'rb'; s.innerHTML = ROBOT_SVG; c.appendChild(s); if (bump) c.classList.add('bump');
      }
      function drawProg(nowIdx) {
        progEl.innerHTML = prog.length ? '' : '<span style="color:#55688a;font-weight:700;align-self:center">Empty. Tap a block above.</span>';
        prog.forEach(function (it, k) {
          var b = document.createElement('button'); b.type = 'button'; b.className = 'nm-chip' + (typeof it === 'object' ? ' rep' : '') + (k === nowIdx ? ' now' : '');
          b.setAttribute('aria-label', 'Remove ' + blockLabel(it)); b.textContent = blockLabel(it) + ' ×';
          b.addEventListener('click', function () { if (running) return; prog.splice(k, 1); drawProg(); });
          progEl.appendChild(b);
        });
      }
      function nextBtn() {
        var last = state.i + 1 >= mission.steps.length, nxt = root.querySelector('[data-area=next]');
        nxt.innerHTML = '<div class="nm-btns"><button class="nm-btn go">' + (last ? 'Finish mission' : 'Next level') + ' <i class="fas fa-arrow-right"></i></button></div>';
        nxt.querySelector('button').addEventListener('click', nextStep);
      }
      root.querySelectorAll('.nm-blk').forEach(function (b) {
        b.addEventListener('click', function () {
          if (running) return;
          if (step.max_blocks && prog.length >= step.max_blocks + 2) return;
          prog.push(b.dataset.r ? { r: parseInt(b.dataset.r, 10) } : b.dataset.c); drawProg();
        });
      });
      root.querySelector('[data-act=clear]').addEventListener('click', function () { if (!running) { prog = []; drawProg(); placeRobot(g.start.x, g.start.y); msg.innerHTML = ''; } });
      showBtn.addEventListener('click', function () {
        if (running) return; state.assisted++; state.sAssist++;
        prog = step.solution.slice(); drawProg(); placeRobot(g.start.x, g.start.y);
        msg.innerHTML = '<div class="nm-msg info">Here is one way. Read it block by block, then press <strong>Run program</strong>.</div>';
      });
      root.querySelector('[data-act=run]').addEventListener('click', function () {
        if (running) return;
        if (!prog.length) { msg.innerHTML = '<div class="nm-msg bad">Add some blocks first.</div>'; bad(); return; }
        bumpCheck(); running = true; msg.innerHTML = '';
        var sim = simulate(g, prog), k = 0, reduce = false;
        try { reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches; } catch (e) {}
        function finish() {
          running = false;
          var tooMany = step.max_blocks && prog.length > step.max_blocks;
          if (sim.error) { bad(); fails++; msg.innerHTML = '<div class="nm-msg bad">' + sim.error + '</div>'; }
          else if (tooMany) { bad(); fails++; msg.innerHTML = '<div class="nm-msg bad">It reached the star, but you used ' + prog.length + ' blocks. Use at most ' + step.max_blocks + '. Try a Repeat block.</div>'; if (!sim.reached) msg.innerHTML = '<div class="nm-msg bad">Too many blocks, and the robot did not reach the star. Try a Repeat block.</div>'; }
          else if (sim.reached) { ok(); msg.innerHTML = '<div class="nm-msg good"><i class="fas fa-circle-check"></i> ' + (step.success_msg || 'The robot reached the star!') + '</div>'; clearDrafts(idx); root.querySelector('[data-act=run]').disabled = true; nextBtn(); return; }
          else {
            bad(); fails++;
            var bumped = sim.frames.filter(function (f) { return f.bump; })[0];
            msg.innerHTML = '<div class="nm-msg bad">' + (bumped ? 'The robot bumped into a wall or the edge (shown in red). Follow your blocks one at a time and find where the path goes wrong.' : 'The robot stopped on the wrong square. Count the squares between the robot and the star.') + '</div>';
          }
          if (fails >= 3) {
            showBtn.disabled = false;
            if (!state.stuckSent && opts.onStep) { state.stuckSent = true; var cs = mission.steps[state.i]; opts.onStep({ index: state.i, skill: cs.skill || mission.skill || '', type: cs.type, checks: state.sChecks, hints: state.sHints, assisted: state.sAssist, stuck: true }); }
          }
        }
        function frame() {
          if (k >= sim.frames.length) return finish();
          var f = sim.frames[k++]; placeRobot(f.x, f.y, f.bump); drawProg(f.block >= 0 ? f.block : undefined);
          if (reduce) frame(); else setTimeout(frame, 330);
        }
        frame();
      });
      drawProg(); placeRobot(g.start.x, g.start.y);
    }

    function renderWorked() {
      var w = mission.worked, parts = [['html', 'HTML'], ['css', 'CSS'], ['js', 'JavaScript']].filter(function (f) { return w[f[0]]; });
      shell('<div class="nm-worked"><h3><i class="fas fa-chalkboard-user"></i> ' + esc(w.title || 'Watch one first') + '</h3>' +
        '<p class="nm-prompt">' + (w.explain || '') + '</p>' +
        parts.map(function (f) { return '<div class="nm-lab">' + f[1] + '</div><pre class="nm-code">' + esc(w[f[0]]) + '</pre>'; }).join('') +
        '<iframe class="nm-frame" sandbox="allow-scripts" title="Worked example result"></iframe></div>' +
        '<div class="nm-btns"><button class="nm-btn go" data-act="start">I get it, start the mission <i class="fas fa-arrow-right"></i></button></div>');
      loadFrame(root.querySelector('.nm-frame'), { html: w.html, css: w.css, js: w.js });
      root.querySelector('[data-act=start]').addEventListener('click', function () { state.workedSeen = true; render(); });
    }

    function render() {
      if (state.i >= mission.steps.length) return finishMission();
      if (state.i === 0 && mission.worked && !state.workedSeen) return renderWorked();
      state.sChecks = 0; state.sHints = 0; state.sAssist = 0; state.stuckSent = false; state.predictMiss = 0;
      var step = mission.steps[state.i];
      if (step.type === 'anatomy') renderAnatomy(step, state.i);
      else if (step.type === 'robot') renderRobot(step, state.i);
      else if (step.type === 'predict') renderPredict(step, state.i);
      else if (step.type === 'order') renderOrder(step, state.i);
      else renderCode(step, state.i);
    }

    if (wasDone && !opts.forceReplay) {
      shell('<div class="nm-done"><i class="fas fa-circle-check" style="font-size:2.2rem;color:#1e5f4b"></i><h3>Mission complete</h3>' +
        '<p style="color:#55688a;margin:0">You already finished this mission.</p><div class="nm-btns" style="justify-content:center;margin-top:.8rem"><button class="nm-btn alt" data-act="replay"><i class="fas fa-rotate-left"></i> Play again</button></div></div>');
      root.querySelector('[data-act=replay]').addEventListener('click', function () { render(); });
      var ev0 = new CustomEvent('nexa:mission-complete', { detail: { restored: true }, bubbles: true }); root.dispatchEvent(ev0);
      if (opts.onComplete) opts.onComplete({ restored: true });
    } else render();
    return { state: state, render: render };
  }

  global.NexaMission = { parseGrid: parseGrid, simulate: simulate, friendlyError: friendlyError, masteryOf: masteryOf, mount: mount, normalize: normalize, stripComments: stripComments, buildDoc: buildDoc, evalCodeTest: evalCodeTest };
})(window);
