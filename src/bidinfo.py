# -*- coding: utf-8 -*-
"""
나라장터 입찰공고 어댑터.

출처: 조달청 나라장터 입찰공고정보서비스 (data.go.kr, 2024-07 등록 /
2026-06 수정). 업무구분(물품/용역/공사/외자)마다 오퍼레이션이 갈린다.
한 오퍼레이션으로 전체를 받으면 정상 응답이 안 온다.

엔드포인트 (2026 기준, ad/ 경로가 현행):
  https://apis.data.go.kr/1230000/ad/BidPublicInfoService/{operation}
구 경로 BidPublicInfoService 는 폴백으로만 둔다.

인증키: NARA_API_KEY 또는 DATA_GO_KR_SERVICE_KEY (Decoding 키).
없으면 캐시 → 목업 순으로 빌드한다. 키가 있어도 호출이 실패하면
마지막 성공 캐시로 대체하고, 전체 빌드를 죽이지 않는다.

정규화 원칙:
  - 없는 추정가격·지역을 지어내지 않는다.
  - 지역은 참가제한/참가가능 지역 필드의 허용 목록 정확 일치만.
  - 마감일시가 없으면 그 건은 버린다 (입찰에는 상시 접수가 없다).
"""
import json
import os
import re
import socket
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone

import config
import deadline as dl
import detail_faq

KST = timezone(timedelta(hours=9))

CACHE = os.path.join(os.path.dirname(__file__), "..", "data", "bid_cache.json")
# 마감 입찰 아카이브는 bid_cache.json 에 함께 둔다 (워크플로가 이미 커밋하는 파일).
ARCHIVE = CACHE
ARCHIVE_DAYS = 180              # 마감 입찰 상세페이지 보관 일수 (목록에는 안 나옴)
MOCK = os.path.join(os.path.dirname(__file__), "..", "data", "bid_mock.json")

# 페이지네이션·배포 용량 상한. 나라장터는 하루 수천 건이라 전부 정적화하지 않는다.
# 페이지네이션은 totalCount 까지 끝까지 돈다. 아래는 무한 루프·과금 방지용 안전 상한
# (100건 × 50페이지 = 종류당 5,000건, 7일치로는 넉넉함). 상한에 걸리거나 중간 페이지가
# 실패하면 META["complete"] 가 False 가 되고, 화면 건수는 "N건 이상" 으로 표기된다.
MAX_PAGES_PER_KIND = 50
NUM_OF_ROWS = 100
INQRY_DAYS = 7                  # 공고게시일 기준 최근 N일 (API는 보통 1개월 이내)
MAX_BIDS = 500                  # 목록·상세 페이지를 만드는 상한 (배포 파일 수 제한). 건수 표기는 상한 전 전체 기준
KEEP_CLOSED_DAYS = 3            # 마감된 지 이 일수 이내만 목록 하단에 남김
MAX_CLOSE_AHEAD_DAYS = 30       # 마감이 너무 먼 건은 마감판 성격에 안 맞아 제외

# 2026년 현행 경로를 앞에, 구 경로를 뒤에. https·http 둘 다 시도한다.
API_BASES = [
    "https://apis.data.go.kr/1230000/ad/BidPublicInfoService",
    "http://apis.data.go.kr/1230000/ad/BidPublicInfoService",
    "https://apis.data.go.kr/1230000/BidPublicInfoService",
    "http://apis.data.go.kr/1230000/BidPublicInfoService",
]

# 비-GHA 리눅스에서는 키 없이 ~0.4–1.3초에 HTTP 400이 온다 (API는 살아 있음).
# GHA(미국)만 경로가 느리거나 필터되어 25초에 타임아웃 난다.
# urllib.request.urlopen 은 connect/read 를 한 값으로만 받으므로 둘 다 ≥60초.
CONNECT_TIMEOUT = 60
READ_TIMEOUT = 60
HTTP_ATTEMPTS = 5          # 재시도 4회 (3–5 범위)
HTTP_BACKOFF = 5          # 라운드 사이 대기 = HTTP_BACKOFF * attempt 초
RETRY_HTTP = {408, 429, 500, 502, 503, 504}
# 입찰 수집 전체 시간 예산(초). API가 느린 날 재시도가 쌓여 배포 잡(120분)이 통째로
# 타임아웃되지 않게, 넘으면 받은 만큼만 쓰거나 캐시로 넘어간다.
FETCH_BUDGET_S = int(os.environ.get("NARA_FETCH_BUDGET_S") or 1800)
_DEADLINE = [None]


