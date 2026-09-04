# -*- coding: utf-8 -*-
"""
지역×분야 롱테일 페이지용 소개문·FAQ.

LLM을 페이지마다 부르지 않는다. 그 페이지에 실제로 올라온 공고(건수,
소관기관, 마감일, 상시 접수 원문 표기)와, 분야/지역마다 다른 고정 문구를
끼워 넣을 뿐이다. 없는 공고를 만들어 넣지 않는다.

구글 FAQ 가이드라인: JSON-LD 답변은 화면에 보이는 문구와 같아야 한다.
"""
from html import escape as h

import json

from enrich import _josa


# 지역 페이지가 "무엇을 묶는지"를 설명한다. 특정 공고·예산을 지어내지 않는다.
# 전남광주는 통합 단위 그대로 둔다 (분리 금지).
REGION_BLURB = {
    "서울": "서울은 시 단위 공고와 자치구 단위 공고가 한 목록에 같이 올라옵니다. 소관기관이 구청이면 해당 구에 사업장이 있어야 하는 경우가 많으니, 제목보다 기관명을 먼저 보는 편이 빠릅니다.",
    "부산": "부산은 시 단위와 구·군 단위 공고가 섞여 있습니다. 공고문의 대상 지역이 특정 구로 좁혀져 있는지, 목록의 소관기관과 맞춰 확인하세요.",
    "대구": "대구는 광역시 단위와 구 단위 공고가 함께 있습니다. 소관기관이 구청이면 그 구의 사업장 요건을 원문에서 먼저 보세요.",
    "인천": "인천은 시 단위와 구·군 단위 공고가 함께 올라옵니다. 대상 지역 문구가 짧아도 원문에 세부 요건이 있는 경우가 있습니다.",
    "대전": "대전은 광역시 사업과 구 단위 사업이 한 목록입니다. 소관기관을 보면 시 전체 대상인지 구 단위인지 가늠하기 쉽습니다.",
    "울산": "울산은 시 단위와 구·군 단위 공고가 섞여 있습니다. 목록의 기관명과 공고문 대상 지역을 함께 보세요.",
    "세종": "세종은 시 단위 공고가 중심입니다. 이 페이지에는 세종 소재 사업장 기준 공고만 있고, 소재지 제한이 없는 사업은 전국 페이지에 따로 있습니다.",
    "경기": "경기는 도와 시·군 공고가 함께 있어 목록이 길어지기 쉽습니다. 시·군 사업은 해당 지역 사업장 요건이 붙는 경우가 많으니 소관기관부터 거르세요.",
    "강원": "강원은 도와 시·군 단위 공고가 섞여 있습니다. 소관기관이 시·군이면 그 지역 사업장 요건을 원문에서 확인하세요.",
    "충북": "충북은 도와 시·군 공고가 한 목록입니다. 대상 지역이 특정 시·군으로 적혀 있는지 공고문에서 한 번 더 보세요.",
    "충남": "충남은 도와 시·군 단위 공고가 함께 올라옵니다. 목록의 소관기관이 범위를 나누는 가장 빠른 힌트입니다.",
    "전북": "전북은 도와 시·군 공고가 함께 있습니다. 소관기관과 공고문 대상 지역이 일치하는지만 보면 됩니다.",
    "전남광주": "전남광주통합특별시 단위로 묶여 있습니다. 광주와 전남을 따로 나누지 않으니, 예전에 광역시·도로 찾던 공고도 이 목록에서 보시면 됩니다.",
    "경북": "경북은 도와 시·군 단위 공고가 섞여 있습니다. 대상 지역 문구는 원문이 짧아도 세부 조건이 있는 경우가 있습니다.",
    "경남": "경남은 도와 시·군 공고가 한 목록입니다. 소관기관이 시·군이면 해당 지역 사업장 요건을 확인하세요.",
    "제주": "제주는 도 단위 공고가 많은 편입니다. 이 페이지는 제주 소재 사업장 기준이고, 소재지 제한이 없는 사업은 전국 페이지에서 따로 볼 수 있습니다.",
    "전국": "사업장 소재지 제한이 없는 공고만 모았습니다. 특정 시·도에만 열리는 사업은 해당 지역 페이지에 있고, 여기에는 전국에서 신청 가능한 공고가 있습니다.",
}

