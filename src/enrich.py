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

PROMPT = """다음 정부지원사업 공고를 신청자 입장에서 차갑게 분석해줘.
홍보 문장·감탄·'좋은 기회' 같은 포장을 쓰지 마라. 공고문을 그대로 베끼지 마라.
공고에 없는 금액·자격·프로그램 이름을 지어내지 마라.
지원규모는 본문에 적힌 표현만 말하고, 없으면 규모를 추측하지 마라.

판단 기준:
1) 실제로 주는 것(현금, 바우처, 융자·보증, 교육, 공간, 컨설팅 등)을 제목·본문에서만 읽기
2) 대상 문구를 '모든 기업'이 아니라 구체 상황으로 바꿔 쓰기
3) 이 공고만의 제약(지역, 업력, 선착순, 자부담, 선정 인원 미공개, 상환, 예산 소진)
4) 준비물 — 본문에 서류 이름이 있을 때만. 없으면 서류 항목을 비운다

공고명: {title}
분야: {category} / 지역: {region}
소관기관: {org}
지원대상: {target}
접수기간: {period}
신청방법: {method}
공고 요약: {overview}
주요 내용: {points}

JSON만 답해. 다른 말 금지.
{{
 "summary": "무엇을 주는지 1문장 + 가장 큰 제약 1문장. 최대 3문장. '~해드립니다' 금지.",
 "fit": ["대상 문구를 상황으로 바꾼 문장 3개. '모든 기업에 유리' 금지."],
 "caution": ["이 공고 본문에서 읽히는 제약 3개. 체납 문장만 반복 금지."],
 "checklist": ["본문에 나온 서류 문장만. 없으면 빈 배열."]
}}"""

