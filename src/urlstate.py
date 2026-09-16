# -*- coding: utf-8 -*-
"""
목록 필터 URL 계약.

지원: ?q=&region=&field=&deadline=&org=&amount=
입찰: ?q=&kind=&deadline=&org=&amount=&region=

다중값은 쉼표 구분 한 키. 새로고침·공유·뒤로가기가 같은 목록을 복원한다.
페이지 경로가 이미 잠근 값(지역 페이지의 region 등)은 쿼리에 넣지 않는다.
"""
from urllib.parse import parse_qs, urlencode

GRANT_KEYS = (
    "q", "region", "field", "deadline", "org", "amount",
    "src", "from", "to", "sort", "open", "district",
)
BID_KEYS = (
    "q", "kind", "deadline", "org", "amount", "region", "sort", "open",
)
LIST_KEYS = {
    "region", "field", "deadline", "org", "amount", "district", "kind",
}
DEFAULTS = {
    "sort": "dday",
    "open": True,
    "src": "",
    "from": "",
    "to": "",
    "q": "",
}


def split_list(v):
    if v is None:
        return []
    if isinstance(v, (list, tuple)):
        out = []
        for item in v:
            out.extend(split_list(item))
        return out
    return [p.strip() for p in str(v).split(",") if p.strip()]


def _first(qs, *keys):
    for k in keys:
        if k in qs and qs[k]:
            raw = qs[k]
            if isinstance(raw, list):
                raw = raw[0] if raw else ""
            return str(raw)
    return ""


def _lists(qs, *keys):
    out = []
    seen = set()
    for k in keys:
        for item in split_list(qs.get(k)):
            if item not in seen:
                seen.add(item)
                out.append(item)
    return out


def parse_query(query):
    """'?a=1' / 'a=1' / dict → parse_qs 형태."""
    if query is None:
        return {}
    if isinstance(query, dict):
        return {k: (v if isinstance(v, list) else [v]) for k, v in query.items()
                if v is not None and v != ""}
    s = str(query).lstrip("?").split("#", 1)[0]
    if not s:
        return {}
    return parse_qs(s, keep_blank_values=False)


def empty_grant():
    return {
        "q": "",
        "region": [],
        "field": [],
        "deadline": [],
        "org": [],
        "amount": [],
        "district": [],
        "src": "",
        "from": "",
        "to": "",
        "sort": "dday",
        "open": True,
    }


def empty_bid():
    return {
        "q": "",
        "kind": [],
        "deadline": [],
        "org": [],
        "amount": [],
        "region": [],
        "sort": "dday",
        "open": True,
    }


def parse_grant(query):
    qs = parse_query(query)
    st = empty_grant()
    st["q"] = _first(qs, "q").strip()
    st["region"] = _lists(qs, "region")
    st["field"] = _lists(qs, "field", "category")
    st["deadline"] = _lists(qs, "deadline", "due")
    st["org"] = _lists(qs, "org")
    st["amount"] = _lists(qs, "amount")
    st["district"] = _lists(qs, "district")
    st["src"] = _first(qs, "src").strip()
    st["from"] = _first(qs, "from").strip()
    st["to"] = _first(qs, "to").strip()
    st["sort"] = _first(qs, "sort").strip() or "dday"
    open_raw = _first(qs, "open").strip()
    st["open"] = open_raw not in ("0", "false", "no")
    return st


def parse_bid(query):
    qs = parse_query(query)
    st = empty_bid()
    st["q"] = _first(qs, "q").strip()
    st["kind"] = _lists(qs, "kind")
    st["deadline"] = _lists(qs, "deadline", "due")
    st["org"] = _lists(qs, "org")
    st["amount"] = _lists(qs, "amount")
    st["region"] = _lists(qs, "region")
    st["sort"] = _first(qs, "sort").strip() or "dday"
    open_raw = _first(qs, "open").strip()
    st["open"] = open_raw not in ("0", "false", "no")
    return st


def _put(pairs, key, value, locked):
    if locked.get(key):
        return
    if isinstance(value, (list, tuple)):
        value = ",".join(v for v in value if v)
    if not value:
        return
    if key == "sort" and value == DEFAULTS["sort"]:
        return
    pairs.append((key, value))


