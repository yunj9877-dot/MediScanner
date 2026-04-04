"""
MediScanner 검색 정확도 평가 (어려운 질문 30개)
- 실제 고령자 사용자가 할 만한 자연스러운 질문
- 추론이 필요한 간접적 표현
- 증상→질병, 생활습관→영향 관계 파악 필요
"""

import re
import pickle
from pathlib import Path

# ============================================================
# 설정값
# ============================================================
EMBEDDING_MODEL = "intfloat/multilingual-e5-large"
CHROMA_DB_PATH = "./data/chroma_db"
COLLECTION_NAME = "medical_knowledge"
E5_QUERY_PREFIX = "query: "

# ============================================================
# 어려운 평가용 QA (30개) - 실제 고령자 질문 스타일
# ============================================================
HARD_EVAL_QA = [
    # === 증상 → 질병 연결 (간접 표현) ===
    {
        "question": "머리가 어지러운데 이러면 고혈압에 안좋아?",
        "keywords": ["어지러움", "현기증", "고혈압", "혈압", "dizziness", "hypertension", "vertigo"],
        "category": "증상-질병"
    },
    {
        "question": "요즘 자꾸 목이 마르고 화장실을 자주 가는데 무슨 병이야?",
        "keywords": ["갈증", "다뇨", "빈뇨", "당뇨", "diabetes", "thirst", "polyuria", "polydipsia"],
        "category": "증상-질병"
    },
    {
        "question": "밤에 다리가 저리고 쥐가 나는데 이거 뭐가 문제야?",
        "keywords": ["저림", "경련", "다리", "신경", "당뇨", "혈액순환", "neuropathy", "cramp", "numbness"],
        "category": "증상-질병"
    },
    {
        "question": "가슴이 답답하고 숨이 차는데 심장이 안좋은 거야?",
        "keywords": ["흉부", "호흡곤란", "심장", "심부전", "협심증", "dyspnea", "chest", "heart failure", "angina"],
        "category": "증상-질병"
    },
    {
        "question": "소변볼 때 찔끔찔끔 나오고 시원하지 않은데 왜 그래?",
        "keywords": ["배뇨", "전립선", "비대", "잔뇨감", "BPH", "prostate", "urination", "hesitancy"],
        "category": "증상-질병"
    },
    
    # === 생활습관 → 질병 영향 ===
    {
        "question": "술을 많이 먹으면 골다공증에는 어떤 영향이 있어?",
        "keywords": ["알코올", "음주", "골다공증", "뼈", "골밀도", "alcohol", "osteoporosis", "bone density"],
        "category": "생활습관-영향"
    },
    {
        "question": "매일 술을 마시면 치매 환자는 몇년 더 살 수 있어?",
        "keywords": ["음주", "알코올", "치매", "수명", "예후", "dementia", "alcohol", "prognosis", "mortality"],
        "category": "생활습관-영향"
    },
    {
        "question": "담배 피우면 당뇨병이 더 나빠져?",
        "keywords": ["흡연", "담배", "당뇨", "혈당", "합병증", "smoking", "diabetes", "complication"],
        "category": "생활습관-영향"
    },
    {
        "question": "커피를 많이 마시면 고혈압 약이 안 듣는다던데 진짜야?",
        "keywords": ["카페인", "커피", "고혈압", "약물", "상호작용", "caffeine", "coffee", "hypertension", "interaction"],
        "category": "생활습관-영향"
    },
    {
        "question": "운동을 안 하면 심장병 걸리기 쉬워?",
        "keywords": ["운동부족", "좌식", "심장", "심혈관", "위험", "sedentary", "cardiovascular", "heart disease", "risk"],
        "category": "생활습관-영향"
    },
    
    # === 음식/약물 상호작용 ===
    {
        "question": "당뇨 있는데 과일 많이 먹어도 괜찮아?",
        "keywords": ["당뇨", "과일", "당분", "혈당", "fruit", "diabetes", "sugar", "glucose"],
        "category": "음식-질병"
    },
    {
        "question": "혈압약 먹는데 자몽 먹으면 안 된다던데 왜야?",
        "keywords": ["자몽", "혈압약", "상호작용", "칼슘채널", "grapefruit", "antihypertensive", "interaction", "CYP3A4"],
        "category": "음식-약물"
    },
    {
        "question": "피 묽게 하는 약 먹는데 시금치 많이 먹어도 돼?",
        "keywords": ["와파린", "항응고제", "비타민K", "시금치", "warfarin", "vitamin K", "spinach", "anticoagulant"],
        "category": "음식-약물"
    },
    {
        "question": "간이 안 좋으면 술 말고 또 뭘 조심해야 해?",
        "keywords": ["간", "간질환", "해독", "약물", "아세트아미노펜", "liver", "hepatotoxic", "acetaminophen"],
        "category": "음식-질병"
    },
    {
        "question": "신장 안 좋은 사람은 바나나 왜 조심해야 해?",
        "keywords": ["신장", "칼륨", "바나나", "고칼륨혈증", "kidney", "potassium", "banana", "hyperkalemia"],
        "category": "음식-질병"
    },
    
    # === 복합 질환 관계 ===
    {
        "question": "당뇨 있으면 왜 발 관리를 잘 해야 해?",
        "keywords": ["당뇨발", "신경병증", "궤양", "절단", "diabetic foot", "neuropathy", "ulcer", "amputation"],
        "category": "복합질환"
    },
    {
        "question": "고혈압이랑 당뇨 같이 있으면 더 위험해?",
        "keywords": ["고혈압", "당뇨", "합병증", "심혈관", "신장", "hypertension", "diabetes", "complication", "cardiovascular"],
        "category": "복합질환"
    },
    {
        "question": "뚱뚱하면 무릎이 왜 아파?",
        "keywords": ["비만", "체중", "관절", "무릎", "퇴행성", "obesity", "knee", "osteoarthritis", "weight"],
        "category": "복합질환"
    },
    {
        "question": "우울하면 진짜 몸도 아플 수 있어?",
        "keywords": ["우울증", "신체증상", "두통", "피로", "depression", "somatic", "fatigue", "pain"],
        "category": "복합질환"
    },
    {
        "question": "스트레스 받으면 위가 왜 아파?",
        "keywords": ["스트레스", "위", "위염", "궤양", "소화", "stress", "stomach", "gastritis", "ulcer"],
        "category": "복합질환"
    },
    
    # === 약물 부작용/주의사항 ===
    {
        "question": "진통제 오래 먹으면 위가 상해?",
        "keywords": ["NSAID", "진통제", "위", "궤양", "출혈", "NSAIDs", "gastric", "ulcer", "bleeding"],
        "category": "약물부작용"
    },
    {
        "question": "스테로이드 약 오래 먹으면 무슨 문제가 생겨?",
        "keywords": ["스테로이드", "부작용", "골다공증", "면역", "steroid", "side effect", "osteoporosis", "immunosuppression"],
        "category": "약물부작용"
    },
    {
        "question": "항생제 먹으면 왜 설사를 해?",
        "keywords": ["항생제", "설사", "장내세균", "클로스트리디움", "antibiotic", "diarrhea", "microbiome", "C. diff"],
        "category": "약물부작용"
    },
    {
        "question": "수면제 오래 먹으면 치매 걸려?",
        "keywords": ["수면제", "벤조디아제핀", "치매", "인지", "sleeping pill", "benzodiazepine", "dementia", "cognitive"],
        "category": "약물부작용"
    },
    {
        "question": "혈압약 먹으면 왜 마른기침이 나와?",
        "keywords": ["ACE", "기침", "부작용", "혈압약", "ACE inhibitor", "cough", "side effect", "bradykinin"],
        "category": "약물부작용"
    },
    
    # === 예방/관리 질문 ===
    {
        "question": "나이 들면 왜 자꾸 넘어져? 어떻게 예방해?",
        "keywords": ["낙상", "균형", "노인", "예방", "근력", "fall", "balance", "elderly", "prevention"],
        "category": "예방관리"
    },
    {
        "question": "암 검진은 몇 살부터 받아야 해?",
        "keywords": ["암", "검진", "스크리닝", "나이", "cancer", "screening", "age", "colonoscopy", "mammography"],
        "category": "예방관리"
    },
    {
        "question": "폐렴 주사 맞아야 해? 몇 년마다 맞아?",
        "keywords": ["폐렴구균", "백신", "예방접종", "노인", "pneumococcal", "vaccine", "elderly", "immunization"],
        "category": "예방관리"
    },
    {
        "question": "뇌졸중 한번 오면 또 올 수 있어? 어떻게 막아?",
        "keywords": ["뇌졸중", "재발", "예방", "항혈소판", "stroke", "recurrence", "prevention", "antiplatelet"],
        "category": "예방관리"
    },
    {
        "question": "치매 걸리지 않으려면 뭘 해야 해?",
        "keywords": ["치매", "예방", "인지", "운동", "dementia", "prevention", "cognitive", "exercise", "brain"],
        "category": "예방관리"
    },
]


