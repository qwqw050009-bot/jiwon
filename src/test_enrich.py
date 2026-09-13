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
    assert "이(가)" not in s and "을(를)" not in s
    assert "대상으로 진행하는" not in s
    assert "2026-09-20" in s or "이번 주" in s


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


if __name__ == "__main__":
    test_josa_batchim()
    test_card_line_uses_real_fields_and_josa()
    test_card_line_always_and_jeonnam()
    test_fallback_no_invented_target()
    test_heal_broken_josa_and_generic()
    print("enrich tests ok")
