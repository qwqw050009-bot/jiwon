# -*- coding: utf-8 -*-
"""
K-Startup(창업진흥원) 오픈API 어댑터. 창업 분야 상세페이지 데이터 깊이 보강용.

기업마당과 역할이 다르다: 기업마당은 지역·분야 커버리지가 넓고,
K-Startup은 창업 분야 하나에 집중하는 대신 지원대상/신청방법/우대사항이
HTML 본문에 뭉쳐 있지 않고 API 필드로 분리돼 있다. 그래서 이 소스는
전체 대체가 아니라 "창업" 카테고리 보강용으로만 쓴다.

실응답 확인 결과 (2026-09-04, kstartup_sample.xml에 원본 저장):
  응답 포맷      dataType=json을 보내도 항상 XML로 온다.
                <results><currentCount>N</currentCount><matchCount>..
                <page>..><perPage>..><totalCount>..>
                <data><item><col name="필드명">값</col>...</item></data></results>
  페이지네이션   요청 파라미터는 pageNo/numOfRows가 아니라 page/perPage.
                (pageNo/numOfRows를 보냈더니 서버가 무시하고 자기 기본값
                 page=1/perPage=10으로 응답했다 — 실제 호출로 확인.)
  필터          rcrt_prgs_yn=Y 를 안 걸면 전체 29,988건(수년치 전체 공고)이
                다 나온다. 모집 중인 것만 서버에서 걸러야 페이지 수가 감당된다.
  인코딩        본문에 &amp;amp; 같은 이중 escape가 실제로 들어있다
                (예: "기술개발(R&amp;amp;D)"). html.unescape를 두 번 적용해야
                "R&D"까지 풀린다.

확인된 필드 → 우리 스키마 매핑 (실제 값 기준, 추측 아님):
  pbanc_sn            공고 일련번호 → id
  biz_pbanc_nm        사업공고명 → title
  pbanc_ntrp_nm       "한국여성과학기술인육성재단" 같은 실제 기관명 → org
                      (주의: sprv_inst는 "공공기관" 같은 분류값이지 기관명이
                       아니다 — 처음엔 sprv_inst를 org로 잘못 넣었다가
                       실응답 보고 바로잡음.)
  biz_prch_dprt_nm    담당부서명 → org에 괄호로 붙임
  prch_cnpl_no        "0264111064"처럼 전화번호 형식 → contact
                      (필드명 자체엔 문의처라는 근거가 없어 100% 확신은 아니다.
                       값 패턴상 가장 유력한 후보라 매핑했다.)
  supt_regin          "전국" 그대로 텍스트로 옴 → region
  supt_biz_clsfc      "기술개발(R&D)"처럼 K-Startup 자체 분류 텍스트 → category
                      키워드 매칭으로 config.CATEGORIES에 최대한 맞추고,
                      못 맞추면 "창업"으로 둔다 (이 데이터 자체가 창업진흥원
                      소스라 기본값으로 타당함).
  pbanc_rcpt_bgng_dt / _end_dt   'YYYYMMDD' → apply_start/apply_end
  aply_trgt_ctnt      신청대상 내용 → target, points
  aply_excl_trgt_ctnt 신청제외대상 → points
  prfn_matr           우대사항 (기업마당엔 없는 필드) → points
  aply_trgt / biz_trgt_age / biz_enyy   쉼표로 나열된 자격조건들 → points
  aply_mthd_*_rcpt_istc (온라인/방문/팩스/우편/이메일/기타 5종) → method
  detl_pg_url         공고 상세페이지 → detail_url (biz_aply_url, biz_gdnc_url 순으로 대체)
  rcrt_prgs_yn        모집진행여부 Y/N → 서버 필터로만 쓰고 별도 필드로는 안 둠

이 모듈은 아직 build.py에 연결되지 않았다. 실제 라이브 호출(페이지네이션,
전체 매핑)은 로컬 fixture(kstartup_sample.xml)로만 검증했고, 진짜 키로
전체 흐름을 도는 건 다음 단계에서 확인해야 한다.
"""
import html
import json
import os
import re
import xml.etree.ElementTree as ET
from datetime import date

TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"[ \t\xa0]+")

# bizinfo.py의 SIDO와 같은 이름 목록. supt_regin이 "전국"처럼 이름 그대로
# 오는 것까지는 실응답으로 확인했다. "서울특별시"류 전체 표기는 아직
# 못 봤지만, 부분일치라 "서울" 같은 짧은 이름이 포함돼 있으면 잡힌다.
# 여러 지역이 함께 나열되는 경우도 있을 수 있어, 기업마당과 동일하게
# 하나만 특정될 때만 그 지역으로 두고 아니면 "전국"으로 둔다 (추측 금지).
SIDO_NAMES = [
    "서울", "부산", "대구", "인천", "대전", "울산", "세종", "경기",
    "강원", "충북", "충남", "전북", "전남", "광주", "경북", "경남", "제주",
]

