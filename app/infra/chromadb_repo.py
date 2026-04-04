"""
hnswlib 시맨틱 검색 (infra 계층)
================================
ChromaDB persistent HNSW 버그를 우회하여 hnswlib를 직접 사용
[2026-04-02] E5-small + hnswlib 직접 검색으로 전환
"""

import json
import pickle
import hnswlib
import numpy as np
from sentence_transformers import SentenceTransformer
from app.config import RETRIEVAL_K
from app.domain.entities import Document

# 상대 경로 (한국어 폴더명 hnswlib 호환)
EMBEDDING_MODEL_PATH = "models/e5-small"
HNSW_INDEX_PATH = "data/chroma_db_e5small/hnsw_index.bin"
HNSW_IDS_PATH = "data/chroma_db_e5small/hnsw_ids.json"
CHUNKS_PKL_PATH = "temp_chunks_source_only.pkl"

E5_QUERY_PREFIX = "query: "
E5_PASSAGE_PREFIX = "passage: "

HNSW_DIM = 384
HNSW_SPACE = "cosine"
HNSW_EF_SEARCH = 50


class ChromaDBRepo:
    """hnswlib 벡터 검색 (ChromaDB 인터페이스 유지)"""

    def __init__(self):
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

        # 3. ID 매핑 로드
        with open(HNSW_IDS_PATH, "r", encoding="utf-8") as f:
            self.hnsw_ids = json.load(f)

        # 4. 문서 텍스트/메타데이터 로드
        print(f"▶ 문서 데이터 로딩: {CHUNKS_PKL_PATH}...")
        with open(CHUNKS_PKL_PATH, "rb") as f:
            chunks_data = pickle.load(f)

        self.all_chunks = chunks_data["chunks"]
        self.all_metadatas = chunks_data["metadatas"]
        self.all_chunk_ids = chunks_data["chunk_ids"]

        # {doc_id: index} 매핑
        self.id_to_index = {}
        for i, cid in enumerate(self.all_chunk_ids):
            self.id_to_index[cid] = i
        print(f"✓ 문서 데이터 로딩 완료 ({len(self.all_chunks):,}개)")

    def embed_text(self, text: str, is_query: bool = True) -> list[float]:
        """텍스트 임베딩 생성 (E5 prefix 적용)"""
        prefix = E5_QUERY_PREFIX if is_query else E5_PASSAGE_PREFIX
        return self.embedder.encode(
            f"{prefix}{text}", normalize_embeddings=True
        ).tolist()

    def search(self, query: str, top_k: int = RETRIEVAL_K) -> list[Document]:
        """시맨틱 검색 - hnswlib knn_query"""
        query_vec = self.embedder.encode(
            f"{E5_QUERY_PREFIX}{query}", normalize_embeddings=True
        ).reshape(1, -1)

        labels, distances = self.hnsw_index.knn_query(query_vec, k=top_k)

        docs = []
        for label, dist in zip(labels[0], distances[0]):
            doc_id = self.hnsw_ids[label]
            idx = self.id_to_index.get(doc_id)
            if idx is not None:
                docs.append(Document(
                    id=doc_id,
                    text=self.all_chunks[idx],
                    metadata=self.all_metadatas[idx],
                    score=1 - float(dist),
                    source="semantic",
                ))
        return docs

    def get_count(self) -> int:
        return self.hnsw_index.get_current_count()

    def get_all_documents(self, batch_size: int = 5000) -> tuple[list[str], list[dict], list[str]]:
        """BM25 인덱스 구축용 전체 문서 반환"""
        return self.all_chunks, self.all_metadatas, self.all_chunk_ids
