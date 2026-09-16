# -*- coding: utf-8 -*-
"""
검색결과(SERP)용 title·meta description.

목록 소개문(intros)과 분리한다. 페이지 종류마다 앞머리를 다르게 두고,
건수는 화면에 실제로 올라온 목록에서만 센다. 없는 숫자를 만들지 않는다.

브랜드 접미사는 항상 `| 지원사업 마감판`.
"""
from datetime import date
import re

import config
from enrich import _josa


BRAND = config.SITE["name"]

# 분야 제목 앞머리. 검색어(분야+지원금/지원사업)를 30자 안에 둔다.
_CAT_LEAD = {
    "금융": "금융 지원금·융자",
    "기술": "기술·R&D 지원사업",
    "인력": "인력·채용 지원금",
    "수출": "수출 바우처·지원사업",
    "내수": "내수·마케팅 지원금",
    "창업": "창업 지원금·지원사업",
    "경영": "경영 지원금·컨설팅",
    "기타": "기타 지원사업",
}

# 분야마다 다른 뒷말. 8개 분야 스니펫이 서로 닮지 않게.
_CAT_HOOK = {
    "금융": "소상공인 정책자금",
    "기술": "중소기업 R&D",
    "인력": "인건비·채용",
    "수출": "해외진출",
    "내수": "소상공인 판로",
    "창업": "예비·초기",
    "경영": "소상공인 시설",
    "기타": "소상공인·중소기업",
}

_CAT_OPEN = {
    "금융": "융자·보증·이차보전이 섞인 금융 공고",
    "기술": "R&D·기술개발·특허 지원 공고",
    "인력": "채용·인건비·교육훈련 지원 공고",
    "수출": "해외진출·수출바우처·전시 지원 공고",
    "내수": "판로·마케팅·유통 지원 공고",
    "창업": "예비·초기창업 사업화 공고",
    "경영": "컨설팅·경영개선·시설 지원 공고",
    "기타": "여덟 분야에 넣기 어려운 공고",
}

# 지역 행정 구조. 제목 중간 토큰만 갈라 17개 지역이 같은 틀로
# 보이지 않게 한다. 전남광주는 통합 단위 그대로.
_REGION_KIND = {
    "서울": "metro", "부산": "metro", "대구": "metro", "대전": "metro",
    "인천": "metro", "울산": "metro",
    "경기": "wide",
    "강원": "do", "충북": "do", "충남": "do", "전북": "do",
    "경북": "do", "경남": "do",
    "세종": "city", "제주": "island",
    "전남광주": "united",
    "전국": "nation",
}

_STATIC_DESC = {
    "about": (
        "정부지원사업을 마감일 순으로 모아 보여주는 사이트입니다. "
        "소상공인·중소기업, 회원가입 없이 지역·분야로 확인하세요."
    ),
    "privacy": (
        "지원사업 마감판 개인정보처리방침입니다. "
        "회원가입 없이 이용하며, 광고·쿠키·문의 창구를 확인할 수 있습니다."
    ),
    "terms": (
        "지원사업 마감판 이용약관입니다. "
        "정보 제공 범위, 원문 확인 책임, 입찰·지원 문의 한계를 정리했습니다."
    ),
    "contact": (
        "지원사업 마감판 문의처입니다. "
        "정보 오류 신고는 받고, 개별 공고 자격·심사는 소관기관에 물어야 합니다."
    ),
}


def year(today=None):
    return (today or date.today()).year


def with_brand(core):
    core = re.sub(r"\s+", " ", (core or "").strip(" ·|-"))
    if not core:
        return BRAND
    if core.endswith(BRAND) or core.endswith(f"| {BRAND}"):
        return core
    return f"{core} | {BRAND}"


