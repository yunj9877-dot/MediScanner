"""
닥터가디언 도메인 엔티티 (데이터 구조)
======================================
클린 아키텍처 안쪽 계층: 외부 도구에 의존하지 않는 순수 데이터 구조
"""

from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class QuestionType(Enum):
    """질문 유형 분류"""
    MEDICAL = "medical"    # 의학 지식 질문 → RAG 검색
    DRUG = "drug"          # 의약품 질문 → API 직접 조회
    HYBRID = "hybrid"      # 복합 질문 → API + RAG 동시


@dataclass
class Question:
    """사용자 질문"""
    text: str
    question_type: QuestionType = QuestionType.MEDICAL
    detected_drugs: list[str] = field(default_factory=list)


@dataclass
class Document:
    """검색된 문서"""
    id: str
    text: str
    metadata: dict = field(default_factory=dict)
    score: float = 0.0
    source: str = ""          # "semantic" 또는 "bm25"
    rrf_score: float = 0.0
    found_in: list[str] = field(default_factory=list)


@dataclass
class DrugInfo:
    """e약은요 API 의약품 정보"""
    item_name: str = ""       # 제품명
    entp_name: str = ""       # 업체명
    efcy: str = ""            # 효능
    use_method: str = ""      # 사용법
    atpn_warn: str = ""       # 경고
    atpn: str = ""            # 주의사항
    intrc: str = ""           # 상호작용
    se: str = ""              # 부작용
    deposit_method: str = ""  # 보관법

    @classmethod
    def from_api(cls, data: dict) -> "DrugInfo":
        """API 응답 딕셔너리에서 DrugInfo 생성"""
        return cls(
            item_name=data.get("itemName", ""),
            entp_name=data.get("entpName", ""),
            efcy=data.get("efcyQesitm", ""),
            use_method=data.get("useMethodQesitm", ""),
            atpn_warn=data.get("atpnWarnQesitm", ""),
            atpn=data.get("atpnQesitm", ""),
            intrc=data.get("intrcQesitm", ""),
            se=data.get("seQesitm", ""),
            deposit_method=data.get("depositMethodQesitm", ""),
        )


@dataclass
class DURInfo:
    """DUR 병용금기 정보"""
    mixture_item_name: str = ""  # 병용금기 약물명
    prohbt_content: str = ""     # 금기 내용
    remark: str = ""             # 사유

    @classmethod
    def from_api(cls, data: dict) -> "DURInfo":
        return cls(
            mixture_item_name=data.get("MIXTURE_ITEM_NAME", ""),
            prohbt_content=data.get("PROHBT_CONTENT", ""),
            remark=data.get("REMARK", ""),
        )


@dataclass
class Answer:
    """닥터가디언 답변"""
    text: str                                    # 답변 내용
    question_type: QuestionType = QuestionType.MEDICAL
    detected_drugs: list[str] = field(default_factory=list)
    sources: list[dict] = field(default_factory=list)
    drug_info: Optional[DrugInfo] = None
    dur_info: list[DURInfo] = field(default_factory=list)
    has_drug_api: bool = False
    has_dur_api: bool = False
    input_tokens: int = 0
    output_tokens: int = 0
