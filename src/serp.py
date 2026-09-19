# -*- coding: utf-8 -*-
"""
검색결과(SERP)용 title·meta description.

목록 소개문(intros)과 분리한다. 페이지 종류마다 앞머리를 다르게 두고,
건수는 화면에 실제로 올라온 목록에서만 센다. 없는 숫자를 만들지 않는다.

제목은 앞 ~32자에 급함(오늘마감·이번주마감·마감임박)과 혜택 키워드
(지원금·모집·신청)를 두고, 공고 원제는 짧게 줄인다. 브랜드 접미사는
항상 `| 지원사업 마감판`.
"""
from datetime import date
import re

import config
from enrich import _josa, amount_card


BRAND = config.SITE["name"]
BRAND_SUFFIX = f"| {BRAND}"

# 모바일 SERP에서 잘리기 전에 보여야 하는 앞머리.
FIRST_CLAUSE_MAX = 32
NOTICE_CORE_MAX = 26

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

# 조합 제목 뒷말. 급함이 없을 때 분야 8종이 같은 접미사로 안 보이게.
_CAT_CHIP = {
    "금융": "융자·보증",
    "기술": "R&D·특허",
    "인력": "인건비·채용",
    "수출": "해외진출",
    "내수": "판로·마케팅",
    "창업": "예비·초기",
    "경영": "컨설팅·시설",
    "기타": "기타 분야",
}

# 지역 설명 둘째 문장. 행정 구조만 말하고 공고 건수·금액을 지어내지 않는다.
_REGION_OPEN = {
    "서울": "시와 자치구 공고가 한 목록이고, 구청 소관이면 그 구 사업장인 경우가 많습니다",
    "부산": "광역시 사업장 기준이며 구·군 공고가 섞여 있습니다",
    "대구": "광역시와 구 공고가 함께 있고, 구청 소관이면 그 구로 좁혀집니다",
    "인천": "시·구·군 공고가 함께 올라오며 짧은 대상 지역도 원문에 세부 요건이 있습니다",
    "대전": "광역시와 구 공고가 한 목록이며 소관기관으로 시 전체와 구 단위를 가릅니다",
    "울산": "시와 구·군 공고가 섞여 있어 기관명과 대상 지역을 함께 봅니다",
    "세종": "시 단위 공고가 중심이고, 소재지 제한이 없으면 전국 목록에 있습니다",
    "경기": "도와 시·군 공고가 한 목록에 모입니다",
    "강원": "도와 시·군 공고가 섞여 있고, 시·군 소관이면 그 지역 사업장 요건이 붙습니다",
    "충북": "도와 시·군 공고가 한 목록이며 특정 시·군으로 적혀 있는지 원문에서 봅니다",
    "충남": "도와 시·군 공고가 함께 올라오며 소관기관이 범위를 나눕니다",
    "전북": "도와 시·군 공고가 함께 있고 소관기관과 대상 지역이 일치하는지만 보면 됩니다",
    "전남광주": "광주와 전남을 나누지 않는 통합특별시 목록입니다",
    "경북": "도와 시·군 공고가 섞여 있고 짧은 대상 지역도 원문에 세부 조건이 있습니다",
    "경남": "도와 시·군 공고가 한 목록이며 시·군 소관이면 해당 지역 사업장 기준입니다",
    "제주": "도 단위 공고가 중심이며 소재지 제한이 없으면 전국 목록에서 봅니다",
    "전국": "사업장 소재지 제한이 없습니다",
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
    "pricing": (
        "지원사업 마감판 요금제입니다. 지금은 무료 이메일 알림만 받으며, 베이직·프로는 사업자 등록 후 오픈 예정입니다."
    ),
}

_TODAY_DEADLINE_RE = re.compile(r"오늘\s*마감")
_YEAR_HEAD_RE = re.compile(r"^(20\d{2})\s*년?\s*")
_NOTICE_TAIL_RE = re.compile(
    r"\s*(?:참여(?:기업|기관)\s*)?모집\s*공고$|"
    r"\s*참여(?:기업|기관)\s*모집$|"
    r"\s*모집공고$|"
    r"\s*공고$"
)
_GENERIC_TAIL_RE = re.compile(
    r"(?:\s+with\s+\S.*$)|"
    r"(?:\s*외부\s*지원\s*프로그램$)|"
    r"(?:\s*지원\s*프로그램$)|"
    r"(?:\s*프로그램$)",
    re.I,
)

