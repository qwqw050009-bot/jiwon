"""GEO 보강: 날짜 ISO 변환, 긴 중복 제목 처리, 짧은 입찰 설명 보강."""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from isodate import iso_date, iso_datetime  # noqa: E402
import seo_dedupe as sd  # noqa: E402
import serp  # noqa: E402


def test_iso():
    assert iso_date("2026.1.5 10:00") == "2026-01-05"
    assert iso_date("예산 소진시까지") == ""
    assert iso_datetime("2026-10-15 10:45") == "2026-10-15T10:45+09:00"
    assert iso_datetime("2026-10-15") == "2026-10-15"


def test_long_tag_drops_brand():
    b = "지원사업 마감판"
    t = sd._with_tag("가" * 50 + f" | {b}", "No.1234567-000", b)
    assert t.endswith("No.1234567-000") and b not in t
    short = sd._with_tag(f"짧은 제목 | {b}", "No.1", b)
    assert short == f"짧은 제목 · No.1 | {b}"


def test_short_bid_desc_gets_facts():
    d = serp.bid_notice_desc({"title": "ICT 공사용 자재", "is_open": True, "dday": 11,
                              "close_dt": "2026-10-26 10:00", "method": "전자입찰", "contract": "일반경쟁"})
    assert "마감일시 2026-10-26 10:00" in d and "전자입찰·일반경쟁" in d and len(d) >= 40


if __name__ == "__main__":
    test_iso(); test_long_tag_drops_brand(); test_short_bid_desc_gets_facts()
    print("ok")
