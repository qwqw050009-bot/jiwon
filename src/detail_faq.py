# -*- coding: utf-8 -*-
"""
공고·입찰 상세 FAQ / 신청 순서.

화면에 보이는 필드만 쓴다. 없는 자격·금액을 지어내지 않는다.
JSON-LD 답변은 같은 함수가 만든 문구와 같아야 한다.
"""
import json
import re


def _txt(v):
    return (v or "").strip()


def _short(v, n=120):
    s = _txt(v)
    if not s:
        return ""
    s = s.splitlines()[0].lstrip("•·*-■ ").strip()
    s = re.sub(r"\s+", " ", s)
    if len(s) > n:
        return s[: n - 1].rstrip(" ·,/") + "…"
    return s


def _join(parts):
    return " ".join(p for p in parts if p).strip()


def notice_faqs(a):
    """지원사업 상세 3~6개. 지원대상·마감·원문·서류는 필드가 있을 때만 구체적으로."""
    a = a or {}
    faqs = []
    target = _short(a.get("target"))
    region = _txt(a.get("region"))
    if target:
        who = f"이 공고에 적힌 지원대상은 {target}입니다."
        if region:
            who += f" 대상 지역 표기는 {region}입니다."
        who += (
            " 업력·매출·체납·중복지원 같은 세부 요건은 공고마다 다르니 원문에서 확인하세요. "
            "이 사이트에서 자격을 심사하거나 보장하지 않습니다."
        )
    else:
        who = (
            "이 페이지에는 지원대상 표기가 없습니다. "
            "업력·매출·체납 요건을 추정하지 않으니 원문 공고에서 확인하세요."
        )
    faqs.append({"q": "누가 신청할 수 있나요?", "a": who})

    if a.get("period_type") == "always":
        raw = _txt(a.get("period_raw")) or "상시 접수"
        deadline = (
            f"접수기간 표기는 {raw}입니다. 마감일이 없는 상시 접수이며, "
            "예산이 끝나면 닫힙니다."
        )
    else:
        start, end = _txt(a.get("apply_start")), _txt(a.get("apply_end"))
        line = _txt(a.get("deadline_line"))
        if start and end:
            deadline = f"접수기간은 {start} ~ {end}입니다."
        elif end:
            deadline = f"마감일은 {end}입니다."
        else:
            deadline = "이 페이지에 마감일 표기가 없습니다. 원문에서 확인하세요."
        if line and line not in deadline:
            deadline += f" 목록 표기는 {line}입니다."
        if a.get("is_closed"):
            deadline += " 이 공고는 접수가 마감되었습니다."
    faqs.append({"q": "마감일은 언제인가요?", "a": deadline})

    org = _txt(a.get("org")) or "소관기관"
    method = _txt(a.get("method"))
    if a.get("detail_url"):
        apply = f"이 사이트에서 신청하지 않습니다. {org} 원문 공고에서 접수하세요."
    else:
        apply = (
            f"원문 주소가 이 페이지에 없습니다. {org} 사이트에서 "
            "공고명으로 찾아 신청하세요."
        )
    if method:
        apply += f" 공고에 적힌 신청방법은 {method}입니다."
    faqs.append({"q": "원문은 어디서 신청하나요?", "a": apply})

    checklist = [(str(x).strip()) for x in ((a.get("ai") or {}).get("checklist") or []) if x]
    if checklist:
        docs = " ".join(checklist)
        docs += " 공고마다 서류가 다르니 원문 목록을 기준으로 하세요."
    else:
        docs = (
            "이 페이지에 서류 목록이 없습니다. 사업자등록증·국세완납 등 공통 서류는 "
            "준비서류 가이드를 참고하고, 최종 목록은 원문에서 확인하세요."
        )
    faqs.append({"q": "신청에 필요한 서류는 무엇인가요?", "a": docs})

    amount = _txt(a.get("amount"))
    card = _txt(a.get("amount_card"))
    shown = amount if amount and amount not in ("공고문 참조", "원문 확인") else card
    if shown:
        faqs.append({
            "q": "지원규모는 얼마인가요?",
            "a": (
                f"본문에 있는 규모 표기는 {shown}입니다. "
                "없는 숫자를 지어내지 않으며, 최종 한도는 원문을 따릅니다."
            ),
        })
    else:
        faqs.append({
            "q": "지원규모는 얼마인가요?",
            "a": "이 공고 본문에서 원 단위 표기를 읽지 못했습니다. 지원규모는 원문에서 확인하세요.",
        })

    src = _txt(a.get("source_label")) or "기업마당"
    col = _txt(a.get("collected_at"))
    src_a = f"데이터 출처는 {src}입니다."
    if col:
        src_a += f" 마지막 수집 시각은 {col} (KST)입니다."
    src_a += " 변경된 내용은 원문이 우선합니다."
    faqs.append({"q": "이 정보는 어디서 왔나요?", "a": src_a})
    return faqs[:6]


