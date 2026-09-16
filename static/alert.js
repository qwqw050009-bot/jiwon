/* 알림 조건: 서버·결제·카카오 없음.
   이메일은 mailto, 조건·일시정지·삭제는 이 브라우저 localStorage 만. */
(function (w) {
  var KEY = 'magampan.alerts.v1';
  var LEGACY = 'alert.conditions.v1';
  var FREQ = {
    now: '메일로 바로 받기',
    daily: '하루 1회 메일',
    weekly: '주 1회 메일'
  };

  function esc(s) {
    if (w.MagampanCard) return MagampanCard.esc(s);
    return String(s == null ? '' : s).replace(/[<>&"]/g, function (c) {
      return { '<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;' }[c];
    });
  }
  function uid() {
    return Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
  }
  function read() {
    try {
      var cur = JSON.parse(localStorage.getItem(KEY) || '[]');
      if (cur && cur.length) return cur;
      var old = JSON.parse(localStorage.getItem(LEGACY) || '[]');
      return (old || []).map(function (k) {
        return { id: uid(), name: k, section: 'grant', q: k, freq: 'daily', paused: false };
      });
    } catch (e) { return []; }
  }
  function write(v) {
    try { localStorage.setItem(KEY, JSON.stringify(v)); return true; }
    catch (e) { return false; }
  }
  function save(rec) {
    rec = rec || {};
    rec.id = rec.id || uid();
    rec.created = rec.created || new Date().toISOString();
    rec.freq = rec.freq || 'daily';
    rec.paused = !!rec.paused;
    var list = read().filter(function (x) { return x.id !== rec.id && x.name !== rec.name; });
    list.unshift(rec);
    write(list.slice(0, 12));
    return rec;
  }
  function pause(id, on) {
    write(read().map(function (x) {
      if (x.id === id) x.paused = on !== false;
      return x;
    }));
  }
  function resume(id) { pause(id, false); }
  function remove(id) {
    write(read().filter(function (x) { return x.id !== id; }));
  }
  function dlabel(a) {
    var d = Number(a && a.d);
    var st = (a && a.st) || '';
    if (st === 'closed' || d < 0) return '마감';
    if (d === 9999 || (a && a.pt === 'always')) return '상시';
    if (d === 0) return '오늘';
    if (d > 0) return 'D-' + d;
    return '접수중';
  }
  function hrefOf(a, section) {
    if (section === 'bid') return '/bid/notice/' + encodeURIComponent(a.i) + '/';
    return '/notice/' + encodeURIComponent(a.i) + '/';
  }
  function previewHTML(hits, opts) {
    opts = opts || {};
    var n = (hits || []).length;
    var samples = (hits || []).slice(0, 5);
    var freq = opts.freq || 'daily';
    var html = '<div class="alert-preview" id="alert-preview">';
    if (n) {
      html += '<p>지금 목록에서 <b>' + n + '건</b>이 이 조건에 맞습니다.</p><ul>';
      samples.forEach(function (a) {
        html += '<li><span class="pill pill-dday">' + esc(dlabel(a)) + '</span> ' +
          '<a href="' + esc(hrefOf(a, opts.section)) + '">' + esc(a.t || '공고') + '</a></li>';
      });
      html += '</ul>';
    } else {
      html += '<p>지금은 맞는 공고가 없습니다. 저장하면 나중에 올라오는 공고를 메일로 받아볼 수 있습니다.</p>';
    }
    html += '<fieldset class="alert-freq"><legend>알림 빈도</legend>';
    ['now', 'daily', 'weekly'].forEach(function (k) {
      html += '<label><input type="radio" name="alert-freq" value="' + k + '"' +
        (k === freq ? ' checked' : '') + '> ' + FREQ[k] + '</label>';
    });
    html += '</fieldset>';
    html += '<p class="f-help">빈도는 이 브라우저에만 기록합니다. 서버 푸시·결제는 없습니다. ' +
      '메일 앱이 열리면 그대로 보내 주세요.</p>';
    html += '<p class="f-help"><a href="/alerts/">저장한 알림 조건 보기</a> · ' +
      '<a href="/scrap/">스크랩</a></p></div>';
    return html;
  }
  function freqOf(root) {
    var el = (root || document).querySelector('input[name="alert-freq"]:checked');
    return (el && el.value) || 'daily';
  }

  w.MagampanAlerts = {
    KEY: KEY, FREQ: FREQ, read: read, write: write, save: save,
    pause: pause, resume: resume, remove: remove,
    previewHTML: previewHTML, freqOf: freqOf, dlabel: dlabel
  };

  var form = document.getElementById('alert-form');
  var kw = document.getElementById('alert-keyword');
  var mail = document.getElementById('alert-email');
  var plan = document.getElementById('alert-plan');
  var status = document.getElementById('alert-status');
  var saveBtn = document.getElementById('alert-save');
  var emailTo = (form && form.getAttribute('action') || '').replace(/^mailto:/i, '');

  function say(msg) {
    if (!status) return;
    status.textContent = msg || '';
  }
  function keyword() {
    return ((kw && kw.value) || '').replace(/\s+/g, ' ').trim();
  }
  function setKeyword(v) {
    if (!kw) return;
    kw.value = v;
    kw.dispatchEvent(new Event('input', { bubbles: true }));
  }
  function seedFromUrl() {
    var q = new URLSearchParams(location.search);
    var k = (q.get('q') || q.get('keyword') || '').trim();
    var p = (q.get('plan') || '').trim().toLowerCase();
    if (k && kw && !kw.value) setKeyword(k);
    if (p && plan) plan.value = p;
  }
  function mailtoHref(extra) {
    var k = keyword();
    var e = ((mail && mail.value) || '').trim();
    var p = (plan && plan.value) || '';
    var sub = encodeURIComponent('[마감판] 알림 신청' + (p ? ' · ' + p : ''));
    var body = encodeURIComponent(
      '알림 신청합니다.\n\n' +
      '이메일: ' + e + '\n' +
      '업종/키워드: ' + (k || '(없음)') + '\n' +
      '희망 플랜: ' + (p || 'free') + '\n' +
      (extra ? extra + '\n' : '') +
      '\n— 지원사업 마감판 알림 신청 양식'
    );
    return 'mailto:' + emailTo + '?subject=' + sub + '&body=' + body;
  }

  if (form) {
    seedFromUrl();
    document.querySelectorAll('[data-alert-keyword]').forEach(function (el) {
      el.addEventListener('click', function () {
        var v = el.getAttribute('data-alert-keyword') || '';
        setKeyword(v);
        var bidQ = document.getElementById('bid-q');
        if (bidQ) {
          bidQ.value = v;
          bidQ.dispatchEvent(new Event('input', { bubbles: true }));
        }
        form.scrollIntoView({ block: 'center', behavior: 'smooth' });
        if (kw) kw.focus();
        say(v + ' 키워드를 넣었습니다. 이메일을 적고 알림을 신청하세요.');
      });
    });
    if (saveBtn) {
      saveBtn.addEventListener('click', function () {
        var k = keyword();
        if (!k) {
          say('저장할 업종이나 키워드를 먼저 적어 주세요.');
          if (kw) kw.focus();
          return;
        }
        save({ name: k, section: 'grant', q: k, freq: 'daily' });
        say('이 브라우저에 조건을 저장했습니다. 알림 빈도와 해지는 알림 조건 페이지에서 바꿀 수 있습니다.');
      });
    }
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      if (!emailTo) {
        say('문의 메일이 아직 없습니다. 사이트 문의 페이지를 이용해 주세요.');
        return;
      }
      if (!mail.checkValidity()) {
        mail.reportValidity();
        return;
      }
      var k = keyword();
      if (k) save({ name: k, section: 'grant', q: k, freq: 'now' });
      var saved = read().map(function (x) { return x.name; }).filter(Boolean);
      window.location.href = mailtoHref(saved.length ? '저장한 조건: ' + saved.join(', ') : '');
      say('메일 앱이 열리면 그대로 보내 주세요. 앱이 없으면 ' + emailTo + ' 으로 같은 내용을 보내 주시면 됩니다.');
    });
  }

  var board = document.getElementById('alerts-board');
  if (!board) return;

  function emptyHTML() {
    return '<div class="empty-filter" role="status">' +
      '<p>저장한 알림 조건이 없습니다. 목록에서 필터를 고른 뒤 「이 조건 알림」을 누르면 여기에 모입니다. 결제는 없습니다.</p>' +
      '<ul class="empty-actions">' +
      '<li><a class="cta empty-cta" href="/">지원사업 보기</a></li>' +
      '<li><a class="hero-secondary" href="/bid/">입찰 보기</a></li>' +
      '<li><a class="hero-secondary" href="/scrap/">스크랩</a></li>' +
      '</ul></div>';
  }
  function render() {
    var list = read();
    if (!list.length) {
      if (board.getAttribute('data-compact')) {
        board.innerHTML = '<p class="note">저장한 알림 조건이 없습니다. 목록에서 「이 조건 알림」을 누르면 생깁니다.</p>';
        return;
      }
      board.innerHTML = emptyHTML();
      return;
    }
    board.innerHTML = list.map(function (x) {
      var freq = FREQ[x.freq] || FREQ.daily;
      var paused = x.paused ? '일시정지' : '받는 중';
      return '<article class="alert-card' + (x.paused ? ' is-paused' : '') + '" data-id="' + esc(x.id) + '">' +
        '<h2>' + esc(x.name || '지금 조건') + '</h2>' +
        '<p>' + esc(x.section === 'bid' ? '입찰' : '지원사업') + ' · ' + esc(freq) +
        ' · ' + paused + '</p>' +
        (x.href ? '<p><a href="' + esc(x.href) + '">이 조건 목록</a></p>' : '') +
        '<div class="alert-card-act">' +
        (x.paused
          ? '<button type="button" class="f-apply" data-act="resume">다시 받기</button>'
          : '<button type="button" class="hero-secondary" data-act="pause">일시정지</button>') +
        '<button type="button" class="f-text" data-act="del">삭제</button>' +
        '</div></article>';
    }).join('');
  }
  board.addEventListener('click', function (e) {
    var btn = e.target.closest('[data-act]');
    if (!btn) return;
    var card = btn.closest('[data-id]');
    if (!card) return;
    var id = card.getAttribute('data-id');
    if (btn.dataset.act === 'pause') pause(id, true);
    if (btn.dataset.act === 'resume') resume(id);
    if (btn.dataset.act === 'del') remove(id);
    render();
  });
  render();
})(window);
