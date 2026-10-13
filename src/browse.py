"""전체 상세 공고 색인 목록 (/browse/).

목록 화면은 20건만 HTML 로 그리고 나머지는 JS 로 펼친다. 그래서 상세페이지
대부분이 내부 링크가 없는 고아였다. 크롤러가 따라갈 수 있는 평범한 페이지 목록을
둔다. 얇은 목록이라 noindex(링크는 따라감)이고 광고도 싣지 않는다.
"""
import html as html_module
import os
import re

PER_PAGE = 200
_TITLE = re.compile(r"<title>(.*?)</title>", re.S)
KINDS = (("notice", "/notice/", "지원사업 공고"), ("bid", "/bid/notice/", "나라장터 입찰공고"))


def _title(dist, u, brand):
    try:
        h = open(os.path.join(dist, u.strip("/"), "index.html"), encoding="utf-8").read()
    except OSError:
        return ""
    m = _TITLE.search(h)
    t = html_module.unescape(m.group(1).strip()) if m else ""
    return t[: -len(f" | {brand}")] if t.endswith(f" | {brand}") else t


def pages_for(urls, meta, prefix):
    items = [u for u in urls if u.startswith(prefix) and u.count("/") == prefix.count("/") + 1]
    items.sort(key=lambda u: ((meta.get(u) or {}).get("lastmod") or "", u), reverse=True)
    return [items[i:i + PER_PAGE] for i in range(0, len(items), PER_PAGE)]


def build(env, site, dist, urls, meta):
    brand = site["name"]
    hub = []
    written = 0
    for key, prefix, label in KINDS:
        chunks = pages_for(urls, meta, prefix)
        hub.append((key, label, len(chunks), sum(len(c) for c in chunks)))
        for i, chunk in enumerate(chunks, 1):
            path = f"/browse/{key}/{i}/"
            lis = "".join(
                f'<li><a href="{u}">{html_module.escape(_title(dist, u, brand) or u)}</a></li>'
                for u in chunk)
            nav = []
            if i > 1:
                nav.append(f'<a href="/browse/{key}/{i-1}/" rel="prev">이전</a>')
            nav.append(f"{i} / {len(chunks)}")
            if i < len(chunks):
                nav.append(f'<a href="/browse/{key}/{i+1}/" rel="next">다음</a>')
            content = (f'<p><a href="/browse/">전체 공고 목록</a> · 최근 날짜순 {len(chunk)}건</p>'
                       f'<ul class="browse-list">{lis}</ul><p class="browse-nav">{" · ".join(nav)}</p>')
            _write(env, site, dist, path, f"{label} 전체 목록 {i}페이지", content)
            written += 1
    lis = "".join(f'<li><a href="/browse/{k}/1/">{lab}</a> — {n}건, {p}페이지</li>'
                  for k, lab, p, n in hub if p)
    _write(env, site, dist, "/browse/", "전체 공고 목록",
           f"<p>마감판이 상세 페이지를 둔 모든 공고입니다. 지금 신청할 공고는 "
           f'<a href="/">홈</a>과 <a href="/bid/">입찰 홈</a>에서 마감일 순으로 보세요.</p><ul>{lis}</ul>')
    return written + 1


def _write(env, site, dist, path, h1, content):
    html = env.get_template("page.html").render(
        site=site, path=path, section="support", page="browse",
        title=f"{h1} | {site['name']}", desc=f"{site['name']} {h1}. 공고 제목과 상세 페이지 링크.",
        h1=h1, content=content, noindex=True, no_ads=True)
    out = os.path.join(dist, path.strip("/"), "index.html")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