def notice_howto(a):
    """지원사업 상세 신청 순서 3단계. 화면에 그대로 노출한다."""
    a = a or {}
    target = _short(a.get("target")) or "원문 확인"
    region = _txt(a.get("region")) or "원문 확인"
    if a.get("period_type") == "always":
        period = _txt(a.get("period_raw")) or "상시 접수"
    else:
        period = _txt(a.get("deadline_line")) or _join([
            _txt(a.get("apply_start")),
            "~" if _txt(a.get("apply_start")) or _txt(a.get("apply_end")) else "",
            _txt(a.get("apply_end")),
        ]) or "원문 확인"
    org = _txt(a.get("org")) or "소관기관"
    return [
        {
            "name": "지원대상과 지역 확인",
            "text": (
                f"지원대상 표기는 {target}이며, 대상 지역은 {region}입니다. "
                "업력·매출·체납은 원문에서 확인하세요."
            ),
        },
        {
            "name": "마감일과 서류 확인",
            "text": (
                f"접수 표기는 {period}입니다. "
                "필요 서류는 공고문 원문 목록을 기준으로 준비하세요."
            ),
        },
        {
            "name": "원문에서 신청",
            "text": f"신청은 {org} 원문에서 합니다. 이 사이트에서 대신 접수하지 않습니다.",
        },
    ]