# 가입 없이 목록을 보고 원문으로 가는 사이트 공통 CTA. 지원금이 공짜라는 뜻이 아니다.
_APPLY_CTA = "가입 없이 원문을 열고 바로 신청하세요."
_LIST_CTA = "소상공인·중소기업이 가입 없이 마감일순으로 보고 원문에서 바로 신청하세요."


def year(today=None):
    return (today or date.today()).year


def with_brand(core):
    core = re.sub(r"\s+", " ", (core or "").strip(" ·|-"))
    if not core:
        return BRAND
    if core.endswith(BRAND) or core.endswith(f"| {BRAND}"):
        return core
    return f"{core} | {BRAND}"


def core_of(title):
    """브랜드 접미사를 뗀 제목 본체."""
    s = (title or "").strip()
    if s.endswith(f" | {BRAND}"):
        return s[: -(len(BRAND) + 3)].rstrip(" ·|-")
    return s


def first_clause(title):
    """` · ` 앞머리. 모바일에서 잘리기 전에 보이는 구간."""
    core = core_of(title)
    if " · " in core:
        return core.split(" · ", 1)[0]
    return core[:FIRST_CLAUSE_MAX]


def today_deadline_hits(text):
    """'오늘마감'과 '오늘 마감'을 같은 급함 토큰으로 센다."""
    return len(_TODAY_DEADLINE_RE.findall(text or ""))


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
        bits.append(f"오늘마감 {c['today']}건")
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


def _snippet_clock(c, head=""):
    """오늘·이번 주·상시만 덧붙인다. 이미 쓴 건수('접수 중 N건')는 반복하지 않는다."""
    clock = _count_clause(c)
    if not clock or clock in (head or ""):
        return ""
    if clock.startswith("접수 중") or clock.startswith("지금 "):
        return ""
    return f" {clock}."


def _urgency_lead(c):
    """제목 앞머리. 오늘마감 → 마감임박 → 건수. 0건은 만들지 않는다."""
    c = c or {}
    if c.get("today"):
        return f"오늘마감 {c['today']}건"
    if c.get("week"):
        return f"마감임박 {c['week']}건"
    if c.get("n"):
        return f"{c['n']}건"
    return ""


def _lead_covers_n(c, lead):
    """앞머리 건수가 목록 전체 건수와 같으면 뒤에 같은 숫자를 반복하지 않는다."""
    n = int((c or {}).get("n") or 0)
    return bool(lead) and n > 0 and lead.endswith(f"{n}건")


def _urgency_chip(c):
    """조합 페이지 제목 뒷말. 같은 틀이 수백 개 반복되지 않게 시계열로 가른다."""
    if c["today"]:
        return f"오늘마감 {c['today']}건"
    if c["week"]:
        return f"마감임박 {c['week']}건"
    if c["always"]:
        return f"상시 {_nbit(c['always'])}".strip()
    return "마감일순"


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


def _cat_chip(name):
    return _CAT_CHIP.get(name) or (name or "지원사업")


def _cat_nature(name):
    """설명용 분야 성격. '~입니다/이며'에 붙는 명사구. 끝의 '공고'는 뗀다."""
    raw = _CAT_OPEN.get(name) or f"{name} 지원 공고"
    s = re.sub(r"\s*공고$", "", raw).strip()
    if s and not s.endswith("지원"):
        s = f"{s} 지원"
    return s


def _region_open(region):
    return _REGION_OPEN.get(region) or "사업장 소재지 기준입니다"


def _region_cta(kind):
    if kind == "nation":
        return "시·도 제한 없이 마감일순으로 보고 바로 신청하세요."
    if kind == "united":
        return "광주·전남을 나누지 않고 가입 없이 마감일순으로 확인하세요."
    if kind == "metro":
        return "구·군 요건은 소관기관과 맞춘 뒤 가입 없이 바로 신청하세요."
    if kind == "wide":
        return "시·군 사업장 요건을 본 뒤 가입 없이 바로 신청하세요."
    if kind == "city":
        return "시 단위 공고를 마감일순으로 보고 바로 신청하세요."
    if kind == "island":
        return "도 단위 공고를 마감일순으로 보고 바로 신청하세요."
    return "사업장 소재지를 맞춘 뒤 가입 없이 바로 신청하세요."


def _region_query_phrase(region, y=None):
    """GSC 쿼리 '{지역} 2026 기업 지원사업 공고'."""
    y = y or year()
    if region == "전국":
        return f"전국 {y} 기업 지원사업 공고"
    if region == "전남광주":
        return f"전남광주 {y} 기업 지원사업 공고"
    if region == "경기":
        return f"경기 {y} 기업 지원사업 공고"
    return f"{_region_query(region)} {y} 기업 지원사업 공고"


