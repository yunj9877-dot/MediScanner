# MediScanner (메디스캐너)

> RAG 기반 한국어 의료 상담 AI 서비스

## 프로젝트 개요

| 항목 | 내용 |
|------|------|
| 목적 | 고령자를 위한 AI 의료 상담 + 약품 정보 서비스 |
| 핵심 기술 | RAG (Retrieval-Augmented Generation) + 하이브리드 검색 |
| 기반 논문 | "Benchmarking RAG for Medicine" (ACL 2024 Findings) |
| 대상 사용자 | 고령자 및 일반 사용자 (모바일 우선) |

## 핵심 기능

- **AI 의료 상담**: 증상/질환 관련 질문에 RAG 기반 답변 + 출처 표시
- **약 검색**: e약은요 API 연동, 복용법/주의사항 제공
- **약 스캔**: GPT-4 Vision OCR로 약 이름 인식 + 안전성 분석
- **개인 맞춤**: 나이/기저질환/복용약 등록 → 맞춤형 답변
- **TTS**: 전 기능 음성 출력 지원 (시니어 접근성)

## 기술 스택

### 백엔드
- **Framework**: FastAPI (Python)
- **벡터DB**: ChromaDB (150만 청크)
- **임베딩**: ko-sroberta-multitask (768차원, 한국어 특화)
- **검색**: 하이브리드 (시맨틱 + BM25 + RRF 융합)
- **LLM**: GPT-4o-mini (답변 생성)
- **외부 API**: 식약처 e약은요, 기상청, 에어코리아

### 프론트엔드
- **Framework**: React + Vite
- **스타일**: Tailwind CSS
- **UI**: 모바일 우선 (375×720px), 시니어 친화적

### 배포
- **플랫폼**: Render (백엔드 + 프론트 통합)
- **방식**: GitHub Push → 자동 빌드/배포

## 디렉토리 구조

```
MediScanner/
├── app/                    # 백엔드 핵심 코드
│   ├── domain/             # 엔티티, 유스케이스
│   └── infra/              # BM25, ChromaDB, OpenAI, API
├── MediScanner-frontend/   # React 프론트엔드
│   └── src/components/     # UI 컴포넌트
├── scripts/                # 유틸리티 스크립트
├── tests/                  # TDD 테스트 (58개)
├── main_rest_api.py        # FastAPI 서버
└── requirements.txt        # Python 의존성
```

## RAG 파이프라인

```
사용자 질문
    │
    ▼
[하이브리드 검색] ← 논문 RRF-2 방식
  ├─ 시맨틱 검색 (ko-sroberta)
  ├─ BM25 키워드 검색
  └─ RRF 융합 → 최종 문서 선정
    │
    ▼
[답변 생성] ← 논문 Self-RAG 방식
  ├─ ISREL: 관련성 검증 (환각 방지)
  ├─ ISSUP: 출처 표시
  └─ ISUSE: 쉬운 말로 설명
    │
    ▼
AI 답변 + 출처 + 면책 문구
```

## TDD 테스트 (58개)

의료 서비스 특성상 코드 결함이 잘못된 의료 정보로 이어질 수 있어, TDD를 통해 전 계층을 독립 검증합니다.

### 테스트 그룹 구성

| 그룹 | 개수 | 검증 내용 |
|------|:----:|----------|
| Domain 엔티티 | 8 | Question, Document, DrugInfo, DURInfo, Answer |
| 약 이름 감지 | 5 | 단일/다수 약, 비타민, 오탐 방지 |
| RRF 융합 | 5 | 순위 계산, 출처 추적, top_k 제한 |
| BM25 검색 | 5 | 한국어 토크나이징, 한영 혼합, 인덱스 |
| GPT 컨텍스트 | 5 | RAG/API/DUR 결과 통합 |
| 질문 분류 | 4 | 의학/약/복합/약단독 분류 |
| API 계층 | 3 | REST 요청/응답 모델 검증 |
| DB 계층 | 13 | 프로필/히스토리 CRUD, 토큰 사용량 |
| 프로필 맞춤 | 4 | 건강 정보 프롬프트 반영 |
| 답변 모드 | 4 | 간단(80토큰)/상세(500토큰) 분기 |
| XML/CDATA | 2 | 허가정보 API 파싱 |
| **합계** | **58** | |

### 테스트 실행

```bash
# Windows PowerShell
$env:PYTHONPATH = "."; pytest tests/test_all.py -v

# 결과: 58 passed
```

### TDD 원칙 (RED → GREEN → REFACTOR)

1. **RED**: 테스트 먼저 작성 (실패)
2. **GREEN**: 테스트 통과하는 최소 코드 구현
3. **REFACTOR**: 코드 정리 (테스트 통과 유지)

### 수동 테스트 체크리스트

발표 데모 시나리오 기준 **72문항** UI/기능 테스트  
→ [TEST_CHECKLIST.md](./TEST_CHECKLIST.md) 참조

## 개인정보 보호 철학

> "메디스캐너는 사용자의 개인 기록을 남기지 않는다."

- **회원가입 없음**: 접속 즉시 사용
- **세션 기반**: 랜덤 세션 ID 자동 생성
- **자동 삭제**: 앱 종료 시 모든 데이터 삭제
- **서버 보관 없음**: 건강 정보 영구 저장하지 않음

## 실행 방법

### 로컬 실행
```bash
# 백엔드 (터미널 1)
uvicorn main_rest_api:app --host 0.0.0.0 --port 8001

# 프론트엔드 (터미널 2)
cd MediScanner-frontend && npm run dev
```
→ http://localhost:5173 접속

### 원클릭 실행
`start.bat` 더블클릭

## 참고 논문

1. **Xiong, G. et al. (2024)** - Benchmarking RAG for Medicine (ACL 2024)
   - RRF-2 하이브리드 검색, Self-RAG 환각 방지의 근거
2. **Reimers, N. & Gurevych, I. (2019)** - Sentence-BERT (EMNLP)
   - ko-sroberta 임베딩 모델의 기반 프레임워크
3. **Beck, K. (2002)** - Test-Driven Development
   - TDD 방법론 (결함률 40~90% 감소 입증)

## 라이선스

이 프로젝트는 학습 목적으로 제작되었습니다.

---

**개발**: K-Digital 의료AI융합 훈련과정 (2026)
