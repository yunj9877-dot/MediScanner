# MediScanner 검색 정확도 평가 기준 문서

작성일: 2026-03-31  
대상 스크립트: evaluate_three_models.py  
평가 질문: evaluate_200_questions_v3.py (200개)

---

## 1. 평가 목적

세 가지 임베딩 모델(ko-sroberta / E5-small / E5-large)의 검색 정확도를
동일 기준으로 비교하여 최적 모델과 검색 방식을 결정한다.

---

## 2. 평가 대상 모델

| 모델 | ChromaDB 경로 | 임베딩 차원 | 특징 |
|---|---|---|---|
| ko-sroberta | data/chroma_db_kosroberta | 768 | 한국어 특화 |
| E5-small | data/chroma_db_e5small | 384 | 경량 다국어 |
| E5-large | data/chroma_db | 1024 | 고성능 다국어 (현재 채택) |

---

## 3. 검색 방식

각 모델에 대해 세 가지 검색 방식을 모두 측정한다.

| 방식 | 설명 |
|---|---|
| 시맨틱 | 임베딩 벡터 유사도만 사용 |
| BM25 | 형태소 분석 기반 키워드 검색만 사용 |
| RRF | 시맨틱 Top-20 + BM25 Top-20 → RRF 융합(k=60) → Top-K |

---

## 4. 평가 질문 구성

총 200개, 7개 카테고리, 2가지 난이도

| 난이도 | 개수 | 특징 |
|---|---|---|
| 기본(basic) | 100개 | 직접적 의학 용어 사용 |
| 추론(hard) | 100개 | 고령자 구어체, 간접 표현 |

**카테고리 분류**

| 카테고리 | 기본 | 추론 |
|---|---|---|
| 증상-질병 | 20개 | 20개 |
| 생활습관-영향 | 15개 | 15개 |
| 음식-약물 상호작용 | 15개 | 15개 |
| 음식-질병 | 10개 | 10개 |
| 복합질환 | 15개 | 15개 |
| 약물부작용 | 15개 | 15개 |
| 예방관리 | 10개 | 10개 |

---

## 5. Hit 판정 기준

### 5.1 기본 원칙

검색된 문서 하나에 아래 두 조건이 **동시에** 충족되어야 Hit으로 인정한다.

```
Hit = must_hit AND context_hit
```

| 조건 | 키워드 수 | 기준 |
|---|---|---|
| must_hit | 보통 2개 (한국어 + 영어) | 1개 이상 포함 |
| context_hit | 3~4개 (한국어 2 + 영어 2) | 1개 이상 포함 |

### 5.2 키워드 구조

```python
{
  "question": "자몽과 약물 상호작용은?",
  "must":    ["자몽", "grapefruit"],
  "context": ["약물", "상호작용", "drug", "interaction"],
  "category": "음식-약물",
  "difficulty": "basic"
}
```

**must** — 질문의 핵심 주제어. 없으면 무조건 Miss  
**context** — 맥락어. must와 함께 있어야 Hit. 한국어 2개 + 영어 2개 = 3~4개

### 5.3 판정 예시

**예시 1 — Hit**
```
질문: "자몽과 약물 상호작용은?"
검색 문서: "...자몽(grapefruit)은 CYP3A4 효소를 억제하여 약물 대사에..."
→ must_hit:    "자몽" 있음 ✓
→ context_hit: "약물" 있음 ✓
→ 판정: HIT ✓
```

**예시 2 — Miss (must 없음)**
```
질문: "자몽과 약물 상호작용은?"
검색 문서: "...약물 상호작용은 환자 안전에 중요합니다..."
→ must_hit:    "자몽", "grapefruit" 둘 다 없음 ✗
→ context_hit: "약물" 있음 ✓
→ 판정: MISS ✗  (must 조건 불충족)
```

