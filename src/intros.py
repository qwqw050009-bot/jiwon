# -*- coding: utf-8 -*-
"""
지역×분야 롱테일 페이지용 소개문·FAQ.

LLM을 페이지마다 부르지 않는다. 그 페이지에 실제로 올라온 공고(건수,
소관기관, 마감일, 상시 접수 원문 표기)와, 분야/지역마다 다른 고정 문구를
끼워 넣을 뿐이다. 없는 공고를 만들어 넣지 않는다.

구글 FAQ 가이드라인: JSON-LD 답변은 화면에 보이는 문구와 같아야 한다.
"""
from html import escape as h
import json
import re

from enrich import _josa, card_line
import config


# 지역 페이지가 "무엇을 묶는지"만 설명한다. 특정 공고·예산을 지어내지 않는다.
# 전남광주는 통합 단위 그대로 둔다 (분리 금지).
REGION_BLURB = {
    "서울": "서울은 시 사업과 자치구 사업이 한 목록입니다. 소관기관이 구청이면 그 구에 사업장이 있어야 하는 경우가 많습니다.",
    "부산": "부산은 시 사업과 구·군 사업이 섞여 있습니다. 공고문 대상 지역이 특정 구로 좁혀져 있는지 소관기관과 맞춰 보세요.",
    "대구": "대구는 광역시 사업과 구 사업이 함께 있습니다. 소관기관이 구청이면 그 구 요건을 원문에서 먼저 보세요.",
    "인천": "인천은 시 사업과 구·군 사업이 함께 올라옵니다. 대상 지역이 짧게 적혀 있어도 원문에 세부 요건이 있는 경우가 있습니다.",
    "대전": "대전은 광역시 사업과 구 사업이 한 목록입니다. 소관기관을 보면 시 전체인지 구 단위인지 가늠할 수 있습니다.",
    "울산": "울산은 시 사업과 구·군 사업이 섞여 있습니다. 목록의 기관명과 공고문 대상 지역을 함께 보세요.",
    "세종": "세종은 시 단위 공고가 중심입니다. 소재지 제한이 없는 사업은 전국 페이지에 따로 있습니다.",
    "경기": "경기는 도와 시·군 공고가 함께 있어 목록이 길어지기 쉽습니다. 시·군 사업은 해당 지역 사업장 요건이 붙는 경우가 많습니다.",
    "강원": "강원은 도와 시·군 공고가 섞여 있습니다. 소관기관이 시·군이면 그 지역 사업장 요건을 원문에서 확인하세요.",
    "충북": "충북은 도와 시·군 공고가 한 목록입니다. 대상 지역이 특정 시·군으로 적혀 있는지 공고문에서 한 번 더 보세요.",
    "충남": "충남은 도와 시·군 공고가 함께 올라옵니다. 소관기관이 범위를 나누는 가장 빠른 힌트입니다.",
    "전북": "전북은 도와 시·군 공고가 함께 있습니다. 소관기관과 공고문 대상 지역이 일치하는지만 보면 됩니다.",
    "전남광주": "전남광주통합특별시 단위로 묶여 있습니다. 광주와 전남을 따로 나누지 않으니, 예전에 광역시·도로 찾던 공고도 이 목록에서 보시면 됩니다.",
    "경북": "경북은 도와 시·군 공고가 섞여 있습니다. 대상 지역 문구가 짧아도 원문에 세부 조건이 있는 경우가 있습니다.",
    "경남": "경남은 도와 시·군 공고가 한 목록입니다. 소관기관이 시·군이면 해당 지역 사업장 요건을 확인하세요.",
    "제주": "제주는 도 단위 공고가 많은 편입니다. 소재지 제한이 없는 사업은 전국 페이지에서 따로 볼 수 있습니다.",
    "전국": "사업장 소재지 제한이 없는 공고만 모았습니다. 특정 시·도에만 열리는 사업은 해당 지역 페이지에 있습니다.",
}

# REGION_BLURB의 두 번째 표현. 같은 지역 안에서 분야 8종 페이지에 이
# 문장이 그대로 반복되면 중복 콘텐츠 신호가 되기 쉬워서, 분야명을
# 씨드로 한 해시로 두 표현 중 하나를 고정 선택한다(_blurb_variant 참고).
REGION_BLURB_ALT = {
    "서울": "자치구 사업 비중이 큰 지역입니다. 소관기관 이름에 구청이 있으면 그 구 소재 사업장만 신청 가능한 경우가 대부분입니다.",
    "부산": "구·군 단위 공고가 상당수를 차지합니다. 공고 제목이나 소관기관에 구·군 이름이 있으면 그 지역 사업장 기준입니다.",
    "대구": "구 단위로 갈라진 공고가 많은 편입니다. 소관기관이 구청이면 대구광역시 전체가 아니라 그 구로 한정된다고 보면 됩니다.",
    "인천": "구·군 단위 공고 비중이 높습니다. 대상 지역 표기가 짧아도 실제로는 특정 구로 좁혀진 경우가 있으니 원문을 확인하세요.",
    "대전": "구 단위 공고와 시 전체 공고가 섞여 있습니다. 소관기관이 구청인지 대전광역시인지로 범위를 가늠하세요.",
    "울산": "구·군 단위 공고가 함께 올라옵니다. 목록의 기관명이 범위를 가르는 가장 빠른 단서입니다.",
    "세종": "세종특별자치시 단위로 공고가 올라옵니다. 사업장 소재지 제한이 없다면 전국 페이지도 함께 확인하세요.",
    "경기": "31개 시·군의 공고가 한 목록에 모입니다. 시·군 이름이 소관기관에 있으면 그 지역 사업장 요건이 붙는 경우가 대부분입니다.",
    "강원": "시·군별로 흩어진 공고가 많습니다. 소관기관 이름의 시·군과 원문 대상 지역이 일치하는지 먼저 보세요.",
    "충북": "시·군 단위 공고 비중이 높은 지역입니다. 대상 지역이 도 전체가 아니라 특정 시·군일 수 있으니 원문을 한 번 더 보세요.",
    "충남": "도 공고와 시·군 공고가 함께 목록에 올라옵니다. 소관기관 이름으로 범위를 먼저 가르면 빠릅니다.",
    "전북": "시·군 단위 공고가 다수입니다. 소관기관과 원문 대상 지역이 일치하는지만 확인하면 됩니다.",
    "전남광주": "광주와 전남을 나누지 않는 통합 단위입니다. 예전에 광주광역시나 전라남도로 찾던 공고도 이 하나의 목록에 있습니다.",
    "경북": "시·군별 공고가 도 전체 공고와 섞여 있습니다. 짧게 적힌 대상 지역도 원문에 세부 조건이 있을 수 있습니다.",
    "경남": "시·군 단위 공고 비중이 높습니다. 소관기관이 시·군이면 그 지역 사업장 기준으로 좁혀집니다.",
    "제주": "제주특별자치도 단위로 공고가 올라옵니다. 소재지 제한이 없는 사업은 전국 목록에서 따로 확인할 수 있습니다.",
    "전국": "특정 시·도에 묶이지 않는 공고만 골랐습니다. 지역 제한이 있는 사업은 각 지역 페이지에서 확인하세요.",
}

CATEGORY_BLURB = {
    "금융": "융자·보증·이차보전처럼 갚아야 하는 자금과, 이자 일부를 보전하는 사업이 섞여 있습니다. 제목의 융자·보증·이차보전 표현을 보면 보조금과 구별하기 쉽습니다.",
    "기술": "R&D·기술개발·특허 지원이 중심입니다. 서류평가·발표평가가 붙는 선정형이 많아 사업계획서 완성도를 먼저 보는 편이 낫습니다.",
    "인력": "채용·인건비·교육훈련 지원입니다. 4대보험 가입 현황과 고용 유지 기간을 보는 공고가 많아, 인력 현황 서류를 먼저 챙겨 두는 편이 낫습니다.",
    "수출": "해외진출·수출바우처·전시회 지원이 많습니다. 예산 소진형 바우처가 섞여 있어 조건을 확인하는 대로 접수하는 쪽이 유리한 경우가 있습니다.",
    "내수": "판로개척·마케팅·유통 지원입니다. 채널 입점, 홍보비, 전시 참가가 많고 바우처형과 선정형이 함께 올라옵니다.",
    "창업": "예비·초기창업 사업화 자금, 입주, 교육이 중심입니다. 업력 3년·7년 이내 조건이 흔하고, 업력은 보통 사업자등록일 기준으로 셉니다.",
    "경영": "컨설팅·경영개선·시설 지원입니다. 업력 제한이 느슨한 공고가 있어, 이미 운영 중인 소상공인도 문을 두드릴 수 있는 편입니다.",
    "기타": "위 일곱 분야에 넣기 어려운 공고입니다. 제목과 소관기관을 보고 업종·상황이 맞는지만 가려 보시면 됩니다.",
}

