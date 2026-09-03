/* 지역·분야 다중 선택 + 검색 + 정렬 + 더보기.
   정적 페이지는 그대로 두고(SEO) 그 위에서 클라이언트 필터링만 한다. */
(function () {
  var root = document.querySelector('.filter');
  var board = document.getElementById('board');
  if (!root || !board) return;

  var SLUG = window.__SLUG__ || { region: {}, category: {} };
  var picked = { region: new Set(), category: new Set() };
  var PAGE = parseInt(board.dataset.limit, 10) || 20;
  var MORE = board.dataset.more || '';   // 메인처럼 별도 목록 페이지가 있으면 그 주소
  var openOnly = true, sortBy = 'dday', q = '', shown = PAGE, all = [], view = [];
  var touched = false;                   // 사용자가 필터를 건드렸는지

  var seedR = root.dataset.region, seedC = root.dataset.category;
  if (seedR) picked.region.add(seedR);
  if (seedC) picked.category.add(seedC);

  function cls(d, a) {
    if (d === 9999) return ['d-a', '상시', a || '상시 접수'];
    if (d < 0) return ['d-c', '마감', (-d) + '일 전 종료'];
    if (d === 0) return ['d-u', '오늘', '오늘 마감'];
    if (d <= 7) return ['d-u', 'D-' + d, ''];
    if (d <= 14) return ['d-s', 'D-' + d, ''];
    return ['d-o', 'D-' + d, ''];
  }

  function esc(s) { return String(s).replace(/[<>&"]/g, function (c) {
    return { '<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;' }[c]; }); }

  function rowHTML(a) {
    var c = cls(a.d, a.p), sub = c[2] || (a.e ? a.e.slice(5) + ' 마감' : '');
    return '<a class="row" href="/notice/' + a.i + '/">' +
      '<div class="dday ' + c[0] + '">' + c[1] + '<small>' + sub + '</small></div>' +
      '<div><h3>' + esc(a.t) + (a.n ? '<span class="tag-new">신규</span>' : '') + '</h3><div class="meta"><i>' + esc(a.o) + '</i><i>' +
      esc(a.c) + '</i><i class="amt">' + esc(a.m) + '</i></div></div>' +
      '<button type="button" class="star" data-id="' + a.i + '" aria-pressed="' +
      (window.Scrap && Scrap.has(a.i)) + '" aria-label="스크랩"></button></a>';
  }

  function summary() {
    var r = [...picked.region], c = [...picked.category], p = [];
    if (r.length) p.push(r.length > 2 ? '지역 ' + r.length + '곳' : r.join('·'));
    if (c.length) p.push(c.length > 2 ? '분야 ' + c.length + '개' : c.join('·'));
    document.getElementById('f-summary').textContent = p.length ? p.join(' / ') : '지역·분야 선택';
    root.classList.toggle('has-pick', !!p.length);
  }

  function syncURL() {
    var r = [...picked.region], c = [...picked.category], p = null;
    if (r.length === 1 && c.length === 1) p = '/region/' + SLUG.region[r[0]] + '/' + SLUG.category[c[0]] + '/';
    else if (r.length === 1 && !c.length) p = '/region/' + SLUG.region[r[0]] + '/';
    else if (!r.length && c.length === 1) p = '/category/' + SLUG.category[c[0]] + '/';
    if (p && location.pathname !== p) history.replaceState(null, '', p);
  }

  function compute() {
    view = all.filter(function (a) {
      if (openOnly && a.d < 0) return false;
      if (picked.region.size && !picked.region.has(a.r)) return false;
      if (picked.category.size && !picked.category.has(a.c)) return false;
      if (q && (a.t + a.o).toLowerCase().indexOf(q) < 0) return false;
      return true;
    });
    if (sortBy === 'new') view.sort(function (x, y) { return y.e < x.e ? -1 : 1; });
    else view.sort(function (x, y) { return (x.d < 0) - (y.d < 0) || x.d - y.d; });
  }

  function render(reset) {
    if (!touched) { summary(); return; }   // 요약판 유지
    if (reset) shown = PAGE;
    compute();
    if (!view.length) {
      board.innerHTML = '<p class="note">조건에 맞는 공고가 없습니다. 선택을 줄이거나 마감된 공고까지 함께 보세요.</p>';
    } else {
      var html = view.slice(0, shown).map(rowHTML).join('');
      if (view.length > shown) {
        html += '<button type="button" class="more" id="f-more">' +
          Math.min(PAGE * 2, view.length - shown) + '건 더 보기</button>';
      } else if (MORE && !picked.region.size && !picked.category.size && !q) {
        html += '<a class="more" href="' + MORE + '">전체 공고 보기</a>';
      }
      board.innerHTML = html;
    }
    var soon = view.filter(function (a) { return a.d >= 0 && a.d <= 7; }).length;
    document.getElementById('f-count').textContent =
      view.length + '건' + (soon ? ' · 이번 주 마감 ' + soon + '건' : '');
    summary(); syncURL();
  }

  function paint() {
    ['region', 'category'].forEach(function (k) {
      document.querySelectorAll('#f-' + k + ' button').forEach(function (b) {
        b.setAttribute('aria-pressed', picked[k].has(b.dataset.v) ? 'true' : 'false');
      });
    });
  }

  document.getElementById('f-toggle').addEventListener('click', function () {
    var body = document.getElementById('f-body'), open = !body.hidden;
    body.hidden = open;
    this.setAttribute('aria-expanded', String(!open));
    root.classList.toggle('open', !open);
  });

  root.addEventListener('click', function (e) {
    var b = e.target.closest('#f-region button, #f-category button');
    if (b) {
      var k = b.parentNode.id.slice(2), v = b.dataset.v;
      picked[k].has(v) ? picked[k].delete(v) : picked[k].add(v);
      touched = true; paint(); render(true); return;
    }
    if (e.target.id === 'f-reset') {
      picked.region.clear(); picked.category.clear();
      touched = true; paint(); render(true);
    }
  });

  board.addEventListener('click', function (e) {
    if (e.target.id === 'f-more') { shown += PAGE * 2; render(); }
    if (e.target.id === 'f-more-static') { touched = true; shown = PAGE * 3; render(); }
  });

  root.addEventListener('change', function (e) {
    if (e.target.id === 'f-openonly') { openOnly = e.target.checked; touched = true; render(true); }
    if (e.target.id === 'f-sort') { sortBy = e.target.value; touched = true; render(true); }
  });

  var t;
  root.addEventListener('input', function (e) {
    if (e.target.id !== 'f-q') return;
    clearTimeout(t);
    var v = e.target.value.trim().toLowerCase();
    t = setTimeout(function () { q = v; touched = true; render(true); }, 180);
  });

  fetch('/notices.json')
    .then(function (r) { return r.json(); })
    .then(function (d) {
      all = d; root.classList.add('ready'); paint();
      compute();
      var soon = view.filter(function (a) { return a.d >= 0 && a.d <= 7; }).length;
      document.getElementById('f-count').textContent =
        view.length + '건' + (soon ? ' · 이번 주 마감 ' + soon + '건' : '');
      summary();
    })
    .catch(function () { root.style.display = 'none'; });
})();
