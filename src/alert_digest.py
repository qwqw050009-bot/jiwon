# -*- coding: utf-8 -*-
"""키워드 알림 다이제스트.

구독자는 SUBSCRIBERS_JSON 환경변수(JSON 배열)로만 받는다.
저장소에 이메일을 쓰지 않는다. 발송 이력 data/alert_sent.json 은
data/seen.json 과 같이 공고 id 배열만 담는다.

하루 1회, 빌드·배포 뒤에 실행한다. 키워드가 맞는 새 공고가 있을 때만
구독자당 메일 한 통을 보낸다. 상태 파일이 없으면 현재 공고 id를
기준선으로 기록하고 메일은 보내지 않는다.
지원 공고 dist/notices.json 만 본다. 입찰(bids.json, /bid/)은 읽지 않는다.

RESEND_API_KEY 가 없거나 구독자가 없으면 로그만 남기고 exit 0.
잘못된 설정(JSON 깨짐, 공고 파일 없음 등)만 0이 아닌 코드.
"""
import json
import os
import time

import requests

import config

ROOT = os.path.join(os.path.dirname(__file__), "..")
NOTICES_PATH = os.path.join(ROOT, "dist", "notices.json")
STATE_PATH = os.path.join(ROOT, "data", "alert_sent.json")
RESEND_URL = "https://api.resend.com/emails"
DEFAULT_FROM = "마감판 <alerts@magampan.com>"
SEND_GAP_SEC = 0.6
EXIT_CONFIG = 2


class ConfigError(Exception):
    """고치면 되는 설정 오류. 빌드를 실패시켜도 되는 경우만."""


def notice_id(notice):
    if not isinstance(notice, dict):
        return ""
    return str(notice.get("i") or notice.get("id") or "").strip()


def notice_title(notice):
    return str(notice.get("t") or notice.get("title") or "").strip()


def summary_text(notice):
    """목록 카드 요약(s/blurb)과 상세 ai.summary. 금액·자격 필드는 넣지 않는다."""
    chunks = []
    for key in ("s", "blurb"):
        val = notice.get(key)
        if isinstance(val, str) and val.strip():
            chunks.append(val.strip())
    ai = notice.get("ai")
    if isinstance(ai, dict):
        summary = ai.get("summary")
        if isinstance(summary, str) and summary.strip():
            chunks.append(summary.strip())
    return "\n".join(chunks)


def keyword_matches(notice, keyword):
    """키워드는 제목 또는 요약의 대소문자 무시 부분 문자열. 한국어 그대로."""
    needle = (keyword or "").strip().casefold()
    if not needle or not isinstance(notice, dict):
        return False
    hay = (notice_title(notice) + "\n" + summary_text(notice)).casefold()
    return needle in hay


def deadline_label(notice):
    """있으면 마감 표기. 없는 날짜·D-9999 는 만들지 않는다."""
    if not isinstance(notice, dict):
        return ""
    pt = str(notice.get("pt") or notice.get("period_type") or "").strip()
    line = str(notice.get("du") or notice.get("deadline_line") or "").strip()
    raw = str(notice.get("p") or notice.get("period_raw") or "").strip()
    end = str(notice.get("e") or notice.get("apply_end") or notice.get("close_dt") or "").strip()
    if pt == "always":
        return line or raw or "상시 접수"
    d = notice.get("d", None)
    if d is None:
        d = notice.get("dday")
    badge = ""
    if isinstance(d, int) and not isinstance(d, bool) and 0 <= d < 9000:
        badge = "오늘 마감" if d == 0 else f"D-{d}"
    when = line or end or raw
    if badge and when:
        return f"{badge} · {when}"
    return badge or when


def notice_link(notice):
    domain = str(config.SITE.get("domain") or "https://magampan.com").rstrip("/")
    return f"{domain}/notice/{notice_id(notice)}/"


def _esc(text):
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def sort_notices(notices):
    def key(notice):
        pt = str(notice.get("pt") or notice.get("period_type") or "")
        d = notice.get("d", notice.get("dday"))
        title = notice_title(notice)
        if isinstance(d, bool) or not isinstance(d, int):
            d = 10 ** 9
        if pt == "always" or d >= 9000:
            return (1, 0, title)
        return (0, d, title)

    return sorted(notices, key=key)