# CATEGORY_BLURB의 두 번째 표현. 같은 분야 문장이 지역 17곳 페이지에
# 토씨 하나 안 틀리고 반복되면 중복 콘텐츠 신호가 되기 쉬워서, 지역명을
# 씨드로 한 해시로 두 표현 중 하나를 고정 선택한다(빌드마다 안 바뀜).
CATEGORY_BLURB_ALT = {
    "금융": "상환 의무가 있는 융자·보증과, 이자만 지원하는 이차보전이 한 목록에 섞여 있습니다. 갚아야 하는 자금인지 먼저 확인하세요.",
    "기술": "R&D 과제와 기술사업화 지원이 대부분입니다. 발표평가까지 가는 경쟁형이 많아, 신청 전에 사업계획서부터 준비하는 편이 유리합니다.",
    "인력": "채용·인건비 지원과 교육훈련 지원이 함께 있습니다. 4대보험 가입 이력을 미리 확인해 두면 서류 준비가 빨라집니다.",
    "수출": "수출바우처·해외전시회 참가 지원이 많고, 예산이 정해진 바우처형이 섞여 있어 조건만 맞으면 서두르는 편이 낫습니다.",
    "내수": "국내 판로·유통·마케팅 지원입니다. 온라인몰 입점, 홍보영상, 전시 참가 지원이 대표적입니다.",
    "창업": "초기·예비창업자를 위한 사업화 자금과 입주공간 지원이 중심입니다. 업력 기준은 사업자등록일부터 셉니다.",
    "경영": "운영 중인 사업장의 시설개선·컨설팅 지원입니다. 창업 초기가 아니어도 신청 가능한 공고가 많습니다.",
    "기타": "여덟 분야 분류에 딱 맞지 않는 공고들입니다. 제목과 지원대상을 먼저 확인하시면 됩니다.",
}


def _blurb_variant(seed, key, primary, alt):
    """
    primary[key] 또는 alt[key] 중 하나를 seed 문자열 해시로 고정 선택한다.
    같은 (seed,key) 조합은 재빌드해도 항상 같은 문장이 나와서 페이지
    내용이 매일 흔들리지 않는다. CATEGORY_BLURB는 seed=지역, key=분야로,
    REGION_BLURB는 seed=분야, key=지역으로 반대로 넣어 쓴다 — 그래야
    "같은 지역 안의 여러 분야 페이지"와 "같은 분야 안의 여러 지역 페이지"
    양쪽에서 반복이 갈린다.
    """
    v = alt.get(key)
    if not v:
        return primary.get(key) or ""
    return v if (sum(ord(c) for c in seed) % 2 == 0) else (primary.get(key) or v)


CATEGORY_GUIDE = {
    "금융": ("/guide/grant-vs-loan/", "지원금과 융자의 차이"),
    "기술": ("/guide/biz-plan-structure/", "사업계획서 기본 구조"),
    "인력": ("/guide/docs-checklist/", "준비서류 총정리"),
    "수출": ("/guide/voucher-vs-selection/", "바우처와 선정 사업 차이"),
    "내수": ("/guide/sme-apply/", "소상공인 지원금 신청 방법"),
    "창업": ("/guide/pre-vs-early/", "예비·초기창업패키지 차이"),
    "경영": ("/guide/sme-apply/", "소상공인 지원금 신청 방법"),
    "기타": ("/guide/workplace-region/", "지역 제한 공고 보는 법"),
}

ALWAYS_GUIDE = ("/guide/always-deadline/", "상시 접수 공고, 지금 신청해야 하는 이유")

# 지역을 행정 구조로만 묶는다. 특정 공고·예산을 지어내지 않는다.
# 전남광주는 통합 단위 그대로 둔다 (분리 금지).
_REGION_GROUP = {
    "서울": "metro_gu", "부산": "metro_gu", "대구": "metro_gu", "대전": "metro_gu",
    "인천": "metro_gun", "울산": "metro_gun",
    "경기": "wide",
    "강원": "do", "충북": "do", "충남": "do", "전북": "do", "경북": "do", "경남": "do",
    "세종": "city", "제주": "island",
    "전남광주": "united",
    "전국": "nation",
}

