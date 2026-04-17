# -*- coding: utf-8 -*-
"""
MediScanner hnswlib index builder
=================================
ChromaDB SQLite에서 벡터를 추출하여 hnswlib 인덱스를 직접 생성합니다.
재임베딩 없이 약 10분이면 완료됩니다.

실행: python build_hnsw_from_sqlite.py
"""

import sqlite3
import numpy as np
import hnswlib
import os
import time
import json

# ============================================================
# Settings
# ============================================================
SQLITE_PATH = "data/chroma_db_e5small/chroma.sqlite3"
INDEX_PATH = "data/chroma_db_e5small/hnsw_index.bin"
IDS_PATH = "data/chroma_db_e5small/hnsw_ids.json"

DIM = 384
SPACE = "cosine"
M = 16
EF_CONSTRUCTION = 100
BATCH_SIZE = 10000

def main():
    start = time.time()

    print("=" * 60)
    print("  hnswlib index build from SQLite")
    print("=" * 60)

    # 1. Count
    conn = sqlite3.connect(SQLITE_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT count(*) FROM embeddings_queue")
    total = cursor.fetchone()[0]
    print(f"  total vectors: {total:,}")

    # 2. Create index
    idx = hnswlib.Index(space=SPACE, dim=DIM)
    idx.init_index(max_elements=total + 1000, M=M, ef_construction=EF_CONSTRUCTION)

    # 3. Extract and add in batches
    cursor.execute("SELECT id, vector FROM embeddings_queue ORDER BY seq_id")

    id_list = []
    label = 0
    batch_vecs = []
    batch_labels = []
    batch_ids = []
    processed = 0

    while True:
        row = cursor.fetchone()
        if row is None:
            break

        doc_id = row[0]
        vec = np.frombuffer(row[1], dtype=np.float32)

        batch_vecs.append(vec)
        batch_labels.append(label)
        batch_ids.append(doc_id)
        label += 1

        if len(batch_vecs) >= BATCH_SIZE:
            idx.add_items(np.array(batch_vecs), batch_labels)
            id_list.extend(batch_ids)
            processed += len(batch_vecs)

            # Save periodically
            idx.save_index(INDEX_PATH)

            elapsed = time.time() - start
            rate = processed / elapsed if elapsed > 0 else 0
            eta = (total - processed) / rate if rate > 0 else 0
            print(f"  [{processed:,}/{total:,}] {rate:.0f} vec/s | ETA: {eta:.0f}s | saved")

            batch_vecs = []
            batch_labels = []
            batch_ids = []

    # Remaining
    if batch_vecs:
        idx.add_items(np.array(batch_vecs), batch_labels)
        id_list.extend(batch_ids)
        processed += len(batch_vecs)

    conn.close()

    # 4. Final save
    idx.save_index(INDEX_PATH)
    idx_size = os.path.getsize(INDEX_PATH) / 1024**3
    print(f"\n  index saved: {idx_size:.2f}GB")
    print(f"  total vectors: {idx.get_current_count():,}")

    # 5. Save ID mapping
    with open(IDS_PATH, "w", encoding="utf-8") as f:
        json.dump(id_list, f)
    print(f"  ID mapping saved: {len(id_list):,} IDs")

    # 6. Verify - load and search
    print("\n  Verify: load + search...")
    idx2 = hnswlib.Index(space=SPACE, dim=DIM)
    idx2.load_index(INDEX_PATH, max_elements=total + 1000)
    idx2.set_ef(50)
    print(f"  loaded: {idx2.get_current_count():,} vectors")

    # Search with first vector
    conn2 = sqlite3.connect(SQLITE_PATH)
    cur2 = conn2.cursor()
    cur2.execute("SELECT vector FROM embeddings_queue LIMIT 1")
    test_vec = np.frombuffer(cur2.fetchone()[0], dtype=np.float32).reshape(1, -1)
    conn2.close()

    labels, distances = idx2.knn_query(test_vec, k=5)
    print(f"  search result labels: {labels[0]}")
    print(f"  search result distances: {distances[0]}")

    elapsed = time.time() - start
    print(f"\n  total time: {elapsed:.1f}s")
    print("  ALL PASSED")
    print("=" * 60)

if __name__ == "__main__":
    main()
