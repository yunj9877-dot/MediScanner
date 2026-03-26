"""
닥터가디언 청크 사이즈 비교 실험
================================
10K 샘플 데이터로 300/500/800자 청크 사이즈를 비교합니다.
검색 방법은 RRF(하이브리드)로만 실행합니다.
(이유: 이전 실험에서 RRF가 가장 높은 성능을 보였으므로)

사용법:
  python scripts/evaluate_chunk_size.py
"""

import json
import os
import sys
import random
import time
import shutil
from pathlib import Path
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import EMBEDDING_MODEL, RETRIEVAL_K, RRF_K


# ============================================================
# 1. 데이터 로드
# ============================================================
def load_documents(data_dir, max_docs=10000):
    """원천데이터에서 문서 로드"""
    json_files = sorted(Path(data_dir).glob("*.json"))
    print(f"📂 원천데이터: {data_dir}")
    print(f"📄 JSON 파일: {len(json_files):,}개")
    
    documents = []
    for f in json_files[:max_docs]:
        try:
            with open(f, "r", encoding="utf-8-sig") as fp:
                data = json.load(fp)
                content = ""
                for key in ["text", "content", "paragraph", "body", "document"]:
                    if key in data and data[key]:
                        content = str(data[key])
                        break
                if not content:
                    content = json.dumps(data, ensure_ascii=False)
                
                documents.append({
                    "content": content,
                    "source_spec": data.get("source_spec", ""),
                    "c_id": data.get("c_id", str(f.stem)),
                    "filename": f.stem,
                })
        except:
            continue
    
    print(f"✅ 로드: {len(documents):,}건\n")
    return documents


def load_qa_data(label_dir, max_samples=500):
    """라벨링 데이터에서 QA 쌍 로드"""
    qa_pairs = []
    json_files = list(Path(label_dir).glob("*.json"))
    
    for f in json_files:
        try:
            with open(f, "r", encoding="utf-8-sig") as fp:
                data = json.load(fp)
                if "question" in data and "answer" in data:
                    qa_pairs.append({
                        "question": data["question"],
                        "answer": data["answer"],
                    })
        except:
            continue
    
    if len(qa_pairs) > max_samples:
        random.seed(42)
        qa_pairs = random.sample(qa_pairs, max_samples)
    
    print(f"✅ QA 쌍: {len(qa_pairs):,}개 (seed=42)\n")
    return qa_pairs


# ============================================================
# 2. 청킹
# ============================================================
def chunk_text(text, chunk_size, overlap=50):
    """텍스트를 chunk_size 단위로 분할"""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap
        if start < 0:
            start = 0
        if end >= len(text):
            break
    return chunks if chunks else [text]


def process_documents(documents, chunk_size):
    """문서 → 청크 변환"""
    ids, metadatas, texts = [], [], []
    for doc in documents:
        chunks = chunk_text(doc["content"], chunk_size)
        for i, chunk in enumerate(chunks):
            ids.append(f"{doc['filename']}_{doc['c_id']}_c{i}")
            texts.append(chunk)
            metadatas.append({
                "source_spec": doc["source_spec"],
                "c_id": doc["c_id"],
                "chunk_index": i,
                "filename": doc["filename"],
            })
    return ids, metadatas, texts


