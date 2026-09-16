/* 목록·스크랩 카드 마크업. notices.json 압축 키를 쓴다. */
(function (w) {
  function esc(s) {
    return String(s == null ? '' : s).replace(/[<>&"]/g, function (c) {
      return { '<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;' }[c];
    });
  }

  function cls(d, p) {
    if (d === 9999) return ['d-a', '상시', p || '상시 접수'];
    if (d < 0) return ['d-c', '마감', (-d) + '일 전 종료'];
    if (d === 0) return ['d-u', '오늘', '오늘 마감'];
    if (d <= 7) return ['d-u', 'D-' + d, ''];
    if (d <= 14) return ['d-s', 'D-' + d, ''];
    return ['d-o', 'D-' + d, ''];
  }

  function html(a) {
    var c = cls(a.d, a.p);
    var sub = c[2] || (a.e ? a.e.slice(5) + ' 마감' : '');
    var tags = '<span class="pill pill-dday ' + c[0] + '">' + esc(c[1]) + '</span>';
    if (a.c) tags += '<span class="pill">' + esc(a.c) + '</span>';
    if (a.r) tags += '<span class="pill">' + esc(a.r) + '</span>';
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
    var when = sub ? '<span class="when">' + esc(sub) + '</span>' : '';
    var starred = w.Scrap && w.Scrap.has(a.i);
    return '<a class="row" href="/notice/' + esc(a.i) + '/">' +
      '<div class="row-body">' +
      '<div class="row-tags">' + tags + '</div>' +
      '<h3>' + esc(a.t) + '</h3>' +
      (meta ? '<div class="meta">' + meta + '</div>' : '') +
      blurb +
      '<div class="row-foot">' + amt + when + '</div>' +
      '</div>' +
      '<button type="button" class="star" data-id="' + esc(a.i) +
      '" aria-pressed="' + (starred ? 'true' : 'false') +
      '" aria-label="스크랩"></button></a>';
  }

  w.MagampanCard = { esc: esc, cls: cls, html: html };
})(window);
