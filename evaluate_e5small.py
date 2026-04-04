"""
MediScanner E5-small 검색 정확도 평가
======================================
임베딩 모델: multilingual-E5-small (384차원)
검색 엔진: hnswlib 직접 검색 (ChromaDB 미사용)

비교 항목:
  - 검색 방식: 시맨틱 / BM25 / RRF 하이브리드
  - Top-K: @3 / @5 / @10
  - 질문 세트: 기본 100개 / 추론 100개 / 전체 200개

Hit 판정 (v1 기준):
  must + context 키워드 중 하나라도 문서에 있으면 Hit

실행:
  $env:PYTHONPATH = "."; python evaluate_e5small.py
"""

import json
import pickle
import re
import time
import os
import csv
from datetime import datetime
from pathlib import Path

import numpy as np

# ============================================================
# 설정
# ============================================================
E5_SMALL_MODEL_PATH = "./models/e5-small"
HNSW_INDEX_PATH     = "./data/chroma_db_e5small/hnsw_index.bin"
HNSW_IDS_PATH       = "./data/chroma_db_e5small/hnsw_ids.json"
CHUNKS_PKL_PATH     = "./temp_chunks_source_only.pkl"
BM25_CACHE_PATH     = "./data/bm25_cache_e5small.pkl"
RESULTS_DIR         = "./results"
QUERY_PREFIX        = "query: "
TOP_K_LIST          = [3, 5, 10]
RRF_K               = 60
BM25_TOP_N          = 20
SEMANTIC_TOP_N      = 20

# ============================================================
# 질문 데이터 로드
# ============================================================
from evaluate_200_questions_v3 import BASIC_QA_100, HARD_QA_100, EVAL_QA_200

QUESTION_SETS = {
    "기본(Basic) 100": BASIC_QA_100,
    "추론(Hard) 100":  HARD_QA_100,
    "전체(All) 200":   EVAL_QA_200,
}

# ============================================================
# Hit 판정
# ============================================================
def is_hit(text: str, must: list, context: list) -> bool:
    """must + context 통합 — 하나라도 포함 시 Hit (v1 기준)"""
    text_lower = text.lower()
    all_keywords = must + context
    return any(kw.lower() in text_lower for kw in all_keywords)

# ============================================================
# 한국어 토크나이저 (BM25용)
# ============================================================
def tokenize(text: str) -> list:
    try:
        from kiwipiepy import Kiwi
        kiwi = Kiwi()
        tokens = []
        for token in kiwi.tokenize(text):
            if len(token.form) > 1:
                tokens.append(token.form.lower())
        return tokens
    except ImportError:
        text = re.sub(r'[^\w\s가-힣a-zA-Z0-9]', ' ', text)
        tokens = text.lower().split()
        return [t for t in tokens if len(t) > 1]

# ============================================================
# 모델 및 인덱스 로드
# ============================================================
print("=" * 60)
print("MediScanner E5-small 검색 성능 평가")
print("=" * 60)

print("\n[1/4] E5-small 모델 로딩 중...")
t0 = time.time()
from sentence_transformers import SentenceTransformer
model = SentenceTransformer(E5_SMALL_MODEL_PATH)
print(f"      완료 ({time.time()-t0:.1f}초)")

print("[2/4] hnswlib 인덱스 로딩 중...")
t0 = time.time()
import hnswlib
hnsw_index = hnswlib.Index(space='cosine', dim=384)
hnsw_index.load_index(HNSW_INDEX_PATH)
hnsw_index.set_ef(200)
with open(HNSW_IDS_PATH, 'r', encoding='utf-8') as f:
    hnsw_ids = json.load(f)  # list: [chunk_id, ...] — index = hnswlib label
print(f"      완료 ({time.time()-t0:.1f}초)")

print("[3/4] 청크 텍스트 로딩 중...")
t0 = time.time()
with open(CHUNKS_PKL_PATH, 'rb') as f:
    raw = pickle.load(f)
# {chunks: [...], chunk_ids: [...], metadatas: [...]} 구조
chunks_list    = raw['chunks']
chunk_ids_list = raw['chunk_ids']
chunks_dict = {chunk_ids_list[i]: chunks_list[i] for i in range(len(chunk_ids_list))}
print(f"      완료 ({time.time()-t0:.1f}초), {len(chunks_dict):,}개 청크")