# 본문에서 지원금액처럼 보이는 표현을 뽑는다. 없는 숫자는 만들지 않는다.
UNIT = r"(?:억|천만|백만|십만|만|천)?"
MONEY = re.compile(
    r"(?:기업당|업체당|점포당|인당|1인당|개소당)?"
    r"(?:\s*(?:최대|한도))?\s*"
    r"[\d,]+\s*" + UNIT + r"\s*원(?:\s*(?:이내|한도|이하|까지))?"
    r"|최대\s*(?:억|천만|백만|십만|만)\s*원"
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
    '공고문 참조'는 값이 아니라 자리표시이므로 본문을 다시 본다.
    지원내용은 보통 마지막 ☞ 항목이므로 뒤에서부터 훑는다.
    """
    raw = (row.get("amount") or "").strip()
    if raw and raw != "공고문 참조":
        return raw
    for p in reversed(row.get("points") or []):
        got = _pick_amount(p)
        if got:
            return got
    return _pick_amount(row.get("overview")) or ""


def amount_card(row):
    """카드용 금액. 본문에서 뽑힌 표기만. 자리표시 '공고문 참조'는 비운다."""
    got = amount_of(row)
    if not got or got == "공고문 참조":
        return ""
    return got.strip()[:28]


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


def title_gist(title):
    """
    카드에 이미 보이는 제목에서 연도·공고·모집 껍질만 벗긴 요지.
    없는 프로그램명을 지어내지 않는다.
    """
    t = (title or "").replace("\xa0", " ").replace("ㆍ", "·")
    t = re.sub(r"\s+", " ", t).strip()
    if not t:
        return ""
    prev = None
    while t != prev:
        prev = t
        t = re.sub(r"^\[[^\]]+\]\s*", "", t)
        t = re.sub(r"20\d{2}년\s*", "", t)
        t = re.sub(r"(?:상반기|하반기)\s*", "", t)
        t = re.sub(r"\d+\s*차\s*", "", t)
    t = re.sub(r"(?:\s*(?:추가\s*)?(?:재)?공고)+$", "", t)
    t = re.sub(r"\s*연장(?:\s*공고)?$", "", t)
    t = re.sub(
        r"\s*(?:참가(?:기업|자|업체)|참여자|수혜기업|신청기업)?"
        r"\s*(?:추가\s*)?모집(?:\s*연장)?$",
        "",
        t,
    )
    t = re.sub(r"\s*(?:신청|접수)$", "", t)
    t = re.sub(r"\s*참가(?:기업|자|업체)$", "", t)
    t = re.sub(r"\s*\([^)]*$", "", t)
    t = t.strip(" -·,./()")
    if len(t) > 32:
        t = t[:31].rstrip(" ·,") + "…"
    return t


def _urgency_chip(row):
    if row.get("period_type") == "always":
        raw = (row.get("period_raw") or "상시").strip()
        return raw if 0 < len(raw) <= 10 else "상시"
    dday = row.get("dday")
    end = (row.get("apply_end") or "").strip()
    if dday == 0:
        return "오늘 마감"
    if isinstance(dday, int) and 0 < dday <= 7:
        if len(end) >= 10:
            return f"{end[5:7]}/{end[8:10]} 마감"
        return "이번 주 마감"
    return ""


def notice_signals(row):
    """
    카드용 짧은 신호. 제목·기간 원문에 있는 말만 쓴다.
    오늘/D-n은 왼쪽 D-day 칸과 겹치니 넣지 않고, 상시 원문과
    융자·바우처·선착순처럼 성격이 갈리는 표기만 둔다.
    """
    row = row or {}
    out = []
    if row.get("period_type") == "always":
        raw = (row.get("period_raw") or "상시 접수").strip()
        out.append({"cls": "always", "label": raw if 0 < len(raw) <= 12 else "상시 접수"})
    title = row.get("title") or ""
    if re.search(r"융자|보증|이차보전|정책자금", title):
        out.append({"cls": "loan", "label": "융자·보증"})
    if "바우처" in title:
        out.append({"cls": "voucher", "label": "바우처"})
    if "선착순" in title:
        out.append({"cls": "queue", "label": "선착순"})
    return out[:4]


def card_line(row):
    """
    목록 카드용 한 줄. '기관 · 지원요지 · 대상'만 쓰고 조사를 붙이지 않는다.
    요지는 제목에서 껍질을 벗긴 것이고, 금액·자격을 지어내지 않는다.
    """
    row = row or {}
    org = (row.get("org") or "").strip()
    target = ((row.get("target") or "").strip().splitlines() or [""])[0].strip()
    if len(target) > 18:
        target = target[:17].rstrip(" ·,/") + "…"
    category = (row.get("category") or "").strip()
    title = (row.get("title") or "").strip()
    if not (org or target or category or title):
        return ""
    gist = title_gist(title) or category
    if target and gist and target in gist:
        who = ""
    else:
        who = target
    parts = [p for p in (org, gist, who) if p]
    chip = _urgency_chip(row)
    if chip and chip not in parts:
        parts.append(chip)
    line = " · ".join(parts)
    return line[:90]


_KWON = ("수도권", "동남권", "서남권", "대경권", "충청권", "호남권", "영남권", "강원권")
_PLACE_STOP = {
    "사업장", "해당", "국내", "역내", "지역", "전국", "관할", "소재지", "본점",
    "기업", "대상", "신청", "소재",
}
_SIDO_WORD = {
    "서울특별시", "부산광역시", "대구광역시", "인천광역시", "광주광역시",
    "대전광역시", "울산광역시", "세종특별자치시", "경기도", "강원특별자치도",
    "강원도", "충청북도", "충청남도", "전북특별자치도", "전라북도", "전라남도",
    "경상북도", "경상남도", "제주특별자치도", "제주도",
    "서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종",
    "경기", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주",
    "전남광주",
}
_DOC_HINT = re.compile(
    r"서류|증빙|증명서|증명원|확인서|계획서|가입자명부|사업자등록증|사업자등록증명"
)
_FILLER_SUMMARY = re.compile(
    r"\s*본문에서 지원규모 표기를 찾지 못했습니다\..*"
)


def _target_text(row):
    """신청대상 필드와, 그에 해당하는 포인트만. 제목은 넣지 않는다."""
    chunks = []
    target = (row.get("target") or "").strip()
    if target:
        chunks.append(target)
    for p in row.get("points") or []:
        if isinstance(p, str) and "신청대상" in p[:12]:
            chunks.append(p)
    return "\n".join(chunks)


def _place_ok(place):
    place = (place or "").strip(" ·,")
    if not place or place in _PLACE_STOP:
        return ""
    if "·" in place or "," in place:
        return place
    if place in _SIDO_WORD or place in _KWON:
        return place
    if len(place) >= 3 and place.endswith(("시", "도", "군", "구")):
        return place
    return ""


def stated_area(row):
    """신청대상 문장에 적힌 지역.

    목록 버킷(region)은 바꾸지 않는다. 제목의 지명으로 시·도를 고르지 않는다.
    출처 칸이 이미 시·도면 그 값을 유지한다.
    """
    bucket = (row.get("region") or "").strip()
    if bucket and bucket != "전국":
        return ""
    text = _target_text(row).replace("ㆍ", "·").replace("（", "(").replace("）", ")")
    if not text:
        return ""
    kwon = "|".join(_KWON)
    m = re.search(rf"({kwon})\s*\([^)]{{1,40}}\)", text)
    if m:
        return re.sub(r"\s+", " ", m.group(0)).strip()
    m = re.search(rf"({kwon})", text)
    if m:
        return m.group(1)
    for line in text.splitlines():
        if "우대" in line:
            continue
        found = re.search(
            r"([가-힣]{2,12}(?:\s*[·,]\s*[가-힣]{2,12}){0,4})\s*소재",
            line,
        )
        if not found:
            continue
        place = _place_ok(re.sub(r"\s+", "", found.group(1)))
        if place:
            return place
    return ""


def region_display(row):
    """(상세 표기, 주석, 카드 알약). 주석은 출처 칸과 문장이 다를 때만."""
    bucket = (row.get("region") or "").strip() or "전국"
    stated = stated_area(row)
    if not stated or stated == bucket:
        return bucket, "", bucket
    pill = stated
    m = re.match(rf"({'|'.join(_KWON)})", stated)
    if m:
        pill = m.group(1)
    elif len(stated) > 12:
        pill = stated[:12].rstrip(" ·,/")
    note = (
        f"출처 지역 칸은 {bucket}입니다. "
        "위 표기는 신청대상 문장에 적힌 지역을 그대로 옮긴 것입니다."
    )
    return stated, note, pill


def _notice_lines(row):
    blobs = []
    for key in ("target", "overview", "method"):
        blobs.extend(str(row.get(key) or "").splitlines())
    for p in row.get("points") or []:
        blobs.extend(str(p).splitlines())
    return blobs


def docs_from_notice(row):
    """본문에 서류 단어가 있는 줄만. 없는 서류 이름은 만들지 않는다."""
    out, seen = [], set()
    for raw in _notice_lines(row):
        line = raw.strip().lstrip("•·*-■○ ")
        line = re.sub(
            r"^(?:신청대상|신청제외대상|우대사항|신청방법|주요내용)\s*:\s*",
            "",
            line,
        ).strip()
        if not line or not _DOC_HINT.search(line):
            continue
        if len(line) > 120:
            line = line[:119].rstrip() + "…"
        if line in seen:
            continue
        seen.add(line)
        out.append(line)
        if len(out) >= 6:
            break
    return out


def caution_from_fields(row):
    """접수기간·신청방법·제외 문장만. 모든 공고에 붙는 문장은 만들지 않는다."""
    out = []
    if row.get("period_type") == "always":
        raw = (row.get("period_raw") or "상시 접수").strip()
        out.append(f"접수기간 표기는 {raw}입니다.")
    else:
        start = (row.get("apply_start") or "").strip()
        end = (row.get("apply_end") or "").strip()
        if start and end:
            out.append(f"접수기간은 {start} ~ {end}입니다.")
        elif end:
            out.append(f"마감일은 {end}입니다.")
    method = (row.get("method") or "").strip()
    if method:
        first = method.splitlines()[0].strip()
        if len(first) > 80:
            first = first[:79].rstrip() + "…"
        out.append(f"신청방법 표기는 {first}입니다. 접수는 원문에서 합니다.")
    for p in row.get("points") or []:
        text = str(p).strip()
        if "제외" in text or "중복" in text:
            if len(text) > 140:
                text = text[:139].rstrip() + "…"
            if text not in out:
                out.append(text)
        if len(out) >= 4:
            break
    return out


def _fallback(row):
    """LLM 없이 쓰는 규칙 기반 해설. 공고에 없는 자격·서류는 넣지 않는다."""
    amount = amount_of(row)
    head = card_line(row)
    if amount:
        head += f" 공고문 지원규모 표기는 {amount}입니다. 이 숫자가 아니면 원문을 따르세요."
    return {
        "summary": head,
        "fit": [],
        "caution": caution_from_fields(row),
        "checklist": docs_from_notice(row),
    }


def ground_ai(ai, row):
    """캐시에 남은 공통 문장(적합 업종, 공통 서류)을 공고 필드로 바꾼다."""
    ai = dict(ai or {})
    summary = _FILLER_SUMMARY.sub("", (ai.get("summary") or "")).strip()
    if not summary:
        summary = _fallback(row).get("summary") or ""
    ai["summary"] = summary
    ai["fit"] = []
    ai["caution"] = caution_from_fields(row)
    ai["checklist"] = docs_from_notice(row)
    return ai


# 예전 규칙기반 fallback이 조사(이/가, 을/를)를 문법에 안 맞게 리터럴로
# 붙여 넣던 버그의 흔적, 그리고 "OO가 OO 지역 OO를 대상으로 진행하는
# OO 분야 지원사업입니다" 상투구. 둘 다 AI를 다시 부르지 않고
# 규칙기반으로만 무료로 재생성한다 (API 비용 0원). enrich_cache와
# data/archive.json(마감 공고의 "ai" 스냅샷)에 둘 다 얼어붙어 있을 수
# 있어서 양쪽에서 재사용할 수 있게 공용 함수로 뺐다.
_BROKEN_JOSA = re.compile(r"이\(가\)|을\(를\)|은\(는\)|와\(과\)|과\(와\)")
_GENERIC_FALLBACK = re.compile(
    r"(?:이|가) .+? 지역 .+?(?:을|를) 대상으로 진행하는 .+? 분야 지원사업입니다"
)
_STRAY_OLD_FALLBACK = re.compile(r"(?:이|가) \S+ 지역 \S+(?:을|를) 대상")
_BULLET_LEAK = re.compile(r"[￭•▪]")
_WRONG_EURO = re.compile(r"접수으로")


def heal_broken_josa(ai, row):
    """
    옛날 조사 버그 문구이거나, 카드에서 버리는 상투구 fallback이면
    규칙기반으로 재생성해 돌려준다. 캐시를 우회해 LLM을 부르지 않는다.
    """
    s = (ai or {}).get("summary") or ""
    if (
        (not s)
        or _BROKEN_JOSA.search(s)
        or _GENERIC_FALLBACK.search(s)
        or _STRAY_OLD_FALLBACK.search(s)
        or _BULLET_LEAK.search(s)
        or _WRONG_EURO.search(s)
    ):
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
