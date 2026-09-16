/* 입찰 목록: 이 페이지 행 + 선택적으로 bids.json.
   notices.json(지원) 을 읽지 않아 두 피드가 섞이지 않는다. */
(function () {
  var board = document.getElementById('bid-board');
  var input = document.getElementById('bid-q');
  var find = document.getElementById('bid-find');
  if (!board || !input) return;

  var PAGE = parseInt(board.dataset.pageSize, 10) || 20;
  var shown = PAGE;
  var hub = location.pathname === '/bid/' || location.pathname === '/bid';
  var PRESET_KEY = 'magampan.bid.presets.v1';
  var EMAIL = (find && find.dataset.email) || 'qwqw050009@gmail.com';
  var KIND = { '물품': 'goods', '용역': 'service', '공사': 'construction', '외자': 'foreign' };
  var KIND_NAME = { goods: '물품', service: '용역', construction: '공사', foreign: '외자' };
  var AMT_NAMES = {};
  var amtTpl = document.getElementById('bid-opt-amount');
  if (amtTpl) {
    amtTpl.content.querySelectorAll('.f-opt').forEach(function (b) {
      AMT_NAMES[b.dataset.v] = (b.querySelector('b') || b).textContent.trim();
    });
  }

  function esc(s) {
    return window.MagampanCard ? MagampanCard.esc(s) : String(s == null ? '' : s).replace(/[<>&"]/g, function (c) {
      return { '<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;' }[c];
    });
  }

  var defaults = {
    kind: (find && find.dataset.kind) || '',
    due: (find && find.dataset.due) || '',
    region: (find && find.dataset.region) || ''
  };

  function emptyPicked() {
    return {
      kind: new Set(), deadline: new Set(), org: new Set(), amount: new Set(),
      region: new Set(), q: '', open: true, sort: 'dday'
    };
  }
  var picked = emptyPicked();
  if (defaults.kind) picked.kind.add(defaults.kind);
  if (defaults.due) picked.deadline.add(defaults.due);
  if (defaults.region) picked.region.add(defaults.region);

  function lockedKeys() {
    return { kind: !!defaults.kind, deadline: !!defaults.due, region: !!defaults.region };
  }

  var urlSt = window.MagampanState ? MagampanState.parseBid(location.search) : null;
  if (urlSt) {
    (urlSt.kind || []).forEach(function (v) { if (!defaults.kind) picked.kind.add(v); });
    (urlSt.deadline || []).forEach(function (v) { if (!defaults.due) picked.deadline.add(v); });
    (urlSt.org || []).forEach(function (v) { picked.org.add(v); });
    (urlSt.amount || []).forEach(function (v) { picked.amount.add(v); });
    (urlSt.region || []).forEach(function (v) { if (!defaults.region) picked.region.add(v); });
    picked.q = (urlSt.q || '').toLowerCase();
    picked.open = urlSt.open !== false;
    picked.sort = urlSt.sort || 'dday';
    if (urlSt.q) input.value = urlSt.q;
    var so = document.getElementById('bid-sort');
    if (so) so.value = picked.sort;
    var oo = document.getElementById('bid-openonly');
    if (oo) oo.checked = picked.open;
  }

  var feed = null;
  var serverRows = [].slice.call(board.querySelectorAll('.row'));
  var overlay = document.getElementById('bid-overlay');
  var panel = document.getElementById('bid-panel');
  var panelTitle = document.getElementById('bid-panel-title');
  var panelBody = document.getElementById('bid-panel-body');
  var panelFoot = document.getElementById('bid-panel-foot');
  var panelKind = '';
  var draft = null;
  var orgQ = '';

  function slugOf(a) {
    return a.ks || KIND[a.k] || '';
  }
  function whenOf(a) {
    if (a.du) return a.du;
    if (!a.e) return '마감일시 미상';
    if (a.tm) return a.e + ' (KST)';
    if (/\d{1,2}:\d{2}/.test(a.e)) return a.e + ' (KST)';
    return a.e + ' · 시간 미상';
  }
  function dlabel(a) {
    var st = a.st || (a.d < 0 ? 'closed' : 'open');
    if (st === 'closed' || a.d < 0) return ['d-c', '마감'];
    if (a.d === 0) return ['d-u', '오늘'];
    if (a.d <= 7) return ['d-u', 'D-' + a.d];
    if (a.d <= 14) return ['d-s', 'D-' + a.d];
    return ['d-o', 'D-' + a.d];
  }

  function rowHTML(a) {
    var c = dlabel(a);
    var sl = a.sl || (a.st === 'upcoming' ? '예정' : a.st === 'closed' ? '마감' : '진행');
    var tags = '<span class="pill pill-dday ' + c[0] + '">' + esc(c[1]) + '</span>';
    if (sl && sl !== c[1]) tags += '<span class="pill pill-st">' + esc(sl) + '</span>';
    if (a.k) tags += '<span class="pill">' + esc(a.k) + '</span>';
    if (a.r) tags += '<span class="pill">' + esc(a.r) + '</span>';
    tags += '<span class="pill pill-src">나라장터</span>';
    if (a.corr) tags += '<span class="pill pill-corr">정정공고</span>';
    else if (a.n) tags += '<span class="pill pill-new">신규</span>';
    var amt = a.m
      ? '<span class="amt">' + esc(a.m) + '</span>'
      : '<span class="amt amt-empty">추정가격은 원문 확인</span>';
    var meta = '';
    if (a.o) meta += '<i>' + esc(a.o) + '</i>';
    if (a.no) meta += '<i>공고 ' + esc(a.no) + '</i>';
    var ext = a.u
      ? '<a class="row-ext" href="' + esc(a.u) + '" rel="nofollow noopener" target="_blank">원문</a>'
      : '';
    var starred = window.Scrap && window.Scrap.has(a.i, 'bid');
    var due = whenOf(a);
    return '<article class="row row--bid" data-kind="' + esc(a.k || '') +
      '" data-cmp="bid" data-id="' + esc(a.i) +
      '" data-title="' + esc(a.t) + '" data-org="' + esc(a.o || '') +
      '" data-due="' + esc(due) + '" data-amt="' + esc(a.m || '') +
      '" data-src="나라장터" data-kind-slug="' + esc(slugOf(a)) +
      '" data-d="' + esc(a.d) + '" data-region="' + esc(a.r || '') +
      '" data-amount="' + esc(a.b || '') + '">' +
      '<button type="button" class="cmp" data-id="' + esc(a.i) +
      '" data-kind="bid" aria-pressed="false" aria-label="비교에 넣기"></button>' +
      '<a class="row-body" href="/bid/notice/' + esc(a.i) + '/">' +
      '<div class="row-tags">' + tags + '</div>' +
      '<h3>' + esc(a.t) + '</h3>' +
      (meta ? '<div class="meta">' + meta + '</div>' : '') +
      '<div class="row-foot">' + amt + '<span class="when">' + esc(due) + '</span></div></a>' +
      '<button type="button" class="star" data-id="' + esc(a.i) +
      '" data-kind="bid" aria-pressed="' + (starred ? 'true' : 'false') +
      '" aria-label="스크랩"></button>' +
      ext + '</article>';
  }

  function matchItem(a) {
    var ks = slugOf(a);
    if (picked.kind.size && !picked.kind.has(ks)) return false;
    if (picked.region.size && !picked.region.has(a.r || '')) return false;
    if (picked.org.size && !picked.org.has(a.o || '')) return false;
    if (picked.amount.size && !picked.amount.has(a.b || 'unk')) return false;
    if (picked.open && (a.st === 'closed' || a.d < 0)) return false;
    if (picked.deadline.size) {
      var hit = false;
      if (picked.deadline.has('today') && a.d === 0) hit = true;
      if (picked.deadline.has('week') && a.d >= 0 && a.d <= 7) hit = true;
      if (!hit) return false;
    }
    if (picked.q) {
      var hay = (a.t + ' ' + (a.o || '') + ' ' + (a.no || '')).toLowerCase();
      if (hay.indexOf(picked.q) < 0) return false;
    }
    return true;
  }

  function emptyHTML() {
    return '<div class="empty-filter" role="status">' +
      '<p>조건에 맞는 입찰공고가 없습니다. 종류·마감일시 선택을 줄이거나 검색어를 줄여 보세요.</p>' +
      '<div class="empty-actions">' +
      '<button type="button" class="f-apply" id="bid-relax">필터 완화</button>' +
      '<a class="hero-secondary" href="/bid/">전체 보기</a>' +
      '<button type="button" class="hero-secondary" id="bid-alert-empty">이 조건 알림</button>' +
      '</div>' +
      '<p class="empty-pop">이어서 보기</p>' +
      '<div class="chips">' +
      '<a href="/bid/">입찰 허브</a>' +
      '<a href="/bid/urgent/">이번 주 마감</a>' +
      '<a href="/">지원 탭</a>' +
      '</div></div>';
  }

  function toURLState() {
    return {
      q: input.value.trim(),
      kind: [...picked.kind],
      deadline: [...picked.deadline],
      org: [...picked.org],
      amount: [...picked.amount],
      region: [...picked.region],
      sort: picked.sort,
      open: picked.open
    };
  }

  function syncURL() {
    var next = location.pathname;
    if (window.MagampanState) next = location.pathname + MagampanState.serializeBid(toURLState(), lockedKeys());
    else {
      var u = new URL(location.href);
      u.search = '';
      if (picked.q) u.searchParams.set('q', input.value.trim());
      next = u.pathname + u.search;
    }
    if (location.pathname + location.search !== next) history.replaceState(null, '', next);
  }

  function paintChips() {
    if (!find) return;
    find.querySelectorAll('[data-bid-kind]').forEach(function (el) {
      var on = picked.kind.has(el.getAttribute('data-bid-kind'));
      el.classList.toggle('is-on', on);
      if (on && picked.kind.size === 1) el.setAttribute('aria-current', 'page');
      else el.removeAttribute('aria-current');
    });
    find.querySelectorAll('[data-bid-due]').forEach(function (el) {
      var on = picked.deadline.has(el.getAttribute('data-bid-due'));
      el.classList.toggle('is-on', on);
      el.setAttribute('aria-pressed', on ? 'true' : 'false');
    });
    var oo = document.getElementById('bid-openonly');
    if (oo) {
      oo.checked = picked.open;
      var lab = oo.closest('.f-chip--check');
      if (lab) lab.classList.toggle('is-on', picked.open);
    }
    paintPills();
  }

  function paintPills() {
    var box = document.getElementById('bid-pills');
    if (!box) return;
    var pills = [];
    picked.kind.forEach(function (v) {
      if (defaults.kind === v) return;
      pills.push({ k: 'kind', v: v, label: KIND_NAME[v] || v });
    });
    picked.deadline.forEach(function (v) {
      if (defaults.due === v) return;
      pills.push({ k: 'deadline', v: v, label: v === 'today' ? '오늘 마감' : '이번 주' });
    });
    picked.org.forEach(function (v) { pills.push({ k: 'org', v: v, label: v }); });
    picked.amount.forEach(function (v) { pills.push({ k: 'amount', v: v, label: AMT_NAMES[v] || v }); });
    picked.region.forEach(function (v) {
      if (defaults.region === v) return;
      pills.push({ k: 'region', v: v, label: v });
    });
    if (picked.q) pills.push({ k: 'q', v: picked.q, label: '검색' });
    if (!pills.length) { box.hidden = true; box.innerHTML = ''; return; }
    box.hidden = false;
    box.innerHTML = pills.map(function (p) {
      return '<button type="button" class="pill-x" data-clear="' + esc(p.k) + '" data-v="' + esc(p.v) + '">' +
        esc(p.label) + ' ×</button>';
    }).join('') + '<button type="button" class="pill-x pill-x--all" id="bid-clear">전체 해제</button>';
  }

  function announce(n, week) {
    var text = n + '건' + (week ? ' · 이번 주 마감 ' + week + '건' : '');
    var countEl = document.getElementById('bid-count');
    if (countEl) countEl.textContent = text;
    var live = document.getElementById('bid-live');
    if (live) {
      live.textContent = '';
      live.textContent = '입찰 목록 ' + n + '건입니다.';
    }
  }

  function hideMore() {
    var b = document.getElementById('bid-more');
    if (b) b.remove();
    var s = document.getElementById('bid-more-static');
    if (s) s.hidden = true;
  }

  function appendMore(remain) {
    if (remain <= 0) return;
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'more';
    btn.id = 'bid-more';
    btn.textContent = remain + '건 더 보기';
    board.appendChild(btn);
  }

  function paintFeed(list) {
    var y = window.scrollY;
    var view = list.filter(matchItem);
    if (picked.sort === 'new') view.sort(function (x, y) { return (y.e || '') < (x.e || '') ? -1 : 1; });
    else view.sort(function (x, y) { return (x.d < 0) - (y.d < 0) || x.d - y.d; });
    var weekN = view.filter(function (a) { return a.d >= 0 && a.d <= 7; }).length;
    hideMore();
    board.classList.add('is-busy');
    var sk = '';
    for (var i = 0; i < 3; i++) {
      sk += '<article class="row sk-row" aria-hidden="true"><div class="sk-bar"></div>' +
        '<div class="sk-bar sk-bar--lg"></div><div class="sk-bar sk-bar--sm"></div></article>';
    }
    board.innerHTML = sk;
    requestAnimationFrame(function () {
      if (!view.length) {
        board.innerHTML = emptyHTML();
        announce(0, 0);
        board.classList.remove('is-busy');
        window.scrollTo(0, y);
        return;
      }
      var html = '';
      view.slice(0, shown).forEach(function (a) { html += rowHTML(a); });
      board.innerHTML = html;
      appendMore(view.length - shown);
      board.classList.remove('is-busy');
      announce(view.length, weekN);
      window.scrollTo(0, y);
    });
  }

  function filtered() {
    return !!(picked.q || (picked.kind.size && !(defaults.kind && picked.kind.size === 1 && picked.kind.has(defaults.kind))) ||
      (picked.deadline.size && !(defaults.due && picked.deadline.has(defaults.due) && picked.deadline.size === 1)) ||
      picked.org.size || picked.amount.size ||
      (picked.region.size && !defaults.region) ||
      picked.open === false || picked.sort !== 'dday');
  }

  function apply() {
    paintChips();
    syncURL();
    if (feed) paintFeed(feed);
  }

  function clearFilters() {
    picked = emptyPicked();
    if (defaults.kind) picked.kind.add(defaults.kind);
    if (defaults.due) picked.deadline.add(defaults.due);
    if (defaults.region) picked.region.add(defaults.region);
    input.value = '';
    shown = PAGE;
    var so = document.getElementById('bid-sort');
    if (so) so.value = 'dday';
    var oo = document.getElementById('bid-openonly');
    if (oo) oo.checked = true;
    apply();
  }

  function relaxFilters() {
    if (picked.open) picked.open = false;
    else if (picked.q) { picked.q = ''; input.value = ''; }
    else if (picked.amount.size) picked.amount.clear();
    else if (picked.org.size) picked.org.clear();
    else if (picked.deadline.size && !defaults.due) picked.deadline.clear();
    else if (picked.kind.size && !defaults.kind) picked.kind.clear();
    shown = PAGE;
    apply();
  }

  function orgsFor() {
    var map = {};
    (feed || []).forEach(function (a) {
      if (!a.o) return;
      map[a.o] = (map[a.o] || 0) + 1;
    });
    return Object.keys(map).sort(function (a, b) { return map[b] - map[a] || a.localeCompare(b, 'ko'); })
      .map(function (name) { return { name: name, n: map[name] }; });
  }

  function cloneDraft() {
    return {
      kind: new Set(picked.kind), deadline: new Set(picked.deadline),
      org: new Set(picked.org), amount: new Set(picked.amount),
      region: new Set(picked.region)
    };
  }

  function fillPanel(kind) {
    panelKind = kind;
    orgQ = '';
    panelFoot.hidden = false;
    document.getElementById('bid-panel-apply').textContent = '적용';
    document.getElementById('bid-panel-reset').hidden = false;
    if (kind === 'org') {
      panelTitle.textContent = '발주기관';
      panelBody.innerHTML = '<div class="f-group"><h3>수요·발주기관</h3>' +
        '<input class="f-search" id="bid-org-q" type="search" placeholder="기관명 찾기" autocomplete="off">' +
        '<div id="bid-live-org"></div></div>';
      paintOrgs();
    } else if (kind === 'amount') {
      panelTitle.textContent = '추정가격';
      panelBody.innerHTML = '<div class="f-group"><h3>나라장터에 값이 있는 구간만</h3>' +
        '<p class="f-help">없는 추정가격은 만들지 않습니다.</p><div id="bid-live-amt"></div></div>';
      var host = document.getElementById('bid-live-amt');
      if (amtTpl) host.innerHTML = amtTpl.innerHTML;
      setPressed();
    } else if (kind === 'all') {
      panelTitle.textContent = '필터';
      var html = '<div class="f-group"><h3>종류</h3><div class="f-opt-row">';
      ['goods', 'service', 'construction', 'foreign'].forEach(function (k) {
        html += '<button type="button" class="f-opt" data-k="kind" data-v="' + k + '">' + (KIND_NAME[k] || k) + '</button>';
      });
      html += '</div></div><div class="f-group"><h3>기간</h3>';
      html += '<button type="button" class="f-opt" data-k="deadline" data-v="today"><b>오늘 마감</b></button>';
      html += '<button type="button" class="f-opt" data-k="deadline" data-v="week"><b>이번 주</b></button></div>';
      html += '<div class="f-group"><h3>추정가격</h3><div id="bid-live-amt"></div></div>';
      panelBody.innerHTML = html;
      var amtH = document.getElementById('bid-live-amt');
      if (amtTpl) amtH.innerHTML = amtTpl.innerHTML;
      setPressed();
    } else if (kind === 'save' || kind === 'alert') {
      var desc = window.MagampanState ? MagampanState.describeBid(toURLState()) : '지금 조건';
      panelTitle.textContent = kind === 'alert' ? '이 조건 알림' : '조건 저장';
      panelBody.innerHTML = '<div class="f-group"><p class="f-help">이 브라우저에만 저장됩니다. 로그인·결제는 없습니다.</p>' +
        '<p class="f-help">지금 조건: ' + esc(desc) + '</p>' +
        '<input class="f-search" id="bid-save-name" value="' + esc(desc.slice(0, 40) || '지금 조건') + '" maxlength="40"></div>';
      document.getElementById('bid-panel-apply').textContent = kind === 'alert' ? '저장하고 메일 열기' : '저장';
      document.getElementById('bid-panel-reset').hidden = true;
    } else if (kind === 'load') {
      panelTitle.textContent = '조건 불러오기';
      var list = readPresets();
      if (!list.length) {
        panelBody.innerHTML = '<p class="f-help">저장된 조건이 없습니다.</p>';
        panelFoot.hidden = true;
      } else {
        panelBody.innerHTML = '<div class="f-preset-list">' + list.map(function (item, i) {
          return '<div class="f-preset" data-i="' + i + '"><b>' + esc(item.name) +
            '</b><button type="button" class="f-preset-del" data-del="' + i + '">삭제</button></div>';
        }).join('') + '</div>';
        panelFoot.hidden = true;
      }
    }
  }

  function setPressed() {
    if (!draft || !panelBody) return;
    panelBody.querySelectorAll('.f-opt').forEach(function (b) {
      var k = b.dataset.k, v = b.dataset.v;
      if (!k || !draft[k]) return;
      b.setAttribute('aria-pressed', draft[k].has(v) ? 'true' : 'false');
    });
  }

  function paintOrgs() {
    var host = document.getElementById('bid-live-org');
    if (!host) return;
    var qv = orgQ.toLowerCase();
    var rows = orgsFor().filter(function (o) { return !qv || o.name.toLowerCase().indexOf(qv) >= 0; });
    host.innerHTML = rows.slice(0, 80).map(function (o) {
      return '<button type="button" class="f-opt" data-k="org" data-v="' + esc(o.name) + '"><b>' +
        esc(o.name) + '</b><span>' + o.n + '건</span></button>';
    }).join('') || '<p class="f-help">맞는 기관이 없습니다.</p>';
    setPressed();
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
    if (!overlay) return;
    draft = cloneDraft();
    fillPanel(kind);
    overlay.hidden = false;
    document.body.classList.add('f-lock');
    if (panel) panel.focus();
  }
  function closePanel() {
    if (!overlay) return;
    overlay.hidden = true;
    document.body.classList.remove('f-lock');
    panelKind = '';
    draft = null;
  }

  function savePreset(andMail) {
    var inp = document.getElementById('bid-save-name');
    var name = ((inp && inp.value) || '지금 조건').trim();
    var list = readPresets().filter(function (x) { return x.name !== name; });
    list.unshift({ name: name, state: toURLState() });
    writePresets(list.slice(0, 8));
    if (andMail) {
      var desc = window.MagampanState ? MagampanState.describeBid(toURLState()) : name;
      var body = '아래 입찰 조건으로 마감 알림을 받고 싶습니다.\n\n' + desc +
        '\n\n페이지: ' + location.href + '\n\n(로그인·결제는 없습니다.)';
      location.href = 'mailto:' + EMAIL + '?subject=' +
        encodeURIComponent('[마감판] 입찰 조건 알림') + '&body=' + encodeURIComponent(body);
    }
  }

  if (overlay) {
    overlay.addEventListener('click', function (e) { if (e.target === overlay) closePanel(); });
    document.getElementById('bid-panel-x').addEventListener('click', closePanel);
    document.getElementById('bid-panel-apply').addEventListener('click', function () {
      if (panelKind === 'save') { savePreset(false); closePanel(); return; }
      if (panelKind === 'alert') { savePreset(true); closePanel(); return; }
      if (draft) {
        picked.kind = draft.kind;
        picked.deadline = draft.deadline;
        picked.org = draft.org;
        picked.amount = draft.amount;
        picked.region = draft.region;
        if (defaults.kind) picked.kind.add(defaults.kind);
        if (defaults.due) picked.deadline.add(defaults.due);
        if (defaults.region) picked.region.add(defaults.region);
      }
      shown = PAGE;
      closePanel();
      apply();
    });
    document.getElementById('bid-panel-reset').addEventListener('click', function () {
      if (!draft) return;
      if (panelKind === 'org') draft.org.clear();
      else if (panelKind === 'amount') draft.amount.clear();
      else if (panelKind === 'all') {
        if (!defaults.kind) draft.kind.clear();
        if (!defaults.due) draft.deadline.clear();
        draft.amount.clear();
      }
      setPressed();
      if (panelKind === 'org') paintOrgs();
    });
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
        if (!item || !item.state) return;
        var st = item.state;
        picked = emptyPicked();
        (st.kind || []).forEach(function (v) { picked.kind.add(v); });
        (st.deadline || []).forEach(function (v) { picked.deadline.add(v); });
        (st.org || []).forEach(function (v) { picked.org.add(v); });
        (st.amount || []).forEach(function (v) { picked.amount.add(v); });
        picked.q = (st.q || '').toLowerCase();
        input.value = st.q || '';
        if (defaults.kind) picked.kind.add(defaults.kind);
        closePanel();
        shown = PAGE;
        apply();
        return;
      }
      var opt = e.target.closest('.f-opt');
      if (!opt || !draft) return;
      var k = opt.dataset.k, v = opt.dataset.v;
      if (!k || !draft[k]) return;
      if (draft[k].has(v)) draft[k].delete(v); else draft[k].add(v);
      opt.setAttribute('aria-pressed', draft[k].has(v) ? 'true' : 'false');
    });
    panelBody.addEventListener('input', function (e) {
      if (e.target.id === 'bid-org-q') { orgQ = e.target.value.trim(); paintOrgs(); }
    });
  }

  if (find) {
    find.addEventListener('click', function (e) {
      var panelBtn = e.target.closest('[data-bid-panel]');
      if (panelBtn) {
        e.preventDefault();
        openPanel(panelBtn.getAttribute('data-bid-panel'));
        return;
      }
      var due = e.target.closest('[data-bid-due]');
      if (due) {
        var v = due.getAttribute('data-bid-due');
        if (picked.deadline.has(v) && picked.deadline.size === 1) picked.deadline.clear();
        else { picked.deadline = new Set([v]); }
        if (defaults.due) picked.deadline.add(defaults.due);
        shown = PAGE;
        apply();
        return;
      }
      var kind = e.target.closest('[data-bid-kind]');
      if (!kind) return;
      if (defaults.kind) return;
      e.preventDefault();
      var ks = kind.getAttribute('data-bid-kind');
      if (picked.kind.has(ks)) picked.kind.delete(ks); else picked.kind.add(ks);
      shown = PAGE;
      apply();
    });
  }

  var pillsBox = document.getElementById('bid-pills');
  if (pillsBox) {
    pillsBox.addEventListener('click', function (e) {
      if (e.target.id === 'bid-clear' || e.target.classList.contains('pill-x--all')) {
        clearFilters();
        return;
      }
      var btn = e.target.closest('[data-clear]');
      if (!btn) return;
      var k = btn.dataset.clear, v = btn.dataset.v;
      if (k === 'q') { picked.q = ''; input.value = ''; }
      else if (picked[k] && picked[k] instanceof Set) picked[k].delete(v);
      shown = PAGE;
      apply();
    });
  }

  board.addEventListener('click', function (e) {
    if (e.target.id === 'bid-more' || e.target.id === 'bid-more-static') {
      shown += PAGE;
      apply();
      return;
    }
    if (e.target.id === 'bid-clear') clearFilters();
    if (e.target.id === 'bid-relax') relaxFilters();
    if (e.target.id === 'bid-alert-empty') openPanel('alert');
  });

  var sortEl = document.getElementById('bid-sort');
  if (sortEl) sortEl.addEventListener('change', function (e) {
    picked.sort = e.target.value; shown = PAGE; apply();
  });
  var openEl = document.getElementById('bid-openonly');
  if (openEl) openEl.addEventListener('change', function (e) {
    picked.open = e.target.checked; shown = PAGE; apply();
  });

  var timer;
  input.addEventListener('input', function () {
    clearTimeout(timer);
    timer = setTimeout(function () {
      shown = PAGE;
      picked.q = (input.value || '').trim().toLowerCase();
      apply();
    }, 180);
  });

  paintChips();
  if ((urlSt && (urlSt.q || filtered())) || filtered()) apply();

  fetch('/bids.json')
    .then(function (r) { return r.json(); })
    .then(function (d) {
      feed = d;
      if (hub || (urlSt && urlSt.q) || filtered()) {
        shown = PAGE;
        apply();
      }
    })
    .catch(function () {});
})();
