/* 입찰 목록: 이 페이지에 서버가 그려 둔 행만 검색·더보기 한다.
   notices.json(지원) 을 읽지 않아 두 피드가 섞이지 않는다.
   헤더 검색으로 /bid/?q= 에 오면 bids.json 으로 입찰 전체만 찾는다. */
(function () {
  var board = document.getElementById('bid-board');
  var input = document.getElementById('bid-q');
  if (!board || !input) return;

  var PAGE = parseInt(board.dataset.pageSize, 10) || 20;
  var shown = PAGE;
  var rows = [].slice.call(board.querySelectorAll('a.row'));
  var hub = location.pathname === '/bid/' || location.pathname === '/bid';
  var seedQ = (new URLSearchParams(location.search).get('q') || '').trim();
  if (seedQ) input.value = seedQ;

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

  function rowHTML(a) {
    var c = cls(a.d, a.e);
    var meta = '<i>' + esc(a.o) + '</i><i>' + esc(a.k) + '</i>';
    if (a.r) meta += '<i>' + esc(a.r) + '</i>';
    if (a.m) meta += '<i class="amt">' + esc(a.m) + '</i>';
    return '<a class="row" href="/bid/notice/' + esc(a.i) + '/">' +
      '<div class="dday ' + c[0] + '">' + c[1] + '<small>' + esc(c[2]) + '</small></div>' +
      '<div><h3>' + esc(a.t) + '</h3><div class="meta">' + meta + '</div></div></a>';
  }

  function hideMore() {
    var b = document.getElementById('bid-more');
    if (b) b.remove();
  }

  function paintDom(q) {
    var n = 0, hit = 0;
    hideMore();
    rows.forEach(function (el) {
      var text = (el.textContent || '').toLowerCase();
      var ok = !q || text.indexOf(q) >= 0;
      if (!ok) { el.hidden = true; return; }
      hit += 1;
      el.hidden = hit > shown;
      if (!el.hidden) n += 1;
    });
    var empty = board.querySelector(':scope > p.note');
    if (empty) empty.hidden = hit > 0;
    if (hit > shown) {
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'more';
      btn.id = 'bid-more';
      btn.textContent = (hit - shown) + '건 더 보기';
      board.appendChild(btn);
    } else if (q && hit === 0) {
      if (!empty) {
        empty = document.createElement('p');
        empty.className = 'note';
        empty.id = 'bid-empty';
        board.appendChild(empty);
      }
      empty.hidden = false;
      empty.textContent = '조건에 맞는 입찰공고가 없습니다. 검색어를 줄여 보세요.';
    }
  }

  function paintFeed(list, q) {
    var view = list.filter(function (a) {
      return !q || (a.t + ' ' + a.o).toLowerCase().indexOf(q) >= 0;
    });
    view.sort(function (x, y) { return (x.d < 0) - (y.d < 0) || x.d - y.d; });
    if (!view.length) {
      board.innerHTML = '<p class="note">조건에 맞는 입찰공고가 없습니다. 검색어를 줄여 보세요.</p>';
      return;
    }
    var html = '';
    view.slice(0, shown).forEach(function (a) { html += rowHTML(a); });
    if (view.length > shown) {
      html += '<button type="button" class="more" id="bid-more">' +
        (view.length - shown) + '건 더 보기</button>';
    }
    board.innerHTML = html;
  }

  var feed = null;

  function apply() {
    var q = (input.value || '').trim().toLowerCase();
    if (hub && q && feed) paintFeed(feed, q);
    else paintDom(q);
  }

  board.addEventListener('click', function (e) {
    if (e.target.id !== 'bid-more') return;
    shown += PAGE;
    apply();
  });

  var timer;
  input.addEventListener('input', function () {
    clearTimeout(timer);
    timer = setTimeout(function () {
      shown = PAGE;
      var v = (input.value || '').trim();
      var u = new URL(location.href);
      if (v) u.searchParams.set('q', v);
      else u.searchParams.delete('q');
      history.replaceState(null, '', u.pathname + u.search);
      apply();
    }, 180);
  });

  if (!hub) {
    shown = PAGE;
    paintDom('');
    if (seedQ) apply();
    return;
  }

  fetch('/bids.json')
    .then(function (r) { return r.json(); })
    .then(function (d) {
      feed = d;
      if (seedQ) apply();
    })
    .catch(function () {
      if (seedQ) paintDom(seedQ.toLowerCase());
    });
})();
