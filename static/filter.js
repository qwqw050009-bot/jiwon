/* 지역·분야·기관·금액·기간 필터 + 검색 + 조건 저장.
   정적 페이지는 그대로 두고(SEO) 그 위에서 클라이언트 필터링만 한다. */
(function () {
  var root = document.getElementById('find');
  var board = document.getElementById('board');
  if (!root || !board) return;

  var PAGE = parseInt(board.dataset.limit, 10) || 20;
  var MORE = board.dataset.more || '';
  var onDistrictPage = !!root.dataset.district;
  var PRESET_KEY = 'magampan.presets.v1';
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
    (s.category || []).forEach(function (v) { p.category.add(v); });
    (s.org || []).forEach(function (v) { p.org.add(v); });
    (s.district || []).forEach(function (v) { p.district.add(v); });
    (s.amount || []).forEach(function (v) { p.amount.add(v); });
    (s.period || []).forEach(function (v) { p.period.add(v); });
    p.from = s.from || ''; p.to = s.to || ''; p.src = s.src || '';
    return p;
  }

  var picked = emptyPicked();
  var draft = null;
  var openOnly = true, sortBy = 'dday', q = '', shown = PAGE, all = [], view = [];
  var touched = false, panelKind = '', orgQ = '', saveName = '';

  if (root.dataset.region) picked.region.add(root.dataset.region);
  if (root.dataset.category) picked.category.add(root.dataset.category);
  if (root.dataset.district) picked.district.add(root.dataset.district);

  var seedQ = new URLSearchParams(location.search).get('q');
  if (seedQ) {
    q = seedQ.trim().toLowerCase();
    touched = true;
    var qInput = document.getElementById('f-q');
    if (qInput) qInput.value = seedQ;
  }

  var overlay = document.getElementById('f-overlay');
  var panel = document.getElementById('f-panel');
  var panelTitle = document.getElementById('f-panel-title');
  var panelBody = document.getElementById('f-panel-body');
  var panelFoot = document.getElementById('f-panel-foot');
  var chipBtns = root.querySelectorAll('.f-chip[data-panel]');

  function match(a) {
    if (openOnly && a.d < 0) return false;
    if (picked.region.size && !picked.region.has(a.r)) return false;
    if (picked.category.size && !picked.category.has(a.c)) return false;
    if (picked.org.size && !picked.org.has(a.o)) return false;
    if (picked.district.size) {
      var g = a.g || [];
      var ok = false;
      picked.district.forEach(function (d) { if (g.indexOf(d) >= 0) ok = true; });
      if (!ok) return false;
    }
    if (picked.amount.size && !picked.amount.has(a.b || 'unk')) return false;
    if (picked.src && (a.src || 'bizinfo') !== picked.src) return false;
    if (q && (a.t + ' ' + a.o + ' ' + (a.w || '')).toLowerCase().indexOf(q) < 0) return false;
    if (picked.period.size) {
      var hit = false;
      if (picked.period.has('today') && a.d === 0) hit = true;
      if (picked.period.has('week') && a.d >= 0 && a.d <= 7) hit = true;
      if (picked.period.has('always') && (a.d === 9999 || a.pt === 'always')) hit = true;
      if (picked.period.has('range') && a.e && a.d !== 9999 && a.pt !== 'always') {
        if ((!picked.from || a.e >= picked.from) && (!picked.to || a.e <= picked.to)) hit = true;
      }
      if (!hit) return false;
    } else if (picked.from || picked.to) {
      if (a.pt === 'always' || a.d === 9999 || !a.e) return false;
      if (picked.from && a.e < picked.from) return false;
      if (picked.to && a.e > picked.to) return false;
    }
    return true;
  }

  function compute() {
    view = all.filter(match);
    if (sortBy === 'new') view.sort(function (x, y) { return (y.e || '') < (x.e || '') ? -1 : 1; });
    else view.sort(function (x, y) { return (x.d < 0) - (y.d < 0) || x.d - y.d; });
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
    }).join('') + '<button type="button" class="pill-x pill-x--all js-f-clear">필터 지우기</button>';
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
      '<p>조건에 맞는 공고가 없습니다. 선택을 줄이거나 마감된 공고까지 함께 보세요.</p>' +
      '<button type="button" class="f-apply js-f-clear">필터 지우기</button>' +
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
    if (root.dataset.region) picked.region.add(root.dataset.region);
    if (root.dataset.category) picked.category.add(root.dataset.category);
    if (root.dataset.district) picked.district.add(root.dataset.district);
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
    var qs = q ? ('?q=' + encodeURIComponent(q)) : '';
    var next = location.pathname + qs;
    if (location.pathname + location.search !== next) history.replaceState(null, '', next);
  }

  function render(reset) {
    paintChips(); paintSum(); paintPills(); paintOpenOnly();
    if (!touched) return;
    if (reset) shown = PAGE;
    compute();
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
    announce(view.length);
    justApplied = false;
    syncURL();
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

  function fillPanel(kind) {
    panelKind = kind;
    orgQ = '';
    saveName = '';
    var html = '';
    panelFoot.hidden = false;
    document.getElementById('f-panel-apply').textContent = '적용';
    document.getElementById('f-panel-reset').hidden = false;

    if (kind === 'region') {
      panelTitle.textContent = '지역';
      html += '<div class="f-group"><h3>일반 필터 · 광역</h3><div class="f-opt-row" id="f-live-region"></div></div>';
      html += '<div class="f-group"><h3>시군구</h3><div class="f-opt-row" id="f-live-district"></div></div>';
      panelBody.innerHTML = html;
      var host = document.getElementById('f-live-region');
      var tpl = document.getElementById('f-opt-region');
      if (tpl) host.innerHTML = tpl.innerHTML;
      paintDistrictOpts();
      setPressed();
    } else if (kind === 'category') {
      panelTitle.textContent = '분야';
      panelBody.innerHTML = '<div class="f-group"><h3>일반 필터 · 사업분야</h3><div id="f-live-cat"></div></div>';
      var cat = document.getElementById('f-live-cat');
      var ct = document.getElementById('f-opt-category');
      if (ct) cat.innerHTML = ct.innerHTML;
      setPressed();
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
      var amt = document.getElementById('f-live-amt');
      var at = document.getElementById('f-opt-amount');
      if (at) amt.innerHTML = at.innerHTML;
      setPressed();
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
    } else if (kind === 'save') {
      panelTitle.textContent = '조건 저장';
      var auto = defaultPresetName();
      panelBody.innerHTML = '<div class="f-group"><p class="f-help">이 브라우저에만 저장됩니다. 로그인 없이 localStorage를 씁니다.</p>' +
        '<label class="f-help" for="f-save-name">이름</label>' +
        '<input class="f-search" id="f-save-name" value="' + MagampanCard.esc(auto) + '" maxlength="40"></div>';
      document.getElementById('f-panel-apply').textContent = '저장';
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
          html += '<div class="f-preset" data-i="' + i + '"><b>' + MagampanCard.esc(item.name) +
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
      return '<button type="button" class="f-opt" data-k="district" data-v="' + MagampanCard.esc(n) + '">' +
        MagampanCard.esc(n) + '</button>';
    }).join('');
    setPressed(host);
  }

  function paintOrgs() {
    var host = document.getElementById('f-live-org');
    if (!host) return;
    var qv = orgQ.toLowerCase();
    var rows = orgsFor().filter(function (o) { return !qv || o.name.toLowerCase().indexOf(qv) >= 0; });
    host.innerHTML = rows.slice(0, 80).map(function (o) {
      return '<button type="button" class="f-opt" data-k="org" data-v="' + MagampanCard.esc(o.name) + '"><b>' +
        MagampanCard.esc(o.name) + '</b><span>' + o.n + '건</span></button>';
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

  function openPanel(kind) {
    draft = clonePicked(picked);
    fillPanel(kind);
    overlay.hidden = false;
    document.body.classList.add('f-lock');
    chipBtns.forEach(function (b) {
      b.setAttribute('aria-expanded', b.dataset.panel === kind ? 'true' : 'false');
    });
    panel.focus();
  }
  function closePanel() {
    overlay.hidden = true;
    document.body.classList.remove('f-lock');
    chipBtns.forEach(function (b) { b.setAttribute('aria-expanded', 'false'); });
    panelKind = '';
    draft = null;
  }

  function applyDraft() {
    if (panelKind === 'save') {
      var inp = document.getElementById('f-save-name');
      var name = ((inp && inp.value) || defaultPresetName()).trim() || '지금 조건';
      var list = readPresets().filter(function (x) { return x.name !== name; });
      list.unshift({ name: name, state: serialize(picked), q: q, openOnly: openOnly, sortBy: sortBy });
      writePresets(list.slice(0, 8));
      closePanel();
      return;
    }
    if (!draft) { closePanel(); return; }
    if (draft.from || draft.to) draft.period.add('range');
    picked = clonePicked(draft);
    touched = true;
    justApplied = true;
    closePanel();
    render(true);
  }

  function resetDraftGroup() {
    if (!draft) return;
    if (panelKind === 'region') { draft.region.clear(); draft.district.clear(); paintDistrictOpts(); }
    else if (panelKind === 'category') draft.category.clear();
    else if (panelKind === 'org') draft.org.clear();
    else if (panelKind === 'amount') draft.amount.clear();
    else if (panelKind === 'period') { draft.period.clear(); draft.from = ''; draft.to = ''; fillPanel('period'); return; }
    setPressed();
    if (panelKind === 'org') paintOrgs();
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

  var t;
  document.getElementById('f-q').addEventListener('input', function (e) {
    clearTimeout(t);
    var v = e.target.value.trim().toLowerCase();
    t = setTimeout(function () { q = v; touched = true; render(true); }, 180);
  });

  fetch('/notices.json')
    .then(function (r) { return r.json(); })
    .then(function (d) {
      all = d; root.classList.add('ready');
      paintChips(); paintSum(); paintPills(); paintOpenOnly();
      if (touched) render(true);
    })
    .catch(function () { /* 검색 폼 GET /all/ 은 그대로 둔다 */ });
})();
