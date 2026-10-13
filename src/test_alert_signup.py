# -*- coding: utf-8 -*-
"""셀프 알림 신청 문구. 결제·Formspree를 신청 경로처럼 말하지 않는다."""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import build
import config
import landing
import pages


def test_privacy_says_resend_confirm_and_unsubscribe():
    rows = dict((slug, html) for slug, _title, html in pages.build(config.SITE))
    privacy = rows["privacy"]
    assert "Resend" in privacy
    assert "확인 메일" in privacy
    assert "수신 거부" in privacy
    assert "GitHub" in privacy
    assert "Formspree" not in privacy
    assert "모든 기능은 무료" in privacy
    assert "사업자 등록 후" not in privacy
    assert "광고" in privacy


def test_faq_explains_confirm_and_how_to_stop():
    blob = " ".join(item["q"] + " " + item["a"] for item in landing.ALERT_FAQS)
    assert "확인 메일" in blob
    assert "수신 거부" in blob
    assert "하루 1회, 새 공고가 있을 때만" in blob
    assert "베이직" not in blob and "프로" not in blob and "사업자 등록" not in blob
    assert "1시간" not in blob


def test_signup_form_posts_to_the_function():
    root = os.path.join(os.path.dirname(__file__), "..")
    form = open(os.path.join(root, "templates", "_alert_form.html"), encoding="utf-8").read()
    assert 'action="/api/alerts/subscribe"' in form
    assert 'name="_gotcha"' in form
    # 개인 메일 주소를 폼에 평문으로 두지 않고 문의 페이지로 보낸다.
    assert "mailto:" not in form and "@gmail.com" not in form
    assert 'href="/contact/"' in form
    js = open(os.path.join(root, "static", "alert.js"), encoding="utf-8").read()
    assert "/api/alerts/subscribe" in js
    assert "is-error" in js
    assert "확인 메일" in js
    headers = build.cf_headers_contents()
    assert "/api/*" in headers
    assert "no-store" in headers
    robots = open(os.path.join(root, "src", "build.py"), encoding="utf-8").read()
    assert 'Disallow: /api/' in robots


if __name__ == "__main__":
    test_privacy_says_resend_confirm_and_unsubscribe()
    test_faq_explains_confirm_and_how_to_stop()
    test_signup_form_posts_to_the_function()
    print("ok")
