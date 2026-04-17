"""
MediScanner 3모델 검색 정확도 비교 평가
==========================================
ko-sroberta / E5-small / E5-large
각 모델의 ChromaDB에서 시맨틱·BM25·RRF 방식으로
200개 질문에 대한 Hit Rate@3/5/10 을 실측합니다.

선행 조건:
  - data/chroma_db/           (E5-large, 기존)
  - data/chroma_db_kosroberta/ (ko-sroberta)
  - data/chroma_db_e5small/   (E5-small)
  - models/ko-sroberta/
  - models/e5-small/

실행:
  python evaluate_three_models.py
  python evaluate_three_models.py --models e5large        # 특정 모델만
  python evaluate_three_models.py --models kosroberta e5small

결과:
  results/eval_three_models_YYYYMMDD_HHMMSS.csv
  results/eval_three_models_YYYYMMDD_HHMMSS_summary.txt
"""

import argparse
import csv
import json
import logging
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import chromadb
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
# 모델 설정
# ═══════════════════════════════════════════════════════════════
MODEL_CONFIGS = {
    "e5large": {
        "label":           "E5-large",
        "model_path":      Path("./models/e5-large"),
        "hf_id":           "intfloat/multilingual-e5-large",
        "chroma_path":     Path("./data/chroma_db"),
        "collection_name": "medical_knowledge",
        "query_prefix":    "query: ",
    },
    "kosroberta": {
        "label":           "ko-sroberta",
        "model_path":      Path("./models/ko-sroberta"),
        "hf_id":           "jhgan/ko-sroberta-multitask",
        "chroma_path":     Path("./data/chroma_db_kosroberta"),
        "collection_name": "medical_knowledge_kr",
        "query_prefix":    "",
    },
    "e5small": {
        "label":           "E5-small",
        "model_path":      Path("./models/e5-small"),
        "hf_id":           "intfloat/multilingual-e5-small",
        "chroma_path":     Path("./data/chroma_db_e5small"),
        "collection_name": "medical_knowledge_e5s",
        "query_prefix":    "query: ",
    },
}

TOP_K_LIST = [3, 5, 10]
RESULTS_DIR = Path("./results")

# ═══════════════════════════════════════════════════════════════
# 평가 질문 — evaluate_200_questions.py 에서 import
# (기본 100개 + 추론 100개, 총 200개)
# ═══════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════
# 평가 질문 — evaluate_200_questions_v2.py 에서 import
# Hit 기준: must 키워드 1개 이상 AND context 키워드 1개 이상
# ═══════════════════════════════════════════════════════════════
try:
    from evaluate_200_questions_v3 import EVAL_QA_200
    ALL_QUESTIONS = EVAL_QA_200
    log.info(f"질문 로드: evaluate_200_questions_v3.py ({len(ALL_QUESTIONS)}개)")
except ImportError:
    log.error("evaluate_200_questions_v3.py 파일이 없습니다. 같은 폴더에 넣어주세요.")
    sys.exit(1)


# ═══════════════════════════════════════════════════════════════
# 토크나이저 (BM25용) — kiwipiepy 형태소 분석
# ═══════════════════════════════════════════════════════════════
try:
    from kiwipiepy import Kiwi
    _kiwi = Kiwi()
    def tokenize_ko(text: str) -> list[str]:
        """kiwipiepy 형태소 분석 — 고혈압약 → [고혈압, 약] 분리"""
        tokens = [token.form for token in _kiwi.tokenize(text.lower())
                  if len(token.form) > 1]
        return tokens
    log.info("토크나이저: kiwipiepy 형태소 분석 사용")
except ImportError:
    def tokenize_ko(text: str) -> list[str]:
        """폴백: 공백 + 정규식 기반"""
        tokens = re.findall(r"[가-힣a-z0-9]+", text.lower())
        return [t for t in tokens if len(t) > 1]
    log.warning("kiwipiepy 없음 — 기본 토크나이저 사용")


# ═══════════════════════════════════════════════════════════════
# 모델 로드
# ═══════════════════════════════════════════════════════════════
def load_model(cfg: dict) -> SentenceTransformer:
    model_path = cfg["model_path"]
    if model_path.exists():
        log.info(f"  로컬 모델 로드: {model_path}")
        return SentenceTransformer(str(model_path))
    else:
        log.warning(f"  로컬 모델 없음, HuggingFace에서 다운로드: {cfg['hf_id']}")
        return SentenceTransformer(cfg["hf_id"])


