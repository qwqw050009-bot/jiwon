# -*- coding: utf-8 -*-
"""
입찰(/bid/) 정적 페이지 생성.

지원사업 목록·지역·분야 페이지와 URL·데이터·카피를 분리한다.
build.py 의 write()/URLS 를 받아 입찰 페이지만 추가한다.
"""
import json
import os

import config
import bidinfo
import filters as filt
import intros
import serp
import deadline as dl
import detail_faq
from isodate import iso_date
import detail_extra

BID_KINDS = config.BID_KINDS
BID_REGIONS = config.BID_REGIONS
REGS = {r["name"]: r for r in BID_REGIONS}


def _crumb_ld(crumbs, site):
    if not crumbs:
        return ""
    els = []
    for i, c in enumerate(crumbs, 1):
        row = {"@type": "ListItem", "position": i, "name": c["name"]}
        if c.get("url"):
            row["item"] = site["domain"] + c["url"]
        els.append(row)
    return json.dumps({
        "@context": "https://schema.org", "@type": "BreadcrumbList",
        "itemListElement": els,
    }, ensure_ascii=False)


def tally(items, full=None, more=None):
    """
    건수. full 을 주면 목록 상한(500건) 전 전체 기준으로 센다.
    more=True 면 수집이 끝까지 되지 않아 하한값이다 → 화면에 "N건 이상".
    """
    src = items if full is None else full
    if more is None:
        more = not bidinfo.META.get("complete", True)
    return {
        "today": sum(1 for a in src if a.get("is_open") and a.get("dday") == 0),
        "urgent": sum(1 for a in src if a.get("is_open") and 0 <= a["dday"] <= 7),
        "soon": sum(1 for a in src if a.get("is_open") and 7 < a["dday"] <= 14),
        "open": sum(1 for a in src if a.get("is_open")),
        "more": bool(more),
    }


def n_label(t, key):
    """'12건' 또는 수집이 덜 됐으면 '500건 이상'."""
    n = int((t or {}).get(key) or 0)
    return f"{n:,}건 이상" if (t or {}).get("more") and n else f"{n:,}건"


def cap_note(shown, total):
    """목록에 보이는 카드 수가 전체보다 적을 때 붙이는 안내."""
    if total > shown:
        return f" 목록에는 마감이 가까운 {shown:,}건까지 보여 줍니다."
    return ""


def hub_intro(t):
    return (
        "<p>입찰은 공공기관이 물품·용역·공사·외자를 살 때 나라장터에 올리는 공고입니다. "
        "기업이 신청해서 받는 지원사업과는 성격이 다릅니다. "
        f'<a href="/">지원사업 마감일</a>은 홈에서 따로 봅니다.</p>'
        f"<p>나라장터 수집 기준으로 오늘 마감 {n_label(t, 'today')}, "
        f"이번 주 마감 {n_label(t, 'urgent')}, 진행 중 {n_label(t, 'open')}입니다.</p>"
    )


def empty_hub_intro():
    return (
        "<p>입찰은 공공기관이 물품·용역·공사·외자를 살 때 나라장터에 올리는 공고입니다. "
        "기업이 신청해서 받는 지원사업과는 성격이 다릅니다. "
        '<a href="/">지원사업 마감일</a>은 홈의 지원 탭에서 따로 봅니다.</p>'
        "<p>지금은 이 사이트에 표시할 진행 중 입찰이 없습니다. "
        "가짜 공고는 올리지 않습니다.</p>"
    )


def empty_hub_faqs():
    return [
        {"q": "왜 입찰 목록이 비어 있나요?",
         "a": "나라장터 연동이 꺼져 있거나, 지금 표시할 진행 중 입찰이 없습니다. "
              "가짜 공고를 올리지 않습니다. 원문은 나라장터에서 확인하세요."},
        {"q": "지원사업은 어디서 보나요?",
         "a": "상단의 지원 탭을 누르거나 홈으로 가면 보조금·융자 공고를 마감일 순으로 볼 수 있습니다."},
        {"q": "원문은 어디서 보나요?",
         "a": "나라장터(https://www.g2b.go.kr/)에서 확인합니다. "
              "이 사이트에서 투찰하거나 대신 접수하지 않습니다."},
    ]


