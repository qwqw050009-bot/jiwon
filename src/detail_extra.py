"""상세페이지를 공고마다 다르게 만드는 블록 (실데이터만).

- summary_box: 필드에서 읽은 요약 (지원 규모·대상·지역·접수기간·D-day·주관기관)
- desc_sections: 원문 본문(overview/points/method)을 대상·지원내용·서류·신청방법으로 나눠 정리
- compare_rows: 비슷한 공고 3~5건 비교 (마감·금액)
- agency_others: 같은 주관기관의 다른 접수 중 공고
- is_thin: 요약이 짧거나 금액·마감일 없이 빈약한 공고 (noindex,follow·sitemap 제외)

없는 값은 만들지 않는다. 값이 없으면 그 줄을 빼고, 다른 공고와 같은 문구를
채워 넣지 않는다.
"""
import re

import filters as filt

_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"[ \t\u00a0]+")
_BULLET = re.compile(r"^\s*(?:[-‐–·•●○◦▶▷►☞※□■◆◇ㅇ\*]|\d+[.)]|[가-하][.)]|[①-⑳])\s*")
REF = ("공고문 참조", "원문 확인", "")

SECTION_RULES = [
    ("docs", "제출서류", ("제출서류", "구비서류", "서류", "사업계획서", "신청서", "증명서", "사본", "등본", "확인서")),
    ("method", "신청방법", ("신청방법", "접수방법", "온라인", "방문", "우편", "이메일", "e-mail", "접수처", "누리집", "홈페이지", "시스템")),
    ("elig", "지원 대상·자격", ("지원대상", "신청자격", "대상", "자격", "제외", "소재", "업력", "이내", "이상인", "기업", "소상공인", "예비창업자")),
    ("support", "지원 내용", ("지원내용", "지원규모", "지원금", "지원한도", "억원", "만원", "천원", "%", "지원", "보조", "융자", "컨설팅")),
]


def clean_text(v):
    s = _TAG.sub(" ", str(v or ""))
    s = s.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    lines = []
    for ln in s.splitlines():
        ln = _WS.sub(" ", ln).strip()
        if ln:
            lines.append(ln)
    return lines


def _has(v):
    return bool(str(v or "").strip()) and str(v).strip() not in REF


def _period(a):
    if a.get("period_type") == "always":
        return a.get("period_raw") or ""
    s, e = a.get("apply_start") or "", a.get("apply_end") or ""
    if s and e:
        return f"{s} ~ {e}"
    return e or a.get("period_raw") or ""


def summary_box(a):
    """필드에서만 읽는 요약. 값 없는 줄은 뺀다."""
    a = a or {}
    out = []
    amt = a.get("amount")
    if _has(amt):
        out.append({"k": "지원 금액·규모", "v": amt, "src": "본문 표기"})
    tgt = (clean_text(a.get("target")) or [""])[0]
    if _has(tgt):
        out.append({"k": "대상", "v": tgt[:80], "src": "지원대상 필드"})
    reg = a.get("region_label") or a.get("region")
    if _has(reg):
        out.append({"k": "지역", "v": reg, "src": "제목·기관·태그"})
    per = _period(a)
    if _has(per):
        out.append({"k": "접수 기간", "v": per, "src": "접수기간 필드"})
    dl = a.get("dlabel")
    if dl:
        out.append({"k": "D-day", "v": dl + (f" ({a['dsub']})" if a.get("dsub") and a.get("dsub") != dl else ""), "src": "오늘 기준 계산"})
    org = a.get("org")
    if _has(org):
        v = org
        ex = a.get("exec_org")
        if _has(ex) and ex != org:
            v = f"{org} (수행 {ex})"
        out.append({"k": "주관기관", "v": v, "src": "소관·수행기관 필드"})
    return out


def _classify(line, head=None):
    low = line.lower()
    for key, _label, words in SECTION_RULES:
        if head and any(w in head for w in words[:2]):
            return key
    for key, _label, words in SECTION_RULES:
        if any(w.lower() in low for w in words[:2]):
            return key
    for key, _label, words in SECTION_RULES:
        if any(w.lower() in low for w in words):
            return key
    return "etc"


