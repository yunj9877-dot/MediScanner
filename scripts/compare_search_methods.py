"""
MediScanner 검색 방식 비교 평가
- 시맨틱만 vs BM25만 vs RRF 하이브리드
- 100% 결과가 진짜인지 검증
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
# 평가용 QA (70개)
# ============================================================
EVAL_QA = [
    {"question": "고혈압 치료 방법은?", "keywords": ["고혈압", "혈압", "치료", "약물", "생활습관", "hypertension", "blood pressure"]},
    {"question": "고혈압 환자의 식이요법은?", "keywords": ["고혈압", "저염", "나트륨", "식이", "DASH", "sodium", "diet"]},
    {"question": "고혈압 약의 종류는?", "keywords": ["ACE", "ARB", "칼슘채널", "이뇨제", "베타차단제", "antihypertensive"]},
    {"question": "심근경색 증상은?", "keywords": ["심근경색", "흉통", "가슴", "통증", "심장", "myocardial", "infarction", "chest pain"]},
    {"question": "심부전 치료는?", "keywords": ["심부전", "심장", "치료", "약물", "heart failure"]},
    {"question": "부정맥이란?", "keywords": ["부정맥", "심장", "박동", "리듬", "arrhythmia"]},
    {"question": "당뇨병 진단 기준은?", "keywords": ["당뇨", "혈당", "HbA1c", "공복", "진단", "diabetes", "glucose", "fasting"]},
    {"question": "당뇨병 합병증은?", "keywords": ["당뇨", "합병증", "신경병증", "망막", "신장", "complication", "neuropathy", "retinopathy"]},
    {"question": "인슐린 주사 방법은?", "keywords": ["인슐린", "주사", "투여", "피하", "insulin", "injection"]},
    {"question": "당뇨병 식이요법은?", "keywords": ["당뇨", "식이", "탄수화물", "혈당", "diabetes", "diet", "carbohydrate"]},
    {"question": "저혈당 증상과 대처는?", "keywords": ["저혈당", "증상", "포도당", "당", "hypoglycemia"]},
    {"question": "당뇨병성 케톤산증이란?", "keywords": ["케톤", "산증", "당뇨", "DKA", "ketoacidosis"]},
    {"question": "폐렴 증상은?", "keywords": ["폐렴", "기침", "발열", "호흡", "가래", "pneumonia", "cough", "fever"]},
    {"question": "천식 치료는?", "keywords": ["천식", "흡입기", "기관지", "스테로이드", "asthma", "inhaler"]},
    {"question": "COPD란?", "keywords": ["COPD", "만성폐쇄성", "폐", "호흡", "chronic obstructive"]},
    {"question": "결핵 치료 기간은?", "keywords": ["결핵", "치료", "항결핵제", "개월", "tuberculosis", "TB"]},
    {"question": "기관지염 증상은?", "keywords": ["기관지염", "기침", "가래", "호흡기", "bronchitis"]},
    {"question": "폐암 초기 증상은?", "keywords": ["폐암", "증상", "기침", "혈담", "lung cancer"]},
    {"question": "위염 치료는?", "keywords": ["위염", "위", "치료", "제산제", "PPI", "gastritis"]},
    {"question": "위궤양 원인은?", "keywords": ["위궤양", "헬리코박터", "NSAID", "위", "ulcer", "H. pylori"]},
    {"question": "역류성 식도염 증상은?", "keywords": ["역류", "식도염", "가슴쓰림", "속쓰림", "GERD", "reflux", "heartburn"]},
    {"question": "간경변 합병증은?", "keywords": ["간경변", "복수", "정맥류", "간", "cirrhosis", "ascites"]},
    {"question": "지방간 치료는?", "keywords": ["지방간", "간", "체중", "운동", "fatty liver", "NAFLD"]},
    {"question": "담석증 증상은?", "keywords": ["담석", "담낭", "통증", "복통", "gallstone", "cholecystitis"]},
    {"question": "만성신부전 치료는?", "keywords": ["신부전", "신장", "투석", "치료", "kidney", "renal failure", "dialysis"]},
    {"question": "신장결석 증상은?", "keywords": ["신장결석", "결석", "통증", "혈뇨", "kidney stone", "nephrolithiasis"]},
    {"question": "단백뇨 원인은?", "keywords": ["단백뇨", "신장", "사구체", "proteinuria"]},
    {"question": "혈액투석이란?", "keywords": ["투석", "혈액", "신장", "dialysis", "hemodialysis"]},
    {"question": "갑상선기능항진증 증상은?", "keywords": ["갑상선", "항진", "증상", "빈맥", "체중감소", "hyperthyroidism", "thyroid"]},
    {"question": "갑상선기능저하증 치료는?", "keywords": ["갑상선", "저하", "레보티록신", "호르몬", "hypothyroidism", "levothyroxine"]},
    {"question": "골다공증 예방은?", "keywords": ["골다공증", "칼슘", "비타민D", "뼈", "osteoporosis", "calcium"]},
    {"question": "통풍 치료는?", "keywords": ["통풍", "요산", "콜히친", "치료", "gout", "uric acid"]},
    {"question": "소아 발열 대처법은?", "keywords": ["소아", "발열", "열", "해열제", "아이", "fever", "child", "pediatric"]},
    {"question": "영유아 예방접종 스케줄은?", "keywords": ["예방접종", "백신", "영유아", "스케줄", "vaccination", "immunization"]},
    {"question": "소아 설사 치료는?", "keywords": ["소아", "설사", "수분", "탈수", "diarrhea", "dehydration"]},
    {"question": "아토피 피부염 관리는?", "keywords": ["아토피", "피부", "보습", "스테로이드", "atopic", "dermatitis", "eczema"]},
    {"question": "소아 비만 관리는?", "keywords": ["소아", "비만", "체중", "식이", "obesity", "overweight"]},
    {"question": "성장 장애 원인은?", "keywords": ["성장", "키", "호르몬", "저신장", "growth", "short stature"]},
    {"question": "임신 초기 증상은?", "keywords": ["임신", "초기", "증상", "입덧", "pregnancy", "morning sickness", "nausea"]},
    {"question": "임신성 당뇨란?", "keywords": ["임신", "당뇨", "혈당", "gestational", "GDM"]},
    {"question": "자연분만과 제왕절개 차이는?", "keywords": ["분만", "제왕절개", "자연", "출산", "delivery", "cesarean", "vaginal"]},
    {"question": "산후우울증 증상은?", "keywords": ["산후", "우울", "증상", "출산", "postpartum", "depression"]},
    {"question": "자궁근종이란?", "keywords": ["자궁", "근종", "양성", "종양", "fibroid", "myoma", "uterine"]},
    {"question": "생리통 완화 방법은?", "keywords": ["생리통", "월경", "통증", "진통제", "dysmenorrhea", "menstrual"]},
    {"question": "허리디스크 증상은?", "keywords": ["디스크", "허리", "요통", "추간판", "herniated", "lumbar", "back pain"]},
    {"question": "골절 응급처치는?", "keywords": ["골절", "응급", "부목", "고정", "fracture", "splint"]},
    {"question": "관절염 종류는?", "keywords": ["관절염", "류마티스", "퇴행성", "관절", "arthritis", "rheumatoid", "osteoarthritis"]},
    {"question": "오십견 치료는?", "keywords": ["오십견", "어깨", "운동", "치료", "frozen shoulder", "adhesive capsulitis"]},
    {"question": "뇌졸중 전조 증상은?", "keywords": ["뇌졸중", "증상", "마비", "언어장애", "stroke", "paralysis", "aphasia"]},
    {"question": "파킨슨병 증상은?", "keywords": ["파킨슨", "떨림", "진전", "운동", "Parkinson", "tremor"]},
    {"question": "편두통 치료는?", "keywords": ["편두통", "두통", "치료", "트립탄", "migraine", "headache"]},
    {"question": "치매 초기 증상은?", "keywords": ["치매", "기억력", "인지", "알츠하이머", "dementia", "Alzheimer", "memory"]},
    {"question": "우울증 증상은?", "keywords": ["우울", "증상", "기분", "무기력", "depression", "mood"]},
    {"question": "불안장애 치료는?", "keywords": ["불안", "치료", "약물", "인지행동", "anxiety", "CBT"]},
    {"question": "수면장애 원인은?", "keywords": ["수면", "불면", "잠", "원인", "insomnia", "sleep disorder"]},
    {"question": "공황장애란?", "keywords": ["공황", "발작", "불안", "호흡", "panic", "attack"]},
    {"question": "여드름 치료는?", "keywords": ["여드름", "피부", "치료", "레티노이드", "acne", "retinoid"]},
    {"question": "건선이란?", "keywords": ["건선", "피부", "각질", "면역", "psoriasis"]},
    {"question": "대상포진 증상은?", "keywords": ["대상포진", "수포", "통증", "신경", "herpes zoster", "shingles"]},
    {"question": "두드러기 원인은?", "keywords": ["두드러기", "알레르기", "가려움", "피부", "urticaria", "hives"]},
    {"question": "백내장 수술은?", "keywords": ["백내장", "수술", "수정체", "시력", "cataract", "lens"]},
    {"question": "녹내장이란?", "keywords": ["녹내장", "안압", "시신경", "시야", "glaucoma", "intraocular pressure"]},
    {"question": "중이염 치료는?", "keywords": ["중이염", "귀", "항생제", "치료", "otitis media", "ear infection"]},
    {"question": "비염 종류는?", "keywords": ["비염", "코", "알레르기", "만성", "rhinitis", "allergic"]},
    {"question": "전립선비대증 증상은?", "keywords": ["전립선", "비대", "배뇨", "소변", "BPH", "prostate", "urination"]},
    {"question": "요로감염 치료는?", "keywords": ["요로", "감염", "방광염", "항생제", "UTI", "urinary tract"]},
    {"question": "신장암 증상은?", "keywords": ["신장암", "혈뇨", "종양", "renal", "kidney cancer"]},
    {"question": "심폐소생술 방법은?", "keywords": ["심폐소생술", "CPR", "흉부압박", "인공호흡", "cardiopulmonary", "resuscitation"]},
    {"question": "화상 응급처치는?", "keywords": ["화상", "응급", "냉각", "처치", "burn", "first aid"]},
    {"question": "식중독 증상은?", "keywords": ["식중독", "구토", "설사", "복통", "food poisoning"]},
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
    """3가지 검색 방식 비교 평가"""
    print("=" * 70)
    print("🔬 MediScanner 검색 방식 비교 (시맨틱 vs BM25 vs RRF)")
    print("=" * 70)
    print(f"   평가 문항: {len(EVAL_QA)}개")
    print("=" * 70)
    
    model, collection, bm25, bm25_ids = load_models()
    
    # 결과 집계
    results = {
        "semantic": {"top3": 0, "top5": 0, "top10": 0},
        "bm25": {"top3": 0, "top5": 0, "top10": 0},
        "rrf": {"top3": 0, "top5": 0, "top10": 0},
    }
    
    print("\n📊 평가 시작...")
    print("-" * 70)
    
    for i, qa in enumerate(EVAL_QA):
        question = qa["question"]
        keywords = qa["keywords"]
        
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
        
        # 진행 상황 (Top-5 기준)
        sem_mark = "✅" if sem_hit["top5"] else "❌"
        bm25_mark = "✅" if bm25_hit["top5"] else "❌"
        rrf_mark = "✅" if rrf_hit["top5"] else "❌"
        print(f"   [{i+1:2d}/{len(EVAL_QA)}] Sem:{sem_mark} BM25:{bm25_mark} RRF:{rrf_mark} | {question}")
    
    # 결과 출력
    total = len(EVAL_QA)
    
    print("\n" + "=" * 70)
    print("📊 검색 방식 비교 결과")
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
    
    # 차이 분석
    print(f"\n   📈 RRF vs 시맨틱 차이:")
    diff3 = rrf['top3']/total*100 - sem['top3']/total*100
    diff5 = rrf['top5']/total*100 - sem['top5']/total*100
    diff10 = rrf['top10']/total*100 - sem['top10']/total*100
    
    sign3 = "+" if diff3 >= 0 else ""
    sign5 = "+" if diff5 >= 0 else ""
    sign10 = "+" if diff10 >= 0 else ""
    
    print(f"      Top-3: {sign3}{diff3:.1f}%p | Top-5: {sign5}{diff5:.1f}%p | Top-10: {sign10}{diff10:.1f}%p")
    
    if diff5 == 0:
        print(f"\n   ⚠️ 주의: RRF와 시맨틱 결과가 동일함!")
        print(f"      → 현재 평가 기준이 너무 느슨할 수 있음")
        print(f"      → 또는 multilingual-e5가 너무 좋아서 시맨틱만으로 충분")
    
    print("\n" + "=" * 70)
    print("🎉 비교 완료!")
    print("=" * 70)


if __name__ == "__main__":
    evaluate()
