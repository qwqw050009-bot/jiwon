# -*- coding: utf-8 -*-
"""
정적 사이트 빌더.
python3 src/build.py  → dist/ 에 전체 사이트 생성.

생성물:
  /                     메인 (마감 임박순)
  /urgent/              이번주 마감
  /category/            분야 허브
  /category/{분야}/      분야별
  /region/              지역 허브
  /region/{지역}/        지역별
  /region/{지역}/?field=  분야는 이 목록의 필터. 조합 HTML은 만들지 않고 301
  /region/{지역}/{시군구}/  시군구 허브 (해시태그 정확 일치, 3건 이상)
  /region/{지역}/{시군구}/?field=  시군구×분야도 같은 목록의 필터. 301
  /notice/{id}/         공고 상세
  /bid/                 나라장터 입찰 허브 (지원 목록과 분리)
  /bid/urgent/          이번 주 마감 입찰
  /bid/kind/{종류}/      물품·용역·공사·외자
  /bid/notice/{id}/     입찰 상세
  /about /privacy /terms /contact   (애드센스 필수 페이지)
  sitemap.xml, robots.txt
"""
import hashlib
import html as html_module
import json
import os
import re
import shutil
import sys
from datetime import date, datetime, timedelta, timezone
from email.utils import format_datetime

import deadline as dl

sys.path.insert(0, os.path.dirname(__file__))

from jinja2 import Environment, FileSystemLoader, select_autoescape

import config
import enrich
import sources
import bizinfo
import kstartup
import ics
import pages as static_pages
import guides
import intros
import serp
import districts as distmod
import bid_build
import filters as filt
import urlstate
import landing
import detail_faq
import detail_extra
import seo_dedupe
import browse
import notice_dedupe

ROOT = os.path.join(os.path.dirname(__file__), "..")
DIST = os.path.join(ROOT, "dist")
SITE = config.SITE

# ads.txt 는 애드센스 심사에 쓰이는 루트 파일이라 dist/ 최상단에 항상 둔다.
# pub id 는 config.SITE['adsense_client'] 와 같고, 다른 값을 만들지 않는다.
# static 복사가 빠져도(파일 없음·copytree ignore) 파이썬 상수로 다시 쓴다.
ADS_TXT_LINE = "google.com, pub-2738052782253666, DIRECT, f08c47fec0942fa0"
ADS_TXT_NAMES = ("ads.txt", "app-ads.txt")
STATIC_ROOT_FILES = ("ads.txt", "app-ads.txt", "_headers", "_redirects")


def ads_txt_contents(site=None):
    """
    루트 /ads.txt·/app-ads.txt 본문. 항상 같은 한 줄 + 개행.
    static/ads.txt 는 교차검증만 하고, 없어도 빌드가 만든다.
    site 인자는 호출 호환용이며 다른 pub id 를 만들지 않는다.
    """
    _ = site
    body = ADS_TXT_LINE + "\n"
    src = os.path.join(ROOT, "static", "ads.txt")
    if os.path.exists(src):
        got = open(src, encoding="utf-8").read()
        line = (got.splitlines() or [""])[0].strip()
        if line and line != ADS_TXT_LINE:
            raise SystemExit(
                f"static/ads.txt 첫 줄이 고정 pub 줄과 다릅니다: {line!r}"
            )
    return body


def cf_headers_contents():
    """Cloudflare Pages _headers. 코드에서 항상 만든다. static 복본에 의존하지 않는다."""
    block = (
        "  Content-Type: text/plain; charset=utf-8\n"
        "  Cache-Control: public, max-age=86400\n"
        "  X-Content-Type-Options: nosniff\n"
    )
    return (
        "/ads.txt\n" + block + "\n"
        "/app-ads.txt\n" + block + "\n"
        "/rss.xml\n"
        "  X-Robots-Tag: noindex\n"
        "\n"
        "/rss/*\n"
        "  X-Robots-Tag: noindex\n"
        "  Content-Type: application/rss+xml; charset=utf-8\n"
        "\n"
        "/api/*\n"
        "  X-Robots-Tag: noindex\n"
        "  Cache-Control: no-store\n"
        "\n"
        "/static/*\n"
        # CSS·JS 참조는 모두 ?v=<해시>. og.png·favicon 은 버전이 없어 immutable 은 쓰지 않는다.
        "  Cache-Control: public, max-age=2592000\n"
    )


def cf_redirects_contents():
    """
    Cloudflare Pages _redirects.

    스플랫(홈 200·404.html)은 쓰지 않는다. 정적 ads.txt 가 있어도
    스플랫이 먼저 먹으면 HTML 을 돌려 애드센스가 '찾을 수 없음'을 본다.
    자신으로의 200 은 force(!) 가 아니라서, 파일이 있으면 원본을 그대로 준다.
    """
    return (
        "/ads.txt /ads.txt 200\n"
        "/app-ads.txt /app-ads.txt 200\n"
        # 유료 플랜을 열지 않는다(사업자 없음, 광고 수익만). 예전 요금제 주소는 홈으로.
        "/pricing / 301\n"
        "/pricing/ / 301\n"
    )


def append_list_redirects(dist, pairs):
    """지역×분야 옛 주소를 지역 목록의 field 쿼리로 보낸다.

    파일을 남겨 두면 Cloudflare가 리다이렉트보다 파일을 먼저 준다.
    스플랫은 넣지 않는다. ads.txt 규칙은 그대로 둔다.
    """
    if not pairs:
        return
    lines = []
    for src, dest in pairs:
        if "*" in src or "*" in dest or not src.startswith("/region/"):
            raise SystemExit(f"조합 리다이렉트가 아닙니다: {src} -> {dest}")
        lines.append(f"{src} {dest} 301\n")
    path = os.path.join(dist, "_redirects")
    with open(path, "a", encoding="utf-8", newline="\n") as f:
        f.writelines(lines)


KEEP_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "keep_indexed.json")


def _load_keep():
    """서치콘솔에서 노출·클릭이 있던 상세 URL. 얇아도 noindex 하지 않는다."""
    try:
        return set(json.load(open(KEEP_PATH, encoding="utf-8")))
    except Exception:
        return set()


KEEP_INDEXED = _load_keep()
DUP_ALIAS = {}   # 병합된 중복 공고 id → 대표 공고 id (main 에서 채움)
KNOWN_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "known_detail_urls.json")
MAX_STATIC_REDIRECTS = 2000      # Cloudflare Pages 정적 리다이렉트 한도
DETAIL_DROP_LIMIT = 0.20         # 상세페이지 수가 이 비율 넘게 줄면 빌드 실패


def is_detail(u):
    return u.startswith("/notice/") or u.startswith("/bid/notice/")


def gone_redirects(known, generated, budget):
    """예전에 내보냈던(검색엔진이 아는) 상세 URL 중 이번에 못 만든 것을 목록으로 301.

    최근에 본 것(값이 큰 last_seen)부터 budget 개까지만. 나머지는 404.
    """
    gen = set(generated)
    gone = [(seen or "", u) for u, seen in known.items() if is_detail(u) and u not in gen]
    gone.sort(reverse=True)
    out = []
    for _, u in gone[:max(0, budget)]:
        out.append((u, "/bid/" if u.startswith("/bid/notice/") else "/"))
    return out


def append_gone_redirects(dist, pairs):
    if not pairs:
        return
    path = os.path.join(dist, "_redirects")
    with open(path, "a", encoding="utf-8", newline="\n") as f:
        for src, dest in pairs:
            if "*" in src or not is_detail(src):
                raise SystemExit(f"상세 리다이렉트가 아닙니다: {src}")
            f.write(f"{src} {dest} 301\n")


def count_redirect_rules(dist):
    try:
        lines = open(os.path.join(dist, "_redirects"), encoding="utf-8").read().splitlines()
    except OSError:
        return 0
    return sum(1 for l in lines if l.strip() and not l.lstrip().startswith("#"))