# (행정구조, 분야)마다 한 문장. 지역명 토큰만 갈아끼운 문장이 100쪽을
# 채우지 않도록, 구·군 구조와 분야 성격을 한 문장에 엮는다.
_COMBO_WEAVE = {
    ("metro_gu", "금융"): (
        "{r} 금융 공고는 시 사업과 구청 사업이 한 목록입니다. "
        "융자·보증·이차보전은 갚는 돈인지부터 보고, 소관기관이 구청이면 "
        "그 구 사업장 요건을 원문에서 확인하세요."
    ),
    ("metro_gu", "기술"): (
        "{r} 기술 공고는 광역시 과제와 구 단위 과제가 섞여 있습니다. "
        "R&D·기술개발은 선정형이 많아 사업계획서를 먼저 보는 편이 낫고, "
        "구청 공고면 그 구 소재 기업인지부터 가리세요."
    ),
    ("metro_gu", "인력"): (
        "{r} 인력 공고는 시 고용 사업과 구 채용 지원이 함께 올라옵니다. "
        "4대보험·고용 유지 기간을 보는 경우가 많고, 소관기관이 구청이면 "
        "그 구 사업장 기준입니다."
    ),
    ("metro_gu", "수출"): (
        "{r} 수출 공고는 시 해외진출 사업과 구 단위 바우처가 한 목록입니다. "
        "예산 소진형이면 조건을 확인하는 대로 접수하는 쪽이 유리합니다."
    ),
    ("metro_gu", "내수"): (
        "{r} 내수 공고는 시 판로 사업과 구 마케팅 지원이 섞여 있습니다. "
        "채널 입점·홍보비·전시는 바우처형과 선정형이 함께 있으니 제목의 "
        "바우처·선정 표현을 먼저 보세요."
    ),
    ("metro_gu", "창업"): (
        "{r} 창업 공고는 시 창업 센터 사업과 구 단위 사업화가 한 목록입니다. "
        "업력은 보통 사업자등록일 기준이고, 구청 공고면 그 구 소재인지를 "
        "원문에서 확인하세요."
    ),
    ("metro_gu", "경영"): (
        "{r} 경영 공고는 시 컨설팅·시설 사업과 구 소상공인 지원이 함께 있습니다. "
        "업력 제한이 느슨한 편이어도 구 단위면 그 구 사업장 요건이 붙습니다."
    ),
    ("metro_gu", "기타"): (
        "{r}에서 여덟 분야에 넣기 어려운 공고입니다. "
        "시 사업인지 구 사업인지는 소관기관이 가장 빠른 힌트입니다."
    ),
    ("metro_gun", "금융"): (
        "{r} 금융 공고는 시 사업과 구·군 사업이 섞여 있습니다. "
        "융자·보증 대상 지역이 특정 구·군으로 좁혀져 있는지 소관기관과 맞춰 보세요."
    ),
    ("metro_gun", "기술"): (
        "{r} 기술 공고는 광역시 과제와 구·군 과제가 함께 있습니다. "
        "선정형 R&D가 많아 사업계획서부터 보고, 구·군 공고면 그 지역 소재지를 확인하세요."
    ),
    ("metro_gun", "인력"): (
        "{r} 인력 공고는 시 고용과 구·군 채용 지원이 한 목록입니다. "
        "인건비·교육은 4대보험 가입 현황을 먼저 보는 경우가 많습니다."
    ),
    ("metro_gun", "수출"): (
        "{r} 수출 공고는 시 해외진출과 구·군 바우처가 함께 올라옵니다. "
        "예산 소진형이면 날짜보다 잔여 예산이 먼저 끊깁니다."
    ),
    ("metro_gun", "내수"): (
        "{r} 내수 공고는 시 유통 사업과 구·군 마케팅이 섞여 있습니다. "
        "입점·홍보·전시는 공고마다 방식이 다르니 제목과 소관기관을 함께 보세요."
    ),
    ("metro_gun", "창업"): (
        "{r} 창업 공고는 시 사업화와 구·군 입주·교육이 한 목록입니다. "
        "예비와 기창업은 업력 산정이 다르니 사업자등록일부터 맞춰 보세요."
    ),
    ("metro_gun", "경영"): (
        "{r} 경영 공고는 시 시설·컨설팅과 구·군 소상공인 지원이 함께 있습니다. "
        "이미 운영 중인 사업장도 문을 두드릴 수 있는 편이지만, 구·군이면 소재지가 갈립니다."
    ),
    ("metro_gun", "기타"): (
        "{r}에서 분류가 애매한 공고입니다. "
        "구·군 이름이 소관기관에 있으면 그 지역 사업장 기준으로 보면 됩니다."
    ),
    ("wide", "금융"): (
        "{r} 금융 공고는 도와 시·군이 한 목록이라 길어지기 쉽습니다. "
        "융자·보증·이차보전은 갚는 돈인지 보고, 시·군 이름이 기관에 있으면 "
        "그 지역 사업장 요건이 붙는 경우가 많습니다."
    ),
    ("wide", "기술"): (
        "{r} 기술 공고는 도 과제와 시·군 과제가 함께 있습니다. "
        "R&D는 선정형이 많아 사업계획서 완성도를 먼저 보고, 시·군 공고면 소재지를 좁히세요."
    ),
    ("wide", "인력"): (
        "{r} 인력 공고는 도 고용 사업과 시·군 채용 지원이 섞여 목록이 깁니다. "
        "인건비·교육은 고용 유지 기간을 보는 공고가 많아 인력 현황부터 챙기세요."
    ),
    ("wide", "수출"): (
        "{r} 수출 공고는 도 해외진출과 시·군 바우처가 한 목록입니다. "
        "시·군 단위 바우처는 예산이 먼저 끝나는 경우가 있으니 조건을 확인하는 대로 보세요."
    ),
    ("wide", "내수"): (
        "{r} 내수 공고는 도 판로 사업과 시·군 마케팅이 함께 올라옵니다. "
        "31개 시·군이 한 목록이라, 소관기관의 시·군 이름부터 가리는 편이 빠릅니다."
    ),
    ("wide", "창업"): (
        "{r} 창업 공고는 도 창업 센터와 시·군 사업화가 한 목록에 모입니다. "
        "업력 3년·7년 이내가 흔하고, 시·군 공고면 해당 지역 사업장 요건을 원문에서 보세요."
    ),
    ("wide", "경영"): (
        "{r} 경영 공고는 도 컨설팅·시설과 시·군 소상공인 지원이 함께 있어 목록이 깁니다. "
        "시·군 이름이 소관기관에 있으면 그 지역 가게·사업장 기준입니다."
    ),
    ("wide", "기타"): (
        "{r}에서 여덟 분야에 넣기 어려운 공고입니다. "
        "시·군이 많아 제목과 소관기관만 보고 업종·소재지가 맞는지를 가리시면 됩니다."
    ),
    ("do", "금융"): (
        "{r} 금융 공고는 도와 시·군이 한 목록입니다. "
        "융자·보증은 갚아야 하는 자금인지 먼저 보고, 시·군 공고면 그 지역 사업장 요건을 확인하세요."
    ),
    ("do", "기술"): (
        "{r} 기술 공고는 도 과제와 시·군 과제가 섞여 있습니다. "
        "선정형 R&D가 많아 신청 전에 사업계획서부터 준비하는 편이 유리합니다."
    ),
    ("do", "인력"): (
        "{r} 인력 공고는 도 고용과 시·군 채용·교육이 함께 있습니다. "
        "4대보험 가입 이력을 미리 확인해 두면 서류 준비가 빨라집니다."
    ),
    ("do", "수출"): (
        "{r} 수출 공고는 도 해외진출과 시·군 전시·바우처가 한 목록입니다. "
        "예산 소진형이면 날짜형보다 먼저 닫힐 수 있습니다."
    ),
    ("do", "내수"): (
        "{r} 내수 공고는 도 유통 사업과 시·군 마케팅이 섞여 있습니다. "
        "대상 지역이 도 전체가 아니라 특정 시·군일 수 있으니 원문을 한 번 더 보세요."
    ),
    ("do", "창업"): (
        "{r} 창업 공고는 도 사업화와 시·군 입주·교육이 함께 올라옵니다. "
        "예비와 기창업은 업력 산정이 다르니 사업자등록일을 기준으로 보세요."
    ),
    ("do", "경영"): (
        "{r} 경영 공고는 도 시설·컨설팅과 시·군 소상공인 지원이 한 목록입니다. "
        "소관기관이 시·군이면 해당 지역 사업장 기준으로 좁혀집니다."
    ),
    ("do", "기타"): (
        "{r}에서 분류가 애매한 공고입니다. "
        "소관기관과 공고문 대상 지역이 일치하는지만 보면 됩니다."
    ),
    ("city", "금융"): (
        "{r} 금융 공고는 시 단위가 중심입니다. "
        "융자·보증·이차보전은 갚는 돈인지 구분하고, 소재지 제한이 없으면 전국 목록도 함께 보세요."
    ),
    ("city", "기술"): (
        "{r} 기술 공고는 시 단위 R&D·기술개발이 중심입니다. "
        "선정형이 많아 사업계획서를 먼저 보는 편이 낫습니다."
    ),
    ("city", "인력"): (
        "{r} 인력 공고는 시 단위 채용·인건비·교육이 중심입니다. "
        "고용 유지 기간과 4대보험 서류를 먼저 챙기세요."
    ),
    ("city", "수출"): (
        "{r} 수출 공고는 시 단위 해외진출·바우처가 중심입니다. "
        "예산 소진형이면 조건을 확인하는 대로 접수하는 쪽이 유리합니다."
    ),
    ("city", "내수"): (
        "{r} 내수 공고는 시 단위 판로·마케팅이 중심입니다. "
        "소재지 제한이 없는 국내 판로 사업은 전국 페이지에도 있습니다."
    ),
    ("city", "창업"): (
        "{r} 창업 공고는 시 단위 사업화·입주가 중심입니다. "
        "업력은 사업자등록일 기준인 경우가 많습니다."
    ),
    ("city", "경영"): (
        "{r} 경영 공고는 시 단위 컨설팅·시설이 중심입니다. "
        "이미 운영 중인 사업장도 신청을 검토할 수 있는 편이지만 원문 대상을 확인하세요."
    ),
    ("city", "기타"): (
        "{r}에서 여덟 분야에 넣기 어려운 시 단위 공고입니다. "
        "제목과 지원대상을 보고 해당 여부만 가리시면 됩니다."
    ),
    ("island", "금융"): (
        "{r} 금융 공고는 도 단위가 많은 편입니다. "
        "융자·보증은 갚는 돈인지 보고, 소재지 제한이 없는 자금은 전국 목록에서 따로 확인할 수 있습니다."
    ),
    ("island", "기술"): (
        "{r} 기술 공고는 도 단위 R&D가 중심입니다. "
        "선정형이면 사업계획서 완성도가 결과를 가릅니다."
    ),
    ("island", "인력"): (
        "{r} 인력 공고는 도 단위 채용·교육이 많은 편입니다. "
        "4대보험 가입 현황을 먼저 보면 서류가 빨라집니다."
    ),
    ("island", "수출"): (
        "{r} 수출 공고는 도 단위 해외진출·전시가 중심입니다. "
        "섬 지역 물류·전시 일정이 원문에 따로 적혀 있는 경우가 있으니 접수 전에 보세요."
    ),
    ("island", "내수"): (
        "{r} 내수 공고는 도 단위 판로·관광 연계 마케팅이 섞여 있습니다. "
        "소재지 제한이 없는 국내 판로 사업은 전국 페이지에도 있습니다."
    ),
    ("island", "창업"): (
        "{r} 창업 공고는 도 단위 사업화·입주가 중심입니다. "
        "예비와 기창업 구분은 사업자등록일부터 보시면 됩니다."
    ),
    ("island", "경영"): (
        "{r} 경영 공고는 도 단위 컨설팅·시설이 많은 편입니다. "
        "이미 운영 중인 사업장 대상이면 업력보다 소재지·체납부터 보세요."
    ),
    ("island", "기타"): (
        "{r}에서 분류가 애매한 도 단위 공고입니다. "
        "제목과 소관기관을 보고 업종이 맞는지만 가리시면 됩니다."
    ),
    ("united", "금융"): (
        "전남광주통합특별시 금융 공고는 광주와 전남을 나누지 않습니다. "
        "융자·보증·이차보전은 갚는 돈인지 보고, 예전에 광역시·도로 찾던 공고도 이 목록에 있습니다."
    ),
    ("united", "기술"): (
        "전남광주통합특별시 기술 공고는 광주와 전남을 한 단위로 둡니다. "
        "R&D·기술개발은 선정형이 많아 사업계획서를 먼저 보세요."
    ),
    ("united", "인력"): (
        "전남광주통합특별시 인력 공고는 광주와 전남을 따로 나누지 않습니다. "
        "채용·인건비·교육은 4대보험 서류를 먼저 챙기는 편이 낫습니다."
    ),
    ("united", "수출"): (
        "전남광주통합특별시 수출 공고는 광주와 전남을 한 목록으로 둡니다. "
        "해외진출·바우처는 예산 소진형이 섞여 있어 조건을 확인하는 대로 접수하는 쪽이 유리합니다."
    ),
    ("united", "내수"): (
        "전남광주통합특별시 내수 공고는 광주와 전남을 나누지 않습니다. "
        "판로·마케팅은 바우처형과 선정형이 함께 있으니 제목의 표현을 먼저 보세요."
    ),
    ("united", "창업"): (
        "전남광주통합특별시 창업 공고는 광주와 전남을 한 단위로 묶습니다. "
        "예전에 광주광역시나 전라남도로 찾던 사업화도 이 목록에서 보시면 됩니다."
    ),
    ("united", "경영"): (
        "전남광주통합특별시 경영 공고는 광주와 전남을 따로 나누지 않습니다. "
        "컨설팅·시설은 이미 운영 중인 소상공인도 문을 두드릴 수 있는 편입니다."
    ),
    ("united", "기타"): (
        "전남광주통합특별시에서 여덟 분야에 넣기 어려운 공고입니다. "
        "광주와 전남을 나누지 않으니, 예전에 광역시·도로 찾던 공고도 여기 있습니다."
    ),
    ("nation", "금융"): (
        "사업장 소재지 제한이 없는 금융 공고만 모았습니다. "
        "융자·보증·이차보전은 갚는 돈인지 구분하고, 특정 시·도 자금은 해당 지역 페이지에 있습니다."
    ),
    ("nation", "기술"): (
        "사업장 소재지 제한이 없는 기술 공고만 모았습니다. "
        "R&D는 선정형이 많아 사업계획서부터 보고, 지역 한정 과제는 시·도 페이지에서 보세요."
    ),
    ("nation", "인력"): (
        "사업장 소재지 제한이 없는 인력 공고만 모았습니다. "
        "채용·인건비·교육은 4대보험 현황을 먼저 보고, 시·도 고용 사업은 지역 페이지에 있습니다."
    ),
    ("nation", "수출"): (
        "사업장 소재지 제한이 없는 수출 공고만 모았습니다. "
        "해외진출·바우처는 예산 소진형이 섞여 있고, 지역 한정 전시는 해당 시·도에 있습니다."
    ),
    ("nation", "내수"): (
        "사업장 소재지 제한이 없는 내수 공고만 모았습니다. "
        "판로·마케팅은 전국 어디서나 요건만 맞으면 검토할 수 있고, 지역 한정은 시·도 페이지에 있습니다."
    ),
    ("nation", "창업"): (
        "사업장 소재지 제한이 없는 창업 공고만 모았습니다. "
        "예비·초기 사업화는 업력부터 가리고, 시·도 창업 센터 사업은 지역 페이지에 있습니다."
    ),
    ("nation", "경영"): (
        "사업장 소재지 제한이 없는 경영 공고만 모았습니다. "
        "컨설팅·시설은 전국 사업장 대상이고, 구·군 소상공인 지원은 해당 지역 페이지에 있습니다."
    ),
    ("nation", "기타"): (
        "사업장 소재지 제한이 없는, 여덟 분야에 넣기 어려운 공고만 모았습니다. "
        "특정 시·도에만 열리는 사업은 해당 지역 페이지에서 확인하세요."
    ),
}