def desc_sections(a, max_lines=12):
    """원문 본문을 섹션으로. 각 섹션은 원문 문장 그대로(정리만)."""
    a = a or {}
    buckets = {k: [] for k, _l, _w in SECTION_RULES}
    buckets["etc"] = []
    seen = set()
    for p in a.get("points") or []:
        lines = clean_text(p)
        if not lines:
            continue
        head = lines[0]
        key0 = _classify(head)
        for i, ln in enumerate(lines):
            t = _BULLET.sub("", ln).strip()
            if len(t) < 4 or t in seen or "공고문 참조" == t.strip("※ "):
                continue
            seen.add(t)
            key = key0 if i else _classify(t)
            buckets[key].append(t)
    for ln in clean_text(a.get("method")):
        t = _BULLET.sub("", ln).strip()
        if len(t) >= 2 and t not in seen:
            seen.add(t)
            k = "docs" if any(w in t for w in ("서류", "신청서", "증명", "사본")) else "method"
            buckets[k].append(t)
    out = []
    labels = {k: l for k, l, _w in SECTION_RULES}
    labels["etc"] = "그 밖의 내용"
    for key in ("elig", "support", "docs", "method", "etc"):
        lines = buckets[key][:max_lines]
        if lines:
            out.append({"key": key, "title": labels[key], "lines": lines})
    return out


def overview_paras(a):
    return [ln for ln in clean_text((a or {}).get("overview")) if len(ln) >= 4]


def _open(row, pool):
    return filt._open_others(row, pool)


def _score(row, x, toks):
    s = 0
    if row.get("category") and x.get("category") == row.get("category"):
        s += 2
    if row.get("region") and x.get("region") == row.get("region"):
        s += 2
    if row.get("org") and x.get("org") == row.get("org"):
        s += 1
    s += min(3, len(toks.intersection(filt.title_tokens(x.get("title") or ""))))
    return s


def compare_rows(a, pool, limit=5, exclude=()):
    """같은 분야·지역·기관·제목 토큰 점수 상위 3~5건. 실제 공고만."""
    a = a or {}
    toks = set(filt.title_tokens(a.get("title") or ""))
    ex = set(exclude)
    scored = []
    for x in _open(a, pool):
        if x.get("id") in ex:
            continue
        sc = _score(a, x, toks)
        if sc >= 2:
            scored.append((-sc, filt._dday_key(x), str(x.get("id")), x))
    scored.sort(key=lambda t: t[:3])
    rows = [t[3] for t in scored[:limit]]
    if len(rows) < 3:
        return []
    return [_cmp(x, a) for x in rows]


def _cmp(x, a):
    why = []
    if a.get("category") and x.get("category") == a.get("category"):
        why.append("같은 분야")
    if a.get("region") and x.get("region") == a.get("region"):
        why.append("같은 지역")
    if a.get("org") and x.get("org") == a.get("org"):
        why.append("같은 기관")
    if not why:
        why.append("제목 유사")
    return {
        "id": x.get("id"), "title": x.get("title") or "",
        "org": x.get("org") or "", "dlabel": x.get("dlabel") or "",
        "deadline": _period(x) if x.get("period_type") == "always" else (x.get("apply_end") or ""),
        "amount": x.get("amount_card") or (x.get("amount") if _has(x.get("amount")) else "") or "",
        "why": "·".join(why),
    }


def agency_others(a, pool, limit=5, exclude=()):
    org = (a or {}).get("org")
    if not _has(org):
        return []
    ex = set(exclude)
    rows = [x for x in _open(a, pool) if x.get("org") == org and x.get("id") not in ex]
    rows.sort(key=filt._dday_key)
    return [_cmp(x, a) for x in rows[:limit]]


def agency_total(a, pool):
    org = (a or {}).get("org")
    if not _has(org):
        return 0
    return sum(1 for x in _open(a, pool) if x.get("org") == org)


# 얇은 상세페이지 기준 (noindex, follow + sitemap 제외). 2026-10 실데이터 1,341건 기준
# 약 19%가 걸린다. 기준을 바꾸면 build 로그 "얇은 상세페이지 noindex N건" 을 같이 확인할 것.
THIN_BODY_MIN = 150          # 요약(개요+요점) 글자 수가 이보다 짧으면 얇다
THIN_BODY_NO_FACTS = 250     # 금액도 마감일도 없으면 이 길이 미만일 때 얇다


def body_len(a):
    """상세 본문으로 보이는 요약(개요 + 요점) 글자 수."""
    a = a or {}
    body = "".join(clean_text(a.get("overview"))) + "".join(
        "".join(clean_text(p)) for p in a.get("points") or [])
    return len(body)


