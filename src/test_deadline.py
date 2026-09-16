# -*- coding: utf-8 -*-
"""D-day·절대날짜·상태가 모순되지 않는지."""
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(__file__))

import deadline as dl


TODAY = date(2026, 9, 16)


def test_always_is_open_not_closed():
    row = {"period_type": "always", "period_raw": "예산 소진시까지", "dday": 9999}
    assert dl.status_of(row, today=TODAY) == "open"
    assert dl.status_label("open") == "진행"
    cls, lab, sub = dl.dday_badge(row)
    assert lab == "상시"
    assert "마감" not in lab
    assert "예산 소진시까지" in sub


def test_closed_badge_is_not_dday():
    row = {"period_type": "dated", "apply_end": "2026-09-10", "dday": -6, "is_open": False}
    assert dl.status_of(row, today=TODAY) == "closed"
    cls, lab, sub = dl.dday_badge(row)
    assert lab == "마감"
    assert not lab.startswith("D-")
    assert "시간 미상" in sub
    assert "2026-09-10" in sub


def test_open_shows_dday_and_absolute_date():
    row = {"period_type": "dated", "apply_end": "2026-09-20", "dday": 4, "is_open": True}
    assert dl.status_of(row, today=TODAY) == "open"
    cls, lab, sub = dl.dday_badge(row)
    assert lab == "D-4"
    assert "2026-09-20" in sub
    assert "시간 미상" in sub


def test_upcoming_when_start_in_future():
    row = {
        "period_type": "dated", "apply_start": "2026-09-20", "apply_end": "2026-09-30",
        "dday": 14, "is_open": True,
    }
    assert dl.status_of(row, today=TODAY) == "upcoming"
    assert dl.status_label("upcoming") == "예정"


def test_time_known_only_when_clock_present():
    assert dl.time_known("2026-09-20") is False
    assert dl.time_known("2026-09-20 18:00") is True
    assert dl.time_known("202609201800") is True
    assert dl.time_known("") is False
    line = dl.deadline_line({"close_dt": "2026-09-20 18:00", "period_type": "dated"})
    assert "18:00" in line
    assert "시간 미상" not in line
    assert "KST" in line


if __name__ == "__main__":
    test_always_is_open_not_closed()
    test_closed_badge_is_not_dday()
    test_open_shows_dday_and_absolute_date()
    test_upcoming_when_start_in_future()
    test_time_known_only_when_clock_present()
    print("deadline tests ok")