class BudgetExceeded(RuntimeError):
    """입찰 수집 시간 예산 초과."""


def _check_budget(need=0):
    d = _DEADLINE[0]
    if d is not None and time.monotonic() + need > d:
        raise BudgetExceeded(f"입찰 수집 시간 예산 {FETCH_BUDGET_S}s 초과")

# 수집 메타. complete=False 면 일부 페이지·종류를 못 받아 건수가 하한값이다.
# 기본은 CACHE 와 같은 폴더의 bid_meta.json (테스트가 CACHE 를 바꾸면 같이 따라간다).
META_PATH = None
META = {"complete": True}
# 상한(MAX_BIDS) 적용 전, 정정공고 병합 후 전체 목록. bid_build 가 건수 표기에 쓴다.
FULL = []
AUTH_RESULT_CODES = {"01", "30", "31", "32"}
AUTH_HTTP = {401, 403}

CACHE_FIELDS = (
    "id", "bid_no", "seq", "title", "kind", "kind_slug", "org",
    "ntce_org", "budget", "budget_raw", "open_dt", "close_dt",
    "region", "detail_url", "method", "contract",
)

KIND_BY_SLUG = {k["slug"]: k for k in config.BID_KINDS}
KIND_BY_NAME = {k["name"]: k for k in config.BID_KINDS}
KIND_BY_API = {k["api"]: k for k in config.BID_KINDS}

REGION_BY_NAME = {r["name"]: r for r in config.BID_REGIONS}

# 나라장터 필드 원문 → 우리 지역명. 키 전체가 필드 값과 같아야 한다 (부분일치·정규식 금지).
REGION_EXACT = {
    "서울특별시": "서울", "서울": "서울",
    "부산광역시": "부산", "부산": "부산",
    "대구광역시": "대구", "대구": "대구",
    "인천광역시": "인천", "인천": "인천",
    "광주광역시": "광주", "광주": "광주",
    "대전광역시": "대전", "대전": "대전",
    "울산광역시": "울산", "울산": "울산",
    "세종특별자치시": "세종", "세종시": "세종", "세종": "세종",
    "경기도": "경기", "경기": "경기",
    "강원특별자치도": "강원", "강원도": "강원", "강원": "강원",
    "충청북도": "충북", "충북": "충북",
    "충청남도": "충남", "충남": "충남",
    "전북특별자치도": "전북", "전라북도": "전북", "전북": "전북",
    "전라남도": "전남", "전남": "전남",
    "경상북도": "경북", "경북": "경북",
    "경상남도": "경남", "경남": "경남",
    "제주특별자치도": "제주", "제주도": "제주", "제주": "제주",
    "전국": "전국",
}


def api_key():
    return (os.environ.get("NARA_API_KEY")
            or os.environ.get("DATA_GO_KR_SERVICE_KEY")
            or "").strip()


def kind_of_slug(slug):
    return KIND_BY_SLUG.get(slug)


def slug_of_kind(name):
    k = KIND_BY_NAME.get(name)
    return k["slug"] if k else ""


def _txt(v):
    if v is None:
        return ""
    return str(v).strip()


def _id(no, seq):
    no = re.sub(r"[^A-Za-z0-9]", "", _txt(no))
    seq = re.sub(r"[^A-Za-z0-9]", "", _txt(seq)) or "000"
    if not no:
        return ""
    return f"{no}-{seq}"


def parse_dt(raw):
    """나라장터 일시 표기 → aware datetime (KST). 모르면 None. 지어내지 않음."""
    s = _txt(raw)
    if not s:
        return None
    s = s.replace("T", " ").replace("/", "-")
    digits = re.sub(r"\D", "", s)
    for fmt, n in (
        ("%Y%m%d%H%M%S", 14),
        ("%Y%m%d%H%M", 12),
        ("%Y%m%d", 8),
    ):
        if len(digits) >= n:
            try:
                dt = datetime.strptime(digits[:n], fmt)
                return dt.replace(tzinfo=KST)
            except ValueError:
                continue
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(s[:len(fmt) + 2].strip(), fmt)
            return dt.replace(tzinfo=KST)
        except ValueError:
            continue
    return None


def format_dt(dt):
    if not dt:
        return ""
    if dt.hour or dt.minute or dt.second:
        return dt.strftime("%Y-%m-%d %H:%M")
    return dt.strftime("%Y-%m-%d")


def parse_price(raw):
    """원 단위 정수. 비거나 파싱 불가면 None. 0은 없는 값으로 본다."""
    s = _txt(raw).replace(",", "").replace("원", "")
    if not s:
        return None
    try:
        n = int(float(s))
    except (TypeError, ValueError):
        return None
    if n <= 0:
        return None
    return n


