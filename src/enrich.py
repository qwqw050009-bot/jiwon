# -*- coding: utf-8 -*-
"""
공고 원문을 그대로 베끼면 중복 콘텐츠로 검색 순위가 안 나오고
애드센스 심사에서도 '가치 없는 콘텐츠'로 걸린다.
그래서 공고마다 우리 관점의 해설을 붙인다.

캐시가 핵심: 한 번 생성한 공고는 다시 호출하지 않는다.
공고 하나당 평생 1회 호출 → 하루 신규 20건이면 하루 20콜.

주의: 실데이터에는 지원금액(amount) 필드가 없다.
      본문(points) 안에 '☞ 기업당 최대 3백만원' 형태로 들어있다.
      그래서 모든 필드 접근은 .get() 으로 방어한다.
"""
import hashlib
import json
import os
import re

CACHE = os.path.join(os.path.dirname(__file__), "..", "data", "enrich_cache.json")

PROMPT = """다음 정부지원사업 공고를 신청자 입장에서 냉정하게 분석해줘.
공고문을 그대로 옮기거나 좋은 말만 나열하지 마라. "이게 실제로 뭘 해주는지 +
누구한테 특히 유리한지 + 신청자 입장에서 아쉬운 점(현금지원 없음, 조건이
까다로움, 세부조건 미공개 등)이 있다면 솔직하게 + 신청 전 뭘 준비해야
하는지"를 판단할 수 있게 새로 써야 한다. 장점만 있는 것처럼 포장하지 마라.

공고명: {title}
분야: {category} / 지역: {region}
소관기관: {org}
지원대상: {target}
접수기간: {period}
신청방법: {method}
공고 요약: {overview}
주요 내용: {points}

아래 JSON 형식으로만 답해. 다른 말 붙이지 마.
{{
 "summary": "이 사업이 실제로 뭘 지원하는지, 그리고 신청자 입장에서 가장
   아쉽거나 확인이 필요한 점 하나를 포함해서 3문장 이내로",
 "fit": ["막연한 대상 말고 '~한 상황의 기업에 특히 유리하다' 식으로 구체적인 상황 3개"],
 "caution": ["체납여부 같은 뻔한 공통사항 말고, 이 공고 특유의 현실적인 제약이나 한계 3개"],
 "checklist": ["준비서류/조건 체크 4개"]
}}"""

# 본문에서 지원금액처럼 보이는 표현을 뽑는다.
UNIT = r"(?:억|천만|백만|십만|만|천)?"
MONEY = re.compile(
    r"(?:최대\s*)?[\d,]+\s*" + UNIT + r"\s*원(?:\s*(?:이내|한도|이하|까지))?"
    r"|총\s*사업비의?\s*\d+\s*%[^\s,]*"
    r"|사업비의?\s*\d+~?\d*\s*%"
)


def _pick_amount(text):
    """지원금액 표현 중 가장 그럴듯한 것 하나. 없으면 None."""
    if not text:
        return None
    cands = MONEY.findall(text) or [m.group(0) for m in MONEY.finditer(text)]
    cands = [c.strip() for c in cands if c and c.strip()]
    if not cands:
        return None
    # '최대'/'한도'/'이내'가 붙은 표현을 우선한다
    for c in cands:
        if any(k in c for k in ("최대", "한도", "이내", "이하")):
            return c
    return cands[0]


def _key(row):
    return hashlib.md5((row.get("title") or "").encode()).hexdigest()[:12]


