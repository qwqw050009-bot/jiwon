# -*- coding: utf-8 -*-
"""
기업마당 실데이터 어댑터.

실응답 확인 결과 (2026-09-03, totalCount 1560):
  pblancNm                    공고명. 앞에 [경기] 형태로 지역이 붙음
  jrsdInsttNm                 소관기관 = 광역시도명 ("경기도")  ← 지역 축의 1차 소스
  excInsttNm                  수행기관 ("기초자치단체", "경기도경제과학진흥원")
  pldirSportRealmLclasCodeNm  분야 (경영/수출/인력/...)
  reqstBeginEndDe             "2026-09-01 ~ 2026-10-02"  ← 마감일
  trgetNm                     지원대상 ("중소기업")
  bsnsSumryCn                 HTML 본문. ☞ 로 구분된 대상/지원내용
  hashtags                    "경영,경기,2026,안산시,..." 분야+지역+키워드
  creatPnttm / updtPnttm      등록/수정 시각 → 신규·변경 감지
  inqireCo                    조회수 → 인기도 정렬 가능
  reqstMthPapersCn            신청방법
  refrncNm                    문의처
  pblancUrl                   원문 링크

중요: 지역을 추측 파싱할 필요가 없다.
      jrsdInsttNm / 제목 접두 / hashtags 세 곳에서 교차 확인 가능.
"""
import html
import json
import os
import re
from datetime import date

# 2026년 기준 실데이터에서 확인된 광역 구분.
# 주의: 전남광주통합특별시는 광주+전남이 통합된 단위로 실제 응답에 등장한다.
SIDO = {
    "서울": "seoul", "부산": "busan", "대구": "daegu", "인천": "incheon",
    "대전": "daejeon", "울산": "ulsan", "세종": "sejong", "경기": "gyeonggi",
    "강원": "gangwon", "충북": "chungbuk", "충남": "chungnam",
    "전북": "jeonbuk", "전남광주": "jeonnam-gwangju",
    "경북": "gyeongbuk", "경남": "gyeongnam", "제주": "jeju",
}

# 소관기관 정식명 → 광역 키. 실응답에 나온 표기를 그대로 매핑한다.
ORG_ALIAS = {
    "서울특별시": "서울", "부산광역시": "부산", "대구광역시": "대구",
    "인천광역시": "인천", "대전광역시": "대전", "울산광역시": "울산",
    "세종특별자치시": "세종", "경기도": "경기", "강원특별자치도": "강원",
    "충청북도": "충북", "충청남도": "충남", "전북특별자치도": "전북",
    "전남광주통합특별시": "전남광주", "경상북도": "경북",
    "경상남도": "경남", "제주특별자치도": "제주",
}

TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"[ \t\xa0]+")


def _region(item):
    """지역 판정. 3중 교차 확인. 못 찾으면 '전국' (추측 금지)."""
    # 1) 제목 접두 [경기] / [전남광주]  ← 긴 키부터 매칭
    m = re.match(r"\s*\[([^\]]+)\]", item.get("pblancNm") or "")
    if m:
        head = m.group(1).strip()
        for k in sorted(SIDO, key=len, reverse=True):
            if head.startswith(k):
                return k
    # 2) 소관기관명 (정식 표기 → 별칭 매핑)
    j = (item.get("jrsdInsttNm") or "").strip()
    if j in ORG_ALIAS:
        return ORG_ALIAS[j]
    # 3) 해시태그
    # 3) 해시태그. 단 전 지역이 나열된 경우는 전국 사업이므로 제외한다.
    tags = [t.strip() for t in (item.get("hashtags") or "").split(",")]
    hit = [t for t in tags if t in SIDO]
    if len(hit) == 1:
        return hit[0]
    return "전국"


def _clean_title(t):
    """제목에서 [경기] 접두 제거 (지역은 별도 필드로 관리)."""
    return re.sub(r"^\s*\[[^\]]+\]\s*", "", t or "").strip()


def _text(h):
    """HTML 본문 → 평문."""
    if not h:
        return ""
    s = TAG_RE.sub("\n", h)
    s = html.unescape(s)
    s = s.replace("ㆍ", "·")
    s = WS_RE.sub(" ", s)
    return "\n".join(x.strip() for x in s.split("\n") if x.strip())


