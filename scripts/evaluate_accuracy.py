"""
MediScanner 검색 정확도 평가 스크립트 (독립형)
- multilingual-e5-large + 800자 청크 평가
- Hit Rate@K 측정 (Top-3, Top-5, Top-10)
"""

import os
import sys
import re
import pickle
from pathlib import Path

# ============================================================
# 설정값 (직접 정의)
# ============================================================
EMBEDDING_MODEL = "intfloat/multilingual-e5-large"
EMBEDDING_DIMENSION = 1024
CHROMA_DB_PATH = "./data/chroma_db"
COLLECTION_NAME = "medical_knowledge"
E5_QUERY_PREFIX = "query: "
CHUNK_SIZE = 800

# ============================================================
# 평가용 QA 데이터 (72개 의료 질문 + 정답 키워드)
# ============================================================
EVAL_QA = [
    # 내과 - 고혈압/심혈관
    {"question": "고혈압 치료 방법은?", "keywords": ["고혈압", "혈압", "치료", "약물", "생활습관", "hypertension", "blood pressure"]},
    {"question": "고혈압 환자의 식이요법은?", "keywords": ["고혈압", "저염", "나트륨", "식이", "DASH", "sodium", "diet"]},
    {"question": "고혈압 약의 종류는?", "keywords": ["ACE", "ARB", "칼슘채널", "이뇨제", "베타차단제", "antihypertensive"]},
    {"question": "심근경색 증상은?", "keywords": ["심근경색", "흉통", "가슴", "통증", "심장", "myocardial", "infarction", "chest pain"]},
    {"question": "심부전 치료는?", "keywords": ["심부전", "심장", "치료", "약물", "heart failure"]},
    {"question": "부정맥이란?", "keywords": ["부정맥", "심장", "박동", "리듬", "arrhythmia"]},
    
    # 내과 - 당뇨
    {"question": "당뇨병 진단 기준은?", "keywords": ["당뇨", "혈당", "HbA1c", "공복", "진단", "diabetes", "glucose", "fasting"]},
    {"question": "당뇨병 합병증은?", "keywords": ["당뇨", "합병증", "신경병증", "망막", "신장", "complication", "neuropathy", "retinopathy"]},
    {"question": "인슐린 주사 방법은?", "keywords": ["인슐린", "주사", "투여", "피하", "insulin", "injection"]},
    {"question": "당뇨병 식이요법은?", "keywords": ["당뇨", "식이", "탄수화물", "혈당", "diabetes", "diet", "carbohydrate"]},
    {"question": "저혈당 증상과 대처는?", "keywords": ["저혈당", "증상", "포도당", "당", "hypoglycemia"]},
    {"question": "당뇨병성 케톤산증이란?", "keywords": ["케톤", "산증", "당뇨", "DKA", "ketoacidosis"]},
    
    # 내과 - 호흡기
    {"question": "폐렴 증상은?", "keywords": ["폐렴", "기침", "발열", "호흡", "가래", "pneumonia", "cough", "fever"]},
    {"question": "천식 치료는?", "keywords": ["천식", "흡입기", "기관지", "스테로이드", "asthma", "inhaler"]},
    {"question": "COPD란?", "keywords": ["COPD", "만성폐쇄성", "폐", "호흡", "chronic obstructive"]},
    {"question": "결핵 치료 기간은?", "keywords": ["결핵", "치료", "항결핵제", "개월", "tuberculosis", "TB"]},
    {"question": "기관지염 증상은?", "keywords": ["기관지염", "기침", "가래", "호흡기", "bronchitis"]},
    {"question": "폐암 초기 증상은?", "keywords": ["폐암", "증상", "기침", "혈담", "lung cancer"]},
    
    # 내과 - 소화기
    {"question": "위염 치료는?", "keywords": ["위염", "위", "치료", "제산제", "PPI", "gastritis"]},
    {"question": "위궤양 원인은?", "keywords": ["위궤양", "헬리코박터", "NSAID", "위", "ulcer", "H. pylori"]},
    {"question": "역류성 식도염 증상은?", "keywords": ["역류", "식도염", "가슴쓰림", "속쓰림", "GERD", "reflux", "heartburn"]},
    {"question": "간경변 합병증은?", "keywords": ["간경변", "복수", "정맥류", "간", "cirrhosis", "ascites"]},
    {"question": "지방간 치료는?", "keywords": ["지방간", "간", "체중", "운동", "fatty liver", "NAFLD"]},
    {"question": "담석증 증상은?", "keywords": ["담석", "담낭", "통증", "복통", "gallstone", "cholecystitis"]},
    
    # 내과 - 신장
    {"question": "만성신부전 치료는?", "keywords": ["신부전", "신장", "투석", "치료", "kidney", "renal failure", "dialysis"]},
    {"question": "신장결석 증상은?", "keywords": ["신장결석", "결석", "통증", "혈뇨", "kidney stone", "nephrolithiasis"]},
    {"question": "단백뇨 원인은?", "keywords": ["단백뇨", "신장", "사구체", "proteinuria"]},
    {"question": "혈액투석이란?", "keywords": ["투석", "혈액", "신장", "dialysis", "hemodialysis"]},
    
    # 내과 - 내분비
    {"question": "갑상선기능항진증 증상은?", "keywords": ["갑상선", "항진", "증상", "빈맥", "체중감소", "hyperthyroidism", "thyroid"]},
    {"question": "갑상선기능저하증 치료는?", "keywords": ["갑상선", "저하", "레보티록신", "호르몬", "hypothyroidism", "levothyroxine"]},
    {"question": "골다공증 예방은?", "keywords": ["골다공증", "칼슘", "비타민D", "뼈", "osteoporosis", "calcium"]},
    {"question": "통풍 치료는?", "keywords": ["통풍", "요산", "콜히친", "치료", "gout", "uric acid"]},
    
    # 소아청소년과
    {"question": "소아 발열 대처법은?", "keywords": ["소아", "발열", "열", "해열제", "아이", "fever", "child", "pediatric"]},
    {"question": "영유아 예방접종 스케줄은?", "keywords": ["예방접종", "백신", "영유아", "스케줄", "vaccination", "immunization"]},
    {"question": "소아 설사 치료는?", "keywords": ["소아", "설사", "수분", "탈수", "diarrhea", "dehydration"]},
    {"question": "아토피 피부염 관리는?", "keywords": ["아토피", "피부", "보습", "스테로이드", "atopic", "dermatitis", "eczema"]},
    {"question": "소아 비만 관리는?", "keywords": ["소아", "비만", "체중", "식이", "obesity", "overweight"]},
    {"question": "성장 장애 원인은?", "keywords": ["성장", "키", "호르몬", "저신장", "growth", "short stature"]},
    
    # 산부인과
    {"question": "임신 초기 증상은?", "keywords": ["임신", "초기", "증상", "입덧", "pregnancy", "morning sickness", "nausea"]},
    {"question": "임신성 당뇨란?", "keywords": ["임신", "당뇨", "혈당", "gestational", "GDM"]},
    {"question": "자연분만과 제왕절개 차이는?", "keywords": ["분만", "제왕절개", "자연", "출산", "delivery", "cesarean", "vaginal"]},
    {"question": "산후우울증 증상은?", "keywords": ["산후", "우울", "증상", "출산", "postpartum", "depression"]},
    {"question": "자궁근종이란?", "keywords": ["자궁", "근종", "양성", "종양", "fibroid", "myoma", "uterine"]},
    {"question": "생리통 완화 방법은?", "keywords": ["생리통", "월경", "통증", "진통제", "dysmenorrhea", "menstrual"]},
    
    # 정형외과/신경외과
    {"question": "허리디스크 증상은?", "keywords": ["디스크", "허리", "요통", "추간판", "herniated", "lumbar", "back pain"]},
    {"question": "골절 응급처치는?", "keywords": ["골절", "응급", "부목", "고정", "fracture", "splint"]},
    {"question": "관절염 종류는?", "keywords": ["관절염", "류마티스", "퇴행성", "관절", "arthritis", "rheumatoid", "osteoarthritis"]},
    {"question": "오십견 치료는?", "keywords": ["오십견", "어깨", "운동", "치료", "frozen shoulder", "adhesive capsulitis"]},
    
    # 신경과
    {"question": "뇌졸중 전조 증상은?", "keywords": ["뇌졸중", "증상", "마비", "언어장애", "stroke", "paralysis", "aphasia"]},
    {"question": "파킨슨병 증상은?", "keywords": ["파킨슨", "떨림", "진전", "운동", "Parkinson", "tremor"]},
    {"question": "편두통 치료는?", "keywords": ["편두통", "두통", "치료", "트립탄", "migraine", "headache"]},
    {"question": "치매 초기 증상은?", "keywords": ["치매", "기억력", "인지", "알츠하이머", "dementia", "Alzheimer", "memory"]},
    
    # 정신건강의학과
    {"question": "우울증 증상은?", "keywords": ["우울", "증상", "기분", "무기력", "depression", "mood"]},
    {"question": "불안장애 치료는?", "keywords": ["불안", "치료", "약물", "인지행동", "anxiety", "CBT"]},
    {"question": "수면장애 원인은?", "keywords": ["수면", "불면", "잠", "원인", "insomnia", "sleep disorder"]},
    {"question": "공황장애란?", "keywords": ["공황", "발작", "불안", "호흡", "panic", "attack"]},
    
    # 피부과
    {"question": "여드름 치료는?", "keywords": ["여드름", "피부", "치료", "레티노이드", "acne", "retinoid"]},
    {"question": "건선이란?", "keywords": ["건선", "피부", "각질", "면역", "psoriasis"]},
    {"question": "대상포진 증상은?", "keywords": ["대상포진", "수포", "통증", "신경", "herpes zoster", "shingles"]},
    {"question": "두드러기 원인은?", "keywords": ["두드러기", "알레르기", "가려움", "피부", "urticaria", "hives"]},
    
    # 안과/이비인후과
    {"question": "백내장 수술은?", "keywords": ["백내장", "수술", "수정체", "시력", "cataract", "lens"]},
    {"question": "녹내장이란?", "keywords": ["녹내장", "안압", "시신경", "시야", "glaucoma", "intraocular pressure"]},
    {"question": "중이염 치료는?", "keywords": ["중이염", "귀", "항생제", "치료", "otitis media", "ear infection"]},
    {"question": "비염 종류는?", "keywords": ["비염", "코", "알레르기", "만성", "rhinitis", "allergic"]},
    
    # 비뇨기과
    {"question": "전립선비대증 증상은?", "keywords": ["전립선", "비대", "배뇨", "소변", "BPH", "prostate", "urination"]},
    {"question": "요로감염 치료는?", "keywords": ["요로", "감염", "방광염", "항생제", "UTI", "urinary tract"]},
    {"question": "신장암 증상은?", "keywords": ["신장암", "혈뇨", "종양", "renal", "kidney cancer"]},
    
    # 응급의학
    {"question": "심폐소생술 방법은?", "keywords": ["심폐소생술", "CPR", "흉부압박", "인공호흡", "cardiopulmonary", "resuscitation"]},
    {"question": "화상 응급처치는?", "keywords": ["화상", "응급", "냉각", "처치", "burn", "first aid"]},
    {"question": "식중독 증상은?", "keywords": ["식중독", "구토", "설사", "복통", "food poisoning"]},
]


