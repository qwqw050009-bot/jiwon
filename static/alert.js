/* 알림 관심 신청: 서버·결제·카카오 없음.
   이메일은 mailto 로 열고, 조건은 이 브라우저 localStorage 에만 둔다. */
(function () {
  var KEY = 'alert.conditions.v1';
  var form = document.getElementById('alert-form');
  var kw = document.getElementById('alert-keyword');
  var mail = document.getElementById('alert-email');
  var plan = document.getElementById('alert-plan');
  var status = document.getElementById('alert-status');
  var saveBtn = document.getElementById('alert-save');
  var emailTo = (form && form.getAttribute('action') || '').replace(/^mailto:/i, '');

  function read() {
    try { return JSON.parse(localStorage.getItem(KEY) || '[]'); }
    catch (e) { return []; }
  }
  function write(v) {
    try { localStorage.setItem(KEY, JSON.stringify(v)); return true; }
    catch (e) { return false; }
  }
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
      if (form) {
        form.scrollIntoView({ block: 'center', behavior: 'smooth' });
        if (kw) kw.focus();
      }
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
      var cur = read();
      if (cur.indexOf(k) >= 0) {
        say('이미 이 브라우저에 저장된 조건입니다. 이메일을 적으면 알림 신청 메일이 열립니다.');
        return;
      }
      cur.unshift(k);
      if (!write(cur)) {
        say('이 브라우저에는 조건을 저장할 수 없습니다. 이메일 신청은 가능합니다.');
        return;
      }
      say('이 브라우저에 조건을 저장했습니다. 무료는 1개, 베이직은 최대 3개, 프로는 무제한입니다. 이메일을 적으면 알림 신청 메일이 열립니다.');
    });
  }

  if (form) {
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
      var saved = keyword() ? '저장한 조건: ' + read().join(', ') : '';
      window.location.href = mailtoHref(saved);
      say('메일 앱이 열리면 그대로 보내 주세요. 앱이 없으면 ' + emailTo + ' 으로 같은 내용을 보내 주시면 됩니다.');
    });
  }
})();
