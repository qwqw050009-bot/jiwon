# -*- coding: utf-8 -*-
"""
시군구(기초자치단체) 롱테일 페이지용 허용 목록과 매칭.

지역을 정규식으로 추측하지 않는다 (CLAUDE.md 1번). 공고가 어떤 시군구에
속하는지는 기업마당 해시태그(normalize()가 만든 tags)가 이 목록의
name_ko와 정확히 같을 때만 인정한다.

전남광주통합특별시는 광주+전남 통합 단위이므로 전남 시·군과 광주의
고유 자치구(광산구)를 모두 sido_name='전남광주' 아래에 둔다. 분리하지 않는다.

중구·동구·서구·남구·북구·강서구처럼 여러 광역에 같은 이름이 있으면
해시태그만으로는 시도를 특정할 수 없어 목록에 넣지 않는다.
고성군(강원/경남)도 같은 이유로 뺀다.
"""
from collections import defaultdict

import config

# 허브·분야 조합 페이지를 만들 최소 건수. 미달 URL은 파일을 쓰지 않아
# Cloudflare Pages가 dist/404.html을 진짜 404로 돌리게 한다.
MIN_COUNT = 3

# 기존 /region/{sido}/{category}/ 경로와 겹치면 안 되는 예약 슬러그.
RESERVED_SLUGS = {c["slug"] for c in config.CATEGORIES}

# 실데이터 해시태그에 보이지만 시군구가 아닌 것. 허용 목록에 넣지 않는다.
# (자동으로 시/군/구 접미를 긁으면 이 잡음이 섞인다.)
NOISE_TAGS = (
    "전시", "게임전시", "제품전시", "샘플전시",
    "관광도시", "창업도시", "실증도시", "스마트도시",
    "규제자유특구", "강소특구", "경남창원강소특구", "창원강소특구", "수안보관광특구",
    "고위험산업군", "국제표준화기구",
    "보호구", "안전보호구", "원상복구", "연말연시", "공동연구",
    "서울특별시", "부산광역시", "대구광역시", "인천광역시", "대전광역시",
    "울산광역시", "광주광역시", "세종특별자치시", "전남광주통합특별시",
    "세종시", "울산시",  # 광역 별칭. 기초가 아님
    "화성특례시", "용인특례시",  # 공식 기초명은 화성시·용인시
)


def _d(name_ko, slug, sido_name):
    return {"name_ko": name_ko, "slug": slug, "sido_name": sido_name}