def clip_desc(text, lo=70, hi=120):
    """
    한글 SERP 설명 길이. 문장 끝(다.)을 우선하고, 없으면 끊는다.
    70자보다 짧아도 의미 있는 문장이면 그대로 둔다.
    """
    s = re.sub(r"\s+", " ", text or "").strip()
    if not s:
        return ""
    if len(s) <= hi:
        return s
    cut = s.rfind("다.", 0, hi - 1)
    if cut >= lo - 2:
        return s[: cut + 2]
    cut = s.rfind(".", 0, hi)
    if cut >= lo:
        return s[: cut + 1]
    br = max(s.rfind(" ", 0, hi - 1), s.rfind("·", 0, hi - 1))
    if br >= lo:
        return s[:br].rstrip(" ·,") + "…"
    return s[: hi - 1].rstrip(" ·,") + "…"


def counts_of(items):
    """목록에 보이는 건수만. is_open이 없어도 dday>=0 이면 접수로 센다."""
    items = items or []
    today = week = always = open_n = 0
    for a in items:
        if a.get("period_type") == "always":
            always += 1
            if a.get("is_open") is False:
                continue
            open_n += 1
            continue
        d = a.get("dday")
        if not isinstance(d, int):
            if a.get("is_open"):
                open_n += 1
            continue
        if d >= 0:
            open_n += 1
        if d == 0:
            today += 1
            week += 1
        elif 0 < d <= 7:
            week += 1
    return {
        "n": len(items),
        "today": today,
        "week": week,
        "always": always,
        "open": open_n,
    }


def _nbit(n):
    n = int(n or 0)
    return f"{n}건" if n > 0 else ""


def _join(*parts):
    out = []
    for p in parts:
        p = re.sub(r"\s+", " ", (p or "").strip(" ·|-"))
        if p:
            out.append(p)
    return " · ".join(out)


def _count_bits(c, include_always=True):
    bits = []
    if c["today"]:
        bits.append(f"오늘 마감 {c['today']}건")
    if c["week"] and c["week"] != c["today"]:
        bits.append(f"이번 주 마감 {c['week']}건")
    if include_always and c["always"]:
        bits.append(f"상시 접수 {c['always']}건")
    return bits


def _count_clause(c, include_always=True):
    bits = _count_bits(c, include_always=include_always)
    if not bits:
        if c["open"]:
            return f"접수 중 {c['open']}건"
        if c["n"]:
            return f"지금 {c['n']}건"
        return ""
    if len(bits) == 1:
        return bits[0]
    return f"{bits[0]}, {', '.join(bits[1:])}"


def _urgency_chip(c):
    """조합 페이지 제목 뒷말. 같은 틀이 수백 개 반복되지 않게 시계열로 가른다."""
    if c["today"]:
        return f"오늘 마감 {c['today']}건"
    if c["week"]:
        return f"이번 주 마감 {c['week']}건"
    if c["always"]:
        return f"상시 {_nbit(c['always'])}".strip()
    return "마감일 순"


def _region_label(region):
    return "전남광주" if region == "전남광주" else (region or "")


def _cat_lead(name):
    return _CAT_LEAD.get(name) or f"{name} 지원사업"


def _cat_hook(name):
    return _CAT_HOOK.get(name) or "소상공인·중소기업"


# ── 홈·긴급·전체 ─────────────────────────────────────────────

def home_title(today=None):
    return with_brand(f"오늘 마감 정부지원사업 · 소상공인 보조금 {year(today)}")


def home_desc(items=None):
    c = counts_of(items)
    clock = _count_clause(c)
    if clock:
        head = f"{clock}입니다."
    else:
        head = "정부지원사업을 마감일 순으로 둡니다."
    return clip_desc(
        f"{head} 소상공인·중소기업 보조금·융자를 회원가입 없이 지역·분야로 "
        f"좁혀 {year()}년 공고를 확인하세요."
    )


def home_h1():
    return "오늘 마감되는 정부지원사업부터 봅니다"


def home_lede():
    return "마감일 순으로 무료 정리합니다. 회원가입 없이 지역·분야로 좁혀 보세요."


