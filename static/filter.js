/* 지역·분야·기관·금액·기간 필터 + 검색 + URL 상태 + 조건 저장.
   정적 페이지는 그대로 두고(SEO) 그 위에서 클라이언트 필터링만 한다. */
(function () {
  var root = document.getElementById('find');
  var board = document.getElementById('board');
  if (!root || !board) return;

  var PAGE = parseInt(board.dataset.limit, 10) || 20;
  var MORE = board.dataset.more || '';
  var PRESET_KEY = 'magampan.presets.v1';
  var ON_KEY = 'magampan.onboard.v1';
  var EMAIL = root.dataset.email || 'qwqw050009@gmail.com';
  var PERIODS = [
    { id: 'today', name: '오늘 마감', desc: '오늘 날짜형 마감' },
    { id: 'week', name: '이번 주', desc: 'D-0부터 D-7' },
    { id: 'always', name: '상시 접수', desc: '예산 소진시까지 등 날짜가 아닌 공고' },
    { id: 'range', name: '마감일 범위', desc: '시작·끝 날짜를 직접 고릅니다' }
  ];

  function emptyPicked() {
    return {
      region: new Set(), category: new Set(), org: new Set(),
      district: new Set(), amount: new Set(), period: new Set(),
      from: '', to: '', src: ''
    };
  }
  function clonePicked(p) {
    return {
      region: new Set(p.region), category: new Set(p.category), org: new Set(p.org),
      district: new Set(p.district), amount: new Set(p.amount), period: new Set(p.period),
      from: p.from, to: p.to, src: p.src
    };
  }
  function serialize(p) {
    return {
      region: [...p.region], category: [...p.category], org: [...p.org],
      district: [...p.district], amount: [...p.amount], period: [...p.period],
      from: p.from || '', to: p.to || '', src: p.src || ''
    };
  }
  function restore(s) {
    var p = emptyPicked();
    if (!s) return p;
    (s.region || []).forEach(function (v) { p.region.add(v); });
    (s.category || s.field || []).forEach(function (v) { p.category.add(v); });
    (s.org || []).forEach(function (v) { p.org.add(v); });
    (s.district || []).forEach(function (v) { p.district.add(v); });
    (s.amount || []).forEach(function (v) { p.amount.add(v); });
    (s.period || s.deadline || []).forEach(function (v) { p.period.add(v); });
    p.from = s.from || ''; p.to = s.to || ''; p.src = s.src || '';
    return p;
  }

  function lockedKeys() {
    return {
      region: !!root.dataset.region,
      field: !!root.dataset.category,
      district: !!root.dataset.district
    };
  }
  function applyPageLocks(p) {
    if (root.dataset.region) p.region.add(root.dataset.region);
    if (root.dataset.category) p.category.add(root.dataset.category);
    if (root.dataset.district) p.district.add(root.dataset.district);
    return p;
  }
  function toURLState() {
    return {
      q: (document.getElementById('f-q') && document.getElementById('f-q').value) || q,
      region: [...picked.region],
      field: [...picked.category],
      deadline: [...picked.period],
      org: [...picked.org],
      amount: [...picked.amount],
      district: [...picked.district],
      src: picked.src,
      from: picked.from,
      to: picked.to,
      sort: sortBy,
      open: openOnly
    };
  }

  var picked = emptyPicked();
  var draft = null;
  var openOnly = true, sortBy = 'dday', q = '', shown = PAGE, all = [], view = [];
  var touched = false, panelKind = '', orgQ = '', saveName = '';

  applyPageLocks(picked);

  var urlSt = window.MagampanState ? MagampanState.parseGrant(location.search) : null;
  if (urlSt) {
    if (urlSt.q || urlSt.region.length || urlSt.field.length || urlSt.deadline.length ||
        urlSt.org.length || urlSt.amount.length || urlSt.district.length ||
        urlSt.src || urlSt.from || urlSt.to || urlSt.sort !== 'dday' || urlSt.open === false) {
      picked = restore({
        region: urlSt.region, category: urlSt.field, org: urlSt.org,
        district: urlSt.district, amount: urlSt.amount, period: urlSt.deadline,
        from: urlSt.from, to: urlSt.to, src: urlSt.src
      });
      applyPageLocks(picked);
      q = urlSt.q.toLowerCase();
      openOnly = urlSt.open !== false;
      sortBy = urlSt.sort || 'dday';
      touched = true;
      var qInput = document.getElementById('f-q');
      if (qInput) qInput.value = urlSt.q;
      var so = document.getElementById('f-sort');
      if (so) so.value = sortBy;
      var oo = document.getElementById('f-openonly');
      if (oo) oo.checked = openOnly;
    }
  }

  var overlay = document.getElementById('f-overlay');
  var panel = document.getElementById('f-panel');
  var panelTitle = document.getElementById('f-panel-title');
  var panelBody = document.getElementById('f-panel-body');
  var panelFoot = document.getElementById('f-panel-foot');
  var chipBtns = root.querySelectorAll('.f-chip[data-panel]');

  function matchWith(a, p, onlyOpen, query) {
    if (onlyOpen && (a.st === 'closed' || a.d < 0)) return false;
    if (p.region.size && !p.region.has(a.r)) return false;
    if (p.category.size && !p.category.has(a.c)) return false;
    if (p.org.size && !p.org.has(a.o)) return false;
    if (p.district.size) {
      var g = a.g || [];
      var ok = false;
      p.district.forEach(function (d) { if (g.indexOf(d) >= 0) ok = true; });
      if (!ok) return false;
    }
    if (p.amount.size && !p.amount.has(a.b || 'unk')) return false;
    if (p.src && (a.src || 'bizinfo') !== p.src) return false;
    if (query && (a.t + ' ' + a.o + ' ' + (a.w || '')).toLowerCase().indexOf(query) < 0) return false;
    if (p.period.size) {
      var hit = false;
      if (p.period.has('today') && a.d === 0) hit = true;
      if (p.period.has('week') && a.d >= 0 && a.d <= 7) hit = true;
      if (p.period.has('always') && (a.d === 9999 || a.pt === 'always')) hit = true;
      if (p.period.has('range') && a.e && a.d !== 9999 && a.pt !== 'always') {
        if ((!p.from || a.e >= p.from) && (!p.to || a.e <= p.to)) hit = true;
      }
      if (!hit) return false;
    } else if (p.from || p.to) {
      if (a.pt === 'always' || a.d === 9999 || !a.e) return false;
      if (p.from && a.e < p.from) return false;
      if (p.to && a.e > p.to) return false;
    }
    return true;
  }
  function match(a) { return matchWith(a, picked, openOnly, q); }

  function compute() {
    view = all.filter(match);
    if (sortBy === 'new') view.sort(function (x, y) { return (y.e || '') < (x.e || '') ? -1 : 1; });
    else view.sort(function (x, y) { return (x.d < 0) - (y.d < 0) || x.d - y.d; });
  }

  function countOpt(k, v) {
    var tmp = clonePicked(draft || picked);
    if (k === 'src') tmp.src = v;
    else if (tmp[k] && tmp[k] instanceof Set) tmp[k].add(v);
    return all.filter(function (a) { return matchWith(a, tmp, openOnly, q); }).length;
  }

  function midAdHTML() {
    var client = board.dataset.adClient || '';
    var slot = board.dataset.adSlotMid || '';
    var mid = parseInt(board.dataset.adMid, 10) || 0;
    if (!mid || !client || !slot) return '';
    var esc = window.MagampanCard ? MagampanCard.esc : function (s) { return s; };
    return '<aside class="ad-slot ad-slot--mid" data-ad-pos="list_mid" aria-label="광고">' +
      '<ins class="adsbygoogle" style="display:block" data-ad-client="' + esc(client) +
      '" data-ad-slot="' + esc(slot) + '" data-ad-format="auto" data-full-width-responsive="true"></ins></aside>';
  }

  function paintChips() {
    function lab(el, base, set, map) {
      if (!el) return;
      var n = set.size;
      var extra = '';
      if (n === 1) extra = (map ? map[[...set][0]] : [...set][0]) || '';
      else if (n > 1) extra = String(n);
      var label = extra ? (n > 1 ? base + ' ' + extra : extra) : base;
      var node = el.firstChild;
      if (!node || node.nodeType !== 3) {
        el.insertBefore(document.createTextNode(label + ' '), el.firstChild);
      } else {
        node.textContent = label + ' ';
      }
      el.classList.toggle('is-on', n > 0);
    }
    var byPanel = {};
    chipBtns.forEach(function (b) { byPanel[b.dataset.panel] = b; });
    lab(byPanel.region, '지역', picked.region);
    lab(byPanel.category, '분야', picked.category);
    lab(byPanel.org, '지원기관', picked.org);
    var amtNames = {};
    var amtTpl = document.getElementById('f-opt-amount');
    var amtOpts = amtTpl ? amtTpl.content.querySelectorAll('.f-opt') : [];
    amtOpts.forEach(function (b) {
      amtNames[b.dataset.v] = (b.querySelector('b') || b).textContent.trim();
    });
    lab(byPanel.amount, '지원금액', picked.amount, amtNames);
    var perNames = { today: '오늘 마감', week: '이번 주', always: '상시', range: '기간' };
    lab(byPanel.period, '기간', picked.period, perNames);
    if (picked.from || picked.to) {
      if (byPanel.period) byPanel.period.classList.add('is-on');
    }
    var nOn = picked.region.size + picked.category.size + picked.org.size +
      picked.amount.size + picked.period.size + picked.district.size + (picked.src ? 1 : 0) + (q ? 1 : 0);
    var sheet = document.getElementById('f-sheet');
    if (sheet) {
      sheet.classList.toggle('is-on', nOn > 0);
      var t = sheet.firstChild;
      var labTxt = nOn ? ('필터 ' + nOn) : '필터';
      if (!t || t.nodeType !== 3) sheet.insertBefore(document.createTextNode(labTxt), sheet.firstChild);
      else t.textContent = labTxt;
    }
  }

  function paintSum() {
    var box = document.getElementById('sum-chips');
    if (!box || !all.length) return;
    box.hidden = false;
    var hasKs = all.some(function (a) { return a.src === 'kstartup'; });
    function count(fn) { return all.filter(fn).length; }
    var map = {
      all: all.length,
      today: count(function (a) { return a.d === 0; }),
      week: count(function (a) { return a.d >= 0 && a.d <= 7; }),
      always: count(function (a) { return a.d === 9999 || a.pt === 'always'; }),
      bizinfo: count(function (a) { return (a.src || 'bizinfo') !== 'kstartup'; }),
      kstartup: count(function (a) { return a.src === 'kstartup'; })
    };
    box.querySelectorAll('.sum-chip').forEach(function (b) {
      var k = b.dataset.sum;
      if (k === 'bizinfo' || k === 'kstartup') b.hidden = !hasKs;
      var label = b.dataset.label || b.textContent.replace(/\s[\d,]+건?$/, '').trim();
      b.dataset.label = label;
      var n = map[k];
      b.textContent = label + (n != null ? ' ' + n : '');
      var on = false;
      if (k === 'all') on = !picked.period.size && !picked.src && !picked.from && !picked.to;
      else if (k === 'today' || k === 'week' || k === 'always') on = picked.period.size === 1 && picked.period.has(k);
      else if (k === 'bizinfo' || k === 'kstartup') on = picked.src === k;
      b.classList.toggle('is-on', on);
    });
  }

  function esc(s) {
    return window.MagampanCard ? MagampanCard.esc(s) : String(s == null ? '' : s);
  }

  function pageLocked(k, v) {
    if (k === 'region' && root.dataset.region === v) return true;
    if (k === 'category' && root.dataset.category === v) return true;
    if (k === 'district' && root.dataset.district === v) return true;
    return false;
  }

  function paintOpenOnly() {
    var lab = root.querySelector('.f-chip--check');
    if (lab) lab.classList.toggle('is-on', !!openOnly);
    var inp = document.getElementById('f-openonly');
    if (inp) inp.checked = !!openOnly;
  }

  function paintPills() {
    var box = document.getElementById('f-pills');
    if (!box) return;
    var pills = [];
    function add(k, v, label) {
      if (pageLocked(k, v)) return;
      pills.push({ k: k, v: v, label: label || v });
    }
    picked.region.forEach(function (v) { add('region', v, v); });
    picked.category.forEach(function (v) { add('category', v, v); });
    picked.org.forEach(function (v) { add('org', v, v); });
    picked.district.forEach(function (v) { add('district', v, v); });
    var amtNames = {};
    var amtTpl = document.getElementById('f-opt-amount');
    var amtOpts = amtTpl ? amtTpl.content.querySelectorAll('.f-opt') : [];
    amtOpts.forEach(function (b) {
      amtNames[b.dataset.v] = (b.querySelector('b') || b).textContent.trim();
    });
    picked.amount.forEach(function (v) { add('amount', v, amtNames[v] || v); });
    var perNames = { today: '오늘 마감', week: '이번 주', always: '상시', range: '기간' };
    picked.period.forEach(function (v) { add('period', v, perNames[v] || v); });
    if (picked.from || picked.to) {
      if (!picked.period.has('range')) add('period', 'range', '기간');
    }
    if (q) pills.push({ k: 'q', v: q, label: '검색' });
    if (picked.src) {
      pills.push({ k: 'src', v: picked.src, label: picked.src === 'kstartup' ? 'K-Startup' : '기업마당' });
    }
    if (!pills.length) {
      box.hidden = true;
      box.innerHTML = '';
      return;
    }
    box.hidden = false;
    box.innerHTML = pills.map(function (p) {
      return '<button type="button" class="pill-x" data-clear="' + esc(p.k) + '" data-v="' + esc(p.v) +
        '" aria-label="' + esc(p.label) + ' 필터 지우기">' + esc(p.label) + ' ×</button>';
    }).join('') + '<button type="button" class="pill-x pill-x--all js-f-clear">전체 해제</button>';
  }

  var POPULAR = ['서울', '경기', '부산', '전국'];
  function emptyHTML() {
    var slugs = ((window.__SLUG__ || {}).region) || {};
    var links = POPULAR.map(function (name) {
      var slug = slugs[name];
      if (!slug) return '';
      return '<a href="/region/' + slug + '/">' + name + '</a>';
    }).join('');
    return '<div class="empty-filter" role="status">' +
      '<p>조건에 맞는 공고가 없습니다. 필터를 완화하거나 전체 목록·이 조건 알림으로 이어가세요.</p>' +
      '<div class="empty-actions">' +
      '<button type="button" class="f-apply js-f-relax">필터 완화</button>' +
      '<a class="hero-secondary" href="/all/">전체 보기</a>' +
      '<button type="button" class="hero-secondary js-f-alert">이 조건 알림</button>' +
      '</div>' +
      (links ? '<p class="empty-pop">많이 찾는 지역</p><div class="chips">' + links + '</div>' : '') +
      '</div>';
  }

  var justApplied = false;
  function announce(n) {
    var soon = view.filter(function (a) { return a.d >= 0 && a.d <= 7; }).length;
    var text = n + '건' + (soon ? ' · 이번 주 마감 ' + soon + '건' : '');
    var countEl = document.getElementById('f-count');
    if (countEl) countEl.textContent = text;
    var live = document.getElementById('f-live');
    if (live && justApplied) {
      live.textContent = '';
      live.textContent = '필터를 적용했습니다. ' + n + '건입니다.';
    }
  }

  function clearFilters() {
    picked = emptyPicked();
    applyPageLocks(picked);
    q = '';
    var qi = document.getElementById('f-q');
    if (qi) qi.value = '';
    openOnly = true;
    sortBy = 'dday';
    var so = document.getElementById('f-sort');
    if (so) so.value = 'dday';
    paintOpenOnly();
    touched = true;
    justApplied = true;
    render(true);
  }

  function relaxFilters() {
    if (openOnly) {
      openOnly = false;
      paintOpenOnly();
    } else if (q) {
      q = '';
      var qi = document.getElementById('f-q');
      if (qi) qi.value = '';
    } else if (picked.amount.size) picked.amount.clear();
    else if (picked.org.size) picked.org.clear();
    else if (picked.period.size) { picked.period.clear(); picked.from = ''; picked.to = ''; }
    else if (picked.category.size && !root.dataset.category) picked.category.clear();
    else if (picked.region.size && !root.dataset.region) { picked.region.clear(); picked.district.clear(); }
    else if (picked.src) picked.src = '';
    touched = true;
    justApplied = true;
    render(true);
  }

  function dropPill(k, v) {
    if (k === 'q') {
      q = '';
      var qi = document.getElementById('f-q');
      if (qi) qi.value = '';
    } else if (k === 'src') {
      picked.src = '';
    } else if (picked[k] && picked[k] instanceof Set) {
      picked[k].delete(v);
      if (k === 'region') picked.district.clear();
      if (k === 'period' && v === 'range') { picked.from = ''; picked.to = ''; }
    }
    touched = true;
    justApplied = true;
    render(true);
  }

  function syncURL() {
    var next = location.pathname;
    if (window.MagampanState) {
      next = location.pathname + MagampanState.serializeGrant(toURLState(), lockedKeys());
    } else if (q) {
      next = location.pathname + '?q=' + encodeURIComponent(q);
    }
    if (location.pathname + location.search !== next) history.replaceState(null, '', next);
  }

  function showSkeleton() {
    if (!board) return;
    board.classList.add('is-busy');
    var sk = '';
    for (var i = 0; i < 4; i++) {
      sk += '<article class="row sk-row" aria-hidden="true">' +
        '<div class="sk-bar"></div><div class="sk-bar sk-bar--lg"></div>' +
        '<div class="sk-bar sk-bar--sm"></div></article>';
    }
    board.innerHTML = sk;
  }

  function render(reset) {
    var y = window.scrollY;
    paintChips(); paintSum(); paintPills(); paintOpenOnly();
    if (!touched) return;
    if (reset) shown = PAGE;
    compute();
    showSkeleton();
    requestAnimationFrame(function () {
      if (!view.length) {
        board.innerHTML = emptyHTML();
      } else {
        var mid = parseInt(board.dataset.adMid, 10) || 0;
        var ad = midAdHTML();
        var slice = view.slice(0, shown);
        var html = '';
        var card = window.MagampanCard;
        for (var i = 0; i < slice.length; i++) {
          html += card ? card.html(slice[i]) : '';
          if (ad && (i + 1) === mid && (i + 1) < view.length) html += ad;
        }
        if (view.length > shown) {
          html += '<button type="button" class="more" id="f-more">' +
            Math.min(PAGE * 2, view.length - shown) + '건 더 보기</button>';
        } else if (MORE && !picked.region.size && !picked.category.size && !q &&
                   !picked.org.size && !picked.district.size && !picked.amount.size &&
                   !picked.period.size && !picked.src) {
          html += '<a class="more" href="' + MORE + '">전체 공고 보기</a>';
        }
        board.innerHTML = html;
        if (ad && board.querySelector('.ad-slot--mid ins.adsbygoogle')) {
          try { (window.adsbygoogle = window.adsbygoogle || []).push({}); } catch (err) {}
        }
      }
      board.classList.remove('is-busy');
      announce(view.length);
      justApplied = false;
      syncURL();
      if (typeof y === 'number') window.scrollTo(0, y);
      if (touched) hideOnboard(false);
    });
  }

  function districtsFor(regions) {
    var set = {};
    all.forEach(function (a) {
      if (regions.size && !regions.has(a.r) && a.r !== '전국') return;
      (a.g || []).forEach(function (g) { set[g] = 1; });
    });
    return Object.keys(set).sort();
  }
  function orgsFor() {
    var map = {};
    all.forEach(function (a) {
      if (!a.o) return;
      map[a.o] = (map[a.o] || 0) + 1;
    });
    return Object.keys(map).sort(function (a, b) { return map[b] - map[a] || a.localeCompare(b, 'ko'); })
      .map(function (name) { return { name: name, n: map[name] }; });
  }

  function setPressed(scope) {
    (scope || panelBody).querySelectorAll('.f-opt').forEach(function (b) {
      var k = b.dataset.k, v = b.dataset.v;
      if (!k || !draft[k]) return;
      b.setAttribute('aria-pressed', draft[k].has(v) ? 'true' : 'false');
    });
  }

  function stampCounts(scope) {
    (scope || panelBody).querySelectorAll('.f-opt[data-k]').forEach(function (b) {
      var n = countOpt(b.dataset.k, b.dataset.v);
      var span = b.querySelector('span');
      if (span && !b.closest('#f-live-org')) {
        if (!span.dataset.base) span.dataset.base = span.textContent;
        span.textContent = (span.dataset.base ? span.dataset.base + ' · ' : '') + n + '건';
      } else if (!span) {
        var em = b.querySelector('em.f-n') || document.createElement('em');
        em.className = 'f-n';
        em.textContent = n;
        b.appendChild(em);
      }
    });
  }

  function fillPanel(kind) {
    panelKind = kind;
    orgQ = '';
    saveName = '';
    var html = '';
    panelFoot.hidden = false;
    document.getElementById('f-panel-apply').textContent = '적용';
    document.getElementById('f-panel-reset').hidden = false;

    if (kind === 'all') {
      panelTitle.textContent = '필터';
      html += '<div class="f-group"><h3>지역</h3><div class="f-opt-row" id="f-live-region"></div></div>';
      html += '<div class="f-group"><h3>시군구</h3><div class="f-opt-row" id="f-live-district"></div></div>';
      html += '<div class="f-group"><h3>분야</h3><div id="f-live-cat"></div></div>';
      html += '<div class="f-group"><h3>기간</h3><div id="f-live-period"></div></div>';
      html += '<div class="f-group"><h3>지원금액</h3><div id="f-live-amt"></div></div>';
      panelBody.innerHTML = html;
      var host = document.getElementById('f-live-region');
      var tpl = document.getElementById('f-opt-region');
      if (tpl) host.innerHTML = tpl.innerHTML;
      var cat = document.getElementById('f-live-cat');
      var ct = document.getElementById('f-opt-category');
      if (ct) cat.innerHTML = ct.innerHTML;
      var amt = document.getElementById('f-live-amt');
      var at = document.getElementById('f-opt-amount');
      if (at) amt.innerHTML = at.innerHTML;
      var per = document.getElementById('f-live-period');
      per.innerHTML = PERIODS.map(function (p) {
        return '<button type="button" class="f-opt" data-k="period" data-v="' + p.id + '"><b>' +
          p.name + '</b><span>' + p.desc + '</span></button>';
      }).join('');
      paintDistrictOpts();
      setPressed();
      stampCounts();
    } else if (kind === 'region') {
      panelTitle.textContent = '지역';
      html += '<div class="f-group"><h3>일반 필터 · 광역</h3><div class="f-opt-row" id="f-live-region"></div></div>';
      html += '<div class="f-group"><h3>시군구</h3><div class="f-opt-row" id="f-live-district"></div></div>';
      panelBody.innerHTML = html;
      var hostR = document.getElementById('f-live-region');
      var tplR = document.getElementById('f-opt-region');
      if (tplR) hostR.innerHTML = tplR.innerHTML;
      paintDistrictOpts();
      setPressed();
      stampCounts();
    } else if (kind === 'category') {
      panelTitle.textContent = '분야';
      panelBody.innerHTML = '<div class="f-group"><h3>일반 필터 · 사업분야</h3><div id="f-live-cat"></div></div>';
      var cat2 = document.getElementById('f-live-cat');
      var ct2 = document.getElementById('f-opt-category');
      if (ct2) cat2.innerHTML = ct2.innerHTML;
      setPressed();
      stampCounts();
    } else if (kind === 'org') {
      panelTitle.textContent = '지원기관';
      panelBody.innerHTML = '<div class="f-group"><h3>일반 필터 · 소관기관</h3>' +
        '<input class="f-search" id="f-org-q" type="search" placeholder="기관명 찾기" autocomplete="off">' +
        '<div id="f-live-org"></div></div>';
      paintOrgs();
    } else if (kind === 'amount') {
      panelTitle.textContent = '지원금액';
      panelBody.innerHTML = '<div class="f-group"><h3>고급 필터 · 본문 표기 구간</h3>' +
        '<p class="f-help">API에 금액 필드가 없어 공고 본문에서 읽은 표기만 나눕니다. 없는 숫자는 만들지 않습니다.</p>' +
        '<div id="f-live-amt"></div></div>';
      var amt2 = document.getElementById('f-live-amt');
      var at2 = document.getElementById('f-opt-amount');
      if (at2) amt2.innerHTML = at2.innerHTML;
      setPressed();
      stampCounts();
    } else if (kind === 'period') {
      panelTitle.textContent = '기간';
      html = '<div class="f-group"><h3>기간 필터</h3>';
      PERIODS.forEach(function (p) {
        html += '<button type="button" class="f-opt" data-k="period" data-v="' + p.id + '"><b>' +
          p.name + '</b><span>' + p.desc + '</span></button>';
      });
      html += '<div class="f-dates">' +
        '<label>시작<input type="date" id="f-from" value="' + (draft.from || '') + '"></label>' +
        '<label>끝<input type="date" id="f-to" value="' + (draft.to || '') + '"></label>' +
        '</div></div>';
      panelBody.innerHTML = html;
      setPressed();
      stampCounts();
    } else if (kind === 'save' || kind === 'alert') {
      panelTitle.textContent = kind === 'alert' ? '이 조건 알림' : '조건 저장';
      var auto = defaultPresetName();
      var desc = window.MagampanState ? MagampanState.describeGrant(toURLState()) : auto;
      var hits = all.filter(match);
      var preview = window.MagampanAlerts
        ? MagampanAlerts.previewHTML(hits.map(function (a) { return a; }), { section: 'grant' })
        : '';
      panelBody.innerHTML = '<div class="f-group"><p class="f-help">이 브라우저에만 저장됩니다. 로그인 없이 localStorage를 씁니다. 결제·회원 가입은 없습니다.</p>' +
        '<p class="f-help">지금 조건: ' + esc(desc) + '</p>' +
        '<label class="f-help" for="f-save-name">이름</label>' +
        '<input class="f-search" id="f-save-name" value="' + esc(auto) + '" maxlength="40">' +
        preview +
        '</div>';
      document.getElementById('f-panel-apply').textContent = kind === 'alert'
        ? (window.MagampanAlerts && MagampanAlerts.applyLabel ? MagampanAlerts.applyLabel() : '저장하고 메일 열기')
        : '저장';
      document.getElementById('f-panel-reset').hidden = true;
    } else if (kind === 'load') {
      panelTitle.textContent = '조건 불러오기';
      var list = readPresets();
      if (!list.length) {
        panelBody.innerHTML = '<p class="f-help">저장된 조건이 없습니다. 필터를 고른 뒤 조건 저장을 누르세요.</p>';
        panelFoot.hidden = true;
      } else {
        html = '<div class="f-preset-list">';
        list.forEach(function (item, i) {
          html += '<div class="f-preset" data-i="' + i + '"><b>' + esc(item.name) +
            '</b><button type="button" class="f-preset-del" data-del="' + i + '">삭제</button></div>';
        });
        html += '</div>';
        panelBody.innerHTML = html;
        document.getElementById('f-panel-apply').textContent = '불러오기';
        panelFoot.hidden = true;
      }
    }
  }

  function paintDistrictOpts() {
    var host = document.getElementById('f-live-district');
    if (!host) return;
    if (!draft.region.size) {
      host.innerHTML = '<p class="f-help">광역을 고르면 시군구가 열립니다. 시군구는 해시태그 정확 일치만 인정합니다.</p>';
      return;
    }
    var names = districtsFor(draft.region);
    if (!names.length) {
      host.innerHTML = '<p class="f-help">이 광역에서 시군구 태그가 붙은 공고가 없습니다. 시군구는 해시태그 정확 일치만 인정합니다.</p>';
      return;
    }
    host.innerHTML = names.map(function (n) {
      return '<button type="button" class="f-opt" data-k="district" data-v="' + esc(n) + '">' +
        esc(n) + '</button>';
    }).join('');
    setPressed(host);
  }

  function paintOrgs() {
    var host = document.getElementById('f-live-org');
    if (!host) return;
    var qv = orgQ.toLowerCase();
    var rows = orgsFor().filter(function (o) { return !qv || o.name.toLowerCase().indexOf(qv) >= 0; });
    host.innerHTML = rows.slice(0, 80).map(function (o) {
      return '<button type="button" class="f-opt" data-k="org" data-v="' + esc(o.name) + '"><b>' +
        esc(o.name) + '</b><span>' + o.n + '건</span></button>';
    }).join('') || '<p class="f-help">맞는 기관이 없습니다.</p>';
    setPressed(host);
  }

  function defaultPresetName() {
    var parts = [];
    if (picked.region.size) parts.push([...picked.region].slice(0, 2).join('·'));
    if (picked.category.size) parts.push([...picked.category].slice(0, 2).join('·'));
    if (picked.period.has('today')) parts.push('오늘 마감');
    else if (picked.period.has('week')) parts.push('이번 주');
    else if (picked.period.has('always')) parts.push('상시');
    if (q) parts.push('검색');
    return parts.join(' · ') || '지금 조건';
  }

  function readPresets() {
    try { return JSON.parse(localStorage.getItem(PRESET_KEY) || '[]'); }
    catch (e) { return []; }
  }
  function writePresets(list) {
    try { localStorage.setItem(PRESET_KEY, JSON.stringify(list)); }
    catch (e) {}
  }

  var panelOpener = null;
  function openPanel(kind) {
    draft = clonePicked(picked);
    fillPanel(kind);
    overlay.hidden = false;
    overlay.setAttribute('aria-hidden', 'false');
    document.body.classList.add('f-lock');
    panelOpener = document.activeElement;
    chipBtns.forEach(function (b) {
      b.setAttribute('aria-expanded', b.dataset.panel === kind ? 'true' : 'false');
    });
    panel.focus();
  }
  function closePanel() {
    overlay.hidden = true;
    overlay.setAttribute('aria-hidden', 'true');
    document.body.classList.remove('f-lock');
    chipBtns.forEach(function (b) { b.setAttribute('aria-expanded', 'false'); });
    panelKind = '';
    draft = null;
    if (panelOpener && panelOpener.focus) panelOpener.focus();
    panelOpener = null;
  }
  if (window.MagampanState && MagampanState.bindDialog) {
    MagampanState.bindDialog(overlay, panel, closePanel);
  }

  function savePreset(andMail) {
    var inp = document.getElementById('f-save-name');
    var name = ((inp && inp.value) || defaultPresetName()).trim() || '지금 조건';
    var list = readPresets().filter(function (x) { return x.name !== name; });
    var rec = { name: name, state: serialize(picked), q: q, openOnly: openOnly, sortBy: sortBy };
    list.unshift(rec);
    writePresets(list.slice(0, 8));
    var freq = window.MagampanAlerts ? MagampanAlerts.freqOf(panelBody) : 'daily';
    if (window.MagampanAlerts) {
      MagampanAlerts.save({
        name: name, section: 'grant', q: q, freq: freq,
        href: location.pathname + (window.MagampanState ? MagampanState.serializeGrant(toURLState(), lockedKeys()) : ''),
        region: [...picked.region], field: [...picked.category],
        deadline: [...picked.period], org: [...picked.org], amount: [...picked.amount]
      });
    }
    if (andMail) {
      var desc = window.MagampanState ? MagampanState.describeGrant(toURLState()) : name;
      var freqLabel = ((window.MagampanAlerts && MagampanAlerts.FREQ[freq]) || freq);
      var email = window.MagampanAlerts && MagampanAlerts.panelEmail
        ? MagampanAlerts.panelEmail(panelBody) : '';
      var body = '아래 조건으로 마감 알림을 받고 싶습니다.\n\n' + desc +
        '\n빈도: ' + freqLabel +
        '\n이메일: ' + (email || '(미입력)') +
        '\n\n페이지: ' + location.href + '\n\n(로그인·결제는 없습니다. 이 메일로 조건만 알려 주세요.)';
      var mailer = window.MagampanAlerts && MagampanAlerts.send
        ? MagampanAlerts.send({
          email: email,
          keyword: name,
          subject: '[마감판] 조건 알림',
          message: body
        })
        : Promise.resolve({ ok: true, via: 'mailto' });
      if (!(window.MagampanAlerts && MagampanAlerts.send)) {
        location.href = 'mailto:' + EMAIL + '?subject=' +
          encodeURIComponent('[마감판] 조건 알림') + '&body=' + encodeURIComponent(body);
      }
      mailer.then(function (res) {
        if (window.MagampanAlerts && MagampanAlerts.sayToast) MagampanAlerts.sayToast(res);
      });
    }
  }

  function applyDraft() {
    if (panelKind === 'save') {
      savePreset(false);
      closePanel();
      return;
    }
    if (panelKind === 'alert') {
      var em = document.getElementById('alert-panel-email');
      if (em && !em.value.trim()) { em.focus(); return; }
      if (em && em.reportValidity && !em.checkValidity()) { em.reportValidity(); return; }
      savePreset(true);
      closePanel();
      return;
    }
    if (!draft) { closePanel(); return; }
    if (draft.from || draft.to) draft.period.add('range');
    picked = clonePicked(draft);
    applyPageLocks(picked);
    touched = true;
    justApplied = true;
    closePanel();
    render(true);
  }

  function resetDraftGroup() {
    if (!draft) return;
    if (panelKind === 'all' || panelKind === 'region') { draft.region.clear(); draft.district.clear(); paintDistrictOpts(); }
    if (panelKind === 'all' || panelKind === 'category') draft.category.clear();
    if (panelKind === 'org') draft.org.clear();
    if (panelKind === 'all' || panelKind === 'amount') draft.amount.clear();
    if (panelKind === 'all' || panelKind === 'period') { draft.period.clear(); draft.from = ''; draft.to = ''; if (panelKind === 'period') { fillPanel('period'); return; } }
    setPressed();
    if (panelKind === 'org') paintOrgs();
    stampCounts();
  }

  chipBtns.forEach(function (b) {
    b.addEventListener('click', function () {
      if (panelKind === b.dataset.panel && !overlay.hidden) { closePanel(); return; }
      openPanel(b.dataset.panel);
    });
  });

  overlay.addEventListener('click', function (e) {
    if (e.target === overlay) closePanel();
  });
  document.getElementById('f-panel-x').addEventListener('click', closePanel);
  document.getElementById('f-panel-apply').addEventListener('click', applyDraft);
  document.getElementById('f-panel-reset').addEventListener('click', resetDraftGroup);

  panelBody.addEventListener('click', function (e) {
    var del = e.target.closest('[data-del]');
    if (del) {
      var list = readPresets();
      list.splice(parseInt(del.dataset.del, 10), 1);
      writePresets(list);
      fillPanel('load');
      return;
    }
    var preset = e.target.closest('.f-preset');
    if (preset && !e.target.closest('[data-del]')) {
      var item = readPresets()[parseInt(preset.dataset.i, 10)];
      if (!item) return;
      picked = restore(item.state);
      applyPageLocks(picked);
      q = (item.q || '').toLowerCase();
      openOnly = item.openOnly !== false;
      sortBy = item.sortBy || 'dday';
      var qi = document.getElementById('f-q');
      if (qi) qi.value = item.q || '';
      document.getElementById('f-openonly').checked = openOnly;
      document.getElementById('f-sort').value = sortBy;
      touched = true;
      justApplied = true;
      closePanel();
      render(true);
      return;
    }
    var opt = e.target.closest('.f-opt');
    if (!opt || !draft) return;
    var k = opt.dataset.k, v = opt.dataset.v;
    if (!k || !draft[k] || !(draft[k] instanceof Set)) return;
    if (draft[k].has(v)) draft[k].delete(v); else draft[k].add(v);
    opt.setAttribute('aria-pressed', draft[k].has(v) ? 'true' : 'false');
    if (k === 'region') paintDistrictOpts();
    stampCounts();
  });

  panelBody.addEventListener('input', function (e) {
    if (e.target.id === 'f-org-q') { orgQ = e.target.value.trim(); paintOrgs(); }
    if (e.target.id === 'f-from' && draft) draft.from = e.target.value;
    if (e.target.id === 'f-to' && draft) draft.to = e.target.value;
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && !overlay.hidden) closePanel();
  });

  document.getElementById('sum-chips').addEventListener('click', function (e) {
    var b = e.target.closest('.sum-chip');
    if (!b) return;
    var k = b.dataset.sum;
    if (k === 'all') { picked.period.clear(); picked.src = ''; picked.from = ''; picked.to = ''; }
    else if (k === 'today' || k === 'week' || k === 'always') {
      if (picked.period.size === 1 && picked.period.has(k)) picked.period.clear();
      else { picked.period = new Set([k]); picked.from = ''; picked.to = ''; }
    } else if (k === 'bizinfo' || k === 'kstartup') {
      picked.src = picked.src === k ? '' : k;
    }
    touched = true;
    justApplied = true;
    render(true);
  });

  var searchForm = root.querySelector('.find-search');
  if (searchForm) searchForm.addEventListener('submit', function (e) {
    e.preventDefault();
  });

  board.addEventListener('click', function (e) {
    if (e.target.id === 'f-more') { shown += PAGE * 2; render(); }
    if (e.target.id === 'f-more-static') { touched = true; shown = PAGE * 3; render(); }
    if (e.target.classList.contains('js-f-clear') || (e.target.closest && e.target.closest('.js-f-clear'))) {
      clearFilters();
    }
    if (e.target.classList.contains('js-f-relax') || (e.target.closest && e.target.closest('.js-f-relax'))) {
      relaxFilters();
    }
    if (e.target.classList.contains('js-f-alert') || (e.target.closest && e.target.closest('.js-f-alert'))) {
      openPanel('alert');
    }
  });

  var pillsBox = document.getElementById('f-pills');
  if (pillsBox) {
    pillsBox.addEventListener('click', function (e) {
      if (e.target.classList.contains('js-f-clear') || e.target.classList.contains('pill-x--all')) {
        clearFilters();
        return;
      }
      var btn = e.target.closest('[data-clear]');
      if (!btn) return;
      dropPill(btn.dataset.clear, btn.dataset.v);
    });
  }

  var moreBtn = document.getElementById('f-more-filters');
  if (moreBtn) {
    moreBtn.addEventListener('click', function () {
      var row = root.querySelector('.find-chips');
      var on = row.classList.toggle('is-more');
      moreBtn.setAttribute('aria-expanded', on ? 'true' : 'false');
    });
  }

  document.querySelectorAll('[data-howto="region"]').forEach(function (el) {
    el.addEventListener('click', function (e) {
      e.preventDefault();
      openPanel('region');
      var find = document.getElementById('find');
      if (find && find.scrollIntoView) find.scrollIntoView({ block: 'nearest' });
    });
  });

  document.getElementById('f-openonly').addEventListener('change', function (e) {
    openOnly = e.target.checked; touched = true; justApplied = true; render(true);
  });
  document.getElementById('f-sort').addEventListener('change', function (e) {
    sortBy = e.target.value; touched = true; render(true);
  });

  var suggestCtl = null;
  var qEl = document.getElementById('f-q');
  if (qEl && window.MagampanSuggest) {
    suggestCtl = MagampanSuggest.bind(qEl, {
      onPick: function (v) {
        q = (v || '').trim().toLowerCase();
        touched = true;
        render(true);
      }
    });
  }
  var t;
  if (qEl) qEl.addEventListener('input', function (e) {
    clearTimeout(t);
    var v = e.target.value.trim().toLowerCase();
    t = setTimeout(function () { q = v; touched = true; render(true); }, 180);
  });

  function markOnboard(step) {
    var box = document.getElementById('onboard');
    if (!box) return;
    box.querySelectorAll('.onboard-steps li').forEach(function (li) {
      li.classList.toggle('is-on', li.dataset.step === step);
    });
  }
  function hideOnboard(save) {
    var box = document.getElementById('onboard');
    if (box) box.hidden = true;
    if (save) {
      try { localStorage.setItem(ON_KEY, '1'); } catch (e) {}
    }
  }
  (function initOnboard() {
    var box = document.getElementById('onboard');
    if (!box) return;
    if (location.pathname !== '/') { box.hidden = true; return; }
    if (touched) { box.hidden = true; return; }
    try { if (localStorage.getItem(ON_KEY)) { box.hidden = true; return; } } catch (e) {}
    box.hidden = false;
    markOnboard('region');
    box.addEventListener('click', function (e) {
      var act = e.target.dataset.onboard;
      if (!act) return;
      if (act === 'skip') { hideOnboard(true); return; }
      if (act === 'region' || act === 'category') {
        markOnboard(act);
        openPanel(act);
      }
    });
  })();

  fetch('/notices.json')
    .then(function (r) { return r.json(); })
    .then(function (d) {
      all = d; root.classList.add('ready');
      if (suggestCtl) {
        var orgs = {};
        d.forEach(function (a) { if (a.o) orgs[a.o] = 1; });
        suggestCtl.add(Object.keys(orgs), '기관');
      }
      paintChips(); paintSum(); paintPills(); paintOpenOnly();
      if (touched) render(true);
    })
    .catch(function () { /* 검색 폼 GET /all/ 은 그대로 둔다 */ });
})();