# 공식 시·군·고유 자치구. slug는 기존 지역 슬러그와 같이 ASCII kebab
# (ansan, hwaseong, jinju, yeosu, gumi). 로마자는 국어의 로마자 표기법.
DISTRICTS = [
    # 서울 자치구 (중구·강서구는 타 광역과 겹쳐 생략)
    _d("종로구", "jongno", "서울"),
    _d("용산구", "yongsan", "서울"),
    _d("성동구", "seongdong", "서울"),
    _d("광진구", "gwangjin", "서울"),
    _d("동대문구", "dongdaemun", "서울"),
    _d("중랑구", "jungnang", "서울"),
    _d("성북구", "seongbuk", "서울"),
    _d("강북구", "gangbuk", "서울"),
    _d("도봉구", "dobong", "서울"),
    _d("노원구", "nowon", "서울"),
    _d("은평구", "eunpyeong", "서울"),
    _d("서대문구", "seodaemun", "서울"),
    _d("마포구", "mapo", "서울"),
    _d("양천구", "yangcheon", "서울"),
    _d("구로구", "guro", "서울"),
    _d("금천구", "geumcheon", "서울"),
    _d("영등포구", "yeongdeungpo", "서울"),
    _d("동작구", "dongjak", "서울"),
    _d("관악구", "gwanak", "서울"),
    _d("서초구", "seocho", "서울"),
    _d("강남구", "gangnam", "서울"),
    _d("송파구", "songpa", "서울"),
    _d("강동구", "gangdong", "서울"),

    # 부산 (중·서·동·남·북·강서구 생략)
    _d("영도구", "yeongdo", "부산"),
    _d("부산진구", "busanjin", "부산"),
    _d("동래구", "dongnae", "부산"),
    _d("해운대구", "haeundae", "부산"),
    _d("사하구", "saha", "부산"),
    _d("금정구", "geumjeong", "부산"),
    _d("연제구", "yeonje", "부산"),
    _d("수영구", "suyeong", "부산"),
    _d("사상구", "sasang", "부산"),
    _d("기장군", "gijang", "부산"),

    # 대구 (중·동·서·남·북구 생략). 군위는 2023년부터 대구.
    _d("수성구", "suseong", "대구"),
    _d("달서구", "dalseo", "대구"),
    _d("달성군", "dalseong", "대구"),
    _d("군위군", "gunwi", "대구"),

    # 인천 (중·동·서구 생략)
    _d("미추홀구", "michuhol", "인천"),
    _d("연수구", "yeonsu", "인천"),
    _d("남동구", "namdong", "인천"),
    _d("부평구", "bupyeong", "인천"),
    _d("계양구", "gyeyang", "인천"),
    _d("강화군", "ganghwa", "인천"),
    _d("옹진군", "ongjin", "인천"),

    # 대전 (동·중·서구 생략)
    _d("유성구", "yuseong", "대전"),
    _d("대덕구", "daedeok", "대전"),

    # 울산 (중·남·동·북구 생략)
    _d("울주군", "ulju", "울산"),

    # 세종은 단층제. 기초 시군구 페이지를 두지 않는다.

    # 경기 31
    _d("수원시", "suwon", "경기"),
    _d("고양시", "goyang", "경기"),
    _d("용인시", "yongin", "경기"),
    _d("성남시", "seongnam", "경기"),
    _d("부천시", "bucheon", "경기"),
    _d("안산시", "ansan", "경기"),
    _d("안양시", "anyang", "경기"),
    _d("남양주시", "namyangju", "경기"),
    _d("화성시", "hwaseong", "경기"),
    _d("평택시", "pyeongtaek", "경기"),
    _d("의정부시", "uijeongbu", "경기"),
    _d("시흥시", "siheung", "경기"),
    _d("파주시", "paju", "경기"),
    _d("광명시", "gwangmyeong", "경기"),
    _d("김포시", "gimpo", "경기"),
    _d("군포시", "gunpo", "경기"),
    _d("광주시", "gwangju", "경기"),
    _d("이천시", "icheon", "경기"),
    _d("양주시", "yangju", "경기"),
    _d("오산시", "osan", "경기"),
    _d("구리시", "guri", "경기"),
    _d("안성시", "anseong", "경기"),
    _d("포천시", "pocheon", "경기"),
    _d("의왕시", "uiwang", "경기"),
    _d("하남시", "hanam", "경기"),
    _d("여주시", "yeoju", "경기"),
    _d("동두천시", "dongducheon", "경기"),
    _d("과천시", "gwacheon", "경기"),
    _d("가평군", "gapyeong", "경기"),
    _d("양평군", "yangpyeong", "경기"),
    _d("연천군", "yeoncheon", "경기"),

    # 강원 (고성군은 경남과 겹쳐 생략)
    _d("춘천시", "chuncheon", "강원"),
    _d("원주시", "wonju", "강원"),
    _d("강릉시", "gangneung", "강원"),
    _d("동해시", "donghae", "강원"),
    _d("태백시", "taebaek", "강원"),
    _d("속초시", "sokcho", "강원"),
    _d("삼척시", "samcheok", "강원"),
    _d("홍천군", "hongcheon", "강원"),
    _d("횡성군", "hoengseong", "강원"),
    _d("영월군", "yeongwol", "강원"),
    _d("평창군", "pyeongchang", "강원"),
    _d("정선군", "jeongseon", "강원"),
    _d("철원군", "cheorwon", "강원"),
    _d("화천군", "hwacheon", "강원"),
    _d("양구군", "yanggu", "강원"),
    _d("인제군", "inje", "강원"),
    _d("양양군", "yangyang", "강원"),

    # 충북
    _d("청주시", "cheongju", "충북"),
    _d("충주시", "chungju", "충북"),
    _d("제천시", "jecheon", "충북"),
    _d("보은군", "boeun", "충북"),
    _d("옥천군", "okcheon", "충북"),
    _d("영동군", "yeongdong", "충북"),
    _d("증평군", "jeungpyeong", "충북"),
    _d("진천군", "jincheon", "충북"),
    _d("괴산군", "goesan", "충북"),
    _d("음성군", "eumseong", "충북"),
    _d("단양군", "danyang", "충북"),

    # 충남
    _d("천안시", "cheonan", "충남"),
    _d("공주시", "gongju", "충남"),
    _d("보령시", "boryeong", "충남"),
    _d("아산시", "asan", "충남"),
    _d("서산시", "seosan", "충남"),
    _d("논산시", "nonsan", "충남"),
    _d("계룡시", "gyeryong", "충남"),
    _d("당진시", "dangjin", "충남"),
    _d("금산군", "geumsan", "충남"),
    _d("부여군", "buyeo", "충남"),
    _d("서천군", "seocheon", "충남"),
    _d("청양군", "cheongyang", "충남"),
    _d("홍성군", "hongseong", "충남"),
    _d("예산군", "yesan", "충남"),
    _d("태안군", "taean", "충남"),

    # 전북
    _d("전주시", "jeonju", "전북"),
    _d("군산시", "gunsan", "전북"),
    _d("익산시", "iksan", "전북"),
    _d("정읍시", "jeongeup", "전북"),
    _d("남원시", "namwon", "전북"),
    _d("김제시", "gimje", "전북"),
    _d("완주군", "wanju", "전북"),
    _d("진안군", "jinan", "전북"),
    _d("무주군", "muju", "전북"),
    _d("장수군", "jangsu", "전북"),
    _d("임실군", "imsil", "전북"),
    _d("순창군", "sunchang", "전북"),
    _d("고창군", "gochang", "전북"),
    _d("부안군", "buan", "전북"),

    # 전남광주: 전남 시·군 + 광주 고유 구(광산구). 동·서·남·북구는 생략.
    _d("목포시", "mokpo", "전남광주"),
    _d("여수시", "yeosu", "전남광주"),
    _d("순천시", "suncheon", "전남광주"),
    _d("나주시", "naju", "전남광주"),
    _d("광양시", "gwangyang", "전남광주"),
    _d("담양군", "damyang", "전남광주"),
    _d("곡성군", "gokseong", "전남광주"),
    _d("구례군", "gurye", "전남광주"),
    _d("고흥군", "goheung", "전남광주"),
    _d("보성군", "boseong", "전남광주"),
    _d("화순군", "hwasun", "전남광주"),
    _d("장흥군", "jangheung", "전남광주"),
    _d("강진군", "gangjin", "전남광주"),
    _d("해남군", "haenam", "전남광주"),
    _d("영암군", "yeongam", "전남광주"),
    _d("무안군", "muan", "전남광주"),
    _d("함평군", "hampyeong", "전남광주"),
    _d("영광군", "yeonggwang", "전남광주"),
    _d("장성군", "jangseong", "전남광주"),
    _d("완도군", "wando", "전남광주"),
    _d("진도군", "jindo", "전남광주"),
    _d("신안군", "sinan", "전남광주"),
    _d("광산구", "gwangsan", "전남광주"),

    # 경북
    _d("포항시", "pohang", "경북"),
    _d("경주시", "gyeongju", "경북"),
    _d("김천시", "gimcheon", "경북"),
    _d("안동시", "andong", "경북"),
    _d("구미시", "gumi", "경북"),
    _d("영주시", "yeongju", "경북"),
    _d("영천시", "yeongcheon", "경북"),
    _d("상주시", "sangju", "경북"),
    _d("문경시", "mungyeong", "경북"),
    _d("경산시", "gyeongsan", "경북"),
    _d("의성군", "uiseong", "경북"),
    _d("청송군", "cheongsong", "경북"),
    _d("영양군", "yeongyang", "경북"),
    _d("영덕군", "yeongdeok", "경북"),
    _d("청도군", "cheongdo", "경북"),
    _d("고령군", "goryeong", "경북"),
    _d("성주군", "seongju", "경북"),
    _d("칠곡군", "chilgok", "경북"),
    _d("예천군", "yecheon", "경북"),
    _d("봉화군", "bonghwa", "경북"),
    _d("울진군", "uljin", "경북"),
    _d("울릉군", "ulleung", "경북"),

    # 경남 (고성군 생략)
    _d("창원시", "changwon", "경남"),
    _d("진주시", "jinju", "경남"),
    _d("통영시", "tongyeong", "경남"),
    _d("사천시", "sacheon", "경남"),
    _d("김해시", "gimhae", "경남"),
    _d("밀양시", "miryang", "경남"),
    _d("거제시", "geoje", "경남"),
    _d("양산시", "yangsan", "경남"),
    _d("의령군", "uiryeong", "경남"),
    _d("함안군", "haman", "경남"),
    _d("창녕군", "changnyeong", "경남"),
    _d("남해군", "namhae", "경남"),
    _d("하동군", "hadong", "경남"),
    _d("산청군", "sancheong", "경남"),
    _d("함양군", "hamyang", "경남"),
    _d("거창군", "geochang", "경남"),
    _d("합천군", "hapcheon", "경남"),

    # 제주 행정시
    _d("제주시", "jeju-si", "제주"),
    _d("서귀포시", "seogwipo", "제주"),
]


