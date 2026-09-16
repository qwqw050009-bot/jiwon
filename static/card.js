/* 목록·스크랩 카드 마크업. notices.json 압축 키를 쓴다. */
(function (w) {
  function esc(s) {
    return String(s == null ? '' : s).replace(/[<>&"]/g, function (c) {
      return { '<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;' }[c];
    });
  }

  function cls(d, p, st) {
    if (st === 'closed' || d < 0) return ['d-c', '마감'];
    if (d === 9999) return ['d-a', '상시'];
    if (d === 0) return ['d-u', '오늘'];
    if (d <= 7) return ['d-u', 'D-' + d];
    if (d <= 14) return ['d-s', 'D-' + d];
    return ['d-o', 'D-' + d];
  }

  function whenOf(a) {
    if (a.du) return a.du;
    if (a.pt === 'always' || a.d === 9999) return a.p || '상시 접수';
    if (!a.e) return '마감일 미상';
    if (a.tm) return a.e + ' (KST)';
    return a.e + ' · 시간 미상';
  }

  function html(a) {
    var st = a.st || (a.d < 0 ? 'closed' : 'open');
    var c = cls(a.d, a.p, st);
    var sl = a.sl || (st === 'closed' ? '마감' : st === 'upcoming' ? '예정' : '진행');
    var tags = '<span class="pill pill-dday ' + c[0] + '">' + esc(c[1]) + '</span>';
    if (sl && sl !== c[1]) tags += '<span class="pill pill-st">' + esc(sl) + '</span>';
    if (a.c) tags += '<span class="pill">' + esc(a.c) + '</span>';
    if (a.r) tags += '<span class="pill">' + esc(a.r) + '</span>';
    if (a.sn) tags += '<span class="pill pill-src">' + esc(a.sn) + '</span>';
    if (a.n) tags += '<span class="pill pill-new">신규</span>';
    (a.sg || []).forEach(function (s) {
      tags += '<span class="pill sig-' + esc(s.k) + '">' + esc(s.l) + '</span>';
    });
    var meta = '';
    if (a.o) meta += '<i>' + esc(a.o) + '</i>';
    if (a.w) meta += '<i class="who">' + esc(a.w) + '</i>';
    var blurb = a.s ? '<p class="blurb">' + esc(a.s) + '</p>' : '';
    var amt = a.m
      ? '<span class="amt">' + esc(a.m) + '</span>'
      : '<span class="amt amt-empty">규모는 원문 확인</span>';
    var when = '<span class="when">' + esc(whenOf(a)) + '</span>';
    var starred = w.Scrap && w.Scrap.has(a.i, 'grant');
    var due = whenOf(a);
    return '<article class="row" data-kind="grant" data-id="' + esc(a.i) +
      '" data-title="' + esc(a.t) + '" data-org="' + esc(a.o || '') +
      '" data-due="' + esc(due) + '" data-amt="' + esc(a.m || '') +
      '" data-src="' + esc(a.sn || '기업마당') + '">' +
      '<button type="button" class="cmp" data-id="' + esc(a.i) +
      '" data-kind="grant" aria-pressed="false" aria-label="비교에 넣기"></button>' +
      '<a class="row-body" href="/notice/' + esc(a.i) + '/">' +
      '<div class="row-tags">' + tags + '</div>' +
      '<h3>' + esc(a.t) + '</h3>' +
      (meta ? '<div class="meta">' + meta + '</div>' : '') +
      blurb +
      '<div class="row-foot">' + amt + when + '</div>' +
      '</a>' +
      '<button type="button" class="star" data-id="' + esc(a.i) +
      '" data-kind="grant" aria-pressed="' + (starred ? 'true' : 'false') +
      '" aria-label="스크랩"></button></article>';
  }

  w.MagampanCard = { esc: esc, cls: cls, html: html, whenOf: whenOf };
})(window);
