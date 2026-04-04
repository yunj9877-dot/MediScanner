"""
MediScanner - ChromaDB 벡터DB 구축 스크립트
AI Hub 필수의료 의학지식 JSON → ChromaDB 변환

실행 방법:
    python scripts/build_vectordb.py --data_dir ./raw_data/필수의료

테스트 검색:
    python scripts/build_vectordb.py --data_dir ./raw_data/필수의료 --test_only

[2026-03-28 업데이트]
- 임베딩 모델: ko-sroberta → multilingual-e5-large
- 청크 크기: 500 → 800
- config.py에서 설정 import (일원화)
"""

import json
import os
import sys
import re
import time
import argparse
from pathlib import Path

# [변경] config.py에서 설정 import (설정 일원화)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.config import (
    EMBEDDING_MODEL,
    EMBEDDING_DIMENSION,
    CHUNK_SIZE,
    CHUNK_OVERLAP,
    COLLECTION_NAME,
    CHROMA_DB_PATH,
    EMBEDDING_BATCH_SIZE,
    E5_PASSAGE_PREFIX,
    E5_QUERY_PREFIX,
)


# ============================================================
# 1. 설정 (config.py에서 가져옴)
# ============================================================

BATCH_SIZE = EMBEDDING_BATCH_SIZE  # config.py에서 가져옴


# ============================================================
# 2. JSON 파일 읽기
# ============================================================

def load_json_files(data_dir: str) -> list:
    """AI Hub JSON 파일들을 읽어서 리스트로 반환"""
    documents = []
    error_count = 0

    data_path = Path(data_dir)
    json_files = list(data_path.rglob("*.json"))

    print(f"\n📁 폴더: {data_dir}")
    print(f"📄 JSON 파일 발견: {len(json_files):,}개")

    for filepath in json_files:
        try:
            with open(filepath, "r", encoding="utf-8-sig") as f:
                data = json.load(f)

            if "content" not in data or not data["content"].strip():
                continue

            documents.append({
                "c_id": str(data.get("c_id", "")),
                "source_spec": str(data.get("source_spec", "")),
                "creation_year": str(data.get("creation_year", "")),
                "content": data["content"].strip(),
                "filename": filepath.name,
            })
        except Exception as e:
            error_count += 1
            if error_count <= 3:
                print(f"  ⚠️ 읽기 실패: {filepath.name} - {e}")

    if error_count > 3:
        print(f"  ⚠️ 외 {error_count - 3}건 추가 오류")

    print(f"✓ 로드 완료: {len(documents):,}건 (오류: {error_count}건)\n")
    return documents


# ============================================================
# 3. 텍스트 청킹
# ============================================================

def chunk_text(text: str) -> list:
    """긴 텍스트를 문장 단위로 분할"""
    if len(text) <= CHUNK_SIZE:
        return [text]

    sentences = re.split(r'(?<=[.!?다요])\s+', text)
    chunks = []
    current = ""

    for sent in sentences:
        if len(current) + len(sent) > CHUNK_SIZE and current:
            chunks.append(current.strip())
            if CHUNK_OVERLAP > 0 and len(current) > CHUNK_OVERLAP:
                current = current[-CHUNK_OVERLAP:] + " " + sent
            else:
                current = sent
        else:
            current = (current + " " + sent).strip() if current else sent

    if current.strip():
        chunks.append(current.strip())

    return chunks


def process_documents(documents: list) -> tuple:
    """문서 → 청크로 변환 (ids, metadatas, texts) 반환"""
    ids, metadatas, texts = [], [], []

    for doc in documents:
        chunks = chunk_text(doc["content"])
        for i, chunk in enumerate(chunks):
            ids.append(f"{doc['filename']}_{doc['c_id']}_c{i}")
            texts.append(chunk)
            metadatas.append({
                "c_id": doc["c_id"],
                "source_spec": doc["source_spec"],
                "creation_year": doc["creation_year"],
                "chunk_index": i,
                "total_chunks": len(chunks),
                "filename": doc["filename"],
            })

    return ids, metadatas, texts


# ============================================================
# 4. ChromaDB 저장
# ============================================================

class E5EmbeddingFunction:
    """
    multilingual-e5용 커스텀 임베딩 함수
    문서 저장 시 "passage: " prefix 자동 추가
    """
    def __init__(self, model_name: str):
        from sentence_transformers import SentenceTransformer
        print(f"▶ 임베딩 모델 로딩: {model_name}...")
        self.model = SentenceTransformer(model_name)
        print(f"✓ 임베딩 모델 로딩 완료")
    
    def __call__(self, input: list[str]) -> list[list[float]]:
        # [중요] passage prefix 추가
        texts_with_prefix = [f"{E5_PASSAGE_PREFIX}{text}" for text in input]
        embeddings = self.model.encode(texts_with_prefix)
        return embeddings.tolist()