# supt_biz_clsfc 값 기준 키워드 매핑. 실제로 확인된 값은 "기술개발(R&D)"
# 하나뿐이고, 나머지(사업화/보육/멘토링/행사 등)는 창업진흥원이 통상 쓰는
# 분류명을 참고한 추정이다 — 실응답에서 새 값이 나올 때마다 이 표를
# 갱신할 것. 매칭 안 되면 "창업"(이 소스 자체가 창업진흥원 데이터라 기본값
# 으로 타당)으로 떨어지니, 잘못 매핑돼도 완전히 엉뚱한 카테고리로 새지는 않는다.
CATEGORY_KEYWORDS = [
    ("기술", "기술"), ("R&D", "기술"), ("수출", "수출"), ("글로벌", "수출"),
    ("인력", "인력"), ("채용", "인력"), ("경영", "경영"), ("컨설팅", "경영"),
    ("멘토링", "경영"), ("금융", "금융"), ("융자", "금융"), ("보증", "금융"),
    ("판로", "내수"), ("마케팅", "내수"), ("사업화", "창업"), ("보육", "창업"),
    ("행사", "기타"), ("네트워크", "기타"), ("창업", "창업"),
]


def _text(s):
    if not s:
        return ""
    s = TAG_RE.sub("\n", s)
    s = html.unescape(html.unescape(s))   # 실데이터의 &amp;amp; 이중escape 대응
    s = WS_RE.sub(" ", s)
    return "\n".join(x.strip() for x in s.split("\n") if x.strip())


def _region(item):
    raw = (item.get("supt_regin") or "").strip()
    if not raw:
        return "전국"
    hit = [n for n in SIDO_NAMES if n in raw]
    if len(hit) == 1:
        return hit[0]
    return "전국"


def _category(item):
    raw = _text(item.get("supt_biz_clsfc"))
    for kw, cat in CATEGORY_KEYWORDS:
        if kw in raw:
            return cat
    return "창업"


def _date(s):
    """'YYYYMMDD' → 'YYYY-MM-DD'. 확인 안 되는 포맷이면 None."""
    s = (s or "").strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        return s
    if re.match(r"^\d{8}$", s):
        return f"{s[:4]}-{s[4:6]}-{s[6:]}"
    return None


def _method(item):
    labels = [
        ("aply_mthd_onli_rcpt_istc", "온라인 접수"),
        ("aply_mthd_vst_rcpt_istc", "방문 접수"),
        ("aply_mthd_fax_rcpt_istc", "팩스 접수"),
        ("aply_mthd_pssr_rcpt_istc", "우편 접수"),
        ("aply_mthd_eml_rcpt_istc", "이메일 접수"),
        ("aply_mthd_etc_istc", "기타"),
    ]
    parts = []
    for key, label in labels:
        v = _text(item.get(key))
        if v:
            parts.append(f"{label}: {v}")
    return "\n".join(parts)


def _org(item):
    name = _text(item.get("pbanc_ntrp_nm"))
    dept = _text(item.get("biz_prch_dprt_nm"))
    if name and dept:
        return f"{name} ({dept})"
    return name or _text(item.get("sprv_inst"))


def normalize(item):
    start = _date(item.get("pbanc_rcpt_bgng_dt"))
    end = _date(item.get("pbanc_rcpt_end_dt"))
    ptype = "dated" if (start and end) else "unknown"

    points = []
    for key, label in (
        ("aply_trgt_ctnt", "신청대상"), ("aply_excl_trgt_ctnt", "신청제외대상"),
        ("prfn_matr", "우대사항"), ("aply_trgt", "신청대상 구분"),
        ("biz_trgt_age", "대상 연령"), ("biz_enyy", "대상 업력"),
    ):
        v = _text(item.get(key))
        if v:
            points.append(f"{label}: {v}")

    return {
        "id": "ks-" + (item.get("pbanc_sn") or item.get("id") or "0"),
        "title": _text(item.get("biz_pbanc_nm")) or _text(item.get("intg_pbanc_biz_nm")),
        "category": _category(item),
        "region": _region(item),
        "org": _org(item),
        "exec_org": _text(item.get("sprv_inst")),
        "target": _text(item.get("aply_trgt_ctnt")),
        "amount": "",
        "apply_start": start,
        "apply_end": end,
        "period_type": ptype,
        "period_raw": f"{item.get('pbanc_rcpt_bgng_dt', '')} ~ {item.get('pbanc_rcpt_end_dt', '')}".strip(" ~"),
        "method": _method(item),
        "contact": (item.get("prch_cnpl_no") or "").strip(),
        "detail_url": item.get("detl_pg_url") or item.get("biz_aply_url") or item.get("biz_gdnc_url") or "",
        "views": 0,
        "created": "",
        "updated": "",
        "overview": _text(item.get("pbanc_ctnt")),
        "points": points,
        "tags": [],
        "source": "kstartup",
    }