# 규칙기반 fallback 한 줄. 카드에 반복되면 오히려 약해 보여서 생략한다.
# enrich._fallback()의 문장 전체("OO가 OO 지역 OO를 대상으로 진행하는
# OO 분야 지원사업입니다.")를 처음부터 지워야 한다. "대상으로 진행하는
# ... 지원사업입니다" 부분만 지우면 앞의 "OO가 OO 지역 OO를 " 조각이
# 그대로 남아 "산업통상부가 전국 지역 중소기업을 ." 처럼 잘린 문구가
# 카드에 노출되는 버그가 있었다 — 문장 시작(^)부터 통째로 매칭한다.
_GENERIC_BLURB = re.compile(
    r"^.+?(?:이|가) .+? 지역 .+?(?:을|를) 대상으로 진행하는 .+? 분야 지원사업입니다\.?\s*"
)


def _orgs(items):
    seen, out = set(), []
    for a in items:
        o = (a.get("org") or "").strip()
        if o and o not in seen:
            seen.add(o)
            out.append(o)
    out.sort()
    return out


def _org_sentence(orgs):
    if not orgs:
        return "소관기관은 공고마다 다르니 목록의 기관명을 확인하세요."
    shown = orgs[:3]
    names = ", ".join(shown)
    if len(orgs) > 3:
        return f"소관기관은 {names} 등 {len(orgs)}곳입니다."
    if len(shown) == 1:
        return f"소관기관은 {shown[0]}입니다."
    return f"소관기관은 {names}입니다."


def _always_raws(always):
    raws = []
    for a in always:
        r = (a.get("period_raw") or "상시 접수").strip()
        if r and r not in raws:
            raws.append(r)
    return raws


def _quote_title(title):
    t = h((title or "").strip())
    return f"「{t}」" if t else ""


def _always_guide_html():
    href, name = ALWAYS_GUIDE
    return f'<a href="{h(href)}">{h(name)}</a>'


def _guide_pair_html(href, name, has_batchim, no_batchim):
    """링크 뒤에 붙는 조사는 앵커가 아니라 평문 제목 받침으로 고른다."""
    return f'<a href="{h(href)}">{h(name)}</a>{_josa(name, has_batchim, no_batchim)}'


def _workplace_guide_link():
    href, name = CATEGORY_GUIDE["기타"]
    return f'<a href="{h(href)}">{h(name)}</a>'


def _workplace_guide_html(has_batchim="을", no_batchim="를"):
    href, name = CATEGORY_GUIDE["기타"]
    return _guide_pair_html(href, name, has_batchim, no_batchim)


def _iro(word):
    return _josa((word or "").strip() or "상시 접수", "으로", "로")


def _always_cta(always, style, short=False, label=""):
    """상시 건수가 있을 때만 쓴다. 문장 골격을 style로 갈라 복붙을 줄인다."""
    n = len(always or [])
    if not n:
        return ""
    raws = _always_raws(always)
    last = raws[-1] if raws else "상시 접수"
    shown = ", ".join(f"'{h(x)}'" for x in raws[:2]) or "'상시 접수'"
    raw0 = f"'{h(raws[0])}'" if raws else "'상시 접수'"
    ghtml = _always_guide_html()
    geul = _josa(ALWAYS_GUIDE[1], "을", "를")
    cat = f"{h(label)} 목록의 " if label else ""
    style = int(style) % 5
    if short:
        variants = (
            f"{cat}상시 {n}건은 예산이 끝나면 닫힙니다.",
            f"{cat}날짜 없는 접수가 {n}건입니다.",
            f"{cat}상시 {n}건 원문은 {raw0}입니다.",
            f"{cat}상시 {n}건은 목록 하단에 있고 마감일이 없습니다.",
            f"{cat}상시 {n}건은 {shown}{_iro(last)} 적혀 있습니다.",
        )
        return variants[style]
    variants = (
        f"{cat}상시 접수는 {n}건입니다. 원문에는 {shown}{_iro(last)} 적혀 있고, "
        f"예산이 먼저 끊길 수 있어 {ghtml}{geul} 참고하세요.",
        f"{cat}날짜 없는 접수가 {n}건입니다. 원문 표기는 {raw0}입니다.",
        f"{cat}상시 {n}건은 목록 하단입니다. {ghtml}{geul} 보면 예산 소진형을 구분할 수 있습니다.",
        f"{cat}상시 {n}건은 마감일이 없고 원문은 {raw0}입니다.",
        f"{cat}날짜 없는 상시 {n}건은 예산이 끝나면 닫힙니다. 원문에는 {shown}{_iro(last)} 적혀 있습니다.",
    )
    return variants[style]


def _deadline_focus(today_n, urgent_n, dated_n, always_n):
    if today_n and not always_n and urgent_n <= today_n:
        return "today_only"
    if always_n and always_n >= max(dated_n, urgent_n, 1):
        return "always_heavy"
    if urgent_n == 0 and dated_n:
        return "quiet_week"
    if today_n:
        return "today_mix"
    if urgent_n:
        return "week"
    if always_n:
        return "always_only"
    return "empty"


