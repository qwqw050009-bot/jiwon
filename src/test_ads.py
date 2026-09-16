# -*- coding: utf-8 -*-
"""ads.txt 와 Cloudflare _headers 는 빌드가 항상 dist 루트에 둔다."""
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
    missing = build.ads_txt_contents({"adsense_client": ""})
    assert "pub-2738052782253666" in missing


def test_headers_mark_ads_txt_plain_and_cacheable():
    h = build.cf_headers_contents()
    assert "/ads.txt" in h
    assert "text/plain" in h
    assert "Cache-Control" in h
    assert "public" in h
    assert "/rss.xml" in h
    assert "X-Robots-Tag: noindex" in h


def test_emit_writes_dist_root_not_static_subdir():
    with tempfile.TemporaryDirectory() as d:
        build.emit_root_text_files(d)
        ads_path = os.path.join(d, "ads.txt")
        headers_path = os.path.join(d, "_headers")
        assert os.path.isfile(ads_path)
        assert os.path.isfile(headers_path)
        assert not os.path.exists(os.path.join(d, "static", "ads.txt"))
        ads = open(ads_path, encoding="utf-8").read()
        headers = open(headers_path, encoding="utf-8").read()
        assert ads.endswith("\n")
        assert ads.splitlines()[0] == build.ADS_TXT_LINE
        assert "Content-Type: text/plain" in headers


if __name__ == "__main__":
    test_ads_txt_always_has_known_pub_and_newline()
    test_headers_mark_ads_txt_plain_and_cacheable()
    test_emit_writes_dist_root_not_static_subdir()
    print("ads tests ok")