def urgent_title(items=None):
    c = counts_of(items)
    n = _nbit(c["n"] or c["week"])
    return with_brand(_join("이번 주 마감 지원사업", n, "D-7 이내"))


def urgent_desc(items=None):
    c = counts_of(items)
    n = c["n"] or c["week"]
    if n:
        head = f"7일 안에 접수가 끝나는 지원사업 {n}건입니다."
    else:
        head = "7일 안에 접수가 끝나는 지원사업만 모았습니다."
    clock = _count_clause(c, include_always=False)
    extra = f" {clock}." if clock and clock not in head else ""
    return clip_desc(
        f"{head}{extra} 소상공인·중소기업 지원금·보조금을 마감일 순으로 확인하세요."
    )


def urgent_h1():
    return "이번 주 마감 지원사업"


def urgent_lede(items=None):
    c = counts_of(items)
    if c["n"]:
        return f"7일 안에 접수가 끝나는 지원사업 {c['n']}건입니다. 오늘 마감부터 보세요."
    return "7일 안에 접수가 끝나는 지원사업만 모았습니다."


def all_title(items=None):
    c = counts_of(items)
    n = _nbit(c["n"] or c["open"])
    return with_brand(_join("정부지원사업 전체", n, f"마감일 순 {year()}"))


def all_desc(items=None):
    c = counts_of(items)
    n = c["n"] or c["open"]
    clock = _count_clause(c)
    if n:
        head = f"접수 중·최근 공고 {n}건을 한 목록에서 마감일 순으로 봅니다."
    else:
        head = "정부지원사업 전체를 마감일 순으로 봅니다."
    extra = f" {clock}." if clock and clock not in head else ""
    return clip_desc(
        f"{head}{extra} 소상공인·중소기업, 지역·분야 필터, 회원가입 없이 확인하세요."
    )


def all_h1():
    return "전체 지원사업, 마감일 순"


def all_lede(items=None):
    c = counts_of(items)
    if c["n"]:
        return f"접수 중인 지원사업 {c['n']}건을 마감일 순으로 정렬했습니다."
    return "접수 중인 지원사업을 마감일 순으로 정렬했습니다."


def new_title(items=None):
    c = counts_of(items)
    return with_brand(_join("새로 올라온 지원사업", _nbit(c["n"]), "오늘 등록"))


def new_desc(items=None):
    c = counts_of(items)
    n = c["n"]
    head = f"오늘 새로 등록된 지원사업 {n}건입니다." if n else "오늘 새로 등록된 지원사업입니다."
    return clip_desc(
        f"{head} 소상공인·중소기업 공고를 마감일 순으로 확인하고, "
        "자격에 맞으면 원문으로 접수하세요."
    )


def new_h1():
    return "새로 올라온 지원사업"


def new_lede(items=None):
    c = counts_of(items)
    if c["n"]:
        return f"최근 새로 등록된 지원사업 {c['n']}건입니다."
    return "최근 새로 등록된 지원사업입니다."


# ── 허브 ────────────────────────────────────────────────────

def category_hub_title():
    return with_brand("분야별 정부지원사업 8종 · 금융부터 창업")


def category_hub_desc(n=0):
    nbit = _nbit(n)
    head = f"지금 {nbit}입니다. " if nbit else ""
    return clip_desc(
        f"금융·기술·인력·수출·내수·창업·경영·기타 8종. {head}"
        "소상공인·중소기업이 마감일 순으로 분야를 골라 확인하세요."
    )


def category_hub_h1():
    return "분야별 정부지원사업"


def category_hub_lede():
    return "금융부터 창업·경영까지 8종. 마감이 가까운 순으로 둡니다."


def region_hub_title():
    return with_brand("지역별 정부지원사업 · 사업장 소재지 17곳")


