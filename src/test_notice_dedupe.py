# -*- coding: utf-8 -*-
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
import notice_dedupe as nd


def R(i, title, org="해양수산부", ex="한국수산회", end="2026-10-30", pt="dated", created="2026-07-01"):
    return {"id": i, "title": title, "org": org, "exec_org": ex, "apply_end": end,
            "period_type": pt, "created": created}


def test_same_notice_merged_newest_kept():
    rows = [R("124341", "2026년 하반기 K-SEAFOOD 모집 공고", created="2026-07-14"),
            R("125365", "[전국] 2026년 하반기  K-SEAFOOD 모집 공고!", created="2026-08-12"),
            R("1", "다른 공고")]
    out, alias = nd.dedupe(rows)
    assert [r["id"] for r in out] == ["125365", "1"]
    assert alias == {"124341": "125365"}
    assert nd.redirect_pairs(alias) == [("/notice/124341/", "/notice/125365/")]


def test_keep_indexed_wins():
    rows = [R("10", "A 공고", created="2026-01-01"), R("20", "A 공고", created="2026-02-01")]
    out, alias = nd.dedupe(rows, keep={"/notice/10/"})
    assert alias == {"20": "10"}


def test_different_exec_org_or_deadline_not_merged():
    rows = [R("1", "AI훈련 공고", org="고용노동부", ex="한국생산성본부"),
            R("2", "AI훈련 공고", org="고용노동부", ex="한국산업인력공단"),
            R("3", "AI훈련 공고", org="고용노동부", ex="한국생산성본부", end="2026-11-01")]
    assert nd.dedupe(rows)[1] == {}


def test_always_merged_but_blank_deadline_not():
    rows = [R("1", "상시 공고", end=None, pt="always"), R("2", "상시 공고", end="", pt="always"),
            R("3", "빈 공고", end=""), R("4", "빈 공고", end="")]
    out, alias = nd.dedupe(rows)
    assert alias == {"1": "2"} or alias == {"2": "1"}
    assert len(out) == 3


def test_corp_suffix_normalized():
    rows = [R("1", "B", ex="(주)스탭스"), R("2", "B", ex="주식회사 스탭스")]
    assert len(nd.dedupe(rows)[1]) == 1


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"):
            f()
    print("ok")