def _deadline_para(urgent, open_dated, always, skip_nearest=False, skip_always=False,
                   style=0, orgs=None, compact=False, label=""):
    """
    오늘/이번 주/상시 비중에 따라 짧은 문장을 고른다. 상시 0건이면
    상시 가이드 CTA를 넣지 않고, 상시가 있어도 문장을 style로 가른다.
    compact면 앞 문단이 이미 건수를 말했으니 숫자를 되풀이하지 않는다.
    """
    urgent = urgent or []
    open_dated = open_dated or []
    always = always or []
    today_n = sum(1 for a in urgent if a.get("dday") == 0)
    urgent_n = len(urgent)
    dated_n = len(open_dated)
    always_n = len(always)
    style = int(style) % 5
    focus = _deadline_focus(today_n, urgent_n, dated_n, always_n)
    bits = []

    nearest = None
    if urgent:
        nearest = min(urgent, key=lambda a: (a.get("dday"), a.get("apply_end") or ""))
    elif open_dated:
        nearest = min(open_dated, key=lambda a: (a.get("dday"), a.get("apply_end") or ""))
    qtitle = "" if skip_nearest or not nearest else _quote_title(nearest.get("title"))
    end = "" if skip_nearest or not nearest else h((nearest or {}).get("apply_end") or "")

    # 앞 문단이 오늘/이번 주/상시 건수를 이미 말했으면 같은 숫자를 반복하지 않는다.
    if compact:
        if always and not skip_always:
            bits.append(_always_cta(always, style, short=style in (1, 3, 4), label=label))
        elif always and skip_always:
            bits.append(_always_cta(always, style, short=True, label=label))
        return " ".join(b for b in bits if b)

    if focus == "today_only":
        today_only = (
            f"오늘 마감만 {today_n}건입니다." + (f" {qtitle}" if qtitle and today_n == 1 else ""),
            f"접수가 오늘 끝나는 공고는 {today_n}건입니다.",
            f"오늘까지인 접수가 {today_n}건입니다.",
            f"이번 주가 아니라 오늘 마감이 {today_n}건입니다.",
            f"오늘 닫히는 접수는 {today_n}건입니다.",
        )
        bits.append(today_only[style].strip())
    elif focus in ("today_mix",) or today_n:
        if style == 0 and qtitle and today_n == 1:
            bits.append(f"오늘 마감은 {qtitle}입니다.")
        elif style == 1:
            bits.append(f"오늘까지 접수하는 공고가 {today_n}건입니다.")
        elif style == 2:
            bits.append(f"접수가 오늘 끝나는 공고는 {today_n}건입니다.")
        elif style == 3 and qtitle:
            bits.append(f"오늘 닫히는 공고가 {today_n}건입니다." + (
                f" 하나는 {qtitle}입니다." if today_n > 1 else f" {qtitle}"))
        else:
            extra = f" {qtitle}" if qtitle and today_n == 1 else ""
            bits.append(f"오늘 마감 {today_n}건입니다.{extra}")
        if urgent_n > today_n:
            bits.append(
                f"이번 주 마감은 모두 {urgent_n}건입니다." if style % 2 == 0
                else f"이번 주 안으로 끝나는 접수는 {urgent_n}건입니다."
            )
    elif focus == "week" or urgent_n:
        if style in (0, 4) and qtitle and end:
            bits.append(f"가장 가까운 마감은 {end}의 {qtitle}입니다.")
            if style == 0:
                bits.append(f"이번 주 마감은 {urgent_n}건입니다.")
        elif style == 1 and end:
            bits.append(f"이번 주 마감 {urgent_n}건 중 가장 가까운 날짜는 {end}입니다.")
        elif style == 2:
            bits.append(f"이번 주 안에 접수가 끝나는 공고는 {urgent_n}건입니다.")
        elif style == 3 and qtitle:
            bits.append(f"일주일 안 마감 {urgent_n}건입니다. 가까운 것은 {qtitle}입니다.")
        else:
            bits.append(f"일주일 안 마감 {urgent_n}건입니다.")
    elif focus == "quiet_week" or dated_n:
        quiet = (
            f"일주일 안 마감은 없고, 날짜가 남은 공고는 {dated_n}건입니다.",
            f"이번 주 마감은 없습니다. 날짜형 접수는 {dated_n}건입니다.",
            f"급한 마감은 없고 날짜가 남은 공고가 {dated_n}건입니다.",
            f"일주일 안 마감은 없습니다. 남은 날짜형은 {dated_n}건입니다.",
            f"이번 주 안에 닫히는 공고는 없고 날짜형은 {dated_n}건입니다.",
        )
        if skip_nearest:
            bits.append(quiet[style])
        elif end and qtitle:
            titled = (
                f"일주일 안 마감은 없고, 가장 가까운 마감일은 {end}의 {qtitle}입니다.",
                f"이번 주 안에 닫히는 공고는 없습니다. 다음 마감은 {end} {qtitle}입니다.",
                f"가장 가까운 날짜형 마감은 {end}입니다. {qtitle}",
                f"급한 마감은 없습니다. {end}의 {qtitle}"
                f"{_josa((nearest or {}).get('title') or '', '이', '가')} 가장 가깝습니다.",
                f"일주일 안 마감은 없고 다음 날짜는 {end}입니다.",
            )
            bits.append(titled[style])
        elif end:
            bits.append(f"가장 가까운 마감일은 {end}입니다.")
        else:
            bits.append(quiet[style])

    if always:
        org0 = ((orgs or [""])[0] or "").strip()
        short = skip_always or focus == "always_heavy" and style in (1, 4) or style in (1, 3)
        if focus == "always_heavy" and not skip_always and style == 2 and org0:
            bits.append(
                f"{h(org0)} 소관 쪽 상시가 {always_n}건입니다. "
                + _always_cta(always, style, short=True, label=label)
            )
        else:
            bits.append(_always_cta(always, style, short=bool(short), label=label))

    if not bits:
        quiet = (
            "지금 접수 기간이 남은 공고가 거의 없으니, 목록의 마감 표시를 기준으로 보세요.",
            "날짜가 남은 공고가 거의 없습니다. 카드의 마감 표시를 보세요.",
            "지금 열린 접수가 거의 없습니다.",
            "목록의 마감 표시를 기준으로 남은 기간을 보시면 됩니다.",
            "접수 중인 날짜가 거의 없습니다.",
        )
        bits.append(quiet[style])
    return " ".join(b for b in bits if b)


def _layout_id(seed):
    """짧은 한글 씨드에서 충돌이 덜 나게 FNV-1a로 버킷을 고른다."""
    hval = 2166136261
    for ch in (seed or ""):
        hval ^= ord(ch)
        hval = (hval * 16777619) & 0xFFFFFFFF
    return int(hval % 5)


def _item_facts(items):
    items = items or []
    dated = [a for a in items if a.get("period_type") != "always"]
    always = [a for a in items if a.get("period_type") == "always"]
    open_dated = [a for a in dated if a.get("dday", -1) >= 0]
    urgent = [a for a in open_dated if a.get("dday", 99) <= 7]
    today = [a for a in urgent if a.get("dday") == 0]
    cats, seen_c = [], set()
    targets, seen_t = [], set()
    for a in items:
        c = (a.get("category") or "").strip()
        if c and c not in seen_c:
            seen_c.add(c)
            cats.append(c)
        t = (a.get("target") or "").strip()
        if t and t not in seen_t:
            seen_t.add(t)
            targets.append(t)
    nearest = None
    pool = urgent or open_dated
    if pool:
        nearest = min(pool, key=lambda a: (a.get("dday"), a.get("apply_end") or ""))
    return {
        "n": len(items),
        "dated": dated,
        "always": always,
        "open_dated": open_dated,
        "urgent": urgent,
        "today": today,
        "orgs": _orgs(items),
        "cats": cats,
        "targets": targets,
        "nearest": nearest,
    }


def _region_label(region):
    if region == "전남광주":
        return "전남광주통합특별시"
    return region


def _scope_short(region):
    if region == "전국":
        return "전국에서 신청할 수 있는, 사업장 소재지 제한이 없는 공고입니다."
    if region == "전남광주":
        return "전남광주통합특별시 단위이며, 광주와 전남을 따로 나누지 않습니다."
    return f"{h(region)} 사업장 소재지 기준입니다."


# 지역명만 바꿔 끼운 문장이 되지 않게, 행정 습관을 지역마다 다르게 적는다.
REGION_HOOK = {
    "서울": "구청 이름이 소관기관에 있으면 서울시 전체가 아니라 그 자치구 사업장 기준입니다.",
    "부산": "구·군청이 올린 공고와 시 공고를 소관기관 이름으로 먼저 나누면 됩니다.",
    "대구": "구청 공고는 광역시 전역이 아니라 해당 구로 읽으면 됩니다.",
    "인천": "구·군 이름이 기관명에 있으면 원문의 대상 지역이 그 구·군인지 맞춰 보세요.",
    "대전": "광역시와 구청을 소관기관에서 구별하면 시 전체인지 구 단위인지 바로 보입니다.",
    "울산": "목록의 기관명이 시인지 구·군인지만 봐도 신청 범위가 갈립니다.",
    "세종": "시 단위 공고가 중심이라, 소재지 제한이 없으면 전국 목록도 같이 보면 됩니다.",
    "경기": "시·군 이름이 소관기관에 붙은 공고가 많아, 도 전체로 읽으면 범위를 넓히게 됩니다.",
    "강원": "시·군청 공고는 도 전체가 아니라 그 시·군 사업장 요건을 원문에서 보면 됩니다.",
    "충북": "대상 지역이 도인지 특정 시·군인지는 공고문 한 줄이 소관기관보다 정확합니다.",
    "충남": "도 공고와 시·군 공고가 섞여 있어 기관명으로 범위를 가르는 편이 빠릅니다.",
    "전북": "소관기관과 원문 대상 지역이 같은지만 보면 시·군 제한을 놓치지 않습니다.",
    "전남광주": "광주와 전남을 나누지 않는 통합 단위라, 예전에 광역시·도로 찾던 공고도 여기 있습니다.",
    "경북": "짧게 적힌 대상 지역도 원문에는 특정 시·군 조건이 있는 경우가 있습니다.",
    "경남": "소관기관이 시·군이면 도 전체가 아니라 그 지역 사업장 기준입니다.",
    "제주": "도 단위 공고가 많고, 소재지 제한이 없는 사업은 전국 페이지에 따로 있습니다.",
    "전국": "전국 단위로, 시·도 제한이 없는 공고만 있습니다. 지역 한정 사업은 각 시·도 페이지로 가세요.",
}


def _combo_weave(region, category):
    group = _REGION_GROUP.get(region, "do")
    tmpl = _COMBO_WEAVE.get((group, category))
    if tmpl:
        return tmpl.format(r=h(_region_label(region)))
    return (
        f"{_scope_short(region)} {h(category)} 공고만 이 페이지에 있습니다. "
        "업력·매출·체납 요건은 공고마다 다르니 원문을 확인하세요."
    )


def _region_hook(region):
    return REGION_HOOK.get(region) or _scope_short(region)


def _guide_anchor(category):
    href, gname = CATEGORY_GUIDE.get(category, ("/guide/aply-trgt-check/", "신청 자격 확인"))
    return f'<a href="{h(href)}">{h(gname)}</a>', gname


def _guide_html(category):
    link, gname = _guide_anchor(category)
    return f"{link}{_josa(gname, '을', '를')}"