SIDO_NAMES = {r["name"] for r in config.REGIONS}
SIDO_SLUG = {r["name"]: r["slug"] for r in config.REGIONS}


def _validate():
    seen_pair, seen_slug = set(), set()
    for d in DISTRICTS:
        name, slug, sido = d["name_ko"], d["slug"], d["sido_name"]
        if sido not in SIDO_NAMES or sido == "전국":
            raise ValueError(f"시군구 '{name}'의 sido_name '{sido}'가 REGIONS에 없음")
        if slug in RESERVED_SLUGS:
            raise ValueError(f"시군구 슬러그 '{slug}'가 분야 슬러그와 충돌")
        if name in NOISE_TAGS:
            raise ValueError(f"잡음 태그 '{name}'를 허용 목록에 넣지 말 것")
        pair = (sido, name)
        if pair in seen_pair:
            raise ValueError(f"중복 시군구 {pair}")
        seen_pair.add(pair)
        key = (sido, slug)
        if key in seen_slug:
            raise ValueError(f"같은 시도 안 슬러그 충돌 {key}")
        seen_slug.add(key)
        if not slug.replace("-", "").isalnum() or slug != slug.lower() or "_" in slug:
            raise ValueError(f"슬러그 '{slug}'는 ASCII kebab 소문자여야 함")