def bid_notice_faqs(a):
    """입찰 상세 3~6개. 지원금·바우처 어휘를 쓰지 않는다."""
    a = a or {}
    faqs = []
    close = _txt(a.get("close_dt")) or _txt(a.get("deadline_line")) or "원문 확인"
    line = _txt(a.get("deadline_line"))
    close_a = f"마감일시는 {close}입니다. 창구 마감은 나라장터 원문을 따릅니다."
    if line and line not in close_a:
        close_a += f" 목록 표기는 {line}입니다."
    if not a.get("is_open"):
        close_a += " 이 공고는 입찰이 마감되었습니다."
    faqs.append({"q": "마감일시는 언제인가요?", "a": close_a})

    org = _txt(a.get("org")) or "수요기관 원문 확인"
    ntce = _txt(a.get("ntce_org"))
    org_a = f"수요기관은 {org}입니다."
    if ntce and ntce != org:
        org_a += f" 공고기관은 {ntce}입니다."
    faqs.append({"q": "수요기관은 어디인가요?", "a": org_a})

    budget = _txt(a.get("budget")) or _txt(a.get("budget_card"))
    if budget:
        faqs.append({
            "q": "추정가격은 얼마인가요?",
            "a": (
                f"나라장터에 적힌 추정가격은 {budget}입니다. "
                "이 숫자가 아니면 원문을 따르세요."
            ),
        })
    else:
        faqs.append({
            "q": "추정가격은 얼마인가요?",
            "a": "이 공고는 나라장터 응답에 추정가격이 없습니다. 원문에서 확인하세요.",
        })

    region = _txt(a.get("region"))
    if region:
        faqs.append({
            "q": "참가지역은 어디인가요?",
            "a": (
                f"참가지역 표기는 {region}입니다. "
                "제목에서 지역을 추측하지 않으며, 나라장터 참가제한·참가가능 필드와 "
                "같을 때만 붙입니다."
            ),
        })
    else:
        faqs.append({
            "q": "참가지역은 어디인가요?",
            "a": (
                "이 공고는 참가제한·참가가능 지역 표기가 허용 목록과 정확히 같지 않아 "
                "지역을 비워 두었습니다. 원문에서 확인하세요."
            ),
        })

    if a.get("detail_url"):
        src_a = (
            "투찰은 나라장터 원문에서 합니다. 이 사이트에서 투찰하거나 대신 접수하지 않습니다."
        )
    else:
        src_a = (
            "이 건의 원문 URL이 없습니다. 나라장터에서 공고번호로 찾아 투찰하세요. "
            "이 사이트에서 대신 접수하지 않습니다."
        )
    no = _txt(a.get("notice_no") or a.get("bid_no") or a.get("id"))
    if no:
        src_a += f" 공고번호는 {no}입니다."
    faqs.append({"q": "원문은 어디서 투찰하나요?", "a": src_a})

    if a.get("is_correction"):
        seq = _txt(a.get("seq")) or "001"
        faqs.append({
            "q": "정정공고인가요?",
            "a": (
                f"나라장터 공고차수 표기가 {seq}이라 정정공고로 표시합니다. "
                "최종 내용은 원문을 따릅니다."
            ),
        })
    elif _txt(a.get("seq")) in ("", "000", "0") or a.get("seq") is not None:
        faqs.append({
            "q": "정정공고인가요?",
            "a": "나라장터 공고차수가 000(최초 공고)입니다. 이후 차수가 있으면 정정공고로 표시합니다.",
        })
    return faqs[:6]


def bid_notice_howto(a):
    a = a or {}
    kind = _txt(a.get("kind")) or "원문 확인"
    region = _txt(a.get("region")) or "원문 확인"
    close = _txt(a.get("deadline_line") or a.get("close_dt")) or "원문 확인"
    budget = _txt(a.get("budget") or a.get("budget_card")) or "원문 확인"
    return [
        {
            "name": "종류와 참가지역 확인",
            "text": (
                f"이 공고의 종류는 {kind}이며, 참가지역 표기는 {region}입니다. "
                "제목에서 지역을 추측하지 않습니다."
            ),
        },
        {
            "name": "마감일시와 추정가격 확인",
            "text": (
                f"투찰 마감은 {close}입니다. 추정가격 표기는 {budget}입니다. "
                "없는 숫자는 채우지 않습니다."
            ),
        },
        {
            "name": "나라장터에서 투찰",
            "text": "투찰은 나라장터 원문에서 합니다. 이 사이트에서 대신 접수하지 않습니다.",
        },
    ]


def howto_jsonld(name, desc, steps):
    """화면에 보이는 단계 문구를 그대로 HowTo로 옮긴다."""
    out = []
    for s in steps or []:
        n = _txt(s.get("name"))
        t = _txt(s.get("text"))
        if not n or not t:
            continue
        out.append({"@type": "HowToStep", "name": n, "text": t[:300]})
    if not out:
        return ""
    return json.dumps({
        "@context": "https://schema.org",
        "@type": "HowTo",
        "name": name,
        "description": desc,
        "step": out,
    }, ensure_ascii=False)


def seq_is_correction(seq):
    """나라장터 공고차수. 000·빈 값은 최초, 1 이상은 정정."""
    digits = re.sub(r"\D", "", str(seq or "")) or "0"
    try:
        return int(digits) >= 1
    except ValueError:
        return False