def format_krw(n):
    """실숫자만 받아 한글 금액으로 표기. 호출 전에 None 검사를 한다."""
    n = int(n)
    eok, rest = divmod(n, 100000000)
    man, won = divmod(rest, 10000)
    parts = []
    if eok:
        parts.append(f"{eok:,}억")
    if man:
        parts.append(f"{man:,}만")
    if won and not eok:
        parts.append(f"{won:,}")
    if not parts:
        return f"{n:,}원"
    body = " ".join(parts)
    if body.endswith("만") or body.endswith("억"):
        return body + "원"
    return body + "원"


def region_of(item):
    """
    참가제한지역·참가가능지역 필드의 허용 목록 정확 일치만.
    제목·기관명에서 추측하지 않는다. 못 찾으면 빈 문자열 (페이지를 만들지 않음).
    """
    for key in ("prtcptLmtRgnNm", "prtcptPsblRgnNm"):
        raw = _txt(item.get(key))
        if not raw:
            continue
        if raw in REGION_EXACT:
            return REGION_EXACT[raw]
    return ""


def gist_of(title):
    """카드 요지. 제목 껍질만 벗기고 없는 품명을 지어내지 않는다."""
    t = (title or "").replace("\xa0", " ").replace("ㆍ", "·")
    t = re.sub(r"\s+", " ", t).strip()
    if not t:
        return ""
    t = re.sub(r"^\[[^\]]+\]\s*", "", t)
    t = re.sub(r"20\d{2}년\s*", "", t)
    t = re.sub(r"\s*(?:입찰)?(?:재)?공고$", "", t)
    t = t.strip(" -·,./()")
    if len(t) > 36:
        t = t[:35].rstrip(" ·,") + "…"
    return t


def card_line(row):
    """기관 · 공고 요지 · 종류. 금액·마감 칩은 값이 있을 때만 뒤에 붙인다."""
    row = row or {}
    org = _txt(row.get("org"))
    gist = gist_of(row.get("title") or "")
    kind = _txt(row.get("kind"))
    parts = [p for p in (org, gist, kind) if p]
    chip = row.get("budget_card") or ""
    if chip and chip not in parts:
        parts.append(chip)
    return " · ".join(parts)[:90]


def now_kst(now=None):
    if now is not None:
        if now.tzinfo is None:
            return now.replace(tzinfo=KST)
        return now.astimezone(KST)
    return datetime.now(KST)


def dday_of(close_dt, now=None):
    now = now_kst(now)
    return (close_dt.astimezone(KST).date() - now.date()).days


def is_open(close_dt, now=None):
    now = now_kst(now)
    c = close_dt if close_dt.tzinfo else close_dt.replace(tzinfo=KST)
    return c >= now


def _eun(word):
    """받침 있으면 '은', 없으면 '는'. 한글이 아니면 '은'."""
    w = (word or "").strip()
    code = ord(w[-1]) - 0xAC00 if w else -1
    return "는" if 0 <= code <= 11171 and code % 28 == 0 else "은"


def is_canceled(row):
    """나라장터 제목 앞의 "(취소)" 표기. 정정공고 안의 다른 위치 '취소'는 보지 않는다."""
    t = (row.get("title") or "").lstrip()
    return t.startswith("(취소)") or t.startswith("[취소]")


