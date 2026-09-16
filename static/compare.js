/* 비교 모드: 카드 최대 3건을 마감·기관·금액·출처로 나란히 본다. 로그인·결제 없음. */
(function () {
  var MAX = 3;
  var picked = [];
  var kind = '';

  function esc(s) {
    return String(s == null ? '' : s).replace(/[<>&"]/g, function (c) {
      return { '<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;' }[c];
    });
  }

  function pinFind() {
    var top = document.querySelector('.top');
    if (!top) return;
    var h = Math.round(top.getBoundingClientRect().height);
    if (h > 0) document.documentElement.style.setProperty('--top-h', h + 'px');
  }

  function rowOf(el) {
    return el && el.closest ? el.closest('.row') : null;
  }

  function recOf(row) {
    if (!row) return null;
    var btn = row.querySelector('.cmp');
    return {
      id: row.getAttribute('data-id') || '',
      kind: (btn && btn.dataset.kind) || row.getAttribute('data-cmp') || 'grant',
      title: row.getAttribute('data-title') || (row.querySelector('h3') || {}).textContent || '',
      org: row.getAttribute('data-org') || '',
      due: row.getAttribute('data-due') || '',
      amt: row.getAttribute('data-amt') || '',
      src: row.getAttribute('data-src') || '',
      href: ((row.querySelector('.row-body') || {}).getAttribute('href')) || ''
    };
  }

  function has(id, k) {
    return picked.some(function (p) { return p.id === id && p.kind === k; });
  }

  function paintButtons() {
    document.querySelectorAll('.cmp[data-id]').forEach(function (btn) {
      var on = has(btn.dataset.id, btn.dataset.kind || 'grant');
      btn.setAttribute('aria-pressed', String(on));
    });
  }

  function paintBar() {
    var bar = document.getElementById('cmp-bar');
    var go = document.getElementById('cmp-go');
    var lab = document.getElementById('cmp-bar-label');
    if (!bar) return;
    if (!picked.length) {
      bar.hidden = true;
      document.body.classList.remove('has-cmp');
      return;
    }
    bar.hidden = false;
    document.body.classList.add('has-cmp');
    lab.textContent = picked.length + '건 선택 · 최대 ' + MAX + '건';
    go.disabled = picked.length < 2;
  }

  function toggle(rec) {
    if (!rec || !rec.id) return;
    if (kind && rec.kind !== kind) {
      picked = [];
    }
    kind = rec.kind;
    var i = -1;
    picked.forEach(function (p, idx) {
      if (p.id === rec.id && p.kind === rec.kind) i = idx;
    });
    if (i >= 0) picked.splice(i, 1);
    else {
      if (picked.length >= MAX) return;
      picked.push(rec);
    }
    if (!picked.length) kind = '';
    paintButtons();
    paintBar();
  }

  function table() {
    var cells = function (key, label) {
      return '<tr><th>' + esc(label) + '</th>' + picked.map(function (p) {
        var v = p[key] || '원문 확인';
        return '<td>' + esc(v) + '</td>';
      }).join('') + '</tr>';
    };
    var heads = '<tr><th></th>' + picked.map(function (p) {
      var href = p.href || (p.kind === 'bid' ? '/bid/notice/' + p.id + '/' : '/notice/' + p.id + '/');
      return '<th><a href="' + esc(href) + '">' + esc(p.title || '공고') + '</a></th>';
    }).join('') + '</tr>';
    return '<table class="cmp-table"><thead>' + heads + '</thead><tbody>' +
      cells('due', '마감') +
      cells('org', '기관') +
      cells('amt', '금액') +
      cells('src', '출처') +
      '</tbody></table>';
  }

  function openSheet() {
    var ov = document.getElementById('cmp-overlay');
    var body = document.getElementById('cmp-body');
    if (!ov || !body || picked.length < 2) return;
    body.innerHTML = table();
    ov.hidden = false;
    document.body.classList.add('f-lock');
  }
  function closeSheet() {
    var ov = document.getElementById('cmp-overlay');
    if (ov) ov.hidden = true;
    document.body.classList.remove('f-lock');
  }

  document.addEventListener('click', function (e) {
    var cmp = e.target.closest('.cmp');
    if (cmp && cmp.dataset.id) {
      e.preventDefault();
      toggle(recOf(rowOf(cmp)) || {
        id: cmp.dataset.id,
        kind: cmp.dataset.kind || 'grant'
      });
      return;
    }
    if (e.target.id === 'cmp-go') { openSheet(); return; }
    if (e.target.id === 'cmp-clear') {
      picked = [];
      kind = '';
      paintButtons();
      paintBar();
      return;
    }
    if (e.target.id === 'cmp-x' || e.target.id === 'cmp-overlay') closeSheet();
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') closeSheet();
  });

  paintButtons();
  paintBar();
  pinFind();
  window.addEventListener('resize', pinFind);
})();
