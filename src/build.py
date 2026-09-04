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
  /region/{지역}/{분야}/  ← 롱테일 조합 (핵심 트래픽 소스)
  /notice/{id}/         공고 상세
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
from datetime import date, datetime, timezone
from email.utils import format_datetime

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

ROOT = os.path.join(os.path.dirname(__file__), "..")
DIST = os.path.join(ROOT, "dist")
SITE = config.SITE

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
    for name in ("style.css", "filter.js", "scrap.js"):
        p = os.path.join(ROOT, "static", name)
        if os.path.exists(p):
            with open(p, "rb") as f:
                h.update(f.read())
    return h.hexdigest()[:10]


env.globals["asset_v"] = _static_version()

URLS = []


def write(path, html):
    """path='/region/seoul/' → dist/region/seoul/index.html"""
    out = os.path.join(DIST, path.strip("/"), "index.html") if path != "/" \
        else os.path.join(DIST, "index.html")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    URLS.append(path)


def fill_defaults(a):
    """실데이터에 없는 필드를 채운다. 목업/실데이터 스키마 차이를 흡수."""
    a.setdefault("amount", "")
    if not a["amount"]:
        a["amount"] = enrich.amount_of(a) or "공고문 참조"
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


def decorate(a):
    """D-day 표시용 값 계산. 상시 접수는 별도 표기."""
    if a.get("period_type") == "always":
        a["cls"], a["dlabel"] = "d-a", "상시"
        a["dsub"] = a.get("period_raw") or "상시 접수"
        return a
    d = a["dday"]
    if d < 0:
        a["cls"], a["dlabel"], a["dsub"] = "d-c", "마감", f"{-d}일 전 종료"
    elif d == 0:
        a["cls"], a["dlabel"], a["dsub"] = "d-u", "오늘", "오늘 마감"
    elif d <= 7:
        a["cls"], a["dlabel"] = "d-u", f"D-{d}"
        a["dsub"] = f"{a['apply_end'][5:]} 마감" if a.get("apply_end") else "마감 임박"
    elif d <= 14:
        a["cls"], a["dlabel"] = "d-s", f"D-{d}"
        a["dsub"] = f"{a['apply_end'][5:]} 마감" if a.get("apply_end") else ""
    else:
        a["cls"], a["dlabel"] = "d-o", f"D-{d}"
        a["dsub"] = f"{a['apply_end'][5:]} 마감" if a.get("apply_end") else ""
    return a


