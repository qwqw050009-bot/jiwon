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
from enrich import _josa, amount_card, title_gist


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

# 검색어에 시가 붙는 광역시·세종만. 경기·도는 시로 쓰지 않는다.
_REGION_SI = {"서울", "부산", "대구", "인천", "대전", "울산", "세종"}

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
        "소상공인·중소기업, 회원가입 없이 지역·분야로 확인하고, 입찰은 따로 보세요."
    ),
    "privacy": (
        "지원사업 마감판 개인정보처리방침입니다. "
        "회원가입 없이 이용하며, 광고·쿠키 안내와 문의 창구를 이 페이지에서 확인할 수 있습니다."
    ),
    "terms": (
        "지원사업 마감판 이용약관입니다. "
        "정보 제공 범위, 원문 확인 책임, 입찰·지원 문의 한계를 이 페이지에서 확인하고 이용해 주세요."
    ),
    "contact": (
        "지원사업 마감판 문의처입니다. "
        "정보 오류 신고는 받고, 개별 공고의 자격·심사는 소관기관 원문에 직접 문의해야 합니다."
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


def _named(label, n):
    """'지원사업 · 5건'이 아니라 '지원사업 5건'으로 붙인다."""
    nbit = _nbit(n)
    label = (label or "").strip()
    return f"{label} {nbit}".strip() if nbit else label


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


def _region_query(region):
    """검색어에 가까운 지역 표기. 부산시·서울시, 전남은 전남광주 그대로."""
    if region == "전남광주":
        return "전남광주"
    if region in _REGION_SI:
        return f"{region}시"
    return region or ""


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
        head = "오늘마감·이번 주 마감 정부지원사업을 마감일 순으로 둡니다."
    return clip_desc(
        f"{head} 오늘마감 공고를 소상공인·중소기업이 회원가입 없이 지역·분야로 "
        f"좁혀 {year()}년 목록에서 확인하세요."
    )


def home_h1():
    return "오늘 마감되는 정부지원사업부터 봅니다"


def home_lede():
    return "마감일 순으로 무료 정리합니다. 회원가입 없이 지역·분야로 좁혀 보세요."


def urgent_title(items=None):
    c = counts_of(items)
    n = c["n"] or c["week"]
    if c["today"]:
        return with_brand(_join(
            _named("오늘 마감", c["today"]),
            _named("이번 주 지원사업", n),
        ))
    return with_brand(_join("오늘 마감 확인", _named("이번 주 지원사업", n), "D-7"))


def urgent_desc(items=None):
    c = counts_of(items)
    n = c["n"] or c["week"]
    if c["today"]:
        head = f"오늘마감 {c['today']}건, 이번 주 마감 {n}건입니다."
    elif n:
        head = f"오늘마감은 없고 이번 주(D-7) 지원사업 {n}건입니다."
    else:
        head = "오늘마감·이번 주 마감 지원사업만 모았습니다."
    return clip_desc(
        f"{head} 소상공인·중소기업 지원금·보조금을 마감일 순으로 보고, 오늘마감부터 원문으로 가세요."
    )


def urgent_h1():
    return "오늘 마감 · 이번 주 지원사업"


def urgent_lede(items=None):
    c = counts_of(items)
    if c["today"]:
        return f"오늘 마감 {c['today']}건을 먼저 보고, 이번 주 {c['n'] or c['week']}건을 이어서 보세요."
    if c["n"]:
        return f"오늘 마감부터 확인하고, 이번 주 지원사업 {c['n']}건을 마감일 순으로 보세요."
    return "오늘 마감과 이번 주(D-7) 지원사업만 모았습니다."


def all_title(items=None):
    c = counts_of(items)
    return with_brand(_join(_named("정부지원사업 전체", c["n"] or c["open"]), f"마감일 순 {year()}"))


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
    return with_brand(_join(_named("새로 올라온 지원사업", c["n"]), "오늘 등록"))


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

def _region_core(region, n):
    """GSC 쿼리 '{지역} 2026 기업 지원사업 공고'를 앞에 둔다."""
    y = year()
    q = _region_query(region)
    kind = _REGION_KIND.get(region, "do")
    if kind == "nation":
        return _join(_named(f"전국 {y} 기업 지원사업 공고", n), "소재지 제한 없음")
    if kind == "united":
        return _join(_named(f"전남광주 {y} 기업 지원사업 공고", n), "통합특별시")
    if kind == "wide":
        return _join(_named(f"경기 {y} 기업 지원사업 공고", n), "시·군 마감일순")
    if kind == "metro":
        return _join(_named(f"{q} {y} 기업 지원사업 공고", n), "마감일 순")
    if kind == "city":
        return _join(_named(f"{q} {y} 기업 지원사업 공고", n), "시 단위")
    if kind == "island":
        return _join(_named(f"{q} {y} 기업 지원사업 공고", n), "도 단위")
    return _join(_named(f"{q} {y} 기업 지원사업 공고", n), "마감일 순")


def region_title(region, items=None):
    c = counts_of(items)
    return with_brand(_region_core(region, c["n"]))


def region_desc(region, items=None):
    c = counts_of(items)
    n = c["n"]
    kind = _REGION_KIND.get(region, "do")
    q = _region_query(region)
    y = year()
    if kind == "nation":
        head = (
            f"전국 어디서나 신청하는 {y} 기업 지원사업 공고 {n}건입니다. 소재지 제한이 없습니다."
            if n else f"전국 어디서나 신청하는 {y} 기업 지원사업 공고만 모았습니다. 소재지 제한이 없습니다."
        )
    elif kind == "united":
        head = (
            f"전남광주 {y} 기업 지원사업 공고 {n}건입니다. 광주와 전남을 나누지 않습니다."
            if n else f"전남광주 {y} 기업 지원사업 공고입니다. 광주와 전남을 나누지 않습니다."
        )
    else:
        head = (
            f"{q} {y} 기업 지원사업 공고 {n}건입니다. 사업장 소재지 기준입니다."
            if n else f"{q} {y} 기업 지원사업 공고를 마감일 순으로 둡니다."
        )
    clock = _count_clause(c)
    extra = f" {clock}." if clock and clock not in head else ""
    return clip_desc(
        f"{head}{extra} 소상공인·중소기업 보조금을 마감일 순으로 확인하고 원문으로 접수하세요."
    )


def region_h1(region):
    y = year()
    if region == "전국":
        return f"전국 {y} 기업 지원사업 공고"
    if region == "전남광주":
        return f"전남광주 {y} 기업 지원사업 공고"
    return f"{_region_query(region)} {y} 기업 지원사업 공고"


def region_lede(region):
    y = year()
    if region == "전국":
        return f"소재지 제한이 없는 {y} 기업 지원사업 공고를 마감일 순으로 둡니다."
    if region == "전남광주":
        return f"전남광주통합특별시 {y} 기업 지원사업 공고를 마감일 순으로 둡니다."
    return f"{_region_query(region)} {y} 기업 지원사업 공고를 마감일 순으로 둡니다."


# ── 지역×분야 ───────────────────────────────────────────────

def combo_title(region, category, items=None):
    c = counts_of(items)
    y = year()
    if region == "전국":
        chip = _urgency_chip(c)
        if chip == "마감일 순":
            chip = "소재지 제한 없음"
        return with_brand(_join(
            _named(f"전국 {category} 지원사업 공고 {y}", c["n"]), chip,
        ))
    q = _region_query(region)
    return with_brand(_join(
        _named(f"{q} {category} 지원사업 공고 {y}", c["n"]),
        _urgency_chip(c),
    ))


def combo_desc(region, category, cat=None, items=None):
    c = counts_of(items)
    extra = ((cat or {}).get("desc") or "").strip()
    y = year()
    if region == "전국":
        if c["n"]:
            head = (
                f"전국에서 신청하는 {category} 지원사업 공고 {c['n']}건입니다. "
                "사업장 소재지 제한이 없습니다."
            )
        else:
            head = f"전국에서 신청하는 {category} 지원사업 공고만 모았습니다. 소재지 제한이 없습니다."
    else:
        q = _region_query(region)
        if c["n"]:
            head = f"{q} {category} 지원사업 공고 {c['n']}건입니다."
        else:
            head = f"{q} {category} 지원사업 공고를 마감일 순으로 둡니다."
    clock = _count_clause(c)
    mid = f" {clock}." if clock and clock not in head else ""
    note = f" {extra}." if extra and extra not in head else ""
    if region == "전국":
        cta = f" {y}년 전국 단위만 보고 대상·소관기관을 확인한 뒤 원문으로 가세요."
    else:
        cta = " 오늘·이번 주 마감을 확인한 뒤 대상·소관기관을 보고 원문으로 가세요."
    return clip_desc(f"{head}{mid}{cta}{note}")


def combo_h1(region, category):
    if region == "전국":
        return f"전국 {category} 지원사업 공고"
    return f"{_region_query(region)} {category} 지원사업 공고"


def combo_lede(region, category):
    if region == "전국":
        return f"소재지 제한이 없는 {category} 공고를 마감일 순으로 둡니다."
    return f"{_region_query(region)} {category} 분야 공고를 마감일 순으로 둡니다."


# ── 시군구 ──────────────────────────────────────────────────

def district_title(sido, district, items=None):
    c = counts_of(items)
    return with_brand(_join(
        _named(f"{district} {year()} 기업 지원사업 공고", c["n"]),
        _region_label(sido),
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
    return f"{district} {year()} 기업 지원사업 공고"


def district_lede(sido, district):
    return f"{_region_label(sido)} {district} 관련 공고를 마감일 순으로 둡니다."


def district_combo_title(sido, district, category, items=None):
    c = counts_of(items)
    return with_brand(_join(
        _named(f"{district} {category} 지원사업", c["n"]), _urgency_chip(c),
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

def _notice_closed(row):
    if row.get("period_type") == "always":
        return False
    if row.get("is_closed"):
        return True
    return isinstance(row.get("dday"), int) and row["dday"] < 0


def _notice_who(row):
    raw = (row.get("target") or "").strip()
    who = (raw.splitlines() or [""])[0].strip()
    who = who.lstrip("•·*- ").strip()
    if len(who) > 40:
        who = who[:39].rstrip(" ·,/") + "…"
    return who


def notice_title(row):
    """
    공고 원제(롱테일 검색어)를 살린다. 약한 접미사(마감일·신청자격,
    마감된 공고)는 원제와 같아 보이는 공식 사이트 스니펫만 만든다.
    오늘·이번 주(D≤7)만 앞에 급함을 둔다.
    """
    row = row or {}
    title = (row.get("title") or "지원사업 공고").strip()
    if row.get("period_type") == "always":
        return with_brand(f"{title} · 상시 접수")
    d = row.get("dday")
    if d == 0:
        return with_brand(f"오늘 마감 · {title}")
    if isinstance(d, int) and 0 < d <= 7:
        return with_brand(f"이번 주 마감 D-{d} · {title}")
    return with_brand(title)


def notice_desc(row, limit=150):
    """
    원제와 다른 스니펫. 마감·대상·지역·요지를 앞에 두고 원문 CTA로 끝낸다.
    깨진 조사 요약은 쓰지 않는다.
    """
    row = row or {}
    closed = _notice_closed(row)
    who = _notice_who(row)
    region = (row.get("region") or "").strip()
    org = (row.get("org") or "").strip()
    gist = title_gist(row.get("title") or "") or (row.get("category") or "").strip()
    end = (row.get("apply_end") or "").strip()
    amt = amount_card(row) or ""
    d = row.get("dday")

    if closed:
        lead = f"접수 마감 {end}." if end else "접수 기간이 끝난 공고입니다."
    elif row.get("period_type") == "always":
        raw = (row.get("period_raw") or "상시 접수").strip()
        lead = f"상시 접수('{raw}'). 예산이 끝나면 닫힙니다."
    elif d == 0:
        lead = "오늘 마감."
    elif isinstance(d, int) and 0 < d <= 7:
        lead = f"이번 주 마감 D-{d}" + (f"({end})." if end else ".")
    elif end:
        lead = f"마감일 {end}."
    else:
        lead = ""

    mid = []
    if region == "전국" and who:
        mid.append(f"소재지 제한 없이 신청할 수 있는 {who} 대상")
    elif region == "전국":
        mid.append("소재지 제한 없이 신청할 수 있는 공고")
    elif region and who:
        mid.append(f"{_region_query(region)} 사업장 기준 {who} 대상")
    elif region:
        mid.append(f"{_region_query(region)} 사업장 기준")
    elif who:
        mid.append(f"{who} 대상")
    if gist and not (gist.endswith("…") and len(who) >= 16):
        mid.append(gist)
    if org and org not in " ".join(mid):
        mid.append(f"{org} 소관")
    if amt:
        mid.append(f"본문 규모 {amt}")
    mid_s = ". ".join(p.strip(" .") for p in mid if p)
    if mid_s and not mid_s.endswith("."):
        mid_s += "."

    leftover = ((row.get("ai") or {}).get("summary") or "").strip()
    if leftover and ("이(가)" in leftover or "을(를)" in leftover):
        leftover = ""
    if leftover and leftover not in (mid_s or "") and len(mid_s) < 70:
        cut = leftover.find("다.")
        extra = leftover[: cut + 2] if cut >= 12 else leftover[:80]
        if extra and extra not in (mid_s or ""):
            mid_s = f"{mid_s} {extra}".strip() if mid_s else extra

    if closed:
        cta = "신청자격·지원내용을 보고, 비슷한 공고는 지역·분야 목록에서 확인하세요."
    else:
        cta = "신청자격·마감일을 확인하고 원문으로 접수하세요."
    return clip_desc(" ".join(p for p in (lead, mid_s, cta) if p), lo=70, hi=limit)


# ── 가이드·고정·캘린더 ───────────────────────────────────────

def guide_hub_title():
    return with_brand(f"정부지원사업 가이드 · 신청 자격·서류 {year()}")


def guide_hub_desc():
    return clip_desc(
        "신청 자격, 서류, 바우처·선정 차이, 소상공인 지원금 순서까지. "
        "공고가 바뀌어도 남는 기본기를 보고, 오늘 마감 목록과 같이 확인하세요."
    )


def guide_title(h1):
    return with_brand(h1)


def calendar_title():
    return with_brand("지원사업 마감일 캘린더 구독 · 무료 ICS")


def calendar_desc():
    return clip_desc(
        "관심 지역·분야 마감일을 내 캘린더에 자동으로 받습니다. "
        "회원가입 없이 ICS로 구독하고, 마감 하루 전 알림을 확인하세요. "
        "상시 접수는 날짜가 없어 캘린더에 넣지 않습니다."
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
    return with_brand(_join(_named("이번 주 마감 입찰", n), "나라장터 D-7"))


def bid_urgent_desc(n=0):
    if n:
        head = f"나라장터에서 7일 안에 마감되는 입찰 {n}건입니다."
    else:
        head = "나라장터에서 7일 안에 마감되는 입찰만 모았습니다."
    return clip_desc(
        f"{head} 물품·용역·공사·외자 마감일시를 확인하고 원문으로 가세요. "
        "지원사업 마감임박은 홈에서 따로 봅니다."
    )


def bid_kind_title(name, n=0):
    return with_brand(_join(_named(f"{name} 입찰공고", n), "나라장터 마감일시"))


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
    return with_brand(_join(_named(f"{region} 참가지역 입찰", n), "나라장터"))


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