def region_hub_desc(n=0, n_regions=0):
    nbit = _nbit(n)
    rbit = f"시·도 {int(n_regions)}곳" if n_regions else "시·도 17곳"
    ro = _josa(rbit, "으로", "로")
    head = f"{nbit}을 {rbit}{ro} 나눕니다. " if nbit else f"{rbit}{ro} 나눕니다. "
    return clip_desc(
        f"사업장 소재지 기준 지원사업. {head}"
        "전남광주는 통합 단위입니다. 거주지 말고 등록증 소재지로 확인하세요."
    )


def region_hub_h1():
    return "지역별 정부지원사업"


def region_hub_lede():
    return "사업장 소재지 기준, 마감일 순. 전남광주는 통합 단위입니다."


# ── 분야 ────────────────────────────────────────────────────

def category_title(name, items=None):
    lead = _cat_lead(name)
    hook = _cat_hook(name)
    c = counts_of(items)
    if c["n"]:
        return with_brand(_join(f"{lead} {_nbit(c['n'])}", hook))
    return with_brand(_join(f"{lead} 마감일", hook))


def category_desc(name, cat=None, items=None):
    c = counts_of(items)
    extra = ((cat or {}).get("desc") or "").strip()
    open_s = _CAT_OPEN.get(name) or f"{name} 지원 공고"
    if c["n"]:
        head = f"{open_s} {c['n']}건입니다."
    else:
        head = f"{open_s}를 마감일 순으로 둡니다."
    clock = _count_clause(c)
    mid = f" {clock}." if clock and clock not in head else ""
    tail = f" {extra}." if extra and extra not in head else ""
    return clip_desc(
        f"{head}{mid} 소상공인·중소기업이 회원가입 없이 지역별로 오늘·이번 주 마감을 확인하세요.{tail}"
    )


def category_h1(name):
    if name == "금융":
        return "금융 지원금·융자, 마감일 순"
    if name == "기타":
        return "기타 지원사업, 마감일 순"
    return f"{name} 지원금·지원사업"


def category_lede(name, cat=None):
    extra = ((cat or {}).get("desc") or f"{name} 지원").strip()
    return f"{extra}. 마감이 가까운 순입니다."


# ── 지역 ────────────────────────────────────────────────────

def _region_core(region, nbit):
    kind = _REGION_KIND.get(region, "do")
    if kind == "nation":
        return _join("전국 신청 가능 지원사업", nbit, "소재지 제한 없음")
    if kind == "united":
        return _join("전남광주 소상공인 지원금", "통합특별시", nbit)
    if kind == "wide":
        return _join("경기 소상공인 지원금", "시·군 지원사업", nbit)
    if kind == "metro":
        return _join(f"{region} 소상공인 지원금", "시·구 지원사업", nbit)
    if kind == "city":
        return _join(f"{region} 소상공인 지원금", "시 단위", nbit)
    if kind == "island":
        return _join(f"{region} 소상공인 지원금", "도 단위", nbit)
    return _join(f"{region} 소상공인 지원금", "정부지원사업", nbit)


def region_title(region, items=None):
    c = counts_of(items)
    return with_brand(_region_core(region, _nbit(c["n"])))


def region_desc(region, items=None):
    c = counts_of(items)
    n = c["n"]
    kind = _REGION_KIND.get(region, "do")
    if kind == "nation":
        head = (
            f"사업장 소재지 제한이 없는 지원사업 {n}건입니다."
            if n else "사업장 소재지 제한이 없는 지원사업만 모았습니다."
        )
    elif kind == "united":
        head = (
            f"광주와 전남을 나누지 않은 전남광주통합특별시 지원사업 {n}건입니다."
            if n else "광주와 전남을 나누지 않은 전남광주통합특별시 지원사업입니다."
        )
    else:
        label = _region_label(region)
        head = (
            f"{label} 사업장 기준 지원사업 {n}건입니다."
            if n else f"{label} 사업장 기준 지원사업을 마감일 순으로 둡니다."
        )
    clock = _count_clause(c)
    extra = f" {clock}." if clock and clock not in head else ""
    return clip_desc(
        f"{head}{extra} 소상공인·중소기업 보조금을 마감일 순으로 확인하고 원문으로 접수하세요."
    )