def _load():
    if os.path.exists(CACHE):
        try:
            with open(CACHE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _save(c):
    with open(CACHE, "w", encoding="utf-8") as f:
        json.dump(c, f, ensure_ascii=False)


def amount_of(row):
    """
    지원규모 추출. 실데이터에는 금액 필드가 없고 본문에만 들어있다.
    지원내용은 보통 마지막 ☞ 항목이므로 뒤에서부터 훑는다.
    """
    if row.get("amount"):
        return row["amount"]
    for p in reversed(row.get("points") or []):
        got = _pick_amount(p)
        if got:
            return got
    return _pick_amount(row.get("overview")) or ""


def _period_text(row):
    if row.get("period_type") == "always":
        return row.get("period_raw") or "상시 접수"
    s, e = row.get("apply_start"), row.get("apply_end")
    return f"{s} ~ {e}" if s and e else (e or "기간 미정")


def _josa(word, has_batchim, no_batchim):
    """
    한글 받침 유무에 따라 조사를 고른다 (예: 이/가, 을/를, 은/는, 과/와).
    받침 판정은 유니코드 한글 완성형 코드 계산으로 한다.
    한글이 아닌 문자로 끝나거나(영문/숫자/기호) 빈 문자열이면 받침 있는
    쪽을 기본값으로 쓴다 — "이(가)" 같은 문법 오류 문구를 그대로 노출하는
    것보다는 한쪽을 골라 틀릴 위험이 훨씬 낫다.
    """
    word = (word or "").strip()
    if not word:
        return has_batchim
    code = ord(word[-1]) - 0xAC00
    if 0 <= code <= 11171:
        return has_batchim if code % 28 != 0 else no_batchim
    return has_batchim


def _place_of(region):
    region = (region or "").strip()
    if region == "전남광주":
        return "전남광주통합특별시"
    return region


# 제목에 이미 보이는 지원 성격만 고른다. 공고명을 새로 지어내지 않는다.
_SUPPORT_KEYS = (
    "특례보증", "이차보전", "신용보증", "기술보증", "융자", "보증",
    "수출바우처", "바우처", "R&D", "연구개발", "기술개발", "특허",
    "인건비", "채용", "교육훈련", "교육", "수출", "전시회", "전시",
    "마케팅", "판로", "컨설팅", "시설개선", "시설", "사업화", "입주",
    "예비창업", "초기창업", "창업", "전통시장", "스마트상점", "착한가격",
)


def _support_cue(title, category):
    title = title or ""
    found = [k for k in _SUPPORT_KEYS if k in title]
    if found:
        # 긴 키를 먼저 매칭한 순서 유지. 같은 계열은 하나만.
        picked = []
        for k in found:
            if any(k in p or p in k for p in picked):
                continue
            picked.append(k)
            if len(picked) == 2:
                break
        return "·".join(picked) + " 지원"
    if category:
        return f"{category} 지원"
    return "지원"


def _urgency_cue(row):
    if row.get("period_type") == "always":
        raw = (row.get("period_raw") or "상시 접수").strip()
        return f"원문 접수기간은 '{raw}'입니다."
    dday = row.get("dday")
    end = (row.get("apply_end") or "").strip()
    if dday == 0:
        return "오늘 마감입니다."
    if isinstance(dday, int) and 0 < dday <= 7:
        return f"{end}까지 접수합니다." if end else "이번 주 안에 접수가 끝납니다."
    if isinstance(dday, int) and dday < 0:
        return "접수가 끝난 공고입니다."
    if end:
        return f"접수 마감은 {end}입니다."
    return ""


def card_line(row):
    """
    목록 카드용 한 줄. 소관기관·대상·지원 성격·마감 힌트만 쓰고
    금액·자격·프로그램명을 지어내지 않는다. 조사는 받침으로 고른다.
    """
    row = row or {}
    org = (row.get("org") or "").strip()
    region = (row.get("region") or "").strip()
    target = (row.get("target") or "").strip()
    category = (row.get("category") or "").strip()
    title = (row.get("title") or "").strip()
    if not (org or region or target or category or title):
        return ""
    org = org or "소관기관"
    support = _support_cue(title, category)
    place = _place_of(region)
    og = _josa(org, "이", "가")
    sg = _josa(support, "을", "를")
    seed = f"{org}|{row.get('title') or ''}|{category}"
    variant = sum(ord(c) for c in seed) % 3
    urgency = _urgency_cue(row)

    if variant == 0 and target and place:
        head = (
            f"{org}{og} {place} 소재 {target}{_josa(target, '을', '를')} "
            f"대상으로 {support}합니다."
        )
    elif variant == 1 and target:
        head = f"{org}{og} {target}에게 {support}합니다."
        if place:
            head += f" 대상 지역은 {place}입니다."
    else:
        head = f"{org}{og} {support}{sg} 진행합니다."
        bits = []
        if place:
            bits.append(f"대상 지역은 {place}")
        if target:
            bits.append(f"대상은 {target}")
        if bits:
            head += " " + ", ".join(bits) + "입니다."
    if urgency:
        head += " " + urgency
    return head


def _fallback(row):
    """LLM 없이 쓰는 규칙 기반 해설. 모든 필드는 방어적으로 접근한다."""
    org = (row.get("org") or "").strip() or "소관기관"
    region = (row.get("region") or "").strip() or "전국"
    target = (row.get("target") or "").strip()
    category = (row.get("category") or "").strip() or "기타"
    method = (row.get("method") or "").strip() or "공고문 참조"
    amount = amount_of(row)
    place = _place_of(region)

    head = card_line(row)
    if amount:
        head += f" 공고문에는 지원규모가 {amount}로 적혀 있습니다."

    who = target or "신청 대상은 공고문 참조"
    fit = [
        f"{place}에 사업장을 둔 {who}" if target else f"{place} 소재 사업장 기준 공고",
        f"{category} 분야 지원이 필요한 곳",
        "신청 시점에 국세·지방세 체납이 없는 사업자",
    ]

    caution = []
    if row.get("period_type") == "always":
        raw = (row.get("period_raw") or "상시 접수").strip()
        caution.append(f"접수기간이 '{raw}'로 명시되어 있어 예산이 끝나면 날짜 전에 닫힐 수 있습니다.")
    else:
        caution.append(f"접수기간은 {_period_text(row)}입니다. 마감 전 여유를 두고 신청하세요.")
    caution.append("같은 연도에 유사 사업을 받았다면 중복 지원이 제한될 수 있습니다.")
    method0 = method.splitlines()[0].strip() if method else "공고문 참조"
    caution.append(f"신청은 {method0} 방식으로 받습니다.")

    checklist = ["사업자등록증명원", "국세·지방세 완납증명서",
                 "최근 연도 재무제표 또는 부가세과세표준증명"]
    checklist.append("4대보험 가입자명부" if category == "인력" else "사업계획서 또는 신청서 양식")

    return {"summary": head, "fit": fit, "caution": caution, "checklist": checklist}


# 예전 규칙기반 fallback이 조사(이/가, 을/를)를 문법에 안 맞게 리터럴로
# 붙여 넣던 버그의 흔적, 그리고 "OO가 OO 지역 OO를 대상으로 진행하는
# OO 분야 지원사업입니다" 상투구. 둘 다 AI를 다시 부르지 않고
# 규칙기반으로만 무료로 재생성한다 (API 비용 0원). enrich_cache와
# data/archive.json(마감 공고의 "ai" 스냅샷)에 둘 다 얼어붙어 있을 수
# 있어서 양쪽에서 재사용할 수 있게 공용 함수로 뺐다.
_BROKEN_JOSA = re.compile(r"이\(가\)|을\(를\)|은\(는\)")
_GENERIC_FALLBACK = re.compile(
    r"(?:이|가) .+? 지역 .+?(?:을|를) 대상으로 진행하는 .+? 분야 지원사업입니다"
)


def heal_broken_josa(ai, row):
    """
    옛날 조사 버그 문구이거나, 카드에서 버리는 상투구 fallback이면
    규칙기반으로 재생성해 돌려준다. 캐시를 우회해 LLM을 부르지 않는다.
    """
    s = (ai or {}).get("summary") or ""
    if (not s) or _BROKEN_JOSA.search(s) or _GENERIC_FALLBACK.search(s):
        return _fallback(row)
    return ai


def enrich_all(rows, use_llm=False):
    """use_llm=False면 호출 0회. True면 캐시에 없는 것만 호출."""
    cache = _load()
    changed = False
    for r in rows:
        k = _key(r)
        if k in cache:
            healed = heal_broken_josa(cache[k], r)
            r["ai"] = healed
            if healed is not cache[k]:
                cache[k] = healed
                changed = True
            continue
        try:
            r["ai"] = _call_llm(r) if use_llm else _fallback(r)
        except Exception as e:
            print(f"  해설 생성 실패({e}) → 규칙 기반으로 대체")
            r["ai"] = _fallback(r)
        cache[k] = r["ai"]
        changed = True
    if changed:
        _save(cache)
    return rows


def _call_llm(row):
    """실제 호출부. 캐시 덕분에 공고당 1회만 돈다."""
    import anthropic
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        messages=[{"role": "user", "content": PROMPT.format(
            title=row.get("title", ""), category=row.get("category", ""),
            region=row.get("region", ""), org=row.get("org", ""),
            target=row.get("target", ""), period=_period_text(row),
            method=row.get("method", ""), overview=row.get("overview", ""),
            points=" / ".join(row.get("points") or []),
        )}],
    )
    text = "".join(b.text for b in msg.content if b.type == "text")
    text = text.replace("```json", "").replace("```", "").strip()
    return json.loads(text)
