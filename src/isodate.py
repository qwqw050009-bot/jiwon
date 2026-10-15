"""화면 날짜 표기를 기계가 읽는 ISO 형식으로 바꾼다(<time datetime>, 구조화 데이터용)."""
import re


def iso_date(v):
    """'2026-10-14', '2026.10.14 10:00' 같은 표기에서 YYYY-MM-DD 만 뽑는다. 못 찾으면 ''."""
    m = re.search(r"(20\d\d)[-./](\d{1,2})[-./](\d{1,2})", str(v or ""))
    return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}" if m else ""


def iso_datetime(v):
    """수집 시각 '2026-10-15 10:45' → '2026-10-15T10:45+09:00'. 시각이 없으면 날짜만."""
    d = iso_date(v)
    if not d:
        return ""
    m = re.search(r"(\d{1,2}):(\d{2})", str(v or "")[10:])
    return f"{d}T{int(m.group(1)):02d}:{m.group(2)}+09:00" if m else d