**예시 3 — Miss (context 없음)**
```
질문: "자몽과 약물 상호작용은?"
검색 문서: "...자몽은 비타민C가 풍부한 과일입니다..."
→ must_hit:    "자몽" 있음 ✓
→ context_hit: "약물", "상호작용", "drug", "interaction" 모두 없음 ✗
→ 판정: MISS ✗  (context 조건 불충족)
```

### 5.4 Top-K 기준

Top-K 안의 문서 중 하나라도 Hit 조건을 만족하면 해당 K에서 Hit.

| 지표 | 설명 |
|---|---|
| Hit Rate@3 | 상위 3개 문서 중 Hit 조건 문서 있으면 Hit |
| Hit Rate@5 | 상위 5개 문서 중 Hit 조건 문서 있으면 Hit |
| Hit Rate@10 | 상위 10개 문서 중 Hit 조건 문서 있으면 Hit |

---

## 6. RRF 융합 방식

MedRAG 논문(Xiong et al., ACL 2024)과 동일한 파라미터 사용.

```
RRF_score(d) = Σ 1 / (k + rank_i(d))
k = 60
```

- 시맨틱 검색 Top-20 + BM25 검색 Top-20 각각 수행
- 각 문서의 순위 기반 RRF 점수 계산 후 재정렬
- 상위 Top-K 선택

---

## 7. BM25 토크나이저 — kiwipiepy 형태소 분석

**설치**: `pip install kiwipiepy`

### 개선 내용

기존 공백+정규식 방식은 복합어를 하나의 덩어리로 인식했다.
kiwipiepy 형태소 분석으로 복합어를 개별 단어로 분리한다.

| 입력 | 기존 (공백 분리) | 개선 (형태소 분리) |
|---|---|---|
| "고혈압약" | ["고혈압약"] | ["고혈압", "약"] |
| "당뇨합병증" | ["당뇨합병증"] | ["당뇨", "합병증"] |
| "심근경색증상" | ["심근경색증상"] | ["심근경색", "증상"] |

### 효과

- "고혈압" 키워드 검색 시 → "고혈압" 문서 + "고혈압약" 문서 모두 검색 가능
- "고혈압약" 키워드 검색 시 → "고혈압"+"약" 토큰이 함께 있는 문서만 검색
- "고혈압"과 "고혈압약"을 서로 다른 개념으로 구분 가능

kiwipiepy 미설치 시 공백+정규식 기반 기본 토크나이저로 자동 폴백.

---

## 8. 결과 저장

실행 완료 시 자동 저장.

| 파일 | 내용 |
|---|---|
| results/eval_three_models_YYYYMMDD_HHMMSS.csv | 전체 수치 (엑셀 열기 가능) |
| results/eval_three_models_YYYYMMDD_HHMMSS_summary.txt | 텍스트 요약 |

---

## 9. 실행 방법

필요 파일 (MediScanner 폴더에 같이 있어야 함):
- `evaluate_three_models.py`
- `evaluate_200_questions_v3.py`

```powershell
# 전체 3모델
python evaluate_three_models.py

# 특정 모델만
python evaluate_three_models.py --models e5large
python evaluate_three_models.py --models kosroberta e5small
```

---

## 10. 버전 이력

| 버전 | 변경 내용 |
|---|---|
| v1 | 키워드 1개만 있어도 Hit — 기준이 너무 관대 |
| v2 | must AND context 방식 도입. context 6~8개. RRF 버그 수정 |
| v3 | context 3~4개로 축소 (한국어 2 + 영어 2). kiwipiepy 형태소 분석 도입 |

---

## 11. 평가 한계 및 주의사항

- 이 평가는 **검색 정확도(Retrieval Accuracy)** 만 측정한다.
  GPT 최종 답변의 품질은 별도 평가가 필요하다.
- Hit 판정은 키워드 존재 여부 기반이므로,
  문서가 질문에 완전히 답하는지는 보장하지 않는다.
- 평가 반복 실행 시 항상 동일한 결과가 나온다 (학습 없음, 읽기 전용).