def tally(items):
    return {
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
# 그런 경우를 대비한 상한선. 정상 운영에서는 이 값에 걸릴 일이 없다.
MAX_ARCHIVED = 300

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
        try:
            end = date.fromisoformat(a.get("apply_end") or "")
        except Exception:
            continue
        if (today - end).days > ARCHIVE_DAYS:
            continue          # 너무 오래돼서 버림
        kept[aid] = a
        if aid in live_ids:
            continue          # 오늘 목록에 이미 있으면 아카이브 페이지 별도 생성 불필요
        row = fill_defaults(dict(a))
        row["dday"] = (today - end).days * -1
        row["is_open"] = False
        row["is_new"] = False
        row = decorate(row)
        row["is_closed"] = True
        out.append(row)

    _save_archive(kept)
    if len(out) > MAX_ARCHIVED:
        # 마감일이 가장 최근인 것부터 우선 유지 (오래된 것부터 잘라낸다)
        out.sort(key=lambda r: r.get("apply_end") or "")
        print(f"경고: 아카이브 대상이 {len(out)}건으로 비정상적으로 많음 "
              f"(소스 전환/ID 생성 로직 변경 의심). 최근 {MAX_ARCHIVED}건만 생성합니다.")
        out = out[-MAX_ARCHIVED:]
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
    """
    공고 상세 페이지에 이미 보이는 문구(ai.fit/caution/checklist, 접수기간, 지원규모)를
    그대로 질문-답변으로 재구성한다. 화면에 없는 내용을 만들어 넣지 않는다
    (구글 FAQ 구조화데이터 가이드라인 — 페이지에 보이지 않는 답변은 안 됨).
    """
    period = (a.get("period_raw") or "상시 접수") if a.get("period_type") == "always" \
        else f"{a.get('apply_start')} ~ {a.get('apply_end')}"
    qa = []
    if a.get("ai", {}).get("fit"):
        qa.append(("어떤 기업이 신청할 수 있나요?", " ".join(a["ai"]["fit"])))
    qa.append(("접수기간과 지원규모는 어떻게 되나요?",
               f"접수기간은 {period}이며, 지원규모는 {a.get('amount') or '공고문 참조'}입니다."))
    if a.get("ai", {}).get("caution"):
        qa.append(("신청 전 확인해야 할 점은 무엇인가요?", " ".join(a["ai"]["caution"])))
    if a.get("ai", {}).get("checklist"):
        qa.append(("신청 시 준비해야 할 서류는 무엇인가요?", " ".join(a["ai"]["checklist"])))
    return json.dumps({
        "@context": "https://schema.org", "@type": "FAQPage",
        "mainEntity": [{
            "@type": "Question", "name": q,
            "acceptedAnswer": {"@type": "Answer", "text": ans},
        } for q, ans in qa],
    }, ensure_ascii=False)


SLUGMAP = json.dumps({
    "region": {r["name"]: r["slug"] for r in config.REGIONS},
    "category": {c["name"]: c["slug"] for c in config.CATEGORIES},
}, ensure_ascii=False)


def render_list(path, h1, lede, items, title=None, desc=None, blocks=None,
                intro=None, sel_region=None, sel_category=None, today=0,
                new_cnt=0, ics_url=None, limit=None, more_href=None,
                sections=None, tally_items=None, beginner_cta=False):
    html = env.get_template("list.html").render(
        site=SITE, path=path, title=title or f"{h1} | {SITE['name']}",
        desc=desc or lede, h1=h1, lede=lede, items=items,
        tally=tally(tally_items if tally_items is not None else items),
        blocks=blocks or [], intro=intro,
        all_regions=config.REGIONS, all_categories=config.CATEGORIES,
        sel_region=sel_region, sel_category=sel_category, slugmap=SLUGMAP,
        today=today, new_cnt=new_cnt, ics_url=ics_url,
        limit=limit or 0, more_href=more_href or "", sections=sections or [],
        beginner_cta=beginner_cta,
    )
    write(path, html)


def main():
    if os.path.exists(DIST):
        shutil.rmtree(DIST)
    os.makedirs(DIST)
    shutil.copytree(os.path.join(ROOT, "static"), os.path.join(DIST, "static"))

    # 키가 있으면 실데이터, 없으면 목업으로 자동 전환.
    # 로컬에서 키 없이 돌려도 그대로 빌드된다.
    key = os.environ.get("BIZINFO_KEY", "").strip()
    if key:
        print("실데이터 모드 (기업마당 API)")
        rows = sources.load(bizinfo.BizinfoSource(key))
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

    use_llm = bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())
    rows = enrich.enrich_all(rows, use_llm=use_llm)
    rows = [decorate(fill_defaults(a)) for a in rows]

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

    cat_chips = [{"name": n, "url": f"/category/{cats[n]['slug']}/", "count": len(v)}
                 for n, v in by_cat.items() if v]
    reg_chips = [{"name": n, "url": f"/region/{regs[n]['slug']}/", "count": len(v)}
                 for n, v in by_reg.items() if v]
    hub = [{"title": "분야로 찾기", "items": cat_chips},
           {"title": "지역으로 찾기", "items": reg_chips}]

    # 메인: 요약판 (섹션마다 5건 + 더보기)
    new_rows = [a for a in rows if a["is_new"]]
    week = [a for a in rows if 0 <= a["dday"] <= 7]
    sections = []
    if week:
        sections.append({"title": "이번 주에 닫히는 공고", "items": week[:5],
                         "href": "/urgent/", "total": len(week)})
    if new_rows:
        sections.append({"title": "오늘 새로 올라온 공고", "items": new_rows[:5],
                         "href": "/new/", "total": len(new_rows)})
    sections.append({"title": "접수 중인 공고", "items": [a for a in rows if a["is_open"]][:5],
                     "href": "/all/", "total": sum(1 for a in rows if a["is_open"])})

    render_list(
        "/", "마감이 가까운 순서로 봅니다",
        "정부·지자체·공공기관이 공고한 사업자 지원사업을 한곳에 모았습니다. "
        "매일 아침 새 공고가 올라오고, 마감이 임박한 순서로 정렬됩니다.",
        [],
        title=f"{SITE['name']} — 정부지원사업 마감일 순 정리",
        desc="중소기업·소상공인 정부지원사업을 마감일 순서로 정리합니다. 지역·분야별로 접수 중인 공고를 확인하세요.",
        blocks=hub, today=sum(1 for a in rows if a["dday"] == 0), new_cnt=new_cnt,
        ics_url="/calendar/all.ics", sections=sections, more_href="/all/",
        tally_items=rows, beginner_cta=True,
    )

    # 전체 목록
    render_list("/all/", "전체 공고",
                "접수 중인 공고 전부를 마감일 순으로 정렬했습니다.",
                rows, limit=20,
                title=f"정부지원사업 전체 공고 목록 | {SITE['name']}",
                desc="중소기업·소상공인 정부지원사업 전체 목록. 지역·분야로 좁혀서 확인하세요.",
                blocks=hub)

    # 신규
    if new_rows:
        render_list("/new/", "새로 올라온 공고",
                    "최근 새로 등록된 공고입니다.", new_rows, limit=20, blocks=hub)

    # 스크랩 페이지 (색인 제외)
    write("/scrap/", env.get_template("scrap.html").render(
        site=SITE, path="/scrap/", page="scrap", title=f"스크랩한 공고 | {SITE['name']}",
        desc="스크랩한 지원사업 공고를 마감일 순으로 모아봅니다."))
    URLS.pop()   # sitemap에서 제외 (개인화 페이지)

    # 마감임박
    urgent = [a for a in rows if 0 <= a["dday"] <= 7]
    render_list("/urgent/", "이번 주에 닫히는 공고",
                "7일 안에 접수가 끝나는 공고만 모았습니다.", urgent, limit=20, blocks=hub)

    # 허브
    render_list("/category/", "분야별로 찾기",
                "지원 분야 8종으로 나눠 정리했습니다.", [], blocks=[hub[0]],
                tally_items=rows)
    render_list("/region/", "지역별로 찾기",
                "사업장 소재지 기준으로 신청 가능한 공고를 모았습니다.", [], blocks=[hub[1]],
                tally_items=rows)

    # 분야별
    for name, c in cats.items():
        items = by_cat[name]
        if not items:
            continue
        sub = [{"name": f"{r} {name}", "url": f"/region/{regs[r]['slug']}/{c['slug']}/",
                "count": len([a for a in items if a["region"] == r])}
               for r in regs if any(a["region"] == r for a in items)]
        other_cats = [x for x in cat_chips if x["name"] != name]
        render_list(
            f"/category/{c['slug']}/", f"{name} 분야 지원사업",
            f"{c['desc']}. 현재 접수 중인 공고를 마감일 순으로 정리했습니다.",
            items,
            title=f"{name} 분야 정부지원사업 모음 | {SITE['name']}",
            desc=f"{name} 지원사업 {len(items)}건. {c['desc']}. 마감일과 지원대상을 한눈에 확인하세요.",
            blocks=[{"title": "다른 분야", "items": other_cats},
                    {"title": "지역으로 좁히기", "items": sub}],
            sel_category=name, ics_url=f"/calendar/{c['slug']}.ics", limit=20,
        )

    # 지역별 + 지역x분야 롱테일
    for rname, r in regs.items():
        items = by_reg[rname]
        if not items:
            continue
        sub = [{"name": f"{rname} {cn}", "url": f"/region/{r['slug']}/{cats[cn]['slug']}/",
                "count": len([a for a in items if a["category"] == cn])}
               for cn in cats if any(a["category"] == cn for a in items)]
        other_regs = [x for x in reg_chips if x["name"] != rname]
        render_list(
            f"/region/{r['slug']}/", f"{rname} 지역 지원사업",
            f"{rname}에 사업장을 둔 기업이 신청할 수 있는 공고입니다.",
            items,
            title=f"{rname} 정부지원사업 · 보조금 공고 모음 | {SITE['name']}",
            desc=f"{rname} 지역 중소기업·소상공인 지원사업 {len(items)}건을 마감일 순으로 정리했습니다.",
            blocks=[{"title": "다른 지역", "items": other_regs},
                    {"title": "분야로 좁히기", "items": sub}],
            sel_region=rname, ics_url=f"/calendar/{r['slug']}.ics", limit=20,
        )
        for cn, c in cats.items():
            cross = [a for a in items if a["category"] == cn]
            if not cross:
                continue
            intro = (f"<p>{rname} 지역에서 접수 중인 {cn} 분야 지원사업 {len(cross)}건입니다. "
                     f"{c['desc']}에 해당하며, 소관기관은 "
                     f"{', '.join(sorted({a['org'] for a in cross})[:3])} 등입니다.</p>")
            other_regs_same_cat = [
                {"name": r2, "url": f"/region/{regs[r2]['slug']}/{c['slug']}/",
                 "count": len([a for a in by_reg[r2] if a["category"] == cn])}
                for r2 in regs if r2 != rname and any(a["category"] == cn for a in by_reg[r2])
            ]
            render_list(
                f"/region/{r['slug']}/{c['slug']}/", f"{rname} {cn} 지원사업",
                f"{rname} 지역 {cn} 분야 공고를 마감일 순으로 정리했습니다.",
                cross,
                title=f"{rname} {cn} 지원사업 {len(cross)}건 — 마감일 순 | {SITE['name']}",
                desc=f"{rname} {cn} 분야 정부지원사업 {len(cross)}건. 지원대상, 지원규모, 마감일을 정리했습니다.",
                intro=intro,
                blocks=[{"title": f"{rname} 다른 분야", "items": sub},
                        {"title": f"다른 지역의 {cn}", "items": other_regs_same_cat}],
                sel_region=rname, sel_category=cn, limit=20,
            )

    # 공고 상세 (접수 중 + 마감 후 최근 것)
    def render_notice(a, pool):
        rel = [x for x in pool
               if x["id"] != a["id"] and x["region"] == a["region"]
               and x["category"] == a["category"]][:5]
        ld = json.dumps({
            "@context": "https://schema.org", "@type": "GovernmentService",
            "name": a["title"], "provider": {"@type": "GovernmentOrganization", "name": a["org"]},
            "areaServed": a["region"], "audience": {"@type": "Audience", "audienceType": a["target"]},
            "description": a["ai"]["summary"],
        }, ensure_ascii=False)
        title_suffix = "— 마감된 공고 정리" if a.get("is_closed") else "— 신청자격·마감일 정리"
        html = env.get_template("detail.html").render(
            site=SITE, path=f"/notice/{a['id']}/",
            title=f"{a['title']} {title_suffix} | {SITE['name']}",
            desc=a["ai"]["summary"][:150], a=a, related=rel,
            jsonld=ld, faq_jsonld=faq_jsonld(a),
        )
        write(f"/notice/{a['id']}/", html)

    for a in rows:
        render_notice(a, rows)

    # 마감 후 7일이 지나 목록에서는 빠졌지만, 검색엔진이 이미 색인했을 상세페이지는
    # ARCHIVE_DAYS일까지 "마감됨 + 유사 공고 추천"으로 살려둔다 (색인/백링크 유지).
    archived = archived_notices(rows, date.today())
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
        site=SITE, path="/calendar/", title=f"마감일 캘린더 구독 | {SITE['name']}",
        desc="관심 지역·분야 지원사업 마감일을 내 캘린더에 자동으로 받아보세요.",
        h1="마감일을 내 캘린더로", content=cal_html))

    # 가이드 (검색 유입용 상시 콘텐츠 — 공고와 달리 매일 안 바뀐다)
    guide_list = guides.build()
    GUIDE_TAGS = {
        "start": ("시작하기", "tag-start"),
        "aply-trgt-check": ("기초", "tag-basic"),
        "voucher-vs-selection": ("전략", "tag-strategy"),
        "docs-checklist": ("서류", "tag-docs"),
        "biz-plan-structure": ("전략", "tag-strategy"),
        "grant-vs-loan": ("기초", "tag-basic"),
    }
    def _guide_card(slug, h1, desc):
        tag_name, tag_cls = GUIDE_TAGS.get(slug, ("가이드", "tag-basic"))
        return (f'<a class="guide-card" href="/guide/{slug}/">'
                f'<span class="guide-tag {tag_cls}">{tag_name}</span>'
                f'<b>{h1}</b><span class="guide-desc">{desc}</span></a>')

    guide_links = "".join(_guide_card(slug, h1, desc) for slug, h1, desc, _ in guide_list)
    write("/guide/", env.get_template("page.html").render(
        site=SITE, path="/guide/", title=f"정부지원사업 가이드 | {SITE['name']}",
        desc="정부지원사업 신청 자격, 서류, 바우처·선정사업 차이 등 기본기를 정리했습니다.",
        h1="정부지원사업 가이드", content=f'<div class="guide-list">{guide_links}</div>'))
    for slug, h1, desc, content in guide_list:
        jsonld = howto_jsonld(h1, desc, content) if slug == "start" else None
        write(f"/guide/{slug}/", env.get_template("page.html").render(
            site=SITE, path=f"/guide/{slug}/", title=f"{h1} | {SITE['name']}",
            desc=desc, h1=h1, content=content, jsonld=jsonld))

    # 고정 페이지 (애드센스 심사 필수)
    site_stats = {
        "open": sum(1 for a in rows if a["is_open"]),
        "orgs": len({a["org"] for a in rows if a.get("org")}),
        "regions": len({a["region"] for a in rows if a["region"] != "전국"}),
    }
    for slug, h1, content in static_pages.build(SITE, site_stats):
        html = env.get_template("page.html").render(
            site=SITE, path=f"/{slug}/", title=f"{h1} | {SITE['name']}",
            desc=h1, h1=h1, content=content,
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
    # 전부 다 넣으면 무의미해지니 신규 공고 우선, 그다음 마감 임박순으로 최대 50건.
    rss_items = sorted(rows, key=lambda a: (not a["is_new"], a["dday"]))[:50]
    now_rfc822 = format_datetime(datetime.now(timezone.utc))
    rss = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<rss version="2.0"><channel>',
           f"<title>{SITE['name']}</title>",
           f"<link>{SITE['domain']}/</link>",
           f"<description>{SITE['tagline']}</description>",
           "<language>ko</language>",
           f"<lastBuildDate>{now_rfc822}</lastBuildDate>"]
    for a in rss_items:
        title = html_module.escape(f"[{a['region']}] {a['title']}")
        desc = html_module.escape(a.get("ai", {}).get("summary", ""))
        rss.append(
            f"<item><title>{title}</title>"
            f"<link>{SITE['domain']}/notice/{a['id']}/</link>"
            f"<guid isPermaLink=\"true\">{SITE['domain']}/notice/{a['id']}/</guid>"
            f"<pubDate>{now_rfc822}</pubDate>"
            f"<description>{desc}</description></item>"
        )
    rss.append("</channel></rss>")
    open(os.path.join(DIST, "rss.xml"), "w", encoding="utf-8").write("\n".join(rss))

    # 필터용 데이터 (압축 키)
    feed = [{"i": a["id"], "t": a["title"], "c": a["category"], "r": a["region"],
             "o": a.get("org", ""), "m": a.get("amount", ""),
             "e": a.get("apply_end") or "", "d": a["dday"],
             "n": 1 if a["is_new"] else 0,
             "p": a.get("period_raw", "")}
            for a in rows]
    with open(os.path.join(DIST, "notices.json"), "w", encoding="utf-8") as f:
        json.dump(feed, f, ensure_ascii=False, separators=(",", ":"))

    # sitemap / robots
    today = date.today().isoformat()
    sm = ['<?xml version="1.0" encoding="UTF-8"?>',
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u in URLS:
        pr = "1.0" if u == "/" else ("0.8" if u.count("/") <= 3 else "0.6")
        sm.append(f"<url><loc>{SITE['domain']}{u}</loc><lastmod>{today}</lastmod>"
                  f"<changefreq>daily</changefreq><priority>{pr}</priority></url>")
    sm.append("</urlset>")
    open(os.path.join(DIST, "sitemap.xml"), "w", encoding="utf-8").write("\n".join(sm))
    # 도메인 연결 전에는 색인을 막는다.
    # .pages.dev 주소로 색인되면 도메인 이전 시 중복 콘텐츠가 된다.
    if SITE.get("allow_index"):
        robots = f"User-agent: *\nAllow: /\nSitemap: {SITE['domain']}/sitemap.xml\n"
    else:
        robots = "User-agent: *\nDisallow: /\n"
    open(os.path.join(DIST, "robots.txt"), "w", encoding="utf-8").write(robots)

    # ads.txt: 애드센스 심사·수익 인증에 필요한 표준 파일.
    # pub-XXXX 부분은 adsense_client("ca-pub-XXXX")에서 "ca-" 접두만 뗀 값이고,
    # 뒤의 f08c47fec0942fa0은 구글이 모든 퍼블리셔 공통으로 쓰는 고정 인증값이다
    # (비밀값 아님 — 구글 자체 문서에 실린 표준 상수).
    if SITE.get("adsense_client"):
        pub_id = SITE["adsense_client"].removeprefix("ca-")
        open(os.path.join(DIST, "ads.txt"), "w", encoding="utf-8").write(
            f"google.com, {pub_id}, DIRECT, f08c47fec0942fa0\n")

    # IndexNow(빙·네이버 지원): 소유확인 키 파일은 로그인/가입 없이 쓰는
    # 공개 토큰이라 늘 배포해두고, 실제 검색엔진 핑은 색인을 허용할 때만 보낸다.
    open(os.path.join(DIST, f"{config.INDEXNOW_KEY}.txt"), "w", encoding="utf-8").write(config.INDEXNOW_KEY)
    if SITE.get("allow_index"):
        try:
            import urllib.request
            payload = json.dumps({
                "host": SITE["domain"].split("//")[-1],
                "key": config.INDEXNOW_KEY,
                "keyLocation": f"{SITE['domain']}/{config.INDEXNOW_KEY}.txt",
                "urlList": [f"{SITE['domain']}{u}" for u in URLS],
            }).encode("utf-8")
            req = urllib.request.Request(
                "https://api.indexnow.org/indexnow", data=payload,
                headers={"Content-Type": "application/json; charset=utf-8"},
            )
            with urllib.request.urlopen(req, timeout=20) as r:
                print(f"IndexNow 제출: status={r.status}, {len(URLS)}개 URL")
        except Exception as e:
            print(f"IndexNow 제출 실패(무시하고 진행): {e}")

    print(f"공고 {len(rows)}건(신규 {new_cnt}건) → 페이지 {len(URLS)}개, "
          f"캘린더 {len(os.listdir(os.path.join(DIST,'calendar')))}개 생성 완료 (dist/)")


if __name__ == "__main__":
    main()
