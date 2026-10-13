import os, sys, tempfile
sys.path.insert(0, os.path.dirname(__file__))
import seo_dedupe as sd

B = "지원사업 마감판"

def test_dup_titles_get_org_or_id():
    pages = {
        "/notice/1/": {"title": f"모집 · A 2026 | {B}", "desc": "같은 설명입니다", "org": "중기부"},
        "/notice/2/": {"title": f"모집 · A 2026 | {B}", "desc": "같은 설명입니다", "org": "산업부"},
        "/bid/notice/R1-000/": {"title": f"X · 마감된 입찰 | {B}", "desc": "d", "org": "시청"},
        "/bid/notice/R2-000/": {"title": f"X · 마감된 입찰 | {B}", "desc": "e", "org": "시청"},
        "/about/": {"title": f"소개 | {B}", "desc": "u", "org": ""},
    }
    ch = sd.disambiguate(pages, B)
    assert ch["/notice/1/"][0] == f"모집 · A 2026 · 중기부 | {B}"
    assert ch["/notice/2/"][0] == f"모집 · A 2026 · 산업부 | {B}"
    assert ch["/notice/1/"][1].endswith("(공고 1)")
    assert ch["/bid/notice/R1-000/"][0] == f"X · 마감된 입찰 · No.1-000 | {B}"
    assert "/about/" not in ch
    titles = {pages[u]["title"] if u not in ch else ch[u][0] for u in pages}
    assert len(titles) == len(pages)

def test_short_ident():
    assert sd.short_ident("R26BK01742157-001") == "No.1742157-001"
    assert sd.short_ident("126670") == "No.126670"
    assert sd.short_ident("ks-179013") == "No.ks-179013"

def test_run_rewrites_html():
    d = tempfile.mkdtemp()
    for i in ("1", "2"):
        os.makedirs(os.path.join(d, "notice", i))
        with open(os.path.join(d, "notice", i, "index.html"), "w", encoding="utf-8") as f:
            f.write(f'<title>T &#39;q&#39; | {B}</title><meta name="description" content="D">'
                    f'<meta property="og:title" content="T &#39;q&#39; | {B}"><meta property="og:description" content="D">')
    assert sd.run(d, ["/notice/1/", "/notice/2/"], B) == 2
    with open(os.path.join(d, "notice", "1", "index.html"), encoding="utf-8") as f:
        h = f.read()
    assert h.count("No.1 |") == 2 and h.count("(공고 1)") == 2

if __name__ == "__main__":
    test_dup_titles_get_org_or_id(); test_short_ident(); test_run_rewrites_html(); print("ok")