# 분야 설명은 공고를 지어내지 않고, 이미 사이트 가이드와 맞는 읽는 법만 적는다.
CATEGORY_BLURB = {
    "금융": "융자·보증·이차보전처럼 갚아야 하는 자금과, 이자 일부를 보전하는 사업이 섞여 있습니다. 보조금과 같은 말로 보여도 상환 의무가 다를 수 있으니 제목의 융자·보증·이차보전 표현을 먼저 보세요.",
    "기술": "R&D·기술개발·특허 지원이 중심입니다. 서류평가·발표평가가 붙는 선정형이 많아, 마감일보다 사업계획서 완성도를 먼저 보는 편이 낫습니다.",
    "인력": "채용·인건비·교육훈련 지원입니다. 4대보험 가입 현황과 고용 유지 기간을 보는 공고가 많아, 신청 전에 인력 현황 서류를 챙겨 두는 편이 낫습니다.",
    "수출": "해외진출·수출바우처·전시회 지원이 많습니다. 예산 소진형 바우처가 섞여 있어, 서류를 오래 붙잡고 있기보다 조건을 확인하는 대로 접수하는 쪽이 유리한 경우가 있습니다.",
    "내수": "판로개척·마케팅·유통 지원입니다. 채널 입점, 홍보비, 전시 참가가 많고 바우처형과 선정형이 함께 올라옵니다.",
    "창업": "예비·초기창업 사업화 자금, 입주, 교육이 중심입니다. 업력 3년·7년 이내 조건이 흔하고, 업력은 보통 사업자등록일 기준으로 셉니다.",
    "경영": "컨설팅·경영개선·시설 지원입니다. 업력 제한이 느슨한 공고가 있어, 이미 운영 중인 소상공인도 문을 두드릴 수 있는 편입니다.",
    "기타": "위 일곱 분야에 넣기 어려운 공고입니다. 제목과 소관기관을 보고 업종·상황이 맞는지만 가려 보시면 됩니다.",
}

CATEGORY_GUIDE = {
    "금융": ("/guide/grant-vs-loan/", "지원금과 융자의 차이"),
    "기술": ("/guide/biz-plan-structure/", "사업계획서 기본 구조"),
    "인력": ("/guide/docs-checklist/", "준비서류 총정리"),
    "수출": ("/guide/voucher-vs-selection/", "바우처와 선정 사업 차이"),
    "내수": ("/guide/voucher-vs-selection/", "바우처와 선정 사업 차이"),
    "창업": ("/guide/start/", "지원사업 시작 가이드"),
    "경영": ("/guide/aply-trgt-check/", "신청 자격 확인"),
    "기타": ("/guide/aply-trgt-check/", "신청 자격 확인"),
}


def _orgs(items):
    seen, out = set(), []
    for a in items:
        o = (a.get("org") or "").strip()
        if o and o not in seen:
            seen.add(o)
            out.append(o)
    out.sort()
    return out


def _org_sentence(orgs):
    if not orgs:
        return "소관기관은 공고마다 다르니 목록의 기관명을 확인하세요."
    shown = orgs[:3]
    names = ", ".join(shown)
    if len(orgs) > 3:
        return f"이 목록의 소관기관은 {names} 등 {len(orgs)}곳입니다."
    if len(shown) == 1:
        return f"이 목록의 소관기관은 {shown[0]}입니다."
    return f"이 목록의 소관기관은 {names}입니다."


def _always_raws(always):
    raws = []
    for a in always:
        r = (a.get("period_raw") or "상시 접수").strip()
        if r and r not in raws:
            raws.append(r)
    return raws


def _quote_title(title):
    t = h((title or "").strip())
    return f"「{t}」" if t else ""


