# -*- coding: utf-8 -*-
"""130/130 마무리: 실전달 알림·LCP·홈 첫 화면. 결제는 N/A."""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import build
import config


ROOT = os.path.join(os.path.dirname(__file__), "..")


def test_formspree_url_shapes():
    assert config.formspree_url("") == ""
    assert config.formspree_url(None) == ""
    assert config.formspree_url("xpzgkjyz") == "https://formspree.io/f/xpzgkjyz"
    assert config.formspree_url("https://formspree.io/f/xpzgkjyz?foo=1") == (
        "https://formspree.io/f/xpzgkjyz"
    )
    assert config.formspree_url("https://getform.io/f/abc") == "https://getform.io/f/abc"
    assert config.formspree_url("drop;me") == ""


def test_ads_txt_untouched():
    assert build.ADS_TXT_LINE == "google.com, pub-2738052782253666, DIRECT, f08c47fec0942fa0"
    body = build.ads_txt_contents()
    assert body.splitlines()[0] == build.ADS_TXT_LINE


def test_no_payment_wall_in_alert_path():
    blob = ""
    for name in ("alert.js", "filter.js", "bid_filter.js", "state.js"):
        blob += open(os.path.join(ROOT, "static", name), encoding="utf-8").read()
    low = blob.lower()
    assert "toss" not in low
    assert "imp.init" not in low
    assert "checkout" not in low
    assert "kakao.init" not in low


if __name__ == "__main__":
    test_formspree_url_shapes()
    test_ads_txt_untouched()
    test_no_payment_wall_in_alert_path()
    print("score tests ok")