def hub_faqs(t):
    return [
        {"q": "입찰공고와 지원사업은 어떻게 다른가요?",
         "a": "입찰은 공공기관이 필요한 물품·용역·공사를 살 때 올리는 공고입니다. "
              "지원사업은 기업이 신청해서 받는 공고라 따로 정리합니다. "
              "지원사업은 홈에서 마감일 순으로 볼 수 있습니다."},
        {"q": "오늘 마감되는 입찰은 몇 건인가요?",
         "a": f"나라장터 수집 기준으로 오늘 마감 {n_label(t, 'today')}, "
              f"이번 주 마감 {n_label(t, 'urgent')}입니다."},
        {"q": "추정가격이 없는 공고는 왜 보이나요?",
         "a": "나라장터 응답에 추정가격이 비어 있는 경우가 있습니다. "
              "없는 숫자를 채워 넣지 않고, 원문 공고에서 확인하도록 비워 둡니다."},
        {"q": "원문은 어디서 보나요?",
         "a": "각 공고의 나라장터 원문 링크로 이동합니다. "
              "이 사이트에서 투찰하거나 대신 접수하지 않습니다."},
    ]


def kind_faqs(kind, items, t):
    name = kind["name"]
    return [
        {"q": f"{name} 입찰은 무엇을 사나요?",
         "a": f"{kind['desc']}입니다. 이 목록에는 진행 중 {n_label(t, 'open')}이 있습니다."},
        {"q": f"{name} 입찰 중 이번 주 마감은 몇 건인가요?",
         "a": f"나라장터 수집 기준으로 이번 주 마감 {n_label(t, 'urgent')}입니다."},
        {"q": "참가 자격은 이 사이트에서 보이나요?",
         "a": "면허·실적 같은 참가 자격은 원문 공고를 기준으로 합니다. "
              "이 목록은 마감일시와 수요기관을 먼저 보여 줍니다."},
    ]


def region_faqs(rname, items, t):
    return [
        {"q": f"{rname} 지역 입찰은 어떻게 고르나요?",
         "a": f"나라장터 참가제한·참가가능 지역 표기가 '{rname}'과 정확히 같은 공고만 모았습니다. "
              "제목에서 지역을 추측하지 않습니다."},
        {"q": f"{rname}에서 이번 주 마감은 몇 건인가요?",
         "a": f"나라장터 수집 기준으로 이번 주 마감 {n_label(t, 'urgent')}, 진행 중 {n_label(t, 'open')}입니다."},
    ]


def empty_copy(what):
    return f"지금 표시할 {what}이 없습니다. 나라장터 자료는 매일 아침 갱신됩니다."


def latest_revisions(rows):
    """같은 공고번호의 차수(-000, -001 …) 중 가장 높은 차수 id 를 돌려준다.
    {id: 최신 id}. 차수 표기가 없으면 자기 자신."""
    best = {}
    for a in rows:
        i = str(a.get("id") or "")
        base, _, ordr = i.rpartition("-")
        if not base or not ordr.isdigit():
            continue
        if base not in best or int(ordr) > int(best[base].rpartition("-")[2]):
            best[base] = i
    out = {}
    for a in rows:
        i = str(a.get("id") or "")
        base, _, ordr = i.rpartition("-")
        out[i] = best.get(base, i) if base and ordr.isdigit() else i
    return out


LATEST = {}


# Cloudflare Pages 는 배포당 파일 2만 개까지다. 마감 입찰은 하루 약 1천 건씩 쌓여
# 180일을 다 살리면 한도를 넘어 배포가 통째로 실패한다(2026-10-29, 아카이브 25,324건).
# 아카이브 상세는 이 개수까지만 만든다. 나머지 지원·입찰 페이지 약 4천 개와 합쳐도 여유가 남는다.
ARCHIVE_PAGE_MAX = 12000


def cap_archived(archived, keep_indexed=None, limit=ARCHIVE_PAGE_MAX):
    """아카이브 상세를 limit 개로 줄인다. 검색 유입이 있던 URL(keep_indexed)을 먼저,
    나머지는 최근 마감 순(archived_bids 정렬 그대로). 빠진 상세는 404.html 로 진짜 404 다
    (어차피 noindex 였던 마감 입찰)."""
    if len(archived) <= limit:
        return archived
    keep = set(keep_indexed or ())
    first = [a for a in archived if f"/bid/notice/{a.get('id')}/" in keep]
    rest = [a for a in archived if f"/bid/notice/{a.get('id')}/" not in keep]
    out = (first + rest)[:limit]
    print(f"입찰 아카이브 상세 {len(archived)}건 중 {len(out)}건만 생성 (배포 파일 수 한도)")
    return out


