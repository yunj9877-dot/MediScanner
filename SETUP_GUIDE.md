# 닥터가디언 - ChromaDB 파이프라인 실행 가이드

## 📁 폴더 구조 만들기

VS Code에서 프로젝트 폴더를 이렇게 만드세요:

```
doctor-guardians/
├── scripts/
│   └── build_vectordb.py       ← 이 파일 (파이프라인 스크립트)
├── data/
│   └── chroma_db/              ← 자동 생성됨 (벡터DB)
├── raw_data/
│   └── 필수의료/               ← AI Hub에서 받은 JSON 파일 전부 여기에
│       ├── TS_국문_기타/
│       ├── TS_국문_의학_교과서/
│       ├── TS_국문_학술_논문_및_저널/
│       ├── TS_국문_학회_가이드라인/
│       └── (나머지 ZIP 풀어서 넣기)
├── requirements.txt
└── .env                        ← 나중에 OpenAI API 키 저장
```

### raw_data 폴더 준비

1. AI Hub에서 받은 ZIP 파일들을 `raw_data/필수의료/` 안에 압축 해제
2. 하위 폴더 구조는 상관없음 — 스크립트가 자동으로 모든 `.json` 파일을 찾음


## 🔧 설치 (터미널에서)

```bash
# 1. 프로젝트 폴더로 이동
cd doctor-guardians

# 2. 가상환경 만들기 (권장)
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Mac/Linux

# 3. 패키지 설치
pip install chromadb sentence-transformers
```

> 첫 실행 시 임베딩 모델(약 500MB)이 자동 다운로드됩니다.


## ▶️ 실행

```bash
# ChromaDB 구축 (JSON → 벡터DB 변환)
python scripts/build_vectordb.py --data_dir ./raw_data/필수의료
```

실행하면 이런 화면이 나옵니다:
```
============================================================
🏥 닥터가디언 - ChromaDB 벡터DB 구축
============================================================

📂 폴더: ./raw_data/필수의료
📄 JSON 파일 발견: 19,201개
✅ 로드 완료: 19,201건

✂️ 청킹 중... (chunk_size=500)
   19,201건 → 약 44,000개 청크

📥 44,000개 청크 저장 시작...
   [ 10.0%] 4,400/44,000  (60초 경과 | 약 540초 남음)
   [ 20.0%] 8,800/44,000  (120초 경과 | 약 480초 남음)
   ...

🔍 테스트 검색 (44,000개 청크)
❓ 고혈압 치료 방법은?
   [1] 📌 대한심장학회
       고혈압 치료의 목표는 혈압을 정상 범위로...

🎉 완료! ChromaDB 위치: ./data/chroma_db
```

예상 소요 시간: **약 10~30분** (PC 성능에 따라 다름)


## 🔍 테스트만 하기

이미 구축한 DB로 검색 테스트만 하려면:

```bash
python scripts/build_vectordb.py --data_dir ./raw_data/필수의료 --test_only
```


## ⚙️ 임베딩 모델 변경 (A/B 테스트)

`build_vectordb.py` 파일 상단의 `EMBEDDING_MODEL`을 바꿔서 비교:

```python
# 옵션 A (기본): 한국어 특화
EMBEDDING_MODEL = "jhgan/ko-sroberta-multitask"

# 옵션 B: 다국어 대형
EMBEDDING_MODEL = "intfloat/multilingual-e5-base"

# 옵션 C: 경량 모델
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
```

모델을 바꾸면 `--db_path`도 바꿔서 별도 DB로 저장하세요:
```bash
python scripts/build_vectordb.py --data_dir ./raw_data/필수의료 --db_path ./data/chroma_model_b
```
