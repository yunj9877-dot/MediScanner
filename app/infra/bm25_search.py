"""
BM25 키워드 검색 (infra 계층)
============================
단어 빈도 기반 문서 검색 (TF-IDF 개선 버전)
+ pickle 캐싱으로 서버 재시작 시 빠른 로딩
"""

import re
import os
import pickle
from rank_bm25 import BM25Okapi
from app.config import RETRIEVAL_K
from app.domain.entities import Document

# 캐시 파일 경로
BM25_CACHE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "bm25_cache.pkl")


class BM25Search:
    """BM25 키워드 검색 — 단어 일치 기반 + 캐싱"""

    def __init__(self):
        self.bm25 = None
        self.docs: list[str] = []
        self.metadatas: list[dict] = []
        self.ids: list[str] = []

    def build_index(self, docs: list[str], metadatas: list[dict], ids: list[str]):
        """BM25 인덱스 구축 (캐시 있으면 캐시에서 로딩)"""
        if not docs:
            print("⚠️ BM25: 문서가 없습니다.")
            return

        # 캐시 확인
        if self._load_cache(len(docs)):
            return

        # 캐시 없으면 새로 구축
        print(f"📦 BM25 인덱스 구축 중... ({len(docs):,}개 청크)")

        self.docs = docs
        self.metadatas = metadatas
        self.ids = ids

        tokenized = [self._tokenize(doc) for doc in docs]
        self.bm25 = BM25Okapi(tokenized)

        print(f"✅ BM25 인덱스 구축 완료 ({len(docs):,}개 문서)")

        # 캐시 저장
        self._save_cache()

    def try_load_cache(self) -> bool:
        """캐시만으로 BM25 로딩 시도 (ChromaDB 조회 없이)"""
        if not os.path.exists(BM25_CACHE_PATH):
            return False
        try:
            print(f"📦 BM25 캐시 로딩 중... ({BM25_CACHE_PATH})")
            with open(BM25_CACHE_PATH, "rb") as f:
                cache = pickle.load(f)
            if cache.get("count", 0) == 0:
                return False
            self.bm25 = cache["bm25"]
            self.docs = cache["docs"]
            self.metadatas = cache["metadatas"]
            self.ids = cache["ids"]
            print(f"✅ BM25 캐시 로딩 완료! ({cache['count']:,}개 문서, 빠른 시작)")
            return True
        except Exception as e:
            print(f"⚠️ BM25 캐시 로딩 실패: {e}")
            return False        

    def _load_cache(self, expected_count: int) -> bool:
        """캐시 파일에서 BM25 인덱스 로딩"""
        if not os.path.exists(BM25_CACHE_PATH):
            return False

        try:
            print(f"📦 BM25 캐시 로딩 중... ({BM25_CACHE_PATH})")
            with open(BM25_CACHE_PATH, "rb") as f:
                cache = pickle.load(f)

            # 문서 수가 다르면 캐시 무효
            cached_count = cache.get("count", 0)
            if cached_count == 0:
                print(f"⚠️ BM25 캐시 비어있음")
                return False
            if cached_count != expected_count:
                print(f"ℹ️ BM25 캐시 문서 수 차이 (캐시: {cached_count:,}개, 현재: {expected_count:,}개) — 캐시 사용")

            self.bm25 = cache["bm25"]
            self.docs = cache["docs"]
            self.metadatas = cache["metadatas"]
            self.ids = cache["ids"]

            print(f"✅ BM25 캐시 로딩 완료! ({expected_count:,}개 문서, 빠른 시작)")
            return True

        except Exception as e:
            print(f"⚠️ BM25 캐시 로딩 실패: {e}")
            return False

    def _save_cache(self):
        """BM25 인덱스를 파일로 저장"""
        try:
            cache_dir = os.path.dirname(BM25_CACHE_PATH)
            if cache_dir:
                os.makedirs(cache_dir, exist_ok=True)
            with open(BM25_CACHE_PATH, "wb") as f:
                pickle.dump({
                    "bm25": self.bm25,
                    "docs": self.docs,
                    "metadatas": self.metadatas,
                    "ids": self.ids,
                    "count": len(self.docs),
                }, f)
            print(f"💾 BM25 캐시 저장 완료 ({BM25_CACHE_PATH})")
        except Exception as e:
            print(f"⚠️ BM25 캐시 저장 실패: {e}")

    def search(self, query: str, top_k: int = RETRIEVAL_K) -> list[Document]:
        """BM25 검색 — 키워드가 일치하는 문서 찾기"""
        if self.bm25 is None:
            return []

        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        scores = self.bm25.get_scores(query_tokens)
        top_indices = sorted(
            range(len(scores)),
            key=lambda i: scores[i],
            reverse=True
        )[:top_k]

        docs = []
        for idx in top_indices:
            if scores[idx] > 0:
                docs.append(Document(
                    id=self.ids[idx],
                    text=self.docs[idx],
                    metadata=self.metadatas[idx],
                    score=float(scores[idx]),
                    source="bm25",
                ))
        return docs

    def _tokenize(self, text: str) -> list[str]:
        """간단한 한국어 토크나이저 (2글자 이상)"""
        tokens = re.findall(r'[가-힣a-zA-Z0-9]+', text.lower())
        return [t for t in tokens if len(t) >= 2]