def _deadline_para(urgent, open_dated, always):
    bits = []
    if urgent:
        today_n = sum(1 for a in urgent if a.get("dday") == 0)
        nearest = min(urgent, key=lambda a: (a.get("dday"), a.get("apply_end") or ""))
        qtitle = _quote_title(nearest.get("title"))
        end = h(nearest.get("apply_end") or "")
        if today_n:
            bits.append(f"오늘 마감되는 공고가 {today_n}건 있습니다.")
        if qtitle and end and nearest.get("dday") != 0:
            bits.append(
                f"가장 가까운 마감은 {end}의 {qtitle}입니다. "
                f"이번 주 안에 접수가 끝나는 공고는 {len(urgent)}건입니다."
            )
        elif qtitle and nearest.get("dday") == 0:
            bits.append(f"그중 오늘 마감은 {qtitle}입니다.")
            if len(urgent) > today_n:
                bits.append(f"이번 주 마감은 모두 {len(urgent)}건입니다.")
        else:
            bits.append(f"이번 주 안에 접수가 끝나는 공고는 {len(urgent)}건입니다.")
    elif open_dated:
        nearest = min(open_dated, key=lambda a: (a.get("dday"), a.get("apply_end") or ""))
        end = h(nearest.get("apply_end") or "")
        qtitle = _quote_title(nearest.get("title"))
        if end and qtitle:
            bits.append(
                f"지금은 일주일 안 마감이 없고, 가장 가까운 마감일은 {end}의 {qtitle}입니다."
            )
        elif end:
            bits.append(f"지금은 일주일 안 마감이 없고, 가장 가까운 마감일은 {end}입니다.")
        else:
            bits.append("날짜가 있는 공고는 목록의 마감 표시를 기준으로 보시면 됩니다.")
    if always:
        raws = _always_raws(always)
        shown = ", ".join(f"'{h(x)}'" for x in raws[:2])
        bits.append(
            f"날짜 없는 상시 접수 공고는 {len(always)}건이며, 원문 표기는 {shown}처럼 "
            f"되어 있습니다. 상시 공고는 마감일이 없어 캘린더 구독에는 넣지 않습니다."
        )
    if not bits:
        bits.append("이 조건으로 접수 기간이 남은 공고가 거의 없으니, 목록의 마감 표시를 기준으로 보세요.")
    bits.append("목록은 마감이 가까운 공고가 위, 상시 접수 공고가 아래에 있습니다.")
    return " ".join(bits)


def _who_answer(region, category, cat_desc):
    if region == "전국":
        who = "사업장 소재지 제한이 없는 공고입니다. 전국 어디서나 요건만 맞으면 신청을 검토할 수 있습니다."
    elif region == "전남광주":
        who = (
            "전남광주통합특별시에 사업장을 둔 기업이 신청 대상인 공고입니다. "
            "광주와 전남을 따로 나누지 않습니다."
        )
    else:
        who = f"{region}에 사업장을 둔 기업이 신청 대상인 공고입니다."
    return (
        f"{who} {category} 분야는 {cat_desc}에 해당합니다. "
        f"업력·매출·체납·중복지원 요건은 공고마다 다르니, 목록에서 연 상세페이지와 원문 공고를 확인하세요."
    )


def _deadline_answer(urgent, open_dated, always, n, always_n, urgent_n):
    bits = [f"이 페이지에는 모두 {n}건이 있습니다."]
    if urgent_n:
        bits.append(f"이번 주 마감은 {urgent_n}건입니다.")
    if open_dated and not urgent:
        nearest = min(open_dated, key=lambda a: (a.get("dday"), a.get("apply_end") or ""))
        end = nearest.get("apply_end") or ""
        if end:
            bits.append(f"날짜가 있는 공고 중 가장 가까운 마감일은 {end}입니다.")
    if always:
        raws = _always_raws(always)
        shown = ", ".join(f"'{x}'" for x in raws[:2]) or "'상시 접수'"
        bits.append(
            f"상시 접수는 {always_n}건이고, 원문에는 {shown}처럼 적혀 있습니다. "
            f"예산이 소진되면 날짜 전에 닫히는 경우가 많습니다."
        )
    bits.append("정확한 접수 기간은 각 공고 상세의 접수기간과 원문이 우선입니다.")
    return " ".join(bits)


def _apply_answer(orgs):
    head = _org_sentence(orgs)
    return (
        f"{head} 신청 방법(온라인·방문·우편)은 공고마다 다르며, "
        f"각 상세페이지의 신청방법과 원문 공고 링크로 접수하시면 됩니다. "
        f"이 사이트는 신청을 대행하지 않습니다."
    )