def load_chroma(cfg: dict):
    client = chromadb.PersistentClient(path=str(cfg["chroma_path"]))
    collection = client.get_collection(cfg["collection_name"])
    count = collection.count()
    log.info(f"  ChromaDB 로드: {cfg['chroma_path'].name} — {count:,}개 청크")
    return collection


# ═══════════════════════════════════════════════════════════════
# 검색 및 평가 함수
# ═══════════════════════════════════════════════════════════════
def semantic_search(model, collection, query: str, prefix: str, top_k: int) -> list[str]:
    q_text = prefix + query
    embedding = model.encode([q_text], normalize_embeddings=True)[0].tolist()
    results = collection.query(query_embeddings=[embedding], n_results=top_k)
    return results["documents"][0] if results["documents"] else []


def bm25_search(bm25: BM25Okapi, corpus_texts: list[str], query: str, top_k: int) -> list[str]:
    tokens = tokenize_ko(query)
    if not tokens:
        return []
    scores = bm25.get_scores(tokens)
    top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
    return [corpus_texts[i] for i in top_indices]


def check_hit(docs: list[str], must: list[str], context: list[str], top_k_list: list[int]) -> dict[int, bool]:
    """
    Hit 기준: must 키워드 1개 이상 AND context 키워드 1개 이상
    둘 다 있어야 Hit, 하나라도 없으면 Miss
    """
    results = {k: False for k in top_k_list}
    must_lower    = [kw.lower() for kw in must]
    context_lower = [kw.lower() for kw in context]
    for i, doc in enumerate(docs):
        doc_lower = doc.lower()
        must_hit    = any(kw in doc_lower for kw in must_lower)
        context_hit = any(kw in doc_lower for kw in context_lower)
        if must_hit and context_hit:
            for k in top_k_list:
                if i < k:
                    results[k] = True
    return results


# ═══════════════════════════════════════════════════════════════
# 단일 모델 평가
# ═══════════════════════════════════════════════════════════════
def evaluate_model(model_key: str, cfg: dict, questions: list[dict]) -> dict:
    label = cfg["label"]
    log.info(f"\n{'='*60}")
    log.info(f"  [{label}] 평가 시작")
    log.info(f"{'='*60}")

    # 모델 & DB 로드
    model = load_model(cfg)
    collection = load_chroma(cfg)

    # BM25 인덱스 구축
    log.info("  BM25 인덱스 구축 중...")
    t0 = time.time()
    all_docs = collection.get(include=["documents"])["documents"]
    tokenized = [tokenize_ko(doc) for doc in all_docs]
    bm25 = BM25Okapi(tokenized)
    log.info(f"  BM25 완료: {len(all_docs):,}개 문서, {time.time()-t0:.1f}초")

    # 평가
    results_sem  = {k: 0 for k in TOP_K_LIST}
    results_bm25 = {k: 0 for k in TOP_K_LIST}
    results_rrf  = {k: 0 for k in TOP_K_LIST}
    n = len(questions)

    for i, item in enumerate(questions):
        q       = item["question"]
        must    = item["must"]
        context = item["context"]

        # 시맨틱
        sem_docs  = semantic_search(model, collection, q, cfg["query_prefix"], max(TOP_K_LIST))
        # BM25
        bm25_docs = bm25_search(bm25, all_docs, q, max(TOP_K_LIST))
        # RRF 융합 — 각 문서의 순위 점수 합산 (k=60)
        rrf_scores = {}
        for rank, doc in enumerate(sem_docs):
            rrf_scores[doc] = rrf_scores.get(doc, 0) + 1 / (60 + rank + 1)
        for rank, doc in enumerate(bm25_docs):
            rrf_scores[doc] = rrf_scores.get(doc, 0) + 1 / (60 + rank + 1)
        rrf_combined = [doc for doc, _ in sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)][:max(TOP_K_LIST)]

        sem_hit  = check_hit(sem_docs,     must, context, TOP_K_LIST)
        bm25_hit = check_hit(bm25_docs,    must, context, TOP_K_LIST)
        rrf_hit  = check_hit(rrf_combined, must, context, TOP_K_LIST)

        for k in TOP_K_LIST:
            if sem_hit[k]:  results_sem[k]  += 1
            if bm25_hit[k]: results_bm25[k] += 1
            if rrf_hit[k]:  results_rrf[k]  += 1

        if (i + 1) % 50 == 0:
            log.info(f"  진행: {i+1}/{n}")

    # 퍼센트 변환
    def pct(d):
        return {k: round(v / n * 100, 1) for k, v in d.items()}

    return {
        "label":    label,
        "n":        n,
        "semantic": pct(results_sem),
        "bm25":     pct(results_bm25),
        "rrf":      pct(results_rrf),
    }