# ============================================================
# 3. 임베딩 + RRF 평가
# ============================================================
def build_and_evaluate(documents, qa_pairs, chunk_size, db_path, top_k=5):
    """특정 청크 사이즈로 임베딩 → RRF 평가"""
    import chromadb
    from chromadb.utils import embedding_functions
    from rank_bm25 import BM25Okapi
    import re
    
    print(f"\n{'='*60}")
    print(f"📊 청크 사이즈: {chunk_size}자 (overlap: 50자)")
    print(f"{'='*60}")
    
    # 청킹
    print(f"✂️ 청킹 중...")
    ids, metadatas, texts = process_documents(documents, chunk_size)
    print(f"   {len(documents):,}건 → {len(ids):,}개 청크")
    
    # ChromaDB 구축
    print(f"🔧 ChromaDB 임베딩 중...")
    if os.path.exists(db_path):
        shutil.rmtree(db_path)
    
    embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=EMBEDDING_MODEL
    )
    client = chromadb.PersistentClient(path=db_path)
    collection = client.create_collection(
        name="chunk_test",
        embedding_function=embedding_fn,
    )
    
    BATCH_SIZE = 100
    total = len(ids)
    start_time = time.time()
    
    for i in range(0, total, BATCH_SIZE):
        end = min(i + BATCH_SIZE, total)
        collection.add(
            ids=ids[i:end],
            documents=texts[i:end],
            metadatas=metadatas[i:end],
        )
        if end % 10000 == 0 or end == total:
            elapsed = time.time() - start_time
            pct = end / total * 100
            print(f"   [{pct:5.1f}%] {end:,}/{total:,} ({elapsed:.0f}초)")
    
    embed_time = time.time() - start_time
    print(f"✅ 임베딩 완료: {collection.count():,}개 ({embed_time:.0f}초)")
    
    # BM25 인덱스 구축
    print(f"📦 BM25 인덱스 구축 중...")
    tokenized = [[w for w in doc.split() if len(w) >= 2] for doc in texts]
    bm25 = BM25Okapi(tokenized)
    print(f"✅ BM25 인덱스 완료")
    
    # RRF 평가
    print(f"\n📊 RRF Hit Rate@{top_k} 평가 중 (500개 QA)...")
    hits = 0
    total_qa = len(qa_pairs)
    start_eval = time.time()
    
    # ID → index 매핑 (빠른 검색용)
    id_to_idx = {doc_id: idx for idx, doc_id in enumerate(ids)}
    
    for i, qa in enumerate(qa_pairs):
        # 정답 키워드 추출
        answer = re.sub(r'^\d+\)\s*', '', qa["answer"].strip())
        keywords = [w for w in answer.split() if len(w) >= 2]
        
        if not keywords:
            total_qa -= 1
            continue
        
        try:
            # 1) 시맨틱 검색
            n_results = min(RETRIEVAL_K, collection.count())
            semantic_results = collection.query(
                query_texts=[qa["question"]],
                n_results=n_results,
            )
            
            # 2) BM25 검색
            query_tokens = [w for w in qa["question"].split() if len(w) >= 2]
            bm25_scores = bm25.get_scores(query_tokens)
            bm25_top_idx = np.argsort(bm25_scores)[::-1][:RETRIEVAL_K]
            
            # 3) RRF 융합
            rrf_scores = {}
            
            if semantic_results and semantic_results["ids"] and semantic_results["ids"][0]:
                for rank, doc_id in enumerate(semantic_results["ids"][0]):
                    rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1 / (RRF_K + rank + 1)
            
            for rank, idx in enumerate(bm25_top_idx):
                if idx < len(ids):
                    doc_id = ids[idx]
                    rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1 / (RRF_K + rank + 1)
            
            sorted_results = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
            
            # 적중 확인
            hit = False
            for doc_id, score in sorted_results:
                idx = id_to_idx.get(doc_id, -1)
                if idx >= 0:
                    doc_text = texts[idx]
                    for keyword in keywords:
                        if keyword in doc_text:
                            hit = True
                            break
                if hit:
                    break
            
            if hit:
                hits += 1
                
        except:
            total_qa -= 1
            continue
        
        if (i + 1) % 50 == 0:
            elapsed = time.time() - start_eval
            pct = (i + 1) / len(qa_pairs) * 100
            print(f"   [{pct:5.1f}%] {i+1}/{len(qa_pairs)} (적중: {hits}, 경과: {elapsed:.0f}초)")
    
    eval_time = time.time() - start_eval
    hit_rate = hits / total_qa * 100 if total_qa > 0 else 0
    
    print(f"\n   ✅ 청크 {chunk_size}자 | RRF Top-{top_k} Hit Rate: {hit_rate:.1f}% ({hits}/{total_qa}) [{eval_time:.1f}초]")
    
    # 정리
    del collection
    del client
    del bm25
    
    import gc
    gc.collect()
    
    import time as t
    t.sleep(2)  # Windows 파일 잠금 해제 대기
    
    try:
        if os.path.exists(db_path):
            shutil.rmtree(db_path)
    except:
        print(f"   ⚠️ 임시 폴더 삭제 실패 (무시해도 됨): {db_path}")
    
    return {
        "chunk_size": chunk_size,
        "num_chunks": len(ids),
        "hit_rate": round(hit_rate, 1),
        "hits": hits,
        "total": total_qa,
        "embed_time": round(embed_time, 1),
        "eval_time": round(eval_time, 1),
    }