def _with_year(core, today=None):
    y = str(year(today))
    core = (core or "").strip()
    if not core:
        return y
    if y in core:
        return core
    return f"{core} {y}"


# ── 홈·긴급·전체 ─────────────────────────────────────────────

def home_title(items=None, today=None):
    """오늘마감 쿼리 + 소상공인 지원금 신청. '오늘 마감'을 한 번 더 쓰지 않는다."""
    c = counts_of(items)
    y = year(today)
    if c["today"]:
        head = f"오늘마감 {c['today']}건"
    else:
        head = "오늘마감"
    return with_brand(_join(head, f"마감일순 소상공인 지원금 신청 {y}"))


def home_desc(items=None):
    c = counts_of(items)
    clock = _count_clause(c)
    if c["today"]:
        head = f"오늘마감 {c['today']}건을 마감일순으로 봅니다."
        extra = []
        if c["week"] and c["week"] != c["today"]:
            extra.append(f"이번 주 마감 {c['week']}건")
        if c["always"]:
            extra.append(f"상시 접수 {c['always']}건")
        if extra:
            head = f"{head.rstrip('.')} ({', '.join(extra)})."
    elif clock:
        head = f"오늘마감은 없고 {clock}."
    else:
        head = "오늘마감 지원사업을 마감일순으로 둡니다."
    return clip_desc(
        f"{head} 소상공인 지원금 신청을 가입 없이 지역·분야로 "
        f"좁혀 {year()}년 원문에서 바로 신청하세요."
    )


def home_h1():
    return "오늘마감되는 소상공인·중소기업 지원금을 마감일 순으로 봅니다"


def home_lede():
    return "회원가입 없이 오늘마감부터 지역·분야로 좁혀 원문에서 바로 신청하세요."


def urgent_title(items=None):
    c = counts_of(items)
    n = c["n"] or c["week"]
    if c["today"]:
        return with_brand(_join(
            _named("오늘마감", c["today"]),
            _named("이번주 마감임박", n),
            "마감일순",
        ))
    return with_brand(_join("오늘마감 확인", _named("이번주 마감임박", n), "마감일순"))


def urgent_desc(items=None):
    c = counts_of(items)
    n = c["n"] or c["week"]
    if c["today"]:
        head = (
            f"오늘마감 {c['today']}건부터 이번주 마감임박 {n}건을 "
            "마감일순으로 모았습니다."
        )
    elif n:
        head = f"오늘마감은 없습니다. 이번주 마감임박(D-7) 지원사업 {n}건입니다."
    else:
        head = "오늘마감과 이번주 마감임박 지원사업만 모았습니다."
    return clip_desc(f"{head} {_LIST_CTA}")


def urgent_h1():
    return "오늘마감부터 이번 주 마감임박 지원사업"


def urgent_lede(items=None):
    c = counts_of(items)
    if c["today"]:
        return f"오늘마감 {c['today']}건을 먼저 보고, 이번 주 {c['n'] or c['week']}건을 이어서 보세요."
    if c["n"]:
        return f"오늘마감부터 확인하고, 이번 주 지원사업 {c['n']}건을 마감일 순으로 보세요."
    return "오늘마감과 이번 주(D-7) 지원사업만 모았습니다."


def all_title(items=None):
    c = counts_of(items)
    lead = _urgency_lead(c)
    body = _named("정부지원사업 전체", 0 if _lead_covers_n(c, lead) else (c["n"] or c["open"]))
    return with_brand(_join(lead if lead != body else "", body, f"마감일순 {year()}"))


