# -*- coding: utf-8 -*-
"""알림 신청·요금제 랜딩 카피. 결제/카카오/로그인은 아직 없다."""

INDUSTRIES = [
    "조명·전기공사",
    "인테리어·마감공사",
    "설비·기계",
    "IT·소프트웨어",
    "기타 용역",
]

HERO_H1 = "지원사업부터 입찰까지, 마감을 놓치면 수천만 원이 날아갑니다"
HERO_LEDE = "전국 지원사업·나라장터 입찰 공고를 한 곳에서, 마감일시 순으로 확인하세요."
HERO_HINT = "가입 없이 이메일 또는 카카오톡으로 마감 임박 알림을 받아보세요."
SAVE_HINT = "무료 회원은 1개, 베이직 이상은 최대 3개, 프로는 무제한 저장 가능합니다."
PRO_LOCK = "낙찰가 예측 · 경쟁강도 보기 (프로 전용)"

MID_CTA_H2 = "매번 검색하기 번거로우신가요?"
MID_CTA_LEDE = "조건을 저장해두면 새 공고가 뜰 때마다 알아서 알려드립니다."

# 화면에 그대로 쓰는 FAQ. 결제·해지는 제품 안내 문구이며, 현재는 이메일 신청만 받는다.
ALERT_FAQS = [
    {
        "q": "알림은 얼마나 정확하고 빠른가요?",
        "a": "나라장터·지원사업 공고 등록 후 최대 1시간 이내로 알림을 발송합니다.",
    },
    {
        "q": "결제는 어떻게 이루어지나요?",
        "a": "등록하신 카드로 매월 자동 결제되며, 카드 정보는 결제대행사(PG)에 안전하게 보관되어 저희는 직접 저장하지 않습니다.",
    },
    {
        "q": "환불이 가능한가요?",
        "a": "구독 시작 후 7일 이내 미사용 시 전액 환불 가능하며, 이후 해지 시 다음 결제일까지 이용 가능합니다.",
    },
    {
        "q": "언제든 해지할 수 있나요?",
        "a": "마이페이지에서 언제든 즉시 해지 가능하며, 별도 문의나 위약금이 없습니다.",
    },
]

PLAN_LEGAL = (
    "모든 플랜은 언제든 해지 가능하며, 해지 시 다음 결제일까지 이용하실 수 있습니다. "
    "결제는 신용/체크카드 자동결제로 진행되며, 등록하신 카드 정보는 결제대행사(PG)에 안전하게 보관됩니다."
)

# 결제·카카오가 아직 없어서 CTA는 이메일 신청으로 연결한다. 플랜 내용은 제품 비전.
PLANS = [
    {
        "id": "free",
        "name": "무료",
        "price": "₩0",
        "period": "월",
        "popular": False,
        "cta": "무료로 시작하기",
        "cta_href": "/#alert",
        "features": [
            "전체 입찰·지원사업 목록 열람",
            "기본 검색 및 카테고리 필터",
            "마감일 표시",
        ],
    },
    {
        "id": "basic",
        "name": "베이직",
        "price": "₩9,900",
        "period": "월",
        "popular": True,
        "badge": "가장 인기있는 플랜",
        "cta": "베이직 시작하기",
        "cta_href": "/?plan=basic#alert",
        "features": [
            "키워드 알림 3개까지 저장",
            "카카오톡 또는 이메일 알림",
            "즐겨찾기 무제한",
            "마감 D-3 사전 알림",
        ],
    },
    {
        "id": "pro",
        "name": "프로",
        "price": "₩29,000",
        "period": "월",
        "popular": False,
        "cta": "프로 시작하기",
        "cta_href": "/?plan=pro#alert",
        "features": [
            "알림 조건 무제한 저장",
            "업종별 맞춤 필터 (조명·인테리어·전기공사 등)",
            "마감 임박 우선 알림 (D-1 즉시 발송)",
            "경쟁강도·참여업체 수 표시 (추후 제공)",
            "우선 고객지원",
        ],
    },
]

PRICING_H1 = "요금제"
PRICING_LEDE = "조건을 저장해두면 새 공고가 뜰 때마다 알아서 알려드립니다."
PRICING_STATUS = (
    "유료 카드결제와 카카오톡 알림은 준비 중입니다. "
    "지금은 이메일로 알림 관심 신청을 받으며, 플랜을 고르면 신청 메일에 반영됩니다."
)


def context():
    """템플릿에 넘기는 읽기 전용 딕셔너리."""
    return {
        "industries": list(INDUSTRIES),
        "hero_h1": HERO_H1,
        "hero_lede": HERO_LEDE,
        "hero_hint": HERO_HINT,
        "save_hint": SAVE_HINT,
        "pro_lock": PRO_LOCK,
        "mid_cta_h2": MID_CTA_H2,
        "mid_cta_lede": MID_CTA_LEDE,
        "alert_faqs": list(ALERT_FAQS),
        "plan_legal": PLAN_LEGAL,
        "plans": [dict(p) for p in PLANS],
        "pricing_h1": PRICING_H1,
        "pricing_lede": PRICING_LEDE,
        "pricing_status": PRICING_STATUS,
    }