def _split_summary(h):
    """
    본문은 '☞ 대상' / '☞ 지원내용' 패턴을 따른다.
    첫 문단 = 개요, ☞ 항목들 = 대상/지원내용.
    """
    body = _text(h)
    parts = [p.strip() for p in body.split("☞") if p.strip()]
    if not parts:
        return body, []
    return parts[0], [re.sub(r"^[-\s]*", "", p) for p in parts[1:]]


# 실데이터 100건 기준 18%가 날짜가 아닌 표현으로 온다.
# 이 공고들은 버리지 않고 '상시' 유형으로 분류해 목록 하단에 배치한다.
ALWAYS_OPEN = ("상시", "수시", "예산", "소진", "차수별", "회차별", "모집 완료")


def _period(s):
    """
    '2026-09-01 ~ 2026-10-02' → ('2026-09-01', '2026-10-02', 'dated')
    '예산 소진시까지'          → (None, None, 'always')
    파싱 불가                  → (None, None, 'unknown')
    """
    if not s:
        return None, None, "unknown"
    m = re.findall(r"(\d{4})[-.](\d{2})[-.](\d{2})", s)
    if len(m) >= 2:
        return "-".join(m[0]), "-".join(m[-1]), "dated"
    if len(m) == 1:
        return "-".join(m[0]), None, "always"
    if any(k in s for k in ALWAYS_OPEN):
        return None, None, "always"
    return None, None, "unknown"


def normalize(item):
    raw_period = item.get("reqstBeginEndDe") or ""
    start, end, ptype = _period(raw_period)
    overview, points = _split_summary(item.get("bsnsSumryCn"))
    return {
        "id": (item.get("pblancId") or "").replace("PBLN_", "").lstrip("0") or "0",
        "title": _clean_title(item.get("pblancNm")),
        "raw_title": item.get("pblancNm") or "",
        "category": item.get("pldirSportRealmLclasCodeNm") or "기타",
        "region": _region(item),
        "org": item.get("jrsdInsttNm") or "",
        "exec_org": item.get("excInsttNm") or "",
        "target": item.get("trgetNm") or "",
        "apply_start": start,
        "apply_end": end,
        "period_type": ptype,      # dated / always / unknown
        "period_raw": raw_period,  # '예산 소진시까지' 등 원문 표기 그대로 노출
        "method": item.get("reqstMthPapersCn") or "",
        "contact": item.get("refrncNm") or "",
        "detail_url": item.get("pblancUrl") or "",
        "views": item.get("inqireCo") or 0,
        "created": (item.get("creatPnttm") or "")[:10],
        "updated": (item.get("updtPnttm") or "")[:10],
        "overview": overview,
        "points": points,
        "tags": [t.strip() for t in (item.get("hashtags") or "").split(",") if t.strip()],
    }


class BizinfoSource:
    """운영용. BIZINFO_KEY 환경변수 필요."""
    URL = "https://apis.data.go.kr/1421000/bizinfo/pblancBsnsService"

    def __init__(self, key=None, pages=None):
        self.key = key or os.environ.get("BIZINFO_KEY", "")
        self.pages = pages

    def fetch(self):
        import urllib.parse, urllib.request
        out, page = [], 1
        while True:
            q = urllib.parse.urlencode({
                "serviceKey": self.key, "dataType": "json",
                "pageNo": page, "numOfRows": 100,
            }, safe="%")
            with urllib.request.urlopen(f"{self.URL}?{q}", timeout=30) as r:
                data = json.loads(r.read().decode("utf-8"))
            body = data.get("response", {}).get("body", {})
            items = body.get("items", {}).get("item", []) or []
            out += [normalize(i) for i in items]
            total = body.get("totalCount", 0)
            if self.pages and page >= self.pages:
                break
            if page * 100 >= total or not items:
                break
            page += 1
        # 상시 접수 공고도 유지한다. 판단 불가(unknown)만 제외.
        return [r for r in out if r["period_type"] != "unknown"]


class SampleSource:
    """저장된 실응답으로 매핑 검증."""
    def __init__(self, path):
        self.path = path

    def fetch(self):
        with open(self.path, encoding="utf-8") as f:
            data = json.load(f)
        items = data["response"]["body"]["items"]["item"]
        return [normalize(i) for i in items]
