"""빌드 후처리: 색인 페이지끼리 <title>·description 이 겹치면 구분자를 붙인다.

상세페이지 제목은 원문 제목을 28자 안팎으로 줄이므로 서로 다른 공고가 같은
제목이 될 수 있다. 검색엔진은 중복 제목을 한 페이지로 묶어버린다.
구분자는 페이지에 이미 있는 값(기관명, 공고번호)만 쓴다. 없는 값을 짓지 않는다.
"""
import html as html_module
import json
import os
import re
from collections import defaultdict

_TITLE = re.compile(r"<title>(.*?)</title>", re.S)
_DESC = re.compile(r'<meta name="description" content="([^"]*)">')
_LD = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)


def _path_file(dist, u):
    return os.path.join(dist, u.strip("/"), "index.html") if u != "/" else os.path.join(dist, "index.html")


def _provider(h):
    for js in _LD.findall(h):
        try:
            o = json.loads(js)
        except Exception:
            continue
        if isinstance(o, dict) and o.get("@type") == "GovernmentService":
            return ((o.get("provider") or {}).get("name") or "").strip()
    return ""


def _ident(u):
    m = re.match(r"^/(?:bid/)?notice/([^/]+)/$", u)
    return m.group(1) if m else ""


def short_ident(ident):
    """제목용 짧은 공고번호. R26BK01742157-001 → No.1742157-001, 126670 → No.126670."""
    m = re.match(r"^[A-Za-z]*\d{0,2}[A-Za-z]+0*(\d+(?:-\d+)?)$", ident)
    return f"No.{m.group(1)}" if m else f"No.{ident}"


def _with_tag(title, tag, brand):
    suffix = f" | {brand}"
    core = title[:-len(suffix)] if title.endswith(suffix) else title
    if tag in core:
        return title
    return f"{core} · {tag}{suffix}" if title.endswith(suffix) else f"{core} · {tag}"


def disambiguate(pages, brand):
    """pages: {url: {"title", "desc", "org"}} → {url: (new_title, new_desc)} (바뀐 것만)."""
    out = {}
    by_t = defaultdict(list)
    for u, p in pages.items():
        by_t[p["title"]].append(u)
    titles = {u: p["title"] for u, p in pages.items()}
    for t, us in by_t.items():
        if len(us) < 2:
            continue
        orgs = {pages[u]["org"] for u in us}
        for u in us:
            org, ident = pages[u]["org"], _ident(u)
            tag = org if (org and len(orgs) == len(us) and org not in t) else ""
            if not tag and ident:
                tag = short_ident(ident)
            if tag:
                titles[u] = _with_tag(t, tag, brand)
    by_d = defaultdict(list)
    for u, p in pages.items():
        by_d[p["desc"]].append(u)
    descs = {u: p["desc"] for u, p in pages.items()}
    for d, us in by_d.items():
        if len(us) < 2 or not d:
            continue
        for u in us:
            ident = _ident(u)
            if ident:
                tail = f" (공고 {ident})"
                descs[u] = d[: max(0, 158 - len(tail))].rstrip() + tail
    for u, p in pages.items():
        if titles[u] != p["title"] or descs[u] != p["desc"]:
            out[u] = (titles[u], descs[u])
    return out


def run(dist, urls, brand):
    pages, raw = {}, {}
    for u in urls:
        f = _path_file(dist, u)
        try:
            h = open(f, encoding="utf-8").read()
        except OSError:
            continue
        t, d = _TITLE.search(h), _DESC.search(h)
        if not t:
            continue
        raw[u] = h
        pages[u] = {"title": html_module.unescape(t.group(1).strip()),
                    "desc": html_module.unescape(d.group(1)) if d else "",
                    "org": _provider(h)}
    changes = disambiguate(pages, brand)
    for u, (nt, nd) in changes.items():
        h = raw[u]
        et, ed = html_module.escape(nt, quote=True), html_module.escape(nd, quote=True)
        h = _TITLE.sub(lambda m: f"<title>{et}</title>", h, count=1)
        h = re.sub(r'<meta property="og:title" content="[^"]*">',
                   lambda m: f'<meta property="og:title" content="{et}">', h, count=1)
        if nd != pages[u]["desc"]:
            h = _DESC.sub(lambda m: f'<meta name="description" content="{ed}">', h, count=1)
            h = re.sub(r'<meta property="og:description" content="[^"]*">',
                       lambda m: f'<meta property="og:description" content="{ed}">', h, count=1)
        open(_path_file(dist, u), "w", encoding="utf-8").write(h)
    return len(changes)