def compose_email(subscriber, notices):
    """제목, 텍스트, HTML. 제목·마감·링크와 운영 안내만."""
    keyword = subscriber["keyword"]
    site_name = config.SITE.get("name") or "지원사업 마감판"
    site_email = config.SITE.get("email") or ""
    ordered = sort_notices(notices)
    n = len(ordered)
    subject = f"[{site_name}] {keyword} 새 공고 {n}건"
    footer = "개인이 운영하는 지원사업·입찰 마감 안내 사이트입니다."
    unsub = (
        "알림을 그만 받으려면 이 메일에 회신하거나 "
        f"{site_email} 로 중단을 요청해 주세요."
    )
    lines = [
        f"{site_name} 키워드 알림",
        "",
        f"키워드 「{keyword}」에 맞는 새 공고 {n}건입니다.",
        "신청은 소관기관이 게시한 원문 공고에서 하세요.",
        "",
    ]
    items = []
    for notice in ordered:
        title = notice_title(notice) or "(제목 없음)"
        url = notice_link(notice)
        due = deadline_label(notice)
        lines.append(f"- {title}")
        if due:
            lines.append(f"  마감: {due}")
        lines.append(f"  {url}")
        lines.append("")
        bit = f'<li><a href="{_esc(url)}">{_esc(title)}</a>'
        if due:
            bit += f"<br>마감: {_esc(due)}"
        bit += "</li>"
        items.append(bit)
    lines.extend(["", footer])
    if site_email:
        lines.append(f"문의 {site_email}")
    lines.extend(["", unsub])
    html = (
        '<!DOCTYPE html><html lang="ko"><body>'
        f"<p>{_esc(site_name)} 키워드 알림</p>"
        f"<p>키워드 「{_esc(keyword)}」에 맞는 새 공고 {n}건입니다.</p>"
        "<p>신청은 소관기관이 게시한 원문 공고에서 하세요.</p>"
        f"<ul>{''.join(items)}</ul>"
        f"<p>{_esc(footer)}"
        + (
            f' 문의 <a href="mailto:{_esc(site_email)}">{_esc(site_email)}</a>.'
            if site_email else ""
        )
        + "</p>"
        f"<p>{_esc(unsub)}</p>"
        "</body></html>"
    )
    return subject, "\n".join(lines), html


def mask_email(email):
    local, _, domain = (email or "").partition("@")
    if not local or not domain:
        return "***"
    return f"{local[:1]}***@{domain}"


def parse_subscribers(raw):
    text = (raw or "").strip()
    if not text:
        return []
    try:
        data = json.loads(text)
    except json.JSONDecodeError as err:
        raise ConfigError("SUBSCRIBERS_JSON 이 JSON이 아닙니다") from err
    if not isinstance(data, list):
        raise ConfigError("SUBSCRIBERS_JSON 은 배열이어야 합니다")
    out = []
    seen = set()
    for item in data:
        if not isinstance(item, dict):
            raise ConfigError("구독자 항목은 객체여야 합니다")
        email = str(item.get("email") or "").strip()
        keyword = str(item.get("keyword") or "").strip()
        plan = str(item.get("plan") or "free").strip().casefold()
        if any(ch in email or ch in keyword for ch in "\r\n"):
            raise ConfigError("구독자 필드에 줄바꿈이 있습니다")
        if not email or "@" not in email or email.startswith("@") or email.endswith("@"):
            print("알림 다이제스트: 이메일 형식이 아닌 항목은 건너뜀")
            continue
        if not keyword:
            print("알림 다이제스트: 키워드 없는 항목은 건너뜀")
            continue
        if plan != "free":
            print(f"알림 다이제스트: 무료 외 플랜은 건너뜀 ({plan})")
            continue
        key = (email.casefold(), keyword.casefold())
        if key in seen:
            continue
        seen.add(key)
        out.append({"email": email, "keyword": keyword, "plan": "free"})
    return out


def load_notices(path):
    if not os.path.isfile(path):
        raise ConfigError(f"공고 목록이 없습니다: {path}")
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as err:
        raise ConfigError("notices.json 을 읽지 못했습니다") from err
    if not isinstance(data, list):
        raise ConfigError("notices.json 은 배열이어야 합니다")
    rows = []
    for item in data:
        if isinstance(item, dict) and notice_id(item):
            rows.append(item)
    return rows


def load_state(path):
    """파일이 없으면 None(기준선). 있으면 id 집합."""
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as err:
        raise ConfigError("alert_sent.json 을 읽지 못했습니다") from err
    if not isinstance(data, list):
        raise ConfigError("alert_sent.json 은 공고 id 배열이어야 합니다")
    ids = set()
    for item in data:
        if not isinstance(item, str) or "@" in item or any(ch in item for ch in "\r\n"):
            raise ConfigError("alert_sent.json 에 id가 아닌 값이 있습니다")
        text = item.strip()
        if text:
            ids.add(text)
    return ids


