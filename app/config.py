"""
DoctorGuardians 설정
====================
ARCHITECTURE.md 기준 확정 설정
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ── OpenAI (답변 생성 + 질문 분류 전용) ──
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_CHAT_MODEL = "gpt-4o-mini"

# ── 임베딩 모델 (로컬, 무료) ──
# MedRAG 논문: MedCPT (의학 특화) → 닥터가디언: ko-sroberta (한국어 특화)
EMBEDDING_MODEL = "jhgan/ko-sroberta-multitask"  # 768차원, 한국어 특화
EMBEDDING_DIMENSION = 768

# ── ChromaDB ──
CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", "./data/chroma_db")
COLLECTION_NAME = "medical_knowledge"  # 단일 컬렉션 (이 채팅방에서 구축한 것과 동일)

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
CHUNK_SIZE = 500             # 청크 크기 (글자)
CHUNK_OVERLAP = 50           # 청크 오버랩 (글자)
EMBEDDING_BATCH_SIZE = 100   # 임베딩 배치 크기
RRF_K = 60                   # RRF 융합 파라미터 (MedRAG 논문 기본값)

# ── Reranker (크로스인코더) ──
RERANKER_MODEL = "Dongjin-kr/ko-reranker"  # 한국어 리랭커

# ── 비용 추적 ──
# 임베딩: ko-sroberta (무료, 로컬) → 비용 없음
# GPT-4o-mini만 유료
COST_INPUT_PER_1K = 0.00015        # gpt-4o-mini input
COST_OUTPUT_PER_1K = 0.0006        # gpt-4o-mini output
