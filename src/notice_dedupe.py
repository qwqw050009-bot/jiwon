# -*- coding: utf-8 -*-
"""같은 공고가 여러 번(같은 소스 재게시·다른 소스) 들어온 것을 하나로 합친다.

같은 공고 = 정규화한 (제목, 소관기관, 수행기관, 마감) 이 모두 같은 것.
- 제목: 앞의 [지역] 같은 꺾쇠 접두, 공백·문장부호를 지우고 소문자.
- 기관: 공백·문장부호·(주)/(사)/주식회사 제거.
  소관부처만 같고 수행기관이 다르면(예: 고용노동부 + 지역별 운영기관) 다른 공고다.
- 마감: apply_end. 상시 공고(period_type=always)는 모두 "always" 로 본다.
  마감이 없는(날짜도 상시도 아닌) 행은 합치지 않는다.

남길 공고(canonical): keep(서치콘솔 노출 URL) 에 있는 것 → 가장 최근 게시
(created 큰 것, 같으면 id 큰 것). 최근 게시가 원문 목록에 더 오래 남는다.
나머지는 /notice/<dup>/ → /notice/<canonical>/ 301 로 넘긴다(색인 신호 이전).
"""
import re

_PREFIX = re.compile(r"^\s*(?:[\[\(【〔<][^\]\)】〕>]{0,20}[\]\)】〕>]\s*)+")
_NONWORD = re.compile(r"[\W_]+", re.U)
_CORP = re.compile(r"\((?:주|사|재)\)|주식회사|사단법인|재단법인")


def norm_title(s):
    s = _PREFIX.sub("", s or "")
    return _NONWORD.sub("", s).lower()


def norm_org(s):
    return _NONWORD.sub("", _CORP.sub("", s or "")).lower()


def key(r):
    t = norm_title(r.get("title"))
    if not t:
        return None
    if r.get("period_type") == "always":
        end = "always"
    else:
        end = (r.get("apply_end") or "").strip()
    if not end:
        return None
    return (t, norm_org(r.get("org")), norm_org(r.get("exec_org")), end)


def _rank(r, keep):
    rid = str(r.get("id") or "")
    num = int(re.sub(r"\D", "", rid) or 0)
    return (f"/notice/{rid}/" in keep, r.get("created") or "", num, rid)


def dedupe(rows, keep=frozenset()):
    """rows → (남긴 rows(원래 순서 유지), {dup_id: canonical_id})."""
    groups = {}
    for r in rows:
        k = key(r)
        if k is not None:
            groups.setdefault(k, []).append(r)
    alias = {}
    for g in groups.values():
        if len(g) < 2:
            continue
        canon = max(g, key=lambda r: _rank(r, keep))
        for r in g:
            if r is not canon and r.get("id") != canon.get("id"):
                alias[str(r["id"])] = str(canon["id"])
    out = [r for r in rows if str(r.get("id")) not in alias]
    return out, alias


def redirect_pairs(alias):
    return sorted((f"/notice/{d}/", f"/notice/{c}/") for d, c in alias.items())
