/* 스크랩: 로그인 없이 브라우저에 공고 ID만 저장.
   서버·계정·DB 없음. 저장 실패(시크릿 모드 등) 시 조용히 비활성화. */
(function () {
  var KEY = 'scrap.v1';
  var HIDE = 'scrap.notice.off';

  function read() {
    try { return JSON.parse(localStorage.getItem(KEY) || '[]'); }
    catch (e) { return []; }
  }
  function write(v) {
    try { localStorage.setItem(KEY, JSON.stringify(v)); return true; }
    catch (e) { return false; }
  }
  function has(id) { return read().indexOf(id) >= 0; }
  function toggle(id) {
    var v = read(), i = v.indexOf(id);
    i >= 0 ? v.splice(i, 1) : v.unshift(id);
    write(v);
    return i < 0;
  }

  function usable() {
    try { localStorage.setItem('_t', '1'); localStorage.removeItem('_t'); return true; }
    catch (e) { return false; }
  }
  var OK = usable();

  /* 스크랩 저장 방식 안내. 처음 스크랩할 때 한 번만.
     '다음부터 보지 않기'를 누르면 다시 안 뜬다. */
  function notice() {
    if (document.getElementById('scrap-note')) return;
    var off; try { off = localStorage.getItem(HIDE); } catch (e) { off = null; }
    if (off && OK) return;

    var el = document.createElement('div');
    el.id = 'scrap-note';
    el.className = 'snote' + (OK ? '' : ' warn');
    el.setAttribute('role', 'status');
    el.innerHTML = OK
      ? '<p>스크랩은 지금 쓰는 브라우저에만 저장됩니다. 다른 기기에서는 보이지 않고, ' +
        '브라우저 기록을 지우면 함께 사라집니다.</p>' +
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

  window.Scrap = { read: read, has: has, toggle: toggle, ok: OK };

  /* 헤더 카운트 */
  function badge() {
    var el = document.getElementById('scrap-count');
    if (!el) return;
    var n = read().length;
    el.textContent = n ? n : '';
    el.hidden = !n;
  }

  /* 상세페이지 버튼 */
  var btn = document.getElementById('scrap-btn');
  if (btn) {
    var id = btn.dataset.id;
    var sync = function () {
      var on = has(id);
      btn.setAttribute('aria-pressed', String(on));
      btn.querySelector('span').textContent = on ? '스크랩함' : '스크랩';
    };
    sync();
    btn.addEventListener('click', function () {
      var on = toggle(id); sync(); badge();
      if (on) notice();
    });
  }

  /* 목록 행의 별 버튼 (위임) */
  document.addEventListener('click', function (e) {
    var s = e.target.closest('.star');
    if (!s) return;
    e.preventDefault();
    var on = toggle(s.dataset.id);
    s.setAttribute('aria-pressed', String(on));
    badge();
    if (on) notice();
    if (document.body.dataset.page === 'scrap') s.closest('.row').remove(), render();
  });

  badge();

  /* 스크랩 목록 페이지 */
  var board = document.getElementById('scrap-board');
  if (!board) return;

  function cls(d) {
    if (d < 0) return ['d-c', '마감', (-d) + '일 전 종료'];
    if (d === 0) return ['d-u', '오늘', '오늘 마감'];
    if (d <= 7) return ['d-u', 'D-' + d, ''];
    if (d <= 14) return ['d-s', 'D-' + d, ''];
    return ['d-o', 'D-' + d, ''];
  }
  function esc(s) { return String(s).replace(/[<>&"]/g, function (c) {
    return { '<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;' }[c]; }); }

  var DATA = [];
  function render() {
    var ids = read();
    var items = ids.map(function (i) {
      return DATA.find(function (a) { return a.i === i; });
    }).filter(Boolean);

    if (!items.length) {
      board.innerHTML = '<p class="note">아직 스크랩한 공고가 없습니다. ' +
        '공고 목록에서 별을 누르면 여기에 모입니다. ' +
        '<a href="/">공고 보러 가기</a></p>';
      document.getElementById('scrap-alert').hidden = true;
      return;
    }
    items.sort(function (x, y) { return (x.d < 0) - (y.d < 0) || x.d - y.d; });

    var soon = items.filter(function (a) { return a.d >= 0 && a.d <= 7; });
    var al = document.getElementById('scrap-alert');
    if (soon.length) {
      al.hidden = false;
      al.textContent = '스크랩한 공고 중 ' + soon.length + '건이 이번 주에 마감됩니다.';
    } else { al.hidden = true; }

    board.innerHTML = items.map(function (a) {
      var c = cls(a.d), sub = c[2] || (a.e.slice(5) + ' 마감');
      return '<a class="row" href="/notice/' + a.i + '/">' +
        '<div class="dday ' + c[0] + '">' + c[1] + '<small>' + sub + '</small></div>' +
        '<div><h3>' + esc(a.t) + '</h3><div class="meta"><i>' + esc(a.o) + '</i><i>' +
        esc(a.c) + '</i><i class="amt">' + esc(a.m) + '</i></div></div>' +
        '<button type="button" class="star" data-id="' + a.i + '" aria-pressed="true" ' +
        'aria-label="스크랩 해제"></button></a>';
    }).join('');
  }

  fetch('/notices.json').then(function (r) { return r.json(); })
    .then(function (d) { DATA = d; render(); })
    .catch(function () {
      board.innerHTML = '<p class="note">공고 정보를 불러오지 못했습니다. 새로고침해 주세요.</p>';
    });
})();
