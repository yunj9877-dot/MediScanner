"""
닥터가디언 성능 평가 스크립트
==============================
Hit Rate@K (적중률) 평가:
- 질문을 검색했을 때, 상위 K개 결과 안에 정답 키워드가 포함되는 비율 측정
- 3가지 검색 방법 비교: 시맨틱만 vs RRF(하이브리드) vs RRF+Reranker

사용법:
  python scripts/evaluate.py --sample 500
"""

import json
import os
import sys
import random
import time
from pathlib import Path

# 프로젝트 루트를 path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import CHROMA_DB_PATH, COLLECTION_NAME, EMBEDDING_MODEL, TOP_K, RETRIEVAL_K, RRF_K, RERANKER_MODEL


def load_qa_data(label_dir, max_samples=500):
    """라벨링 데이터에서 QA 쌍 로드"""
    qa_pairs = []
    json_files = list(Path(label_dir).glob("*.json"))
    
    print(f"📂 라벨링 데이터 폴더: {label_dir}")
    print(f"📄 JSON 파일 수: {len(json_files):,}개")
    
    for f in json_files:
        try:
            with open(f, "r", encoding="utf-8-sig") as fp:
                data = json.load(fp)
                if "question" in data and "answer" in data:
                    qa_pairs.append({
                        "qa_id": data.get("qa_id", ""),
                        "question": data["question"],
                        "answer": data["answer"],
                    })
        except:
            continue
    
    print(f"✅ QA 쌍 로드: {len(qa_pairs):,}개")
    
    # 랜덤 샘플링
    if len(qa_pairs) > max_samples:
        random.seed(42)  # 재현 가능하도록 시드 고정
        qa_pairs = random.sample(qa_pairs, max_samples)
        print(f"🎲 랜덤 샘플: {max_samples}개 추출 (seed=42)")
    
    return qa_pairs


def extract_answer_keywords(answer_text):
    """정답에서 핵심 키워드 추출"""
    # 객관식 번호 제거: "4) 메타콜린 기관지유발검사" → "메타콜린 기관지유발검사"
    import re
    cleaned = re.sub(r'^\d+\)\s*', '', answer_text.strip())
    
    # 2글자 이상 단어만 추출
    keywords = [w for w in cleaned.split() if len(w) >= 2]
    
    return keywords


def check_hit(search_results, answer_keywords):
    """검색 결과에 정답 키워드가 포함되는지 확인"""
    if not answer_keywords:
        return False
    
    for doc in search_results:
        text = doc.get("text", "")
        # 키워드 중 하나라도 포함되면 적중
        for keyword in answer_keywords:
            if keyword in text:
                return True
    
    return False


def evaluate_semantic_only(engine, query, top_k):
    """시맨틱 검색만 사용"""
    results = engine._search_semantic(query, top_k=top_k)
    return [{"text": r["text"], "metadata": r["metadata"]} for r in results]


def evaluate_rrf(engine, query, top_k):
    """RRF 하이브리드 검색 (시맨틱 + BM25)"""
    semantic = engine._search_semantic(query, top_k=RETRIEVAL_K)
    bm25 = engine._search_bm25(query, top_k=RETRIEVAL_K)
    fused = engine._rrf_fusion(semantic, bm25)
    return [{"text": r["text"], "metadata": r["metadata"]} for r in fused[:top_k]]


def evaluate_rrf_reranker(engine, query, top_k):
    """RRF + Reranker (전체 파이프라인)"""
    semantic = engine._search_semantic(query, top_k=RETRIEVAL_K)
    bm25 = engine._search_bm25(query, top_k=RETRIEVAL_K)
    fused = engine._rrf_fusion(semantic, bm25)
    reranked = engine._rerank(query, fused[:RETRIEVAL_K], top_k=top_k)
    return [{"text": r["text"], "metadata": r["metadata"]} for r in reranked]


