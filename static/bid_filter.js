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
  var seed = new URLSearchParams(location.search);
  var seedQ = (seed.get('q') || '').trim();
  if (seedQ) input.value = seedQ;

  var defaults = {
    kind: (find && find.dataset.kind) || '',
    due: (find && find.dataset.due) || '',
    region: (find && find.dataset.region) || ''
  };
  var picked = {
    kind: seed.get('kind') || defaults.kind,
    due: seed.get('due') || defaults.due,
    q: seedQ.toLowerCase()
  };
  if (defaults.kind) picked.kind = defaults.kind;

  var feed = null;
  var serverRows = [].slice.call(board.querySelectorAll('a.row'));
  var KIND = { '물품': 'goods', '용역': 'service', '공사': 'construction', '외자': 'foreign' };

  function esc(s) {
    return String(s).replace(/[<>&"]/g, function (c) {
      return { '<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;' }[c];
    });
  }

  function cls(d, close) {
    var sub = close ? String(close).slice(5, 16) : '';
    if (d < 0) return ['d-c', '마감', sub];
    if (d === 0) return ['d-u', '오늘', (close && String(close).length >= 16 ? String(close).slice(11, 16) : '') + ' 마감'];
    if (d <= 7) return ['d-u', 'D-' + d, sub];
    if (d <= 14) return ['d-s', 'D-' + d, sub];
    return ['d-o', 'D-' + d, sub];
  }

  function slugOf(a) {
    return a.ks || KIND[a.k] || '';
  }

  function rowHTML(a) {
    var c = cls(a.d, a.e);
    var tags = '<span class="pill pill-dday ' + c[0] + '">' + esc(c[1]) + '</span>';
    if (a.k) tags += '<span class="pill">' + esc(a.k) + '</span>';
    if (a.r) tags += '<span class="pill">' + esc(a.r) + '</span>';
    var amt = a.m
      ? '<span class="amt">' + esc(a.m) + '</span>'
      : '<span class="amt amt-empty">추정가격은 원문 확인</span>';
    var when = c[2] ? '<span class="when">' + esc(c[2]) + '</span>' : '';
    return '<a class="row" href="/bid/notice/' + esc(a.i) + '/" data-kind="' + esc(a.k || '') +
      '" data-kind-slug="' + esc(slugOf(a)) + '" data-d="' + esc(a.d) + '" data-region="' + esc(a.r || '') + '">' +
      '<div class="row-body">' +
      '<div class="row-tags">' + tags + '</div>' +
      '<h3>' + esc(a.t) + '</h3>' +
      (a.o ? '<div class="meta"><i>' + esc(a.o) + '</i></div>' : '') +
      '<div class="row-foot">' + amt + when + '</div></div></a>';
  }

  function matchItem(a) {
    var ks = slugOf(a);
    if (picked.kind && ks !== picked.kind) return false;
    if (defaults.region && a.r !== defaults.region) return false;
    if (picked.due === 'today' && a.d !== 0) return false;
    if (picked.due === 'week' && (a.d < 0 || a.d > 7)) return false;
    if (picked.q) {
      var hay = (a.t + ' ' + a.o).toLowerCase();
      if (hay.indexOf(picked.q) < 0) return false;
    }
    return true;
  }

  function matchDom(el) {
    var ks = el.getAttribute('data-kind-slug') || KIND[el.getAttribute('data-kind')] || '';
    var d = parseInt(el.getAttribute('data-d'), 10);
    var r = el.getAttribute('data-region') || '';
    if (picked.kind && ks !== picked.kind) return false;
    if (defaults.region && r !== defaults.region) return false;
    if (picked.due === 'today' && d !== 0) return false;
    if (picked.due === 'week' && (d < 0 || d > 7)) return false;
    if (picked.q) {
      var hay = (el.textContent || '').toLowerCase();
      if (hay.indexOf(picked.q) < 0) return false;
    }
    return true;
  }

  function emptyHTML() {
    return '<div class="empty-filter" role="status">' +
      '<p>조건에 맞는 입찰공고가 없습니다. 종류·마감일시 선택을 줄이거나 검색어를 줄여 보세요.</p>' +
      '<button type="button" class="f-apply" id="bid-clear">필터 지우기</button>' +
      '<p class="empty-pop">이어서 보기</p>' +
      '<div class="chips">' +
      '<a href="/bid/">입찰 허브</a>' +
      '<a href="/bid/urgent/">이번 주 마감</a>' +
      '<a href="/">지원 탭</a>' +
      '</div></div>';
  }

  function paintChips() {
    if (!find) return;
    find.querySelectorAll('[data-bid-kind]').forEach(function (el) {
      var on = el.getAttribute('data-bid-kind') === picked.kind;
      el.classList.toggle('is-on', on);
      if (on) el.setAttribute('aria-current', 'page');
      else el.removeAttribute('aria-current');
    });
    find.querySelectorAll('[data-bid-due]').forEach(function (el) {
      var on = el.getAttribute('data-bid-due') === picked.due;
      el.classList.toggle('is-on', on);
      el.setAttribute('aria-pressed', on ? 'true' : 'false');
    });
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
    var view = list.filter(matchItem);
    view.sort(function (x, y) { return (x.d < 0) - (y.d < 0) || x.d - y.d; });
    var weekN = view.filter(function (a) { return a.d >= 0 && a.d <= 7; }).length;
    hideMore();
    board.querySelectorAll('.sec-head, a.row, p.note, .empty-filter, a.more').forEach(function (el) {
      el.remove();
    });
    if (!view.length) {
      board.innerHTML = emptyHTML();
      announce(0, 0);
      return;
    }
    var html = '';
    view.slice(0, shown).forEach(function (a) { html += rowHTML(a); });
    board.innerHTML = html;
    appendMore(view.length - shown);
    announce(view.length, weekN);
  }

  function paintDom() {
    hideMore();
    var empty = board.querySelector('.empty-filter, :scope > p.note');
    var heads = board.querySelectorAll('.sec-head');
    heads.forEach(function (h) { h.hidden = true; });
    var hit = 0;
    var weekN = 0;
    serverRows.forEach(function (el) {
      var ok = matchDom(el);
      if (!ok) { el.hidden = true; return; }
      hit += 1;
      if (parseInt(el.getAttribute('data-d'), 10) <= 7 &&
          parseInt(el.getAttribute('data-d'), 10) >= 0) weekN += 1;
      el.hidden = hit > shown;
    });
    if (empty) empty.remove();
    var leftover = board.querySelector('.empty-filter');
    if (leftover) leftover.remove();
    if (hit === 0) {
      board.insertAdjacentHTML('beforeend', emptyHTML());
    } else {
      appendMore(hit - shown);
    }
    announce(hit, weekN);
  }

  function filtered() {
    return !!(picked.q || (picked.kind && picked.kind !== defaults.kind) ||
      (picked.due && picked.due !== defaults.due));
  }

  function apply() {
    paintChips();
    if (feed) paintFeed(feed);
    else paintDom();
  }

  function syncURL() {
    var u = new URL(location.href);
    if (picked.q) u.searchParams.set('q', input.value.trim());
    else u.searchParams.delete('q');
    if (!defaults.kind && picked.kind) u.searchParams.set('kind', picked.kind);
    else u.searchParams.delete('kind');
    if (picked.due && picked.due !== defaults.due) u.searchParams.set('due', picked.due);
    else if (!defaults.due) u.searchParams.delete('due');
    else u.searchParams.delete('due');
    history.replaceState(null, '', u.pathname + u.search);
  }

  function clearFilters() {
    picked.q = '';
    input.value = '';
    picked.kind = defaults.kind;
    picked.due = defaults.due;
    shown = PAGE;
    syncURL();
    apply();
  }

  if (find) {
    find.addEventListener('click', function (e) {
      var due = e.target.closest('[data-bid-due]');
      if (due) {
        var v = due.getAttribute('data-bid-due');
        picked.due = picked.due === v ? defaults.due : v;
        shown = PAGE;
        syncURL();
        apply();
        return;
      }
      var kind = e.target.closest('[data-bid-kind]');
      if (!kind) return;
      if (defaults.kind) return;
      e.preventDefault();
      var ks = kind.getAttribute('data-bid-kind');
      picked.kind = picked.kind === ks ? '' : ks;
      shown = PAGE;
      syncURL();
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
  });

  var timer;
  input.addEventListener('input', function () {
    clearTimeout(timer);
    timer = setTimeout(function () {
      shown = PAGE;
      picked.q = (input.value || '').trim().toLowerCase();
      syncURL();
      apply();
    }, 180);
  });

  paintChips();
  if (seedQ || filtered()) apply();
  else {
    var staticMore = document.getElementById('bid-more-static');
    if (!staticMore && serverRows.length > PAGE) {
      shown = PAGE;
      paintDom();
    }
  }

  fetch('/bids.json')
    .then(function (r) { return r.json(); })
    .then(function (d) {
      feed = d;
      if (hub || seedQ || filtered()) {
        shown = PAGE;
        apply();
      }
    })
    .catch(function () {
      if (seedQ || filtered()) paintDom();
    });
})();
