# -*- coding: utf-8 -*-
"""
목록 필터용 보조 값. 실데이터에 없는 필드를 만들지 않는다.

- 지원금액 밴드: enrich.amount_of 가 본문에서 고른 표기를 숫자로 읽을
  수 있을 때만 구간을 붙인다. 퍼센트·미기재는 unk.
- 시군구: districts.belongs 와 같은 해시태그 정확 일치만.
- 소스는 공고에 source 가 있으면 그대로, 없으면 기업마당(bizinfo).
"""
import re

import deadline as dl
import districts as distmod
import enrich

AMOUNT_BANDS = [
    {"id": "lt10", "name": "1천만 원 미만", "desc": "본문 표기가 1천만 원 미만"},
    {"id": "10to50", "name": "1천만~5천만 원", "desc": "1천만 원 이상 5천만 원 미만"},
    {"id": "50to100", "name": "5천만~1억 원", "desc": "5천만 원 이상 1억 원 미만"},
    {"id": "gte100", "name": "1억 원 이상", "desc": "1억 원 이상"},
    {"id": "unk", "name": "금액 미기재", "desc": "본문에서 원 단위 표기를 못 읽음"},
]

SOURCE_LABEL = {
    "bizinfo": "기업마당",
    "kstartup": "K-Startup",
    "g2b": "나라장터",
}

_AMT = re.compile(
    r"([\d,]+(?:\.\d+)?)\s*(억|천만|백만|십만|만|천)?\s*원"
)
_UNIT = {
    "억": 100_000_000,
    "천만": 10_000_000,
    "백만": 1_000_000,
    "십만": 100_000,
    "만": 10_000,
    "천": 1_000,
}


def amount_won(text):
    """원 단위 정수. 퍼센트만 있거나 숫자가 없으면 None. 없는 값을 지어내지 않는다."""
    if not text:
        return None
    t = re.sub(r"\s+", "", str(text))
    m = _AMT.search(t)
    if not m:
        return None
    try:
        n = float(m.group(1).replace(",", ""))
    except ValueError:
        return None
    mul = _UNIT.get(m.group(2) or "", 1)
    won = int(n * mul)
    return won if won > 0 else None


def amount_band_id(row):
    """compact feed 의 b 키. amount_of 표기를 읽지 못하면 unk."""
    got = enrich.amount_of(row) if row else ""
    won = amount_won(got)
    if won is None:
        return "unk"
    if won < 10_000_000:
        return "lt10"
    if won < 50_000_000:
        return "10to50"
    if won < 100_000_000:
        return "50to100"
    return "gte100"


def source_of(row):
    src = (row.get("source") or "").strip() if row else ""
    if src == "kstartup":
        return "kstartup"
    if src in ("g2b", "nara", "bid"):
        return "g2b"
    return "bizinfo"


def source_label(row):
    return SOURCE_LABEL.get(source_of(row), "기업마당")


def notice_no(row):
    """원문 공고번호. 없으면 id. 없는 번호를 지어내지 않는다."""
    row = row or {}
    for key in ("pblanc_id", "bid_no", "notice_no"):
        v = (row.get(key) or "").strip()
        if v:
            return v
    return (row.get("id") or "").strip()


def posted_at(row):
    """게시일. created/updated/open_dt 중 있는 것만."""
    row = row or {}
    for key in ("created", "updated", "open_dt", "posted_at"):
        v = (row.get(key) or "").strip()
        if v:
            return v[:16]
    return ""


def districts_of(row):
    """해시태그 정확 일치 시군구 이름만. 정규식 추측 없음."""
    row = row or {}
    tags = row.get("tags") or []
    if not tags:
        return []
    out = []
    seen = set()
    for d in distmod.DISTRICTS:
        name = d["name_ko"]
        if name in seen:
            continue
        if distmod.belongs(row, d):
            seen.add(name)
            out.append(name)
    return out


def is_correction(row):
    """원문 제목·플래그에 정정이 있을 때만. 없는 정정을 만들지 않는다."""
    row = row or {}
    if row.get("is_correction"):
        return True
    title = row.get("title") or ""
    return "정정" in title