def load_models():
    """모델 및 DB 로드"""
    from sentence_transformers import SentenceTransformer
    import chromadb
    
    print("📦 임베딩 모델 로딩 중...")
    model = SentenceTransformer(EMBEDDING_MODEL)
    
    print("📦 ChromaDB 로딩 중...")
    client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    collection = client.get_collection(name=COLLECTION_NAME)
    print(f"   문서 수: {collection.count():,}개")
    
    # BM25 캐시
    bm25, bm25_ids = None, None
    cache_path = Path("bm25_cache.pkl")
    if cache_path.exists():
        print("📦 BM25 캐시 로딩 중...")
        with open(cache_path, "rb") as f:
            cache = pickle.load(f)
        bm25 = cache.get("bm25")
        bm25_ids = cache.get("ids")
        print(f"   BM25 문서 수: {len(bm25_ids):,}개")
    
    return model, collection, bm25, bm25_ids


def search_semantic_only(model, collection, query: str, top_k: int = 10):
    """시맨틱 검색만"""
    query_emb = model.encode(f"{E5_QUERY_PREFIX}{query}", normalize_embeddings=True).tolist()
    results = collection.query(query_embeddings=[query_emb], n_results=top_k, include=["documents"])
    return results["documents"][0] if results["documents"] else []