def _count_lead(region, category, facts, style):
    n = facts["n"]
    cat = h(category)
    if style == 0:
        return f"{_where(region)} {cat} 지원사업은 {n}건입니다."
    if style == 1:
        return f"이 목록의 {cat} 공고는 {n}건입니다. {_scope_short(region)}"
    if style == 2:
        return f"{_scope_short(region)} {cat}만 보면 지금 {n}건입니다."
    if style == 3:
        return f"{h(_region_label(region))} {cat} 지원사업은 {n}건입니다. 마감이 가까운 순입니다."
    return f"{cat} 분야만 모아 {n}건입니다. {_scope_short(region)}"


def _mix_sentence(facts, style=0):
    u, a, o = len(facts["urgent"]), len(facts["always"]), len(facts["open_dated"])
    bits = []
    if facts["today"]:
        bits.append(f"오늘 마감 {len(facts['today'])}건")
    if u:
        bits.append(f"이번 주 마감 {u}건")
    elif o:
        bits.append(f"날짜가 남은 공고 {o}건")
    if a:
        bits.append(f"상시 접수 {a}건")
    if not bits:
        quiet = (
            "지금 접수 기간이 남은 공고가 거의 없습니다.",
            "날짜가 남은 접수가 거의 없습니다.",
            "지금 열린 접수가 거의 없습니다.",
            "접수 기간이 남은 공고가 거의 없습니다.",
            "마감이 남은 건이 거의 없습니다.",
        )
        return quiet[int(style) % 5]
    joined = ", ".join(bits)
    dotted = " · ".join(bits)
    style = int(style) % 5
    if style == 0:
        return f"이 페이지에는 {joined}이 있습니다."
    if style == 1:
        return f"지금 {dotted}입니다."
    if style == 2:
        return f"목록 기준으로 {joined}입니다."
    if style == 3:
        if len(bits) == 1:
            return f"{bits[0]}입니다."
        return f"{bits[0]}이고, {', '.join(bits[1:])}입니다."
    return f"접수 상태는 {joined}입니다."


def _org_lead(facts):
    return _org_sentence(facts["orgs"])


def _title_lead(facts):
    nearest = facts.get("nearest")
    if not nearest:
        if facts["always"]:
            raws = _always_raws(facts["always"])
            shown = ", ".join(f"'{h(x)}'" for x in raws[:2]) or "'상시 접수'"
            return (
                f"날짜 없는 상시 접수가 {len(facts['always'])}건 있고, "
                f"원문에는 {shown}처럼 적혀 있습니다."
            )
        return ""
    qtitle = _quote_title(nearest.get("title"))
    end = h(nearest.get("apply_end") or "")
    if nearest.get("dday") == 0 and qtitle:
        return f"오늘 마감 중 하나는 {qtitle}입니다."
    if qtitle and end:
        return f"가장 가까운 마감은 {end}의 {qtitle}입니다."
    if end:
        return f"가장 가까운 마감일은 {end}입니다."
    return ""


def _scope_who(region):
    if region == "전국":
        return "사업장 소재지 제한이 없는 공고입니다."
    if region == "전남광주":
        return "전남광주통합특별시 사업장 기준이며, 광주와 전남을 따로 나누지 않습니다."
    return f"{region} 사업장 소재지 기준 공고입니다."


def _target_sentence(facts):
    targets = facts.get("targets") or []
    if not targets:
        return "지원대상 표기는 공고마다 다르니 각 카드와 원문을 보세요."
    if len(targets) == 1:
        return f"이 목록의 지원대상 표기는 '{targets[0]}'입니다."
    shown = ", ".join(f"'{x}'" for x in targets[:4])
    extra = f" 등 {len(targets)}종" if len(targets) > 4 else ""
    return f"이 목록의 지원대상 표기는 {shown}{extra}입니다."


def _who_answer(region, category, cat_desc, facts=None):
    facts = facts or {"orgs": [], "cats": [], "targets": []}
    return (
        f"{_scope_who(region)} {_target_sentence(facts)} "
        f"{cat_desc} 성격의 공고입니다. "
        f"{_org_sentence(facts.get('orgs') or [])} "
        "업력·매출·체납·중복지원은 공고마다 다르니 원문을 확인하세요."
    )


def _deadline_answer(urgent, open_dated, always, always_n, urgent_n):
    bits = []
    if urgent_n:
        bits.append(f"이번 주 마감은 {urgent_n}건입니다.")
    if open_dated and not urgent:
        nearest = min(open_dated, key=lambda a: (a.get("dday"), a.get("apply_end") or ""))
        end = nearest.get("apply_end") or ""
        if end:
            bits.append(f"날짜가 있는 공고 중 가장 가까운 마감일은 {end}입니다.")
    if always:
        raws = _always_raws(always)
        shown = ", ".join(f"'{x}'" for x in raws[:2]) or "'상시 접수'"
        bits.append(
            f"상시 접수는 {always_n}건이고, 원문에는 {shown}처럼 적혀 있습니다. "
            f"예산이 소진되면 날짜 전에 닫히는 경우가 많습니다."
        )
    if not bits:
        bits.append("지금 날짜가 남은 공고가 거의 없습니다.")
    bits.append("정확한 기간은 각 공고 상세의 접수기간과 원문을 보면 됩니다.")
    return " ".join(bits)


def _apply_answer(orgs):
    if not orgs:
        return "소관기관은 공고마다 다릅니다. 각 상세페이지의 원문 링크로 접수하세요."
    if len(orgs) == 1:
        return (
            f"이 목록의 소관기관은 {orgs[0]}입니다. "
            f"접수는 각 공고 상세의 신청방법과 원문 링크로 {orgs[0]}에 하면 됩니다."
        )
    names = ", ".join(orgs[:3])
    tail = f" 등 {len(orgs)}곳" if len(orgs) > 3 else ""
    return (
        f"소관기관은 {names}{tail}입니다. "
        "신청 창구가 기관마다 다르니 해당 공고 상세의 원문으로 들어가세요."
    )


def _where(region):
    if region == "전국":
        return "전국에서 신청할 수 있는"
    if region == "전남광주":
        return "전남광주통합특별시에서 지금 접수 중이거나 최근 마감된"
    return f"{h(region)}에서 지금 접수 중이거나 최근 마감된"


def _shape(facts):
    n = max(facts["n"], 1)
    if facts["today"]:
        return "today"
    if facts["always"] and len(facts["always"]) * 2 >= n and len(facts["always"]) > len(facts["urgent"]):
        return "always"
    if len(facts["urgent"]) >= 3:
        return "urgent"
    if len(facts["orgs"]) == 1:
        return "one_org"
    return "balanced"


def _split_sents(text):
    text = re.sub(r"\s+", " ", text or "").strip()
    if not text:
        return []
    return [p.strip() for p in re.split(r"(?<=다\.)\s+", text) if p.strip()]