def load_embedding_model():
    """임베딩 모델 로드"""
    from sentence_transformers import SentenceTransformer
    print("📦 임베딩 모델 로딩 중...")
    model = SentenceTransformer(EMBEDDING_MODEL)
    print(f"   모델: {EMBEDDING_MODEL}")
    print(f"   차원: {EMBEDDING_DIMENSION}")
    return model


def load_chromadb():
    """ChromaDB 로드"""
    import chromadb
    print("📦 ChromaDB 로딩 중...")
    client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    collection = client.get_collection(name=COLLECTION_NAME)
    count = collection.count()
    print(f"   컬렉션: {COLLECTION_NAME}")
    print(f"   문서 수: {count:,}개")
    return collection


def load_bm25_cache():
    """BM25 캐시 로드 (자동 구조 감지)"""
    cache_path = Path("bm25_cache.pkl")
    if not cache_path.exists():
        print("⚠️ BM25 캐시 없음 - 시맨틱 검색만 사용")
        return None, None, None
    
    print("📦 BM25 캐시 로딩 중...")
    with open(cache_path, "rb") as f:
        cache = pickle.load(f)
    
    # 캐시 구조 확인
    print(f"   캐시 키: {list(cache.keys())}")
    
    bm25 = cache.get("bm25")
    
    # doc_ids 또는 ids 키 확인
    doc_ids = cache.get("doc_ids") or cache.get("ids") or cache.get("document_ids")
    
    # corpus 키 확인 (문서 내용)
    corpus = cache.get("corpus") or cache.get("documents") or cache.get("texts")
    
    if bm25 is None:
        print("⚠️ BM25 객체 없음 - 시맨틱 검색만 사용")
        return None, None, None
    
    if doc_ids is not None:
        print(f"   문서 ID 수: {len(doc_ids):,}개")
    elif corpus is not None:
        print(f"   문서 수 (corpus): {len(corpus):,}개")
        # corpus가 있으면 인덱스를 doc_ids로 사용
        doc_ids = list(range(len(corpus)))
    else:
        print("⚠️ 문서 ID/corpus 없음 - 시맨틱 검색만 사용")
        return None, None, None
    
    return bm25, doc_ids, corpus


