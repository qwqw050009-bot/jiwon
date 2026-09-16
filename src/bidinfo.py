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

KST = timezone(timedelta(hours=9))

CACHE = os.path.join(os.path.dirname(__file__), "..", "data", "bid_cache.json")
MOCK = os.path.join(os.path.dirname(__file__), "..", "data", "bid_mock.json")

# 페이지네이션·배포 용량 상한. 나라장터는 하루 수천 건이라 전부 정적화하지 않는다.
MAX_PAGES_PER_KIND = 4          # 100건 × 4페이지 × 4종류 = 최대 1,600건 수신
NUM_OF_ROWS = 100
INQRY_DAYS = 7                  # 공고게시일 기준 최근 N일 (API는 보통 1개월 이내)
MAX_BIDS = 500                  # 정렬 후 최종 목록 상한
KEEP_CLOSED_DAYS = 3            # 마감된 지 이 일수 이내만 목록 하단에 남김
MAX_CLOSE_AHEAD_DAYS = 30       # 마감이 너무 먼 건은 마감판 성격에 안 맞아 제외

# 2026년 현행 경로를 앞에, 구 경로를 뒤에. https·http 둘 다 시도한다.
API_BASES = [
    "https://apis.data.go.kr/1230000/ad/BidPublicInfoService",
    "http://apis.data.go.kr/1230000/ad/BidPublicInfoService",
    "https://apis.data.go.kr/1230000/BidPublicInfoService",
    "http://apis.data.go.kr/1230000/BidPublicInfoService",
]

# GitHub Actions(미국) → apis.data.go.kr 는 25초에 자주 끊긴다.
# urllib.request.urlopen 은 connect/read 를 한 값으로만 받으므로 긴 쪽(read)을 쓴다.
CONNECT_TIMEOUT = 30
READ_TIMEOUT = 60
HTTP_ATTEMPTS = 3
HTTP_BACKOFF = 5          # 라운드 사이 대기 = HTTP_BACKOFF * attempt 초
RETRY_HTTP = {408, 429, 500, 502, 503, 504}

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


def decorate(row, now=None):
    """D-day 배지·카드 한 줄. 마감일시가 있는 행만 들어온다."""
    close = parse_dt(row.get("close_dt"))
    now = now_kst(now)
    if not close:
        return None
    d = dday_of(close, now)
    open_ = is_open(close, now)
    row["dday"] = d
    row["is_open"] = open_
    row["status"] = "open" if open_ else "closed"
    close_hm = close.strftime("%H:%M")
    close_md = close.strftime("%m/%d")
    if not open_:
        row["cls"], row["dlabel"] = "d-c", "마감"
        row["dsub"] = f"{close_md} {close_hm}"
    elif d == 0:
        row["cls"], row["dlabel"] = "d-u", "오늘"
        row["dsub"] = f"{close_hm} 마감"
    elif d <= 7:
        row["cls"], row["dlabel"] = "d-u", f"D-{d}"
        row["dsub"] = f"{close_md} {close_hm}"
    elif d <= 14:
        row["cls"], row["dlabel"] = "d-s", f"D-{d}"
        row["dsub"] = f"{close_md} {close_hm}"
    else:
        row["cls"], row["dlabel"] = "d-o", f"D-{d}"
        row["dsub"] = f"{close_md} {close_hm}"
    raw = row.get("budget_raw")
    row["budget_card"] = format_krw(raw) if raw else ""
    row["blurb"] = card_line(row)
    row["region_slug"] = (REGION_BY_NAME.get(row.get("region") or "") or {}).get("slug", "")
    row["kind_slug"] = slug_of_kind(row.get("kind") or "")
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


def process(rows, now=None, cap=MAX_BIDS):
    """캐시/목업/라이브 공통. D-day를 다시 계산하고 상한을 적용한다."""
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
    out.sort(key=_sort_key)
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
                    if str(code) in ("01", "30", "31", "32"):
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
                http_code = _http_code(e)
                if http_code in (400, 401, 403):
                    raise RuntimeError(reason)
                if _is_timeout(e):
                    timed_out_origins.add(origin)
        if attempt < HTTP_ATTEMPTS and (last is None or _retryable(last)):
            delay = HTTP_BACKOFF * attempt
            print(f"  [입찰 HTTP] {op} {delay}s 후 재시도 ({attempt}/{HTTP_ATTEMPTS})")
            time.sleep(delay)
    raise last


def _fetch_kind(key, kind, bgn, end, pages):
    out, page = [], 1
    op = kind["op"]
    while page <= pages:
        items, total = _get(key, op, page, bgn, end)
        out.extend(items)
        print(f"  [입찰 {kind['name']}] {page}페이지 수신 ({len(out)}/{total})")
        if not items or page * NUM_OF_ROWS >= total:
            break
        page += 1
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
          f"attempts={HTTP_ATTEMPTS}")
    rows, errors = [], []
    auth_dead = False
    for kind in config.BID_KINDS:
        if auth_dead:
            errors.append(f"{kind['name']}: skipped (auth)")
            continue
        try:
            raw = _fetch_kind(key, kind, bgn, end, pages)
        except Exception as e:
            reason = _err_reason(e)
            errors.append(f"{kind['name']}: {reason}")
            print(f"  [입찰 {kind['name']}] 호출 실패({reason})")
            msg = str(e)
            if any(x in msg for x in (
                "resultCode=01", "resultCode=30", "resultCode=31", "resultCode=32",
            )) or _http_code(e) in (400, 401, 403) or reason in (
                "HTTP 400", "HTTP 401", "HTTP 403",
            ):
                auth_dead = True
            continue
        for item in raw:
            row = normalize(item, kind["name"], now=now)
            if row:
                rows.append(row)
    processed = process(rows, now=now)
    if processed:
        _save_cache(processed)
        if errors:
            print(f"  [입찰] 일부 종류 실패, {len(processed)}건은 유지")
        return processed
    if errors:
        raise RuntimeError("; ".join(errors))
    return processed


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
