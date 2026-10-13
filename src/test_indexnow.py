import os, sys, json
from datetime import date
sys.path.insert(0, os.path.dirname(__file__))
import indexnow

def test_batches_under_limit():
    paths = [f"/notice/{i}/" for i in range(11667)]
    bodies = list(indexnow.payloads(paths, "https://magampan.com", "k"))
    assert [len(b["urlList"]) for b in bodies] == [10000, 1667]
    assert bodies[0]["host"] == "magampan.com"
    assert bodies[0]["keyLocation"] == "https://magampan.com/k.txt"
    assert bodies[0]["urlList"][0] == "https://magampan.com/notice/0/"

def test_changed_only():
    urls = ["/", "/notice/1/", "/notice/2/", "/about/"]
    meta = {"/notice/1/": {"lastmod": "2026-10-13"}, "/notice/2/": {"lastmod": "2026-09-01"}}
    assert indexnow.changed_urls(urls, meta, date(2026, 10, 13)) == ["/", "/notice/1/"]

def test_http_error_does_not_raise():
    import urllib.error, io
    def boom(req, timeout):
        raise urllib.error.HTTPError(req.full_url, 400, "Bad", {}, io.BytesIO(b"bad"))
    assert indexnow.submit(["/"], "https://magampan.com", "k", opener=boom) is False

if __name__ == "__main__":
    test_batches_under_limit(); test_changed_only(); test_http_error_does_not_raise(); print("ok")
