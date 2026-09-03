# -*- coding: utf-8 -*-
"""
캘린더 구독(.ics) 생성.

사용자가 한 번 구독하면 매일 빌드된 파일을 캘린더 앱이 알아서 다시 읽는다.
서버도 로그인도 알림 발송도 필요 없다.
"""
from datetime import date, timedelta

MAX = 300  # 피드당 최대 일정 수


def _esc(t):
    return (str(t).replace("\\", "\\\\").replace(";", r"\;")
            .replace(",", r"\,").replace("\n", r"\n"))


def _fold(line):
    """RFC 5545: 한 줄 75옥텟 제한."""
    b = line.encode("utf-8")
    if len(b) <= 73:
        return line
    out, cur = [], b""
    for ch in line:
        e = ch.encode("utf-8")
        if len(cur) + len(e) > 73:
            out.append(cur.decode("utf-8"))
            cur = b" "
        cur += e
    out.append(cur.decode("utf-8"))
    return "\r\n".join(out)


def build_ics(items, name, domain, stamp):
    """마감일을 종일 일정으로. 하루 전 알림 포함."""
    L = [
        "BEGIN:VCALENDAR", "VERSION:2.0",
        "PRODID:-//jiwon//deadline//KO",
        "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_esc(name)}",
        "X-WR-TIMEZONE:Asia/Seoul",
        f"X-WR-CALDESC:{_esc(name)} 접수 마감일입니다. 신청 전 원문 공고를 확인하세요.",
        "REFRESH-INTERVAL;VALUE=DURATION:PT12H",
        "X-PUBLISHED-TTL:PT12H",
    ]
    for a in items[:MAX]:
        if a.get("period_type") == "always":
            continue          # 마감일이 없으므로 캘린더 제외
        if a["dday"] < 0:
            continue
        try:
            end = date.fromisoformat(a["apply_end"])
        except Exception:
            continue
        L += [
            "BEGIN:VEVENT",
            f"UID:{a['id']}@jiwon",
            f"DTSTAMP:{stamp}",
            f"DTSTART;VALUE=DATE:{end.strftime('%Y%m%d')}",
            f"DTEND;VALUE=DATE:{(end + timedelta(days=1)).strftime('%Y%m%d')}",
            _fold(f"SUMMARY:[마감] {_esc(a['title'])}"),
            _fold("DESCRIPTION:" + _esc(
                f"{a['org']} · {a['category']} · {a['amount']}\n"
                f"지원대상: {a['target']}\n"
                f"접수기간: {a['apply_start']} ~ {a['apply_end']}\n\n"
                f"{domain}/notice/{a['id']}/")),
            f"URL:{domain}/notice/{a['id']}/",
            _fold(f"LOCATION:{_esc(a['region'])}"),
            "TRANSP:TRANSPARENT",
            "BEGIN:VALARM", "ACTION:DISPLAY",
            "TRIGGER:-P1D",
            _fold(f"DESCRIPTION:{_esc(a['title'])} 내일 마감"),
            "END:VALARM",
            "END:VEVENT",
        ]
    L.append("END:VCALENDAR")
    return "\r\n".join(L) + "\r\n"
