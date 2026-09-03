# -*- coding: utf-8 -*-
"""
데이터 소스 계층.

지금은 MockSource가 돌아감. API 키 받으면 BizinfoSource 하나만 켜면 되고
build.py 는 한 줄도 안 고쳐도 됨. (같은 dict 스키마를 뱉도록 맞춰놨음)

표준 스키마:
  id, title, category, region, org, apply_start, apply_end,
  target, amount, method, detail_url
"""
import hashlib
import json
import os
from datetime import date, timedelta

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def _mk_id(title, org):
    return hashlib.md5(f"{title}{org}".encode()).hexdigest()[:10]


class MockSource:
    """API 없이 구조/디자인/SEO를 완성하기 위한 더미 소스."""

    def fetch(self):
        with open(os.path.join(DATA_DIR, "mock.json"), encoding="utf-8") as f:
            rows = json.load(f)
        for r in rows:
            r["id"] = _mk_id(r["title"], r["org"])
        return rows


class BizinfoSource:
    """
    기업마당 오픈API. 인증키 받으면 아래 주석 해제하고 build.py에서 교체.

    def fetch(self):
        import requests
        url = "https://www.bizinfo.go.kr/uss/rss/bizinfoApi.do"
        params = {"crtfcKey": os.environ["BIZINFO_KEY"],
                  "dataType": "json", "searchCnt": 500}
        raw = requests.get(url, params=params, timeout=30).json()
        items = raw["jsonArray"]
        return [self._normalize(i) for i in items]

    def _normalize(self, i):
        # 기업마당 필드 → 표준 스키마 매핑
        return {
            "id": _mk_id(i.get("pblancNm",""), i.get("jrsdInsttNm","")),
            "title": i.get("pblancNm"),
            "category": i.get("pldirSportRealmLclasCodeNm"),
            "region": self._region(i.get("pblancNm","")),
            "org": i.get("jrsdInsttNm"),
            "apply_start": i.get("reqstBeginEndDe","").split("~")[0].strip(),
            "apply_end": i.get("reqstBeginEndDe","").split("~")[-1].strip(),
            "target": i.get("trgetNm",""),
            "amount": "",
            "method": i.get("reqstMthPapersCn",""),
            "detail_url": "https://www.bizinfo.go.kr" + i.get("pblancUrl",""),
        }
    """
    pass


def load(source=None):
    src = source or MockSource()
    rows = src.fetch()
    today = date.today()
    out = []
    for r in rows:
        if r.get("period_type") == "always":
            r["dday"], r["is_open"] = 9999, True
            out.append(r)
            continue
        try:
            end = date.fromisoformat(r["apply_end"])
        except Exception:
            continue
        r["dday"] = (end - today).days
        if r["dday"] < -7:      # 마감 일주일 지난 건 제외
            continue
        r["is_open"] = r["dday"] >= 0
        out.append(r)
    out.sort(key=lambda x: (x.get("period_type") == "always",
                            not x["is_open"], x["dday"]))
    return out