def search_bm25_only(bm25, bm25_ids, collection, query: str, top_k: int = 10):
    """BM25 검색만"""
    if bm25 is None:
        return []
    
    tokens = [t for t in re.split(r'\s+', query.lower()) if len(t) >= 2]
    if not tokens:
        return []
    
    scores = bm25.get_scores(tokens)
    top_indices = scores.argsort()[-top_k:][::-1]
    
    docs = []
    for idx in top_indices:
        if scores[idx] > 0:
            doc_id = bm25_ids[idx]
            result = collection.get(ids=[doc_id], include=["documents"])
            if result["documents"]:
                docs.append(result["documents"][0])
    return docs


def search_rrf(model, collection, bm25, bm25_ids, query: str, top_k: int = 10, k: int = 60):
    """RRF 하이브리드 검색"""
    # 시맨틱
    query_emb = model.encode(f"{E5_QUERY_PREFIX}{query}", normalize_embeddings=True).tolist()
    sem_results = collection.query(query_embeddings=[query_emb], n_results=20, include=["documents"])
    sem_ids = sem_results["ids"][0] if sem_results["ids"] else []
    sem_docs = sem_results["documents"][0] if sem_results["documents"] else []
    
    # BM25
    bm25_result_ids = []
    if bm25 is not None:
        tokens = [t for t in re.split(r'\s+', query.lower()) if len(t) >= 2]
        if tokens:
            scores = bm25.get_scores(tokens)
            top_indices = scores.argsort()[-20:][::-1]
            bm25_result_ids = [bm25_ids[idx] for idx in top_indices if scores[idx] > 0]
    
    # RRF 융합
    rrf_scores = {}
    for rank, doc_id in enumerate(sem_ids):
        rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1 / (k + rank + 1)
    for rank, doc_id in enumerate(bm25_result_ids):
        rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1 / (k + rank + 1)
    
    sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)[:top_k]
    
    docs = []
    for doc_id in sorted_ids:
        if doc_id in sem_ids:
            idx = sem_ids.index(doc_id)
            docs.append(sem_docs[idx])
        else:
            result = collection.get(ids=[doc_id], include=["documents"])
            if result["documents"]:
                docs.append(result["documents"][0])
    return docs


def check_hit(docs: list, keywords: list) -> dict:
    """키워드 매칭으로 Hit 확인"""
    results = {"top3": False, "top5": False, "top10": False}
    
    for i, doc in enumerate(docs[:10]):
        content = doc.lower()
        hit = any(kw.lower() in content for kw in keywords)
        
        if hit:
            if i < 3:
                results["top3"] = True
                results["top5"] = True
                results["top10"] = True
                break
            elif i < 5:
                results["top5"] = True
                results["top10"] = True
            elif i < 10:
                results["top10"] = True
    
    return results


