/* 필터 URL 계약. src/urlstate.py 와 키를 맞춘다.
   지원: ?q=&region=&field=&deadline=&org=&amount=
   입찰: ?q=&kind=&deadline=&org=&amount=&region= */
(function (w) {
  function lists(sp, keys) {
    var out = [], seen = {};
    keys.forEach(function (k) {
      (sp.getAll(k) || []).forEach(function (raw) {
        String(raw || '').split(',').forEach(function (p) {
          p = p.trim();
          if (p && !seen[p]) { seen[p] = 1; out.push(p); }
        });
      });
    });
    return out;
  }
  function setList(sp, key, arr) {
    if (arr && arr.length) sp.set(key, arr.join(','));
    else sp.delete(key);
  }
  function qsOf(sp) {
    var s = sp.toString();
    return s ? ('?' + s) : '';
  }

  function parseGrant(search) {
    var sp = new URLSearchParams(String(search || '').replace(/^\?/, ''));
    return {
      q: (sp.get('q') || '').trim(),
      region: lists(sp, ['region']),
      field: lists(sp, ['field', 'category']),
      deadline: lists(sp, ['deadline', 'due']),
      org: lists(sp, ['org']),
      amount: lists(sp, ['amount']),
      district: lists(sp, ['district']),
      src: (sp.get('src') || '').trim(),
      from: sp.get('from') || '',
      to: sp.get('to') || '',
      sort: sp.get('sort') || 'dday',
      open: sp.get('open') !== '0'
    };
  }

  function serializeGrant(st, locked) {
    locked = locked || {};
    var sp = new URLSearchParams();
    if (st.q) sp.set('q', st.q);
    if (!locked.region) setList(sp, 'region', st.region);
    if (!locked.field) setList(sp, 'field', st.field);
    if (!locked.deadline) setList(sp, 'deadline', st.deadline);
    if (!locked.org) setList(sp, 'org', st.org);
    if (!locked.amount) setList(sp, 'amount', st.amount);
    if (!locked.district) setList(sp, 'district', st.district);
    if (!locked.src && st.src) sp.set('src', st.src);
    if (st.from) sp.set('from', st.from);
    if (st.to) sp.set('to', st.to);
    if (st.sort && st.sort !== 'dday') sp.set('sort', st.sort);
    if (st.open === false) sp.set('open', '0');
    return qsOf(sp);
  }

  function parseBid(search) {
    var sp = new URLSearchParams(String(search || '').replace(/^\?/, ''));
    return {
      q: (sp.get('q') || '').trim(),
      kind: lists(sp, ['kind']),
      deadline: lists(sp, ['deadline', 'due']),
      org: lists(sp, ['org']),
      amount: lists(sp, ['amount']),
      region: lists(sp, ['region']),
      sort: sp.get('sort') || 'dday',
      open: sp.get('open') !== '0'
    };
  }

  function serializeBid(st, locked) {
    locked = locked || {};
    var sp = new URLSearchParams();
    if (st.q) sp.set('q', st.q);
    if (!locked.kind) setList(sp, 'kind', st.kind);
    if (!locked.deadline) setList(sp, 'deadline', st.deadline);
    if (!locked.org) setList(sp, 'org', st.org);
    if (!locked.amount) setList(sp, 'amount', st.amount);
    if (!locked.region) setList(sp, 'region', st.region);
    if (st.sort && st.sort !== 'dday') sp.set('sort', st.sort);
    if (st.open === false) sp.set('open', '0');
    return qsOf(sp);
  }

  function describeGrant(st) {
    var bits = [];
    if (st.q) bits.push('검색 ' + st.q);
    [['region', '지역'], ['field', '분야'], ['org', '기관'],
     ['deadline', '기간'], ['amount', '금액'], ['district', '시군구']].forEach(function (p) {
      if (st[p[0]] && st[p[0]].length) bits.push(p[1] + ' ' + st[p[0]].join('·'));
    });
    if (st.src === 'kstartup') bits.push('출처 K-Startup');
    else if (st.src === 'bizinfo') bits.push('출처 기업마당');
    if (st.from || st.to) bits.push('날짜 ' + (st.from || '') + '~' + (st.to || ''));
    if (st.open === false) bits.push('마감 포함');
    return bits.join(' / ') || '전체';
  }

  function describeBid(st) {
    var bits = [];
    if (st.q) bits.push('검색 ' + st.q);
    [['kind', '종류'], ['region', '지역'], ['org', '발주기관'],
     ['deadline', '기간'], ['amount', '추정가격']].forEach(function (p) {
      if (st[p[0]] && st[p[0]].length) bits.push(p[1] + ' ' + st[p[0]].join('·'));
    });
    if (st.open === false) bits.push('마감 포함');
    return bits.join(' / ') || '입찰 전체';
  }

  function bindDialog(overlay, panel, onClose) {
    if (!overlay || overlay.dataset.a11yBound) return;
    overlay.dataset.a11yBound = '1';
    overlay.addEventListener('keydown', function (e) {
      if (overlay.hidden) return;
      if (e.key === 'Escape') {
        e.preventDefault();
        if (onClose) onClose();
        return;
      }
      if (e.key !== 'Tab' || !panel) return;
      var nodes = [].slice.call(panel.querySelectorAll(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
      )).filter(function (el) {
        return !el.disabled && el.getAttribute('aria-hidden') !== 'true';
      });
      if (!nodes.length) return;
      var first = nodes[0], last = nodes[nodes.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault(); last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault(); first.focus();
      }
    });
  }

  function currentQ() {
    var live = document.getElementById('f-q') || document.getElementById('bid-q');
    if (live && live.value.trim()) return live.value.trim();
    var head = document.querySelector('.hsearch input[name="q"]');
    if (head && head.value.trim()) return head.value.trim();
    return (new URLSearchParams(location.search).get('q') || '').trim();
  }

  function escHtml(s) {
    return String(s == null ? '' : s).replace(/[<>&"]/g, function (c) {
      return { '<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;' }[c];
    });
  }
  function toast(msg, opts) {
    opts = opts || {};
    var old = document.getElementById('mp-toast');
    if (old) old.remove();
    var el = document.createElement('div');
    el.id = 'mp-toast';
    el.className = 'mp-toast';
    el.setAttribute('role', 'status');
    el.setAttribute('aria-live', 'polite');
    el.style.cssText = 'position:fixed;left:14px;right:14px;bottom:14px;z-index:100;max-width:420px;margin:0 auto;background:#1A1A1A;color:#fff;padding:12px 16px;border-radius:12px;box-shadow:0 6px 24px rgba(0,0,0,.22)';
    var html = '<p>' + escHtml(msg) + '</p>';
    if (opts.href) {
      html += '<p><a href="' + escHtml(opts.href) + '">' +
        escHtml(opts.label || '열기') + '</a></p>';
    }
    el.innerHTML = html;
    document.body.appendChild(el);
    requestAnimationFrame(function () { el.classList.add('in'); });
    clearTimeout(toast._t);
    toast._t = setTimeout(function () {
      el.classList.remove('in');
      setTimeout(function () { if (el.parentNode) el.remove(); }, 200);
    }, opts.ms || 3200);
    return el;
  }

  function isTyping(el) {
    if (!el) return false;
    var t = (el.tagName || '').toLowerCase();
    return t === 'input' || t === 'textarea' || t === 'select' || el.isContentEditable;
  }
  function helpBox() { return document.getElementById('keys-help'); }
  function closeHelp() {
    var box = helpBox();
    if (!box) return;
    box.hidden = true;
  }
  function openHelp() {
    var box = helpBox();
    if (!box) return;
    box.hidden = false;
    var sheet = box.querySelector('.keys-sheet');
    if (sheet && sheet.focus) sheet.focus();
  }
  function toggleHelp() {
    var box = helpBox();
    if (!box) return;
    if (box.hidden) openHelp(); else closeHelp();
  }
  function bindKeys() {
    var box = helpBox();
    if (box) {
      box.addEventListener('click', function (e) { if (e.target === box) closeHelp(); });
      var x = document.getElementById('keys-x');
      if (x) x.addEventListener('click', closeHelp);
    }
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') {
        closeHelp();
        return;
      }
      if (isTyping(e.target)) return;
      if (e.key === '?' || (e.key === '/' && e.shiftKey)) {
        e.preventDefault();
        toggleHelp();
        return;
      }
      if (e.key === '/' && !e.shiftKey) {
        e.preventDefault();
        var inp = document.getElementById('f-q') || document.getElementById('bid-q') ||
          document.querySelector('.hsearch input');
        if (inp) inp.focus();
      }
    });
  }

  function bindModeSwitch() {
    document.querySelectorAll('.mode-switch a[data-mode]').forEach(function (a) {
      a.addEventListener('click', function (e) {
        var q = currentQ();
        if (!q) return;
        var href = a.getAttribute('href') || '/';
        if (/[?&]q=/.test(href)) return;
        e.preventDefault();
        var join = href.indexOf('?') >= 0 ? '&' : '?';
        location.href = href + join + 'q=' + encodeURIComponent(q);
      });
    });
    var q = currentQ();
    if (!q) return;
    document.querySelectorAll('.hsearch input[name="q"]').forEach(function (inp) {
      if (!inp.value) inp.value = q;
    });
  }

  w.MagampanState = {
    parseGrant: parseGrant,
    serializeGrant: serializeGrant,
    parseBid: parseBid,
    serializeBid: serializeBid,
    describeGrant: describeGrant,
    describeBid: describeBid,
    bindDialog: bindDialog,
    currentQ: currentQ
  };
  w.MagampanToast = toast;

  if (typeof document !== 'undefined') {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', function () {
        bindModeSwitch();
        bindKeys();
      });
    } else {
      bindModeSwitch();
      bindKeys();
    }
  }
})(window);
