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


def related_notices(row, pool, limit=5):
    """같은 지역·분야를 우선하고, 부족하면 지역 또는 분야로 채운다. 가짜 공고는 없다."""
    row = row or {}
    rid = row.get("id")
    region = row.get("region")
    cat = row.get("category")
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

    def dkey(x):
        d = x.get("dday")
        return d if isinstance(d, int) else 9999

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
    out = []
    for group in (both, by_reg, by_cat):
        for x in sorted(group, key=dkey):
            out.append(x)
            if len(out) >= limit:
                return out
    return out


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
