# -*- coding: utf-8 -*-
"""키워드 알림: 매칭, 새 공고가 없으면 발송하지 않음. 네트워크 없음."""
import json
import os
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(__file__))

import alert_digest
import landing


def _notice(nid, title, summary="", **extra):
    row = {"i": nid, "t": title, "s": summary, "d": 3, "du": "2026-10-20 · 시간 미상", "pt": "dated"}
    row.update(extra)
    return row


def _write(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


class _Resp:
    def __init__(self, status_code):
        self.status_code = status_code


class _JsonResp:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def _empty_get(url, headers=None, timeout=None):
    return _JsonResp(200, {"object": "list", "has_more": False, "data": []})


def test_keyword_matches_korean_title_and_summary():
    title_hit = _notice("a1", "2026 제조업 스마트공장 지원")
    assert alert_digest.keyword_matches(title_hit, "제조업")
    summary_hit = _notice("a2", "콘텐츠 제작 지원", "생성형 AI 음성 영상 도구를 씁니다")
    assert alert_digest.keyword_matches(summary_hit, "AI 음성 영상")
    assert not alert_digest.keyword_matches(summary_hit, "제조업")
    folded = _notice("a3", "ai voice lab")
    assert alert_digest.keyword_matches(folded, "AI Voice")
    assert not alert_digest.keyword_matches(title_hit, "")
    assert not alert_digest.keyword_matches(title_hit, "   ")
    # 금액·기관 필드는 매칭에 쓰지 않는다.
    money = {"i": "a4", "t": "일반 공고", "s": "", "m": "제조업 2억원", "o": "제조업진흥원"}
    assert not alert_digest.keyword_matches(money, "제조업")


def test_full_row_summary_field_matches():
    row = {"id": "b1", "title": "일반 모집", "ai": {"summary": "제조업 설비 교체"}}
    assert alert_digest.keyword_matches(row, "제조업")
    row2 = {"id": "b2", "title": "일반 모집", "blurb": "AI 음성 영상 편집"}
    assert alert_digest.keyword_matches(row2, "AI 음성 영상")


def test_deadline_label_skips_missing_and_always_sentinel():
    assert "D-3" in alert_digest.deadline_label(_notice("a", "t"))
    assert "2026-10-20" in alert_digest.deadline_label(_notice("a", "t"))
    today = _notice("a", "t", d=0, du="2026-10-07")
    assert alert_digest.deadline_label(today).startswith("오늘 마감")
    always = _notice("a", "t", pt="always", d=9999, du="예산 소진시까지", p="예산 소진시까지")
    label = alert_digest.deadline_label(always)
    assert label == "예산 소진시까지"
    assert "9999" not in label
    assert alert_digest.deadline_label({"i": "x", "t": "제목만"}) == ""


def test_no_send_when_no_new_matches():
    with tempfile.TemporaryDirectory() as tmp:
        notices = os.path.join(tmp, "notices.json")
        state = os.path.join(tmp, "alert_sent.json")
        rows = [
            _notice("old", "제조업 지원"),
            _notice("also", "AI 음성 영상 공고"),
        ]
        _write(notices, rows)
        _write(state, ["old", "also"])
        env = {
            "SUBSCRIBERS_JSON": json.dumps([
                {"email": "maker@example.com", "keyword": "제조업", "plan": "free"},
                {"email": "media@example.com", "keyword": "AI 음성 영상", "plan": "free"},
            ]),
            "RESEND_API_KEY": "re_test",
            "RESEND_FROM": "마감판 <alerts@magampan.com>",
        }

        def boom(*args, **kwargs):
            raise AssertionError("no new matches must not call the network")

        with patch("alert_digest.requests.post", side_effect=boom), \
             patch("alert_digest.requests.get", side_effect=_empty_get):
            code = alert_digest.execute(environ=env, notices_path=notices, state_path=state)
        assert code == 0
        with open(state, encoding="utf-8") as f:
            saved = json.load(f)
        assert set(saved) == {"also", "old"}
        assert "example.com" not in json.dumps(saved)


def test_no_send_when_new_notices_do_not_match_keyword():
    with tempfile.TemporaryDirectory() as tmp:
        notices = os.path.join(tmp, "notices.json")
        state = os.path.join(tmp, "alert_sent.json")
        _write(notices, [_notice("old", "제조업 지원"), _notice("new", "카페 인테리어")])
        _write(state, ["old"])
        env = {
            "SUBSCRIBERS_JSON": json.dumps([
                {"email": "maker@example.com", "keyword": "제조업", "plan": "free"},
            ]),
            "RESEND_API_KEY": "re_test",
        }

        def boom(*args, **kwargs):
            raise AssertionError("unmatched new notice must not send")

        with patch("alert_digest.requests.post", side_effect=boom), \
             patch("alert_digest.requests.get", side_effect=_empty_get):
            code = alert_digest.execute(environ=env, notices_path=notices, state_path=state)
        assert code == 0
        with open(state, encoding="utf-8") as f:
            saved = json.load(f)
        assert saved == ["new", "old"]


def test_sends_one_email_for_new_keyword_match_only():
    with tempfile.TemporaryDirectory() as tmp:
        notices = os.path.join(tmp, "notices.json")
        state = os.path.join(tmp, "alert_sent.json")
        rows = [
            _notice("old", "제조업 이미 보냄"),
            _notice("new-m", "중소 제조업 시설 교체", d=1, du="2026-10-08"),
            _notice("new-v", "지역 축제", s="AI 음성 영상 홍보 영상 제작"),
            _notice("new-x", "무관한 공고", m="최대 2억원"),
        ]
        _write(notices, rows)
        _write(state, ["old"])
        env = {
            "SUBSCRIBERS_JSON": json.dumps([
                {"email": "maker@example.com", "keyword": "제조업", "plan": "free"},
                {"email": "media@example.com", "keyword": "AI 음성 영상", "plan": "free"},
                {"email": "paid@example.com", "keyword": "제조업", "plan": "pro"},
            ]),
            "RESEND_API_KEY": "re_test",
        }
        calls = []

        def fake_post(url, json=None, headers=None, timeout=None):
            calls.append({"url": url, "json": json, "headers": headers})
            return _Resp(200)

        with patch("alert_digest.requests.post", side_effect=fake_post), \
             patch("alert_digest.requests.get", side_effect=_empty_get), \
             patch("alert_digest.time.sleep") as slept:
            code = alert_digest.execute(environ=env, notices_path=notices, state_path=state)
        assert code == 0
        assert len(calls) == 2
        assert slept.called
        tos = [c["json"]["to"] for c in calls]
        assert tos == [["maker@example.com"], ["media@example.com"]]
        assert all(c["url"] == alert_digest.RESEND_URL for c in calls)
        assert calls[0]["headers"]["Authorization"] == "Bearer re_test"
        body = calls[0]["json"]["text"]
        html = calls[0]["json"]["html"]
        assert "중소 제조업 시설 교체" in body
        assert "https://magampan.com/notice/new-m/" in body
        assert "D-1" in body
        assert "2026-10-08" in body
        assert "이미 보냄" not in body
        assert "무관한" not in body
        assert "2억원" not in body and "2억원" not in html
        assert "개인이 운영하는 지원사업·입찰 마감 안내 사이트입니다." in body
        assert "원문 공고" in body
        assert "qwqw050009@gmail.com" in body
        assert "회신" in body
        assert "/api/alerts/unsubscribe?token=" in body
        assert "/api/alerts/unsubscribe?token=" in html
        assert calls[0]["json"]["headers"]["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
        assert calls[0]["json"]["reply_to"] == "qwqw050009@gmail.com"
        video = calls[1]["json"]["text"]
        assert "AI 음성 영상" in video
        assert "https://magampan.com/notice/new-v/" in video
        assert "제조업" not in calls[1]["json"]["subject"]
        with open(state, encoding="utf-8") as f:
            saved = json.load(f)
        assert saved == ["new-m", "new-v", "new-x", "old"]
        blob = json.dumps(saved, ensure_ascii=False)
        assert "@" not in blob


def test_failed_send_does_not_mark_those_ids():
    with tempfile.TemporaryDirectory() as tmp:
        notices = os.path.join(tmp, "notices.json")
        state = os.path.join(tmp, "alert_sent.json")
        _write(notices, [_notice("new-m", "제조업 공고"), _notice("new-x", "무관 공고")])
        _write(state, ["old"])
        env = {
            "SUBSCRIBERS_JSON": json.dumps([
                {"email": "maker@example.com", "keyword": "제조업", "plan": "free"},
            ]),
            "RESEND_API_KEY": "re_test",
        }

        def fake_post(url, json=None, headers=None, timeout=None):
            return _Resp(429)

        with patch("alert_digest.requests.post", side_effect=fake_post), \
             patch("alert_digest.requests.get", side_effect=_empty_get):
            code = alert_digest.execute(environ=env, notices_path=notices, state_path=state)
        assert code == 0
        with open(state, encoding="utf-8") as f:
            saved = json.load(f)
        assert "new-m" not in saved
        assert set(saved) == {"old", "new-x"}


def test_missing_secret_is_noop_and_does_not_touch_state():
    with tempfile.TemporaryDirectory() as tmp:
        notices = os.path.join(tmp, "notices.json")
        state = os.path.join(tmp, "alert_sent.json")
        _write(notices, [_notice("new-m", "제조업 공고")])
        env = {
            "SUBSCRIBERS_JSON": "",
            "RESEND_API_KEY": "re_test",
        }

        def boom(*args, **kwargs):
            raise AssertionError("empty subscribers must not send")

        with patch("alert_digest.requests.post", side_effect=boom), \
             patch("alert_digest.requests.get", side_effect=_empty_get):
            assert alert_digest.execute(environ=env, notices_path=notices, state_path=state) == 0
        assert not os.path.exists(state)
        env["SUBSCRIBERS_JSON"] = json.dumps([
            {"email": "maker@example.com", "keyword": "제조업", "plan": "free"},
        ])
        env["RESEND_API_KEY"] = ""

        def no_get(*args, **kwargs):
            raise AssertionError("missing api key must not list contacts")

        with patch("alert_digest.requests.post", side_effect=boom), \
             patch("alert_digest.requests.get", side_effect=no_get):
            assert alert_digest.execute(environ=env, notices_path=notices, state_path=state) == 0
        assert not os.path.exists(state)


def test_baseline_records_ids_without_sending():
    with tempfile.TemporaryDirectory() as tmp:
        notices = os.path.join(tmp, "notices.json")
        state = os.path.join(tmp, "missing.json")
        _write(notices, [_notice("n1", "제조업 공고"), _notice("n2", "다른 공고")])
        env = {
            "SUBSCRIBERS_JSON": json.dumps([
                {"email": "maker@example.com", "keyword": "제조업", "plan": "free"},
            ]),
            "RESEND_API_KEY": "re_test",
        }

        def boom(*args, **kwargs):
            raise AssertionError("first run must not email the whole catalog")

        with patch("alert_digest.requests.post", side_effect=boom), \
             patch("alert_digest.requests.get", side_effect=_empty_get):
            code = alert_digest.execute(environ=env, notices_path=notices, state_path=state)
        assert code == 0
        with open(state, encoding="utf-8") as f:
            assert json.load(f) == ["n1", "n2"]


def test_bad_subscribers_json_is_config_error():
    try:
        alert_digest.parse_subscribers("{")
        raised = False
    except alert_digest.ConfigError:
        raised = True
    assert raised
    try:
        alert_digest.parse_subscribers('{"email":"a@example.com"}')
        raised = False
    except alert_digest.ConfigError:
        raised = True
    assert raised
    with patch("alert_digest.execute", side_effect=alert_digest.ConfigError("broken")):
        assert alert_digest.main() == 2


def test_execute_bad_json_returns_via_main():
    with tempfile.TemporaryDirectory() as tmp:
        notices = os.path.join(tmp, "notices.json")
        _write(notices, [_notice("n1", "제조업")])
        with patch.dict(os.environ, {
            "SUBSCRIBERS_JSON": "{",
            "RESEND_API_KEY": "re_test",
            "ALERT_NOTICES_PATH": notices,
            "ALERT_STATE_PATH": os.path.join(tmp, "state.json"),
        }, clear=False):
            assert alert_digest.main() == 2


def test_email_omits_amount_even_if_present_on_notice():
    notice = _notice("z", "제조업 공고", m="최대 2억원", w="소상공인만")
    subject, text, html = alert_digest.compose_email(
        {"email": "maker@example.com", "keyword": "제조업", "plan": "free"},
        [notice],
    )
    assert "제조업" in subject
    assert "2억원" not in text and "2억원" not in html
    assert "소상공인" not in text
    assert "https://magampan.com/notice/z/" in text


UNSUB_FIXTURE = (
    "dXNlckBleGFtcGxlLmNvbQrsoJzsobDsl4U."
    "f8f94461a85fd248526fe00b3a4f15a3250a726e8417012b2a4eb3dfd27ba784"
)


def test_unsubscribe_token_matches_pages_function():
    token = alert_digest.sign_unsubscribe("test-secret", "User@Example.com", "  제조업  ")
    assert token == UNSUB_FIXTURE
    url = alert_digest.unsubscribe_url("test-secret", "User@Example.com", "제조업")
    assert url.startswith("https://magampan.com/api/alerts/unsubscribe?token=")
    assert token in url


def _contact_get(contacts):
    """목록에는 속성이 없고, 개별 조회에 속성이 있다."""

    def get(url, headers=None, timeout=None):
        base = url.split("?", 1)[0]
        if base.rstrip("/") == alert_digest.CONTACTS_URL.rstrip("/"):
            rows = [{"id": item["id"], "email": item["email"], "unsubscribed": item["unsubscribed"]}
                    for item in contacts]
            has_more = False
            if "after=" in url:
                rows = []
            return _JsonResp(200, {"object": "list", "has_more": has_more, "data": rows})
        email = base.rsplit("/", 1)[-1]
        from urllib.parse import unquote
        email = unquote(email)
        for item in contacts:
            if item["email"].casefold() == email.casefold():
                return _JsonResp(200, item)
        return _JsonResp(404, {"message": "missing"})

    return get


def test_merges_resend_contacts_and_skips_blocked():
    with tempfile.TemporaryDirectory() as tmp:
        notices = os.path.join(tmp, "notices.json")
        state = os.path.join(tmp, "alert_sent.json")
        _write(notices, [
            _notice("old", "이미 보냄"),
            _notice("new-m", "중소 제조업 시설"),
            _notice("new-v", "영상", s="AI 음성 영상"),
        ])
        _write(state, ["old"])
        contacts = [
            {
                "id": "c1",
                "email": "remote@example.com",
                "unsubscribed": False,
                "properties": {
                    "keywords": {"type": "string", "value": "제조업\nAI 음성 영상"},
                    "blocked_keywords": {"type": "string", "value": ""},
                },
            },
            {
                "id": "c2",
                "email": "maker@example.com",
                "unsubscribed": True,
                "properties": {
                    "keywords": {"type": "string", "value": "제조업"},
                    "blocked_keywords": {"type": "string", "value": "제조업"},
                },
            },
            {
                "id": "c3",
                "email": "pending@example.com",
                "unsubscribed": True,
                "properties": {
                    "pending_keyword": {"type": "string", "value": "제조업"},
                    "confirm_token": {"type": "string", "value": "secret-token"},
                },
            },
        ]
        env = {
            "SUBSCRIBERS_JSON": json.dumps([
                {"email": "maker@example.com", "keyword": "제조업", "plan": "free"},
                {"email": "remote@example.com", "keyword": "제조업", "plan": "free"},
                {"email": "extra@example.com", "keyword": "영상", "plan": "free"},
            ]),
            "RESEND_API_KEY": "re_test",
        }
        calls = []

        def fake_post(url, json=None, headers=None, timeout=None):
            calls.append(json)
            return _Resp(200)

        with patch("alert_digest.requests.post", side_effect=fake_post), \
             patch("alert_digest.requests.get", side_effect=_contact_get(contacts)), \
             patch("alert_digest.time.sleep"):
            code = alert_digest.execute(environ=env, notices_path=notices, state_path=state)
        assert code == 0
        tos = [c["to"][0] for c in calls]
        assert "maker@example.com" not in tos
        assert "pending@example.com" not in tos
        assert tos.count("remote@example.com") == 2
        assert "extra@example.com" in tos
        assert "secret-token" not in json.dumps(calls)
        with open(state, encoding="utf-8") as f:
            blob = f.read()
        assert "@" not in blob


def test_resend_failure_does_not_advance_state():
    with tempfile.TemporaryDirectory() as tmp:
        notices = os.path.join(tmp, "notices.json")
        state = os.path.join(tmp, "alert_sent.json")
        _write(notices, [_notice("new-m", "제조업 공고")])
        _write(state, ["old"])

        def bad_get(url, headers=None, timeout=None):
            return _JsonResp(503, {"message": "down"})

        def boom(*args, **kwargs):
            raise AssertionError("failed contact list must not send")

        env = {
            "SUBSCRIBERS_JSON": json.dumps([
                {"email": "maker@example.com", "keyword": "제조업", "plan": "free"},
            ]),
            "RESEND_API_KEY": "re_test",
        }
        raised = False
        with patch("alert_digest.requests.post", side_effect=boom), \
             patch("alert_digest.requests.get", side_effect=bad_get):
            try:
                alert_digest.execute(environ=env, notices_path=notices, state_path=state)
            except alert_digest.ConfigError:
                raised = True
        assert raised
        with open(state, encoding="utf-8") as f:
            assert json.load(f) == ["old"]


def test_list_contacts_follows_cursor():
    pages = {
        "": [{"id": "a", "email": "a@example.com"}],
        "a": [{"id": "b", "email": "b@example.com"}],
    }

    def get(url, headers=None, timeout=None):
        after = ""
        if "after=" in url:
            after = url.split("after=", 1)[1]
        return _JsonResp(200, {"data": pages.get(after, []), "has_more": after == ""})

    rows = alert_digest._list_contacts(get, "re_test")
    assert [row["id"] for row in rows] == ["a", "b"]


def test_faq_is_daily_and_only_when_new():
    blob = " ".join(item["a"] for item in landing.ALERT_FAQS)
    assert "하루 1회, 새 공고가 있을 때만" in blob
    assert "1시간" not in blob


if __name__ == "__main__":
    test_keyword_matches_korean_title_and_summary()
    test_full_row_summary_field_matches()
    test_deadline_label_skips_missing_and_always_sentinel()
    test_no_send_when_no_new_matches()
    test_no_send_when_new_notices_do_not_match_keyword()
    test_sends_one_email_for_new_keyword_match_only()
    test_failed_send_does_not_mark_those_ids()
    test_missing_secret_is_noop_and_does_not_touch_state()
    test_baseline_records_ids_without_sending()
    test_bad_subscribers_json_is_config_error()
    test_execute_bad_json_returns_via_main()
    test_email_omits_amount_even_if_present_on_notice()
    test_unsubscribe_token_matches_pages_function()
    test_merges_resend_contacts_and_skips_blocked()
    test_resend_failure_does_not_advance_state()
    test_list_contacts_follows_cursor()
    test_faq_is_daily_and_only_when_new()
    print("ok")
