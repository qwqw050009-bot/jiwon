# -*- coding: utf-8 -*-
"""
마감·상태 표시. D-day와 절대 날짜가 모순되지 않게 한곳에서만 정한다.

- 상시: D-day 배지는 '상시', 상태는 '진행'. 가짜 마감일을 만들지 않는다.
- 날짜형: dday < 0 이면 배지·상태 모두 '마감' (D--n 금지).
- 접수 시작일이 오늘보다 뒤면 '예정'.
- 시각이 없으면 '시간 미상'을 명시한다. 없는 시각을 00:00으로 꾸미지 않는다.
"""
import re
from datetime import date, datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
TZ_LABEL = "KST"

STATUS_LABEL = {
    "upcoming": "예정",
    "open": "진행",
    "closed": "마감",
}

_TIME = re.compile(r"\d{1,2}:\d{2}")
_DIGITS = re.compile(r"\D")


def today_kst(now=None):
    if now is None:
        now = datetime.now(KST)
    elif getattr(now, "tzinfo", None) is None:
        now = now.replace(tzinfo=KST)
    else:
        now = now.astimezone(KST)
    if isinstance(now, datetime):
        return now.date()
    return now


def collected_stamp(now=None):
    """빌드(마지막 수집) 시각. KST 벽시계. 없는 값을 지어내지 않는다."""
    if now is None:
        now = datetime.now(KST)
    elif getattr(now, "tzinfo", None) is None:
        now = now.replace(tzinfo=KST)
    else:
        now = now.astimezone(KST)
    return now.strftime("%Y-%m-%d %H:%M")


def time_known(raw):
    """원문에 시각이 있으면 True. YYYY-MM-DD 만 있으면 False."""
    s = (raw or "").strip()
    if not s:
        return False
    if _TIME.search(s):
        return True
    digits = _DIGITS.sub("", s)
    return len(digits) >= 12


def status_of(row, today=None):
    """upcoming / open / closed. 상시는 날짜가 없어 open."""
    row = row or {}
    today = today or today_kst()
    if row.get("period_type") == "always":
        return "open"
    if row.get("is_closed") is True or row.get("is_open") is False:
        return "closed"
    d = row.get("dday")
    if isinstance(d, int) and d < 0:
        return "closed"
    start = (row.get("apply_start") or row.get("open_dt") or "").strip()
    if start:
        try:
            if date.fromisoformat(start[:10]) > today:
                return "upcoming"
        except ValueError:
            pass
    return "open"


def status_label(code):
    return STATUS_LABEL.get(code or "", "진행")


def deadline_line(row):
    """카드·상세용 절대 마감 표기. 상시는 원문 기간, 시각 없으면 시간 미상."""
    row = row or {}
    if row.get("period_type") == "always":
        return (row.get("period_raw") or "상시 접수").strip()
    end = (row.get("apply_end") or row.get("close_dt") or "").strip()
    if not end:
        return "마감일 미상"
    if time_known(end):
        return f"{end} ({TZ_LABEL})"
    return f"{end} · 시간 미상"


def dday_badge(row):
    """
    (css class, 배지 글자, 보조 한 줄).
    마감된 공고는 '마감'만. D-day와 '마감'을 동시에 쓰지 않는다.
    """
    row = row or {}
    st = status_of(row)
    line = deadline_line(row)
    if row.get("period_type") == "always":
        return "d-a", "상시", line
    d = row.get("dday")
    if st == "closed" or (isinstance(d, int) and d < 0):
        return "d-c", "마감", line
    if d == 0:
        return "d-u", "오늘", line
    if isinstance(d, int) and d <= 7:
        return "d-u", f"D-{d}", line
    if isinstance(d, int) and d <= 14:
        return "d-s", f"D-{d}", line
    if isinstance(d, int):
        return "d-o", f"D-{d}", line
    return "d-o", "접수중", line
