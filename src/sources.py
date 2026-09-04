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


class JsonSource:
    """이미 정규화된 JSON (data/api_cache.json 등). 키가 없을 때 캐시 검증용."""

    def __init__(self, path=None):
        self.path = path or os.path.join(DATA_DIR, "api_cache.json")

    def fetch(self):
        with open(self.path, encoding="utf-8") as f:
            return json.load(f)


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


def _process(rows):
    """D-day 계산 + 마감 일주일 지난 것 제외. 정렬은 안 한다(호출부에서 합친 뒤 한 번에)."""
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
    return out


def _sort_key(x):
    return (x.get("period_type") == "always", not x["is_open"], x["dday"])


def load(source=None):
    src = source or MockSource()
    rows = _process(src.fetch())
    rows.sort(key=_sort_key)
    return rows


def merge_extra(rows, extra_raw):
    """
    이미 load()를 거친 rows에 보강 데이터소스(K-Startup 등)를 합친다.
    제목이 정확히 겹치는 공고는 같은 사업의 중복 게시로 보고 건너뛴다
    (기업마당 쪽을 우선 유지 — 이미 커버리지가 넓고 먼저 들어온 소스라서).
    나머지는 동일한 D-day 계산을 거쳐 합친 뒤 다시 정렬한다.
    반환값: (합쳐진 rows, 중복이라 제외된 건수)
    """
    existing_titles = {(r.get("title") or "").strip() for r in rows}
    fresh = [r for r in extra_raw if (r.get("title") or "").strip() not in existing_titles]
    merged = rows + _process(fresh)
    merged.sort(key=_sort_key)
    return merged, len(extra_raw) - len(fresh)
