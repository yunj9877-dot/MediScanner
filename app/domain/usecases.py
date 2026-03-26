"""
닥터가디언 유스케이스 (domain 계층)
===================================
핵심 비즈니스 로직: "질문 → 분류 → 검색 → 답변" 파이프라인
외부 도구(infra)를 주입받아 사용하므로, infra를 교체해도 이 코드는 변경 없음

핵심 원칙: "정확한 답이 있는 곳에서는 직접 가져오고, 없는 곳에서만 검색한다"
"""

from app.domain.entities import (
    Question, QuestionType, Document, DrugInfo, DURInfo, Answer
)
from app.infra.chromadb_repo import ChromaDBRepo
from app.infra.bm25_search import BM25Search
from app.infra.rrf_fusion import RRFFusion
from app.infra.openai_client import OpenAIClient
from app.infra.drug_api import DrugAPIClient, extract_drug_names
from app.config import TOP_K, RETRIEVAL_K


class MedicalQAUseCase:
    """
    닥터가디언 핵심 유스케이스

    질문 유형에 따라 자동으로 최적 방식 선택:
    - 의약품 질문 → 의약품 API 직접 조회 (~100%)
    - 의학 지식 질문 → RRF 하이브리드 검색 (~81%)
    - 복합 질문 → API + RAG 동시 사용
    """

    def __init__(self):
        # infra 계층 주입
        self.chromadb = ChromaDBRepo()
        self.bm25 = BM25Search()
        self.rrf = RRFFusion()
        self.openai = OpenAIClient()
        self.drug_api = DrugAPIClient()

        # BM25 인덱스 구축 (ChromaDB에서 문서 가져오기)
        # BM25 캐시가 있으면 ChromaDB 조회 건너뜀 (서버 시작 속도 최적화)
        if self.bm25.try_load_cache():
            print("✅ BM25 캐시에서 빠른 로딩 완료")
        else:
            print("📦 ChromaDB에서 문서 로딩 중...")
            docs, metadatas, ids = self.chromadb.get_all_documents()
            self.bm25.build_index(docs, metadatas, ids)

    # ════════════════════════════════════════
    # 1. 질문 분류
    # ════════════════════════════════════════
    def classify_question(self, query: str) -> Question:
        """
        질문에서 약 이름을 감지하여 분류:
        - DRUG: 약 이름만 있는 질문 → API 직접 조회
        - MEDICAL: 의학 지식 질문 → RAG 검색
        - HYBRID: 약 + 질환 복합 질문 → API + RAG 동시
        """
        drug_names = extract_drug_names(query)

        medical_keywords = [
            "치료", "원인", "증상", "예방", "합병증", "진단",
            "검사", "수술", "운동", "식이", "관리",
        ]
        has_medical = any(kw in query for kw in medical_keywords)

        if drug_names and has_medical:
            q_type = QuestionType.HYBRID
        elif drug_names:
            q_type = QuestionType.DRUG
        else:
            q_type = QuestionType.MEDICAL

        return Question(
            text=query,
            question_type=q_type,
            detected_drugs=drug_names,
        )

    # ════════════════════════════════════════
    # 2. RRF 하이브리드 검색
    # ════════════════════════════════════════
    def search(self, query: str, top_k: int = TOP_K) -> list[Document]:
        """
        MedRAG 논문 RRF-2 하이브리드 검색:
        1) 시맨틱 검색 → 상위 20개
        2) BM25 검색 → 상위 20개
        3) RRF 융합 → 최종 Top-K

        ※ Reranker 미사용 (성능 실험 결과 RRF만이 81.2%로 최고)
        """
        semantic_results = self.chromadb.search(query, top_k=RETRIEVAL_K)
        bm25_results = self.bm25.search(query, top_k=RETRIEVAL_K)
        fused_results = self.rrf.fuse(semantic_results, bm25_results, top_k=top_k)
        return fused_results

    # ════════════════════════════════════════
    # 3. 통합 질문 처리 (핵심!)
    # ════════════════════════════════════════
    async def ask(
        self,
        query: str,
        answer_mode: str = "simple",
        user_profile: dict | None = None,
    ) -> Answer:
        """
        닥터가디언 핵심 함수:
        1) 질문 분류 (약 이름 감지)
        2) 유형별 데이터 수집 (API / RAG / 둘 다)
        3) GPT 답변 생성 (Self-RAG 환각 방지)

        Args:
            query: 사용자 질문
            answer_mode: "simple"(간단 2~3문장) / "detailed"(상세 설명)
            user_profile: 사용자 프로필 {"name", "age", "diseases", "medications"}
        """
        # 1) 질문 분류
        question = self.classify_question(query)

        # 2) 유형별 데이터 수집
        docs: list[Document] = []
        drug_info: DrugInfo | None = None
        dur_info: list[DURInfo] = []

        # RAG 검색 (의학지식 또는 복합)
        if question.question_type in (QuestionType.MEDICAL, QuestionType.HYBRID):
            docs = self.search(query)

        # API 조회 (의약품 또는 복합)
        if question.question_type in (QuestionType.DRUG, QuestionType.HYBRID):
            if question.detected_drugs:
                first_drug = question.detected_drugs[0]
                drug_results, dur_results = await self.drug_api.get_full_info(first_drug)

                if drug_results:
                    drug_info = drug_results[0]
                dur_info = dur_results

        # 3) GPT 답변 생성 (프로필 + answer_mode 전달)
        answer_text, input_tokens, output_tokens = self.openai.generate(
            query=query,
            docs=docs,
            drug_info=drug_info,
            dur_info=dur_info if dur_info else None,
            answer_mode=answer_mode,
            user_profile=user_profile,
        )

        # 4) Answer 엔티티 반환
        return Answer(
            text=answer_text,
            question_type=question.question_type,
            detected_drugs=question.detected_drugs,
            sources=[
                {
                    "source": doc.metadata.get("source_spec", ""),
                    "rrf_score": doc.rrf_score,
                    "found_in": doc.found_in,
                }
                for doc in docs
            ],
            drug_info=drug_info,
            dur_info=dur_info,
            has_drug_api=drug_info is not None,
            has_dur_api=len(dur_info) > 0,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