print("[4/4] BM25 캐시 로딩 중...")
t0 = time.time()
bm25_available = False
bm25 = None
bm25_ids = []
if Path(BM25_CACHE_PATH).exists():
    with open(BM25_CACHE_PATH, 'rb') as f:
        bm25_data = pickle.load(f)
    bm25 = bm25_data.get('bm25')
    bm25_ids = bm25_data.get('ids', [])
    bm25_available = bm25 is not None
    print(f"      완료 ({time.time()-t0:.1f}초), {len(bm25_ids):,}개 문서")
else:
    print("      ⚠ BM25 캐시 없음 — BM25/RRF 테스트 건너뜀")

# ============================================================
# 검색 함수
# ============================================================
def semantic_search(query: str, top_k: int) -> list:
    """hnswlib 시맨틱 검색 → [chunk_id, ...]"""
    vec = model.encode([QUERY_PREFIX + query], normalize_embeddings=True)[0]
    labels, _ = hnsw_index.knn_query(vec, k=min(top_k, hnsw_index.get_current_count()))
    results = []
    for label in labels[0]:
        if label < len(hnsw_ids):
            chunk_id = hnsw_ids[label]
            if chunk_id in chunks_dict:
                results.append(chunk_id)
    return results

def bm25_search(query: str, top_n: int) -> list:
    """BM25 키워드 검색 → [chunk_id, ...]"""
    if not bm25_available:
        return []
    tokens = tokenize(query)
    if not tokens:
        return []
    scores = bm25.get_scores(tokens)
    top_indices = np.argsort(scores)[::-1][:top_n]
    results = []
    for idx in top_indices:
        if scores[idx] > 0 and idx < len(bm25_ids):
            chunk_id = bm25_ids[idx]
            if chunk_id in chunks_dict:
                results.append(chunk_id)
    return results

def rrf_search(query: str, top_k: int) -> list:
    """RRF 하이브리드 검색 → [chunk_id, ...]"""
    sem_results = semantic_search(query, SEMANTIC_TOP_N)
    bm_results  = bm25_search(query, BM25_TOP_N)

    rrf_scores = {}
    for rank, chunk_id in enumerate(sem_results):
        rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0) + 1 / (RRF_K + rank + 1)
    for rank, chunk_id in enumerate(bm_results):
        rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0) + 1 / (RRF_K + rank + 1)

    sorted_ids = sorted(rrf_scores, key=rrf_scores.get, reverse=True)
    return sorted_ids[:top_k]

# ============================================================
# 단일 세트 평가 함수
# ============================================================
def evaluate_set(qa_list: list, search_mode: str, top_k: int) -> dict:
    """
    반환: {hits: int, total: int, hit_rate: float,
           category_hits: {cat: [hit, total]}}
    """
    hits = 0
    total = len(qa_list)
    category_hits = {}

    for qa in qa_list:
        question = qa['question']
        must     = qa['must']
        context  = qa['context']
        category = qa.get('category', '기타')

        # 검색
        if search_mode == 'semantic':
            result_ids = semantic_search(question, top_k)
        elif search_mode == 'bm25':
            result_ids = bm25_search(question, top_k)
        else:  # rrf
            result_ids = rrf_search(question, top_k)

        # Hit 판정
        hit = False
        for chunk_id in result_ids[:top_k]:
            text = chunks_dict.get(chunk_id, '')
            if isinstance(text, dict):
                text = text.get('text', '')
            if is_hit(str(text), must, context):
                hit = True
                break

        if hit:
            hits += 1

        # 카테고리별 집계
        if category not in category_hits:
            category_hits[category] = [0, 0]
        category_hits[category][1] += 1
        if hit:
            category_hits[category][0] += 1

    return {
        'hits': hits,
        'total': total,
        'hit_rate': round(hits / total * 100, 1),
        'category_hits': category_hits,
    }

# ============================================================
# 전체 평가 실행
# ============================================================
SEARCH_MODES = ['semantic', 'bm25', 'rrf'] if bm25_available else ['semantic']
MODE_LABELS  = {'semantic': '시맨틱', 'bm25': 'BM25', 'rrf': 'RRF'}

results_table = {}  # (set_name, mode, k) → hit_rate

print("\n" + "=" * 60)
print("평가 시작")
print("=" * 60)

