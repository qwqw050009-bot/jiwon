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


def tally(items):
    return {
        "today": sum(1 for a in items if a.get("is_open") and a.get("dday") == 0),
        "urgent": sum(1 for a in items if a.get("is_open") and 0 <= a["dday"] <= 7),
        "soon": sum(1 for a in items if a.get("is_open") and 7 < a["dday"] <= 14),
        "open": sum(1 for a in items if a.get("is_open")),
    }


def hub_intro(t):
    return (
        "<p>입찰은 공공기관이 물품·용역·공사·외자를 살 때 나라장터에 올리는 공고입니다. "
        "기업이 신청해서 받는 지원사업과는 성격이 다릅니다. "
        f'<a href="/">지원사업 마감일</a>은 홈에서 따로 봅니다.</p>'
        f"<p>이 목록 기준으로 오늘 마감 {int(t['today'])}건, "
        f"이번 주 마감 {int(t['urgent'])}건, 진행 중 {int(t['open'])}건입니다.</p>"
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
         "a": f"이 목록 기준으로 오늘 마감 {int(t['today'])}건, "
              f"이번 주 마감 {int(t['urgent'])}건입니다."},
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
         "a": f"{kind['desc']}입니다. 이 목록에는 진행 중 {int(t['open'])}건이 있습니다."},
        {"q": f"{name} 입찰 중 이번 주 마감은 몇 건인가요?",
         "a": f"이 목록 기준으로 이번 주 마감 {int(t['urgent'])}건입니다."},
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
         "a": f"이 목록 기준으로 이번 주 마감 {int(t['urgent'])}건, 진행 중 {int(t['open'])}건입니다."},
    ]


def empty_copy(what):
    return f"지금 표시할 {what}이 없습니다. 나라장터 자료는 매일 아침 갱신됩니다."


