# -*- coding: utf-8 -*-
"""마감 입찰 아카이브 상세 상한 (Cloudflare Pages 2만 파일 한도)."""
import bid_build


def _rows(n):
    # archived_bids 는 최근 마감 순으로 돌려준다.
    return [{"id": f"B{i:05d}-000"} for i in range(n)]


def test_under_limit_untouched():
    rows = _rows(5)
    assert bid_build.cap_archived(rows, limit=10) == rows


def test_cap_keeps_recent_first():
    out = bid_build.cap_archived(_rows(50), limit=10)
    assert [a["id"] for a in out] == [f"B{i:05d}-000" for i in range(10)]


def test_cap_keeps_indexed_urls_even_if_old():
    keep = {"/bid/notice/B00049-000/"}
    out = bid_build.cap_archived(_rows(50), keep_indexed=keep, limit=10)
    ids = [a["id"] for a in out]
    assert len(ids) == 10
    assert "B00049-000" in ids
    assert "B00008-000" in ids and "B00009-000" not in ids


def test_default_limit_leaves_room_under_pages_cap():
    assert bid_build.ARCHIVE_PAGE_MAX <= 14000
