import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import detail_extra as dx


def _n(i, **kw):
    base = {"id": str(i), "title": f"공고 {i}", "org": "중기부", "category": "창업",
            "region": "서울", "dday": i, "dlabel": f"D-{i}", "apply_end": "2026-11-0%d" % (i % 9 + 1),
            "period_type": "dated", "amount_card": ""}
    base.update(kw)
    return base


RICH = {
    "id": "1", "title": "2026 서울 창업 지원", "org": "서울시", "exec_org": "서울경제진흥원",
    "category": "창업", "region": "서울", "target": "중소기업\n기타", "amount": "최대 5천만원",
    "apply_start": "2026-10-01", "apply_end": "2026-10-30", "dlabel": "D-17", "dday": 17,
    "overview": "<p>서울 소재 창업기업을&nbsp;지원합니다.</p>",
    "points": ["지원대상\n- 서울 소재 업력 3년 이내 기업", "지원내용\n- 사업화 자금 최대 5천만원"],
    "method": "온라인 접수\n제출서류: 사업계획서 1부",
}


def test_summary_only_real_fields():
    rows = dx.summary_box(RICH)
    keys = [r["k"] for r in rows]
    assert keys == ["지원 금액·규모", "대상", "지역", "접수 기간", "D-day", "주관기관"]
    assert "서울경제진흥원" in rows[-1]["v"]
    empty = dx.summary_box({"amount": "공고문 참조", "target": ""})
    assert all(r["k"] != "지원 금액·규모" for r in empty)
    assert all(r["k"] != "대상" for r in empty)


def test_sections_classify_and_clean():
    secs = {s["key"]: s["lines"] for s in dx.desc_sections(RICH)}
    assert any("업력 3년" in l for l in secs["elig"])
    assert any("사업화 자금" in l for l in secs["support"])
    assert any("사업계획서" in l for l in secs["docs"])
    assert "온라인 접수" in secs["method"]
    assert dx.overview_paras(RICH) == ["서울 소재 창업기업을 지원합니다."]


def test_compare_needs_three_and_excludes():
    pool = [RICH] + [_n(i) for i in range(2, 8)]
    rows = dx.compare_rows(RICH, pool, limit=5, exclude=["2"])
    assert 3 <= len(rows) <= 5
    assert all(r["id"] not in ("1", "2") for r in rows)
    assert dx.compare_rows(RICH, [RICH, _n(2)]) == []


def test_agency_others_same_org_only():
    pool = [RICH, _n(2, org="서울시"), _n(3, org="서울시"), _n(4, org="다른곳"), _n(5, org="서울시", dday=-1)]
    rows = dx.agency_others(RICH, pool)
    assert [r["id"] for r in rows] == ["2", "3"]
    assert dx.agency_total(RICH, pool) == 2


def test_thin_detection():
    # 요약 150자 미만은 필드가 차 있어도 얇다.
    assert dx.is_thin(RICH)
    assert dx.is_thin({"title": "x", "amount": "공고문 참조"})
    assert dx.is_thin({"title": "x", "target": "중소기업"})
    assert dx.is_thin({"title": "x", "target": "중소기업", "method": "온라인", "contact": "02"})
    long_body = "서울 소재 창업기업의 사업화를 돕는 공고입니다. " * 6   # 약 160자
    longer = long_body * 2                                            # 약 320자
    dated = dict(RICH, overview=long_body)
    assert not dx.is_thin(dated)                                      # 마감일·금액 있음
    always = {"title": "x", "period_type": "always", "period_raw": "예산 소진 시까지",
              "amount": "공고문 참조", "overview": long_body}
    assert dx.is_thin(always)                                         # 금액·마감일 없고 250자 미만
    assert not dx.is_thin(dict(always, overview=longer))              # 본문이 충분히 길면 색인
    assert not dx.is_thin(dict(always, amount="최대 1억원"))           # 금액이 있으면 색인
    assert dx.is_thin(dict(always, amount=", 원"))                    # 숫자 없는 금액은 없는 것


def test_pages_differ():
    pool = [RICH] + [_n(i, org="서울시") for i in range(2, 8)]
    a = dx.notice_stats_line(RICH, pool)
    b = dx.notice_stats_line(pool[3], pool)
    assert a and b and a != b
    assert dx.list_stats([]) == ""
    assert "2건" in dx.list_stats(pool[:2])


def test_bid_compare_and_agency():
    a = {"id": "b0", "title": "청사 보수공사", "kind": "공사", "region": "서울", "org": "서울시", "dday": 3}
    pool = [a] + [{"id": f"b{i}", "title": f"청사 보수공사 {i}", "kind": "공사", "region": "서울",
                   "org": "서울시" if i < 3 else "구청", "dday": i, "budget_card": "1억"} for i in range(1, 7)]
    rows = dx.bid_compare_rows(a, pool, limit=5)
    assert 3 <= len(rows) <= 5 and rows[0]["amount"] == "1억"
    ag = dx.bid_agency_others(a, pool, exclude=[r["id"] for r in rows])
    assert all(r["org"] == "서울시" for r in ag)