total_tests = len(QUESTION_SETS) * len(SEARCH_MODES) * len(TOP_K_LIST)
done = 0
eval_start = time.time()

for set_name, qa_list in QUESTION_SETS.items():
    for mode in SEARCH_MODES:
        for k in TOP_K_LIST:
            done += 1
            print(f"  [{done:2d}/{total_tests}] {set_name} | {MODE_LABELS[mode]} | Top-{k} ... ", end='', flush=True)
            t0 = time.time()
            res = evaluate_set(qa_list, mode, k)
            elapsed = time.time() - t0
            results_table[(set_name, mode, k)] = res
            print(f"{res['hit_rate']:5.1f}%  ({elapsed:.1f}초)")

total_elapsed = time.time() - eval_start
print(f"\n총 소요 시간: {total_elapsed:.1f}초")

# ============================================================
# 결과 출력 (표 형식)
# ============================================================
print("\n" + "=" * 70)
print("📊 E5-small 검색 방식별 Hit Rate 비교")
print("=" * 70)

header = f"{'질문 세트':<18} {'방식':<8}"
for k in TOP_K_LIST:
    header += f"  @{k:2d}"
print(header)
print("-" * 70)

for set_name in QUESTION_SETS:
    for mode in SEARCH_MODES:
        row = f"{set_name:<18} {MODE_LABELS[mode]:<8}"
        for k in TOP_K_LIST:
            hr = results_table[(set_name, mode, k)]['hit_rate']
            row += f"  {hr:5.1f}%"
        print(row)
    print("-" * 70)

# ============================================================
# 카테고리별 결과 출력 (RRF @5 기준)
# ============================================================
if 'rrf' in SEARCH_MODES:
    print("\n📋 카테고리별 Hit Rate (RRF @5)")
    print("-" * 60)
    for set_name in QUESTION_SETS:
        res = results_table[(set_name, 'rrf', 5)]
        print(f"\n[{set_name}]")
        for cat, (h, t) in sorted(res['category_hits'].items()):
            pct = round(h/t*100, 1) if t > 0 else 0
            bar = '█' * int(pct/5) + '░' * (20 - int(pct/5))
            print(f"  {cat:<16} {bar}  {pct:5.1f}%  ({h}/{t})")

# ============================================================
# 결과 저장
# ============================================================
Path(RESULTS_DIR).mkdir(exist_ok=True)
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

# CSV 저장
csv_path = f"{RESULTS_DIR}/eval_e5small_{timestamp}.csv"
with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
    writer = csv.writer(f)
    writer.writerow(['질문세트', '검색방식', 'Top-K', 'Hit수', '전체수', 'Hit Rate(%)'])
    for (set_name, mode, k), res in results_table.items():
        writer.writerow([set_name, MODE_LABELS[mode], k,
                         res['hits'], res['total'], res['hit_rate']])

# 요약 TXT 저장
txt_path = f"{RESULTS_DIR}/eval_e5small_{timestamp}_summary.txt"
with open(txt_path, 'w', encoding='utf-8') as f:
    f.write("MediScanner E5-small 검색 성능 평가 결과\n")
    f.write(f"실행일시: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    f.write(f"임베딩 모델: multilingual-E5-small (384차원)\n")
    f.write(f"검색 아키텍처: hnswlib 직접 검색 + BM25 RRF\n")
    f.write(f"평가 데이터: 200개 (기본 100 + 추론 100)\n")
    f.write(f"Hit 판정: must AND context (v3 기준)\n\n")
    f.write("=" * 60 + "\n")
    f.write(f"{'질문 세트':<18} {'방식':<8}")
    for k in TOP_K_LIST:
        f.write(f"  @{k:2d}")
    f.write("\n" + "-" * 60 + "\n")
    for set_name in QUESTION_SETS:
        for mode in SEARCH_MODES:
            row = f"{set_name:<18} {MODE_LABELS[mode]:<8}"
            for k in TOP_K_LIST:
                hr = results_table[(set_name, mode, k)]['hit_rate']
                row += f"  {hr:5.1f}%"
            f.write(row + "\n")
        f.write("-" * 60 + "\n")

print(f"\n✅ 결과 저장 완료")
print(f"   CSV: {csv_path}")
print(f"   TXT: {txt_path}")
print("\n평가 완료!")
