# -*- coding: utf-8 -*-
"""규칙기반 해설·조사·카드 한 줄 회귀."""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import enrich


def test_josa_batchim():
    assert enrich._josa("산업통상부", "이", "가") == "가"
    assert enrich._josa("서울경제진흥원", "이", "가") == "이"
    assert enrich._josa("중소기업", "을", "를") == "을"
    assert enrich._josa("소상공인", "을", "를") == "을"
    assert enrich._josa("예비창업자", "을", "를") == "를"
    assert enrich._josa("창업진흥원", "이", "가") == "이"
    assert enrich._josa("", "이", "가") == "이"
    assert enrich._josa("K-Startup", "이", "가") == "이"


def test_card_line_uses_real_fields_and_josa():
    row = {
        "title": "천안시 2026년 소상공인 특례보증 지원사업 공고",
        "org": "충청남도",
        "region": "충남",
        "target": "소상공인",
        "category": "금융",
        "period_type": "dated",
        "apply_end": "2026-09-20",
        "dday": 7,
    }
    s = enrich.card_line(row)
    assert "충청남도" in s
    assert "소상공인" in s
    assert "특례보증" in s
    assert " · " in s
    assert "이(가)" not in s and "을(를)" not in s
    assert "대상으로 진행하는" not in s
    assert "09/20" in s or "이번 주" in s


def test_card_line_always_and_jeonnam():
    row = {
        "title": "전남 창업 사업화 지원",
        "org": "전남광주통합특별시",
        "region": "전남광주",
        "target": "예비창업자",
        "category": "창업",
        "period_type": "always",
        "period_raw": "예산 소진시까지",
    }
    s = enrich.card_line(row)
    assert "전남광주통합특별시" in s
    assert "예비창업자" in s
    assert "예산 소진시까지" in s
    assert "이(가)" not in s
    assert "을(를)" not in s


def test_fallback_no_invented_target():
    row = {"org": "산업통상부", "region": "전국", "category": "기술", "title": "기술개발 공고"}
    ai = enrich._fallback(row)
    assert "중소기업을" not in ai["summary"]
    assert "이(가)" not in ai["summary"]
    assert "을(를)" not in ai["summary"]
    assert "산업통상부" in ai["summary"]
    assert ai["summary"] != (
        "산업통상부가 전국 지역 중소기업을 대상으로 진행하는 기술 분야 지원사업입니다."
    )


def test_heal_broken_josa_and_generic():
    row = {
        "title": "테스트 특례보증",
        "org": "한국무역협회",
        "region": "광주",
        "target": "예비창업자",
        "category": "금융",
    }
    broken = {
        "summary": "한국무역협회이(가) 광주 지역 예비창업자을(를) 대상으로 진행하는 금융 분야 지원사업입니다.",
        "fit": ["x"],
        "caution": ["y"],
        "checklist": ["z"],
    }
    healed = enrich.heal_broken_josa(broken, row)
    assert healed is not broken
    assert "이(가)" not in healed["summary"]
    assert "을(를)" not in healed["summary"]
    assert "한국무역협회" in healed["summary"]

    generic = {
        "summary": "창업진흥원이 대전 지역 예비창업자를 대상으로 진행하는 금융 분야 지원사업입니다.",
        "fit": ["x"],
        "caution": ["y"],
        "checklist": ["z"],
    }
    healed2 = enrich.heal_broken_josa(generic, row)
    assert "대상으로 진행하는" not in healed2["summary"]
    assert "이(가)" not in healed2["summary"]

    good = {"summary": "충청남도가 소상공인에게 특례보증 지원을 합니다. 오늘 마감입니다."}
    assert enrich.heal_broken_josa(good, row) is good


def test_fallback_uses_title_shape_and_euro_josa():
    row = {
        "title": "소상공인 특례보증 지원사업",
        "org": "충청남도",
        "region": "충남",
        "target": "소상공인",
        "category": "금융",
        "period_type": "always",
        "period_raw": "예산 소진시까지",
        "method": "이메일 접수",
    }
    ai = enrich._fallback(row)
    assert "이(가)" not in ai["summary"]
    assert "을(를)" not in ai["summary"]
    assert "접수으로" not in " ".join(ai["caution"])
    joined = " ".join(ai["caution"])
    assert "이메일 접수" in joined
    assert "사업자등록증명" not in " ".join(ai["checklist"])
    assert ai["fit"] == []
    assert "원금" not in joined


def test_notice_signals_from_visible_title():
    always = enrich.notice_signals({
        "title": "수출바우처 선착순 모집",
        "period_type": "always",
        "period_raw": "예산 소진시까지",
    })
    labels = [s["label"] for s in always]
    assert "예산 소진시까지" in labels
    assert "바우처" in labels
    assert "선착순" in labels
    loan = enrich.notice_signals({
        "title": "소상공인 정책자금 융자",
        "period_type": "dated",
        "dday": 2,
    })
    assert any(s["cls"] == "loan" for s in loan)
    assert not any(s["cls"] == "today" for s in loan)