def _parse_xml(raw):
    """<results><data><item><col name="k">v</col>...</item></data></results> → dict 리스트."""
    root = ET.fromstring(raw)
    meta = {tag: (root.findtext(tag) or "") for tag in ("currentCount", "matchCount", "page", "perPage", "totalCount")}
    items = []
    for item_el in root.findall("./data/item"):
        row = {}
        for col in item_el.findall("col"):
            row[col.get("name")] = col.text or ""
        items.append(row)
    return meta, items


class KstartupSource:
    """
    운영용. KSTARTUP_KEY 환경변수 필요 (BIZINFO_KEY와 별도 발급).
    dataType=json을 보내도 서버는 항상 XML로 응답한다 (실호출로 확인).
    """
    URLS = [
        "https://apis.data.go.kr/B552735/kisedKstartupService01/getAnnouncementInformation01",
    ]
    CACHE = os.path.join(os.path.dirname(__file__), "..", "data", "kstartup_cache.json")

    def __init__(self, key=None, pages=None):
        self.key = key or os.environ.get("KSTARTUP_KEY", "")
        self.pages = pages

    def _get(self, page, per_page=100, debug=False):
        import time, urllib.parse, urllib.request
        q = urllib.parse.urlencode({
            "serviceKey": self.key, "page": page, "perPage": per_page,
            "rcrt_prgs_yn": "Y",   # 모집 중인 공고만 (안 걸면 3만 건 가까이 나온다)
        }, safe="%")
        last = None
        for attempt in range(3):
            for base in self.URLS:
                url = f"{base}?{q}"
                try:
                    req = urllib.request.Request(
                        url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/xml"},
                    )
                    with urllib.request.urlopen(req, timeout=120) as r:
                        raw = r.read().decode("utf-8", errors="replace")
                        try:
                            return _parse_xml(raw)
                        except ET.ParseError as e:
                            if debug:
                                masked = url.split("serviceKey=")[0] + "serviceKey=***"
                                print(f"  [debug] status={r.status} url={masked}")
                                print(f"  [debug] 응답 본문(앞 500자): {raw[:500]!r}")
                            raise
                except Exception as e:
                    last = e
                    if debug:
                        masked = url.split("serviceKey=")[0] + "serviceKey=***"
                        print(f"  [debug] {type(e).__name__}: {e}  url={masked}")
            if debug:
                break
            time.sleep(5 * (attempt + 1))
        raise last

    def fetch(self):
        try:
            return self._fetch_live()
        except Exception as e:
            print(f"K-Startup API 호출 실패({e}). 캐시로 대체합니다.")
            if os.path.exists(self.CACHE):
                with open(self.CACHE, encoding="utf-8") as f:
                    return json.load(f)
            return []   # 캐시도 없으면 창업 보강 없이 기업마당만으로 빌드 (전체 실패시키지 않음)

    def _fetch_live(self):
        out, page = [], 1
        while True:
            meta, items = self._get(page)
            out += [normalize(i) for i in items]
            total = int(meta.get("totalCount") or 0)
            print(f"  [k-startup] {page}페이지 수신 ({len(out)}/{total})")
            if self.pages and page >= self.pages:
                break
            if not items or len(out) >= total:
                break
            page += 1
        try:
            with open(self.CACHE, "w", encoding="utf-8") as f:
                json.dump(out, f, ensure_ascii=False)
        except Exception:
            pass
        return out


if __name__ == "__main__":
    # 로컬 검증용. 절대 키를 코드/커밋에 남기지 말 것 — 실행 전에
    # 터미널에서 직접 export/set 해서 환경변수로만 넘긴다.
    #   (powershell) $env:KSTARTUP_KEY="발급받은키"; python src/kstartup.py
    # 출력에는 키가 찍히지 않는다.
    key = os.environ.get("KSTARTUP_KEY", "").strip()
    if not key:
        print("KSTARTUP_KEY 환경변수가 없습니다. 설정 후 다시 실행하세요.")
        raise SystemExit(1)
    src = KstartupSource(key, pages=1)
    try:
        meta, items = src._get(1, per_page=5, debug=True)
    except Exception as e:
        print(f"호출 실패: {e}")
        raise SystemExit(1)
    print(f"meta={meta}\n총 {len(items)}건 수신\n")
    for i, raw in enumerate(items):
        print(f"--- [{i}] normalize() 결과 ---")
        print(json.dumps(normalize(raw), ensure_ascii=False, indent=2))