def title_tokens(title):
    """제목 유사도용 토큰. 연도·공고 껍질은 빼고 실단어만."""
    raw = (title or "").replace("\xa0", " ")
    parts = re.split(r"[\[\]()（）【】『』「」·,./\s~\-–—]+", raw)
    stop = {
        "년", "공고", "지원", "사업", "모집", "안내", "및", "등", "위한", "관련",
        "재공고", "추가", "연장", "차", "건",
    }
    out = []
    seen = set()
    for p in parts:
        p = p.strip()
        if len(p) < 2 or p in stop:
            continue
        if re.fullmatch(r"20\d{2}", p):
            continue
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def compact(row):
    """notices.json 한 줄. 키를 짧게 유지한다."""
    st = row.get("status") or dl.status_of(row)
    rec = {
        "i": row.get("id") or "",
        "t": row.get("title") or "",
        "c": row.get("category") or "",
        "r": row.get("region") or "",
        "o": row.get("org") or "",
        "m": row.get("amount_card") or "",
        "e": row.get("apply_end") or "",
        "d": row.get("dday", 0),
        "n": 1 if row.get("is_new") else 0,
        "p": row.get("period_raw") or "",
        "src": source_of(row),
        "sn": source_label(row),
        "b": amount_band_id(row),
        "pt": row.get("period_type") or "dated",
        "st": st,
        "sl": row.get("status_label") or dl.status_label(st),
        "du": row.get("deadline_line") or dl.deadline_line(row),
        "tm": 1 if dl.time_known(row.get("apply_end") or "") else 0,
        "no": notice_no(row),
    }
    if is_correction(row):
        rec["corr"] = 1
    pd = posted_at(row)
    if pd:
        rec["pd"] = pd
    col = (row.get("collected_at") or "").strip()
    if col:
        rec["col"] = col
    if row.get("blurb"):
        rec["s"] = row["blurb"]
    who = row.get("target_short") or ""
    if who:
        rec["w"] = who
    dist = districts_of(row)
    if dist:
        rec["g"] = dist
    sig = row.get("signals") or []
    if sig:
        rec["sg"] = [{"k": x.get("cls") or "", "l": x.get("label") or ""} for x in sig]
    return rec


def bid_amount_band_id(row):
    """입찰 추정가격 밴드. 원문 숫자가 있을 때만. 없으면 unk."""
    raw = row.get("budget_raw") if row else None
    won = None
    if isinstance(raw, int) and raw > 0:
        won = raw
    elif raw not in (None, ""):
        try:
            won = int(raw)
        except (TypeError, ValueError):
            won = None
    if won is None:
        won = amount_won(row.get("budget_card") or row.get("budget") or "")
    if won is None or won <= 0:
        return "unk"
    if won < 10_000_000:
        return "lt10"
    if won < 50_000_000:
        return "10to50"
    if won < 100_000_000:
        return "50to100"
    return "gte100"


def compact_bid(row):
    """bids.json 한 줄. notices.json 과 섞지 않는다."""
    st = row.get("status") or dl.status_of(row)
    rec = {
        "i": row.get("id") or "",
        "t": row.get("title") or "",
        "k": row.get("kind") or "",
        "ks": row.get("kind_slug") or "",
        "o": row.get("org") or "",
        "m": row.get("budget_card") or row.get("budget") or "",
        "e": row.get("close_dt") or "",
        "d": row.get("dday", 0),
        "r": row.get("region") or "",
        "src": "g2b",
        "sn": "나라장터",
        "st": st,
        "sl": row.get("status_label") or dl.status_label(st),
        "du": row.get("deadline_line") or dl.deadline_line(row),
        "tm": 1 if dl.time_known(row.get("close_dt") or "") else 0,
        "no": notice_no(row),
        "b": bid_amount_band_id(row),
        "u": row.get("detail_url") or "",
    }
    if row.get("ntce_org"):
        rec["nt"] = row["ntce_org"]
    pd = posted_at(row)
    if pd:
        rec["pd"] = pd
    col = (row.get("collected_at") or "").strip()
    if col:
        rec["col"] = col
    if row.get("is_new"):
        rec["n"] = 1
    if is_correction(row):
        rec["corr"] = 1
    return rec