def all_desc(items=None):
    c = counts_of(items)
    n = c["n"] or c["open"]
    clock = _count_clause(c)
    if n:
        head = f"접수 중·최근 공고 {n}건을 한 목록에서 마감일순으로 봅니다."
    else:
        head = "정부지원사업 전체를 마감일순으로 봅니다."
    extra = f" {clock}." if clock and clock not in head else ""
    return clip_desc(
        f"{head}{extra} 소상공인·중소기업이 가입 없이 지역·분야로 바로 신청하세요."
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
    return clip_desc(f"{head} {_LIST_CTA}")


def new_h1():
    return "새로 올라온 지원사업"


def new_lede(items=None):
    c = counts_of(items)
    if c["n"]:
        return f"최근 새로 등록된 지원사업 {c['n']}건입니다."
    return "최근 새로 등록된 지원사업입니다."


# ── 허브 ────────────────────────────────────────────────────

def category_hub_title():
    return with_brand(f"분야별 정부지원사업 8종 · 마감일순 {year()}")


def category_hub_desc(n=0):
    nbit = _nbit(n)
    head = f"지금 {nbit}입니다. " if nbit else ""
    return clip_desc(
        f"금융·기술·인력·수출·내수·창업·경영·기타 8종. {head}"
        "소상공인·중소기업이 마감일순으로 분야를 골라 바로 신청하세요."
    )


def category_hub_h1():
    return "분야별 정부지원사업, 마감일 순"


def category_hub_lede():
    return "금융부터 창업·경영까지 8종. 마감이 가까운 순입니다."


def region_hub_title():
    return with_brand(f"지역별 정부지원사업 · 사업장 소재지 17곳 · 마감일순")


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
    return "지역별 정부지원사업, 마감일 순"


def region_hub_lede():
    return "사업장 소재지 기준, 마감일 순. 전남광주는 통합 단위입니다."


# ── 분야 ────────────────────────────────────────────────────

def category_title(name, items=None):
    lead = _cat_lead(name)
    hook = _cat_hook(name)
    c = counts_of(items)
    urg = _urgency_lead(c)
    body = lead if _lead_covers_n(c, urg) else _named(lead, c["n"])
    if not c["n"]:
        body = f"{lead} 마감일"
        urg = ""
    return with_brand(_join(urg, body, hook))


def category_desc(name, cat=None, items=None):
    c = counts_of(items)
    extra = ((cat or {}).get("desc") or "").strip()
    open_s = _CAT_OPEN.get(name) or f"{name} 지원 공고"
    clock = _count_clause(c)
    if c["n"]:
        head = f"{open_s} {c['n']}건입니다."
    else:
        head = f"{open_s}를 마감일순으로 둡니다."
    mid = f" {clock}." if clock and clock not in head else ""
    tail = f" {extra}." if extra and extra not in head else ""
    return clip_desc(
        f"{head}{mid} 소상공인·중소기업이 회원가입 없이 지역별로 "
        f"오늘마감·이번 주 마감을 확인하고 원문에서 바로 신청하세요.{tail}"
    )


def category_h1(name):
    if name == "금융":
        return "금융 지원금·융자, 마감일 순"
    if name == "기타":
        return "기타 지원사업, 마감일 순"
    return f"{name} 지원금·지원사업, 마감일 순"


def _lede_clock(items):
    """레데 끝에 붙는 오늘/이번 주 건수. 없는 숫자를 만들지 않는다."""
    c = counts_of(items)
    if c["today"]:
        return f" 오늘 마감 {c['today']}건입니다."
    if c["week"]:
        return f" 이번 주 마감 {c['week']}건입니다."
    if c["n"]:
        return f" 지금 {c['n']}건입니다."
    return ""


def category_lede(name, cat=None, items=None):
    extra = ((cat or {}).get("desc") or f"{name} 지원").strip()
    return f"{extra}. 마감이 가까운 순입니다.{_lede_clock(items)}"


# ── 지역 ────────────────────────────────────────────────────

def _region_hook(kind, c=None):
    """
    지역 제목 뒷말. 오늘마감은 실제 오늘 마감 건이 있을 때만.
    홈·마감임박이 오늘마감 쿼리를 가져가므로, 없는 급함을 붙이지 않는다.
    """
    c = c or {}
    if c.get("today"):
        return f"오늘마감 {c['today']}건"
    if c.get("week"):
        return f"마감임박 {c['week']}건"
    if c.get("always"):
        return f"상시 {_nbit(c['always'])}".strip()
    if kind == "nation":
        return "소재지 제한 없음"
    if kind == "united":
        return "통합특별시"
    if kind == "city":
        return "시 단위"
    if kind == "island":
        return "제주특별자치도"
    if kind == "wide":
        return "시·군 공고"
    if kind == "metro":
        return "광역시 소재지"
    return "도 단위"


def _region_core(region, n, c=None):
    """앞머리에 오늘마감/마감임박/건수, 이어서 GSC 쿼리 문구."""
    c = c or {}
    phrase = _region_query_phrase(region)
    lead = _urgency_lead(c)
    if not lead:
        kind = _REGION_KIND.get(region, "do")
        return _join(phrase, _region_hook(kind, c))
    body = phrase if _lead_covers_n(c, lead) else _named(phrase, n)
    return _join(lead, body, "마감일순")


def region_title(region, items=None):
    c = counts_of(items)
    return with_brand(_region_core(region, c["n"], c))


def region_desc(region, items=None):
    c = counts_of(items)
    n = c["n"]
    kind = _REGION_KIND.get(region, "do")
    q = _region_query(region)
    y = year()
    open_s = _region_open(region)
    clock = _count_clause(c, include_always=False)
    if kind == "nation":
        head = (
            f"전국 어디서나 신청하는 {y} 기업 지원사업 공고 {n}건입니다."
            if n else f"전국 어디서나 신청하는 {y} 기업 지원사업 공고만 모았습니다."
        )
    elif kind == "united":
        head = (
            f"전남광주 {y} 기업 지원사업 공고 {n}건입니다."
            if n else f"전남광주 {y} 기업 지원사업 공고입니다."
        )
    else:
        head = (
            f"{q} {y} 기업 지원사업 공고 {n}건입니다."
            if n else f"{q} {y} 기업 지원사업 공고를 마감일순으로 둡니다."
        )
    if clock and clock not in head:
        head = head.replace("입니다.", f", {clock}입니다.", 1)
        if not head.endswith("입니다.") and clock not in head:
            head = f"{head} {clock}."
    return clip_desc(f"{head} {open_s}. {_region_cta(kind)}")


def region_h1(region):
    return f"{_region_query_phrase(region).replace(' 공고', '')}, 마감일 순"


def region_lede(region, items=None):
    y = year()
    open_s = _region_open(region)
    clock = _lede_clock(items)
    if region == "전국":
        head = f"소재지 제한이 없는 {y} 기업 지원사업 공고를 마감일 순으로 둡니다."
    elif region == "전남광주":
        head = f"전남광주통합특별시 {y} 기업 지원사업 공고를 마감일 순으로 둡니다."
    else:
        head = f"{_region_query(region)} {y} 기업 지원사업 공고를 마감일 순으로 둡니다."
    return f"{head} {open_s}.{clock}".replace("..", ".")


# ── 지역×분야 ───────────────────────────────────────────────

def combo_title(region, category, items=None):
    c = counts_of(items)
    y = year()
    lead = _urgency_lead(c)
    if region == "전국":
        phrase = f"전국 {category} 지원사업 공고 {y}"
    else:
        phrase = f"{_region_query(region)} {category} 지원사업 공고 {y}"
    body = phrase if _lead_covers_n(c, lead) else _named(phrase, c["n"])
    chip = ""
    if not c.get("today") and not c.get("week"):
        chip = _cat_chip(category)
        if region == "전국":
            chip = f"{chip} · 소재지 제한 없음"
    return with_brand(_join(lead, body, chip))


def combo_desc(region, category, cat=None, items=None):
    c = counts_of(items)
    nature = _cat_nature(category)
    y = year()
    kind = _REGION_KIND.get(region, "do")
    clock = _count_clause(c, include_always=False)
    if region == "전국":
        if c["n"]:
            head = f"전국에서 신청하는 {category} 지원사업 공고 {c['n']}건입니다."
        else:
            head = f"전국에서 신청하는 {category} 지원사업 공고만 모았습니다."
        place = f"{nature}이며 소재지 제한이 없습니다."
    else:
        q = _region_query(region)
        if c["n"]:
            head = f"{q} {category} 지원사업 공고 {c['n']}건입니다."
        else:
            head = f"{q} {category} 지원사업 공고를 마감일순으로 둡니다."
        place = f"{nature}입니다. {_region_open(region)}."
    if clock and clock not in head:
        head = head.replace("입니다.", f", {clock}입니다.", 1)
    if region == "전국":
        cta = f"{y}년 전국 단위만 보고 가입 없이 바로 신청하세요."
    else:
        cta = _region_cta(kind)
    return clip_desc(f"{head} {place} {cta}".strip())


def combo_h1(region, category):
    if region == "전국":
        return f"전국 {category} 지원사업, 마감일 순"
    return f"{_region_query(region)} {category} 지원사업, 마감일 순"


def combo_lede(region, category, items=None):
    clock = _lede_clock(items)
    nature = _cat_nature(category)
    if region == "전국":
        return f"소재지 제한이 없는 {category} 공고를 마감일 순으로 둡니다. {nature}입니다.{clock}"
    return (
        f"{_region_query(region)} {category} 분야 공고를 마감일 순으로 둡니다. "
        f"{nature}입니다.{clock}"
    )


# ── 시군구 ──────────────────────────────────────────────────

def district_title(sido, district, items=None):
    c = counts_of(items)
    lead = _urgency_lead(c)
    phrase = f"{district} {year()} 기업 지원사업 공고"
    body = phrase if _lead_covers_n(c, lead) else _named(phrase, c["n"])
    return with_brand(_join(lead, body, _region_label(sido)))


def district_desc(sido, district, items=None):
    c = counts_of(items)
    label = _region_label(sido)
    y = year()
    clock = _count_clause(c, include_always=False)
    if c["n"]:
        head = f"{district} {y} 기업 지원사업 공고 {c['n']}건입니다."
    else:
        head = f"{district} {y} 기업 지원사업 공고만 모았습니다."
    if clock and clock not in head:
        head = head.replace("입니다.", f", {clock}입니다.", 1)
    place = f"{label} 목록에서 이 시군구 해시태그만 골랐습니다. 시·도 전체가 아닙니다."
    return clip_desc(f"{head} {place} {_APPLY_CTA}")


def district_h1(sido, district):
    return f"{district} {year()} 기업 지원사업, 마감일 순"


def district_lede(sido, district, items=None):
    clock = _lede_clock(items)
    return (
        f"{_region_label(sido)} {district} 관련 공고를 마감일 순으로 둡니다. "
        f"시·도 전체가 아니라 이 시군구 해시태그만 골랐습니다.{clock}"
    )


def district_combo_title(sido, district, category, items=None):
    c = counts_of(items)
    lead = _urgency_lead(c)
    phrase = f"{district} {category} 지원사업"
    body = phrase if _lead_covers_n(c, lead) else _named(phrase, c["n"])
    chip = "" if lead else _cat_chip(category)
    return with_brand(_join(lead, body, chip))


def district_combo_desc(sido, district, category, cat=None, items=None):
    c = counts_of(items)
    label = _region_label(sido)
    nature = _cat_nature(category)
    clock = _count_clause(c, include_always=False)
    if c["n"]:
        head = f"{district} {category} 지원사업 {c['n']}건입니다."
    else:
        head = f"{district} {category} 지원사업만 모았습니다."
    if clock and clock not in head:
        head = head.replace("입니다.", f", {clock}입니다.", 1)
    place = f"{nature}입니다. {label} 목록에서 이 시군구만 골랐습니다."
    return clip_desc(f"{head} {place} {_APPLY_CTA}")


def district_combo_h1(sido, district, category):
    return f"{district} {category} 지원사업, 마감일 순"


def district_combo_lede(sido, district, category, items=None):
    clock = _lede_clock(items)
    nature = _cat_nature(category)
    return (
        f"{_region_label(sido)} {district} {category} 분야 공고를 마감일 순으로 둡니다. "
        f"{nature}입니다.{clock}"
    )


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


def _benefit_word(row):
    """제목·본문에 있는 혜택만. 금액이 확인된 경우에만 지원금."""
    title = (row or {}).get("title") or ""
    if "지원금" in title:
        return "지원금"
    if "보조금" in title:
        return "보조금"
    if amount_card(row or {}):
        return "지원금"
    if "모집" in title:
        return "모집"
    if "신청" in title:
        return "신청"
    return "신청"


def _strip_notice_noise(title):
    s = _YEAR_HEAD_RE.sub("", (title or "").strip())
    prev = None
    while prev != s:
        prev = s
        s = _NOTICE_TAIL_RE.sub("", s).strip(" ·,/-")
    s = _GENERIC_TAIL_RE.sub("", s).strip(" ·,/-")
    return re.sub(r"\s+", " ", s).strip()


def _clip_core(s, budget):
    s = re.sub(r"\s+", " ", s or "").strip(" ·,/-")
    if not s or len(s) <= budget:
        return s
    trimmed = re.sub(r"\s*\([^)]*\)\s*$", "", s).strip()
    if trimmed and len(trimmed) <= budget:
        return trimmed
    cut = max(s.rfind(" ", 0, budget + 1), s.rfind("·", 0, budget + 1),
              s.rfind("/", 0, budget + 1))
    if cut >= 6:
        return s[:cut].rstrip(" ·,/-")
    return s[:budget].rstrip(" ·,/-")


def short_notice_core(title, budget=NOTICE_CORE_MAX):
    """원제에서 연도·공고 꼬리·장황한 수식을 걷어 짧은 핵심만 남긴다."""
    raw = (title or "").strip() or "지원사업"
    s = _strip_notice_noise(raw)
    parens = re.findall(r"\(([^)]+)\)", s)
    if parens:
        bit = parens[0].split(",")[0].strip()
        if 2 <= len(bit) <= 14 and not bit.isdigit():
            rest = re.sub(r"\([^)]+\)", "", s)
            rest = re.sub(r"\s+", " ", rest).strip(" ·,/-")
            rest = _clip_core(rest, max(6, budget - len(bit) - 1))
            if rest and rest not in bit:
                s = f"{bit} {rest}"
            else:
                s = bit
    s = _clip_core(s, budget)
    return s or _clip_core(raw, budget)


def _notice_lead(row):
    d = row.get("dday")
    benefit = _benefit_word(row)
    if row.get("period_type") == "always":
        return f"상시접수 {benefit}"
    if d == 0:
        return f"오늘마감 {benefit}"
    if isinstance(d, int) and 0 < d <= 7:
        return f"이번주마감 D-{d}"
    return benefit


def notice_title(row):
    """
    앞머리에 오늘마감/이번주마감/혜택, 이어서 짧은 원제와 연도.
    원제 전체를 그대로 넣지 않는다. 닫힌 공고에 '마감된 공고'를 붙이지 않는다.
    """
    row = row or {}
    title = (row.get("title") or "지원사업 공고").strip()
    lead = _notice_lead(row)
    core = short_notice_core(title)
    if lead.split()[-1] in core:
        pass
    elif any(w in core for w in ("지원금", "보조금", "모집", "신청")):
        pass
    elif lead not in ("신청", "모집", "지원금", "보조금"):
        if _benefit_word(row) not in core and _benefit_word(row) not in lead:
            core = f"{core} {_benefit_word(row)}".strip()
    return with_brand(_join(lead, _with_year(core)))


def _deadline_lead(row, closed, d):
    """스니펫의 마감 조각. 제목을 다시 쓰지 않는다."""
    end = (row.get("apply_end") or "").strip()
    if closed:
        return f"접수 마감 {end}." if end else "접수 기간이 끝난 공고입니다."
    if row.get("period_type") == "always":
        raw = (row.get("period_raw") or "상시 접수").strip()
        if raw and raw != "상시 접수":
            return f"상시 접수({raw}). 예산이 끝나면 닫힙니다."
        return "상시 접수. 예산이 끝나면 닫힙니다."
    if d == 0:
        return f"오늘마감({end})." if end else "오늘마감."
    if isinstance(d, int) and 0 < d <= 7:
        return f"이번 주 마감 D-{d}({end})." if end else f"이번 주 마감 D-{d}."
    if end:
        return f"마감일 {end}."
    return ""


def notice_desc(row, limit=150):
    """
    대상·금액(본문에서 뽑힌 것만)·마감을 앞에 두고, 가입 없이 CTA.
    없는 금액을 만들지 않는다. 깨진 조사 요약은 쓰지 않는다.
    """
    row = row or {}
    closed = _notice_closed(row)
    who = _notice_who(row)
    region = (row.get("region") or "").strip()
    org = (row.get("org") or "").strip()
    amt = amount_card(row) or ""
    d = row.get("dday")
    deadline = _deadline_lead(row, closed, d)

    parts = []
    if who:
        if who.startswith("대상"):
            parts.append(who if who.endswith(".") else f"{who}.")
        else:
            parts.append(f"대상 {who}.")
    if amt:
        parts.append(f"본문 기준 {amt}.")
    if deadline:
        parts.append(deadline if deadline.endswith(".") else deadline + ".")
    if region == "전국":
        parts.append("소재지 제한 없이 신청할 수 있습니다.")
    elif region:
        parts.append(f"{_region_query(region)} 사업장 기준.")
    if org and org not in " ".join(parts):
        parts.append(f"{org} 소관.")

    leftover = ((row.get("ai") or {}).get("summary") or "").strip()
    if leftover and ("이(가)" in leftover or "을(를)" in leftover):
        leftover = ""
    body = " ".join(parts)
    if leftover and leftover not in body and len(body) < 55 and not who:
        cut = leftover.find("다.")
        extra = leftover[: cut + 2] if cut >= 12 else leftover[:80]
        if extra and extra not in body:
            parts.append(extra)

    if closed:
        parts.append("비슷한 공고는 지역·분야 목록에서 확인하세요.")
    else:
        parts.append("무료 열람, " + _APPLY_CTA)
    return clip_desc(" ".join(p for p in parts if p), lo=70, hi=limit)


# ── 가이드·고정·캘린더 ───────────────────────────────────────

def guide_hub_title():
    return with_brand(f"정부지원사업 가이드 · 신청 자격·서류 {year()}")


def guide_hub_desc():
    return clip_desc(
        "신청 자격, 서류, 바우처·선정 차이, 소상공인 지원금 신청 순서까지. "
        "공고가 바뀌어도 남는 기본기를 보고, 오늘마감 목록과 같이 확인하세요."
    )


def guide_title(h1):
    return with_brand(_with_year(h1))


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


def pricing_title():
    return with_brand("요금제 · 지금은 무료 이메일 알림")


def pricing_desc():
    return clip_desc(
        "목록 열람과 이메일 마감 알림은 무료입니다. "
        "베이직·프로는 사업자 등록 후 오픈 / 준비 중이며, 카드결제·토스·PG는 없습니다."
    )


def scrap_title():
    return with_brand("스크랩한 공고")


def scrap_desc():
    return (
        "이 브라우저에 스크랩한 지원사업·입찰을 마감일 순으로 모읍니다. "
        "로그인 없이 기기에만 저장되며, 서버에 올리지 않습니다."
    )


def alerts_title():
    return with_brand("알림 조건")


def alerts_desc():
    return (
        "이 브라우저에 저장한 검색 조건의 미리보기·빈도·일시정지·삭제입니다. "
        "메일은 폼 전달(설정 시) 또는 mailto로 보내며 결제·서버 계정은 없습니다."
    )


# ── 입찰 (지원금·바우처 카피 금지) ───────────────────────────

def bid_hub_title(tally=None, today=None):
    t = tally or {}
    n_today = int(t.get("today") or 0)
    urgent = int(t.get("urgent") or 0)
    open_n = int(t.get("open") or 0)
    y = year(today)
    if n_today and open_n:
        return with_brand(_join(
            _named("오늘마감", n_today),
            _named("나라장터 입찰공고", open_n),
            f"마감일시 {y}",
        ))
    if urgent and open_n:
        return with_brand(_join(
            _named("마감임박", urgent),
            _named("나라장터 입찰공고", open_n),
            f"마감일시 {y}",
        ))
    if open_n:
        return with_brand(_join(_named("나라장터 입찰공고", open_n), f"마감일시 {y}"))
    return with_brand(f"나라장터 입찰공고 마감일시 · {y}")


def bid_hub_h1():
    return "나라장터 입찰공고, 마감일시 순"


def bid_hub_desc(tally=None, today=None):
    t = tally or {}
    n_today = int(t.get("today") or 0)
    urgent = int(t.get("urgent") or 0)
    open_n = int(t.get("open") or 0)
    y = year(today)
    if open_n:
        bits = [f"나라장터 {y} 입찰 {open_n}건을 마감일시 순으로 봅니다."]
        clock = []
        if n_today:
            clock.append(f"오늘 마감 {n_today}건")
        if urgent and urgent != n_today:
            clock.append(f"이번 주 {urgent}건")
        if clock:
            bits.append(", ".join(clock) + ".")
        bits.append("물품·용역·공사·외자, 수요기관·추정가격을 확인하세요.")
        return clip_desc(" ".join(bits))
    return clip_desc(
        f"나라장터 {y} 입찰공고를 마감일시 순으로 정리합니다. "
        "물품·용역·공사·외자로 나누고, 수요기관과 추정가격을 확인할 수 있습니다."
    )


def bid_urgent_title(n=0, today=None):
    return with_brand(_join(
        _named("나라장터 이번 주 마감 입찰", n),
        f"마감일시 {year(today)}",
    ))


def bid_urgent_h1():
    return "나라장터 이번 주 마감 입찰"


def bid_urgent_desc(n=0, today=None):
    y = year(today)
    if n:
        head = f"나라장터 {y}에서 7일 안에 마감일시가 있는 입찰 {n}건입니다."
    else:
        head = f"나라장터 {y}에서 7일 안에 마감일시가 있는 입찰만 모았습니다."
    return clip_desc(
        f"{head} 물품·용역·공사·외자를 확인하고 원문으로 가세요. "
        "지원사업 마감임박은 홈에서 따로 봅니다."
    )


def bid_kind_title(name, n=0, today=None):
    return with_brand(_join(
        _named(f"나라장터 {name} 입찰공고", n),
        f"마감일시 {year(today)}",
    ))


def bid_kind_desc(name, n=0, kind_desc="", today=None):
    extra = (kind_desc or "").strip()
    y = year(today)
    if n:
        head = f"나라장터 {y} {name} 입찰 진행 중 {n}건입니다."
    else:
        head = f"나라장터 {y} {name} 입찰을 마감일시 순으로 둡니다."
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
    title = short_notice_core((row.get("title") or "입찰공고").strip(), budget=28)
    if not row.get("is_open") or (isinstance(row.get("dday"), int) and row["dday"] < 0):
        return with_brand(_join(title, "마감된 입찰"))
    d = row.get("dday")
    if d == 0:
        return with_brand(_join("오늘마감", title, "나라장터"))
    if isinstance(d, int) and 0 < d <= 7:
        return with_brand(_join(f"D-{d} 마감", title, "나라장터"))
    return with_brand(_join(title, "나라장터 마감일시"))


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