# ═══════════════════════════════════════════════════════════════
# 결과 출력 & 저장
# ═══════════════════════════════════════════════════════════════
def print_summary(all_results: list[dict]):
    print("\n" + "=" * 72)
    print("  MediScanner 3모델 검색 정확도 비교 결과 (200개 질문)")
    print("=" * 72)
    header = f"{'모델':<16} {'방식':<10} {'@3':>7} {'@5':>7} {'@10':>7}"
    print(header)
    print("-" * 72)
    for r in all_results:
        for method_name, method_key in [("시맨틱", "semantic"), ("BM25", "bm25"), ("RRF", "rrf")]:
            vals = r[method_key]
            mark = " ★" if method_key == "rrf" else ""
            print(f"{r['label']:<16} {method_name:<10} "
                  f"{vals[3]:>6.1f}% {vals[5]:>6.1f}% {vals[10]:>6.1f}%{mark}")
        print("-" * 72)
    print()


def save_csv(all_results: list[dict], ts: str):
    RESULTS_DIR.mkdir(exist_ok=True)
    path = RESULTS_DIR / f"eval_three_models_{ts}.csv"
    rows = []
    for r in all_results:
        for method_key in ["semantic", "bm25", "rrf"]:
            vals = r[method_key]
            rows.append({
                "model":    r["label"],
                "method":   method_key,
                "top3":     vals[3],
                "top5":     vals[5],
                "top10":    vals[10],
                "n_questions": r["n"],
            })
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["model", "method", "top3", "top5", "top10", "n_questions"])
        writer.writeheader()
        writer.writerows(rows)
    log.info(f"  CSV 저장: {path}")
    return path


def save_summary(all_results: list[dict], ts: str):
    RESULTS_DIR.mkdir(exist_ok=True)
    path = RESULTS_DIR / f"eval_three_models_{ts}_summary.txt"
    lines = ["MediScanner 3모델 검색 정확도 비교\n", f"측정 일시: {ts}\n", "=" * 60 + "\n"]
    for r in all_results:
        lines.append(f"\n[{r['label']}]  (총 {r['n']}개 질문)\n")
        for method_name, method_key in [("시맨틱", "semantic"), ("BM25", "bm25"), ("RRF", "rrf")]:
            vals = r[method_key]
            lines.append(f"  {method_name:<10}  @3: {vals[3]:>5.1f}%  @5: {vals[5]:>5.1f}%  @10: {vals[10]:>5.1f}%\n")
        lines.append("-" * 60 + "\n")
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(lines)
    log.info(f"  요약 저장: {path}")


# ═══════════════════════════════════════════════════════════════
# 메인
# ═══════════════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(description="MediScanner 3모델 평가")
    parser.add_argument(
        "--models", nargs="+",
        choices=list(MODEL_CONFIGS.keys()),
        default=list(MODEL_CONFIGS.keys()),
        help="평가할 모델 키 (기본: 전체)"
    )
    args = parser.parse_args()

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log.info(f"평가 시작: {ts}")
    log.info(f"대상 모델: {args.models}")
    log.info(f"질문 수: {len(ALL_QUESTIONS)}개")

    total_start = time.time()
    all_results = []

    for model_key in args.models:
        cfg = MODEL_CONFIGS[model_key]
        if not cfg["chroma_path"].exists():
            log.warning(f"  [{cfg['label']}] ChromaDB 없음, 건너뜀: {cfg['chroma_path']}")
            continue
        result = evaluate_model(model_key, cfg, ALL_QUESTIONS)
        all_results.append(result)

    if not all_results:
        log.error("평가 가능한 모델이 없습니다.")
        sys.exit(1)

    print_summary(all_results)
    save_csv(all_results, ts)
    save_summary(all_results, ts)

    elapsed = time.time() - total_start
    log.info(f"\n전체 완료: {elapsed/60:.1f}분")
    log.info(f"결과 저장 위치: {RESULTS_DIR}/")


if __name__ == "__main__":
    main()
