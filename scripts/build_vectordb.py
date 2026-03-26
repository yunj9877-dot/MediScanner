"""
닥터가디언 - ChromaDB 벡터DB 구축 스크립트
AI Hub 필수의료 의학지식 JSON → ChromaDB 변환

실행 방법:
    python scripts/build_vectordb.py --data_dir ./raw_data/필수의료

테스트 검색:
    python scripts/build_vectordb.py --data_dir ./raw_data/필수의료 --test_only
"""

import json
import os
import sys
import re
import time
import argparse
from pathlib import Path


# ============================================================
# 1. 설정
# ============================================================

CHUNK_SIZE = 500          # 한 청크 최대 글자 수
CHUNK_OVERLAP = 50        # 청크 간 겹치는 글자 수
COLLECTION_NAME = "medical_knowledge"
CHROMA_DB_PATH = "./data/chroma_db"
BATCH_SIZE = 100          # 한 번에 DB에 넣는 개수

# 임베딩 모델 (A/B 테스트용으로 교체 가능)
# 옵션 A: "jhgan/ko-sroberta-multitask"       ← 한국어 특화 (기본값)
# 옵션 B: "intfloat/multilingual-e5-base"     ← 다국어 대형
# 옵션 C: "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"  ← 경량
EMBEDDING_MODEL = "jhgan/ko-sroberta-multitask"


# ============================================================
# 2. JSON 파일 읽기
# ============================================================

def load_json_files(data_dir: str) -> list:
    """AI Hub JSON 파일들을 읽어서 리스트로 반환"""
    documents = []
    error_count = 0

    data_path = Path(data_dir)
    json_files = list(data_path.rglob("*.json"))

    print(f"\n📂 폴더: {data_dir}")
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

    print(f"✅ 로드 완료: {len(documents):,}건 (오류: {error_count}건)\n")
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
    """문서 → 청크로 변환, (ids, metadatas, texts) 반환"""
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
# 4. ChromaDB에 저장
# ============================================================

def build_chromadb(ids, metadatas, texts, db_path, resume=False):
    """ChromaDB에 임베딩 + 저장"""
    import chromadb
    from chromadb.utils import embedding_functions

    print(f"🔧 ChromaDB 설정")
    print(f"   DB 경로: {db_path}")
    print(f"   임베딩 모델: {EMBEDDING_MODEL}")
    print(f"   모드: {'이어하기 (resume)' if resume else '신규 구축'}")

    # 임베딩 함수
    embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=EMBEDDING_MODEL
    )

    # DB 클라이언트
    client = chromadb.PersistentClient(path=db_path)

    if resume:
        # 이어하기: 기존 컬렉션 유지
        try:
            collection = client.get_collection(
                name=COLLECTION_NAME,
                embedding_function=embedding_fn,
            )
            existing_count = collection.count()
            print(f"   📦 기존 청크: {existing_count:,}개")

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
                metadata={"description": "닥터가디언 의학지식 코퍼스"}
            )
    else:
        # 신규: 기존 컬렉션 삭제 후 생성
        try:
            client.delete_collection(COLLECTION_NAME)
            print("   ⚠️ 기존 컬렉션 삭제됨")
        except:
            pass

        collection = client.create_collection(
            name=COLLECTION_NAME,
            embedding_function=embedding_fn,
            metadata={"description": "닥터가디언 의학지식 코퍼스"}
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
# 5. 테스트 검색
# ============================================================

def test_search(db_path):
    """ChromaDB 테스트 검색"""
    import chromadb
    from chromadb.utils import embedding_functions

    embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=EMBEDDING_MODEL
    )
    client = chromadb.PersistentClient(path=db_path)
    collection = client.get_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_fn,
    )

    queries = [
        "고혈압 치료 방법은?",
        "당뇨병 합병증에는 무엇이 있나요?",
        "두통이 심할 때 어떻게 해야 하나요?",
        "임산부가 먹으면 안 되는 약은?",
    ]

    print(f"🔍 테스트 검색 ({collection.count():,}개 청크)")
    print("=" * 60)

    for query in queries:
        results = collection.query(query_texts=[query], n_results=3)

        print(f"\n❓ {query}")
        print("-" * 50)
        for i, (doc, meta) in enumerate(
            zip(results["documents"][0], results["metadatas"][0])
        ):
            print(f"   [{i+1}] 📌 {meta['source_spec']}")
            print(f"       {doc[:120]}...")
            print()


# ============================================================
# 6. 메인
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="닥터가디언 ChromaDB 구축")
    parser.add_argument("--data_dir", required=True, help="JSON 폴더 경로")
    parser.add_argument("--db_path", default=CHROMA_DB_PATH, help="DB 저장 경로")
    parser.add_argument("--test_only", action="store_true", help="테스트만 실행")
    parser.add_argument("--max_docs", type=int, default=0, help="최대 문서 수 (0=전체)")
    parser.add_argument("--no_confirm", action="store_true", help="확인 없이 바로 진행")
    parser.add_argument("--resume", action="store_true", help="이어하기 (기존 데이터 유지, 새 청크만 추가)")
    args = parser.parse_args()

    if args.test_only:
        test_search(args.db_path)
        return

    print("=" * 60)
    print("🏥 닥터가디언 - ChromaDB 벡터DB 구축")
    print("=" * 60)

    # 1) JSON 로드
    documents = load_json_files(args.data_dir)
    if not documents:
        print("❌ JSON 파일이 없습니다. 경로를 확인하세요.")
        sys.exit(1)

    # max_docs 제한
    if args.max_docs > 0 and len(documents) > args.max_docs:
        documents = documents[:args.max_docs]
        print(f"📌 --max_docs={args.max_docs} → {len(documents):,}건으로 제한\n")

    # 2) 청킹
    print(f"✂️ 청킹 중... (chunk_size={CHUNK_SIZE})")
    ids, metadatas, texts = process_documents(documents)
    print(f"   {len(documents):,}건 → {len(ids):,}개 청크\n")

    # 확인 단계
    if not args.no_confirm:
        answer = input(f"💡 {len(ids):,}개 청크를 임베딩합니다. 계속할까요? (y/n): ")
        if answer.lower() != "y":
            print("취소되었습니다.")
            return

    # 3) ChromaDB 저장
    build_chromadb(ids, metadatas, texts, args.db_path, resume=args.resume)

    # 4) 테스트
    test_search(args.db_path)

    print("=" * 60)
    print("🎉 완료! ChromaDB 위치:", args.db_path)
    print("=" * 60)


if __name__ == "__main__":
    main()