def embed_query(model, query: str) -> list:
    """쿼리 임베딩 (E5 prefix 적용)"""
    prefixed_query = f"{E5_QUERY_PREFIX}{query}"
    embedding = model.encode(prefixed_query, normalize_embeddings=True)
    return embedding.tolist()


def search_semantic(collection, query_embedding, top_k=20):
    """시맨틱 검색"""
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        include=["documents", "metadatas"]
    )
    
    docs = []
    for i, doc_id in enumerate(results["ids"][0]):
        docs.append({
            "id": doc_id,
            "content": results["documents"][0][i],
            "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
            "rank": i + 1,
            "source": "semantic"
        })
    return docs


def search_bm25(bm25, doc_ids, query: str, top_k=20):
    """BM25 검색"""
    if bm25 is None or doc_ids is None:
        return []
    
    # 한국어 토크나이징 (2글자 이상)
    tokens = [t for t in re.split(r'\s+', query) if len(t) >= 2]
    if not tokens:
        return []
    
    scores = bm25.get_scores(tokens)
    top_indices = scores.argsort()[-top_k:][::-1]
    
    docs = []
    for rank, idx in enumerate(top_indices):
        if scores[idx] > 0:
            # doc_ids가 정수 리스트인 경우 문자열로 변환
            if isinstance(doc_ids[idx], int):
                doc_id = f"chunk_{idx}"
            else:
                doc_id = doc_ids[idx]
            docs.append({
                "id": doc_id,
                "score": float(scores[idx]),
                "rank": rank + 1,
                "source": "bm25"
            })
    return docs