def decorate(row, now=None):
    """D-day 배지·카드 한 줄. 마감일시가 있는 행만 들어온다."""
    close = parse_dt(row.get("close_dt"))
    now = now_kst(now)
    if not close:
        return None
    d = dday_of(close, now)
    # 발주기관이 취소한 공고(제목이 "(취소)"로 시작)는 진행 중 목록에서 뺀다.
    canceled = is_canceled(row)
    open_ = is_open(close, now) and not canceled
    row["dday"] = d
    row["is_open"] = open_
    row["canceled"] = canceled
    open_dt = parse_dt(row.get("open_dt"))
    if canceled:
        row["status"] = "canceled"
    elif not open_:
        row["status"] = "closed"
    elif open_dt and open_dt > now:
        row["status"] = "upcoming"
    else:
        row["status"] = "open"
    row["status_label"] = dl.status_label(row["status"])
    row["time_known"] = dl.time_known(row.get("close_dt") or "")
    row["deadline_line"] = dl.deadline_line(row)
    row["org_eun"] = _eun(row.get("org") or "같은 수요기관")
    row["source"] = "g2b"
    row["source_label"] = "나라장터"
    row["notice_no"] = row.get("bid_no") or row.get("id") or ""
    row["posted_at"] = (row.get("open_dt") or "")[:16]
    if canceled:
        row["cls"], row["dlabel"] = "d-c", "취소"
        row["dsub"] = row["deadline_line"]
    elif not open_:
        row["cls"], row["dlabel"] = "d-c", "마감"
        row["dsub"] = row["deadline_line"]
    elif d == 0:
        row["cls"], row["dlabel"] = "d-u", "오늘"
        row["dsub"] = row["deadline_line"]
    elif d <= 7:
        row["cls"], row["dlabel"] = "d-u", f"D-{d}"
        row["dsub"] = row["deadline_line"]
    elif d <= 14:
        row["cls"], row["dlabel"] = "d-s", f"D-{d}"
        row["dsub"] = row["deadline_line"]
    else:
        row["cls"], row["dlabel"] = "d-o", f"D-{d}"
        row["dsub"] = row["deadline_line"]
    raw = row.get("budget_raw")
    row["budget_card"] = format_krw(raw) if raw else ""
    row["blurb"] = card_line(row)
    row["region_slug"] = (REGION_BY_NAME.get(row.get("region") or "") or {}).get("slug", "")
    row["kind_slug"] = slug_of_kind(row.get("kind") or "")
    row["is_correction"] = detail_faq.seq_is_correction(row.get("seq"))
    posted = parse_dt(row.get("open_dt"))
    row["is_new"] = (not row["is_correction"]) and bool(posted) and posted.date() == now.date()
    return row


def normalize(item, kind_name, now=None):
    """API 원건 → 내부 스키마. kind_name은 호출한 오퍼레이션에서 온 값만 쓴다."""
    kind = KIND_BY_NAME.get(kind_name)
    if not kind:
        return None
    bid_no = _txt(item.get("bidNtceNo"))
    seq = _txt(item.get("bidNtceOrd")) or "000"
    aid = _id(bid_no, seq)
    title = _txt(item.get("bidNtceNm"))
    close = parse_dt(item.get("bidClseDt"))
    if not aid or not title or not close:
        return None
    price = parse_price(item.get("presmptPrce")) or parse_price(item.get("bdgtAmt"))
    region = region_of(item)
    org = _txt(item.get("dminsttNm")) or _txt(item.get("ntceInsttNm"))
    open_dt = parse_dt(item.get("bidNtceDt")) or parse_dt(item.get("bidBeginDt"))
    url = _txt(item.get("bidNtceDtlUrl"))
    row = {
        "id": aid,
        "bid_no": re.sub(r"[^A-Za-z0-9]", "", bid_no),
        "seq": re.sub(r"[^A-Za-z0-9]", "", seq) or "000",
        "title": title,
        "kind": kind["name"],
        "kind_slug": kind["slug"],
        "org": org,
        "ntce_org": _txt(item.get("ntceInsttNm")),
        "budget": format_krw(price) if price else "",
        "budget_raw": price,
        "open_dt": format_dt(open_dt),
        "close_dt": format_dt(close),
        "region": region,
        "detail_url": url,
        "method": _txt(item.get("bidMethdNm")),
        "contract": _txt(item.get("cntrctCnclsMthdNm")),
    }
    return decorate(row, now=now)


def _sort_key(row):
    return (row.get("status") != "open", row.get("dday", 9999), row.get("title") or "")


def _seq_num(row):
    seq = str(row.get("seq") or "")
    if not seq:
        seq = str(row.get("id") or "").rpartition("-")[2]
    return int(seq) if seq.isdigit() else -1


def _bid_base(row):
    no = str(row.get("bid_no") or "")
    if no:
        return no
    base, _, ordr = str(row.get("id") or "").rpartition("-")
    return base if base and ordr.isdigit() else str(row.get("id") or "")


def latest_only(rows):
    """
    정정공고 병합. 같은 공고번호(bidNtceNo)의 차수(-000 원공고, -001 정정 …) 중
    가장 높은 차수 1건만 남긴다. 예: R26BK01755554-000, -001 → -001 만.
    순서는 입력 순서를 따른다.
    """
    best = {}
    for r in rows or []:
        b = _bid_base(r)
        if b not in best or _seq_num(r) > _seq_num(best[b]):
            best[b] = r
    keep = {id(v) for v in best.values()}
    return [r for r in rows or [] if id(r) in keep]