def region_h1(region):
    if region == "전국":
        return "전국에서 신청하는 지원사업"
    if region == "전남광주":
        return "전남광주 소상공인 지원사업"
    return f"{region} 소상공인 지원사업"


def region_lede(region):
    if region == "전국":
        return "소재지 제한이 없는 공고를 마감일 순으로 둡니다."
    if region == "전남광주":
        return "전남광주통합특별시 사업장 기준 공고를 마감일 순으로 둡니다."
    return f"{region} 사업장 기준 공고를 마감일 순으로 둡니다."


# ── 지역×분야 ───────────────────────────────────────────────

def combo_title(region, category, items=None):
    c = counts_of(items)
    label = _region_label(region)
    return with_brand(_join(
        f"{label} {category} 지원사업", _nbit(c["n"]), _urgency_chip(c),
    ))


def combo_desc(region, category, cat=None, items=None):
    c = counts_of(items)
    label = _region_label(region)
    extra = ((cat or {}).get("desc") or "").strip()
    if c["n"]:
        head = f"{label} {category}만 보면 지금 {c['n']}건입니다."
    else:
        head = f"{label} {category} 지원사업을 마감일 순으로 둡니다."
    clock = _count_clause(c)
    mid = f" {clock}." if clock and clock not in head else ""
    note = f" {extra}." if extra and extra not in head else ""
    return clip_desc(
        f"{head}{mid} 오늘·이번 주 마감을 확인한 뒤 대상·소관기관을 보고 원문으로 가세요.{note}"
    )


def combo_h1(region, category):
    return f"{_region_label(region)} {category} 지원사업"


def combo_lede(region, category):
    return f"{_region_label(region)} {category} 분야 공고를 마감일 순으로 둡니다."


# ── 시군구 ──────────────────────────────────────────────────

def district_title(sido, district, items=None):
    c = counts_of(items)
    return with_brand(_join(
        f"{district} 지원사업", _nbit(c["n"]), f"{_region_label(sido)} 소상공인",
    ))


def district_desc(sido, district, items=None):
    c = counts_of(items)
    label = _region_label(sido)
    if c["n"]:
        head = f"{label} {district} 이름이 붙은 지원사업 {c['n']}건입니다."
    else:
        head = f"{label} {district} 이름이 붙은 지원사업만 모았습니다."
    clock = _count_clause(c)
    extra = f" {clock}." if clock and clock not in head else ""
    return clip_desc(
        f"{head}{extra} 시·도 전체가 아니라 이 시군구 해시태그만 모아 마감일 순으로 확인하세요."
    )


def district_h1(sido, district):
    return f"{district} 지원사업 · {_region_label(sido)}"


def district_lede(sido, district):
    return f"{_region_label(sido)} {district} 관련 공고를 마감일 순으로 둡니다."


def district_combo_title(sido, district, category, items=None):
    c = counts_of(items)
    return with_brand(_join(
        f"{district} {category} 지원사업", _nbit(c["n"]), _urgency_chip(c),
    ))


def district_combo_desc(sido, district, category, cat=None, items=None):
    c = counts_of(items)
    label = _region_label(sido)
    extra = ((cat or {}).get("desc") or "").strip()
    if c["n"]:
        head = f"{district} {category}만 보면 {c['n']}건입니다. {label} 목록에서 이 시군구만 골랐습니다."
    else:
        head = f"{label} {district} {category} 공고를 마감일 순으로 둡니다."
    clock = _count_clause(c)
    mid = f" {clock}." if clock and clock not in head else ""
    note = f" {extra}." if extra and extra not in head else ""
    return clip_desc(
        f"{head}{mid} 오늘·이번 주 마감을 보고 원문으로 접수하세요.{note}"
    )