def rrf_fusion(semantic_docs, bm25_docs, k=60, top_k=10):
    """RRF 융합"""
    rrf_scores = {}
    
    # 시맨틱 검색 결과
    for doc in semantic_docs:
        doc_id = doc["id"]
        rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1 / (k + doc["rank"])
    
    # BM25 검색 결과
    for doc in bm25_docs:
        doc_id = doc["id"]
        rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1 / (k + doc["rank"])
    
    # 정렬
    sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)
    return sorted_ids[:top_k]


def check_hit_semantic(semantic_docs: list, keywords: list) -> dict:
    """시맨틱 검색 결과에서 Hit 확인 (문서 내용 직접 사용)"""
    results = {"top3": False, "top5": False, "top10": False}
    
    for i, doc in enumerate(semantic_docs[:10]):
        content = doc.get("content", "").lower()
        
        # 키워드 중 하나라도 포함되면 Hit
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
    """정확도 평가 실행"""
    print("=" * 60)
    print("🔬 MediScanner 검색 정확도 평가")
    print("=" * 60)
    print(f"   임베딩 모델: {EMBEDDING_MODEL}")
    print(f"   청크 크기: {CHUNK_SIZE}자")
    print(f"   평가 문항: {len(EVAL_QA)}개")
    print("=" * 60)
    
    # 모델 및 DB 로드
    model = load_embedding_model()
    collection = load_chromadb()
    bm25, bm25_doc_ids, corpus = load_bm25_cache()
    
    use_bm25 = bm25 is not None and bm25_doc_ids is not None
    search_method = "RRF 하이브리드 (시맨틱 + BM25)" if use_bm25 else "시맨틱 검색만"
    print(f"\n   검색 방식: {search_method}")
    
    print("\n" + "=" * 60)
    print("📊 평가 시작...")
    print("=" * 60)
    
    # 결과 집계
    hits = {"top3": 0, "top5": 0, "top10": 0}
    
    for i, qa in enumerate(EVAL_QA):
        question = qa["question"]
        keywords = qa["keywords"]
        
        # 1. 쿼리 임베딩
        query_embedding = embed_query(model, question)
        
        # 2. 시맨틱 검색
        semantic_docs = search_semantic(collection, query_embedding, top_k=20)
        
        if use_bm25:
            # 3. BM25 검색
            bm25_docs = search_bm25(bm25, bm25_doc_ids, question, top_k=20)
            
            # 4. RRF 융합 후 ChromaDB에서 문서 가져오기
            final_ids = rrf_fusion(semantic_docs, bm25_docs, k=60, top_k=10)
            
            # ChromaDB에서 문서 내용 가져오기
            final_docs = []
            for doc_id in final_ids:
                try:
                    doc_result = collection.get(ids=[doc_id], include=["documents"])
                    if doc_result["documents"]:
                        final_docs.append({"id": doc_id, "content": doc_result["documents"][0]})
                except:
                    pass
            
            # Hit 확인
            hit_result = {"top3": False, "top5": False, "top10": False}
            for j, doc in enumerate(final_docs[:10]):
                content = doc.get("content", "").lower()
                hit = any(kw.lower() in content for kw in keywords)
                if hit:
                    if j < 3:
                        hit_result["top3"] = True
                        hit_result["top5"] = True
                        hit_result["top10"] = True
                        break
                    elif j < 5:
                        hit_result["top5"] = True
                        hit_result["top10"] = True
                    elif j < 10:
                        hit_result["top10"] = True
        else:
            # 시맨틱만 사용
            hit_result = check_hit_semantic(semantic_docs, keywords)
        
        if hit_result["top3"]:
            hits["top3"] += 1
        if hit_result["top5"]:
            hits["top5"] += 1
        if hit_result["top10"]:
            hits["top10"] += 1
        
        # 진행 상황 출력
        status = "✅" if hit_result["top5"] else "❌"
        print(f"   [{i+1:2d}/{len(EVAL_QA)}] {status} {question}")
    
    # 결과 출력
    print("\n" + "=" * 60)
    print("📊 평가 결과")
    print("=" * 60)
    
    total = len(EVAL_QA)
    
    print(f"\n   📈 Hit Rate 결과:")
    print(f"   ┌─────────────┬──────────┬──────────┐")
    print(f"   │   Top-K     │   Hit    │ Hit Rate │")
    print(f"   ├─────────────┼──────────┼──────────┤")
    print(f"   │   Top-3     │  {hits['top3']:2d}/{total}  │  {hits['top3']/total*100:5.1f}%  │")
    print(f"   │   Top-5     │  {hits['top5']:2d}/{total}  │  {hits['top5']/total*100:5.1f}%  │")
    print(f"   │   Top-10    │  {hits['top10']:2d}/{total}  │  {hits['top10']/total*100:5.1f}%  │")
    print(f"   └─────────────┴──────────┴──────────┘")
    
    print(f"\n   📋 설정:")
    print(f"      - 임베딩 모델: {EMBEDDING_MODEL}")
    print(f"      - 청크 크기: {CHUNK_SIZE}자")
    print(f"      - 검색 방식: {search_method}")
    
    # 기존 결과와 비교
    print(f"\n   📊 기존 결과와 비교 (ko-sroberta + 500자):")
    print(f"   ┌─────────────┬──────────┬──────────┬──────────┐")
    print(f"   │   Top-K     │   기존   │   신규   │   변화   │")
    print(f"   ├─────────────┼──────────┼──────────┼──────────┤")
    
    old_results = {"top3": 77.0, "top5": 81.2, "top10": 84.4}
    new_top3 = hits['top3']/total*100
    new_top5 = hits['top5']/total*100
    new_top10 = hits['top10']/total*100
    
    diff3 = new_top3 - old_results["top3"]
    diff5 = new_top5 - old_results["top5"]
    diff10 = new_top10 - old_results["top10"]
    
    sign3 = "+" if diff3 >= 0 else ""
    sign5 = "+" if diff5 >= 0 else ""
    sign10 = "+" if diff10 >= 0 else ""
    
    print(f"   │   Top-3     │  {old_results['top3']:5.1f}%  │  {new_top3:5.1f}%  │ {sign3}{diff3:5.1f}%p │")
    print(f"   │   Top-5     │  {old_results['top5']:5.1f}%  │  {new_top5:5.1f}%  │ {sign5}{diff5:5.1f}%p │")
    print(f"   │   Top-10    │  {old_results['top10']:5.1f}%  │  {new_top10:5.1f}%  │ {sign10}{diff10:5.1f}%p │")
    print(f"   └─────────────┴──────────┴──────────┴──────────┘")
    
    print("\n" + "=" * 60)
    print("🎉 평가 완료!")
    print("=" * 60)
    
    return {
        "top3": new_top3,
        "top5": new_top5,
        "top10": new_top10
    }


if __name__ == "__main__":
    evaluate()
