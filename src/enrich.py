# -*- coding: utf-8 -*-
"""
공고 원문을 그대로 베끼면 중복 콘텐츠로 검색 순위가 안 나오고
애드센스 심사에서도 '가치 없는 콘텐츠'로 걸린다.
그래서 공고마다 우리 관점의 해설을 붙인다.

캐시가 핵심: 한 번 생성한 공고는 다시 호출하지 않는다.
공고 하나당 평생 1회 호출 → 하루 신규 20건이면 하루 20콜.
"""
import json
import os
import hashlib

CACHE = os.path.join(os.path.dirname(__file__), "..", "data", "enrich_cache.json")

PROMPT = """다음 정부지원사업 공고를 신청자 입장에서 해설해줘.
공고문을 그대로 옮기지 말고, 실무자가 판단에 쓸 수 있게 새로 써야 한다.

공고명: {title}
분야: {category} / 지역: {region}
소관기관: {org}
지원대상: {target}
지원규모: {amount}
신청방법: {method}

아래 JSON 형식으로만 답해. 다른 말 붙이지 마.
{{
 "summary": "이 사업이 뭔지 2문장 요약",
 "fit": ["이런 기업에 적합하다 3개"],
 "caution": ["신청 전 확인할 점 3개"],
 "checklist": ["준비서류/조건 체크 4개"]
}}"""


def _key(row):
    return hashlib.md5(row["title"].encode()).hexdigest()[:12]


def _load():
    if os.path.exists(CACHE):
        with open(CACHE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save(c):
    with open(CACHE, "w", encoding="utf-8") as f:
        json.dump(c, f, ensure_ascii=False, indent=1)


def _fallback(row):
    """API 키 없을 때 쓰는 규칙 기반 해설. 구조 확인용."""
    return {
        "summary": f"{row['org']}이(가) {row['region']} 지역 {row['target']}을(를) 대상으로 "
                   f"진행하는 {row['category']} 분야 지원사업입니다. "
                   f"지원규모는 {row['amount']} 수준입니다.",
        "fit": [
            f"{row['region']}에 사업장을 둔 {row['target']}",
            f"{row['category']} 분야 자금이 필요한 곳",
            "신청 시점에 세금 체납이 없는 사업자",
        ],
        "caution": [
            "동일 연도에 유사 사업을 받았다면 중복 지원이 제한될 수 있습니다.",
            "접수는 예산 소진 시 조기 마감되는 경우가 많습니다.",
            f"신청은 {row['method']}으로만 받습니다.",
        ],
        "checklist": [
            "사업자등록증명원",
            "국세·지방세 완납증명서",
            "최근 연도 재무제표 또는 부가세과세표준증명",
            "4대보험 가입자명부(인력 분야인 경우)",
        ],
    }


def enrich_all(rows, use_llm=False):
    """use_llm=False면 호출 0회. 나중에 True로 바꾸면 캐시에 없는 것만 호출."""
    cache = _load()
    changed = False
    for r in rows:
        k = _key(r)
        if k in cache:
            r["ai"] = cache[k]
            continue
        if use_llm:
            r["ai"] = _call_llm(r)
        else:
            r["ai"] = _fallback(r)
        cache[k] = r["ai"]
        changed = True
    if changed:
        _save(cache)
    return rows


def _call_llm(row):
    """
    실제 호출부. anthropic SDK 설치 후 사용.
    캐시 덕분에 공고당 1회만 돈다.
    """
    import anthropic
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        messages=[{"role": "user", "content": PROMPT.format(**row)}],
    )
    text = "".join(b.text for b in msg.content if b.type == "text")
    text = text.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(text)
    except Exception:
        return _fallback(row)
