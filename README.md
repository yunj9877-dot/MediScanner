# 메디스캐너 (MediScanner)

**RAG 기반 한국어 의료 상담 AI 서비스 — 고령층을 위한 접근성 중심 헬스케어 플랫폼**

> K-Digital Training 캡스톤 프로젝트 | 4팀 | 2026.04.20

---

## 서비스 개요

메디스캐너는 65세 이상 고령층이 회원가입 없이 구어체로 질문하면, RAG 기반 신뢰할 수 있는 의료 정보를 제공하는 AI 상담 서비스입니다.

**핵심 원칙**
- 회원가입 없음 — 세션 기반 랜덤 ID, 종료 시 자동 삭제
- 구어체 질문 그대로 인식 — "혈압약 먹는데 자몽 먹어도 돼?"
- RAG 근거 제시 + Self-RAG 환각 방지
- 모바일 375px 최적화 + TTS 전 기능 음성 출력

---

## 주요 기능

| 기능 | 설명 |
|---|---|
| AI 의료 상담 | RAG 검색 + GPT-4o-mini 맞춤 답변 (기저질환·복용약 반영) |
| 약스캔 | 약봉투 OCR 촬영 → 성분 자동 추출 → 식약처 DUR 병용금기 검사 |
| 약 검색 | 식약처 e약은요 API — 약품 정보·복용법·부작용 |
| TTS 음성 안내 | 전 기능 Web Speech API 음성 출력 |
| 건강 환경 정보 | 기상청 날씨 + 에어코리아 미세먼지 실시간 연동 |

---

## 기술 스택

| 구분 | 기술 |
|---|---|
| Frontend | React 18 + Vite + Tailwind CSS |
| Backend | FastAPI (Python 3.13) |
| 임베딩 모델 | multilingual-E5-small (Microsoft, 384차원, 100개 언어) |
| 벡터 검색 | hnswlib 직접 검색 + ChromaDB 0.4.24 (메타데이터) |
| 키워드 검색 | BM25 (rank_bm25 + kiwipiepy) |
| LLM | GPT-4o-mini |
| 아키텍처 | Clean Architecture + TDD (58개 테스트 100% 통과) |

---

## 데이터셋