def source_tally(items):
    items = items or []
    biz = sum(1 for a in items if source_of(a) != "kstartup")
    ks = sum(1 for a in items if source_of(a) == "kstartup")

    def dday(a):
        d = a.get("dday")
        return d if isinstance(d, int) else None

    return {
        "bizinfo": biz,
        "kstartup": ks,
        "today": sum(1 for a in items if dday(a) == 0),
        "week": sum(1 for a in items if (d := dday(a)) is not None and 0 <= d <= 7),
        "always": sum(1 for a in items if a.get("period_type") == "always"
                      or dday(a) == 9999),
        "open": sum(1 for a in items if (d := dday(a)) is not None and d >= 0),
        "new": sum(1 for a in items if a.get("is_new")),
    }


def _open_others(row, pool):
    rid = (row or {}).get("id")
    others = []
    for x in pool or []:
        if x.get("id") == rid:
            continue
        if x.get("is_open") is False:
            continue
        d = x.get("dday")
        if isinstance(d, int) and d < 0:
            continue
        others.append(x)
    return others


def _dday_key(x):
    d = x.get("dday")
    return d if isinstance(d, int) else 9999


def _title_rank(row, others):
    tokens = set(title_tokens((row or {}).get("title") or ""))
    if not tokens:
        return []
    scored = []
    for x in others:
        shared = tokens.intersection(title_tokens(x.get("title") or ""))
        if shared:
            scored.append((-len(shared), _dday_key(x), x))
    scored.sort(key=lambda t: (t[0], t[1]))
    return [t[2] for t in scored]


def _fill_related(groups, others, limit):
    """그룹 우선순위로 3~limit건. 가짜 공고는 넣지 않는다."""
    limit = max(0, min(int(limit or 0), 6) or 6)
    out, seen = [], set()

    def take(seq):
        for x in seq:
            xid = x.get("id")
            if not xid or xid in seen:
                continue
            seen.add(xid)
            out.append(x)
            if len(out) >= limit:
                return True
        return False

    for group in groups:
        if take(group):
            return out
    if len(out) < min(3, limit):
        take(sorted(others, key=_dday_key))
    return out


def related_notices(row, pool, limit=6):
    """같은 지역·분야, 이어서 지역/분야, 제목 토큰 겹침. 3~6건. 가짜 공고는 없다."""
    others = _open_others(row, pool)
    region = (row or {}).get("region")
    cat = (row or {}).get("category")
    both, by_reg, by_cat = [], [], []
    for x in others:
        same_r = region and x.get("region") == region
        same_c = cat and x.get("category") == cat
        if same_r and same_c:
            both.append(x)
        elif same_r:
            by_reg.append(x)
        elif same_c:
            by_cat.append(x)
    by_title = _title_rank(row, others)
    return _fill_related(
        [sorted(both, key=_dday_key), sorted(by_reg, key=_dday_key),
         sorted(by_cat, key=_dday_key), by_title],
        others, limit,
    )


def related_bids(row, pool, limit=6):
    """같은 종류·참가지역을 우선하고, 부족하면 제목 유사·마감순으로 채운다."""
    others = _open_others(row, pool)
    kind = (row or {}).get("kind")
    region = (row or {}).get("region")
    both, by_kind, by_reg = [], [], []
    for x in others:
        same_k = kind and x.get("kind") == kind
        same_r = region and x.get("region") == region
        if same_k and same_r:
            both.append(x)
        elif same_k:
            by_kind.append(x)
        elif same_r:
            by_reg.append(x)
    by_title = _title_rank(row, others)
    return _fill_related(
        [sorted(both, key=_dday_key), sorted(by_kind, key=_dday_key),
         sorted(by_reg, key=_dday_key), by_title],
        others, limit,
    )


def urgent_rail(items, limit=8):
    out = []
    for a in items or []:
        d = a.get("dday")
        if d is None:
            continue
        if 0 <= d <= 7:
            out.append(a)
        if len(out) >= limit:
            break
    return out


def today_rail(items, limit=8):
    """오늘 마감(D-0)만. 상시·마감된 공고는 넣지 않는다."""
    out = []
    for a in items or []:
        if a.get("dday") == 0:
            out.append(a)
        if len(out) >= limit:
            break
    return out
