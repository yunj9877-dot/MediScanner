# MediScanner - 설치 및 실행 가이드

## 📋 시스템 요구사항

- Python 3.10 이상
- Node.js 18 이상
- RAM 8GB 이상 권장
- 디스크 여유 공간 5GB 이상 (데이터 파일 포함)

---

## 📁 프로젝트 구조

```
MediScanner/
├── app/                        ← FastAPI 백엔드 (Clean Architecture)
│   ├── core/                   ← 설정, 의존성 주입
│   ├── domain/                 ← 도메인 모델
│   ├── infrastructure/         ← DB, 검색 엔진 구현체
│   └── interfaces/             ← API 라우터
├── MediScanner-frontend/       ← React + Vite + Tailwind CSS
├── data/                       ← ChromaDB (메타데이터 전용)
├── eval_data/                  ← 평가 질문셋
├── results/                    ← 검색 성능 평가 결과
├── scripts/                    ← 평가 스크립트
├── tests/                      ← TDD 테스트 (58개)
├── hnsw_index.bin              ← hnswlib 벡터 인덱스 (별도 보관)
├── hnsw_ids.json               ← HNSW ID 매핑
├── temp_chunks_source_only.pkl ← 청크 텍스트 조회용 (별도 보관)
├── bm25_cache_e5small.pkl      ← BM25 인덱스 캐시 (별도 보관)
├── main_rest_api.py            ← FastAPI 앱 진입점
├── requirements.txt
├── start.bat                   ← 백엔드 실행 스크립트 (Windows)
└── .env                        ← API 키 설정
```

---

## ⚙️ 1단계: 환경 변수 설정

프로젝트 루트에 `.env` 파일을 생성하고 아래 내용을 입력하세요:

```env
OPENAI_API_KEY=sk-...
```

---

## 🔧 2단계: 백엔드 설치

```bash
# 프로젝트 폴더로 이동
cd MediScanner

# 패키지 설치
pip install -r requirements.txt
```

> ⚠️ chromadb는 반드시 **0.4.24** 버전이어야 합니다. 다른 버전 설치 시 동작하지 않습니다.

---

## 🗂️ 3단계: 데이터 파일 배치

아래 파일들은 용량이 커서 별도 보관됩니다. 실행 전 프로젝트 루트에 복사해주세요:

| 파일명 | 설명 | 위치 |
|--------|------|------|
| `hnsw_index.bin` | hnswlib 벡터 인덱스 (676,570 청크) | 루트 |
| `hnsw_ids.json` | HNSW ID ↔ 청크 ID 매핑 | 루트 |
| `temp_chunks_source_only.pkl` | 청크 텍스트 조회 딕셔너리 | 루트 |
| `bm25_cache_e5small.pkl` | BM25 인덱스 캐시 | 루트 |

---

## ▶️ 4단계: 백엔드 실행

### Windows
```bash
start.bat
```

### 직접 실행
```bash
uvicorn main_rest_api:app --host 0.0.0.0 --port 8001 --reload
```

백엔드 서버: `http://localhost:8001`  
API 문서: `http://localhost:8001/docs`

---

## 🌐 5단계: 프론트엔드 실행

```bash
cd MediScanner-frontend

# 최초 실행 시 패키지 설치
npm install

# 개발 서버 실행
npm run dev
```

프론트엔드: `http://localhost:5173`

---

## 🧪 테스트 실행

```bash
# 전체 테스트 (58개)
pytest tests/ -v
```

---

## 🔍 검색 성능 평가

```bash
# E5-small Hit Rate 평가 (200개 질문)
python scripts/evaluate_200_questions_v3.py

# 결과는 results/ 폴더에 자동 저장
```

---

## 🏗️ 기술 스택

| 구분 | 기술 |
|------|------|
| 백엔드 | FastAPI + uvicorn (port 8001) |
| 프론트엔드 | React + Vite + Tailwind CSS (port 5173) |
| 임베딩 모델 | multilingual-E5-small (384차원) |
| 벡터 검색 | hnswlib (직접 knn_query) |
| 키워드 검색 | BM25 (rank-bm25) |
| 하이브리드 | RRF (Reciprocal Rank Fusion, k=60) |
| LLM | GPT-4o-mini |
| 메타데이터 DB | ChromaDB 0.4.24 |
| 아키텍처 | Clean Architecture + TDD |

---

## ❓ 자주 묻는 문제

**Q. `hnsw_index.bin` 로드 오류가 발생해요**  
A. hnswlib는 경로에 한글이 포함된 경우 오류가 발생합니다. 반드시 상대 경로로 접근하도록 설정을 확인하세요.

**Q. chromadb 버전 오류가 발생해요**  
A. `pip install chromadb==0.4.24` 로 정확한 버전을 설치하세요.

**Q. numpy 관련 오류가 발생해요**  
A. `pip install "numpy<2.0.0"` 으로 numpy 버전을 낮춰주세요.