def superseded_ids(rows):
    """rows 안에서 더 높은 차수가 있는 이전 차수 id 집합."""
    best = {}
    for r in rows or []:
        b = _bid_base(r)
        best[b] = max(best.get(b, -1), _seq_num(r))
    return {r.get("id") for r in rows or [] if _seq_num(r) < best.get(_bid_base(r), -1)}


def process(rows, now=None, cap=MAX_BIDS):
    """캐시/목업/라이브 공통. D-day를 다시 계산하고, 정정공고를 병합하고, 상한을 적용한다.
    상한 전 전체 목록은 FULL 에 남긴다(건수 표기용)."""
    now = now_kst(now)
    out, seen = [], set()
    for r in rows or []:
        row = decorate(dict(r), now=now)
        if not row:
            continue
        d = row["dday"]
        if d < -KEEP_CLOSED_DAYS or d > MAX_CLOSE_AHEAD_DAYS:
            continue
        if row["id"] in seen:
            continue
        seen.add(row["id"])
        out.append(row)
    out = latest_only(out)
    out.sort(key=_sort_key)
    FULL[:] = out
    if cap and len(out) > cap:
        out = out[:cap]
    return out


def _items_from_body(body):
    items = (body or {}).get("items")
    if items is None or items == "" or items == "null":
        return []
    if isinstance(items, dict):
        item = items.get("item", items)
        if isinstance(item, list):
            return [x for x in item if isinstance(x, dict)]
        if isinstance(item, dict):
            return [item]
        return []
    if isinstance(items, list):
        return [x for x in items if isinstance(x, dict)]
    return []


def _xml_text(el):
    if el is None or el.text is None:
        return ""
    return el.text.strip()


def _parse_xml(raw):
    root = ET.fromstring(raw)
    # 네임스페이스 없는 표준 응답
    header = root.find("header")
    body = root.find("body")
    result = _xml_text(header.find("resultCode")) if header is not None else ""
    total = _xml_text(body.find("totalCount")) if body is not None else "0"
    items = []
    if body is not None:
        wrap = body.find("items")
        if wrap is not None:
            for it in wrap.findall("item"):
                items.append({ch.tag: (ch.text or "").strip() for ch in it})
    try:
        total_n = int(total or 0)
    except ValueError:
        total_n = 0
    return result, items, total_n


def _parse_payload(raw):
    raw = (raw or "").lstrip("\ufeff")
    if not raw:
        return "empty", [], 0
    if raw[:1] in "{[":
        data = json.loads(raw)
        header = (data.get("response") or {}).get("header") or {}
        body = (data.get("response") or {}).get("body") or {}
        code = _txt(header.get("resultCode"))
        try:
            total = int(body.get("totalCount") or 0)
        except (TypeError, ValueError):
            total = 0
        return code, _items_from_body(body), total
    return _parse_xml(raw)


def _origin(base):
    p = urllib.parse.urlparse(base)
    return f"{p.scheme}://{p.netloc}".lower()


def _is_timeout(exc):
    cur, seen = exc, 0
    while cur is not None and seen < 5:
        if isinstance(cur, (TimeoutError, socket.timeout)):
            return True
        text = str(cur).lower()
        if "timed out" in text or "timeout" in text:
            return True
        cur = getattr(cur, "reason", None)
        if isinstance(cur, str):
            t = cur.lower()
            return "timed out" in t or "timeout" in t
        seen += 1
    return False


def _http_code(exc):
    code = getattr(exc, "code", None)
    try:
        return int(code)
    except (TypeError, ValueError):
        return None


def _err_reason(exc):
    """로그용 한 줄. URL·serviceKey 는 넣지 않는다."""
    if _is_timeout(exc):
        return "timed out"
    code = _http_code(exc)
    if code is not None:
        return f"HTTP {code}"
    reason = getattr(exc, "reason", None)
    if reason is not None:
        return f"urlopen error {reason}"[:160]
    text = re.sub(r"(serviceKey=)[^&\s]+", r"\1***", str(exc), flags=re.I)
    return f"{type(exc).__name__}: {text}"[:160]


def _retryable(exc):
    if _is_timeout(exc):
        return True
    return _http_code(exc) in RETRY_HTTP


def _is_auth_failure(exc):
    """키/권한 오류만. 타임아웃·5xx·HTTP 400 은 종류를 건너뛰지 않는다."""
    if exc is None or _is_timeout(exc):
        return False
    if _http_code(exc) in AUTH_HTTP:
        return True
    msg = str(exc)
    if any(f"resultCode={c}" in msg for c in AUTH_RESULT_CODES):
        return True
    return any(s in msg for s in ("HTTP 401", "HTTP 403", "HTTP Error 401", "HTTP Error 403"))


