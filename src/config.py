# -*- coding: utf-8 -*-
"""사이트 전역 설정. 도메인/애드센스 ID만 바꾸면 됨."""
import os
import re


def formspree_url(raw=None):
    """정적 알림 폼 엔드포인트. 없으면 빈 문자열 → mailto 폴백.

    `FORMSPREE_ID` 는 Formspree 공개 폼 ID (`xpzgkjyz`) 또는
    `https://formspree.io/f/...` 전체 URL. Getform 등 https 웹훅도 허용.
    코드에 실제 ID를 넣지 않는다. 키가 없거나 형식이 이상하면 빈 값.
    """
    if raw is None:
        raw = os.environ.get("FORMSPREE_ID") or os.environ.get("FORMSPREE_ENDPOINT") or ""
    raw = str(raw or "").strip()
    if not raw:
        return ""
    if raw.startswith("https://"):
        return raw.split("?", 1)[0]
    if re.fullmatch(r"[A-Za-z0-9]+", raw):
        return "https://formspree.io/f/" + raw
    return ""


SITE = {
    "name": "지원사업 마감판",
    "tagline": "오늘 마감되는 정부지원사업부터 봅니다",
    "domain": "https://magampan.com",
    "adsense_client": "ca-pub-2738052782253666",
    # 디스플레이 광고 단위 슬롯 ID. 비어 있으면 수동 유닛을 그리지 않고
    # <head>의 자동 광고만 동작한다(빈 회색 박스를 남기지 않기 위함).
    # 애드센스 > 광고 > 디스플레이 광고에서 단위를 만든 뒤 숫자 ID를 넣으면
    # 해당 자리에 채워진다. 가짜 ID를 넣지 말 것.
    "adsense_slots": {
        "list_top": "",
        "list_mid": "",
        "list_bottom": "",
        "detail_mid": "",
        "detail_bottom": "",
    },
    "allow_index": True,                   # 도메인 연결 완료 (2026-09-04)
    "ga_id": "",                           # ← G-XXXXXXX (선택)
    "google_site_verification": "Gu5i_F8dMB1UeRpB-399OCLdtPoVFe1e3Ed2opMQIbQ",
    "naver_site_verification": "0bc9dc85c2832ca5736a60371a695d6cc6d8d3d4",
    "email": "qwqw050009@gmail.com",
    # 빌드 시 FORMSPREE_ID 가 있으면 알림 폼이 여기로 POST 한다. 코드에 ID를 넣지 않음.
    "formspree_id": "",
    "publisher": "지원사업 마감판",
    # 사업자등록 전. 대표자·등록번호·통신판매업·주소는 비워 두고 가짜 숫자를 만들지 않는다.
    "business": {
        "ceo": "",
        "biz_no": "",
        "mail_order": "",
        "address": "",
    },
}

# IndexNow(빙·네이버 지원) 소유 확인용 랜덤 토큰. 로그인/가입이 필요한
# API 키가 아니라 사이트 소유권 확인용 공개 문자열이라 값 자체는 비밀이
# 아니다 — 다만 도메인이 example.com인 동안은 검색엔진에 제출해봐야
# 의미가 없으니 allow_index가 True일 때만 build.py에서 실제로 핑을 보낸다.
INDEXNOW_KEY = "6f753d4933a33d1f858c76dc38a574f0"

# 기업마당 분야 8종 (API 필드와 1:1 매칭)
CATEGORIES = [
    {"slug": "financial", "name": "금융", "desc": "융자·보증·이차보전 등 자금 지원"},
    {"slug": "tech", "name": "기술", "desc": "R&D·기술개발·특허 지원"},
    {"slug": "manpower", "name": "인력", "desc": "채용·인건비·교육훈련 지원"},
    {"slug": "export", "name": "수출", "desc": "해외진출·바우처·전시회 지원"},
    {"slug": "domestic", "name": "내수", "desc": "판로개척·마케팅·유통 지원"},
    {"slug": "startup", "name": "창업", "desc": "예비·초기창업 사업화 자금"},
    {"slug": "management", "name": "경영", "desc": "컨설팅·경영개선·시설 지원"},
    {"slug": "etc", "name": "기타", "desc": "그 외 지원사업"},
]

# 실데이터(2026-09) 기준. 광주·전남은 전남광주통합특별시로 합쳐져 있다.
REGIONS = [
    {"slug": "seoul", "name": "서울"}, {"slug": "busan", "name": "부산"},
    {"slug": "daegu", "name": "대구"}, {"slug": "incheon", "name": "인천"},
    {"slug": "daejeon", "name": "대전"}, {"slug": "ulsan", "name": "울산"},
    {"slug": "sejong", "name": "세종"}, {"slug": "gyeonggi", "name": "경기"},
    {"slug": "gangwon", "name": "강원"}, {"slug": "chungbuk", "name": "충북"},
    {"slug": "chungnam", "name": "충남"}, {"slug": "jeonbuk", "name": "전북"},
    {"slug": "jeonnam-gwangju", "name": "전남광주"},
    {"slug": "gyeongbuk", "name": "경북"}, {"slug": "gyeongnam", "name": "경남"},
    {"slug": "jeju", "name": "제주"}, {"slug": "nationwide", "name": "전국"},
]

# 롱테일 페이지: 지역(18) x 분야(8) = 144개 조합 페이지 자동 생성
# + 공고 상세페이지 N개 + 허브 26개

# ── 입찰(나라장터) 전용. 지원 목록·지역·분야 페이지에 섞지 않는다. ──
# 업무구분 4종. API 오퍼레이션은 종류마다 다르다 (한 오퍼레이션으로 전체를 받으면 안 됨).
BID_KINDS = [
    {"slug": "goods", "name": "물품", "api": "thng",
     "op": "getBidPblancListInfoThng", "desc": "물품 구매 입찰공고"},
    {"slug": "service", "name": "용역", "api": "servc",
     "op": "getBidPblancListInfoServc", "desc": "용역 입찰공고"},
    {"slug": "construction", "name": "공사", "api": "cnstwk",
     "op": "getBidPblancListInfoCnstwk", "desc": "공사 입찰공고"},
    {"slug": "foreign", "name": "외자", "api": "frgcpt",
     "op": "getBidPblancListInfoFrgcpt", "desc": "외자 입찰공고"},
]

# 나라장터 참가제한·참가가능 지역 필드와 1:1 정확 일치만 인정한다.
# 제목에서 정규식으로 추측하지 않는다. 광주·전남은 나라장터에서 따로 오므로
# 지원사업 쪽 전남광주 통합 단위와 합치지 않는다.
BID_REGIONS = [
    {"slug": "seoul", "name": "서울"}, {"slug": "busan", "name": "부산"},
    {"slug": "daegu", "name": "대구"}, {"slug": "incheon", "name": "인천"},
    {"slug": "gwangju", "name": "광주"}, {"slug": "daejeon", "name": "대전"},
    {"slug": "ulsan", "name": "울산"}, {"slug": "sejong", "name": "세종"},
    {"slug": "gyeonggi", "name": "경기"}, {"slug": "gangwon", "name": "강원"},
    {"slug": "chungbuk", "name": "충북"}, {"slug": "chungnam", "name": "충남"},
    {"slug": "jeonbuk", "name": "전북"}, {"slug": "jeonnam", "name": "전남"},
    {"slug": "gyeongbuk", "name": "경북"}, {"slug": "gyeongnam", "name": "경남"},
    {"slug": "jeju", "name": "제주"}, {"slug": "nationwide", "name": "전국"},
]