# ============================================================
# 4. 메인
# ============================================================
def main():
    print("=" * 60)
    print("🏥 닥터가디언 - 청크 사이즈 비교 실험")
    print("=" * 60)
    print("   데이터: 10K 샘플 (필수의료 원천데이터)")
    print("   검색: RRF 하이브리드만 (이전 실험에서 최고 성능)")
    print("   비교: 300자 / 500자 / 800자")
    print("   평가: Hit Rate@5 (500개 QA)")
    print()
    
    data_dir = "raw_data/1_필수의료 의학지식 데이터/3.개방데이터/1.데이터/Training/01.원천데이터"
    label_dir = "raw_data/1_필수의료 의학지식 데이터/3.개방데이터/1.데이터/Training/02.라벨링데이터"
    
    documents = load_documents(data_dir, max_docs=10000)
    qa_pairs = load_qa_data(label_dir, max_samples=500)
    
    if not documents or not qa_pairs:
        print("❌ 데이터 로드 실패")
        sys.exit(1)
    
    chunk_sizes = [500, 800]  # 300자는 완료됨 (68.4%)
    results = [
        {"chunk_size": 300, "num_chunks": 113405, "hit_rate": 68.4, "hits": 342, "total": 500, "embed_time": 4530.0, "eval_time": 451.7},
    ]
    
    for cs in chunk_sizes:
        db_path = f"./data/chunk_test_{cs}"
        result = build_and_evaluate(documents, qa_pairs, cs, db_path, top_k=5)
        results.append(result)
    
    # 결과 요약
    print(f"\n{'='*60}")
    print(f"📋 청크 사이즈 비교 결과 (10K 샘플, RRF Top-5)")
    print(f"{'='*60}\n")
    
    print(f"{'청크 사이즈':<12} | {'청크 수':>10} | {'Hit Rate':>10} | {'임베딩':>10} | {'평가':>10}")
    print("-" * 65)
    for r in results:
        print(f"{r['chunk_size']}자{'':<8} | {r['num_chunks']:>10,} | {r['hit_rate']:>9.1f}% | {r['embed_time']:>9.1f}초 | {r['eval_time']:>9.1f}초")
    
    # 최적 청크 사이즈
    best = max(results, key=lambda x: x["hit_rate"])
    print(f"\n🏆 최적 청크 사이즈: {best['chunk_size']}자 (Hit Rate: {best['hit_rate']}%)")
    
    if best["chunk_size"] != 500:
        print(f"⚠️ 현재 서비스는 500자 → {best['chunk_size']}자로 재임베딩 권장")
    else:
        print(f"✅ 현재 서비스(500자)가 최적! 재임베딩 불필요")
    
    # JSON 저장
    os.makedirs("eval_data", exist_ok=True)
    output_path = "eval_data/chunk_size_results.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({"results": results, "best_chunk_size": best["chunk_size"]}, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 결과 저장: {output_path}")


if __name__ == "__main__":
    main()