def build_chromadb(ids, metadatas, texts, db_path, resume=False):
    """ChromaDB에 임베딩 + 저장"""
    import chromadb

    print(f"🔧 ChromaDB 설정")
    print(f"   DB 경로: {db_path}")
    print(f"   임베딩 모델: {EMBEDDING_MODEL}")
    print(f"   임베딩 차원: {EMBEDDING_DIMENSION}")
    print(f"   청크 크기: {CHUNK_SIZE}자")
    print(f"   모드: {'이어쓰기 (resume)' if resume else '새로 구축'}")

    # 커스텀 임베딩 함수 (passage prefix 적용)
    embedding_fn = E5EmbeddingFunction(EMBEDDING_MODEL)

    # DB 클라이언트
    client = chromadb.PersistentClient(path=db_path)

    if resume:
        # 이어쓰기: 기존 컬렉션 유지
        try:
            collection = client.get_collection(
                name=COLLECTION_NAME,
                embedding_function=embedding_fn,
            )
            existing_count = collection.count()
            print(f"   ▶ 기존 청크: {existing_count:,}개")

            # 이미 있는 ID 목록 가져오기
            existing_ids = set()
            batch_size = 5000
            for offset in range(0, existing_count, batch_size):
                result = collection.get(limit=batch_size, offset=offset)
                existing_ids.update(result["ids"])

            # 새로 추가할 것만 필터링
            new_ids, new_metadatas, new_texts = [], [], []
            for i in range(len(ids)):
                if ids[i] not in existing_ids:
                    new_ids.append(ids[i])
                    new_metadatas.append(metadatas[i])
                    new_texts.append(texts[i])

            skipped = len(ids) - len(new_ids)
            print(f"   ⏭️ 건너뛰기: {skipped:,}개 (이미 존재)")
            print(f"   ➕ 새로 추가: {len(new_ids):,}개")

            ids, metadatas, texts = new_ids, new_metadatas, new_texts

            if not ids:
                print("\n✅ 모든 청크가 이미 저장되어 있습니다!")
                return collection

        except Exception:
            print("   ⚠️ 기존 컬렉션 없음 → 새로 생성합니다")
            collection = client.create_collection(
                name=COLLECTION_NAME,
                embedding_function=embedding_fn,
                metadata={"description": "MediScanner 의학지식 코퍼스"}
            )
    else:
        # 새로: 기존 컬렉션 삭제 후 생성
        try:
            client.delete_collection(COLLECTION_NAME)
            print("   ⚠️ 기존 컬렉션 삭제됨")
        except:
            pass

        collection = client.create_collection(
            name=COLLECTION_NAME,
            embedding_function=embedding_fn,
            metadata={"description": "MediScanner 의학지식 코퍼스"}
        )

    # 배치 저장
    total = len(ids)
    print(f"\n📥 {total:,}개 청크 저장 시작...\n")
    start = time.time()

    for i in range(0, total, BATCH_SIZE):
        end = min(i + BATCH_SIZE, total)

        collection.add(
            ids=ids[i:end],
            documents=texts[i:end],
            metadatas=metadatas[i:end],
        )

        elapsed = time.time() - start
        speed = end / elapsed if elapsed > 0 else 0
        remaining = (total - end) / speed if speed > 0 else 0
        pct = end / total * 100

        print(f"   [{pct:5.1f}%] {end:,}/{total:,}  "
              f"({elapsed:.0f}초 경과 | 약 {remaining:.0f}초 남음)")

    elapsed_total = time.time() - start
    print(f"\n✅ 저장 완료! ({elapsed_total:.1f}초 = {elapsed_total/60:.1f}분)")
    print(f"   저장된 청크: {collection.count():,}개\n")

    return collection


# ============================================================
# 5. BM25 캐시 생성
# ============================================================

def build_bm25_cache(db_path):
    """BM25 인덱스 구축 + pickle 캐시 저장 (UI 시작 시간 단축)"""
    import pickle
    import chromadb
    from rank_bm25 import BM25Okapi
    
    cache_path = os.path.join(os.path.dirname(__file__), "..", "bm25_cache.pkl")
    cache_path = os.path.abspath(cache_path)
    
    print(f"\n📦 BM25 캐시 생성 중...")
    print(f"   캐시 경로: {cache_path}")
    
    # ChromaDB에서 전체 문서 로드
    client = chromadb.PersistentClient(path=db_path)
    collection = client.get_collection(name=COLLECTION_NAME)
    count = collection.count()
    
    print(f"   총 청크: {count:,}개")
    
    all_docs, all_metadatas, all_ids = [], [], []
    
    for offset in range(0, count, 5000):
        result = collection.get(limit=5000, offset=offset, include=["documents", "metadatas"])
        if result["documents"]:
            all_docs.extend(result["documents"])
            all_metadatas.extend(result["metadatas"])
            all_ids.extend(result["ids"])
        
        pct = min(offset + 5000, count) / count * 100
        print(f"   [{pct:5.1f}%] 문서 로딩 중...")
    
    # 토크나이징
    def tokenize_korean(text: str) -> list[str]:
        tokens = re.findall(r'[가-힣a-zA-Z0-9]+', text.lower())
        return [t for t in tokens if len(t) >= 2]
    
    print(f"   토크나이징 중...")
    tokenized_docs = [tokenize_korean(d) for d in all_docs]
    
    # BM25 인덱스 생성
    print(f"   BM25 인덱스 생성 중...")
    bm25 = BM25Okapi(tokenized_docs)
    
    # 캐시 저장
    with open(cache_path, "wb") as f:
        pickle.dump({
            "docs": all_docs,
            "metadatas": all_metadatas,
            "ids": all_ids,
            "bm25": bm25,
        }, f)
    
    cache_size_mb = os.path.getsize(cache_path) / (1024 * 1024)
    print(f"✅ BM25 캐시 저장 완료! ({cache_size_mb:.1f}MB)")
    print(f"   → UI 시작 시 캐시 로딩으로 빠른 시작 가능\n")


