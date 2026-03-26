"""
RRF 융합 (infra 계층)
====================
MedRAG 논문 RRF-2 방식: 시맨틱 + BM25 결과를 합쳐서 최종 순위 결정
공식: RRF_score(d) = Σ 1/(k + rank_i(d))
"""

from app.config import RRF_K
from app.domain.entities import Document


class RRFFusion:
    """Reciprocal Rank Fusion — 두 검색 결과를 합치는 알고리즘"""

    def fuse(
        self,
        semantic_docs: list[Document],
        bm25_docs: list[Document],
        k: int = RRF_K,
        top_k: int = 5,
    ) -> list[Document]:
        """
        시맨틱 + BM25 검색 결과를 RRF로 융합

        양쪽에서 모두 높은 순위인 문서가 최종 1위가 됨
        """
        rrf_scores: dict[str, dict] = {}

        # 시맨틱 검색 순위 반영
        for rank, doc in enumerate(semantic_docs):
            doc_id = doc.id
            rrf_score = 1.0 / (k + rank + 1)
            if doc_id not in rrf_scores:
                rrf_scores[doc_id] = {"score": 0, "doc": doc, "found_in": []}
            rrf_scores[doc_id]["score"] += rrf_score
            rrf_scores[doc_id]["found_in"].append("semantic")

        # BM25 검색 순위 반영
        for rank, doc in enumerate(bm25_docs):
            doc_id = doc.id
            rrf_score = 1.0 / (k + rank + 1)
            if doc_id not in rrf_scores:
                rrf_scores[doc_id] = {"score": 0, "doc": doc, "found_in": []}
            rrf_scores[doc_id]["score"] += rrf_score
            rrf_scores[doc_id]["found_in"].append("bm25")

        # RRF 점수순 정렬
        sorted_items = sorted(
            rrf_scores.values(),
            key=lambda x: x["score"],
            reverse=True
        )

        # Document 객체로 변환
        results = []
        for item in sorted_items[:top_k]:
            doc = item["doc"]
            doc.rrf_score = round(item["score"], 6)
            doc.found_in = item["found_in"]
            results.append(doc)

        return results
