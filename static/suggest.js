/* 검색 제안. 페이지에 이미 있는 지역·분야·기관만 쓴다. 외부 API 없음. */
(function (w) {
  function esc(s) {
    return String(s == null ? '' : s).replace(/[<>&"]/g, function (c) {
      return { '<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;' }[c];
    });
  }

  function dist(a, b) {
    a = String(a || ''); b = String(b || '');
    if (a === b) return 0;
    if (!a.length) return b.length;
    if (!b.length) return a.length;
    if (Math.abs(a.length - b.length) > 2) return 99;
    var prev = [];
    for (var j = 0; j <= b.length; j++) prev[j] = j;
    for (var i = 1; i <= a.length; i++) {
      var cur = [i];
      for (j = 1; j <= b.length; j++) {
        var cost = a.charAt(i - 1) === b.charAt(j - 1) ? 0 : 1;
        cur[j] = Math.min(cur[j - 1] + 1, prev[j] + 1, prev[j - 1] + cost);
      }
      prev = cur;
    }
    return prev[b.length];
  }

  function highlight(text, q) {
    var s = String(text || '');
    if (!q) return esc(s);
    var i = s.toLowerCase().indexOf(q.toLowerCase());
    if (i < 0) return esc(s);
    return esc(s.slice(0, i)) + '<mark>' + esc(s.slice(i, i + q.length)) + '</mark>' +
      esc(s.slice(i + q.length));
  }

  function uniq(items) {
    var seen = {}, out = [];
    items.forEach(function (it) {
      var k = (it.label || '') + '|' + (it.group || '');
      if (!it.label || seen[k]) return;
      seen[k] = 1;
      out.push(it);
    });
    return out;
  }

  function fromPage() {
    var items = [];
    function add(label, group) {
      if (label) items.push({ label: label, group: group || '검색' });
    }
    document.querySelectorAll('#f-opt-region .f-opt, [data-k="region"]').forEach(function (b) {
      add((b.dataset.v || b.textContent || '').trim(), '지역');
    });
    document.querySelectorAll('#f-opt-category .f-opt, [data-k="category"]').forEach(function (b) {
      add((b.dataset.v || (b.querySelector('b') || b).textContent || '').trim(), '분야');
    });
    document.querySelectorAll('[data-alert-keyword]').forEach(function (b) {
      add((b.getAttribute('data-alert-keyword') || b.textContent || '').trim(), '업종');
    });
    document.querySelectorAll('[data-bid-kind]').forEach(function (b) {
      add((b.textContent || '').trim(), '종류');
    });
    var slug = w.__SLUG__ || {};
    Object.keys(slug.region || {}).forEach(function (name) { add(name, '지역'); });
    Object.keys(slug.category || {}).forEach(function (name) { add(name, '분야'); });
    ['소상공인', '창업', '바우처', '정책자금', '수출', 'R&D', '인력', '융자'].forEach(function (k) {
      add(k, '키워드');
    });
    return uniq(items);
  }

  function rank(items, q) {
    q = (q || '').trim();
    if (q.length < 1) return [];
    var ql = q.toLowerCase();
    var hits = [];
    items.forEach(function (it) {
      var lab = it.label || '';
      var ll = lab.toLowerCase();
      var score = 80;
      if (ll === ql) score = 0;
      else if (ll.indexOf(ql) === 0) score = 1;
      else if (ll.indexOf(ql) > 0) score = 2;
      else {
        var d = dist(ll, ql);
        if (d <= 1 && ql.length >= 2) score = 10 + d;
        else if (d <= 2 && ql.length >= 4) score = 20 + d;
        else return;
      }
      hits.push({ item: it, score: score });
    });
    hits.sort(function (a, b) { return a.score - b.score || a.item.label.localeCompare(b.item.label, 'ko'); });
    var out = [];
    var seen = {};
    hits.forEach(function (h) {
      if (seen[h.item.label]) return;
      seen[h.item.label] = 1;
      out.push(h.item);
    });
    return out.slice(0, 8);
  }

  function bind(input, opts) {
    if (!input || input.dataset.suggestBound) return;
    input.dataset.suggestBound = '1';
    opts = opts || {};
    var extra = [];
    var box = document.createElement('div');
    box.className = 'suggest';
    box.hidden = true;
    box.setAttribute('role', 'listbox');
    box.id = (input.id || 'q') + '-suggest';
    input.setAttribute('aria-autocomplete', 'list');
    input.setAttribute('aria-controls', box.id);
    input.setAttribute('aria-expanded', 'false');
    var wrap = input.closest('.find-search, .hsearch') || input.parentNode;
    wrap.classList.add('has-suggest');
    wrap.appendChild(box);
    var idx = -1;
    var shown = [];

    function corpus() {
      return uniq(fromPage().concat(extra));
    }
    function close() {
      box.hidden = true;
      box.innerHTML = '';
      input.setAttribute('aria-expanded', 'false');
      idx = -1;
      shown = [];
    }
    function paint(items) {
      shown = items;
      idx = items.length ? 0 : -1;
      if (!items.length) { close(); return; }
      box.hidden = false;
      input.setAttribute('aria-expanded', 'true');
      var q = input.value.trim();
      box.innerHTML = items.map(function (it, i) {
        return '<button type="button" class="suggest-item' + (i === 0 ? ' is-on' : '') +
          '" role="option" data-i="' + i + '" aria-selected="' + (i === 0 ? 'true' : 'false') + '">' +
          '<b>' + highlight(it.label, q) + '</b><span>' + esc(it.group) + '</span></button>';
      }).join('');
    }
    function mark() {
      box.querySelectorAll('.suggest-item').forEach(function (el, i) {
        var on = i === idx;
        el.classList.toggle('is-on', on);
        el.setAttribute('aria-selected', on ? 'true' : 'false');
      });
    }
    function pick(it) {
      if (!it) return;
      input.value = it.label;
      input.dispatchEvent(new Event('input', { bubbles: true }));
      close();
      if (opts.onPick) opts.onPick(it.label);
    }

    input.addEventListener('input', function () {
      var q = input.value.trim();
      if (q.length < 1) { close(); return; }
      paint(rank(corpus(), q));
    });
    input.addEventListener('keydown', function (e) {
      if (box.hidden || !shown.length) {
        if (e.key === 'Enter' && opts.onEnter) opts.onEnter(input.value);
        return;
      }
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        idx = (idx + 1) % shown.length;
        mark();
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        idx = (idx - 1 + shown.length) % shown.length;
        mark();
      } else if (e.key === 'Enter') {
        if (idx >= 0 && shown[idx]) {
          e.preventDefault();
          pick(shown[idx]);
        }
      } else if (e.key === 'Escape') {
        close();
      }
    });
    box.addEventListener('mousedown', function (e) {
      var btn = e.target.closest('.suggest-item');
      if (!btn) return;
      e.preventDefault();
      pick(shown[parseInt(btn.dataset.i, 10)]);
    });
    input.addEventListener('blur', function () {
      setTimeout(close, 120);
    });
    return {
      add: function (labels, group) {
        (labels || []).forEach(function (lab) {
          extra.push({ label: lab, group: group || '기관' });
        });
        extra = uniq(extra);
      }
    };
  }

  function auto() {
    document.querySelectorAll('.hsearch input[name="q"]').forEach(function (inp) {
      bind(inp);
    });
  }
  if (typeof document !== 'undefined') {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', auto);
    else auto();
  }

  w.MagampanSuggest = { bind: bind, rank: rank, highlight: highlight, dist: dist };
})(window);
