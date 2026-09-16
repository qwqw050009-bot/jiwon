/* 필터 URL 계약. src/urlstate.py 와 키를 맞춘다.
   지원: ?q=&region=&field=&deadline=&org=&amount=
   입찰: ?q=&kind=&deadline=&org=&amount=&region= */
(function (w) {
  function lists(sp, keys) {
    var out = [], seen = {};
    keys.forEach(function (k) {
      (sp.getAll(k) || []).forEach(function (raw) {
        String(raw || '').split(',').forEach(function (p) {
          p = p.trim();
          if (p && !seen[p]) { seen[p] = 1; out.push(p); }
        });
      });
    });
    return out;
  }
  function setList(sp, key, arr) {
    if (arr && arr.length) sp.set(key, arr.join(','));
    else sp.delete(key);
  }
  function qsOf(sp) {
    var s = sp.toString();
    return s ? ('?' + s) : '';
  }

  function parseGrant(search) {
    var sp = new URLSearchParams(String(search || '').replace(/^\?/, ''));
    return {
      q: (sp.get('q') || '').trim(),
      region: lists(sp, ['region']),
      field: lists(sp, ['field', 'category']),
      deadline: lists(sp, ['deadline', 'due']),
      org: lists(sp, ['org']),
      amount: lists(sp, ['amount']),
      district: lists(sp, ['district']),
      src: (sp.get('src') || '').trim(),
      from: sp.get('from') || '',
      to: sp.get('to') || '',
      sort: sp.get('sort') || 'dday',
      open: sp.get('open') !== '0'
    };
  }

  function serializeGrant(st, locked) {
    locked = locked || {};
    var sp = new URLSearchParams();
    if (st.q) sp.set('q', st.q);
    if (!locked.region) setList(sp, 'region', st.region);
    if (!locked.field) setList(sp, 'field', st.field);
    if (!locked.deadline) setList(sp, 'deadline', st.deadline);
    if (!locked.org) setList(sp, 'org', st.org);
    if (!locked.amount) setList(sp, 'amount', st.amount);
    if (!locked.district) setList(sp, 'district', st.district);
    if (!locked.src && st.src) sp.set('src', st.src);
    if (st.from) sp.set('from', st.from);
    if (st.to) sp.set('to', st.to);
    if (st.sort && st.sort !== 'dday') sp.set('sort', st.sort);
    if (st.open === false) sp.set('open', '0');
    return qsOf(sp);
  }

  function parseBid(search) {
    var sp = new URLSearchParams(String(search || '').replace(/^\?/, ''));
    return {
      q: (sp.get('q') || '').trim(),
      kind: lists(sp, ['kind']),
      deadline: lists(sp, ['deadline', 'due']),
      org: lists(sp, ['org']),
      amount: lists(sp, ['amount']),
      region: lists(sp, ['region']),
      sort: sp.get('sort') || 'dday',
      open: sp.get('open') !== '0'
    };
  }

  function serializeBid(st, locked) {
    locked = locked || {};
    var sp = new URLSearchParams();
    if (st.q) sp.set('q', st.q);
    if (!locked.kind) setList(sp, 'kind', st.kind);
    if (!locked.deadline) setList(sp, 'deadline', st.deadline);
    if (!locked.org) setList(sp, 'org', st.org);
    if (!locked.amount) setList(sp, 'amount', st.amount);
    if (!locked.region) setList(sp, 'region', st.region);
    if (st.sort && st.sort !== 'dday') sp.set('sort', st.sort);
    if (st.open === false) sp.set('open', '0');
    return qsOf(sp);
  }

  function describeGrant(st) {
    var bits = [];
    if (st.q) bits.push('검색 ' + st.q);
    [['region', '지역'], ['field', '분야'], ['org', '기관'],
     ['deadline', '기간'], ['amount', '금액'], ['district', '시군구']].forEach(function (p) {
      if (st[p[0]] && st[p[0]].length) bits.push(p[1] + ' ' + st[p[0]].join('·'));
    });
    if (st.src === 'kstartup') bits.push('출처 K-Startup');
    else if (st.src === 'bizinfo') bits.push('출처 기업마당');
    if (st.from || st.to) bits.push('날짜 ' + (st.from || '') + '~' + (st.to || ''));
    if (st.open === false) bits.push('마감 포함');
    return bits.join(' / ') || '전체';
  }

  function describeBid(st) {
    var bits = [];
    if (st.q) bits.push('검색 ' + st.q);
    [['kind', '종류'], ['region', '지역'], ['org', '발주기관'],
     ['deadline', '기간'], ['amount', '추정가격']].forEach(function (p) {
      if (st[p[0]] && st[p[0]].length) bits.push(p[1] + ' ' + st[p[0]].join('·'));
    });
    if (st.open === false) bits.push('마감 포함');
    return bits.join(' / ') || '입찰 전체';
  }

  w.MagampanState = {
    parseGrant: parseGrant,
    serializeGrant: serializeGrant,
    parseBid: parseBid,
    serializeBid: serializeBid,
    describeGrant: describeGrant,
    describeBid: describeBid
  };
})(window);