def _pack_paras(sentences, max_paras=4):
    """문장을 중복 없이 2~4문단으로 묶는다. 통합 단위 안내가 두 번 나오지 않게 한다."""
    seen, uniq = set(), []
    united_used = False
    for s in sentences:
        for part in _split_sents(s):
            key = re.sub(r"\s+", " ", part)
            if key in seen or len(key) < 8:
                continue
            if "광주와 전남" in key:
                if united_used:
                    continue
                united_used = True
            seen.add(key)
            uniq.append(part)
    if not uniq:
        return []
    if len(uniq) <= 3:
        return [" ".join(uniq)] if len(uniq) == 1 else [
            uniq[0], " ".join(uniq[1:])
        ][:max_paras]
    # 앞·중간·마감·다음 행동으로 나눈다.
    n = len(uniq)
    cuts = [1, max(2, n // 2), max(3, n - 1), n]
    paras, start = [], 0
    for cut in cuts:
        chunk = uniq[start:cut]
        if chunk:
            paras.append(" ".join(chunk))
        start = cut
        if len(paras) >= max_paras:
            break
    if start < n and paras:
        paras[-1] = paras[-1] + " " + " ".join(uniq[start:])
    return paras[:max_paras]


def _next_step(category, facts):
    """가이드 제목의 받침으로 조사를 붙인다. 링크 뒤에 를/을을 하드코딩하지 않는다."""
    link, gname = _guide_anchor(category)
    eul = _josa(gname, "을", "를")
    if category == "금융":
        return f"제목에 융자·보증·이차보전이 있으면 갚는 돈이니 {link}부터 보시면 됩니다."
    if category == "기술":
        return f"선정형 R&D면 사업계획서 완성도가 결과를 가르니 {link}{eul} 보면 됩니다."
    if category == "인력":
        return f"인건비·채용 공고는 4대보험 서류를 먼저 챙기고, 발급처는 {link}에 있습니다."
    if category == "수출":
        return f"바우처형이면 예산이 날짜보다 먼저 끊기니 {link}{eul} 함께 보세요."
    if category in ("내수", "경영"):
        return f"이미 운영 중인 사업장이면 {link} 순서로 걸러 보세요."
    if category == "창업":
        return f"예비와 기창업은 업력 산정이 다르니 {link}에서 트랙을 가리세요."
    return f"제목과 지원대상이 맞는지 가린 뒤 {link}{eul} 보시면 됩니다."


def _combo_paras(region, category, cat, facts):
    """
    페이지에 보이는 건수·기관·마감·대상만 쓰고, 조합마다 문장 순서를 바꾼다.
    같은 문장을 두 문단에 반복하지 않는다.
    """
    n = facts["n"]
    layout = _layout_id(f"{region}|{category}")
    shape = _shape(facts)
    desc = h((cat or {}).get("desc") or f"{category} 지원")
    weave = _combo_weave(region, category)
    hook = _region_hook(region)
    titled = _title_lead(facts)
    used_title = bool(titled)
    orgs = _org_sentence(facts["orgs"])
    mix = _mix_sentence(facts, layout)
    count = _count_lead(region, category, facts, layout)
    nxt = _next_step(category, facts)
    tgt = _target_sentence(facts)

    # 오늘 마감이 있어도 레이아웃마다 첫 문장을 다르게 둔다.
    if layout == 0:
        open_s = f"{count} {desc}입니다. {mix}"
    elif layout == 1:
        open_s = f"{titled or count} {mix}"
    elif layout == 2:
        open_s = f"{orgs} {h(category)}만 보면 {n}건입니다. {_scope_short(region)}"
        orgs = ""
    elif layout == 3:
        if shape == "always":
            open_s = f"{titled or mix} {count}"
        else:
            open_s = f"{weave} {count}"
            weave = ""
    else:
        if shape == "today" and titled:
            open_s = f"{titled} {_scope_short(region)}"
        elif shape == "always":
            open_s = f"{titled or mix} {count}"
        else:
            open_s = f"{count} {mix}"

    mix_used = bool(mix) and mix in open_s
    dl_style = (_layout_id(f"{region}|{category}|dl") + layout) % 5
    deadline = _deadline_para(
        facts["urgent"], facts["open_dated"], facts["always"],
        skip_nearest=used_title,
        skip_always=used_title and not facts.get("nearest"),
        style=dl_style,
        orgs=facts["orgs"],
        compact=mix_used,
        label=category,
    )

    if layout == 0:
        mid = [hook, weave, tgt]
        tail = [deadline, orgs, nxt]
    elif layout == 1:
        mid = [weave, orgs, hook]
        tail = [deadline, nxt]
    elif layout == 2:
        mid = [weave, hook, mix if mix not in open_s else ""]
        tail = [deadline, tgt, nxt]
    elif layout == 3:
        mid = [hook, orgs, tgt]
        tail = [deadline, nxt]
    else:
        mid = [hook, titled if not used_title else "", orgs]
        tail = [weave, deadline, nxt]

    sentences = [open_s] + mid + tail
    paras = _pack_paras(sentences, max_paras=4)
    if n <= 2 and len(paras) > 3:
        # 짧은 목록도 가이드 다음 단계는 남긴다 (조사 회귀 포함).
        paras = paras[:2] + paras[-1:]
    blob = " ".join(paras)
    if region not in blob and _region_label(region) not in blob:
        if paras:
            paras[0] = f"{_scope_short(region)} {paras[0]}"
        else:
            paras = [_scope_short(region)]
        blob = " ".join(paras)
    if f"{n}건" not in blob:
        lead = f"{h(category)} 목록은 {n}건입니다."
        if paras:
            paras[0] = f"{lead} {paras[0]}"
        else:
            paras = [lead]
    return paras


def _count_answer(region, category, facts):
    n = facts["n"]
    bits = [f"{region} {category} 목록은 지금 {n}건입니다."]
    if facts["today"]:
        q = _quote_title(facts["today"][0].get("title"))
        extra = f" 그중 {q}가 있습니다." if q else ""
        bits.append(f"오늘 마감은 {len(facts['today'])}건입니다.{extra}")
    bits.append(f"이번 주 마감 {len(facts['urgent'])}건, 상시 접수 {len(facts['always'])}건입니다.")
    if facts["nearest"] and facts["nearest"].get("apply_end") and facts["nearest"].get("dday") != 0:
        bits.append(f"가장 가까운 날짜형 마감은 {facts['nearest'].get('apply_end')}입니다.")
    return " ".join(bits)


def _combo_faqs(region, category, cat, facts, label=None):
    cat_desc = (cat or {}).get("desc") or f"{category} 지원"
    style = _layout_id(f"{region}|{category}|faq")
    who_label = label or region
    count_qs = [
        f"{who_label} {category} 지원사업은 지금 몇 건인가요?",
        f"이 페이지의 {who_label} {category} 공고는 몇 건인가요?",
        f"{who_label}에서 {category} 지원사업은 지금 얼마나 열려 있나요?",
        f"{who_label} {category} 목록에는 지금 무엇이 올라가 있나요?",
    ]
    who_qs = [
        f"{who_label}에서 {category} 지원사업은 누가 신청할 수 있나요?",
        f"{who_label} {category} 공고의 신청 대상은 어떻게 보나요?",
        f"{who_label} {category} 목록은 누구를 위한 건가요?",
        f"{who_label} 사업장이면 {category} 공고를 넣을 수 있나요?",
    ]
    apply_qs = [
        "신청은 어디서 하나요?",
        "접수는 어느 기관으로 하나요?",
        "이 목록의 공고는 어디에서 신청하나요?",
        "신청 방법은 공고마다 다른가요?",
    ]
    faqs = [
        {"q": count_qs[style % 4], "a": _count_answer(region, category, facts)},
        {"q": who_qs[style % 4], "a": _who_answer(region, category, cat_desc, facts)},
        {
            "q": "마감일과 상시 접수는 어떻게 보나요?",
            "a": _deadline_answer(
                facts["urgent"], facts["open_dated"], facts["always"],
                len(facts["always"]), len(facts["urgent"]),
            ),
        },
        {"q": apply_qs[style % 4], "a": _apply_answer(facts["orgs"])},
    ]
    if facts["always"]:
        raw0 = _always_raws(facts["always"])[0] if _always_raws(facts["always"]) else "상시 접수"
        faqs.append({
            "q": "상시 접수면 천천히 신청해도 되나요?",
            "a": (
                f"그렇지 않습니다. 이 목록의 상시 공고 {len(facts['always'])}건은 날짜 대신 "
                f"'{raw0}'처럼 적혀 있고, 예산이 소진되면 조기 마감되는 경우가 많습니다. "
                f"조건을 확인하는 대로 접수하는 편이 안전합니다."
            ),
        })
    return faqs


def build(region, category, cat, items):
    """
    region×category 페이지용 소개 문단(2~4)과 화면용 FAQ.
    반환: (paragraphs_html, faqs)  faqs는 [{"q","a"}, ...]
    """
    facts = _item_facts(items)
    paras = _combo_paras(region, category, cat, facts)
    faqs = _combo_faqs(region, category, cat, facts)
    return paras, faqs


def region_hub_intro(n, n_regions):
    """지역 허브(/region/)용 소개 HTML. 칩은 위에 두고 목록은 SSR로 둔다."""
    return (
        f"<p>사업장 소재지 기준 공고 {n}건을 마감이 가까운 순으로 둡니다. "
        f"지역은 {n_regions}곳으로 나뉩니다.</p>"
        "<p>전남광주통합특별시는 광주와 전남을 한 단위로 둡니다. "
        "소재지 제한이 없는 사업은 전국에서 보시면 됩니다.</p>"
    )


HOME_GUIDES = [
    {
        "href": "/guide/find-by-deadline/",
        "name": "마감일로 지원사업 찾기",
        "desc": "오늘 마감·이번 주 마감부터 보는 순서",
    },
    {
        "href": "/guide/workplace-region/",
        "name": "지역 제한 공고 보는 법",
        "desc": "거주지 말고 사업장 소재지",
    },
    {
        "href": "/guide/deadline-alert/",
        "name": "마감일 놓치지 않는 법",
        "desc": "캘린더 구독과 상시 접수",
    },
]


def home_intro(today_n, week_n, open_n):
    """
    홈 소개 HTML. 화면에 보이는 건수만 쓴다. 없는 공고를 지어내지 않는다.
    검색엔진이 '오늘 마감'·'이번 주 마감' 문구를 JS 없이 읽게 한다.
    """
    return (
        f"<p>지금 <a href=\"/urgent/\">오늘 마감</a> {int(today_n)}건, "
        f"<a href=\"/urgent/\">이번 주 마감</a> {int(week_n)}건입니다. "
        f"접수 중인 공고 {int(open_n)}건을 마감일 순으로 둡니다. "
        "회원가입 없이 지역·분야로 좁힐 수 있습니다.</p>"
    )


def category_title(name):
    """분야 목록 title. 검색어(분야 + 마감일)를 앞에 둔다."""
    return f"{name} 지원사업 마감일 | {config.SITE['name']}"


def category_desc(name, cat):
    """분야 목록 meta. 마감일 순·회원가입 없음·지역을 명시한다."""
    extra = (cat or {}).get("desc") or f"{name} 지원"
    return (
        f"{name} 분야 정부지원사업을 마감일 순으로 정리합니다. "
        f"회원가입 없이 지역별로 오늘 마감·이번 주 마감을 확인할 수 있습니다. "
        f"{extra}."
    )


def category_hub_intro(n):
    """분야 허브(/category/)용 소개 HTML."""
    return (
        f"<p>지원 분야 8종으로 나눈 공고 {n}건입니다. 아래는 전체를 마감일 순으로 "
        "둔 목록이고, 칩을 누르면 해당 분야만 봅니다.</p>"
        "<p>창업은 예비·초기 사업화, 경영은 이미 운영 중인 소상공인 쪽이 많습니다. "
        "융자·보증은 금융에서 따로 모았습니다.</p>"
    )


def region_page_intro(region, items):
    """지역 단독 페이지 소개 문단. 없는 공고를 지어내지 않는다."""
    facts = _item_facts(items)
    n = facts["n"]
    p1 = (
        f"{_where(region)} 지원사업은 {n}건입니다. "
        "분야를 가리지 않고 마감이 가까운 순으로 두었습니다."
    )
    p2 = REGION_BLURB.get(region) or (
        f"{h(region)} 소재 사업장 기준 공고입니다. 공고문 대상 지역을 원문에서 확인하세요."
    )
    p2 = f"{p2} {h(_org_lead(facts))}"
    p3 = _deadline_para(
        facts["urgent"], facts["open_dated"], facts["always"],
        style=_layout_id(f"{region}|page"),
        orgs=facts["orgs"],
        label=region,
    )
    if facts["cats"]:
        shown = ", ".join(h(c) for c in facts["cats"][:5])
        p4 = (
            f"이 목록에 올라온 분야는 {shown}입니다. "
            f"분야를 좁히려면 아래 칩을 누르면 됩니다. "
            f"{_workplace_guide_link()}도 함께 보세요."
        )
        return [p1, p2, p3, p4]
    return [p1, p2, p3]


def _district_scope(sido, district):
    d, s = h(district), h(sido)
    if sido == "전남광주":
        return (
            f"전남광주통합특별시 공고와 전국 공고 가운데 해시태그가 '{d}'인 것만 모았습니다. "
            "광주와 전남을 따로 나누지 않습니다."
        )
    return (
        f"{s} 공고와 전국 공고 가운데 해시태그가 '{d}'인 것만 모았습니다. "
        "다른 시·도 공고는 같은 이름이 붙어 있어도 넣지 않습니다."
    )


def district_page_intro(sido, district, items):
    """시군구 허브 소개. 건수·소관기관만 쓰고 지원금·자격을 지어내지 않는다."""
    facts = _item_facts(items)
    n = facts["n"]
    d, s = h(district), h(sido)
    layout = _layout_id(f"{sido}|{district}")
    scope = _district_scope(sido, district)
    sido_note = REGION_BLURB.get(sido) or _scope_short(sido)
    mix = _mix_sentence(facts)
    orgs = h(_org_lead(facts))
    deadline = _deadline_para(
        facts["urgent"], facts["open_dated"], facts["always"],
        style=layout,
        orgs=facts["orgs"],
        label=district,
    )
    titled = _title_lead(facts)
    cats = ""
    if facts["cats"]:
        cats = f"이 목록에 보이는 분야는 {', '.join(h(c) for c in facts['cats'][:5])}입니다."
    if layout == 0:
        paras = [
            f"{s} {d} 관련 지원사업은 {n}건입니다. {scope} 마감이 가까운 순입니다.",
            f"{sido_note} {orgs}",
            deadline,
        ]
    elif layout == 1:
        paras = [
            f"{mix} {s} {d} 해시태그로 묶으면 {n}건입니다.",
            f"{scope} {orgs}",
            f"{titled} {deadline}".strip(),
        ]
    elif layout == 2:
        paras = [
            f"{s} {d}만 보면 지금 {n}건입니다. {scope}",
            f"{orgs} {mix}",
            deadline,
        ]
    else:
        paras = [
            f"{titled or mix} {s} {d} 관련 공고는 {n}건입니다.",
            f"{scope} {sido_note}",
            f"{orgs} {deadline}",
        ]
    if cats:
        paras.append(
            f"{cats} 분야를 더 좁히려면 아래 칩을 누르면 됩니다. "
            f"{_workplace_guide_link()}도 함께 보세요."
        )
    return [re.sub(r"\s+", " ", p).strip() for p in paras if p and p.strip()]


def district_combo_intro(sido, district, category, cat, items):
    """시군구×분야 소개·FAQ. 화면에 보이는 건수·기관·마감만 쓴다."""
    facts = _item_facts(items)
    n = facts["n"]
    d, s, cname = h(district), h(sido), h(category)
    cat_desc = (cat or {}).get("desc") or f"{category} 지원"
    layout = _layout_id(f"{sido}|{district}|{category}")
    weave = _combo_weave(sido, category)
    scope = _district_scope(sido, district)
    deadline = _deadline_para(
        facts["urgent"], facts["open_dated"], facts["always"],
        style=layout,
        orgs=facts["orgs"],
        label=category,
    )
    orgs = h(_org_lead(facts))
    mix = _mix_sentence(facts)
    titled = _title_lead(facts)
    guide = (
        f"신청이 처음이면 {_guide_html(category)} 먼저 보시면 됩니다. "
        f"{_workplace_guide_link()}도 함께 보세요."
    )
    if layout == 0:
        paras = [
            f"{s} {d}의 {cname} 지원사업은 {n}건입니다. {h(cat_desc)}에 해당하며, {scope}",
            f"{weave} {orgs}",
            deadline,
            guide,
        ]
    elif layout == 1:
        paras = [
            f"{mix} {s} {d} {cname}만 보면 {n}건입니다.",
            f"{scope} {orgs}",
            f"{weave} {deadline}",
            guide,
        ]
    else:
        paras = [
            f"{titled or mix} {s} {d} {cname} 공고는 {n}건입니다. {scope}",
            f"{weave} {orgs}",
            deadline,
            guide,
        ]
    if n <= 2:
        paras = paras[:3]
    paras = [re.sub(r"\s+", " ", p).strip() for p in paras if p and p.strip()]

    faqs = _combo_faqs(sido, category, cat, facts, label=district)
    faqs[1] = {
        "q": f"{district} {category} 목록에는 어떤 공고가 들어가나요?",
        "a": (
            f"{scope} {cat_desc} 성격의 공고입니다. "
            "업력·매출·체납·중복지원 요건은 공고마다 다르니, 각 공고 상세와 원문을 확인하세요."
        ),
    }
    return paras, faqs


def category_page_intro(category, cat, items):
    """분야 단독 페이지 소개 문단."""
    facts = _item_facts(items)
    n = facts["n"]
    cat_desc = (cat or {}).get("desc") or f"{category} 지원"
    cat_note = CATEGORY_BLURB.get(category) or (
        f"{h(category)}{_josa(category, '을', '를')} 공고 제목과 지원대상을 보고 해당 여부를 가리시면 됩니다."
    )
    p1 = (
        f"{h(category)} 분야 지원사업은 {n}건입니다. "
        f"{h(cat_desc)}에 해당하는 공고를 마감이 가까운 순으로 두었습니다. "
        f"{_mix_sentence(facts)}"
    )
    p2 = (
        f"{cat_note} 신청이 처음이면 {_guide_html(category)} 먼저 보시면 됩니다."
    )
    p3 = (
        f"{h(_org_lead(facts))} 지역을 좁히려면 "
        f'<a href="/region/">지역별 목록</a>과 '
        f"{_workplace_guide_html()} 보시면 됩니다."
    )
    return [p1, p2, p3]


def faq_jsonld(faqs):
    return json.dumps({
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [{
            "@type": "Question",
            "name": f["q"],
            "acceptedAnswer": {"@type": "Answer", "text": f["a"]},
        } for f in faqs],
    }, ensure_ascii=False)


def blurb_of(row):
    """카드용 한 줄. 상투구·조사 오류면 기관·요지·대상 한 줄로 대체한다."""
    s = ((row.get("ai") or {}).get("summary") or "").strip()
    if s and ("이(가)" in s or "을(를)" in s):
        s = ""
    if s and _GENERIC_BLURB.search(s):
        rest = _GENERIC_BLURB.sub("", s)
        rest = re.sub(r"지원규모는 .+ 수준입니다\.?\s*", "", rest).strip()
        s = rest if len(rest) >= 24 else ""
    if s and " · " in s[:50]:
        return s.split(" 공고문")[0].strip()[:90]
    if not s:
        s = (card_line(row) or "").strip()
    if not s:
        return ""
    if " · " in s:
        return s[:90]
    cut = s.find("다.")
    if cut >= 8:
        s = s[: cut + 2]
    if len(s) > 90:
        s = s[:89].rstrip() + "…"
    return s


def ad_plan(n, *, has_sections=False):
    """
    광고 밀도. H1 옆에는 두지 않고, 얇은 페이지에는 슬롯을 줄인다.
    슬롯 ID가 비어 있으면 템플릿이 유닛을 그리지 않는다.
    반환: (top: bool, mid_after: int, bottom: bool)
    """
    if has_sections:
        return True, 0, True
    if n < 4:
        return False, 0, False
    if n < 8:
        return True, 0, False
    if n < 14:
        return True, 0, True
    return True, 8, True


def resolve_ads(plan, site):
    """슬롯 ID가 있는 위치만 켠다. ID 없는 빈 박스를 만들지 않기 위함."""
    top, mid, bottom = plan
    slots = (site or {}).get("adsense_slots") or {}
    client = (site or {}).get("adsense_client") or ""
    if not client:
        return False, 0, False
    if top and not slots.get("list_top"):
        top = False
    if mid and not slots.get("list_mid"):
        mid = 0
    if bottom and not slots.get("list_bottom"):
        bottom = False
    return top, mid, bottom