def _urlopen(req, connect_timeout=None, read_timeout=None):
    """테스트에서 mock 하는 HTTP 진입점. urllib는 connect/read를 한 값만 받는다."""
    connect_timeout = CONNECT_TIMEOUT if connect_timeout is None else connect_timeout
    read_timeout = READ_TIMEOUT if read_timeout is None else read_timeout
    return urllib.request.urlopen(req, timeout=max(connect_timeout, read_timeout))


def _save_cache(rows):
    """실데이터가 하나라도 있으면 저장. 빈 목록으로 기존 캐시를 덮지 않는다."""
    if not rows:
        return False
    try:
        os.makedirs(os.path.dirname(os.path.abspath(CACHE)), exist_ok=True)
        serial = [{k: r.get(k) for k in CACHE_FIELDS} for r in rows]
        # 이전 캐시의 마감 건을 ARCHIVE_DAYS 동안 보존 (상세페이지 유지용)
        ids = {r.get("id") for r in serial}
        now = now_kst()
        for r in _load_list(CACHE):
            close = parse_dt(r.get("close_dt"))
            if r.get("id") and r["id"] not in ids and close and (now - close).days <= ARCHIVE_DAYS:
                serial.append({k: r.get(k) for k in CACHE_FIELDS})
                ids.add(r["id"])
        with open(CACHE, "w", encoding="utf-8") as f:
            json.dump(serial, f, ensure_ascii=False)
        print(f"  [입찰] 캐시 {len(serial)}건 저장")
        return True
    except Exception as e:
        print(f"  [입찰] 캐시 저장 실패({_err_reason(e)})")
        return False


def _get(key, op, page, bgn, end):
    q = urllib.parse.urlencode({
        "serviceKey": key,
        "pageNo": page,
        "numOfRows": NUM_OF_ROWS,
        "inqryDiv": 1,
        "inqryBgnDt": bgn,
        "inqryEndDt": end,
        "type": "json",
    }, safe="%")
    last = None
    for attempt in range(1, HTTP_ATTEMPTS + 1):
        timed_out_origins = set()
        for base in API_BASES:
            origin = _origin(base)
            if origin in timed_out_origins:
                continue
            _check_budget()
            try:
                req = urllib.request.Request(
                    f"{base}/{op}?{q}",
                    headers={"User-Agent": "Mozilla/5.0",
                             "Accept": "application/json, application/xml"},
                )
                with _urlopen(req) as r:
                    raw = r.read().decode("utf-8", errors="replace")
                code, items, total = _parse_payload(raw)
                if code and code not in ("00", "0", "000", "200"):
                    err = RuntimeError(f"{op} resultCode={code}")
                    # 인증 실패는 다른 호스트를 갈아도 같으므로 바로 중단
                    if str(code) in AUTH_RESULT_CODES:
                        raise err
                    last = err
                    print(f"  [입찰 HTTP] {op} {base} #{attempt}/{HTTP_ATTEMPTS} resultCode={code}")
                    continue
                return items, total
            except RuntimeError:
                raise
            except Exception as e:
                last = e
                reason = _err_reason(e)
                print(f"  [입찰 HTTP] {op} {base} #{attempt}/{HTTP_ATTEMPTS} {reason}")
                if _is_auth_failure(e):
                    raise
                if _is_timeout(e):
                    timed_out_origins.add(origin)
        if attempt < HTTP_ATTEMPTS and (last is None or _retryable(last)):
            delay = HTTP_BACKOFF * attempt
            _check_budget(delay)
            print(f"  [입찰 HTTP] {op} {delay}s 후 재시도 ({attempt}/{HTTP_ATTEMPTS})")
            time.sleep(delay)
    raise last


def _fetch_kind(key, kind, bgn, end, pages, status=None):
    """totalCount 까지 끝까지 받는다. 중간 실패·안전 상한이면 status["complete"]=False."""
    out, page = [], 1
    op = kind["op"]
    complete = False
    while page <= pages:
        try:
            items, total = _get(key, op, page, bgn, end)
        except Exception as e:
            if status is not None and isinstance(e, BudgetExceeded):
                status["budget"] = True
            if out:
                print(f"  [입찰 {kind['name']}] {page}페이지 실패"
                      f"({_err_reason(e)}), 이미 받은 {len(out)}건 유지")
                break
            raise
        out.extend(items)
        print(f"  [입찰 {kind['name']}] {page}페이지 수신 ({len(out)}/{total})")
        if not items or page * NUM_OF_ROWS >= total:
            complete = True
            break
        page += 1
    if not complete:
        print(f"  [입찰 {kind['name']}] 전체를 받지 못함 — 건수는 'N건 이상'으로 표기")
    if status is not None and not complete:
        status["complete"] = False
    return out