def district_combo_h1(sido, district, category):
    return f"{district} {category} 지원사업"


def district_combo_lede(sido, district, category):
    return f"{_region_label(sido)} {district} {category} 분야 공고를 마감일 순으로 둡니다."


# ── 상세 ────────────────────────────────────────────────────

def notice_title(row):
    row = row or {}
    title = (row.get("title") or "지원사업 공고").strip()
    closed = row.get("is_closed") or (
        isinstance(row.get("dday"), int) and row["dday"] < 0
        and row.get("period_type") != "always"
    )
    if closed:
        return with_brand(f"{title} — 마감된 공고")
    if row.get("period_type") == "always":
        return with_brand(f"{title} — 상시 접수")
    d = row.get("dday")
    if d == 0:
        return with_brand(f"[오늘 마감] {title}")
    if isinstance(d, int) and 0 < d <= 7:
        return with_brand(f"[D-{d}] {title}")
    return with_brand(f"{title} — 마감일·신청자격")


def notice_desc(row, limit=150):
    row = row or {}
    summary = ((row.get("ai") or {}).get("summary") or "").strip()
    if not summary:
        summary = (row.get("blurb") or "").strip()
    if not summary:
        org = (row.get("org") or "").strip()
        cat = (row.get("category") or "").strip()
        region = (row.get("region") or "").strip()
        bits = []
        if org:
            bits.append(f"{org} 소관")
        if region:
            bits.append(region)
        if cat:
            bits.append(f"{cat} 분야")
        bits.append("지원사업입니다. 신청자격과 마감일을 원문에서 확인하세요.")
        summary = " ".join(bits)
    prefix = ""
    if row.get("is_closed") or (isinstance(row.get("dday"), int) and row["dday"] < 0
                                and row.get("period_type") != "always"):
        prefix = "마감된 공고입니다. "
    elif row.get("period_type") == "always":
        raw = (row.get("period_raw") or "상시 접수").strip()
        prefix = f"상시 접수('{raw}'). "
    elif row.get("dday") == 0:
        prefix = "오늘 마감. "
    elif isinstance(row.get("dday"), int) and 0 < row["dday"] <= 7:
        prefix = f"D-{row['dday']} 마감. "
    return clip_desc(prefix + summary, lo=70, hi=limit)


# ── 가이드·고정·캘린더 ───────────────────────────────────────

def guide_hub_title():
    return with_brand(f"정부지원사업 가이드 · 신청 자격·서류 {year()}")


def guide_hub_desc():
    return clip_desc(
        "신청 자격, 서류, 바우처·선정 차이, 소상공인 지원금 순서까지. "
        "공고가 바뀌어도 남는 기본기를 확인하세요."
    )


def guide_title(h1):
    return with_brand(h1)


def calendar_title():
    return with_brand("지원사업 마감일 캘린더 구독 · 무료 ICS")


def calendar_desc():
    return clip_desc(
        "관심 지역·분야 마감일을 내 캘린더에 자동으로 받습니다. "
        "회원가입 없이 ICS로 구독하고, 마감 하루 전 알림을 확인하세요."
    )


def static_desc(slug, h1=""):
    return _STATIC_DESC.get(slug) or clip_desc(
        f"{h1 or slug}. 지원사업 마감판의 고정 안내 페이지입니다."
    )


def scrap_title():
    return with_brand("스크랩한 지원사업")


def scrap_desc():
    return "이 브라우저에 스크랩한 지원사업을 마감일 순으로 모읍니다. 서버에 저장하지 않습니다."


# ── 입찰 (지원금·바우처 카피 금지) ───────────────────────────

def bid_hub_title():
    return with_brand("나라장터 입찰공고 마감일시 · 오늘 마감")