def evaluate():
    """어려운 질문 30개로 3가지 검색 방식 비교"""
    print("=" * 70)
    print("🔬 MediScanner 검색 평가 (어려운 질문 30개)")
    print("   - 실제 고령자 사용자 스타일 질문")
    print("   - 추론 필요한 간접 표현")
    print("=" * 70)
    print(f"   평가 문항: {len(HARD_EVAL_QA)}개")
    print("=" * 70)
    
    model, collection, bm25, bm25_ids = load_models()
    
    # 결과 집계
    results = {
        "semantic": {"top3": 0, "top5": 0, "top10": 0},
        "bm25": {"top3": 0, "top5": 0, "top10": 0},
        "rrf": {"top3": 0, "top5": 0, "top10": 0},
    }
    
    # 카테고리별 집계
    category_results = {}
    
    print("\n📊 평가 시작...")
    print("-" * 70)
    
    for i, qa in enumerate(HARD_EVAL_QA):
        question = qa["question"]
        keywords = qa["keywords"]
        category = qa["category"]
        
        # 카테고리별 초기화
        if category not in category_results:
            category_results[category] = {"total": 0, "semantic": 0, "bm25": 0, "rrf": 0}
        category_results[category]["total"] += 1
        
        # 3가지 검색 방식
        sem_docs = search_semantic_only(model, collection, question)
        bm25_docs = search_bm25_only(bm25, bm25_ids, collection, question)
        rrf_docs = search_rrf(model, collection, bm25, bm25_ids, question)
        
        # Hit 확인
        sem_hit = check_hit(sem_docs, keywords)
        bm25_hit = check_hit(bm25_docs, keywords)
        rrf_hit = check_hit(rrf_docs, keywords)
        
        # 집계
        for key in ["top3", "top5", "top10"]:
            if sem_hit[key]: results["semantic"][key] += 1
            if bm25_hit[key]: results["bm25"][key] += 1
            if rrf_hit[key]: results["rrf"][key] += 1
        
        # 카테고리별 집계 (Top-5 기준)
        if sem_hit["top5"]: category_results[category]["semantic"] += 1
        if bm25_hit["top5"]: category_results[category]["bm25"] += 1
        if rrf_hit["top5"]: category_results[category]["rrf"] += 1
        
        # 진행 상황
        sem_mark = "✅" if sem_hit["top5"] else "❌"
        bm25_mark = "✅" if bm25_hit["top5"] else "❌"
        rrf_mark = "✅" if rrf_hit["top5"] else "❌"
        print(f"   [{i+1:2d}/{len(HARD_EVAL_QA)}] S:{sem_mark} B:{bm25_mark} R:{rrf_mark} | {question[:40]}...")
    
    # 결과 출력
    total = len(HARD_EVAL_QA)
    
    print("\n" + "=" * 70)
    print("📊 검색 방식 비교 결과 (어려운 질문 30개)")
    print("=" * 70)
    
    print(f"\n   ┌──────────────┬──────────┬──────────┬──────────┐")
    print(f"   │   검색 방식   │  Top-3   │  Top-5   │  Top-10  │")
    print(f"   ├──────────────┼──────────┼──────────┼──────────┤")
    
    sem = results["semantic"]
    print(f"   │ 시맨틱만      │  {sem['top3']/total*100:5.1f}%  │  {sem['top5']/total*100:5.1f}%  │  {sem['top10']/total*100:5.1f}%  │")
    
    bm = results["bm25"]
    print(f"   │ BM25만       │  {bm['top3']/total*100:5.1f}%  │  {bm['top5']/total*100:5.1f}%  │  {bm['top10']/total*100:5.1f}%  │")
    
    rrf = results["rrf"]
    print(f"   │ RRF 하이브리드 │  {rrf['top3']/total*100:5.1f}%  │  {rrf['top5']/total*100:5.1f}%  │  {rrf['top10']/total*100:5.1f}%  │")
    
    print(f"   └──────────────┴──────────┴──────────┴──────────┘")
    
    # 카테고리별 결과
    print(f"\n   📊 카테고리별 Top-5 Hit Rate:")
    print(f"   ┌────────────────┬───────┬────────┬────────┬────────┐")
    print(f"   │    카테고리     │ 문항수 │ 시맨틱 │ BM25  │  RRF  │")
    print(f"   ├────────────────┼───────┼────────┼────────┼────────┤")
    
    for cat, data in sorted(category_results.items()):
        t = data["total"]
        s_rate = data["semantic"] / t * 100 if t > 0 else 0
        b_rate = data["bm25"] / t * 100 if t > 0 else 0
        r_rate = data["rrf"] / t * 100 if t > 0 else 0
        print(f"   │ {cat:14s} │  {t:2d}개  │ {s_rate:5.1f}% │ {b_rate:5.1f}% │ {r_rate:5.1f}% │")
    
    print(f"   └────────────────┴───────┴────────┴────────┴────────┘")
    
    # RRF vs 시맨틱 차이 분석
    print(f"\n   📈 RRF vs 시맨틱 차이:")
    diff5 = rrf['top5']/total*100 - sem['top5']/total*100
    sign5 = "+" if diff5 >= 0 else ""
    print(f"      Top-5: {sign5}{diff5:.1f}%p")
    
    if abs(diff5) < 3:
        print(f"\n   ⚠️ RRF와 시맨틱 결과 차이가 크지 않음")
        print(f"      → 이 어려운 질문들에서는 RRF 효과가 제한적")
    elif diff5 > 0:
        print(f"\n   ✅ RRF가 시맨틱보다 {diff5:.1f}%p 더 높음!")
        print(f"      → 어려운 질문에서도 RRF 효과 있음")
    else:
        print(f"\n   ❌ 시맨틱이 RRF보다 더 높음")
        print(f"      → BM25가 오히려 방해가 될 수 있음")
    
    print("\n" + "=" * 70)
    print("🎉 평가 완료!")
    print("=" * 70)


if __name__ == "__main__":
    evaluate()
