"""
MediScanner RAG 엔진 (hnswlib 직접 검색 버전)
=============================================
chromadb의 HNSW persistent 버그를 우회하여
hnswlib를 직접 사용하여 벡터 검색을 수행합니다.

변경사항:
  - ChromaDB query() → hnswlib knn_query()
  - 문서 텍스트/메타데이터: temp_chunks_source_only.pkl에서 로드
  - BM25: 기존 bm25_cache_e5small.pkl 사용
  - [2026-04-02] E5-small + hnswlib 직접 검색으로 전환
"""

import re
import os
import json
import pickle
import sqlite3
import hnswlib
import numpy as np
from openai import OpenAI
from sentence_transformers import SentenceTransformer
from rank_bm25 import BM25Okapi
from typing import Optional
from app.config import (
    OPENAI_API_KEY, OPENAI_CHAT_MODEL,
    TOP_K, RETRIEVAL_K, RRF_K,
    COST_INPUT_PER_1K, COST_OUTPUT_PER_1K,
)

# ============================================================
# 경로 설정 — 상대 경로 사용 (한국어 폴더명 hnswlib 호환)
# ============================================================
EMBEDDING_MODEL_PATH = "models/e5-small"
HNSW_INDEX_PATH = "data/chroma_db_e5small/hnsw_index.bin"
HNSW_IDS_PATH = "data/chroma_db_e5small/hnsw_ids.json"
CHUNKS_PKL_PATH = "temp_chunks_source_only.pkl"
BM25_CACHE_PATH = "data/bm25_cache_e5small.pkl"

# E5 prefix
E5_QUERY_PREFIX = "query: "
E5_PASSAGE_PREFIX = "passage: "

# HNSW 검색 파라미터
HNSW_EF_SEARCH = 50
HNSW_DIM = 384
HNSW_SPACE = "cosine"


