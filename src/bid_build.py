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
import intros

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
                    beginner=False, crumbs=None, empty=None):
        n = len(items)
        ad_top, ad_mid_after, ad_bottom = intros.resolve_ads(
            intros.ad_plan(n, has_sections=bool(sections)), site)
        crumbs = crumbs or []
        html = env.get_template("bid_list.html").render(
            site=site, path=path, section="bid",
            title=title or f"{h1} | {site['name']}",
            desc=desc or lede, h1=h1, lede=lede, items=items,
            tally=tally(items) if not sections else t_all,
            intro=intro or "", faqs=faqs or [],
            faq_jsonld=intros.faq_jsonld(faqs or []),
            blocks=blocks or [], sections=sections or [],
                beginner=beginner, empty=empty or empty_copy("입찰공고"),
            crumbs=crumbs, crumb_jsonld=_crumb_ld(crumbs, site),
            ad_top=ad_top, ad_mid_after=ad_mid_after, ad_bottom=ad_bottom,
            bid_kinds=BID_KINDS, today=sum(1 for a in items if a.get("is_open") and a.get("dday") == 0)
            if not sections else t_all.get("today", 0),
        )
        write(path, html)

    open_rows = [a for a in rows if a.get("is_open")]
    week = [a for a in open_rows if 0 <= a["dday"] <= 7]
    today_rows = [a for a in open_rows if a["dday"] == 0]
    later = [a for a in open_rows if a["dday"] > 7]
    sections = []
    if week:
        sections.append({"title": "이번 주 마감", "items": week[:8],
                         "href": "/bid/urgent/", "total": len(week)})
    if later:
        sections.append({"title": "이후 마감", "items": later[:8],
                         "href": "", "total": len(later)})
    if not sections and open_rows:
        sections.append({"title": "진행 중인 입찰", "items": open_rows[:8],
                         "href": "/bid/urgent/", "total": len(open_rows)})

    faqs = hub_faqs(t_all)
    render_list(
        "/bid/", "나라장터 입찰, 마감일시 순",
        "오늘 마감되는 입찰부터 봅니다. 물품·용역·공사·외자로 나눕니다.",
        [],
        title=f"나라장터 입찰공고 마감일시 | {site['name']}",
        desc="나라장터 입찰공고를 마감일시 순으로 정리합니다. 물품·용역·공사·외자, 수요기관, 추정가격을 확인할 수 있습니다.",
        intro=hub_intro(t_all), faqs=faqs, beginner=True,
        sections=sections,
        blocks=[{"title": "종류로 찾기", "items": kind_chips}]
               + ([{"title": "참가지역으로 찾기", "items": reg_chips}] if reg_chips else []),
        crumbs=[{"name": "홈", "url": "/"}, {"name": "입찰", "url": "/bid/"}],
        empty=empty_copy("입찰공고"),
    )

    render_list(
        "/bid/urgent/", "이번 주 마감 입찰",
        "7일 안에 마감일시가 있는 입찰만 모았습니다.",
        week,
        title=f"이번 주 마감 입찰공고 | {site['name']}",
        desc=f"나라장터 입찰 중 7일 안에 마감되는 공고 {len(week)}건을 마감일시 순으로 정리했습니다.",
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
    )

    for kind in BID_KINDS:
        items = by_kind[kind["name"]]
        kt = tally(items)
        kfaqs = kind_faqs(kind, items, kt)
        render_list(
            f"/bid/kind/{kind['slug']}/", f"{kind['name']} 입찰공고",
            f"{kind['desc']}. 마감일시가 가까운 순입니다.",
            items,
            title=f"{kind['name']} 입찰공고 마감일시 | {site['name']}",
            desc=f"나라장터 {kind['name']} 입찰 {len([a for a in items if a.get('is_open')])}건을 마감일시 순으로 정리했습니다.",
            intro=(f"<p>{kind['desc']}입니다. 이 목록 기준으로 진행 중 {kt['open']}건, "
                   f"이번 주 마감 {kt['urgent']}건입니다. "
                   "추정가격은 나라장터에 값이 있을 때만 보여 줍니다.</p>"),
            faqs=kfaqs,
            blocks=[{"title": "다른 종류", "items": [c for c in kind_chips if c["name"] != kind["name"]]}],
            crumbs=[{"name": "홈", "url": "/"},
                    {"name": "입찰", "url": "/bid/"},
                    {"name": kind["name"], "url": f"/bid/kind/{kind['slug']}/"}],
            empty=empty_copy(f"{kind['name']} 입찰"),
        )

    if reg_chips:
        render_list(
            "/bid/region/", "참가지역으로 찾기",
            "나라장터 참가제한·참가가능 지역 표기가 허용 목록과 정확히 같은 공고만 모았습니다.",
            [a for a in rows if a.get("region")],
            title=f"지역별 입찰공고 | {site['name']}",
            desc="나라장터 참가지역 표기가 확인된 입찰공고를 마감일시 순으로 정리합니다.",
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
                title=f"{r['name']} 입찰공고 마감일시 | {site['name']}",
                desc=f"나라장터 참가지역이 {r['name']}인 입찰 {len(items)}건을 마감일시 순으로 정리했습니다.",
                faqs=region_faqs(r["name"], items, rt),
                blocks=[{"title": "다른 지역", "items": [c for c in reg_chips if c["name"] != r["name"]]}],
                crumbs=[{"name": "홈", "url": "/"},
                        {"name": "입찰", "url": "/bid/"},
                        {"name": "지역", "url": "/bid/region/"},
                        {"name": r["name"], "url": f"/bid/region/{r['slug']}/"}],
                empty=empty_copy(f"{r['name']} 입찰"),
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
        html = env.get_template("bid_detail.html").render(
            site=site, path=npath, section="bid", page="bid-detail",
            title=f"{a['title']} — 입찰 마감일시 | {site['name']}",
            desc=(a.get("blurb") or a.get("title") or "")[:150],
            a=a, related=rel,
            crumbs=crumbs, crumb_jsonld=_crumb_ld(crumbs, site),
            faq_jsonld=intros.faq_jsonld(notice_faqs(a)),
            faqs=notice_faqs(a),
            bid_kinds=BID_KINDS,
        )
        write(npath, html)

    def slug_of(name):
        return bidinfo.slug_of_kind(name)

    for a in rows:
        render_notice(a)

    feed = [{"i": a["id"], "t": a["title"], "k": a.get("kind") or "",
             "o": a.get("org") or "", "m": a.get("budget") or "",
             "e": a.get("close_dt") or "", "d": a["dday"],
             "r": a.get("region") or ""}
            for a in rows]
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
