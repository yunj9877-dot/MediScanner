"""
MediScanner RAG 엔진 (호환용 래퍼)
======================================
클린 아키텍처 전환 후, 기존 스크립트(evaluate.py 등) 호환을 위해 유지
실제 서비스 로직은 domain/usecases.py + infra/ 에 있음

변경사항:
  - Reranker 제거 (성능 실험 결과 RRF만 81.2%로 최고)
  - 고령자 맞춤 프롬프트 적용
  - API 데이터 컨텍스트 지원
"""

import re
import os
import pickle
import chromadb
from openai import OpenAI
from sentence_transformers import SentenceTransformer
from rank_bm25 import BM25Okapi
from typing import Optional
from app.config import (
    OPENAI_API_KEY, OPENAI_CHAT_MODEL,
    EMBEDDING_MODEL,
    CHROMA_DB_PATH, COLLECTION_NAME,
    TOP_K, RETRIEVAL_K, RRF_K,
    COST_INPUT_PER_1K, COST_OUTPUT_PER_1K,
)


class RAGEngine:
    """
    하이브리드 RAG 엔진 (MedRAG 논문 RRF-2 방식)
    ※ Reranker 제거됨 (성능 실험: RRF 81.2% > RRF+Reranker 77.4%)
    """

    def __init__(self, openai_api_key: str = ""):
        self.openai_api_key = openai_api_key or OPENAI_API_KEY
        self.client = OpenAI(api_key=self.openai_api_key) if self.openai_api_key else None

        print(f"📦 임베딩 모델 로딩: {EMBEDDING_MODEL}...")
        self.embedder = SentenceTransformer(EMBEDDING_MODEL)
        print(f"✅ 임베딩 모델 로딩 완료 ({EMBEDDING_MODEL})")

        self.chroma = chromadb.PersistentClient(path=CHROMA_DB_PATH)

        self.bm25 = None
        self.bm25_docs = []
        self.bm25_metadatas = []
        self.bm25_ids = []
        self._build_bm25_index()

        self.usage = {"input_tokens": 0, "output_tokens": 0, "api_calls": 0, "searches": 0}

    BM25_CACHE_PATH = os.path.join(os.path.dirname(__file__), "..", "bm25_cache.pkl")

    def _build_bm25_index(self):
        """BM25 인덱스 구축 (pickle 캐시 우선 로드)"""
        cache_path = os.path.abspath(self.BM25_CACHE_PATH)

        if os.path.exists(cache_path):
            try:
                print(f"📦 BM25 캐시 로딩 중... ({cache_path})")
                with open(cache_path, "rb") as f:
                    cache = pickle.load(f)
                self.bm25_docs = cache["docs"]
                self.bm25_metadatas = cache["metadatas"]
                self.bm25_ids = cache["ids"]
                self.bm25 = cache["bm25"]
                print(f"✅ BM25 캐시 로딩 완료 ({len(self.bm25_docs):,}개 문서)")
                return
            except Exception as e:
                print(f"⚠️ BM25 캐시 로딩 실패, 새로 구축합니다: {e}")

        try:
            collection = self.chroma.get_collection(name=COLLECTION_NAME)
            count = collection.count()
            if count == 0:
                return

            print(f"📦 BM25 인덱스 구축 중... ({count:,}개 청크)")
            all_docs, all_metadatas, all_ids = [], [], []

            for offset in range(0, count, 5000):
                result = collection.get(limit=5000, offset=offset, include=["documents", "metadatas"])
                if result["documents"]:
                    all_docs.extend(result["documents"])
                    all_metadatas.extend(result["metadatas"])
                    all_ids.extend(result["ids"])

            self.bm25_docs = all_docs
            self.bm25_metadatas = all_metadatas
            self.bm25_ids = all_ids
            self.bm25 = BM25Okapi([self._tokenize_korean(d) for d in all_docs])
            print(f"✅ BM25 인덱스 구축 완료 ({len(all_docs):,}개 문서)")

            try:
                with open(cache_path, "wb") as f:
                    pickle.dump({
                        "docs": self.bm25_docs,
                        "metadatas": self.bm25_metadatas,
                        "ids": self.bm25_ids,
                        "bm25": self.bm25,
                    }, f)
                cache_size_mb = os.path.getsize(cache_path) / (1024 * 1024)
                print(f"💾 BM25 캐시 저장 완료 ({cache_path}, {cache_size_mb:.1f}MB)")
            except Exception as e:
                print(f"⚠️ BM25 캐시 저장 실패: {e}")

        except Exception as e:
            print(f"⚠️ BM25 인덱스 구축 실패: {e}")

    def _tokenize_korean(self, text: str) -> list[str]:
        tokens = re.findall(r'[가-힣a-zA-Z0-9]+', text.lower())
        return [t for t in tokens if len(t) >= 2]

    def embed_text(self, text: str) -> list[float]:
        return self.embedder.encode(text).tolist()

    def _search_semantic(self, query: str, top_k: int = RETRIEVAL_K) -> list[dict]:
        try:
            collection = self.chroma.get_collection(name=COLLECTION_NAME)
        except Exception:
            return []
        results = collection.query(
            query_embeddings=[self.embed_text(query)], n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )
        docs = []
        if results and results["documents"]:
            for i, doc in enumerate(results["documents"][0]):
                docs.append({
                    "id": results["ids"][0][i], "text": doc,
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "score": 1 - results["distances"][0][i], "source": "semantic",
                })
        return docs

    def _search_bm25(self, query: str, top_k: int = RETRIEVAL_K) -> list[dict]:
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

    def search(self, query: str, top_k: int = TOP_K) -> list[dict]:
        """RRF 하이브리드 검색 (Reranker 미사용, 81.2%)"""
        self.usage["searches"] += 1
        semantic = self._search_semantic(query, top_k=RETRIEVAL_K)
        bm25 = self._search_bm25(query, top_k=RETRIEVAL_K)
        fused = self._rrf_fusion(semantic, bm25)
        return [{
            "text": d["text"], "metadata": d["metadata"],
            "distance": 1 - d.get("rrf_score", 0), "collection": COLLECTION_NAME,
            "rrf_score": d.get("rrf_score", 0), "found_in": d.get("found_in", []),
        } for d in fused[:top_k]]

    def generate_answer(self, query: str, retrieved_docs: list[dict],
                        drug_api_data: Optional[dict] = None,
                        dur_api_data: Optional[list] = None,
                        answer_mode: str = "simple",
                        user_profile: Optional[dict] = None) -> dict:
        if not self.client:
            raise ValueError("OpenAI API 키가 설정되지 않았습니다")

        parts = []
        if retrieved_docs:
            parts.append("【의료DB 검색 결과】")
            for i, doc in enumerate(retrieved_docs, 1):
                source = doc["metadata"].get("source_spec", "출처 없음")
                parts.append(f"[문서 {i}] (출처: {source})\n{doc['text']}")
        if drug_api_data:
            parts.append("\n【식약처 e약은요 API - 의약품 정보】")
            for k, v in [("제품명","itemName"),("효능","efcyQesitm"),("사용법","useMethodQesitm"),
                         ("주의사항","atpnQesitm"),("부작용","seQesitm")]:
                parts.append(f"{k}: {drug_api_data.get(v, '')}")
        if dur_api_data:
            parts.append("\n【DUR - 병용금기 정보】")
            for item in dur_api_data:
                parts.append(f"- {item.get('MIXTURE_ITEM_NAME','')}: {item.get('PROHBT_CONTENT','')} (사유: {item.get('REMARK','')})")

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

        # 기저질환별 ①②③ 형식 템플릿 생성
        disease_list = []
        format_instruction = ""
        if user_profile and user_profile.get("diseases"):
            disease_list = [d.strip() for d in user_profile["diseases"].split(',') if d.strip()]
        if disease_list:
            circles = ['①', '②', '③', '④', '⑤', '⑥', '⑦', '⑧']
            lines = ["【반드시 아래 형식으로 답변하세요 — 기저질환 항목을 하나도 빠뜨리지 마세요】"]
            for i, disease in enumerate(disease_list):
                c = circles[i] if i < len(circles) else f"({i+1})"
                lines.append(f"{c} {disease}: (이 질환에 미치는 영향 1~2문장)")
            if user_profile.get("medications"):
                lines.append(f"💊 복용약 주의: (복용 중인 {user_profile['medications']}와의 관계 1문장)")
            format_instruction = "\n" + "\n".join(lines)

        # answer_mode에 따라 프롬프트 분기
        if answer_mode == "simple":
            system_prompt = """당신은 고령자를 위한 개인 맞춤 의료 상담 AI 메디스캐너입니다.

답변 규칙:
1. 기저질환 각각을 ①②③ 형식으로 답변하세요.
2. 각 항목은 반드시 새 줄에서 시작하세요. ①과 ② 사이에 줄바꿈 필수.
3. 각 항목은 핵심만 담아 반드시 20자 이내로 작성하세요.
4. 출처는 절대 표시하지 마세요. (출처:...) 문구 금지.
5. 위험한 내용은 ⚠️ 표시하세요.
6. 마지막에 "※ 참고용 정보이며, 정확한 진단은 의료 전문가와 상담하세요." 추가

예시 형식:
① 고혈압: 혈압 상승 위험 ⚠️
② 당뇨병: 혈당 급상승 위험 ⚠️
③ 심장질환: 심박수 증가 위험 ⚠️
※ 참고용 정보이며, 정확한 진단은 의료 전문가와 상담하세요."""
            max_tokens = 80 + len(disease_list) * 40
        else:
            system_prompt = """당신은 고령자를 위한 개인 맞춤 의료 상담 AI 메디스캐너입니다.

답변 규칙:
1. 기저질환 각각을 ①②③ 형식으로 각각 새 줄에서 시작하여 답변하세요.
2. ①과 ② 사이에 반드시 줄바꿈을 넣으세요.
3. '일반적으로는...' 표현 절대 금지. 이 분의 기저질환 기준으로만 말하세요.
4. 복용 중인 약과의 상호작용도 💊 항목으로 새 줄에 추가하세요.
5. 출처는 절대 표시하지 마세요. (출처:...) 문구 금지.
6. 위험한 내용은 ⚠️ 또는 ❌로 표시하세요.
7. 마지막에 "※ 참고용 정보이며, 정확한 진단은 의료 전문가와 상담하세요." 추가"""
            max_tokens = 500 + len(disease_list) * 80

        response = self.client.chat.completions.create(
            model=OPENAI_CHAT_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"【참고자료】\n{chr(10).join(parts)}\n\n【사용자 질문】\n{query}{format_instruction}\n\n위 형식을 반드시 지켜서 답변해주세요."},
            ],
            temperature=0.3, max_tokens=max_tokens,
        )

        usage = response.usage
        self.usage["input_tokens"] += usage.prompt_tokens
        self.usage["output_tokens"] += usage.completion_tokens
        self.usage["api_calls"] += 1

        return {
            "answer": response.choices[0].message.content,
            "sources": [{"collection": d["collection"], "source": d["metadata"].get("source_spec",""),
                         "distance": round(d["distance"],4), "found_in": d.get("found_in",[])} for d in retrieved_docs],
            "tokens": {"input": usage.prompt_tokens, "output": usage.completion_tokens},
        }

    def get_collection_stats(self) -> dict:
        try: return {COLLECTION_NAME: self.chroma.get_collection(name=COLLECTION_NAME).count()}
        except: return {COLLECTION_NAME: 0}

    def get_cost(self) -> dict:
        ic = (self.usage["input_tokens"]/1000)*COST_INPUT_PER_1K
        oc = (self.usage["output_tokens"]/1000)*COST_OUTPUT_PER_1K
        t = ic + oc
        return {"embedding_cost":0,"input_cost":round(ic,6),"output_cost":round(oc,6),
                "total_usd":round(t,6),"total_krw":round(t*1400,2),"usage":self.usage}

    def reset_usage(self):
        self.usage = {"input_tokens":0,"output_tokens":0,"api_calls":0,"searches":0}