class RAGEngine:
    """
    hnswlib 직접 검색 RAG 엔진
    - 벡터 검색: hnswlib (knn_query)
    - 문서 조회: 메모리 딕셔너리 (pkl에서 로드)
    - 키워드 검색: BM25
    """

    def __init__(self, openai_api_key: str = ""):
        self.openai_api_key = openai_api_key or OPENAI_API_KEY
        self.client = OpenAI(api_key=self.openai_api_key) if self.openai_api_key else None

        # 1. 임베딩 모델 로드
        print(f"▶ 임베딩 모델 로딩: {EMBEDDING_MODEL_PATH}...")
        self.embedder = SentenceTransformer(EMBEDDING_MODEL_PATH)
        print(f"✓ 임베딩 모델 로딩 완료 (E5-small)")

        # 2. hnswlib 인덱스 로드
        print(f"▶ hnswlib 인덱스 로딩: {HNSW_INDEX_PATH}...")
        self.hnsw_index = hnswlib.Index(space=HNSW_SPACE, dim=HNSW_DIM)
        self.hnsw_index.load_index(HNSW_INDEX_PATH, max_elements=700000)
        self.hnsw_index.set_ef(HNSW_EF_SEARCH)
        print(f"✓ hnswlib 인덱스 로딩 완료 ({self.hnsw_index.get_current_count():,}개 벡터)")

        # 3. ID 매핑 로드 (label → doc_id)
        print(f"▶ ID 매핑 로딩: {HNSW_IDS_PATH}...")
        with open(HNSW_IDS_PATH, "r", encoding="utf-8") as f:
            self.hnsw_ids = json.load(f)
        print(f"✓ ID 매핑 로딩 완료 ({len(self.hnsw_ids):,}개)")

        # 4. 문서 텍스트/메타데이터 로드
        print(f"▶ 문서 데이터 로딩: {CHUNKS_PKL_PATH}...")
        with open(CHUNKS_PKL_PATH, "rb") as f:
            chunks_data = pickle.load(f)

        # {doc_id: {"text": ..., "metadata": ...}} 딕셔너리 구축
        self.doc_lookup = {}
        for chunk_id, text, meta in zip(
            chunks_data["chunk_ids"], chunks_data["chunks"], chunks_data["metadatas"]
        ):
            self.doc_lookup[chunk_id] = {"text": text, "metadata": meta}
        print(f"✓ 문서 데이터 로딩 완료 ({len(self.doc_lookup):,}개)")

        # 5. BM25 인덱스 로드
        self.bm25 = None
        self.bm25_docs = []
        self.bm25_metadatas = []
        self.bm25_ids = []
        self._build_bm25_index()

        self.usage = {"input_tokens": 0, "output_tokens": 0, "api_calls": 0, "searches": 0}

    def _build_bm25_index(self):
        """BM25 인덱스 로드"""
        if os.path.exists(BM25_CACHE_PATH):
            try:
                print(f"▶ BM25 캐시 로딩 중... ({BM25_CACHE_PATH})")
                with open(BM25_CACHE_PATH, "rb") as f:
                    cache = pickle.load(f)
                self.bm25_docs = cache["docs"]
                self.bm25_metadatas = cache["metadatas"]
                self.bm25_ids = cache["ids"]
                self.bm25 = cache["bm25"]
                print(f"✓ BM25 캐시 로딩 완료 ({len(self.bm25_docs):,}개 문서)")
            except Exception as e:
                print(f"⚠️ BM25 캐시 로딩 실패: {e}")
        else:
            print(f"⚠️ BM25 캐시 없음: {BM25_CACHE_PATH}")

    def _tokenize_korean(self, text: str) -> list[str]:
        tokens = re.findall(r'[가-힣a-zA-Z0-9]+', text.lower())
        return [t for t in tokens if len(t) >= 2]

    def embed_text(self, text: str, is_query: bool = True) -> list[float]:
        """텍스트 임베딩 생성 (E5 prefix 적용)"""
        prefix = E5_QUERY_PREFIX if is_query else E5_PASSAGE_PREFIX
        return self.embedder.encode(f"{prefix}{text}", normalize_embeddings=True).tolist()

    def _search_semantic(self, query: str, top_k: int = RETRIEVAL_K) -> list[dict]:
        """시맨틱 검색 (hnswlib 직접)"""
        query_vec = self.embedder.encode(
            f"{E5_QUERY_PREFIX}{query}", normalize_embeddings=True
        ).reshape(1, -1)

        labels, distances = self.hnsw_index.knn_query(query_vec, k=top_k)

        docs = []
        for label, dist in zip(labels[0], distances[0]):
            doc_id = self.hnsw_ids[label]
            doc_data = self.doc_lookup.get(doc_id, {})
            if doc_data:
                docs.append({
                    "id": doc_id,
                    "text": doc_data["text"],
                    "metadata": doc_data["metadata"],
                    "score": 1 - dist,  # cosine distance → similarity
                    "source": "semantic",
                })
        return docs

    def _search_bm25(self, query: str, top_k: int = RETRIEVAL_K) -> list[dict]:
        """BM25 키워드 검색"""
        if self.bm25 is None:
            return []
        query_tokens = self._tokenize_korean(query)
        if not query_tokens:
            return []
        scores = self.bm25.get_scores(query_tokens)
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
        return [
            {"id": self.bm25_ids[idx], "text": self.bm25_docs[idx],
             "metadata": self.bm25_metadatas[idx], "score": float(scores[idx]), "source": "bm25"}
            for idx in top_indices if scores[idx] > 0
        ]

    def _rrf_fusion(self, semantic_docs: list[dict], bm25_docs: list[dict], k: int = RRF_K) -> list[dict]:
        """RRF 융합"""
        rrf_scores = {}
        for rank, doc in enumerate(semantic_docs):
            did = doc["id"]
            if did not in rrf_scores:
                rrf_scores[did] = {"score": 0, "doc": doc, "found_in": []}
            rrf_scores[did]["score"] += 1.0 / (k + rank + 1)
            rrf_scores[did]["found_in"].append("semantic")
        for rank, doc in enumerate(bm25_docs):
            did = doc["id"]
            if did not in rrf_scores:
                rrf_scores[did] = {"score": 0, "doc": doc, "found_in": []}
            rrf_scores[did]["score"] += 1.0 / (k + rank + 1)
            rrf_scores[did]["found_in"].append("bm25")

        results = []
        for item in sorted(rrf_scores.values(), key=lambda x: x["score"], reverse=True):
            doc = item["doc"]
            doc["rrf_score"] = round(item["score"], 6)
            doc["found_in"] = item["found_in"]
            results.append(doc)
        return results

    def search(self, query: str, top_k: int = TOP_K, model: str = "e5-small") -> list[dict]:
        """시맨틱 검색 (hnswlib)"""
        self.usage["searches"] += 1

        query_vec = self.embedder.encode(
            f"{E5_QUERY_PREFIX}{query}", normalize_embeddings=True
        ).reshape(1, -1)

        labels, distances = self.hnsw_index.knn_query(query_vec, k=top_k)

        docs = []
        for label, dist in zip(labels[0], distances[0]):
            doc_id = self.hnsw_ids[label]
            doc_data = self.doc_lookup.get(doc_id, {})
            if doc_data:
                docs.append({
                    "text": doc_data["text"],
                    "metadata": doc_data["metadata"],
                    "distance": round(float(dist), 4),
                    "collection": "medical_knowledge_e5s",
                    "found_in": ["semantic"],
                })
        return docs

    def generate_answer(self, query: str, retrieved_docs: list[dict],
                        drug_api_data: Optional[dict] = None,
                        dur_api_data: Optional[list] = None,
                        answer_mode: str = "simple",
                        user_profile: Optional[dict] = None,
                        profile_drug_api_data: Optional[list] = None) -> dict:
        if not self.client:
            raise ValueError("OpenAI API 키가 설정되지 않았습니다")

        parts = []
        if retrieved_docs:
            parts.append("【의료DB 검색 결과】")
            for i, doc in enumerate(retrieved_docs, 1):
                source = doc["metadata"].get("source_spec", "출처 없음")
                parts.append(f"[문서 {i}] (출처: {source})\n{doc['text']}")

        # 실제 출처명 목록 추출
        actual_sources = list(set([
            doc["metadata"].get("source_spec", "")
            for doc in retrieved_docs
            if doc["metadata"].get("source_spec", "")
        ]))
        sources_str = ", ".join(actual_sources) if actual_sources else "없음"
        if drug_api_data:
            parts.append("\n【식약처 e약은요 API - 의약품 정보】")
            for k, v in [("제품명","itemName"),("효능","efcyQesitm"),("사용법","useMethodQesitm"),
                         ("주의사항","atpnQesitm"),("부작용","seQesitm")]:
                parts.append(f"{k}: {drug_api_data.get(v, '')}")
        if dur_api_data:
            parts.append("\n【DUR - 병용금기 정보】")
            for item in dur_api_data:
                parts.append(f"- {item.get('MIXTURE_ITEM_NAME','')}: {item.get('PROHBT_CONTENT','')} (사유: {item.get('REMARK','')})")

        if profile_drug_api_data:
            parts.append("\n【복용 중인 약 - 식약처 확인 정보】")
            for drug in profile_drug_api_data:
                parts.append(f"▶ {drug.get('item_name','')}: {drug.get('efcy','')[:200]}")

        if user_profile:
            profile_parts = []
            if user_profile.get("age"):
                profile_parts.append(f"나이: {user_profile['age']}세")
            if user_profile.get("diseases"):
                profile_parts.append(f"기저질환: {user_profile['diseases']}")
            if user_profile.get("medications"):
                profile_parts.append(f"복용 중인 약: {user_profile['medications']}")
            if profile_parts:
                parts.append(f"\n【사용자 건강 정보】\n{', '.join(profile_parts)}")

        disease_list = []
        format_instruction = ""
        if user_profile and user_profile.get("diseases"):
            disease_list = [d.strip() for d in user_profile["diseases"].split(',') if d.strip()]
        if disease_list:
            lines = [f"""【답변 우선순위 규칙】
1. 사용자 질문과 직접 관련된 기저질환/복용약을 먼저, 충분히 설명하세요.
2. 질문과 관련 없는 기저질환은 1줄로 간단히만 언급하세요.
3. 복용약은 질문 상황과 연결될 때만 설명하세요.

등록된 기저질환: {', '.join(disease_list)}"""]
            if user_profile.get("medications"):
                lines.append(f"복용약: {user_profile['medications']}")
            format_instruction = "\n" + "\n".join(lines)

        if answer_mode == "simple":
            system_prompt = f"""당신은 고령자를 위한 개인 맞춤 의료 상담 AI 메디스캐너입니다.

간단 답변 규칙:
1. 사용자 질문과 직접 관련된 핵심 답변 첫 문장은 반드시 **문장** 형식으로 감싸세요.
2. 나머지는 2~3문장으로 핵심만 추가하세요.
3. 질문과 관련 없는 기저질환, 복용약은 언급하지 마세요.
4. 위험한 내용만 ⚠️로 표시하세요.
5. 출처는 표시하지 마세요.
6. 마지막에 "※ 정확한 진단은 의료 전문가와 상담하세요." 한 줄만 추가하세요."""
            max_tokens = 200
        else:
            system_prompt = f"""당신은 고령자를 위한 개인 맞춤 의료 상담 AI 메디스캐너입니다.

답변 규칙:
1. 사용자 질문에 직접 답하는 핵심 첫 문장은 반드시 **문장** 형식으로 감싸세요.
2. 질문과 관련된 기저질환은 ● 문장 3~4개로 충분히 설명하세요.
3. 질문과 관련 없는 기저질환은 마지막에 1줄씩만 간단히 언급하세요.
4. 복용약은 질문 상황과 연결될 때만 💊 항목으로 설명하세요.
5. '일반적으로는...' 표현 절대 금지. 이 분의 상황 기준으로만 말하세요.
6. 확인된 위험 내용은 ⚠️로 강조하세요.
7. 모든 항목 답변이 끝난 후, 반드시 아래 목록에서만 출처를 선택하여 표시하세요.
   사용 가능한 출처 목록: {sources_str}
   형식: (출처: [위 목록 중 하나])
   목록에 없는 출처(nedrug, 대한의학회 등)는 절대 쓰지 마세요.
8. 출처 다음 줄에 "※ 참고용 정보이니, 정확한 진단은 의료 전문가와 상담하세요." 추가"""
            max_tokens = 800 + len(disease_list) * 60

        response = self.client.chat.completions.create(
            model=OPENAI_CHAT_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"【참고자료】\n{chr(10).join(parts)}\n\n【 사용자 질문】\n{query}{format_instruction}\n\n※ 형식을 반드시 지켜서 답변해주세요."},
            ],
            temperature=0.3, max_tokens=max_tokens,
        )

        usage = response.usage
        self.usage["input_tokens"] += usage.prompt_tokens
        self.usage["output_tokens"] += usage.completion_tokens
        self.usage["api_calls"] += 1

        return {
            "answer": response.choices[0].message.content,
            "sources": [{"collection": d.get("collection", "medical_knowledge_e5s"),
                         "source": d["metadata"].get("source_spec", ""),
                         "distance": round(d.get("distance", 0), 4),
                         "found_in": d.get("found_in", [])} for d in retrieved_docs],
            "tokens": {"input": usage.prompt_tokens, "output": usage.completion_tokens},
        }

    def get_collection_stats(self) -> dict:
        return {"medical_knowledge_e5s": self.hnsw_index.get_current_count()}

    def get_cost(self) -> dict:
        ic = (self.usage["input_tokens"] / 1000) * COST_INPUT_PER_1K
        oc = (self.usage["output_tokens"] / 1000) * COST_OUTPUT_PER_1K
        t = ic + oc
        return {"embedding_cost": 0, "input_cost": round(ic, 6), "output_cost": round(oc, 6),
                "total_usd": round(t, 6), "total_krw": round(t * 1400, 2), "usage": self.usage}

    def reset_usage(self):
        self.usage = {"input_tokens": 0, "output_tokens": 0, "api_calls": 0, "searches": 0}