def run_evaluation(engine, qa_pairs, top_k_values=[3, 5, 10]):
    """전체 평가 실행"""
    
    methods = {
        "시맨틱만": evaluate_semantic_only,
        "RRF (하이브리드)": evaluate_rrf,
        "RRF + Reranker": evaluate_rrf_reranker,
    }
    
    results = {}
    
    for method_name, method_fn in methods.items():
        print(f"\n{'='*60}")
        print(f"📊 평가 중: {method_name}")
        print(f"{'='*60}")
        
        results[method_name] = {}
        
        for k in top_k_values:
            hits = 0
            total = len(qa_pairs)
            start = time.time()
            
            for i, qa in enumerate(qa_pairs):
                # 정답 키워드 추출
                keywords = extract_answer_keywords(qa["answer"])
                
                if not keywords:
                    total -= 1
                    continue
                
                # 검색 실행
                try:
                    search_results = method_fn(engine, qa["question"], top_k=k)
                    
                    # 적중 확인
                    if check_hit(search_results, keywords):
                        hits += 1
                except Exception as e:
                    total -= 1
                    continue
                
                # 진행률 (50개마다)
                if (i + 1) % 50 == 0:
                    elapsed = time.time() - start
                    pct = (i + 1) / len(qa_pairs) * 100
                    print(f"   [{pct:5.1f}%] {i+1}/{len(qa_pairs)}  "
                          f"(적중: {hits}, 경과: {elapsed:.0f}초)")
            
            elapsed = time.time() - start
            hit_rate = hits / total * 100 if total > 0 else 0
            
            results[method_name][k] = {
                "hits": hits,
                "total": total,
                "hit_rate": hit_rate,
                "elapsed": elapsed,
            }
            
            print(f"\n   ✅ Top-{k} Hit Rate: {hit_rate:.1f}% "
                  f"({hits}/{total}) [{elapsed:.1f}초]")
    
    return results


def print_summary(results, qa_count):
    """결과 요약 출력"""
    print(f"\n{'='*60}")
    print(f"📋 성능 평가 결과 요약 (QA 샘플: {qa_count}개)")
    print(f"{'='*60}\n")
    
    # 헤더
    k_values = sorted(list(list(results.values())[0].keys()))
    header = f"{'검색 방법':<20}"
    for k in k_values:
        header += f" | Top-{k:>2}"
    print(header)
    print("-" * len(header))
    
    # 각 방법별 결과
    for method_name, k_results in results.items():
        row = f"{method_name:<20}"
        for k in k_values:
            rate = k_results[k]["hit_rate"]
            row += f" | {rate:5.1f}%"
        print(row)
    
    print(f"\n{'='*60}")
    
    # 개선율 계산
    if "시맨틱만" in results and "RRF + Reranker" in results:
        for k in k_values:
            base = results["시맨틱만"][k]["hit_rate"]
            best = results["RRF + Reranker"][k]["hit_rate"]
            improvement = best - base
            print(f"📈 Top-{k} 개선율: 시맨틱만 → RRF+Reranker = +{improvement:.1f}%p")
    
    # JSON으로도 저장
    output_path = "eval_data/evaluation_results.json"
    os.makedirs("eval_data", exist_ok=True)
    
    save_data = {
        "qa_count": qa_count,
        "results": {}
    }
    for method, k_results in results.items():
        save_data["results"][method] = {}
        for k, data in k_results.items():
            save_data["results"][method][f"top_{k}"] = {
                "hit_rate": round(data["hit_rate"], 2),
                "hits": data["hits"],
                "total": data["total"],
                "elapsed_seconds": round(data["elapsed"], 1),
            }
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(save_data, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 결과 저장: {output_path}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="닥터가디언 성능 평가")
    parser.add_argument("--label_dir", type=str, 
                        default="raw_data/1_필수의료 의학지식 데이터/3.개방데이터/1.데이터/Training/02.라벨링데이터",
                        help="라벨링 데이터 폴더 경로")
    parser.add_argument("--sample", type=int, default=500, help="평가할 QA 샘플 수")
    parser.add_argument("--top_k", type=str, default="3,5,10", help="평가할 Top-K 값 (쉼표 구분)")
    args = parser.parse_args()
    
    top_k_values = [int(k) for k in args.top_k.split(",")]
    
    print("=" * 60)
    print("🏥 닥터가디언 - 성능 평가 (Hit Rate@K)")
    print("=" * 60)
    print(f"   평가 방식: Hit Rate@K (적중률)")
    print(f"   설명: 질문의 정답 키워드가 검색 결과 Top-K 안에 포함되는 비율")
    print(f"   샘플 수: {args.sample}개")
    print(f"   Top-K: {top_k_values}")
    print(f"   비교: 시맨틱만 vs RRF(하이브리드) vs RRF+Reranker")
    print()
    
    # 1) QA 데이터 로드
    qa_pairs = load_qa_data(args.label_dir, max_samples=args.sample)
    
    if not qa_pairs:
        print("❌ QA 데이터가 없습니다. 경로를 확인하세요.")
        sys.exit(1)
    
    # 2) RAG 엔진 초기화
    print(f"\n🔧 RAG 엔진 초기화 중...")
    from app.rag_engine import RAGEngine
    engine = RAGEngine()
    print(f"✅ RAG 엔진 준비 완료\n")
    
    # 3) 평가 실행
    results = run_evaluation(engine, qa_pairs, top_k_values)
    
    # 4) 결과 요약
    print_summary(results, len(qa_pairs))


if __name__ == "__main__":
    main()
