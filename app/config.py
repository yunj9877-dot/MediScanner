"""
MediScanner 설정
====================
ARCHITECTURE.md 기준 확정 설정
2026-03-28 업데이트: multilingual-e5-large + 800자 청크
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ── OpenAI (답변 생성 + 질문 분류 전용) ──
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_CHAT_MODEL = "gpt-4o-mini"

# ── 임베딩 모델 (로컬, 무료) ──
# [변경] ko-sroberta → multilingual-e5-large
# 이유: 영어 원천데이터 + 한국어 QA 모두 최적 지원
# 논문: "Multilingual E5 Text Embeddings: A Technical Report" (Wang et al., 2024)
EMBEDDING_MODEL = "intfloat/multilingual-e5-large"  # 1024차원, 다국어 (영어+한국어)
EMBEDDING_DIMENSION = 1024

# ── ChromaDB ──
CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", "./data/chroma_db")
COLLECTION_NAME = "medical_knowledge"  # 단일 컬렉션

# ── 공공데이터 API ──
DATA_GO_KR_API_KEY = os.getenv("DATA_GO_KR_API_KEY", "")

# e약은요 API
DRUG_API_BASE = "https://apis.data.go.kr/1471000/DrbEasyDrugInfoService/getDrbEasyDrugList"

# DUR 품목정보 API (병용금기)
DUR_API_BASE = "https://apis.data.go.kr/1471000/DURPrdlstInfoService03/getUsjntTabooInfoList03"

# 의약품 제품 허가정보 API (전체 허가 의약품 162만 건)
PERMIT_API_BASE = "https://apis.data.go.kr/1471000/DrugPrdtPrmsnInfoService07/getDrugPrdtPrmsnDtlInq06"

# ── RAG 설정 ──
TOP_K = 5                    # 최종 반환 상위 K개
RETRIEVAL_K = 20             # 1차 검색 후보 수 (BM25 + 시맨틱 각각)
CHUNK_SIZE = 800             # [변경] 500 → 800 (청크 실험 결과 70.8% 최고)
CHUNK_OVERLAP = 80           # [변경] 50 → 80 (청크 크기 비례 증가)
EMBEDDING_BATCH_SIZE = 100   # 임베딩 배치 크기
RRF_K = 60                   # RRF 융합 파라미터 (MedRAG 논문 기본값)

# ── Reranker (크로스인코더) ──
# 실험 결과: RRF만 81.2% > RRF+Reranker 77.4% → Reranker 미사용
RERANKER_MODEL = "Dongjin-kr/ko-reranker"  # 한국어 리랭커 (비활성화됨)
USE_RERANKER = False  # [추가] Reranker 사용 여부

# ── multilingual-e5 prefix 설정 ──
# multilingual-e5는 query/passage prefix 필요
E5_QUERY_PREFIX = "query: "      # 검색 쿼리용
E5_PASSAGE_PREFIX = "passage: "  # 문서 임베딩용

# ── 비용 추적 ──
# 임베딩: multilingual-e5 (무료, 로컬) → 비용 없음
# GPT-4o-mini만 유료
COST_INPUT_PER_1K = 0.00015        # gpt-4o-mini input
COST_OUTPUT_PER_1K = 0.0006        # gpt-4o-mini output
