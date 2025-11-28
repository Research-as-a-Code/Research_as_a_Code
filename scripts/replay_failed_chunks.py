#!/usr/bin/env python3
"""
Replay Failed Chunks - Retry ingestion of previously failed chunks

Usage:
    python replay_failed_chunks.py <collection_name>
    
Example:
    python replay_failed_chunks.py us_tariffs
    
This will:
1. Scan /data/ingestion_failures/{collection}/ for failure logs
2. Load failed chunks
3. Retry embedding and ingestion
4. Report results
"""

import os
import sys
import json
import time
from pathlib import Path
from typing import List
import httpx
from pymilvus import connections, Collection
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

MILVUS_HOST = os.getenv("MILVUS_HOST", "milvus-standalone")
MILVUS_PORT = os.getenv("MILVUS_PORT", "19530")
EMBEDDING_NIM_URL = os.getenv("EMBEDDING_NIM_URL", "http://embedding-service.nim.svc.cluster.local:8000")
FAILURE_LOG_DIR = Path(os.getenv("FAILURE_LOG_DIR", "/data/ingestion_failures"))


def get_embedding(text: str, nim_url: str) -> List[float]:
    """Get embedding for a single chunk"""
    try:
        response = httpx.post(
            f"{nim_url}/v1/embeddings",
            json={"input": [text], "model": "snowflake/arctic-embed-l", "input_type": "passage"},
            timeout=60.0
        )
        if response.status_code == 200:
            return response.json()["data"][0]["embedding"]
    except Exception as e:
        logger.error(f"Embedding error: {e}")
    return None


def replay_failures(collection_name: str):
    """Replay all failed chunks for a collection"""
    
    print(f"🔄 Replaying Failed Chunks for: {collection_name}")
    print("=" * 80)
    print()
    
    # Connect to Milvus
    logger.info(f"🔌 Connecting to Milvus...")
    connections.connect(alias="default", host=MILVUS_HOST, port=MILVUS_PORT)
    collection = Collection(collection_name)
    logger.info(f"  ✅ Connected to collection: {collection_name}")
    print()
    
    # Find failure logs
    failure_dir = FAILURE_LOG_DIR / collection_name
    if not failure_dir.exists():
        logger.info(f"✅ No failure logs found for {collection_name}")
        logger.info(f"   Directory: {failure_dir}")
        return
    
    failure_files = sorted(failure_dir.glob("*.json"))
    logger.info(f"📂 Found {len(failure_files)} failure log files")
    print()
    
    total_chunks = 0
    total_recovered = 0
    total_still_failed = 0
    
    for fail_file in failure_files:
        logger.info(f"📄 Processing: {fail_file.name}")
        
        with open(fail_file, 'r', encoding='utf-8') as f:
            failure_record = json.load(f)
        
        source_file = failure_record['source_file']
        chunks = failure_record['chunks']
        total_chunks += len(chunks)
        
        logger.info(f"   Source: {source_file}")
        logger.info(f"   Chunks: {len(chunks)}")
        logger.info(f"   Original error: {failure_record['error']}")
        
        # Retry each chunk
        recovered = []
        still_failed = []
        
        for idx, chunk in enumerate(chunks, 1):
            text = chunk['full_text']
            
            logger.info(f"   Retrying chunk {idx}/{len(chunks)}...")
            embedding = get_embedding(text, EMBEDDING_NIM_URL)
            
            if embedding:
                recovered.append((embedding, text, source_file))
                logger.info(f"      ✅ Recovered!")
            else:
                still_failed.append(chunk)
                logger.error(f"      ❌ Still failed")
            
            time.sleep(0.1)
        
        # Insert recovered chunks
        if recovered:
            embeddings = [r[0] for r in recovered]
            texts = [r[1] for r in recovered]
            sources = [r[2] for r in recovered]
            
            collection.insert([embeddings, texts, sources])
            collection.flush()
            logger.info(f"   💾 Inserted {len(recovered)} recovered chunks")
            total_recovered += len(recovered)
        
        total_still_failed += len(still_failed)
        
        # Archive processed failure log
        archive_dir = failure_dir / "processed"
        archive_dir.mkdir(exist_ok=True)
        fail_file.rename(archive_dir / fail_file.name)
        logger.info(f"   📦 Archived to: processed/{fail_file.name}")
        print()
    
    # Summary
    print("=" * 80)
    print(f"✅ REPLAY COMPLETE!")
    print("=" * 80)
    print(f"Total chunks attempted: {total_chunks}")
    print(f"Recovered: {total_recovered} ({total_recovered/total_chunks*100:.1f}%)")
    print(f"Still failed: {total_still_failed}")
    print(f"Collection now has: {collection.num_entities:,} chunks")
    print()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python replay_failed_chunks.py <collection_name>")
        print("Example: python replay_failed_chunks.py us_tariffs")
        sys.exit(1)
    
    collection_name = sys.argv[1]
    replay_failures(collection_name)