# ============================================================
# 6. 테스트 검색
# ============================================================

def test_search(db_path):
    """ChromaDB 테스트 검색"""
    import chromadb
    from sentence_transformers import SentenceTransformer
    
    # 검색용 모델 로드 (query prefix 직접 적용 위해)
    print(f"▶ 테스트용 임베딩 모델 로딩...")
    model = SentenceTransformer(EMBEDDING_MODEL)
    
    client = chromadb.PersistentClient(path=db_path)
    # [중요] embedding_function 없이 가져옴 - query_embeddings 직접 사용할 것
    collection = client.get_collection(name=COLLECTION_NAME)

    queries = [
        "고혈압 치료 방법은?",
        "당뇨병 합병증에서 무엇이 있나요?",
        "두통이 심할 때 어떻게 해야 하나요?",
        "임산부가 먹으면 안 되는 음식은?",
    ]

    print(f"🔍 테스트 검색 ({collection.count():,}개 청크)")
    print("=" * 60)

    for query in queries:
        # [중요] 검색 시 query prefix 적용 후 직접 임베딩
        query_with_prefix = f"{E5_QUERY_PREFIX}{query}"
        query_embedding = model.encode(query_with_prefix).tolist()
        
        # query_embeddings 사용 (query_texts 아님!)
        results = collection.query(query_embeddings=[query_embedding], n_results=3)

        print(f"\n❓ {query}")
        print("-" * 50)
        for i, (doc, meta) in enumerate(
            zip(results["documents"][0], results["metadatas"][0])
        ):
            print(f"   [{i+1}] 📎 {meta['source_spec']}")
            print(f"       {doc[:120]}...")
            print()


# ============================================================
# 7. 메인
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="MediScanner ChromaDB 구축")
    parser.add_argument("--data_dir", required=True, help="JSON 폴더 경로")
    parser.add_argument("--db_path", default=CHROMA_DB_PATH, help="DB 저장 경로")
    parser.add_argument("--test_only", action="store_true", help="테스트만 실행")
    parser.add_argument("--max_docs", type=int, default=0, help="최대 문서 수 (0=전체)")
    parser.add_argument("--no_confirm", action="store_true", help="확인 없이 바로 진행")
    parser.add_argument("--resume", action="store_true", help="이어쓰기 (기존 데이터 유지, 새 청크만 추가)")
    args = parser.parse_args()

    if args.test_only:
        test_search(args.db_path)
        return

    print("=" * 60)
    print("🏥 MediScanner - ChromaDB 벡터DB 구축")
    print(f"   임베딩 모델: {EMBEDDING_MODEL}")
    print(f"   임베딩 차원: {EMBEDDING_DIMENSION}")
    print(f"   청크 크기: {CHUNK_SIZE}자")
    print("=" * 60)

    # 1) JSON 로드
    documents = load_json_files(args.data_dir)
    if not documents:
        print("❌ JSON 파일이 없습니다. 경로를 확인하세요.")
        sys.exit(1)

    # max_docs 제한
    if args.max_docs > 0 and len(documents) > args.max_docs:
        documents = documents[:args.max_docs]
        print(f"📎 --max_docs={args.max_docs} → {len(documents):,}건으로 제한\n")

    # 2) 청킹
    print(f"✂️ 청킹 중... (chunk_size={CHUNK_SIZE})")
    ids, metadatas, texts = process_documents(documents)
    print(f"   {len(documents):,}건 → {len(ids):,}개 청크\n")

    # 확인 질의
    if not args.no_confirm:
        answer = input(f"📌 {len(ids):,}개 청크를 임베딩합니다. 계속할까요? (y/n): ")
        if answer.lower() != "y":
            print("취소되었습니다")
            return

    # 3) ChromaDB 저장
    build_chromadb(ids, metadatas, texts, args.db_path, resume=args.resume)

    # 4) BM25 캐시 생성 (UI 빠른 시작용)
    build_bm25_cache(args.db_path)

    # 5) 테스트
    test_search(args.db_path)

    print("=" * 60)
    print("🎉 완료! ChromaDB 위치:", args.db_path)
    print("=" * 60)


if __name__ == "__main__":
    main()