**출처: AI Hub (https://aihub.or.kr) — 국가 공인 데이터**

| 구분 | 데이터명 | 건수 | 비고 |
|---|---|---|---|
| 원천 | 필수의료 의학지식 데이터 | 38,406건 | 52,126개 파일, c_id 중복 13,720건 제외 |
| 원천 | 전문 의학지식 데이터 | 82,368건 | 112,257개 파일, c_id 중복 29,889건 제외 |
| **합계** | | **120,774건** | **→ 676,570 청크** (800자/80자 오버랩, 라벨링 미포함) |

---

## RAG 파이프라인

```
한국어 질문
    ↓
E5-small 임베딩 (query: 접두사)
    ↓
hnswlib 시맨틱 Top-20  +  BM25 키워드 Top-20
    ↓
RRF 융합 (k=60) → Top-5 선택
    ↓
Self-RAG 검증 (ISREL → ISSUP → ISUSE)
    ↓
GPT-4o-mini + 사용자 프로필 → 최종 답변
```

**검색 성능 (E5-small, 완화 기준, 200개 질문)**

| 검색 방식 | 기본 100개 @5 | 추론 100개 @5 | 전체 200개 @5 |
|---|---|---|---|
| 시맨틱 | 98.0% | 93.0% | 95.5% |
| BM25 | 95.0% | 79.0% | 87.0% |
| **RRF (채택)** | **99.0%** | **95.0%** | **97.0%** |

> MedRAG 논문 (Xiong et al., ACL 2024)과 동일 결론 — RRF 하이브리드가 가장 우수

---

## 프로젝트 구조

```
MediScanner/
├── app/                        # Clean Architecture 백엔드
│   ├── domain/                 # 핵심 비즈니스 로직 (외부 의존 없음)
│   │   ├── entities.py
│   │   └── usecases.py
│   ├── api/                    # REST API 계층
│   │   └── routes.py
│   ├── infra/                  # 인프라 구현체
│   │   ├── bm25_search.py
│   │   ├── chromadb_repo.py
│   │   ├── rrf_fusion.py
│   │   ├── drug_api.py
│   │   └── openai_client.py
│   ├── config.py
│   ├── database.py
│   └── rag_engine.py
├── MediScanner-frontend/       # React + Vite + Tailwind
│   └── src/
│       ├── App.jsx
│       └── components/
├── tests/                      # TDD 테스트
│   └── test_all.py             # 58개 테스트 100% 통과
├── scripts/                    # 평가 스크립트
│   ├── evaluate_e5small.py
│   ├── evaluate_200_questions_v3.py
│   ├── build_hnsw_from_sqlite.py
│   ├── build_vectordb.py
│   ├── compare_search_methods.py
│   ├── evaluate_chunk_size.py
│   ├── evaluate_hard_questions.py
│   └── evaluate_three_models.py
├── results/                    # 성능 평가 결과 CSV
├── eval_data/                  # 평가 데이터
├── main_rest_api.py            # FastAPI 진입점 (포트 8001)
├── requirements.txt
└── start.bat                   # 백엔드 + 프론트엔드 동시 실행
```

---

## 로컬 실행 방법

### 사전 준비

```bash
git clone https://github.com/yunj9877-dot/MediScanner.git
cd MediScanner
```

### .env 설정

```
OPENAI_API_KEY=your_openai_api_key
DATA_GO_KR_API_KEY=your_data_go_kr_api_key
```

### 백엔드 실행

```bash
pip install -r requirements.txt
uvicorn main_rest_api:app --host 0.0.0.0 --port 8001
```

### 프론트엔드 실행

```bash
cd MediScanner-frontend
npm install
npm run dev
```

### 한 번에 실행 (Windows)

```
start.bat
```

> 백엔드 http://localhost:8001 | 프론트엔드 http://localhost:5173

---

## 테스트 실행

```bash
pytest tests/test_all.py -v
```

**58개 테스트 전 계층 100% 통과**

| 테스트 그룹 | 개수 | 검증 내용 |
|---|---|---|
| TestEntities | 8개 | Domain 엔티티 구조 |
| TestRRFFusion | 5개 | RRF 융합 순위 계산 |
| TestBM25Search | 5개 | 한국어 키워드 검색 |
| TestDatabase | 12개 | 프로필·히스토리 CRUD |
| 기타 | 28개 | API, Self-RAG, 답변 모드 등 |

---

## REST API 엔드포인트

| 엔드포인트 | 메서드 | 기능 |
|---|---|---|
| `/api/chat` | POST | RAG 기반 AI 의료 상담 |
| `/api/profile/{user_id}` | GET/POST/DELETE | 건강 프로필 관리 |
| `/api/medicine/search` | POST | 식약처 약품 검색 |
| `/api/camera/analyze` | POST | 약봉투 OCR + 안전성 분석 |
| `/api/analyze-profile` | POST | AI 건강 분석 리포트 |
| `/api/weather` | GET | 날씨 + 미세먼지 |
| `/api/voice-correct` | POST | 음성 입력 텍스트 교정 |
| `/api/cleanup/{user_id}` | POST | 세션 데이터 삭제 |

---

## 참고 논문

| 논문 | 활용 |
|---|---|
| Xiong et al. (2024). *Benchmarking RAG for Medicine*. ACL 2024 Findings. | RAG 파이프라인 설계, RRF 방법론 |
| Asai et al. (2024). *Self-RAG*. ICLR 2024 (Oral Top 1%). | ISREL·ISSUP·ISUSE 환각 방지 |
| Wang et al. (2024). *Multilingual E5 Text Embeddings*. arXiv:2402.05672. | E5-small 임베딩 모델 |
| Martin, R.C. (2017). *Clean Architecture*. Prentice Hall. | 계층 분리·의존성 규칙 |
| Marabesi et al. (2024). *TDD & Test Smells*. MDPI Computers 13(3). | TDD 품질 검증 |

---

## 개인정보 보호 설계

> **"회원가입 없음 · 로그인 없음 · 앱 종료 시 모든 기록 즉시 삭제"**

메디스캐너는 고령층의 민감한 건강 정보를 서버에 남기지 않는 것을 핵심 설계 원칙으로 합니다.

| 구현 항목 | 방법 | 효과 |
|---|---|---|
| 세션 ID | `sessionStorage` 랜덤 ID 자동 생성 | 탭·브라우저 닫으면 즉시 소멸 |
| 앱 종료 버튼 | `/api/cleanup/{session_id}` 즉시 호출 | 서버 DB 프로필·상담기록 전부 삭제 |
| 브라우저 강제 종료 | `beforeunload` 이벤트 → `sendBeacon` API | 갑자기 닫아도 누락 없이 자동 삭제 |
| 회원가입 구조 | 이름·연락처 등 개인 식별 정보 수집 구조 자체 없음 | 수집 불가능한 구조적 보호 |
| 기저질환·복용약 | 세션 중에만 SQLite 임시 저장 | 세션 종료 시 완전 삭제 |

---

## 환경

- Python 3.13.5
- Node.js v24.13.1
- ChromaDB 0.4.24 (고정)

---

*K-Digital Training 의료AI융합 훈련과정 | 4팀 박윤정 | 2026*