def bid_hub_desc(tally=None):
    t = tally or {}
    today = int(t.get("today") or 0)
    urgent = int(t.get("urgent") or 0)
    open_n = int(t.get("open") or 0)
    if open_n:
        bits = [f"나라장터 입찰 {open_n}건을 마감일시 순으로 봅니다."]
        clock = []
        if today:
            clock.append(f"오늘 마감 {today}건")
        if urgent and urgent != today:
            clock.append(f"이번 주 {urgent}건")
        if clock:
            bits.append(", ".join(clock) + ".")
        bits.append("물품·용역·공사·외자, 수요기관·추정가격을 확인하세요.")
        return clip_desc(" ".join(bits))
    return clip_desc(
        "나라장터 입찰공고를 마감일시 순으로 정리합니다. "
        "물품·용역·공사·외자로 나누고, 수요기관과 추정가격을 확인할 수 있습니다."
    )


def bid_urgent_title(n=0):
    return with_brand(_join("이번 주 마감 입찰", _nbit(n), "나라장터 D-7"))


def bid_urgent_desc(n=0):
    if n:
        head = f"나라장터에서 7일 안에 마감되는 입찰 {n}건입니다."
    else:
        head = "나라장터에서 7일 안에 마감되는 입찰만 모았습니다."
    return clip_desc(
        f"{head} 물품·용역·공사·외자 마감일시를 확인하고 원문으로 가세요."
    )


def bid_kind_title(name, n=0):
    return with_brand(_join(f"{name} 입찰공고", _nbit(n), "나라장터 마감일시"))


def bid_kind_desc(name, n=0, kind_desc=""):
    extra = (kind_desc or "").strip()
    if n:
        head = f"나라장터 {name} 입찰 진행 중 {n}건입니다."
    else:
        head = f"나라장터 {name} 입찰을 마감일시 순으로 둡니다."
    note = f" {extra}." if extra and extra not in head else ""
    return clip_desc(
        f"{head}{note} 수요기관·추정가격을 보고 원문에서 참가 자격을 확인하세요."
    )


def bid_region_hub_title():
    return with_brand("지역별 입찰공고 · 나라장터 참가지역")


def bid_region_hub_desc():
    return clip_desc(
        "나라장터 참가제한·참가가능 지역 표기가 확인된 입찰만 모았습니다. "
        "제목에서 지역을 추측하지 않습니다. 마감일시 순으로 확인하세요."
    )


def bid_region_title(region, n=0):
    return with_brand(_join(f"{region} 참가지역 입찰", _nbit(n), "나라장터"))


def bid_region_desc(region, n=0):
    if n:
        head = f"참가지역 표기가 {region}{_josa(region, '과', '와')} 정확히 같은 입찰 {n}건입니다."
    else:
        head = f"참가지역 표기가 {region}{_josa(region, '과', '와')} 정확히 같은 입찰만 모았습니다."
    return clip_desc(
        f"{head} 제목에서 지역을 추측하지 않습니다. 마감일시 순으로 확인하세요."
    )


def bid_notice_title(row):
    row = row or {}
    title = (row.get("title") or "입찰공고").strip()
    if not row.get("is_open") or (isinstance(row.get("dday"), int) and row["dday"] < 0):
        return with_brand(f"{title} — 마감된 입찰")
    d = row.get("dday")
    if d == 0:
        return with_brand(f"[오늘 마감] {title}")
    if isinstance(d, int) and 0 < d <= 7:
        return with_brand(f"[D-{d}] {title}")
    return with_brand(f"{title} — 입찰 마감일시")


def bid_notice_desc(row):
    row = row or {}
    blurb = (row.get("blurb") or row.get("title") or "").strip()
    prefix = ""
    if not row.get("is_open") or (isinstance(row.get("dday"), int) and row["dday"] < 0):
        prefix = "마감된 입찰입니다. "
    elif row.get("dday") == 0:
        prefix = "오늘 마감. "
    elif isinstance(row.get("dday"), int) and 0 < row["dday"] <= 7:
        prefix = f"D-{row['dday']} 마감. "
    return clip_desc(prefix + blurb, lo=40, hi=150)