def is_thin(a):
    """
    얇은 상세페이지면 True. 아래 중 하나면 얇다.
      1) 요약이 THIN_BODY_MIN(150)자 미만
      2) 본문 금액 표기가 없고, 마감일이 없는 상시 공고이며, 요약이 THIN_BODY_NO_FACTS(250)자 미만
      3) (기존) 요약 40자 미만이면서 대상·방법·문의·금액 중 1개 이하만 있음 — 1)에 포함됨
    금액 판단은 enrich.amount_card 와 같다(숫자 없는 ', 원' 은 없는 것으로 본다).
    """
    a = a or {}
    n = body_len(a)
    if n < THIN_BODY_MIN:
        return True
    from enrich import amount_card
    has_amount = bool(amount_card(a))
    has_deadline = a.get("period_type") != "always" and bool(a.get("apply_end"))
    if not has_amount and not has_deadline and n < THIN_BODY_NO_FACTS:
        return True
    return False


def notice_stats_line(a, pool):
    """이 공고의 위치를 실제 수치로: 같은 분야·지역 접수 중 몇 건 중 마감 몇 번째."""
    a = a or {}
    cat, reg = a.get("category"), a.get("region")
    same = [x for x in _open(a, pool) if x.get("category") == cat and x.get("region") == reg]
    if not same or not cat or not reg:
        return ""
    d = a.get("dday")
    earlier = sum(1 for x in same if isinstance(d, int) and isinstance(x.get("dday"), int) and x["dday"] < d)
    s = f"{reg} {cat} 분야에서 지금 접수 중인 다른 공고는 {len(same)}건입니다."
    if isinstance(d, int) and d >= 0 and d != 9999:
        s += f" 이 공고보다 먼저 마감되는 공고는 {earlier}건입니다."
    return s


def list_stats(items):
    """목록 페이지용 실제 통계 한 문단. 항목이 없으면 빈 문자열."""
    items = list(items or [])
    if not items:
        return ""
    n = len(items)
    amt = sum(1 for x in items if x.get("amount_card"))
    always = sum(1 for x in items if x.get("period_type") == "always")
    week = sum(1 for x in items if isinstance(x.get("dday"), int) and 0 <= x["dday"] <= 7)
    orgs = {}
    for x in items:
        if x.get("org"):
            orgs[x["org"]] = orgs.get(x["org"], 0) + 1
    top = sorted(orgs.items(), key=lambda t: (-t[1], t[0]))[:3]
    s = f"집계 기준 {n}건 중 7일 안에 마감 {week}건, 상시·예산소진형 {always}건, 본문에 지원 금액이 적힌 공고 {amt}건입니다."
    if top:
        s += " 공고가 많은 기관: " + ", ".join(f"{o} {c}건" for o, c in top) + "."
    return s


# ── 입찰 상세 ────────────────────────────────────────────────

def _bid_cmp(x, a):
    why = []
    if a.get("kind") and x.get("kind") == a.get("kind"):
        why.append("같은 종류")
    if a.get("region") and x.get("region") == a.get("region"):
        why.append("같은 지역")
    if a.get("org") and x.get("org") == a.get("org"):
        why.append("같은 수요기관")
    return {
        "id": x.get("id"), "title": x.get("title") or "", "org": x.get("org") or "",
        "dlabel": x.get("dlabel") or "", "deadline": str(x.get("close_dt") or "")[:16],
        "amount": x.get("budget_card") or "",
        "why": "·".join(why) or "제목 유사",
    }


def bid_compare_rows(a, pool, limit=5, exclude=()):
    a = a or {}
    toks = set(filt.title_tokens(a.get("title") or ""))
    ex = set(exclude)
    scored = []
    for x in _open(a, pool):
        if x.get("id") in ex:
            continue
        s = 0
        if a.get("kind") and x.get("kind") == a.get("kind"):
            s += 2
        if a.get("region") and x.get("region") == a.get("region"):
            s += 2
        if a.get("org") and x.get("org") == a.get("org"):
            s += 1
        s += min(3, len(toks.intersection(filt.title_tokens(x.get("title") or ""))))
        if s >= 3:
            scored.append((-s, filt._dday_key(x), str(x.get("id")), x))
    scored.sort(key=lambda t: t[:3])
    rows = [t[3] for t in scored[:limit]]
    return [_bid_cmp(x, a) for x in rows] if len(rows) >= 3 else []


def bid_agency_others(a, pool, limit=5, exclude=()):
    org = (a or {}).get("org")
    if not _has(org):
        return []
    ex = set(exclude)
    rows = [x for x in _open(a, pool) if x.get("org") == org and x.get("id") not in ex]
    rows.sort(key=filt._dday_key)
    return [_bid_cmp(x, a) for x in rows[:limit]]