def fetch_live(key=None, pages=None, now=None):
    key = key or api_key()
    if not key:
        raise RuntimeError("NARA_API_KEY / DATA_GO_KR_SERVICE_KEY 없음")
    now = now_kst(now)
    end = now.strftime("%Y%m%d%H%M")
    bgn = (now - timedelta(days=INQRY_DAYS)).strftime("%Y%m%d%H%M")
    pages = pages or MAX_PAGES_PER_KIND
    print(f"  [입찰] HTTP timeout connect={CONNECT_TIMEOUT}s read={READ_TIMEOUT}s "
          f"attempts={HTTP_ATTEMPTS} budget={FETCH_BUDGET_S}s")
    status = {"complete": True}
    auth_dead = False
    _DEADLINE[0] = time.monotonic() + FETCH_BUDGET_S
    try:
        return _fetch_all(key, bgn, end, pages, now, status, auth_dead)
    finally:
        _DEADLINE[0] = None


def _open_count(rows, now):
    return sum(1 for r in rows if isinstance(r, dict) and is_open(parse_dt(r.get("close_dt")), now))


def _fetch_all(key, bgn, end, pages, now, status, auth_dead):
    rows, errors = [], []
    for kind in config.BID_KINDS:
        if auth_dead:
            errors.append(f"{kind['name']}: skipped (auth)")
            continue
        try:
            raw = _fetch_kind(key, kind, bgn, end, pages, status)
        except Exception as e:
            if isinstance(e, BudgetExceeded):
                status["budget"] = True
            reason = _err_reason(e)
            errors.append(f"{kind['name']}: {reason}")
            print(f"  [입찰 {kind['name']}] 호출 실패({reason})")
            # 타임아웃·5xx·HTTP 400 은 이 종류만 건너뛴다. 나머지를 버리지 않는다.
            if _is_auth_failure(e):
                auth_dead = True
            continue
        for item in raw:
            row = normalize(item, kind["name"], now=now)
            if row:
                rows.append(row)
    processed = process(rows, now=now)
    if processed and status.get("budget"):
        # 시간 예산으로 잘린 수집이 기존 캐시보다 접수중 건이 적으면 캐시가 낫다.
        old_open = _open_count(_load_list(CACHE), now)
        new_open = _open_count(FULL, now)
        if new_open < old_open:
            raise RuntimeError(f"시간 예산 초과로 일부만 수집({new_open} < 캐시 {old_open})")
    if processed:
        # 캐시에는 상한 전 전체(FULL)를 둔다. 캐시로 빌드해도 건수가 맞게.
        _save_cache(list(FULL))
        _save_meta({"complete": status["complete"] and not errors,
                    "fetched_at": now.strftime("%Y-%m-%d %H:%M")})
        if errors:
            print(f"  [입찰] 일부 종류 실패, {len(processed)}건은 유지")
        return processed
    if errors:
        raise RuntimeError("; ".join(errors))
    return processed


def _meta_path():
    return META_PATH or os.path.join(os.path.dirname(os.path.abspath(CACHE)), "bid_meta.json")


def _save_meta(meta):
    META.clear()
    META.update(meta)
    try:
        with open(_meta_path(), "w", encoding="utf-8") as f:
            json.dump(META, f, ensure_ascii=False)
    except OSError as e:
        print(f"  [입찰] 메타 저장 실패({e})")


def _load_meta():
    """캐시 빌드용. 파일이 없으면(예전 캐시) 500건 상한으로 잘렸을 수 있어 하한값으로 본다."""
    try:
        with open(_meta_path(), encoding="utf-8") as f:
            d = json.load(f)
        meta = {"complete": bool(d.get("complete")), "fetched_at": d.get("fetched_at") or ""}
    except Exception:
        meta = {"complete": False}
    META.clear()
    META.update(meta)


def load_cache(now=None):
    if not os.path.exists(CACHE):
        return []
    try:
        with open(CACHE, encoding="utf-8") as f:
            raw = json.load(f)
    except Exception:
        return []
    if not isinstance(raw, list) or not raw:
        return []
    _load_meta()
    return process(raw, now=now)