def serialize_grant(state, locked=None):
    locked = locked or {}
    st = empty_grant()
    st.update(state or {})
    pairs = []
    _put(pairs, "q", (st.get("q") or "").strip(), locked)
    _put(pairs, "region", st.get("region") or [], locked)
    _put(pairs, "field", st.get("field") or st.get("category") or [], locked)
    _put(pairs, "deadline", st.get("deadline") or st.get("period") or [], locked)
    _put(pairs, "org", st.get("org") or [], locked)
    _put(pairs, "amount", st.get("amount") or [], locked)
    _put(pairs, "district", st.get("district") or [], locked)
    _put(pairs, "src", st.get("src") or "", locked)
    _put(pairs, "from", st.get("from") or "", locked)
    _put(pairs, "to", st.get("to") or "", locked)
    _put(pairs, "sort", st.get("sort") or "dday", locked)
    if st.get("open") is False and not locked.get("open"):
        pairs.append(("open", "0"))
    return urlencode(pairs, doseq=False)


def serialize_bid(state, locked=None):
    locked = locked or {}
    st = empty_bid()
    st.update(state or {})
    pairs = []
    _put(pairs, "q", (st.get("q") or "").strip(), locked)
    _put(pairs, "kind", st.get("kind") or [], locked)
    _put(pairs, "deadline", st.get("deadline") or st.get("due") or [], locked)
    _put(pairs, "org", st.get("org") or [], locked)
    _put(pairs, "amount", st.get("amount") or [], locked)
    _put(pairs, "region", st.get("region") or [], locked)
    _put(pairs, "sort", st.get("sort") or "dday", locked)
    if st.get("open") is False and not locked.get("open"):
        pairs.append(("open", "0"))
    return urlencode(pairs, doseq=False)


def query_string(serialized):
    return ("?" + serialized) if serialized else ""


def roundtrip_grant(query, locked=None):
    """parse → serialize. 잠긴 키는 결과에서 빠진다."""
    return serialize_grant(parse_grant(query), locked=locked)


def roundtrip_bid(query, locked=None):
    return serialize_bid(parse_bid(query), locked=locked)


def is_filtered_grant(state):
    st = state or {}
    return bool(
        (st.get("q") or "").strip()
        or st.get("region") or st.get("field") or st.get("deadline")
        or st.get("org") or st.get("amount") or st.get("district")
        or st.get("src") or st.get("from") or st.get("to")
        or (st.get("sort") and st.get("sort") != "dday")
        or st.get("open") is False
    )


def describe_grant(state):
    """알림 메일·조건 저장용 한 줄. 없는 조건을 지어내지 않는다."""
    st = parse_grant(serialize_grant(state or {})) if not isinstance(state, dict) else (state or {})
    bits = []
    if st.get("q"):
        bits.append("검색 " + st["q"])
    for key, label in (
        ("region", "지역"), ("field", "분야"), ("org", "기관"),
        ("deadline", "기간"), ("amount", "금액"), ("district", "시군구"),
    ):
        vals = st.get(key) or []
        if vals:
            bits.append(label + " " + "·".join(vals))
    if st.get("src") == "kstartup":
        bits.append("출처 K-Startup")
    elif st.get("src") == "bizinfo":
        bits.append("출처 기업마당")
    if st.get("from") or st.get("to"):
        bits.append("날짜 " + (st.get("from") or "") + "~" + (st.get("to") or ""))
    if st.get("open") is False:
        bits.append("마감 포함")
    return " / ".join(bits) or "전체"


def describe_bid(state):
    st = state or {}
    bits = []
    if st.get("q"):
        bits.append("검색 " + st["q"])
    for key, label in (
        ("kind", "종류"), ("region", "지역"), ("org", "발주기관"),
        ("deadline", "기간"), ("amount", "추정가격"),
    ):
        vals = st.get(key) or []
        if vals:
            bits.append(label + " " + "·".join(vals))
    if st.get("open") is False:
        bits.append("마감 포함")
    return " / ".join(bits) or "입찰 전체"
