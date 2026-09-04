# -*- coding: utf-8 -*-
"""사이트 전역 설정. 도메인/애드센스 ID만 바꾸면 됨."""

SITE = {
    "name": "지원사업 마감판",
    "tagline": "오늘 마감되는 정부지원사업부터 봅니다",
    "domain": "https://magampan.com",
    "adsense_client": "",                  # ← ca-pub-XXXXXXXX (승인 후 입력)
    "allow_index": True,                   # 도메인 연결 완료 (2026-09-04)
    "ga_id": "",                           # ← G-XXXXXXX (선택)
    "google_site_verification": "Gu5i_F8dMB1UeRpB-399OCLdtPoVFe1e3Ed2opMQIbQ",
    "naver_site_verification": "0bc9dc85c2832ca5736a60371a695d6cc6d8d3d4",
    "email": "contact@example.com",
    "publisher": "지원사업 마감판",
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
