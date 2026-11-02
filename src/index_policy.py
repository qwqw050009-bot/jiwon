"""
색인 정책 (2026-11 GSC: 색인 834 / 크롤링됨-미색인 4,783 / 발견됨-미색인 5,659).

구글이 비슷하고 얇은 페이지가 너무 많다고 보고 크롤링을 거의 멈췄다. 그래서
sitemap·index 대상을 '검색으로 들어올 가치가 있는' 수백 개로 줄인다.
페이지(HTML)는 모두 200 으로 남기고 noindex,follow + sitemap 제외만 한다.

색인하는 것
  - 홈·가이드·고정 페이지·지역/분야 허브·입찰 홈/종류 허브 (그대로)
  - 접수 중이고 본문이 충분한(NOTICE_RICH_MIN 자 이상, 얇지 않은) 지원 공고
  - data/keep_indexed.json 에 있는 URL (서치콘솔 노출·클릭 이력) — 무조건
색인하지 않는 것
  - 마감된 지원 공고(일수와 상관없이), 얇은 공고
  - 입찰 상세 전부(나라장터 원문을 옮긴 정형 페이지라 서로 거의 같다) — keep 제외
  - 접수 중 공고가 LIST_MIN_OPEN 건 미만인 시군구 허브·지역×분야 조합
"""

NOTICE_RICH_MIN = 300   # 요약(개요+요점) 글자 수
LIST_MIN_OPEN = 8       # 시군구·지역×분야 목록을 색인할 최소 접수 중 공고 수


def notice_indexable(a, npath, keep=(), thin=False, body_len=0):
    if npath in keep:
        return True
    a = a or {}
    if a.get("is_closed") or not a.get("is_open", True):
        return False
    if thin:
        return False
    return body_len >= NOTICE_RICH_MIN


def bid_indexable(npath, keep=(), canonical_path=None):
    if canonical_path:
        return False
    return npath in keep


def is_permutation(path):
    """/region/{지역}/{시군구 또는 분야}/ 같은 2단 이상 조합 목록."""
    parts = [p for p in path.strip("/").split("/") if p]
    return len(parts) >= 3 and parts[0] == "region"


def list_indexable(path, items, keep=()):
    if path in keep or not is_permutation(path):
        return True
    n_open = sum(1 for a in items or () if a.get("is_open"))
    return n_open >= LIST_MIN_OPEN