def build(region, category, cat, items):
    """
    region×category 페이지용 소개 문단(2~4)과 화면용 FAQ.
    반환: (paragraphs_html, faqs)  faqs는 [{"q","a"}, ...]
    """
    items = items or []
    n = len(items)
    cat_desc = (cat or {}).get("desc") or f"{category} 분야"
    dated = [a for a in items if a.get("period_type") != "always"]
    always = [a for a in items if a.get("period_type") == "always"]
    open_dated = [a for a in dated if a.get("dday", -1) >= 0]
    urgent = [a for a in open_dated if a.get("dday", 99) <= 7]
    orgs = _orgs(items)

    c_eun = f"{h(category)}{_josa(category, '은', '는')}"
    if region == "전국":
        where = "전국 단위로 지금 접수 중이거나 최근 마감된"
    else:
        where = f"{h(region)} 지역에서 지금 접수 중이거나 최근 마감된"

    p1 = (
        f"{where} {h(category)} 분야 지원사업 "
        f"{n}건을 마감이 가까운 순서로 모아 둔 페이지입니다. "
        f"{c_eun} {h(cat_desc)}에 해당하는 공고입니다."
    )

    region_note = REGION_BLURB.get(region) or (
        f"{h(region)} 소재 사업장 기준 공고입니다. 공고문 대상 지역을 원문에서 확인하세요."
    )
    p2 = f"{region_note} {h(_org_sentence(orgs))}"

    p3 = _deadline_para(urgent, open_dated, always)

    cat_note = CATEGORY_BLURB.get(category) or (
        f"{h(category)}{_josa(category, '을', '를')} 공고 제목과 지원대상을 보고 해당 여부를 가리시면 됩니다."
    )
    href, gname = CATEGORY_GUIDE.get(category, ("/guide/aply-trgt-check/", "신청 자격 확인"))
    extra = ""
    if always:
        extra = (
            f' 상시·예산 소진형 공고가 {len(always)}건 있어, 마감일이 없어도 예산이 끝나면 접수가 닫힙니다. '
            f'<a href="/guide/always-deadline/">상시 접수 공고를 놓치지 않는 법</a>도 함께 보시면 됩니다.'
        )
    p4 = (
        f"{cat_note}{extra} 신청이 처음이면 "
        f'<a href="{h(href)}">{h(gname)}</a>{_josa(gname, "을", "를")} 먼저 보시면 됩니다. '
        f"최종 조건과 예산은 각 공고 원문이 우선입니다."
    )

    paras = [p1, p2, p3, p4]
    # 공고가 한두 건이면 분야 일반론을 줄여 부풀리지 않는다.
    if n <= 2:
        paras = [p1, p2, p3]

    faqs = [
        {
            "q": f"{region} {category} 지원사업은 지금 몇 건인가요?",
            "a": (
                f"이 페이지에는 {n}건이 있습니다. "
                f"이번 주 마감 {len(urgent)}건, 상시 접수 {len(always)}건입니다. "
                f"새 공고는 매일 아침 목록에 반영됩니다."
            ),
        },
        {
            "q": f"{region}에서 {category} 지원사업은 누가 신청할 수 있나요?",
            "a": _who_answer(region, category, cat_desc),
        },
        {
            "q": "마감일과 상시 접수는 어떻게 보나요?",
            "a": _deadline_answer(urgent, open_dated, always, n, len(always), len(urgent)),
        },
        {
            "q": "신청은 어디서 하나요?",
            "a": _apply_answer(orgs),
        },
    ]
    if always:
        faqs.append({
            "q": "상시 접수면 천천히 신청해도 되나요?",
            "a": (
                f"그렇지 않습니다. 이 목록의 상시 공고 {len(always)}건은 날짜 대신 "
                f"'{_always_raws(always)[0] if _always_raws(always) else '상시 접수'}'처럼 "
                f"적혀 있고, 예산이 소진되면 조기 마감되는 경우가 많습니다. "
                f"조건을 확인하는 대로 접수하는 편이 안전합니다."
            ),
        })

    return paras, faqs


def faq_jsonld(faqs):
    return json.dumps({
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [{
            "@type": "Question",
            "name": f["q"],
            "acceptedAnswer": {"@type": "Answer", "text": f["a"]},
        } for f in faqs],
    }, ensure_ascii=False)


def blurb_of(row):
    """카드용 한 줄. 이미 붙은 ai.summary만 잘라 쓰고, 없으면 빈 문자열."""
    s = ((row.get("ai") or {}).get("summary") or "").strip()
    if not s:
        return ""
    cut = s.find("다.")
    if cut >= 8:
        s = s[: cut + 2]
    if len(s) > 90:
        s = s[:89].rstrip() + "…"
    return s


def ad_plan(n, *, has_sections=False):
    """
    광고 밀도. H1 옆에는 두지 않고, 얇은 페이지에는 슬롯을 줄인다.
    반환: (top: bool, mid_after: int, bottom: bool)
    mid_after 가 0 이면 목록 중간 슬롯 없음.
    """
    if has_sections:
        return True, 0, True
    if n < 4:
        return False, 0, False
    if n < 8:
        return True, 0, False
    if n < 14:
        return True, 0, True
    return True, 8, True