def live_detail_urls(domain, timeout=30):
    """배포 중인 sitemap 의 상세 URL 목록. 못 읽으면 None."""
    try:
        import urllib.request
        req = urllib.request.Request(domain + "/sitemap.xml", headers={"User-Agent": "Mozilla/5.0 (compatible; magampan-build/1.0)"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode("utf-8", "replace")
    except Exception as e:
        print(f"라이브 sitemap 확인 실패(가드는 이전 기록만 사용): {e}")
        return None
    locs = [l.replace(domain, "", 1) for l in re.findall(r"<loc>([^<]+)</loc>", body)]
    return [u for u in locs if is_detail(u)]


def detail_guard(now_count, baselines, limit=DETAIL_DROP_LIMIT):
    """기준값 중 최대 대비 limit 넘게 줄면 오류 메시지, 아니면 None."""
    base = max([b for b in baselines if b] or [0])
    if base and now_count < base * (1 - limit):
        return (f"상세페이지 수가 {base}건 → {now_count}건으로 {limit:.0%} 넘게 줄었습니다. "
                f"아카이브/캡 회귀 의심. 의도한 변경이면 ALLOW_DETAIL_DROP=1 로 빌드하세요.")
    return None


# Pages Functions(호스트 301 미들웨어·/api/alerts)를 거치지 않아도 되는 정적 파일.
# HTML 경로는 모두 미들웨어를 거쳐 *.pages.dev·www → magampan.com 301 이 유지된다.
# 여기 있는 파일은 별칭 호스트에서도 200 으로 나가지만 HTML 이 아니라 중복 색인 대상이 아니다.
ROUTES_EXCLUDE = (
    "/static/*", "/calendar/*", "/notices.json", "/bids.json",
    "/ads.txt", "/app-ads.txt", "/promo.txt",
    "/naver0defc699223f8ffa807d6d0bc99bb36c.html",
)


def routes_json_contents():
    excl = list(ROUTES_EXCLUDE) + [f"/{config.INDEXNOW_KEY}.txt"]
    return json.dumps({"version": 1, "include": ["/*"], "exclude": excl}, indent=2) + "\n"


_PRE = re.compile(r"<(pre|textarea)\b", re.I)


def minify_html(text):
    """줄 앞뒤 공백과 빈 줄만 없앤다. 줄바꿈은 남겨 인라인 요소 사이 간격·렌더링이 같다."""
    if _PRE.search(text):
        return text
    return "\n".join(l.strip() for l in text.split("\n") if l.strip()) + "\n"


def minify_dist_html(dist):
    before = after = 0
    for root, _, files in os.walk(dist):
        for name in files:
            if not name.endswith(".html"):
                continue
            p = os.path.join(root, name)
            with open(p, encoding="utf-8") as f:
                raw = f.read()
            out = minify_html(raw)
            before += len(raw.encode("utf-8"))
            after += len(out.encode("utf-8"))
            if out != raw:
                with open(p, "w", encoding="utf-8", newline="\n") as f:
                    f.write(out)
    return before, after


def emit_root_text_files(dist):
    """ads.txt·app-ads.txt·_headers·_redirects 를 dist 루트에 항상 쓴다."""
    os.makedirs(dist, exist_ok=True)
    body = ads_txt_contents()
    for name in ADS_TXT_NAMES:
        with open(os.path.join(dist, name), "w", encoding="utf-8", newline="\n") as f:
            f.write(body)
    with open(os.path.join(dist, "_headers"), "w", encoding="utf-8", newline="\n") as f:
        f.write(cf_headers_contents())
    with open(os.path.join(dist, "_redirects"), "w", encoding="utf-8", newline="\n") as f:
        f.write(cf_redirects_contents())
    with open(os.path.join(dist, "_routes.json"), "w", encoding="utf-8", newline="\n") as f:
        f.write(routes_json_contents())
    assert_ads_delivery(dist)


def assert_ads_delivery(dist):
    """빌드가 ads.txt 없이 끝나지 않게 한다. HTML·BOM·다른 pub 은 실패."""
    for name in ADS_TXT_NAMES:
        path = os.path.join(dist, name)
        if not os.path.isfile(path):
            raise SystemExit(f"{name} 가 dist 루트에 없습니다")
        raw = open(path, "rb").read()
        if raw.startswith(b"\xef\xbb\xbf"):
            raise SystemExit(f"{name} 에 BOM 이 있습니다")
        low = raw.lower()
        if b"<html" in low or b"<!doctype" in low:
            raise SystemExit(f"{name} 가 HTML 처럼 보입니다")
        text = raw.decode("ascii")
        if not text.endswith("\n"):
            raise SystemExit(f"{name} 끝에 개행이 없습니다")
        if text.splitlines()[0] != ADS_TXT_LINE:
            raise SystemExit(f"{name} 첫 줄이 고정 pub 줄이 아닙니다: {text!r}")
    headers = open(os.path.join(dist, "_headers"), encoding="utf-8").read()
    for needle in (
        "/ads.txt", "/app-ads.txt",
        "Content-Type: text/plain; charset=utf-8",
        "Cache-Control: public, max-age=86400",
        "X-Content-Type-Options: nosniff",
    ):
        if needle not in headers:
            raise SystemExit(f"dist/_headers 에 {needle!r} 가 없습니다")
    redirects = open(os.path.join(dist, "_redirects"), encoding="utf-8").read()
    for bad in ("/* /index.html", "/* /404.html", "/ads.txt /index.html",
                "/ads.txt /404.html"):
        if bad in redirects.replace("  ", " "):
            raise SystemExit(f"dist/_redirects 가 ads.txt 를 HTML 로 삼킵니다: {bad}")
    if "/ads.txt" not in redirects:
        raise SystemExit("dist/_redirects 에 /ads.txt 규칙이 없습니다")

env = Environment(
    loader=FileSystemLoader(os.path.join(ROOT, "templates")),
    autoescape=select_autoescape(["html"]),
)


def _static_version():
    """
    style.css/filter.js/scrap.js 내용 해시. CSS/JS를 고치고 배포해도
    파일명(URL)이 그대로라 CDN·브라우저 캐시가 예전 버전을 계속 보여주는
    문제가 있었다(실제로 한 번 겪음). ?v=해시를 붙여서 내용이 바뀔 때만
    URL도 바뀌게 해 캐시를 자연스럽게 무효화한다.
    """
    h = hashlib.md5()
    for name in ("style.css", "filter.js", "scrap.js", "bid_filter.js", "card.js",
                 "state.js", "alert.js", "suggest.js", "compare.js"):
        p = os.path.join(ROOT, "static", name)
        if os.path.exists(p):
            with open(p, "rb") as f:
                h.update(f.read())
    return h.hexdigest()[:10]


env.globals["asset_v"] = _static_version()
env.globals["bid_kinds"] = config.BID_KINDS
env.globals["bid_has_regions"] = False
env.globals["amount_bands"] = filt.AMOUNT_BANDS
env.globals["landing"] = landing.context()
env.globals["formspree_url"] = config.formspree_url()

URLS = []
URL_META = {}


NOINDEX_DETAIL = []   # 얇은 상세페이지: HTML 은 남기되 sitemap 제외·noindex


# 이번 빌드가 직접 쓴 HTML 파일(dist 기준 상대 경로). stray_html_files() 가드용.
WRITTEN = set()


def write(path, html, index=True, lastmod=None, changefreq=None, priority=None):
    """path='/region/seoul/' → dist/region/seoul/index.html"""
    out = os.path.join(DIST, path.strip("/"), "index.html") if path != "/" \
        else os.path.join(DIST, "index.html")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    WRITTEN.add(os.path.relpath(out, DIST).replace(os.sep, "/"))
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    if index:
        URLS.append(path)
        URL_META[path] = {
            "lastmod": lastmod,
            "changefreq": changefreq,
            "priority": priority,
        }


# write() 를 거치지 않고 일부러 두는 HTML. static/ 아래 파일도 허용한다.
EXPECTED_EXTRA_HTML = {"404.html", "naver0defc699223f8ffa807d6d0bc99bb36c.html"}


def stray_html_files(dist, written, extra=EXPECTED_EXTRA_HTML):
    """
    이번 빌드가 만들지 않은 HTML 이 dist 에 있으면 그 목록을 돌려준다.
    예전 /bid/ 처럼 오래된 bid.html 이 남아 Cloudflare Pages 가 /bid 요청을
    그쪽으로 보내는 일을 막는다(Pages 는 /bid 를 bid.html 로도 찾는다).
    """
    out = []
    for root, _dirs, files in os.walk(dist):
        for name in files:
            if not name.endswith(".html"):
                continue
            rel = os.path.relpath(os.path.join(root, name), dist).replace(os.sep, "/")
            if rel in written or rel in extra or rel.startswith("static/"):
                continue
            out.append(rel)
    return sorted(out)


def _date_of(row, fallback=None):
    """공고 날짜 필드에서 YYYY-MM-DD만. 없는 날짜를 짓지 않는다."""
    for key in ("posted_at", "updated", "created", "open_dt",
                "apply_end", "close_dt", "collected_at"):
        v = str((row or {}).get(key) or "")[:10]
        if re.match(r"^\d{4}-\d{2}-\d{2}$", v):
            return v
    return fallback


def minify_css(text):
    """주석·중복 공백만 줄인다. calc() 수식 기호는 건드리지 않는다."""
    text = re.sub(r"/\*.*?\*/", "", text or "", flags=re.S)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*", "\n", text)
    text = re.sub(r"\s*([{}:;,])\s*", r"\1", text)
    return text.strip() + "\n"


def fill_defaults(a):
    """실데이터에 없는 필드를 채운다. 목업/실데이터 스키마 차이를 흡수."""
    a.setdefault("amount", "")
    parsed = enrich.amount_of(a)
    # ', 원'처럼 숫자가 빠진 원문 표기는 금액으로 보지 않는다(카드·상세·FAQ 모두).
    if not enrich.valid_amount(a["amount"]):
        a["amount"] = parsed or "공고문 참조"
    a["amount_card"] = enrich.amount_card(a)
    a.setdefault("target", "")
    a.setdefault("org", "")
    a.setdefault("overview", "")
    a.setdefault("points", [])
    a.setdefault("method", "")
    a.setdefault("contact", "")
    a.setdefault("period_type", "dated")
    a.setdefault("period_raw", "")
    a.setdefault("apply_start", "")
    a.setdefault("apply_end", "")
    a.setdefault("detail_url", "https://www.bizinfo.go.kr/")
    return a


def decorate(a, collected_at=None, today=None):
    """D-day 표시용 값 계산. 상시 접수는 별도 표기. 마감 배지와 D-n을 동시에 쓰지 않는다."""
    today = today or dl.today_kst()
    a["status"] = dl.status_of(a, today=today)
    a["status_label"] = dl.status_label(a["status"])
    a["deadline_line"] = dl.deadline_line(a)
    a["time_known"] = dl.time_known(a.get("apply_end") or "")
    a["source"] = a.get("source") or filt.source_of(a)
    a["source_label"] = filt.source_label(a)
    a["notice_no"] = filt.notice_no(a)
    a["posted_at"] = filt.posted_at(a)
    if collected_at:
        a["collected_at"] = collected_at
    a["cls"], a["dlabel"], a["dsub"] = dl.dday_badge(a)
    a["is_correction"] = filt.is_correction(a)
    a["blurb"] = intros.blurb_of(a)
    a["signals"] = enrich.notice_signals(a)
    who = ((a.get("target") or "").splitlines() or [""])[0].strip()
    a["target_short"] = (who[:23].rstrip(" ·,/") + "…") if len(who) > 24 else who
    a["ai"] = enrich.ground_ai(enrich.heal_broken_josa(a.get("ai"), a), a)
    label, note, pill = enrich.region_display(a)
    a["region_label"] = label
    a["region_note"] = note
    a["region_pill"] = pill
    return a


def home_sections(rows, new_rows, week):
    """홈 섹션. 앞에서 이미 보여 준 공고는 다음 섹션에 다시 넣지 않는다."""
    shown = set()
    sections = []
    if week:
        items = week[:5]
        shown.update(a.get("id") for a in items)
        sections.append({
            "title": "이번 주에 닫히는 공고", "items": items,
            "href": "/urgent/", "total": len(week),
        })
    fresh = [a for a in new_rows if a.get("id") not in shown][:5]
    if fresh:
        shown.update(a.get("id") for a in fresh)
        sections.append({
            "title": "오늘 새로 올라온 공고", "items": fresh,
            "href": "/new/", "total": len(new_rows),
        })
    open_items = [a for a in rows if a.get("is_open") and a.get("id") not in shown][:5]
    if open_items:
        sections.append({
            "title": "접수 중인 공고", "items": open_items,
            "href": "/all/", "total": sum(1 for a in rows if a.get("is_open")),
        })
    return sections


def tally(items):
    return {
        "today": sum(1 for a in items if a["dday"] == 0),
        "urgent": sum(1 for a in items if 0 <= a["dday"] <= 7),
        "soon": sum(1 for a in items if 7 < a["dday"] <= 14
                    and a.get("period_type") != "always"),
        "open": sum(1 for a in items if a["dday"] >= 0),
    }


# 마감 후 7일이 지나면 목록에서는 빠지지만(sources.load), 상세페이지 URL은
# 검색엔진이 이미 색인해뒀을 수 있다. 여기서 죽이면 쌓아둔 색인/백링크가
# 날아가므로, 마감된 공고도 별도 아카이브에 최대 ARCHIVE_DAYS일 보관하며
# "마감됨 + 유사 공고 추천"으로 상세페이지를 계속 살려둔다.
ARCHIVE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "archive.json")
ARCHIVE_DAYS = 180
# 소스 전환(mock↔실데이터)이나 ID 생성 로직 변경 등으로 오늘 목록과 아카이브가
# 통째로 안 겹치는 사고가 나면 상세페이지가 수백~수천 개로 폭증할 수 있다.
# 그런 경우를 대비한 경고선. 180일 보관 정책상 2,000건대는 정상이므로
# (300 상한이 마감 공고 상세를 잘라 404를 냈다) 잘라내지 않고 경고만 남긴다.
MAX_ARCHIVED = 5000

ARCHIVE_FIELDS = (
    "id", "title", "category", "region", "org", "target", "amount",
    "method", "contact", "detail_url", "apply_start", "apply_end",
    "period_type", "period_raw", "points", "overview", "ai",
)


def _load_archive():
    try:
        with open(ARCHIVE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_archive(arc):
    with open(ARCHIVE_PATH, "w", encoding="utf-8") as f:
        json.dump(arc, f, ensure_ascii=False)


def archived_notices(rows, today):
    """
    오늘 빌드에 없는(=마감 7일 초과로 빠진) 과거 공고 중,
    마감일로부터 ARCHIVE_DAYS일이 안 지난 것만 살려서 반환한다.
    상시(period_type=always) 공고는 마감일이 없어 아카이브 대상에서 뺀다.
    """
    arc = _load_archive()
    live_ids = {a["id"] for a in rows}
    for a in rows:
        if a.get("period_type") != "always":
            arc[a["id"]] = {k: a.get(k) for k in ARCHIVE_FIELDS}

    kept, out = {}, []
    for aid, a in arc.items():
        if sources.is_excluded_title(a.get("title")):
            continue          # 포상·표창 등 지원사업이 아닌 공고는 아카이브에도 두지 않는다
        try:
            end = date.fromisoformat(a.get("apply_end") or "")
        except Exception:
            continue
        if (today - end).days > ARCHIVE_DAYS:
            continue          # 너무 오래돼서 버림
        kept[aid] = a
        if aid in live_ids or str(aid) in DUP_ALIAS:
            continue          # 오늘 목록에 이미 있으면 아카이브 페이지 별도 생성 불필요
        row = fill_defaults(dict(a))
        row["dday"] = (today - end).days * -1
        row["is_open"] = False
        row["is_closed"] = True
        row["is_new"] = False
        row = decorate(row, collected_at=env.globals.get("collected_at"), today=today)
        # 아카이브에 얼어붙은 "ai" 스냅샷도 옛날 조사 버그 문구를 담고
        # 있을 수 있다. enrich_all()을 다시 거치지 않는 경로라 여기서도
        # 같은 방식으로(비용 없이) 고쳐준다.
        row["ai"] = enrich.heal_broken_josa(row.get("ai"), row)
        out.append(row)

    _save_archive(kept)
    if len(out) > MAX_ARCHIVED:
        # 마감일이 가장 최근인 것부터 우선 유지 (오래된 것부터 잘라낸다)
        print(f"경고: 아카이브 대상이 {len(out)}건으로 경고선 {MAX_ARCHIVED}건을 넘었습니다 "
              f"(소스 전환/ID 생성 로직 변경 의심). 자르지 않고 모두 생성합니다.")
    return out


def howto_jsonld(h1, desc, content_html):
    """
    가이드 본문의 <h2>단계 제목</h2><p>설명</p> 구조를 그대로 HowTo 구조화
    데이터로 옮긴다. 페이지에 보이는 순서/문구를 그대로 재사용할 뿐, 없는
    단계를 지어내지 않는다 (구글 HowTo 가이드라인 — 화면과 일치해야 함).
    "1단계 — ", "2단계 — " 형태의 h2만 단계로 인정한다.
    """
    steps = []
    for m in re.finditer(r"<h2>(\d단계\s*—\s*[^<]+)</h2>\s*<p>(.*?)</p>", content_html, re.S):
        name = html_module.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip()
        text = html_module.unescape(re.sub(r"<[^>]+>", " ", m.group(2))).strip()
        steps.append({"@type": "HowToStep", "name": name, "text": text[:300]})
    if not steps:
        return None
    return json.dumps({
        "@context": "https://schema.org", "@type": "HowTo",
        "name": h1, "description": desc, "step": steps,
    }, ensure_ascii=False)


def faq_jsonld(a):
    """공고 상세 FAQPage. 화면에 보이는 notice_faqs 문구와 같다."""
    return intros.faq_jsonld(detail_faq.notice_faqs(a))


SLUGMAP = json.dumps({
    "region": {r["name"]: r["slug"] for r in config.REGIONS},
    "category": {c["name"]: c["slug"] for c in config.CATEGORIES},
}, ensure_ascii=False)


def _crumbs_kw(crumbs):
    """page.html 류 렌더에 넘길 빵가루(화면) + BreadcrumbList(JSON-LD)."""
    return {"crumbs": crumbs, "crumb_jsonld": crumb_ld(crumbs)}


def crumb_ld(crumbs):
    """화면에 보이는 빵가루와 같은 순서의 BreadcrumbList JSON-LD."""
    if not crumbs:
        return ""
    els = []
    for i, c in enumerate(crumbs, 1):
        row = {"@type": "ListItem", "position": i, "name": c["name"]}
        if c.get("url"):
            row["item"] = SITE["domain"] + c["url"]
        els.append(row)
    return json.dumps({
        "@context": "https://schema.org", "@type": "BreadcrumbList",
        "itemListElement": els,
    }, ensure_ascii=False)


def website_ld():
    """홈 전용 WebSite + SearchAction. 검색 실주소는 헤더 폼과 같다."""
    return json.dumps({
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": SITE["name"],
        "url": SITE["domain"] + "/",
        "potentialAction": {
            "@type": "SearchAction",
            "target": {
                "@type": "EntryPoint",
                "urlTemplate": SITE["domain"] + "/all/?q={search_term_string}",
            },
            "query-input": "required name=search_term_string",
        },
    }, ensure_ascii=False)


def render_list(path, h1, lede, items, title=None, desc=None, blocks=None,
                intro=None, intro_paras=None, faqs=None, faq_jsonld=None,
                sel_region=None, sel_category=None, sel_district=None, today=0,
                new_cnt=0, ics_url=None, limit=None, more_href=None,
                sections=None, tally_items=None, beginner_cta=False,
                crumbs=None, website_jsonld="", home_guides=None,
                list_guides=None, region_n=0, show_rail=True):
    n_for_ads = len(tally_items) if (tally_items is not None and sections) else len(items)
    ad_top, ad_mid_after, ad_bottom = intros.resolve_ads(
        intros.ad_plan(n_for_ads, has_sections=bool(sections),
                       hub=path.startswith(("/region/", "/category/"))), SITE)
    crumbs = crumbs or []
    if intro_paras and path.startswith(("/region/", "/category/")) and items:
        st = detail_extra.list_stats(tally_items if tally_items is not None else items)
        if st:
            intro_paras = list(intro_paras) + [html_module.escape(st)]
    pool = tally_items if tally_items is not None else items
    if show_rail:
        today_items = filt.today_rail(pool)
        week_rail = [a for a in filt.urgent_rail(pool) if a.get("dday") != 0]
    else:
        today_items, week_rail = [], []
    today_n = today or sum(1 for a in pool if a.get("dday") == 0)
    related = intros.related_hubs(
        path=path, region=sel_region, category=sel_category, district=sel_district,
    )
    html = env.get_template("list.html").render(
        site=SITE, path=path, section="support",
        page="home" if path == "/" else "list",
        title=title or f"{h1} | {SITE['name']}",
        desc=desc or lede, h1=h1, lede=lede, items=items,
        tally=tally(tally_items if tally_items is not None else items),
        blocks=blocks or [], intro=intro, intro_paras=intro_paras or [],
        faqs=faqs or [], faq_jsonld=faq_jsonld or "",
        ad_top=ad_top, ad_mid_after=ad_mid_after, ad_bottom=ad_bottom,
        all_regions=config.REGIONS, all_categories=config.CATEGORIES,
        sel_region=sel_region, sel_category=sel_category,
        sel_district=sel_district, slugmap=SLUGMAP,
        today=today_n, new_cnt=new_cnt, ics_url=ics_url,
        limit=limit or 0, more_href=more_href or "", sections=sections or [],
        beginner_cta=beginner_cta, crumbs=crumbs, crumb_jsonld=crumb_ld(crumbs),
        website_jsonld=website_jsonld or "", home_guides=home_guides or [],
        list_guides=list_guides or [],
        urgent_rail=week_rail,
        today_rail=today_items,
        related_hubs=related,
        source_tally=filt.source_tally(pool),
        collected_at=env.globals.get("collected_at") or "",
        alert_email=SITE.get("email") or "",
        region_n=region_n,
        # 빈 목록에는 자동 광고도 싣지 않는다 (애드센스: 콘텐츠 없는 화면 광고 금지).
        no_ads=not items and not sections,
    )
    write(path, html)


RSS_MAX = 50
COMBO_MIN = 3     # 지역×분야 허브를 만드는 최소 접수 중 공고 수


def _rss_date(a, fallback):
    """공고 게시일(없으면 빌드 시각)을 RFC 822 로. 없는 날짜를 짓지 않는다."""
    d = _date_of(a)
    if d:
        try:
            return format_datetime(datetime.strptime(d, "%Y-%m-%d").replace(tzinfo=timezone(timedelta(hours=9))))
        except ValueError:
            pass
    return fallback


def rss_xml(title, link, desc, items, now_rfc822):
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<rss version="2.0"><channel>',
           f"<title>{html_module.escape(title)}</title>",
           f"<link>{link}</link>",
           f"<description>{html_module.escape(desc)}</description>",
           "<language>ko</language>",
           f"<lastBuildDate>{now_rfc822}</lastBuildDate>"]
    for a in items:
        t = html_module.escape(f"[{a['region']}] {a['title']}")
        d = html_module.escape((a.get("ai") or {}).get("summary", ""))
        url = f"{SITE['domain']}/notice/{a['id']}/"
        out.append(
            f"<item><title>{t}</title><link>{url}</link>"
            f'<guid isPermaLink="true">{url}</guid>'
            f"<pubDate>{_rss_date(a, now_rfc822)}</pubDate>"
            f"<description>{d}</description></item>"
        )
    out.append("</channel></rss>")
    return "\n".join(out)


def _feed_pick(items):
    live = [a for a in items if a.get("is_open")]
    return sorted(live, key=lambda a: (not a.get("is_new"), a["dday"]))[:RSS_MAX]


def write_rss_feeds(rows, by_reg, by_cat, regs, cats):
    """/rss.xml(전체), /rss/region/<slug>.xml, /rss/category/<slug>.xml. 반환: 만든 피드 수."""
    now_rfc822 = format_datetime(datetime.now(timezone.utc))
    with open(os.path.join(DIST, "rss.xml"), "w", encoding="utf-8") as f:
        f.write(rss_xml(SITE["name"], f"{SITE['domain']}/", SITE["tagline"], _feed_pick(rows), now_rfc822))
    n = 1
    for kind, groups, meta in (("region", by_reg, regs), ("category", by_cat, cats)):
        os.makedirs(os.path.join(DIST, "rss", kind), exist_ok=True)
        for name, items in groups.items():
            picked = _feed_pick(items)
            if not picked or name not in meta:
                continue
            slug = meta[name]["slug"]
            label = f"{name} 지원사업" if kind == "region" else f"{name} 분야 지원사업"
            with open(os.path.join(DIST, "rss", kind, f"{slug}.xml"), "w", encoding="utf-8") as f:
                f.write(rss_xml(f"{label} 마감 · {SITE['name']}", f"{SITE['domain']}/{kind}/{slug}/",
                                f"{label} 공고를 새 공고 먼저, 마감이 가까운 순으로 담은 피드입니다.",
                                picked, now_rfc822))
            n += 1
    return n


def main():
    # 빌드 전에 출력 폴더를 통째로 비운다(이전 빌드의 잔재 HTML 이 배포되지 않게).
    if os.path.exists(DIST):
        shutil.rmtree(DIST)
    os.makedirs(DIST)
    WRITTEN.clear()
    browse.WRITTEN.clear()
    shutil.copytree(
        os.path.join(ROOT, "static"), os.path.join(DIST, "static"),
        ignore=shutil.ignore_patterns(*STATIC_ROOT_FILES),
    )
    css_path = os.path.join(DIST, "static", "style.css")
    if os.path.isfile(css_path):
        raw = open(css_path, encoding="utf-8").read()
        open(css_path, "w", encoding="utf-8").write(minify_css(raw))
    emit_root_text_files(DIST)

    collected_at = dl.collected_stamp()
    env.globals["collected_at"] = collected_at
    env.globals["alert_email"] = SITE.get("email") or ""
    env.globals["formspree_url"] = config.formspree_url()

    # 키가 있으면 실데이터, 없으면 목업으로 자동 전환.
    # 로컬에서 키 없이 돌려도 그대로 빌드된다.
    key = os.environ.get("BIZINFO_KEY", "").strip()
    cache_path = os.path.join(ROOT, "data", "api_cache.json")
    if key:
        print("실데이터 모드 (기업마당 API)")
        rows = sources.load(bizinfo.BizinfoSource(key))
    elif os.environ.get("MAGAMPAN_USE_CACHE", "").strip() and os.path.exists(cache_path):
        # 로컬에서 시군구 페이지를 실데이터 스키마(tags)로 검증할 때.
        # 키가 없는 기본 경로는 기존처럼 목업이다.
        print("캐시 모드 (data/api_cache.json)")
        rows = sources.load(sources.JsonSource(cache_path))
    else:
        print("목업 모드 (BIZINFO_KEY 없음)")
        rows = sources.load()

    # K-Startup은 창업 분야 데이터 깊이 보강용 선택적 소스.
    # KSTARTUP_KEY가 없으면 이 블록은 그냥 건너뛰고 기존과 완전히 동일하게 빌드된다.
    ks_key = os.environ.get("KSTARTUP_KEY", "").strip()
    if ks_key:
        ks_raw = kstartup.KstartupSource(ks_key).fetch()
        before = len(ks_raw)
        rows, dup_cnt = sources.merge_extra(rows, ks_raw)
        print(f"K-Startup 보강: {before - dup_cnt}건 추가 (제목 중복 {dup_cnt}건 제외, 총 {before}건 수신)")

    # 같은 공고(정규화 제목+소관·수행기관+마감)가 여러 번 들어오면 하나만 남기고 나머지는 301.
    rows, alias = notice_dedupe.dedupe(rows, KEEP_INDEXED)
    DUP_ALIAS.clear()
    DUP_ALIAS.update(alias)
    print(f"같은 공고 병합: {len(alias)}건을 대표 공고로 301")

    use_llm = bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())
    rows = enrich.enrich_all(rows, use_llm=use_llm)
    rows = [decorate(fill_defaults(a), collected_at=collected_at) for a in rows]

    # 어제 대비 신규 공고 감지 (data/seen.json 과 비교)
    seen_path = os.path.join(ROOT, "data", "seen.json")
    try:
        with open(seen_path, encoding="utf-8") as f:
            seen = set(json.load(f))
    except Exception:
        seen = set()
    first_run = not seen
    for a in rows:
        a["is_new"] = (not first_run) and a["id"] not in seen
    with open(seen_path, "w", encoding="utf-8") as f:
        json.dump(sorted({a["id"] for a in rows} | seen), f)
    new_cnt = sum(1 for a in rows if a["is_new"])

    cats = {c["name"]: c for c in config.CATEGORIES}
    regs = {r["name"]: r for r in config.REGIONS}
    by_cat = {n: [a for a in rows if a["category"] == n] for n in cats}
    by_reg = {n: [a for a in rows if a["region"] == n] for n in regs}
    # 지역·분야 RSS 피드 주소(접수 중 공고가 있는 것만 만든다). 목록 페이지 <head>·본문 링크에 쓴다.
    env.globals["rss_feeds"] = {
        **{f"/region/{regs[n]['slug']}/": f"/rss/region/{regs[n]['slug']}.xml"
           for n, v in by_reg.items() if any(a.get("is_open") for a in v)},
        **{f"/category/{cats[n]['slug']}/": f"/rss/category/{cats[n]['slug']}.xml"
           for n, v in by_cat.items() if any(a.get("is_open") for a in v)},
    }
    # 시군구는 허용 목록×해시태그 정확 일치만. 3건 미만은 페이지를 만들지 않는다.
    by_district = distmod.grouped(rows)
    n_dist_hubs = sum(len(v) for v in by_district.values())
    if n_dist_hubs:
        print(f"시군구 허브 {n_dist_hubs}곳 (허용 목록 {len(distmod.DISTRICTS)}개 중 {distmod.MIN_COUNT}건 이상)")

    cat_chips = [{"name": n, "url": f"/category/{cats[n]['slug']}/", "count": len(v)}
                 for n, v in by_cat.items() if v]
    reg_chips = [{"name": n, "url": f"/region/{regs[n]['slug']}/", "count": len(v)}
                 for n, v in by_reg.items() if v]
    hub = [{"title": "분야로 찾기", "items": cat_chips},
           {"title": "지역으로 찾기", "items": reg_chips}]

    # 메인: 요약판 (섹션마다 5건 + 더보기). 같은 카드는 한 섹션에만.
    new_rows = [a for a in rows if a["is_new"]]
    week = [a for a in rows if 0 <= a["dday"] <= 7]
    sections = home_sections(rows, new_rows, week)

    today_n = sum(1 for a in rows if a["dday"] == 0)
    week_n = sum(1 for a in rows if 0 <= a["dday"] <= 7)
    open_n = sum(1 for a in rows if a.get("is_open"))
    render_list(
        "/", serp.home_h1(),
        serp.home_lede(),
        [],
        title=serp.home_title(rows),
        desc=serp.home_desc(rows),
        intro=intros.home_intro(today_n, week_n, open_n),
        blocks=hub, today=today_n, new_cnt=new_cnt,
        ics_url="/calendar/all.ics", sections=sections, more_href="/all/",
        tally_items=rows, beginner_cta=True, website_jsonld=website_ld(),
        home_guides=intros.HOME_GUIDES,
        faqs=intros.home_faqs(today_n, week_n, open_n),
        faq_jsonld=intros.faq_jsonld(intros.home_faqs(today_n, week_n, open_n)),
        region_n=len(reg_chips),
        show_rail=False,
    )

    # 전체 목록
    render_list("/all/", serp.all_h1(),
                serp.all_lede(rows),
                rows, limit=20,
                title=serp.all_title(rows),
                desc=serp.all_desc(rows),
                blocks=hub, list_guides=intros.list_guides())

    # 신규
    if new_rows:
        render_list("/new/", serp.new_h1(),
                    serp.new_lede(new_rows), new_rows, limit=20, blocks=hub,
                    title=serp.new_title(new_rows),
                    desc=serp.new_desc(new_rows),
                    list_guides=intros.list_guides())

    # 스크랩·알림 조건 (색인 제외, 개인화)
    write("/scrap/", env.get_template("scrap.html").render(
        site=SITE, path="/scrap/", page="scrap", section="support",
        title=serp.scrap_title(),
        desc=serp.scrap_desc(),
        noindex=True, no_ads=True,
        crumbs=[{"name": "홈", "url": "/"}, {"name": "스크랩", "url": "/scrap/"}],
    ), index=False)
    write("/alerts/", env.get_template("alerts.html").render(
        site=SITE, path="/alerts/", page="alerts", section="support",
        title=serp.alerts_title(),
        desc=serp.alerts_desc(),
        noindex=True, no_ads=True,
        crumbs=[{"name": "홈", "url": "/"}, {"name": "알림 조건", "url": "/alerts/"}],
    ), index=False)

    # 마감임박
    urgent = [a for a in rows if 0 <= a["dday"] <= 7]
    render_list("/urgent/", serp.urgent_h1(),
                serp.urgent_lede(urgent), urgent, limit=20, blocks=hub,
                title=serp.urgent_title(urgent),
                desc=serp.urgent_desc(urgent),
                list_guides=intros.list_guides())

    # 허브
    # 예전엔 items=[] 로 넘겨서 상단 통계는 실제 숫자가 뜨는데 본문은
    # "지금 접수 중인 공고가 없습니다"만 고정으로 뜨는 버그가 있었다
    # (filter.js가 사용자가 필터를 건드리기 전엔 목록을 안 채우는 구조라,
    # 서버 렌더 items가 비어있으면 JS 유무와 상관없이 항상 빈 화면으로
    # 보임 — CLAUDE.md 4번 규칙 "JS 꺼져도 서버 렌더 목록이 보여야 한다"
    # 위반이기도 했다). 분야·지역 칩 아래에 실제 목록도 함께 보여준다.
    render_list(
        "/category/", serp.category_hub_h1(),
        serp.category_hub_lede(),
        rows, limit=20, blocks=[hub[0]],
        intro=intros.category_hub_intro(len(rows)),
        faqs=intros.hub_faqs("category", len(rows)),
        faq_jsonld=intros.faq_jsonld(intros.hub_faqs("category", len(rows))),
        list_guides=intros.list_guides(),
        crumbs=[{"name": "홈", "url": "/"}, {"name": "분야", "url": "/category/"}],
        title=serp.category_hub_title(),
        desc=serp.category_hub_desc(len(rows)),
    )
    render_list(
        "/region/", serp.region_hub_h1(),
        serp.region_hub_lede(),
        rows, limit=20, blocks=[hub[1]],
        intro=intros.region_hub_intro(len(rows), len(regs)),
        faqs=intros.hub_faqs("region", len(rows), len(regs)),
        faq_jsonld=intros.faq_jsonld(intros.hub_faqs("region", len(rows), len(regs))),
        list_guides=intros.list_guides(),
        crumbs=[{"name": "홈", "url": "/"}, {"name": "지역", "url": "/region/"}],
        title=serp.region_hub_title(),
        desc=serp.region_hub_desc(len(rows), len(regs)),
    )

    # 지역×분야 조합 허브: 접수 중 공고가 COMBO_MIN 건 이상인 조합만 /region/{지역}/{분야}/ 페이지를 만든다.
    # 그보다 적은 조합의 옛 주소는 파일을 만들지 않고 지역 목록 필터(?field=)로 301 한다.
    combo_redirects = []
    combo_pages = {}
    for rname, r in regs.items():
        for cn, c in cats.items():
            citems = [a for a in by_reg[rname] if a["category"] == cn]
            if sum(1 for a in citems if a.get("is_open")) >= COMBO_MIN:
                combo_pages[(rname, cn)] = (f"/region/{r['slug']}/{c['slug']}/", citems)

    def combo_href(rname, cn):
        hit = combo_pages.get((rname, cn))
        return hit[0] if hit else urlstate.field_href(f"/region/{regs[rname]['slug']}/", cn)

    # 분야별
    for name, c in cats.items():
        items = by_cat[name]
        if not items:
            continue
        sub = [{"name": f"{r} {name}",
                "url": combo_href(r, name),
                "count": len([a for a in items if a["region"] == r])}
               for r in regs if any(a["region"] == r for a in items)]
        other_cats = [x for x in cat_chips if x["name"] != name]
        render_list(
            f"/category/{c['slug']}/", serp.category_h1(name),
            serp.category_lede(name, c, items),
            items,
            title=serp.category_title(name, items),
            desc=serp.category_desc(name, c, items),
            intro_paras=intros.category_page_intro(name, c, items),
            faqs=intros.category_page_faqs(name, c, items),
            faq_jsonld=intros.faq_jsonld(intros.category_page_faqs(name, c, items)),
            list_guides=intros.list_guides(category=name),
            blocks=[{"title": "다른 분야", "items": other_cats},
                    {"title": "지역으로 좁히기", "items": sub}],
            sel_category=name, ics_url=f"/calendar/{c['slug']}.ics", limit=20,
            crumbs=[{"name": "홈", "url": "/"},
                    {"name": "분야", "url": "/category/"},
                    {"name": name, "url": f"/category/{c['slug']}/"}],
        )

    # 지역별 + 지역x분야 롱테일
    for rname, r in regs.items():
        items = by_reg[rname]
        if not items:
            continue
        sub = [{"name": f"{rname} {cn}",
                "url": combo_href(rname, cn),
                "count": len([a for a in items if a["category"] == cn])}
               for cn in cats if any(a["category"] == cn for a in items)]
        other_regs = [x for x in reg_chips if x["name"] != rname]
        d_chips = [
            {"name": d["name_ko"],
             "url": f"/region/{r['slug']}/{d['slug']}/",
             "count": len(ditems)}
            for d, ditems in by_district.get(rname, [])
        ]
        sido_blocks = [{"title": "다른 지역", "items": other_regs}]
        if d_chips:
            sido_blocks.append({"title": "시군구로 좁히기", "items": d_chips})
        sido_blocks.append({"title": "분야로 좁히기", "items": sub})
        render_list(
            f"/region/{r['slug']}/", serp.region_h1(rname),
            serp.region_lede(rname, items),
            items,
            title=serp.region_title(rname, items),
            desc=serp.region_desc(rname, items),
            intro_paras=intros.region_page_intro(rname, items),
            faqs=intros.region_page_faqs(rname, items),
            faq_jsonld=intros.faq_jsonld(intros.region_page_faqs(rname, items)),
            list_guides=intros.list_guides(region=rname),
            blocks=sido_blocks,
            sel_region=rname, ics_url=f"/calendar/{r['slug']}.ics", limit=20,
            crumbs=[{"name": "홈", "url": "/"},
                    {"name": "지역", "url": "/region/"},
                    {"name": rname, "url": f"/region/{r['slug']}/"}],
        )
        for cn, c in cats.items():
            if not any(a["category"] == cn for a in items):
                continue
            hit = combo_pages.get((rname, cn))
            if not hit:
                combo_redirects.append((
                    f"/region/{r['slug']}/{c['slug']}/",
                    urlstate.field_href(f"/region/{r['slug']}/", cn),
                ))
                continue
            cpath, citems = hit
            c_paras, c_faqs = intros.build(rname, cn, c, citems)
            sib_cats = [{"name": f"{rname} {x}", "url": combo_pages[(rname, x)][0],
                         "count": len(combo_pages[(rname, x)][1])}
                        for x in cats if x != cn and (rname, x) in combo_pages]
            sib_regs = [{"name": f"{y} {cn}", "url": combo_pages[(y, cn)][0],
                         "count": len(combo_pages[(y, cn)][1])}
                        for y in regs if y != rname and (y, cn) in combo_pages]
            c_blocks = [{"title": f"{rname} 다른 분야", "items": sib_cats}] if sib_cats else []
            if sib_regs:
                c_blocks.append({"title": f"다른 지역의 {cn}", "items": sib_regs})
            c_blocks.append({"title": "더 넓게", "items": [
                {"name": f"{rname} 전체", "url": f"/region/{r['slug']}/", "count": len(items)},
                {"name": f"{cn} 전체", "url": f"/category/{c['slug']}/", "count": len(by_cat[cn])},
            ]})
            render_list(
                cpath, serp.combo_h1(rname, cn),
                serp.combo_lede(rname, cn, citems),
                citems,
                title=serp.combo_title(rname, cn, citems),
                desc=serp.combo_desc(rname, cn, c, citems),
                intro_paras=c_paras,
                faqs=c_faqs, faq_jsonld=intros.faq_jsonld(c_faqs),
                list_guides=intros.list_guides(region=rname, category=cn),
                blocks=c_blocks,
                sel_region=rname, sel_category=cn, limit=20,
                crumbs=[{"name": "홈", "url": "/"},
                        {"name": "지역", "url": "/region/"},
                        {"name": rname, "url": f"/region/{r['slug']}/"},
                        {"name": cn, "url": cpath}],
            )

        # 시군구 허브. 시군구×분야는 같은 허브의 field 필터로 보낸다.
        siblings = [
            {"name": d["name_ko"],
             "url": f"/region/{r['slug']}/{d['slug']}/",
             "count": len(ditems)}
            for d, ditems in by_district.get(rname, [])
        ]
        for d, ditems in by_district.get(rname, []):
            dpath = f"/region/{r['slug']}/{d['slug']}/"
            dname = d["name_ko"]
            d_cat_chips = []
            d_cross = {}
            for cn, c in cats.items():
                cross = [a for a in ditems if a.get("category") == cn]
                if len(cross) >= distmod.MIN_COUNT:
                    d_cross[cn] = cross
                    d_cat_chips.append({
                        "name": f"{dname} {cn}",
                        "url": urlstate.field_href(dpath, cn),
                        "count": len(cross),
                    })
            other_d = [x for x in siblings if x["url"] != dpath]
            d_blocks = []
            if d_cat_chips:
                d_blocks.append({"title": "분야로 좁히기", "items": d_cat_chips})
            if other_d:
                d_blocks.append({"title": f"{rname} 다른 시군구", "items": other_d})
            d_blocks.append({"title": f"{rname} 전체", "items": [
                {"name": f"{rname} 전체", "url": f"/region/{r['slug']}/", "count": len(items)},
            ]})
            intro_paras = intros.district_page_intro(rname, dname, ditems)
            d_faqs = intros.district_page_faqs(rname, dname, ditems)
            render_list(
                dpath, serp.district_h1(rname, dname),
                serp.district_lede(rname, dname, ditems),
                ditems,
                title=serp.district_title(rname, dname, ditems),
                desc=serp.district_desc(rname, dname, ditems),
                intro_paras=intro_paras,
                faqs=d_faqs, faq_jsonld=intros.faq_jsonld(d_faqs),
                list_guides=intros.list_guides(region=rname),
                blocks=d_blocks,
                sel_region=rname, limit=20,
                sel_district=dname,
                crumbs=[{"name": "홈", "url": "/"},
                        {"name": "지역", "url": "/region/"},
                        {"name": rname, "url": f"/region/{r['slug']}/"},
                        {"name": dname, "url": dpath}],
            )
            for cn in d_cross:
                c = cats[cn]
                combo_redirects.append((
                    f"{dpath}{c['slug']}/",
                    urlstate.field_href(dpath, cn),
                ))

    # 리다이렉트 파일은 빌드 마지막 emit_root_text_files() 가 다시 쓰므로
    # 여기서 붙이지 않는다. combo_redirects 는 main 끝에서 붙인다.

    # 공고 상세 (접수 중 + 마감 후 최근 것)
    config_regs = {r["name"]: r for r in config.REGIONS}

    def render_notice(a, pool):
        rel = filt.related_notices(a, pool, limit=6)
        npath = f"/notice/{a['id']}/"
        ld_obj = {
            "@context": "https://schema.org",
            "@type": "GovernmentService",
            "name": a["title"],
            "url": SITE["domain"] + npath,
            "identifier": a.get("notice_no") or a.get("id") or "",
            "provider": {"@type": "GovernmentOrganization", "name": a.get("org") or ""},
            "areaServed": a.get("region_label") or a.get("region") or "",
            "audience": {"@type": "Audience", "audienceType": a.get("target") or ""},
            "description": (a.get("ai") or {}).get("summary") or " ".join(detail_extra.overview_paras(a))[:300],
        }
        if a.get("posted_at"):
            ld_obj["datePublished"] = a["posted_at"]
        if a.get("detail_url"):
            ld_obj["sameAs"] = a["detail_url"]
        if a.get("source_label"):
            ld_obj["isBasedOn"] = a["source_label"]
        ld = json.dumps(ld_obj, ensure_ascii=False)
        rslug = (regs.get(a.get("region") or "") or {}).get("slug")
        cslug = (cats.get(a.get("category") or "") or {}).get("slug")
        crumbs = [{"name": "홈", "url": "/"}]
        if rslug:
            crumbs.append({"name": a.get("region") or "지역",
                           "url": f"/region/{rslug}/"})
        if cslug:
            crumbs.append({"name": a.get("category") or "분야",
                           "url": f"/category/{cslug}/"})
        crumbs.append({"name": a.get("title") or "공고", "url": npath})
        faqs = detail_faq.notice_faqs(a)
        howto = detail_faq.notice_howto(a)
        rel_ids = [x.get("id") for x in rel]
        compare = detail_extra.compare_rows(a, pool, limit=5, exclude=rel_ids)
        agency = detail_extra.agency_others(
            a, pool, limit=5, exclude=rel_ids + [c["id"] for c in compare])
        same_rc = detail_extra.same_region_category(
            a, pool, limit=5, exclude=[c["id"] for c in compare] + [c["id"] for c in agency])
        thin = detail_extra.is_thin(a) and npath not in KEEP_INDEXED
        html = env.get_template("detail.html").render(
            summary=detail_extra.summary_box(a),
            sections=detail_extra.desc_sections(a),
            overview_paras=detail_extra.overview_paras(a),
            compare=compare, agency=agency, same_rc=same_rc,
            region_slug=(config_regs.get(a.get("region")) or {}).get("slug", ""),
            agency_total=detail_extra.agency_total(a, pool),
            stats_line=detail_extra.notice_stats_line(a, pool),
            noindex=thin,
            site=SITE, path=npath, page="detail", section="support",
            title=serp.notice_title(a),
            desc=serp.notice_desc(a), a=a, related=rel,
            jsonld=ld, faq_jsonld=intros.faq_jsonld(faqs),
            faqs=faqs, howto=howto,
            howto_jsonld=detail_faq.howto_jsonld(
                f"{a.get('title') or '지원사업'} 신청 순서",
                serp.notice_desc(a), howto),
            crumbs=crumbs, crumb_jsonld=crumb_ld(crumbs),
            collected_at=a.get("collected_at") or env.globals.get("collected_at") or "",
        )
        if thin:
            NOINDEX_DETAIL.append(npath)
        write(npath, html, index=not thin, lastmod=_date_of(a), changefreq="weekly")

    for a in rows:
        render_notice(a, rows)

    # 마감 후 7일이 지나 목록에서는 빠졌지만, 검색엔진이 이미 색인했을 상세페이지는
    # ARCHIVE_DAYS일까지 "마감됨 + 유사 공고 추천"으로 살려둔다 (색인/백링크 유지).
    archived = archived_notices(rows, dl.today_kst())
    for a in archived:
        render_notice(a, rows)   # 추천은 항상 지금 접수 중인 공고 풀에서 뽑는다
    if archived:
        print(f"아카이브 상세페이지 {len(archived)}건 유지")

    # 캘린더 구독 안내 페이지
    cal_links = "".join(
        f'<a href="/calendar/{c["slug"]}.ics" download>{n} 분야</a>'
        for n, c in cats.items() if by_cat[n])
    reg_links = "".join(
        f'<a href="/calendar/{r["slug"]}.ics" download>{n}</a>'
        for n, r in regs.items() if by_reg[n])
    cal_html = f"""
<p>관심 있는 지역이나 분야를 캘린더에 구독해 두면, 새 공고의 마감일이 자동으로 들어옵니다.
마감 하루 전에는 알림이 뜹니다. 회원가입이나 앱 설치는 필요 없습니다.</p>
<h2>구독 방법</h2>
<p><b>아이폰·맥</b> — 아래 링크를 누르면 캘린더 앱이 열리고 구독 여부를 묻습니다.</p>
<p><b>구글 캘린더</b> — 링크를 길게 눌러 주소를 복사한 뒤, 구글 캘린더의
다른 캘린더 추가 → URL로 만들기에 붙여넣습니다.</p>
<p>구독한 캘린더는 하루 두 번 자동으로 갱신됩니다.</p>
<h2>전체</h2>
<div class="chips cal"><a href="/calendar/all.ics" download>전체 공고</a></div>
<h2>분야별</h2>
<div class="chips cal">{cal_links}</div>
<h2>지역별</h2>
<div class="chips cal">{reg_links}</div>
<p class="note">캘린더에는 접수 중인 공고의 마감일만 담깁니다.
지원 조건은 변경될 수 있으니 신청 전 원문 공고를 확인하세요.</p>"""
    write("/calendar/", env.get_template("page.html").render(
        site=SITE, path="/calendar/", section="support",
        title=serp.calendar_title(),
        desc=serp.calendar_desc(),
        h1="마감일을 내 캘린더로", content=cal_html,
        **_crumbs_kw([{"name": "홈", "url": "/"}, {"name": "캘린더", "url": "/calendar/"}])))

    # 가이드 (검색 유입용 상시 콘텐츠 — 공고와 달리 매일 안 바뀐다)
    guide_list = guides.build()
    def _guide_card(slug, h1, desc):
        tag_name, tag_cls = guides.tag_of(slug)
        return (f'<a class="guide-card" href="/guide/{slug}/">'
                f'<span class="guide-tag {tag_cls}">{tag_name}</span>'
                f'<b>{h1}</b><span class="guide-desc">{desc}</span></a>')

    guide_links = "".join(_guide_card(slug, h1, desc) for slug, h1, desc, _ in guide_list)
    write("/guide/", env.get_template("page.html").render(
        site=SITE, path="/guide/", section="support",
        title=serp.guide_hub_title(),
        desc=serp.guide_hub_desc(),
        h1="정부지원사업 가이드", content=f'<div class="guide-list">{guide_links}</div>',
        **_crumbs_kw([{"name": "홈", "url": "/"}, {"name": "가이드", "url": "/guide/"}])),
        changefreq="weekly")
    for slug, h1, desc, content in guide_list:
        jsonld = howto_jsonld(h1, desc, content) if slug in (
            "start", "find-by-deadline", "sme-apply", "deadline-alert",
            "workplace-region", "policy-fund", "tax-insurance-check",
            "calendar-howto", "sme-cert", "export-voucher", "rd-first",
            "hire-grant",
        ) else None
        # 서류 가이드에는 서류 제출 흐름의 다음 단계(HWP 공고문 열기·제출용 PDF)를 붙인다.
        if guides.tag_of(slug)[0] == "서류" and "support-docs-pdf" not in content:
            content += (
                '<p class="note">공고문·신청서가 HWP 파일이라 열리지 않거나, 여러 서류를 PDF 하나로 묶어 '
                '용량 제한에 맞춰야 한다면 <a href="https://schemaextract.shop/support-docs-pdf">HWP도우미의 제출 서류 PDF 만들기</a>'
                '를 쓰세요. 파일은 업로드되지 않고 내 브라우저 안에서만 처리됩니다.</p>')
        write(f"/guide/{slug}/", env.get_template("page.html").render(
            site=SITE, path=f"/guide/{slug}/", section="support",
            title=serp.guide_title(h1),
            desc=desc, h1=h1, content=content, jsonld=jsonld,
            **_crumbs_kw([{"name": "홈", "url": "/"}, {"name": "가이드", "url": "/guide/"},
                          {"name": h1, "url": f"/guide/{slug}/"}])),
            changefreq="weekly")

    # 고정 페이지 (애드센스 심사 필수)
    site_stats = {
        "open": sum(1 for a in rows if a["is_open"]),
        "orgs": len({a["org"] for a in rows if a.get("org")}),
        "regions": len({a["region"] for a in rows if a["region"] != "전국"}),
    }
    for slug, h1, content in static_pages.build(SITE, site_stats):
        html = env.get_template("page.html").render(
            site=SITE, path=f"/{slug}/", section="support",
            title=serp.with_brand(h1),
            desc=serp.static_desc(slug, h1), h1=h1, content=content,
            **_crumbs_kw([{"name": "홈", "url": "/"}, {"name": h1, "url": f"/{slug}/"}]),
        )
        write(f"/{slug}/", html)

    # 캘린더 구독 파일
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    os.makedirs(os.path.join(DIST, "calendar"), exist_ok=True)

    def put_ics(fname, items, label):
        with open(os.path.join(DIST, "calendar", fname), "w", encoding="utf-8") as f:
            f.write(ics.build_ics(items, label, SITE["domain"], stamp))

    put_ics("all.ics", rows, f"{SITE['name']} 전체")
    for nm, c in cats.items():
        if by_cat[nm]:
            put_ics(f"{c['slug']}.ics", by_cat[nm], f"{nm} 분야 마감")
    for nm, r in regs.items():
        if by_reg[nm]:
            put_ics(f"{r['slug']}.ics", by_reg[nm], f"{nm} 지역 마감")

    # 커뮤니티 붙여넣기용 주간 요약 (복붙 30초)
    wk = [a for a in rows if 0 <= a["dday"] <= 7][:10]
    promo = [f"[이번 주 마감] 정부지원사업 {len(wk)}건 정리", ""]
    for a in wk:
        d = "오늘 마감" if a["dday"] == 0 else f"D-{a['dday']}"
        promo.append(f"· {d} | {a['title']} ({a['org']}, {a['amount']})")
    promo += ["", f"전체 목록: {SITE['domain']}/urgent/",
              f"캘린더 구독하면 마감일이 자동으로 들어옵니다: {SITE['domain']}/calendar/"]
    with open(os.path.join(DIST, "promo.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(promo))

    # RSS 피드. 피드리더 구독뿐 아니라 Zapier/IFTTT 같은 무료 자동화 도구가
    # "새 글 뜨면 알림" 트리거로 쓸 수 있는 표준 포맷이라 만들어둔다.
    # 카카오 알림톡은 사업자가 필요해 열지 않는다. 그 대신 전체·지역별·분야별 피드를 둔다.
    # 피드마다 신규 공고 우선, 그다음 마감 임박순으로 최대 50건. 마감된 공고는 넣지 않는다.
    n_feeds = write_rss_feeds(rows, by_reg, by_cat, regs, cats)
    print(f"RSS 피드 {n_feeds}개 (전체 1 + 지역·분야별)")
    # rss.xml noindex 와 ads.txt Content-Type 은 emit_root_text_files() 가
    # 빌드 초반에 dist/_headers 로 이미 쓴다. 여기서 덮어쓰지 않는다.

    # 필터용 데이터 (압축 키)
    feed = [filt.compact(a) for a in rows]
    with open(os.path.join(DIST, "notices.json"), "w", encoding="utf-8") as f:
        json.dump(feed, f, ensure_ascii=False, separators=(",", ":"))

    # 입찰 트리. 지원 목록·지역·분야 페이지와 데이터·URL을 섞지 않는다.
    support_n = len(URLS)
    bid_build.build(env, write, SITE, URLS, DIST, noindex_sink=NOINDEX_DETAIL)
    bid_n = len(URLS) - support_n

    # 404 페이지. Cloudflare Pages는 dist/404.html이 있으면 존재하지 않는
    # URL에 이 파일을 진짜 404 상태코드로 돌려준다 — 없으면(지금까지 없었음)
    # 홈페이지를 200으로 대신 돌려주는 소프트 404가 나서 SEO에 안 좋았다.
    # sitemap에 넣으면 안 되므로 write() 대신 직접 쓴다.
    # 스플랫 _redirects(모든 경로를 404.html 이나 홈으로)는 쓰지 않는다. Cloudflare는
    # 정적 파일이 있어도 리다이렉트를 적용하고, 404 상태 재작성은 지원하지
    # 않아 기존 지원 URL을 깨뜨릴 수 있다.
    html_404 = env.get_template("404.html").render(
        site=SITE, path="/404.html", title=f"페이지를 찾을 수 없습니다 | {SITE['name']}",
        desc="요청하신 페이지를 찾을 수 없습니다. 지원사업·입찰 목록에서 다시 찾아보세요.", noindex=True,
        no_ads=True,
    )
    open(os.path.join(DIST, "404.html"), "w", encoding="utf-8").write(html_404)

    # 색인 페이지끼리 겹치는 제목·설명에 기관명/공고번호를 붙인다.
    n_dedup = seo_dedupe.run(DIST, URLS, SITE["name"])
    print(f"중복 제목·설명 구분 {n_dedup}건")
    print(f"전체 공고 목록 /browse/ {browse.build(env, SITE, DIST, URLS, URL_META)}페이지")

    # sitemap / robots
    today = dl.today_kst().isoformat()
    sm = ['<?xml version="1.0" encoding="UTF-8"?>',
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u in URLS:
        meta = URL_META.get(u) or {}
        lm = meta.get("lastmod") or today
        if lm > today:
            lm = today
        if u.startswith("/guide/") or u in (
            "/about/", "/privacy/", "/terms/", "/contact/", "/calendar/",
        ):
            freq = meta.get("changefreq") or "weekly"
        elif u.startswith("/notice/") or u.startswith("/bid/notice/"):
            freq = meta.get("changefreq") or "weekly"
        else:
            freq = meta.get("changefreq") or "daily"
        pr = meta.get("priority") or (
            "1.0" if u in ("/", "/bid/") else
            ("0.8" if u.count("/") <= 3 else "0.6")
        )
        sm.append(f"<url><loc>{SITE['domain']}{u}</loc><lastmod>{lm}</lastmod>"
                  f"<changefreq>{freq}</changefreq><priority>{pr}</priority></url>")
    sm.append("</urlset>")
    open(os.path.join(DIST, "sitemap.xml"), "w", encoding="utf-8").write("\n".join(sm))
    # 도메인 연결 전에는 색인을 막는다.
    # .pages.dev 주소로 색인되면 도메인 이전 시 중복 콘텐츠가 된다.
    if SITE.get("allow_index"):
        robots = (
            "User-agent: *\n"
            "Allow: /ads.txt\n"
            "Allow: /app-ads.txt\n"
            "Disallow: /scrap/\n"
            "Disallow: /alerts/\n"
            "Disallow: /api/\n"
            "Allow: /\n"
            f"Sitemap: {SITE['domain']}/sitemap.xml\n"
        )
    else:
        robots = (
            "User-agent: *\n"
            "Allow: /ads.txt\n"
            "Allow: /app-ads.txt\n"
            "Disallow: /\n"
        )
    open(os.path.join(DIST, "robots.txt"), "w", encoding="utf-8").write(robots)

    # ads.txt 는 빌드 초반에도 쓰지만, 마지막에 한 번 더 써서 중간 단계가
    # dist 를 비우거나 덮어써도 크롤러가 HTML 홈을 받지 않게 한다.
    emit_root_text_files(DIST)
    append_list_redirects(DIST, combo_redirects)

    # 검색엔진이 아는 상세 URL(시드 파일 + 라이브 sitemap) 중 사라진 것은 목록으로 301.
    detail_now = [u for u in URLS if is_detail(u)]
    # noindex 로 sitemap 에서만 뺀 페이지는 HTML 이 살아 있으므로 301 대상도,
    # 가드의 감소분도 아니다.
    _dn = set(detail_now)
    detail_live = detail_now + [u for u in NOINDEX_DETAIL if u not in _dn]
    print(f"얇은 상세페이지 noindex {len(NOINDEX_DETAIL)}건 (sitemap 제외)")
    try:
        known = json.load(open(KNOWN_PATH, encoding="utf-8"))
    except Exception:
        known = {}
    seed_count = known.pop("__count__", 0)
    if not isinstance(seed_count, int):
        seed_count = 0
    live = None
    if SITE.get("allow_index") and not os.environ.get("SKIP_LIVE_GUARD"):
        live = live_detail_urls(SITE["domain"])
    for u in live or []:
        known[u] = today
    # 병합된 중복 공고 URL 은 대표 공고로 301 (목록으로 보내지 않는다).
    dup_pairs = notice_dedupe.redirect_pairs(DUP_ALIAS)
    append_gone_redirects(DIST, dup_pairs)
    dup_src = [src for src, _ in dup_pairs]
    print(f"중복 공고 301 {len(dup_pairs)}건")
    budget = MAX_STATIC_REDIRECTS - count_redirect_rules(DIST)
    gone = gone_redirects(known, detail_live + dup_src, budget)
    append_gone_redirects(DIST, gone)
    print(f"사라진 상세 URL 301 {len(gone)}건 (정적 규칙 여유 {budget})")

    # 빌드 가드: 라이브 sitemap(없으면 시드 기록) 대비 20% 넘게 줄면 실패
    live_n = len(live) if live is not None else None
    # 중복 병합으로 줄어든 URL 은 대표 공고로 301 되어 살아 있으므로 가드에서 감소로 세지 않는다.
    msg = detail_guard(len(detail_live) + len(dup_src), [live_n if live_n is not None else seed_count])
    print(f"상세페이지 {len(detail_now)}건 (라이브 {live_n}, 시드 {seed_count})")
    if msg and not os.environ.get("ALLOW_DETAIL_DROP"):
        raise SystemExit(msg)
    print(f"지역×분야 허브 {len(combo_pages)}개 (접수 중 {COMBO_MIN}건 이상)")
    if combo_redirects:
        print(f"지역×분야 리다이렉트 {len(combo_redirects)}건 (공고가 적은 조합은 지역 목록 필터로)")
    print("ads.txt·app-ads.txt 루트 확인:", ADS_TXT_LINE)
    fs = env.globals.get("formspree_url") or ""
    print("알림 신청: /api/alerts/subscribe (Resend 연락처, 확인 메일)")
    if fs:
        print("FORMSPREE_ID 는 알림 신청에 쓰지 않습니다.")
    hb, ha = minify_dist_html(DIST)
    print(f"HTML 공백 정리: {hb}B → {ha}B")
    for rel in ("index.html", "static/style.css", "static/filter.js", "static/alert.js"):
        p = os.path.join(DIST, rel)
        if os.path.isfile(p):
            print(f"  {rel} {os.path.getsize(p)}B")

    # 네이버 서치어드바이저 HTML 파일 소유확인. 사이트 루트에 그대로 둔다.
    naver_html = "naver0defc699223f8ffa807d6d0bc99bb36c.html"
    naver_src = os.path.join(ROOT, naver_html)
    if os.path.exists(naver_src):
        shutil.copy2(naver_src, os.path.join(DIST, naver_html))

    # IndexNow(빙·네이버 지원): 소유확인 키 파일은 로그인/가입 없이 쓰는
    # 공개 토큰이라 늘 배포해두고, 실제 검색엔진 핑은 색인을 허용할 때만 보낸다.
    open(os.path.join(DIST, f"{config.INDEXNOW_KEY}.txt"), "w", encoding="utf-8").write(config.INDEXNOW_KEY)
    # 실제 제출은 배포 뒤 alert_digest.py 단계에서 src/indexnow.py 가 한다 (키 파일이 라이브여야 함).
    import indexnow
    indexnow.save_list(URLS, URL_META, dl.today_kst())

    stray = stray_html_files(DIST, WRITTEN | browse.WRITTEN)
    if stray:
        raise SystemExit("이번 빌드가 만들지 않은 HTML 이 dist 에 있습니다(잔재 파일): "
                         + ", ".join(stray[:20]))
    print("잔재 HTML 점검: 이번 빌드가 만든 파일만 있음")

    print(f"지원 {len(rows)}건(신규 {new_cnt}건) → {support_n}페이지, "
          f"입찰 +{bid_n}페이지, 합계 {len(URLS)}페이지, "
          f"캘린더 {len(os.listdir(os.path.join(DIST,'calendar')))}개 생성 완료 (dist/)")


if __name__ == "__main__":
    main()