def save_state(path, ids):
    clean = []
    for item in ids:
        text = str(item).strip()
        if not text or "@" in text or any(ch in text for ch in "\r\n"):
            raise ConfigError("상태 파일에 이메일을 쓸 수 없습니다")
        clean.append(text)
    payload = json.dumps(sorted(set(clean)), ensure_ascii=False)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            if f.read().strip() == payload:
                return False
    with open(path, "w", encoding="utf-8") as f:
        f.write(payload)
        f.write("\n")
    return True


def _from_address(raw):
    text = (raw or "").strip() or DEFAULT_FROM
    if any(ch in text for ch in "\r\n"):
        raise ConfigError("RESEND_FROM 에 줄바꿈이 있습니다")
    return text


def post_resend(api_key, from_addr, to_addr, subject, text, html, reply_to):
    payload = {
        "from": from_addr,
        "to": [to_addr],
        "subject": subject,
        "text": text,
        "html": html,
    }
    if reply_to:
        payload["reply_to"] = reply_to
    resp = requests.post(
        RESEND_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=20,
    )
    return resp.status_code


def execute(environ=None, notices_path=None, state_path=None):
    env = os.environ if environ is None else environ
    subscribers = parse_subscribers(env.get("SUBSCRIBERS_JSON") or "")
    if not subscribers:
        print("알림 다이제스트: 구독자 없음 (SUBSCRIBERS_JSON 비어 있음) — 건너뜀")
        return 0
    api_key = (env.get("RESEND_API_KEY") or "").strip()
    if not api_key:
        print("알림 다이제스트: RESEND_API_KEY 없음 — 건너뜀")
        return 0
    from_addr = _from_address(env.get("RESEND_FROM") or "")
    notices_file = notices_path or (env.get("ALERT_NOTICES_PATH") or "").strip() or NOTICES_PATH
    state_file = state_path or (env.get("ALERT_STATE_PATH") or "").strip() or STATE_PATH
    notices = load_notices(notices_file)
    current_ids = {notice_id(n) for n in notices}
    sent = load_state(state_file)
    if sent is None:
        save_state(state_file, current_ids)
        print(f"알림 다이제스트: 기준선 {len(current_ids)}건 기록. 메일은 보내지 않음")
        return 0
    fresh = [n for n in notices if notice_id(n) not in sent]
    if not fresh:
        print("알림 다이제스트: 새 공고 없음")
        return 0
    jobs = []
    for sub in subscribers:
        hits = [n for n in fresh if keyword_matches(n, sub["keyword"])]
        if hits:
            jobs.append((sub, hits))
        else:
            print(f"알림 다이제스트: 일치 없음 ({sub['keyword']})")
    if not jobs:
        save_state(state_file, sent | current_ids)
        print(f"알림 다이제스트: 새 공고 {len(fresh)}건, 키워드 일치 없음 — 메일 없음")
        return 0
    reply_to = config.SITE.get("email") or ""
    failed = set()
    state = set(sent)
    sent_mails = 0
    for index, (sub, hits) in enumerate(jobs):
        if index:
            time.sleep(SEND_GAP_SEC)
        ids = {notice_id(n) for n in hits}
        subject, text, html = compose_email(sub, hits)
        try:
            status = post_resend(
                api_key, from_addr, sub["email"], subject, text, html, reply_to,
            )
        except Exception as err:
            print(f"알림 다이제스트: 발송 오류 ({type(err).__name__})")
            failed |= ids
            continue
        if 200 <= status < 300:
            state |= ids
            save_state(state_file, state)
            sent_mails += 1
            print(
                f"알림 다이제스트: 발송 {len(hits)}건 → {mask_email(sub['email'])}"
                f" ({sub['keyword']})"
            )
        else:
            print(f"알림 다이제스트: 발송 실패 status={status}")
            failed |= ids
    save_state(state_file, (state | current_ids) - failed)
    print(f"알림 다이제스트: 메일 {sent_mails}통")
    return 0


def main():
    try:
        return execute()
    except ConfigError as err:
        print(f"알림 다이제스트 설정 오류: {err}")
        return EXIT_CONFIG


if __name__ == "__main__":
    raise SystemExit(main())