def build(env, write, site, urls, dist):
    """입찰 트리를 dist/ 에 추가하고, 생성한 경로 수를 반환한다."""
    before = len(urls)
    rows = bidinfo.load()
    t_all = tally(rows)
    by_kind = {k["name"]: [a for a in rows if a.get("kind") == k["name"]]
               for k in BID_KINDS}
    by_reg = {r["name"]: [a for a in rows if a.get("region") == r["name"]]
              for r in BID_REGIONS}
    kind_chips = [{"name": k["name"], "url": f"/bid/kind/{k['slug']}/",
                   "count": len(by_kind[k["name"]])}
                  for k in BID_KINDS]
    reg_chips = [{"name": r["name"], "url": f"/bid/region/{r['slug']}/",
                  "count": len(v)}
                 for r, v in ((r, by_reg[r["name"]]) for r in BID_REGIONS) if v]
    env.globals["bid_has_regions"] = bool(reg_chips)

    def render_list(path, h1, lede, items, *, title=None, desc=None,
                    intro=None, faqs=None, blocks=None, sections=None,
                    beginner=False, crumbs=None, empty=None, bid_empty=None,
                    sel_kind="", sel_due="", sel_region="", limit=20, page="list"):
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
            tally=None if bid_empty else (tally(items) if not sections else t_all),
            intro=intro or "", faqs=faqs or [],
            faq_jsonld=intros.faq_jsonld(faqs or []),
            blocks=[] if bid_empty else blocks, sections=[] if bid_empty else sections,
            beginner=False if bid_empty else beginner,
            empty=empty or empty_copy("입찰공고"),
            bid_empty=bid_empty,
            crumbs=crumbs, crumb_jsonld=_crumb_ld(crumbs, site),
            ad_top=None if bid_empty else ad_top,
            ad_mid_after=None if bid_empty else ad_mid_after,
            ad_bottom=None if bid_empty else ad_bottom,
            bid_kinds=BID_KINDS, today=0 if bid_empty else (
                sum(1 for a in items if a.get("is_open") and a.get("dday") == 0)
                if not sections else t_all.get("today", 0)),
            sel_kind=sel_kind, sel_due=sel_due, sel_region=sel_region,
            limit=0 if bid_empty else limit,
            collected_at=env.globals.get("collected_at") or "",
            alert_email=site.get("email") or "",
        )
        write(path, html)

    open_rows = [a for a in rows if a.get("is_open")]
    week = [a for a in open_rows if 0 <= a["dday"] <= 7]

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
        lede = "오늘 마감되는 입찰부터 봅니다. 물품·용역·공사·외자로 나눕니다."
        hub_blocks = [{"title": "종류로 찾기", "items": kind_chips}]
        if reg_chips:
            hub_blocks.append({"title": "참가지역으로 찾기", "items": reg_chips})
        hub_items = open_rows
    render_list(
        "/bid/", "나라장터 입찰, 마감일시 순",
        lede,
        hub_items,
        title=serp.bid_hub_title(),
        desc=serp.bid_hub_desc(None if hub_empty else t_all),
        intro=intro, faqs=faqs, beginner=not hub_empty,
        blocks=hub_blocks, limit=20,
        crumbs=[{"name": "홈", "url": "/"}, {"name": "입찰", "url": "/bid/"}],
        empty=("나라장터 연동이 꺼져 있거나, 오늘 기준 진행 중인 공고가 없습니다."
               if hub_empty else empty_copy("입찰공고")),
        bid_empty=hub_empty,
    )

    render_list(
        "/bid/urgent/", "이번 주 마감 입찰",
        "7일 안에 마감일시가 있는 입찰만 모았습니다.",
        week,
        title=serp.bid_urgent_title(len(week)),
        desc=serp.bid_urgent_desc(len(week)),
        faqs=[
            {"q": "이번 주 마감 입찰은 몇 건인가요?",
             "a": f"이 목록 기준으로 {len(week)}건입니다. 마감일시는 나라장터 원문을 따릅니다."},
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
        kt = tally(items)
        kfaqs = kind_faqs(kind, items, kt)
        render_list(
            f"/bid/kind/{kind['slug']}/", f"{kind['name']} 입찰공고",
            f"{kind['desc']}. 마감일시가 가까운 순입니다.",
            items,
            title=serp.bid_kind_title(kind["name"], kt["open"]),
            desc=serp.bid_kind_desc(kind["name"], kt["open"], kind.get("desc") or ""),
            intro=(f"<p>{kind['desc']}입니다. 이 목록 기준으로 진행 중 {kt['open']}건, "
                   f"이번 주 마감 {kt['urgent']}건입니다. "
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
            rt = tally(items)
            render_list(
                f"/bid/region/{r['slug']}/", f"{r['name']} 참가지역 입찰",
                f"참가지역 표기가 {r['name']}과 정확히 같은 공고입니다.",
                items,
                title=serp.bid_region_title(r["name"], len(items)),
                desc=serp.bid_region_desc(r["name"], len(items)),
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
        rel = [x for x in open_rows
               if x["id"] != a["id"] and x.get("kind") == a.get("kind")][:5]
        npath = f"/bid/notice/{a['id']}/"
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
        html = env.get_template("bid_detail.html").render(
            site=site, path=npath, section="bid", page="bid-detail",
            title=serp.bid_notice_title(a),
            desc=serp.bid_notice_desc(a),
            a=a, related=rel,
            crumbs=crumbs, crumb_jsonld=_crumb_ld(crumbs, site),
            jsonld=json.dumps(ld_obj, ensure_ascii=False),
            faq_jsonld=intros.faq_jsonld(notice_faqs(a)),
            faqs=notice_faqs(a),
            bid_kinds=BID_KINDS,
            collected_at=a.get("collected_at") or env.globals.get("collected_at") or "",
        )
        write(npath, html)

    def slug_of(name):
        return bidinfo.slug_of_kind(name)

    collected_at = env.globals.get("collected_at") or dl.collected_stamp()
    for a in rows:
        a["collected_at"] = collected_at
        a["source"] = "g2b"
        a["source_label"] = a.get("source_label") or "나라장터"
        a["notice_no"] = a.get("notice_no") or a.get("bid_no") or a.get("id") or ""
        a["amount_band"] = filt.bid_amount_band_id(a)

    for a in rows:
        render_notice(a)

    feed = [filt.compact_bid(a) for a in rows]
    # write() 는 index.html 전용이라 피드 파일은 직접 둔다.
    with open(os.path.join(dist, "bids.json"), "w", encoding="utf-8") as f:
        json.dump(feed, f, ensure_ascii=False, separators=(",", ":"))

    added = len(urls) - before
    print(f"입찰 {len(rows)}건 → 페이지 {added}개 추가")
    return added


def notice_faqs(a):
    close = a.get("close_dt") or "원문 확인"
    org = a.get("org") or "수요기관 원문 확인"
    qa = [
        {"q": "마감일시는 언제인가요?",
         "a": f"마감일시는 {close}입니다. 창구 마감은 나라장터 원문을 따릅니다."},
        {"q": "수요기관은 어디인가요?",
         "a": f"수요기관은 {org}입니다."},
    ]
    if a.get("budget"):
        qa.append({"q": "추정가격은 얼마인가요?",
                   "a": f"나라장터에 적힌 추정가격은 {a['budget']}입니다. "
                        "이 숫자가 아니면 원문을 따르세요."})
    else:
        qa.append({"q": "추정가격은 얼마인가요?",
                   "a": "이 공고는 나라장터 응답에 추정가격이 없습니다. 원문에서 확인하세요."})
    return qa
