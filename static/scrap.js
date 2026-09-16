/* 스크랩: 로그인 없이 브라우저에 공고 ID만 저장.
   지원 scrap.v1, 입찰 scrap.bid.v1. 계정 이전은 안내만. */
(function () {
  var KEY = 'scrap.v1';
  var KEY_BID = 'scrap.bid.v1';
  var HIDE = 'scrap.notice.off';

  function parse(key) {
    try { return JSON.parse(localStorage.getItem(key) || '[]'); }
    catch (e) { return []; }
  }
  function save(key, v) {
    try { localStorage.setItem(key, JSON.stringify(v)); return true; }
    catch (e) { return false; }
  }
  function read() { return parse(KEY); }
  function readBid() { return parse(KEY_BID); }
  function store(kind) { return kind === 'bid' ? KEY_BID : KEY; }
  function list(kind) { return kind === 'bid' ? readBid() : read(); }
  function has(id, kind) { return list(kind).indexOf(id) >= 0; }
  function toggle(id, kind) {
    kind = kind || 'grant';
    var k = store(kind);
    var v = parse(k);
    var i = v.indexOf(id);
    i >= 0 ? v.splice(i, 1) : v.unshift(id);
    save(k, v);
    return i < 0;
  }
  function usable() {
    try { localStorage.setItem('_t', '1'); localStorage.removeItem('_t'); return true; }
    catch (e) { return false; }
  }
  var OK = usable();

  function notice() {
    if (document.getElementById('scrap-note')) return;
    var off; try { off = localStorage.getItem(HIDE); } catch (e) { off = null; }
    if (off && OK) return;

    var el = document.createElement('div');
    el.id = 'scrap-note';
    el.className = 'snote' + (OK ? '' : ' warn');
    el.setAttribute('role', 'status');
    el.innerHTML = OK
      ? '<p>스크랩은 지금 쓰는 브라우저에만 저장됩니다. 나중에 계정을 만들면 이 목록을 옮길 수 있게 안내할 예정입니다. 결제·로그인은 없습니다.</p>' +
        '<div class="snote-act"><button type="button" data-a="off">다음부터 보지 않기</button>' +
        '<button type="button" data-a="close">확인</button></div>'
      : '<p>이 브라우저에서는 스크랩을 저장할 수 없습니다. 시크릿 모드이거나 저장이 차단된 상태입니다. ' +
        '일반 창에서 열면 저장됩니다.</p>' +
        '<div class="snote-act"><button type="button" data-a="close">확인</button></div>';

    document.body.appendChild(el);
    requestAnimationFrame(function () { el.classList.add('in'); });

    el.addEventListener('click', function (e) {
      var a = e.target.dataset.a;
      if (!a) return;
      if (a === 'off') { try { localStorage.setItem(HIDE, '1'); } catch (err) {} }
      el.classList.remove('in');
      setTimeout(function () { el.remove(); }, 200);
    });

    clearTimeout(notice._t);
    notice._t = setTimeout(function () {
      if (el.isConnected) { el.classList.remove('in'); setTimeout(function () { el.remove(); }, 200); }
    }, 9000);
  }

  window.Scrap = {
    read: read, readBid: readBid, has: has, toggle: toggle, ok: OK,
    kindOf: function (el) {
      return (el && el.dataset && el.dataset.kind) || 'grant';
    }
  };

  function badge() {
    var el = document.getElementById('scrap-count');
    if (!el) return;
    var n = read().length + readBid().length;
    el.textContent = n ? n : '';
    el.hidden = !n;
  }

  function syncStars(id, kind) {
    kind = kind || 'grant';
    var on = has(id, kind);
    document.querySelectorAll('.cta-star[data-id="' + id + '"], .star[data-id="' + id + '"]').forEach(function (el) {
      var k = el.dataset.kind || 'grant';
      if (k !== kind) return;
      el.setAttribute('aria-pressed', String(on));
      var sp = el.querySelector('span');
      if (sp) sp.textContent = on ? '스크랩함' : '스크랩';
    });
  }
  document.querySelectorAll('.cta-star[data-id]').forEach(function (btn) {
    syncStars(btn.dataset.id, btn.dataset.kind || 'grant');
  });
  document.querySelectorAll('.star[data-id]').forEach(function (btn) {
    syncStars(btn.dataset.id, btn.dataset.kind || 'grant');
  });
  document.addEventListener('click', function (e) {
    var b = e.target.closest('.cta-star, .star');
    if (!b || !b.dataset.id) return;
    if (b.classList.contains('star')) e.preventDefault();
    var kind = b.dataset.kind || 'grant';
    var on = toggle(b.dataset.id, kind);
    syncStars(b.dataset.id, kind);
    badge();
    if (on) notice();
    if (document.body.dataset.page === 'scrap' && b.classList.contains('star')) {
      var row = b.closest('.row');
      if (row) row.remove();
      renderPage();
    }
  });

  badge();

  var board = document.getElementById('scrap-board');
  if (!board) return;

  var GRANT = [];
  var BIDS = [];
  var tab = 'grant';

  function bidHTML(a) {
    var c = window.MagampanCard
      ? MagampanCard.cls(a.d, '', a.st)
      : (a.d === 0 ? ['d-u', '오늘'] : ['d-o', 'D-' + a.d]);
    var amt = a.m
      ? '<span class="amt">' + esc(a.m) + '</span>'
      : '<span class="amt amt-empty">추정가격은 원문 확인</span>';
    var starred = has(a.i, 'bid');
    return '<article class="row row--bid" data-kind="' + esc(a.k || '') +
      '" data-cmp="bid" data-id="' + esc(a.i) +
      '" data-title="' + esc(a.t) + '" data-org="' + esc(a.o || '') +
      '" data-due="' + esc(a.du || a.e || '') + '" data-amt="' + esc(a.m || '') +
      '" data-src="나라장터">' +
      '<button type="button" class="cmp" data-id="' + esc(a.i) + '" data-kind="bid" aria-pressed="false" aria-label="비교에 넣기"></button>' +
      '<a class="row-body" href="/bid/notice/' + esc(a.i) + '/">' +
      '<div class="row-tags"><span class="pill pill-dday ' + c[0] + '">' + esc(c[1]) + '</span>' +
      (a.k ? '<span class="pill">' + esc(a.k) + '</span>' : '') +
      '<span class="pill pill-src">나라장터</span>' +
      (a.corr ? '<span class="pill pill-corr">정정공고</span>' : (a.n ? '<span class="pill pill-new">신규</span>' : '')) +
      '</div><h3>' + esc(a.t) + '</h3>' +
      (a.o ? '<div class="meta"><i>' + esc(a.o) + '</i></div>' : '') +
      '<div class="row-foot">' + amt + '<span class="when">' + esc(a.du || a.e || '') + '</span></div></a>' +
      '<button type="button" class="star" data-id="' + esc(a.i) + '" data-kind="bid" aria-pressed="' +
      (starred ? 'true' : 'false') + '" aria-label="스크랩"></button></article>';
  }

  function esc(s) {
    if (window.MagampanCard) return MagampanCard.esc(s);
    return String(s == null ? '' : s).replace(/[<>&"]/g, function (c) {
      return { '<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;' }[c];
    });
  }

  function emptyHTML() {
    if (tab === 'bid') {
      return '<div class="empty-filter" role="status">' +
        '<p>아직 스크랩한 입찰이 없습니다. 입찰 목록에서 별을 누르면 여기에 모입니다.</p>' +
        '<ul class="empty-actions"><li><a class="cta empty-cta" href="/bid/">입찰 허브</a></li></ul></div>';
    }
    return '<div class="empty-filter" role="status">' +
      '<p>아직 스크랩한 지원사업이 없습니다. 공고 목록에서 별을 누르면 여기에 모입니다.</p>' +
      '<ul class="empty-actions"><li><a class="cta empty-cta" href="/">공고 보러 가기</a></li></ul></div>';
  }

  function renderPage() {
    var ids = tab === 'bid' ? readBid() : read();
    var pool = tab === 'bid' ? BIDS : GRANT;
    var items = ids.map(function (i) {
      return pool.find(function (a) { return a.i === i; });
    }).filter(Boolean);

    var al = document.getElementById('scrap-alert');
    if (!items.length) {
      board.innerHTML = emptyHTML();
      if (al) al.hidden = true;
      return;
    }
    items.sort(function (x, y) { return (x.d < 0) - (y.d < 0) || x.d - y.d; });
    var soon = items.filter(function (a) { return a.d >= 0 && a.d <= 7; });
    if (al) {
      if (soon.length) {
        al.hidden = false;
        al.textContent = '스크랩한 공고 중 ' + soon.length + '건이 이번 주에 마감됩니다.';
      } else al.hidden = true;
    }
    board.innerHTML = items.map(function (a) {
      if (tab === 'bid') return bidHTML(a);
      return window.MagampanCard ? MagampanCard.html(a) : '';
    }).join('');
  }

  document.querySelectorAll('[data-scrap-tab]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      tab = btn.dataset.scrapTab || 'grant';
      document.querySelectorAll('[data-scrap-tab]').forEach(function (b) {
        var on = b === btn;
        b.classList.toggle('is-on', on);
        b.setAttribute('aria-pressed', String(on));
      });
      renderPage();
    });
  });

  Promise.all([
    fetch('/notices.json').then(function (r) { return r.ok ? r.json() : []; }).catch(function () { return []; }),
    fetch('/bids.json').then(function (r) { return r.ok ? r.json() : []; }).catch(function () { return []; })
  ]).then(function (pair) {
    GRANT = pair[0] || [];
    BIDS = pair[1] || [];
    renderPage();
  });
})();
