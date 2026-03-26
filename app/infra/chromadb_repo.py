"""
ChromaDB 시맨틱 검색 (infra 계층)
================================
ko-sroberta 임베딩으로 의미 유사도 기반 검색
"""

import chromadb
from sentence_transformers import SentenceTransformer
from app.config import EMBEDDING_MODEL, CHROMA_DB_PATH, COLLECTION_NAME, RETRIEVAL_K
from app.domain.entities import Document


class ChromaDBRepo:
    """ChromaDB 벡터 검색 — 의미 유사도 기반"""

    def __init__(self):
        print(f"📦 임베딩 모델 로딩: {EMBEDDING_MODEL}...")
        self.embedder = SentenceTransformer(EMBEDDING_MODEL)
        print(f"✅ 임베딩 모델 로딩 완료 ({EMBEDDING_MODEL})")

        self.client = chromadb.PersistentClient(path=CHROMA_DB_PATH)

    def embed_text(self, text: str) -> list[float]:
        return self.embedder.encode(text).tolist()

    def search(self, query: str, top_k: int = RETRIEVAL_K) -> list[Document]:
        """시맨틱 검색 — 질문과 의미가 비슷한 문서 찾기"""
        try:
            collection = self.client.get_collection(name=COLLECTION_NAME)
        except Exception:
            return []

        query_embedding = self.embed_text(query)

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )

        docs = []
        if results and results["documents"]:
            for i, text in enumerate(results["documents"][0]):
                docs.append(Document(
                    id=results["ids"][0][i] if results["ids"] else f"sem_{i}",
                    text=text,
                    metadata=results["metadatas"][0][i] if results["metadatas"] else {},
                    score=1 - results["distances"][0][i],
                    source="semantic",
                ))
        return docs

    def get_count(self) -> int:
        try:
            return self.client.get_collection(name=COLLECTION_NAME).count()
        except Exception:
            return 0

    def get_all_documents(self, batch_size: int = 5000) -> tuple[list[str], list[dict], list[str]]:
        """BM25 인덱스 구축용 전체 문서 반환"""
        try:
            collection = self.client.get_collection(name=COLLECTION_NAME)
            count = collection.count()
        except Exception:
            return [], [], []

        all_docs, all_metadatas, all_ids = [], [], []

        for offset in range(0, count, batch_size):
            result = collection.get(
                limit=batch_size,
                offset=offset,
                include=["documents", "metadatas"],
            )
            if result["documents"]:
                all_docs.extend(result["documents"])
                all_metadatas.extend(result["metadatas"])
                all_ids.extend(result["ids"])

        return all_docs, all_metadatas, all_ids