def _materialize_mock(spec, now=None):
    """목업 한 건. close_days 오프셋으로 오늘 기준 마감일시를 만든다."""
    now = now_kst(now)
    kind_name = spec.get("kind") or "용역"
    close_days = int(spec.get("close_days", 7))
    close_hour = int(spec.get("close_hour", 18))
    close = (now + timedelta(days=close_days)).replace(
        hour=close_hour, minute=0, second=0, microsecond=0)
    open_ = (close - timedelta(days=10)).replace(hour=9, minute=0)
    item = dict(spec.get("item") or {})
    item.setdefault("bidClseDt", close.strftime("%Y-%m-%d %H:%M:%S"))
    item.setdefault("bidNtceDt", open_.strftime("%Y-%m-%d %H:%M:%S"))
    return normalize(item, kind_name, now=now)


def load_mock(now=None, path=None):
    path = path or MOCK
    with open(path, encoding="utf-8") as f:
        specs = json.load(f)
    rows = []
    for spec in specs:
        row = _materialize_mock(spec, now=now)
        if row:
            rows.append(row)
    META.clear()
    META.update({"complete": True})
    return process(rows, now=now, cap=MAX_BIDS)


def load(now=None):
    """
    빌드 진입점.
      1) 키가 있으면 라이브. 실패 시 캐시.
      2) 키 없고 캐시가 있으면 캐시 (D-day만 다시 계산).
      3) GitHub Actions에서는 캐시도 없으면 빈 목록 — 목업을 배포하지 않는다.
      4) 로컬에서만 캐시 없을 때 목업.
    """
    key = api_key()
    gha = bool(os.environ.get("GITHUB_ACTIONS"))

    def cache_or_empty_or_mock(reason):
        cached = load_cache(now=now)
        if cached:
            print(f"입찰 캐시 {len(cached)}건")
            return cached
        if gha:
            print(f"입찰: {reason}. GitHub Actions에서는 목업을 올리지 않고 빈 목록으로 둡니다.")
            return []
        rows = load_mock(now=now)
        print(f"입찰 목업 {len(rows)}건")
        return rows

    if key:
        try:
            rows = fetch_live(key, now=now)
            print(f"입찰 실데이터 {len(rows)}건 (나라장터)")
            return rows
        except Exception as e:
            print(f"나라장터 API 호출 실패({e}). 캐시로 대체합니다.")
            return cache_or_empty_or_mock("라이브 실패·캐시 없음")
    cached = load_cache(now=now)
    if cached:
        print(f"입찰 캐시 {len(cached)}건 (NARA_API_KEY 없음)")
        return cached
    return cache_or_empty_or_mock("NARA_API_KEY 없음")


def _load_list(path):
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
    except Exception:
        return []
    if isinstance(d, dict):
        d = list(d.values())
    return d if isinstance(d, list) else []


def _load_archive(path=None):
    return {r["id"]: r for r in _load_list(path or ARCHIVE) if isinstance(r, dict) and r.get("id")}


def archived_bids(rows, now=None, path=None, save=False):
    """
    목록(rows)에서 빠진 마감 입찰도 ARCHIVE_DAYS일 동안 상세페이지를 살린다.
    rows 를 아카이브에 합치고, 오래된 건 버리고, rows 에 없는 마감 건을
    decorate 해서 돌려준다 (status=closed, 마감 배지).
    """
    now = now_kst(now)
    arc = _load_archive(path)
    live = set()
    for r in rows or []:
        if r.get("id"):
            live.add(r["id"])
            arc[r["id"]] = {k: r.get(k) for k in CACHE_FIELDS}
    kept, out = {}, []
    # 정정공고로 목록에서 빠진 이전 차수. 상세 URL 은 남겨 최신 차수로 canonical 한다.
    old_revs = superseded_ids(list(rows or []) + list(arc.values()))
    for bid_id, r in arc.items():
        close = parse_dt(r.get("close_dt"))
        if not close or (now - close).days > ARCHIVE_DAYS:
            continue
        kept[bid_id] = r
        if bid_id in live:
            continue
        row = decorate(dict(r), now=now)
        if not row or (row.get("is_open") and bid_id not in old_revs):
            continue      # 아직 열린 건은 라이브 목록 몫 (이전 차수는 예외)
        row["is_archived"] = True
        out.append(row)
    if save:
        try:
            with open(path or ARCHIVE, "w", encoding="utf-8") as f:
                json.dump(list(kept.values()), f, ensure_ascii=False)
        except OSError as e:
            print(f"  [입찰] 아카이브 저장 실패({e})")
    out.sort(key=lambda r: r.get("close_dt") or "", reverse=True)
    return out