_validate()

BY_SIDO = defaultdict(list)
for _drow in DISTRICTS:
    BY_SIDO[_drow["sido_name"]].append(_drow)


def belongs(notice, district):
    """
    공고가 이 시군구 페이지에 들어가는지.
    - tags에 district.name_ko가 정확히 들어 있고
    - notice.region이 그 시군구의 시도이거나 '전국'
    다른 시도 공고는 태그가 같아도 넣지 않는다.
    """
    tags = notice.get("tags") or []
    if district["name_ko"] not in tags:
        return False
    region = notice.get("region") or "전국"
    return region == district["sido_name"] or region == "전국"


def tag_index(rows):
    """태그 → 그 태그를 가진 공고 목록 (rows 순서 유지)."""
    idx = defaultdict(list)
    for a in rows:
        seen = set()
        for t in a.get("tags") or []:
            if t in seen:
                continue
            seen.add(t)
            idx[t].append(a)
    return idx


def notices_from_index(idx, district):
    sido = district["sido_name"]
    out = []
    for a in idx.get(district["name_ko"], []):
        region = a.get("region") or "전국"
        if region == sido or region == "전국":
            out.append(a)
    return out


def grouped(rows):
    """
    생성 기준(MIN_COUNT)을 넘는 시군구만.
    반환: sido_name → [(district_dict, items), ...] 건수 내림차순.
    """
    idx = tag_index(rows)
    by_sido = defaultdict(list)
    for d in DISTRICTS:
        items = notices_from_index(idx, d)
        if len(items) >= MIN_COUNT:
            by_sido[d["sido_name"]].append((d, items))
    for sido in by_sido:
        by_sido[sido].sort(key=lambda x: (-len(x[1]), x[0]["name_ko"]))
    return by_sido
