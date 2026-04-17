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
    log.info(f"  ChromaDB 로드: {cfg['chroma_path'].name}")
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
    Hit 기준: 언어 구분 없이 전체 키워드 중 2개 이상 포함
    """
    results = {k: False for k in top_k_list}
    all_kw = [kw.lower() for kw in (must + context)]
    for i, doc in enumerate(docs):
        doc_lower = doc.lower()
        matched = sum(1 for kw in all_kw if kw in doc_lower)
        if matched >= 2:
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

    # BM25 인덱스 구축 (캐시 사용)
    import pickle, hashlib
    cache_dir = Path("./bm25_cache")
    cache_dir.mkdir(exist_ok=True)
    # ChromaDB 경로 기반으로 캐시 파일명 결정 (모델별 독립)
    cache_key = hashlib.md5(str(cfg["chroma_path"]).encode()).hexdigest()[:8]
    cache_path = cache_dir / f"bm25_{model_key}_{cache_key}.pkl"

    t0 = time.time()
    if cache_path.exists():
        log.info(f"  BM25 캐시 로드: {cache_path.name}")
        with open(cache_path, "rb") as f:
            cached = pickle.load(f)
            bm25     = cached["bm25"]
            all_docs = cached["docs"]
        log.info(f"  BM25 캐시 완료: {len(all_docs):,}개 문서, {time.time()-t0:.1f}초")
    else:
        log.info("  BM25 인덱스 구축 중... (최초 1회, 이후 캐시 사용)")
        all_docs  = collection.get(include=["documents"])["documents"]
        tokenized = [tokenize_ko(doc) for doc in all_docs]
        bm25      = BM25Okapi(tokenized)
        with open(cache_path, "wb") as f:
            pickle.dump({"bm25": bm25, "docs": all_docs}, f)
        log.info(f"  BM25 완료 및 캐시 저장: {len(all_docs):,}개 문서, {time.time()-t0:.1f}초 → {cache_path.name}")

    # 평가
    results_sem  = {k: 0 for k in TOP_K_LIST}
    results_bm25 = {k: 0 for k in TOP_K_LIST}
    results_rrf  = {k: 0 for k in TOP_K_LIST}

    # 난이도별
    diff_results = {
        "basic": {"sem": {k: 0 for k in TOP_K_LIST}, "bm25": {k: 0 for k in TOP_K_LIST}, "rrf": {k: 0 for k in TOP_K_LIST}, "n": 0},
        "hard":  {"sem": {k: 0 for k in TOP_K_LIST}, "bm25": {k: 0 for k in TOP_K_LIST}, "rrf": {k: 0 for k in TOP_K_LIST}, "n": 0},
    }
    # 카테고리별 (Top-5 기준)
    cat_results = {}
    # RRF Miss 케이스
    miss_cases = []

    n = len(questions)

    for i, item in enumerate(questions):
        q        = item["question"]
        must     = item["must"]
        context  = item["context"]
        diff     = item.get("difficulty", "basic")
        category = item.get("category", "기타")

        # 시맨틱
        sem_docs  = semantic_search(model, collection, q, cfg["query_prefix"], max(TOP_K_LIST))
        # BM25
        bm25_docs = bm25_search(bm25, all_docs, q, max(TOP_K_LIST))
        # RRF 융합
        rrf_scores = {}
        for rank, doc in enumerate(sem_docs):
            rrf_scores[doc] = rrf_scores.get(doc, 0) + 1 / (60 + rank + 1)
        for rank, doc in enumerate(bm25_docs):
            rrf_scores[doc] = rrf_scores.get(doc, 0) + 1 / (60 + rank + 1)
        rrf_combined = [doc for doc, _ in sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)][:max(TOP_K_LIST)]

        sem_hit  = check_hit(sem_docs,     must, context, TOP_K_LIST)
        bm25_hit = check_hit(bm25_docs,    must, context, TOP_K_LIST)
        rrf_hit  = check_hit(rrf_combined, must, context, TOP_K_LIST)

        # 전체 집계
        for k in TOP_K_LIST:
            if sem_hit[k]:  results_sem[k]  += 1
            if bm25_hit[k]: results_bm25[k] += 1
            if rrf_hit[k]:  results_rrf[k]  += 1

        # 난이도별 집계
        d = diff_results.get(diff, diff_results["basic"])
        d["n"] += 1
        for k in TOP_K_LIST:
            if sem_hit[k]:  d["sem"][k]  += 1
            if bm25_hit[k]: d["bm25"][k] += 1
            if rrf_hit[k]:  d["rrf"][k]  += 1

        # 카테고리별 집계 (Top-5 기준)
        if category not in cat_results:
            cat_results[category] = {"sem": 0, "bm25": 0, "rrf": 0, "n": 0}
        cat_results[category]["n"] += 1
        if sem_hit[5]:  cat_results[category]["sem"]  += 1
        if bm25_hit[5]: cat_results[category]["bm25"] += 1
        if rrf_hit[5]:  cat_results[category]["rrf"]  += 1

        # RRF Miss 케이스 기록
        if not rrf_hit[5]:
            miss_cases.append({
                "q": q, "category": category, "difficulty": diff,
                "sem": sem_hit[5], "bm25": bm25_hit[5]
            })

        if (i + 1) % 50 == 0:
            log.info(f"  진행: {i+1}/{n}")

    # 퍼센트 변환
    def pct(d, total):
        return {k: round(v / total * 100, 1) for k, v in d.items()}

    def diff_pct(d):
        total = d["n"] if d["n"] > 0 else 1
        return {
            "n":    d["n"],
            "sem":  pct(d["sem"],  total),
            "bm25": pct(d["bm25"], total),
            "rrf":  pct(d["rrf"],  total),
        }

    return {
        "label":        label,
        "n":            n,
        "semantic":     pct(results_sem,  n),
        "bm25":         pct(results_bm25, n),
        "rrf":          pct(results_rrf,  n),
        "by_difficulty": {d: diff_pct(v) for d, v in diff_results.items()},
        "by_category":  cat_results,
        "miss_cases":   miss_cases,
    }


# ═══════════════════════════════════════════════════════════════
# 결과 출력 & 저장
# ═══════════════════════════════════════════════════════════════
def print_summary(all_results: list[dict]):
    CAT_ORDER = ["증상-질병", "생활습관-영향", "음식-약물", "음식-질병", "복합질환", "약물부작용", "예방관리"]

    for r in all_results:
        print("\n" + "=" * 72)
        print(f"  [{r['label']}]  (전체 {r['n']}개)")
        print("=" * 72)

        # 전체 결과
        print(f"\n  [전체 {r['n']}개]")
        print(f"  {'방식':<10} {'@3':>7} {'@5':>7} {'@10':>7}")
        print("  " + "-" * 34)
        for method_name, method_key in [("시맨틱", "semantic"), ("BM25", "bm25"), ("RRF ★", "rrf")]:
            v = r[method_key]
            print(f"  {method_name:<10} {v[3]:>6.1f}% {v[5]:>6.1f}% {v[10]:>6.1f}%")

        # 난이도별
        print(f"\n  [난이도별 — RRF Top-5 기준]")
        print(f"  {'난이도':<10} {'문항':>5} {'시맨틱':>8} {'BM25':>8} {'RRF':>8}")
        print("  " + "-" * 46)
        for diff_key, diff_label in [("basic", "기본"), ("hard", "추론")]:
            d = r["by_difficulty"].get(diff_key, {})
            if not d or d.get("n", 0) == 0:
                continue
            s = d["sem"][5]
            b = d["bm25"][5]
            rv = d["rrf"][5]
            print(f"  {diff_label:<10} {d['n']:>5}개 {s:>7.1f}% {b:>7.1f}% {rv:>7.1f}%")

        # 카테고리별
        print(f"\n  [카테고리별 — RRF Top-5 기준]")
        print(f"  {'카테고리':<16} {'문항':>5} {'시맨틱':>8} {'BM25':>8} {'RRF':>8}")
        print("  " + "-" * 52)
        cat = r.get("by_category", {})
        for c in CAT_ORDER:
            if c not in cat:
                continue
            d = cat[c]
            n = d["n"] if d["n"] > 0 else 1
            print(f"  {c:<16} {d['n']:>5}개"
                  f" {d['sem']/n*100:>7.1f}%"
                  f" {d['bm25']/n*100:>7.1f}%"
                  f" {d['rrf']/n*100:>7.1f}%")

        # Miss 케이스
        miss = r.get("miss_cases", [])
        if miss:
            print(f"\n  [RRF Top-5 Miss 케이스 — {len(miss)}개]")
            print(f"  {'#':>3}  {'질문':<38}  {'카테고리':<14}  {'난이도':<6}  S  B")
            print("  " + "-" * 70)
            for j, m in enumerate(miss[:20]):
                q_short = m["q"][:36] + ".." if len(m["q"]) > 36 else m["q"]
                s = "✓" if m["sem"] else "✗"
                b = "✓" if m["bm25"] else "✗"
                print(f"  {j+1:>3}  {q_short:<38}  {m['category']:<14}  {m['difficulty']:<6}  {s}  {b}")
            if len(miss) > 20:
                print(f"  ... 외 {len(miss)-20}개")

    # ── 모델간 비교 테이블 ──
    print("\n\n" + "=" * 80)
    print("  [모델간 비교]")
    print("=" * 80)

    def cmp_table(title, get_vals):
        """모델간 비교 테이블 출력 헬퍼"""
        print(f"\n  ── {title} ──")
        print(f"  {'모델':<16} {'시맨틱@3':>9} {'시맨틱@5':>9} {'시맨틱@10':>10} {'BM25@3':>8} {'BM25@5':>8} {'BM25@10':>9} {'RRF@3':>7} {'RRF@5':>7} {'RRF@10':>8}")
        print("  " + "-" * 98)
        for r in all_results:
            vals = get_vals(r)
            if vals is None:
                continue
            s, b, rrf = vals
            print(f"  {r['label']:<16}"
                  f" {s[3]:>8.1f}% {s[5]:>8.1f}% {s[10]:>9.1f}%"
                  f" {b[3]:>7.1f}% {b[5]:>7.1f}% {b[10]:>8.1f}%"
                  f" {rrf[3]:>6.1f}% {rrf[5]:>6.1f}% {rrf[10]:>7.1f}%")

    # 전체 200개
    cmp_table("전체 200개", lambda r: (r["semantic"], r["bm25"], r["rrf"]))

    # 기본 100개
    def get_basic(r):
        d = r["by_difficulty"].get("basic", {})
        if not d or d.get("n", 0) == 0: return None
        return d["sem"], d["bm25"], d["rrf"]
    cmp_table("기본 질문 100개", get_basic)

    # 추론 100개
    def get_hard(r):
        d = r["by_difficulty"].get("hard", {})
        if not d or d.get("n", 0) == 0: return None
        return d["sem"], d["bm25"], d["rrf"]
    cmp_table("추론 질문 100개", get_hard)

    # 카테고리별 RRF Top-5 모델 비교
    CAT_ORDER = ["증상-질병", "생활습관-영향", "음식-약물", "음식-질병", "복합질환", "약물부작용", "예방관리"]
    labels = [r["label"] for r in all_results]
    print(f"\n  ── 카테고리별 RRF Top-5 ──")
    print(f"  {'카테고리':<16}" + "".join(f"{l:>16}" for l in labels))
    print("  " + "-" * (16 + 16 * len(labels)))
    for cat in CAT_ORDER:
        row = f"  {cat:<16}"
        for r in all_results:
            d = r.get("by_category", {}).get(cat)
            if d and d["n"] > 0:
                row += f"{d['rrf']/d['n']*100:>15.1f}%"
            else:
                row += f"{'—':>16}"
        print(row)
    print()


def save_csv(all_results: list[dict], ts: str):
    RESULTS_DIR.mkdir(exist_ok=True)
    path = RESULTS_DIR / f"eval_three_models_{ts}.csv"
    rows = []

    # 전체 수치
    for r in all_results:
        for method_key in ["semantic", "bm25", "rrf"]:
            vals = r[method_key]
            rows.append({
                "구분": "전체", "모델": r["label"], "방식": method_key,
                "난이도": "전체", "카테고리": "전체",
                "문항수": r["n"],
                "Top3": vals[3], "Top5": vals[5], "Top10": vals[10],
            })
        # 난이도별
        for diff_key, diff_label in [("basic", "기본"), ("hard", "추론")]:
            d = r["by_difficulty"].get(diff_key, {})
            if not d or d.get("n", 0) == 0:
                continue
            for method_key, method_data in [("semantic", d["sem"]), ("bm25", d["bm25"]), ("rrf", d["rrf"])]:
                rows.append({
                    "구분": "난이도별", "모델": r["label"], "방식": method_key,
                    "난이도": diff_label, "카테고리": "전체",
                    "문항수": d["n"],
                    "Top3": method_data[3], "Top5": method_data[5], "Top10": method_data[10],
                })
        # 카테고리별 (Top-5만)
        for cat, d in r.get("by_category", {}).items():
            n = d["n"] if d["n"] > 0 else 1
            rows.append({
                "구분": "카테고리별", "모델": r["label"], "방식": "rrf",
                "난이도": "전체", "카테고리": cat,
                "문항수": d["n"],
                "Top3": "-", "Top5": round(d["rrf"]/n*100, 1), "Top10": "-",
            })

    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["구분","모델","방식","난이도","카테고리","문항수","Top3","Top5","Top10"])
        writer.writeheader()
        writer.writerows(rows)
    log.info(f"  CSV 저장: {path}")
    return path


def save_summary(all_results: list[dict], ts: str):
    CAT_ORDER = ["증상-질병", "생활습관-영향", "음식-약물", "음식-질병", "복합질환", "약물부작용", "예방관리"]
    RESULTS_DIR.mkdir(exist_ok=True)
    path = RESULTS_DIR / f"eval_three_models_{ts}_summary.txt"
    lines = ["MediScanner 3모델 검색 정확도 비교\n", f"측정 일시: {ts}\n", "=" * 60 + "\n"]

    for r in all_results:
        lines.append(f"\n[{r['label']}]  (전체 {r['n']}개)\n")
        lines.append("  전체\n")
        for mn, mk in [("시맨틱", "semantic"), ("BM25", "bm25"), ("RRF", "rrf")]:
            v = r[mk]
            lines.append(f"    {mn:<8}  @3:{v[3]:>5.1f}%  @5:{v[5]:>5.1f}%  @10:{v[10]:>5.1f}%\n")
        lines.append("  난이도별 (RRF Top-5)\n")
        for dk, dl in [("basic","기본"),("hard","추론")]:
            d = r["by_difficulty"].get(dk, {})
            if d and d.get("n", 0) > 0:
                lines.append(f"    {dl}({d['n']}개)  시맨틱:{d['sem'][5]:>5.1f}%  BM25:{d['bm25'][5]:>5.1f}%  RRF:{d['rrf'][5]:>5.1f}%\n")
        lines.append("  카테고리별 (RRF Top-5)\n")
        for c in CAT_ORDER:
            d = r.get("by_category", {}).get(c)
            if d:
                n = d["n"] if d["n"] > 0 else 1
                lines.append(f"    {c:<16}  {d['n']:>3}개  RRF:{d['rrf']/n*100:>5.1f}%\n")
        miss = r.get("miss_cases", [])
        lines.append(f"  RRF Miss: {len(miss)}개\n")
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
