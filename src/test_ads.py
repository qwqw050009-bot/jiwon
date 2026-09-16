# -*- coding: utf-8 -*-
"""ads.txt 와 Cloudflare _headers/_redirects 는 빌드가 항상 dist 루트에 둔다."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(__file__))

import build


def test_ads_txt_always_has_known_pub_and_newline():
    body = build.ads_txt_contents()
    assert body.endswith("\n")
    assert body.splitlines()[0] == "google.com, pub-2738052782253666, DIRECT, f08c47fec0942fa0"
    assert "ca-pub" not in body
    # 빈 클라이언트여도 고정 pub 줄을 쓴다. 다른 id 를 만들지 않는다.
    missing = build.ads_txt_contents({"adsense_client": ""})
    assert missing == body
    assert "pub-2738052782253666" in missing


def test_headers_mark_ads_txt_plain_and_cacheable():
    h = build.cf_headers_contents()
    assert "/ads.txt" in h
    assert "/app-ads.txt" in h
    assert "Content-Type: text/plain; charset=utf-8" in h
    assert "Cache-Control: public, max-age=86400" in h
    assert "X-Content-Type-Options: nosniff" in h
    assert "/rss.xml" in h
    assert "X-Robots-Tag: noindex" in h
    assert "/static/*" in h


def test_redirects_do_not_swallow_ads_txt():
    r = build.cf_redirects_contents()
    assert "/ads.txt /ads.txt 200" in r
    assert "/app-ads.txt /app-ads.txt 200" in r
    assert "/* /index.html" not in r
    assert "/* /404.html" not in r
    assert "/index.html" not in r
    assert "404.html" not in r


def test_emit_writes_dist_root_not_static_subdir():
    with tempfile.TemporaryDirectory() as d:
        build.emit_root_text_files(d)
        for name in ("ads.txt", "app-ads.txt", "_headers", "_redirects"):
            assert os.path.isfile(os.path.join(d, name)), name
            assert not os.path.exists(os.path.join(d, "static", name))
        ads = open(os.path.join(d, "ads.txt"), encoding="utf-8").read()
        app = open(os.path.join(d, "app-ads.txt"), encoding="utf-8").read()
        assert ads == app == build.ADS_TXT_LINE + "\n"
        assert ads.endswith("\n")
        headers = open(os.path.join(d, "_headers"), encoding="utf-8").read()
        assert "Content-Type: text/plain; charset=utf-8" in headers
        assert "max-age=86400" in headers
        raw = open(os.path.join(d, "ads.txt"), "rb").read()
        assert not raw.startswith(b"\xef\xbb\xbf")
        build.assert_ads_delivery(d)


def test_emit_without_static_copy_still_writes():
    """static/ads.txt 가 없어도 상수로 루트 파일을 만든다."""
    with tempfile.TemporaryDirectory() as d:
        orig = build.ROOT
        try:
            build.ROOT = d  # static/ads.txt 없는 빈 루트
            os.makedirs(os.path.join(d, "out"))
            body = build.ads_txt_contents()
            assert body == build.ADS_TXT_LINE + "\n"
            build.emit_root_text_files(os.path.join(d, "out"))
            got = open(os.path.join(d, "out", "ads.txt"), encoding="utf-8").read()
            assert got == build.ADS_TXT_LINE + "\n"
        finally:
            build.ROOT = orig


if __name__ == "__main__":
    test_ads_txt_always_has_known_pub_and_newline()
    test_headers_mark_ads_txt_plain_and_cacheable()
    test_redirects_do_not_swallow_ads_txt()
    test_emit_writes_dist_root_not_static_subdir()
    test_emit_without_static_copy_still_writes()
    print("ads tests ok")