def test_heal_bullet_and_wrong_euro():
    row = {
        "title": "입주자 모집",
        "org": "중앙대학교 산학협력단",
        "region": "전국",
        "target": "예비창업자",
        "category": "창업",
    }
    leaked = {"summary": "중앙대학교 산학협력단이 전국 지역 ￭ 예비창업자를 대상으로"}
    healed = enrich.heal_broken_josa(leaked, row)
    assert "￭" not in healed["summary"]
    assert "이(가)" not in healed["summary"]
    euro = {"summary": "신청은 이메일 접수으로만 받습니다."}
    healed2 = enrich.heal_broken_josa(euro, row)
    assert "접수으로" not in healed2["summary"]
    assert healed2 is not euro


def test_amount_of_skips_placeholder_and_parses_body():
    row = {
        "amount": "공고문 참조",
        "title": "특례보증",
        "points": ["기업당 최대 2,000만원 이내 특례보증을 지원합니다."],
    }
    assert "2,000" in enrich.amount_of(row)
    assert enrich.amount_card(row)
    assert "공고문 참조" not in enrich.amount_card(row)
    empty = {"amount": "공고문 참조", "points": ["대상은 소상공인입니다."], "overview": ""}
    assert enrich.amount_of(empty) == ""
    assert enrich.amount_card(empty) == ""


def test_card_line_differs_when_titles_differ():
    base = {
        "org": "경상북도", "region": "경북", "target": "중소기업",
        "category": "경영", "period_type": "dated", "dday": 10,
    }
    a = enrich.card_line({**base, "title": "2026년 6차 농촌융복합산업 경영체 경쟁력 강화 지원 사업 신청 공고"})
    b = enrich.card_line({**base, "title": "경산시 2026년 여성ㆍ가족친화기업 지원사업 참여기업 모집 공고"})
    assert a != b
    assert "농촌융복합" in a
    assert "가족친화" in b
    assert "이(가)" not in a + b


def test_stated_area_quotes_target_and_skips_preference():
    row = {
        "region": "전국",
        "title": "2026 「Go to Market」동남권 창업기업 온라인 판로개척 교육 참가자 모집",
        "target": "동남권(부산·울산·경남) 소재, 업력 7년 미만 (예비)창업기업",
        "points": ["인증·검사실적 보유 기업, 업체당 최대 150만 원"],
        "category": "창업",
        "org": "경상국립대학교",
    }
    label, note, pill = enrich.region_display(row)
    assert label.startswith("동남권")
    assert "부산" in label and "경남" in label
    assert label != "전국"
    assert "전국" in note
    assert pill == "동남권"
    assert row["region"] == "전국"
    ai = enrich.ground_ai({
        "summary": "요약",
        "fit": ["전국에 사업장을 두고 대상 표기가 '동남권'인 곳", "창업 성격이 제목·대상과 맞는 곳"],
        "caution": ["같은 연도에 유사 항목을 받았다면 중복 지원이 제한될 수 있습니다."],
        "checklist": ["사업자등록증명원", "국세·지방세 완납증명서", "재무제표", "사업계획서"],
    }, row)
    blob = " ".join(ai["fit"] + ai["checklist"] + ai["caution"])
    assert "사업자등록" not in blob
    assert "재무제표" not in blob
    assert "전국에 사업장" not in blob
    assert ai["fit"] == []
    pref = {"region": "전국", "target": "서초구 거주자 또는 서초구 소재 기업 우대"}
    assert enrich.region_display(pref)[0] == "전국"
    titled = {"region": "전국", "title": "[대전] 웰컴 스테이", "target": "참가기업"}
    assert enrich.stated_area(titled) == ""


def test_home_sections_do_not_repeat_ids():
    import build
    rows = [
        {"id": "a", "dday": 1, "is_open": True, "is_new": True},
        {"id": "b", "dday": 2, "is_open": True, "is_new": False},
        {"id": "c", "dday": 9, "is_open": True, "is_new": False},
    ]
    week = [rows[0], rows[1]]
    sections = build.home_sections(rows, [rows[0]], week)
    shown = []
    for sec in sections:
        shown.extend(x["id"] for x in sec["items"])
    assert shown == ["a", "b", "c"]
    assert len(shown) == len(set(shown))


if __name__ == "__main__":
    test_josa_batchim()
    test_card_line_uses_real_fields_and_josa()
    test_card_line_always_and_jeonnam()
    test_fallback_no_invented_target()
    test_heal_broken_josa_and_generic()
    test_fallback_uses_title_shape_and_euro_josa()
    test_notice_signals_from_visible_title()
    test_heal_bullet_and_wrong_euro()
    test_amount_of_skips_placeholder_and_parses_body()
    test_card_line_differs_when_titles_differ()
    test_stated_area_quotes_target_and_skips_preference()
    test_home_sections_do_not_repeat_ids()
    print("enrich tests ok")