def build(env, write, site, urls, dist, noindex_sink=None, keep_indexed=None):
    """입찰 트리를 dist/ 에 추가하고, 생성한 경로 수를 반환한다."""
    before = len(urls)
    rows = bidinfo.load()
    # 건수는 상한(MAX_BIDS) 전 전체 기준. 카드·상세 페이지는 rows(상한 적용)만 만든다.
    full_rows = list(bidinfo.FULL) or list(rows)
    t_all = tally(rows, full_rows)
    by_kind = {k["name"]: [a for a in rows if a.get("kind") == k["name"]]
               for k in BID_KINDS}
    by_reg = {r["name"]: [a for a in rows if a.get("region") == r["name"]]
              for r in BID_REGIONS}
    # 칩 건수도 목록 상한(500) 전 전체 기준. 페이지는 상한 안의 카드로만 만든다.
    full_by_kind = {k["name"]: sum(1 for a in full_rows if a.get("kind") == k["name"] and a.get("is_open"))
                    for k in BID_KINDS}
    full_by_reg = {r["name"]: sum(1 for a in full_rows if a.get("region") == r["name"] and a.get("is_open"))
                   for r in BID_REGIONS}
    kind_chips = [{"name": k["name"], "url": f"/bid/kind/{k['slug']}/",
                   "count": full_by_kind[k["name"]]}
                  for k in BID_KINDS]
    reg_chips = [{"name": r["name"], "url": f"/bid/region/{r['slug']}/",
                  "count": full_by_reg[r["name"]]}
                 for r, v in ((r, by_reg[r["name"]]) for r in BID_REGIONS) if v]
    env.globals["bid_has_regions"] = bool(reg_chips)

    def render_list(path, h1, lede, items, *, title=None, desc=None,
                    intro=None, faqs=None, blocks=None, sections=None,
                    beginner=False, crumbs=None, empty=None, bid_empty=None,
                    sel_kind="", sel_due="", sel_region="", limit=20, page="list",
                    full=None):
        n = len(items)
        sections = sections or []
        blocks = blocks or []
        if bid_empty is None:
            bid_empty = not items and not sections
        ad_top, ad_mid_after, ad_bottom = intros.resolve_ads(
            intros.ad_plan(0 if bid_empty else n, has_sections=bool(sections) and not bid_empty), site)
        crumbs = crumbs or []
        html = env.get_template("bid_list.html").render(
            site=site, path=path, section="bid", page=page,
            title=title or f"{h1} | {site['name']}",
            desc=desc or lede, h1=h1, lede=lede, items=items,
            tally=None if bid_empty else (tally(items, full) if not sections else t_all),
            intro=intro or "", faqs=faqs or [],
            faq_jsonld=intros.faq_jsonld(faqs or []),
            blocks=[] if bid_empty else blocks, sections=[] if bid_empty else sections,
            beginner=False if bid_empty else beginner,
            empty=empty or empty_copy("입찰공고"),
            bid_empty=bid_empty, no_ads=bid_empty,
            crumbs=crumbs, crumb_jsonld=_crumb_ld(crumbs, site),
            ad_top=None if bid_empty else ad_top,
            ad_mid_after=None if bid_empty else ad_mid_after,
            ad_bottom=None if bid_empty else ad_bottom,
            bid_kinds=BID_KINDS, today=0 if bid_empty else (
                tally(items, full).get("today", 0)
                if not sections else t_all.get("today", 0)),
            sel_kind=sel_kind, sel_due=sel_due, sel_region=sel_region,
            limit=0 if bid_empty else limit,
            collected_at=env.globals.get("collected_at") or "",
            alert_email=site.get("email") or "",
            today_rail=[] if bid_empty else filt.today_rail(items),
            related_hubs=[] if bid_empty else intros.bid_related_hubs(
                path=path, kind_slug=sel_kind,
                region_slug=(REGS.get(sel_region) or {}).get("slug", "")),
        )
        write(path, html)

    open_rows = [a for a in rows if a.get("is_open")]
    week = [a for a in open_rows if 0 <= a["dday"] <= 7]
    full_open = [a for a in full_rows if a.get("is_open")]
    full_week = [a for a in full_open if 0 <= a["dday"] <= 7]
    # "진행중"은 전체 진행 중(full_open), "이번 주 마감"은 그중 7일 안. 같은 목록으로 세면 둘이 늘 같아진다.
    t_week = tally(week, full_open)

    hub_empty = not open_rows
    if hub_empty:
        faqs = empty_hub_faqs()
        intro = empty_hub_intro()
        lede = "지금은 표시할 진행 중 입찰이 없습니다. 나라장터 원문과 지원사업은 아래에서 갈 수 있습니다."
        hub_blocks = []
        hub_items = []
    else:
        faqs = hub_faqs(t_all)
        intro = hub_intro(t_all)
        lede = ("오늘 마감되는 입찰부터 봅니다. 물품·용역·공사·외자로 나눕니다."
                + cap_note(len(open_rows), len(full_open)))
        hub_blocks = [{"title": "종류로 찾기", "items": kind_chips}]
        if reg_chips:
            hub_blocks.append({"title": "참가지역으로 찾기", "items": reg_chips})
        hub_items = open_rows
    render_list(
        "/bid/", serp.bid_hub_h1(),
        lede,
        hub_items,
        title=serp.bid_hub_title(None if hub_empty else t_all),
        desc=serp.bid_hub_desc(None if hub_empty else t_all),
        full=full_open,
        intro=intro, faqs=faqs, beginner=not hub_empty,
        blocks=hub_blocks, limit=20,
        crumbs=[{"name": "홈", "url": "/"}, {"name": "입찰", "url": "/bid/"}],
        empty=("나라장터 연동이 꺼져 있거나, 오늘 기준 진행 중인 공고가 없습니다."
               if hub_empty else empty_copy("입찰공고")),
        bid_empty=hub_empty,
    )

    render_list(
        "/bid/urgent/", serp.bid_urgent_h1(),
        "7일 안에 마감일시가 있는 입찰만 모았습니다." + cap_note(len(week), len(full_week)),
        week,
        title=serp.bid_urgent_title(t_week["urgent"], more=t_week["more"]),
        desc=serp.bid_urgent_desc(t_week["urgent"], more=t_week["more"]),
        full=full_open,
        faqs=[
            {"q": "이번 주 마감 입찰은 몇 건인가요?",
             "a": f"나라장터에서 받은 전체 기준으로 {n_label(t_week, 'urgent')}입니다. 마감일시는 나라장터 원문을 따릅니다."},
            {"q": "지원사업 마감임박은 어디에 있나요?",
             "a": "지원사업 마감임박은 홈의 마감임박 메뉴에서 봅니다. 이 페이지는 입찰만 다룹니다."},
        ],
        blocks=[{"title": "종류로 찾기", "items": kind_chips}],
        crumbs=[{"name": "홈", "url": "/"},
                {"name": "입찰", "url": "/bid/"},
                {"name": "마감임박", "url": "/bid/urgent/"}],
        empty=empty_copy("이번 주 마감 입찰"),
        sel_due="week", limit=20,
    )

    for kind in BID_KINDS:
        items = by_kind[kind["name"]]
        kfull = [a for a in full_rows if a.get("kind") == kind["name"]]
        kt = tally(items, kfull)
        kfaqs = kind_faqs(kind, items, kt)
        render_list(
            f"/bid/kind/{kind['slug']}/",             f"{kind['name']} 입찰공고",
            (
                f"{kind['desc']}. 마감일시가 가까운 순입니다. "
                + (f"오늘 마감 {n_label(kt, 'today')}입니다." if kt.get("today") else
                   f"이번 주 마감 {n_label(kt, 'urgent')}입니다." if kt.get("urgent") else
                   f"진행 중 {n_label(kt, 'open')}입니다.")
            ),
            items,
            title=serp.bid_kind_title(kind["name"], kt["open"], more=kt["more"]),
            desc=serp.bid_kind_desc(kind["name"], kt["open"], kind.get("desc") or "", more=kt["more"]),
            full=kfull,
            intro=(f"<p>{kind['desc']}입니다. 나라장터 수집 기준으로 진행 중 {n_label(kt, 'open')}, "
                   f"이번 주 마감 {n_label(kt, 'urgent')}입니다. "
                   "추정가격은 나라장터에 값이 있을 때만 보여 줍니다.</p>"),
            faqs=kfaqs,
            blocks=[{"title": "다른 종류", "items": [c for c in kind_chips if c["name"] != kind["name"]]}],
            crumbs=[{"name": "홈", "url": "/"},
                    {"name": "입찰", "url": "/bid/"},
                    {"name": kind["name"], "url": f"/bid/kind/{kind['slug']}/"}],
            empty=empty_copy(f"{kind['name']} 입찰"),
            sel_kind=kind["slug"], limit=20,
        )

    if reg_chips:
        render_list(
            "/bid/region/", "참가지역으로 찾기",
            "나라장터 참가제한·참가가능 지역 표기가 허용 목록과 정확히 같은 공고만 모았습니다.",
            [a for a in rows if a.get("region")],
            title=serp.bid_region_hub_title(),
            desc=serp.bid_region_hub_desc(),
            faqs=[
                {"q": "왜 모든 시·도가 없나요?",
                 "a": "참가제한·참가가능 지역 필드가 허용 목록과 정확히 같은 공고만 지역 페이지를 만듭니다. "
                      "제목에서 지역을 추측하지 않습니다."},
                {"q": "지역이 안 적힌 공고는 어디에 있나요?",
                 "a": "입찰 허브와 종류별 목록에 그대로 있습니다. 지역을 비워 둔 채 보여 줍니다."},
            ],
            blocks=[{"title": "참가지역", "items": reg_chips}],
            crumbs=[{"name": "홈", "url": "/"},
                    {"name": "입찰", "url": "/bid/"},
                    {"name": "지역", "url": "/bid/region/"}],
            empty=empty_copy("지역이 확인된 입찰"),
            limit=20,
        )
        for r in BID_REGIONS:
            items = by_reg[r["name"]]
            if not items:
                continue
            rfull = [a for a in full_rows if a.get("region") == r["name"]]
            rt = tally(items, rfull)
            render_list(
                f"/bid/region/{r['slug']}/", f"{r['name']} 참가지역 입찰",
                f"참가지역 표기가 {r['name']}과 정확히 같은 공고입니다.",
                items,
                title=serp.bid_region_title(r["name"], len(rfull), more=rt["more"]),
                desc=serp.bid_region_desc(r["name"], len(rfull), more=rt["more"]),
                full=rfull,
                faqs=region_faqs(r["name"], items, rt),
                blocks=[{"title": "다른 지역", "items": [c for c in reg_chips if c["name"] != r["name"]]}],
                crumbs=[{"name": "홈", "url": "/"},
                        {"name": "입찰", "url": "/bid/"},
                        {"name": "지역", "url": "/bid/region/"},
                        {"name": r["name"], "url": f"/bid/region/{r['slug']}/"}],
                empty=empty_copy(f"{r['name']} 입찰"),
                sel_region=r["name"], limit=20,
            )

    def render_notice(a):
        rel = filt.related_bids(a, open_rows, limit=6)
        npath = f"/bid/notice/{a['id']}/"
        # 이전 차수는 최신 차수로 canonical 하고 sitemap 에서 뺀다 (중복 제목 방지).
        latest = LATEST.get(str(a.get("id") or ""), a.get("id"))
        canonical_path = f"/bid/notice/{latest}/" if latest != a.get("id") else None
        # 마감·취소된 입찰은 다시 투찰할 수 없어 검색 유입 가치가 낮다. HTML 은
        # 남기고(링크·북마크 보존) noindex,follow + sitemap 제외. 서치콘솔에서
        # 노출·클릭이 있던 URL(keep_indexed)은 그대로 색인한다.
        closed_thin = (not canonical_path and not a.get("is_open")
                       and npath not in (keep_indexed or ()))
        kslug = a.get("kind_slug") or slug_of(a.get("kind"))
        crumbs = [{"name": "홈", "url": "/"},
                  {"name": "입찰", "url": "/bid/"}]
        if kslug:
            crumbs.append({"name": a.get("kind") or "종류",
                           "url": f"/bid/kind/{kslug}/"})
        crumbs.append({"name": a.get("title") or "공고", "url": npath})
        ld_obj = {
            "@context": "https://schema.org",
            "@type": "GovernmentService",
            "name": a.get("title") or "",
            "url": site["domain"] + npath,
            "identifier": a.get("notice_no") or a.get("bid_no") or a.get("id") or "",
            "provider": {"@type": "GovernmentOrganization",
                         "name": a.get("org") or a.get("ntce_org") or ""},
            "description": a.get("blurb") or a.get("title") or "",
        }
        if a.get("region"):
            ld_obj["areaServed"] = a["region"]
        if a.get("posted_at") or a.get("open_dt"):
            ld_obj["datePublished"] = a.get("posted_at") or a.get("open_dt")
        if a.get("detail_url"):
            ld_obj["sameAs"] = a["detail_url"]
        ld_obj["isBasedOn"] = "나라장터"
        faqs = detail_faq.bid_notice_faqs(a)
        howto = detail_faq.bid_notice_howto(a)
        rel_ids = [x.get("id") for x in rel]
        compare = detail_extra.bid_compare_rows(a, open_rows, limit=5, exclude=rel_ids)
        agency = detail_extra.bid_agency_others(
            a, open_rows, limit=5, exclude=rel_ids + [c["id"] for c in compare])
        html = env.get_template("bid_detail.html").render(
            compare=compare, agency=agency,
            site=site, path=npath, section="bid", page="bid-detail",
            canonical_path=canonical_path,
            noindex=closed_thin,
            title=serp.bid_notice_title(a),
            desc=serp.bid_notice_desc(a),
            a=a, related=rel,
            crumbs=crumbs, crumb_jsonld=_crumb_ld(crumbs, site),
            jsonld=json.dumps(ld_obj, ensure_ascii=False),
            faq_jsonld=intros.faq_jsonld(faqs),
            faqs=faqs, howto=howto,
            howto_jsonld=detail_faq.howto_jsonld(
                f"{a.get('title') or '입찰'} 투찰 순서",
                serp.bid_notice_desc(a), howto),
            bid_kinds=BID_KINDS,
            collected_at=a.get("collected_at") or env.globals.get("collected_at") or "",
        )
        lm = ""
        keys = ("close_dt", "posted_at") if not a.get("is_open") else ("posted_at", "open_dt", "collected_at")
        for key in keys:
            lm = str(a.get(key) or "")[:10]
            if len(lm) == 10 and lm[4] == "-" and lm[7] == "-":
                break
            lm = ""
        if canonical_path or closed_thin:
            write(npath, html, index=False)
            if noindex_sink is not None:
                noindex_sink.append(npath)
        else:
            write(npath, html, lastmod=lm or None, changefreq="weekly")

    def slug_of(name):
        return bidinfo.slug_of_kind(name)

    collected_at = env.globals.get("collected_at") or dl.collected_stamp()
    for a in rows:
        a["collected_at"] = collected_at
        a["posted_iso"] = iso_date(a.get("posted_at") or a.get("open_dt"))
        a["source"] = "g2b"
        a["source_label"] = a.get("source_label") or "나라장터"
        a["notice_no"] = a.get("notice_no") or a.get("bid_no") or a.get("id") or ""
        a["amount_band"] = filt.bid_amount_band_id(a)

    # 목록에서 빠진 마감 입찰도 180일간 상세를 살린다 (색인·백링크 유지).
    archived = cap_archived(bidinfo.archived_bids(rows), keep_indexed)
    LATEST.update(latest_revisions(list(rows) + list(archived)))

    for a in rows:
        render_notice(a)

    for a in archived:
        a["collected_at"] = collected_at
        a["posted_iso"] = iso_date(a.get("posted_at") or a.get("open_dt"))
        a["notice_no"] = a.get("notice_no") or a.get("bid_no") or a.get("id") or ""
        a["amount_band"] = filt.bid_amount_band_id(a)
        render_notice(a)
    if archived:
        print(f"입찰 아카이브 상세페이지 {len(archived)}건 유지")

    feed = [filt.compact_bid(a) for a in rows]
    # write() 는 index.html 전용이라 피드 파일은 직접 둔다.
    with open(os.path.join(dist, "bids.json"), "w", encoding="utf-8") as f:
        json.dump(feed, f, ensure_ascii=False, separators=(",", ":"))

    added = len(urls) - before
    print(f"입찰 {len(rows)}건 → 페이지 {added}개 추가")
    return added


def notice_faqs(a):
    """입찰 상세 FAQ. 화면에 보이는 필드만. 지원금 어휘 없음."""
    return detail_faq.bid_notice_faqs(a)
