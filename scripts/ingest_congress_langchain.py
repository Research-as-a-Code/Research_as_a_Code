#!/usr/bin/env python3
"""
Congress Plain Text Ingestion with LangChain

For plain text files (no markdown, no headers):
- Simple extraction (no Docling needed)
- RecursiveCharacterTextSplitter with paragraph/sentence separators
- All reliability features (retry, persist failures, incremental)
"""

import os
import sys
import time
import json
from pathlib import Path
from typing import List, Dict, Set, Tuple
from datetime import datetime
import httpx
from pymilvus import connections, Collection, CollectionSchema, FieldSchema, DataType, utility
import logging

from langchain_text_splitters import RecursiveCharacterTextSplitter

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration
MILVUS_HOST = os.getenv("MILVUS_HOST", "milvus-standalone")
MILVUS_PORT = os.getenv("MILVUS_PORT", "19530")
EMBEDDING_NIM_URL = os.getenv("EMBEDDING_NIM_URL", "http://embedding-service.nim.svc.cluster.local:8000")
EMBEDDING_DIM = 1024
BATCH_SIZE = 10
# Failure persistence configuration (directory created when needed, not at import time)
FAILURE_LOG_DIR = Path(os.getenv("FAILURE_LOG_DIR", "/data/ingestion_failures"))


def extract_text(file_path: str) -> str:
    """Simple text file extraction (no Docling needed)"""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            text = f.read()
        logger.info(f"    📝 Read {len(text)} characters")
        return text
    except Exception as e:
        logger.error(f"    ❌ Error reading file: {e}")
        return ""


def chunk_plain_text(text: str, filename: str) -> List[Dict]:
    """
    Chunk plain text using RecursiveCharacterTextSplitter
    
    Optimized for legislative/congressional text:
    - Splits on paragraphs first (\n\n)
    - Then sentences (. )
    - Good balance of granularity and semantic coherence
    """
    try:
        logger.info(f"    🔧 Chunking with RecursiveCharacterTextSplitter...")
        
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            separators=["\n\n", "\n", ". ", ", ", " ", ""],  # Paragraph → sentence → word
            length_function=len,
        )
        
        text_chunks = splitter.split_text(text)
        
        chunks = [
            {
                "text": chunk,
                "metadata": {"source": filename, "chunking": "recursive_char"}
            }
            for chunk in text_chunks
        ]
        
        logger.info(f"    ✅ Created {len(chunks)} chunks")
        if chunks:
            avg = sum(len(c["text"]) for c in chunks) / len(chunks)
            logger.info(f"       Avg size: {avg:.0f} chars")
        
        return chunks
        
    except Exception as e:
        logger.error(f"    ❌ Chunking error: {e}")
        return []


def persist_failed_chunks(chunks: List[Dict], filename: str, error: str, collection_name: str):
    """Persist failed chunks to disk"""
    try:
        failure_dir = FAILURE_LOG_DIR / collection_name
        failure_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        failure_file = failure_dir / f"{timestamp}_{filename}.json"
        
        failure_record = {
            "timestamp": datetime.now().isoformat(),
            "collection": collection_name,
            "source_file": filename,
            "error": str(error),
            "chunk_count": len(chunks),
            "chunks": chunks
        }
        
        with open(failure_file, 'w', encoding='utf-8') as f:
            json.dump(failure_record, f, indent=2, ensure_ascii=False)
        
        logger.info(f"    💾 Failed chunks persisted: {failure_file.name}")
        
    except Exception as e:
        logger.error(f"    ⚠️  Could not persist failures: {e}")


def get_embeddings_batch(texts: List[str], nim_url: str, max_retries: int = 3) -> Tuple[List[List[float]], List[Tuple]]:
    """Get embeddings with retry and individual fallback"""
    # Try batch with retries
    for attempt in range(max_retries):
        try:
            response = httpx.post(
                f"{nim_url}/v1/embeddings",
                json={"input": texts, "model": "snowflake/arctic-embed-l", "input_type": "passage"},
                timeout=60.0
            )
            
            if response.status_code == 200:
                return [item["embedding"] for item in response.json()["data"]], []
            elif attempt < max_retries - 1:
                wait_time = 2 ** attempt
                logger.warning(f"    ⚠️  API error {response.status_code}, retry {attempt+1}/{max_retries} in {wait_time}s...")
                time.sleep(wait_time)
            else:
                logger.warning(f"    ⚠️  Batch failed, trying individually...")
                break
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                logger.warning(f"    ⚠️  Error: {e}, retry {attempt+1}/{max_retries} in {wait_time}s...")
                time.sleep(wait_time)
            else:
                logger.warning(f"    ⚠️  Batch failed, trying individually...")
                break
    
    # Individual processing
    logger.info(f"    🔧 Processing {len(texts)} chunks individually...")
    embeddings = []
    failed_indices = []
    
    for idx, text in enumerate(texts):
        try:
            response = httpx.post(
                f"{nim_url}/v1/embeddings",
                json={"input": [text], "model": "snowflake/arctic-embed-l", "input_type": "passage"},
                timeout=60.0
            )
            if response.status_code == 200:
                embeddings.append(response.json()["data"][0]["embedding"])
            else:
                logger.error(f"       ❌ Chunk {idx+1} failed (HTTP {response.status_code})")
                failed_indices.append((idx, text, f"HTTP {response.status_code}"))
            time.sleep(0.05)
        except Exception as e:
            logger.error(f"       ❌ Chunk {idx+1} error: {e}")
            failed_indices.append((idx, text, str(e)))
    
    logger.info(f"    ✅ Individual: {len(embeddings)}/{len(texts)} succeeded")
    return embeddings, failed_indices


def get_already_ingested_files(collection_name: str) -> Set[str]:
    """Query Milvus for already-ingested files"""
    try:
        if not utility.has_collection(collection_name):
            return set()
        
        collection = Collection(collection_name)
        collection.load()
        
        logger.info(f"  🔍 Checking for already-ingested files...")
        file_chunk_counts = {}
        offset = 0
        page_size = 10000
        max_offset = 16000
        
        while offset < max_offset:
            try:
                query_result = collection.query(
                    expr="id >= 0",
                    output_fields=["source"],
                    limit=min(page_size, max_offset - offset),
                    offset=offset
                )
                if not query_result:
                    break
                for item in query_result:
                    file_chunk_counts[item['source']] = file_chunk_counts.get(item['source'], 0) + 1
                if len(query_result) < page_size:
                    break
                offset += len(query_result)
            except Exception as e:
                logger.warning(f"     ⚠️  Error at offset {offset}: {e}")
                break
        
        if file_chunk_counts:
            logger.info(f"  ✅ Found {len(file_chunk_counts)} already-ingested files")
        return set(file_chunk_counts.keys())
    except Exception as e:
        logger.warning(f"  ⚠️  Could not query existing files: {e}")
        return set()


def create_collection(collection_name: str, drop_existing: bool = False):
    """Create or get Milvus collection"""
    if utility.has_collection(collection_name):
        if drop_existing:
            logger.warning(f"  ⚠️  Dropping existing collection '{collection_name}'...")
            utility.drop_collection(collection_name)
        else:
            logger.info(f"  📦 Using existing collection '{collection_name}'")
            return Collection(collection_name)
    
    fields = [
        FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=EMBEDDING_DIM),
        FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
        FieldSchema(name="source", dtype=DataType.VARCHAR, max_length=1024),
    ]
    
    schema = CollectionSchema(fields=fields, description=f"{collection_name} collection")
    collection = Collection(name=collection_name, schema=schema)
    
    index_params = {
        "metric_type": "L2",
        "index_type": "HNSW",
        "params": {"M": 16, "efConstruction": 200}
    }
    collection.create_index(field_name="embedding", index_params=index_params)
    logger.info(f"  ✅ Collection '{collection_name}' created")
    return collection


def ingest_directory(
    collection_name: str,
    data_dir: Path,
    file_pattern: str = "*.txt",
    drop_existing: bool = False
) -> Tuple[int, int, int]:
    """Main congress plain text ingestion"""
    
    print("🚀 Congress Plain Text Ingestion (LangChain)")
    print("=" * 80)
    print(f"Collection: {collection_name}")
    print(f"Data directory: {data_dir}")
    print(f"Method: RecursiveCharacterTextSplitter (1000/200)")
    print(f"Files: Plain text (no Docling needed)")
    print()
    
    connections.connect(alias="default", host=MILVUS_HOST, port=MILVUS_PORT)
    logger.info("  ✅ Connected to Milvus!")
    
    collection = create_collection(collection_name, drop_existing)
    
    already_ingested = set()
    if not drop_existing:
        already_ingested = get_already_ingested_files(collection_name)
    
    print()
    
    files = sorted(data_dir.glob(file_pattern))
    total_files = len(files)
    logger.info(f"📚 Found {total_files} files total")
    
    if already_ingested:
        files = [f for f in files if f.name not in already_ingested]
        logger.info(f"  ⏭️  Skipping {len(already_ingested)} already-ingested files")
        logger.info(f"  ✅ Will process {len(files)} new files")
    
    if not files:
        logger.info("✅ All files already ingested!")
        return 0, len(already_ingested), 0
    
    print()
    
    all_embeddings = []
    all_texts = []
    all_sources = []
    
    success_count = 0
    skipped_count = len(already_ingested)
    failed_count = 0
    
    for idx, file_path in enumerate(files, 1):
        filename = file_path.name
        logger.info(f"📄 [{idx}/{len(files)}] Processing: {filename}")
        
        # Extract text
        text = extract_text(str(file_path))
        
        if not text or len(text) < 100:
            logger.warning(f"    ⚠️  Insufficient text")
            failed_count += 1
            continue
        
        # Chunk text
        chunks = chunk_plain_text(text, filename)
        
        if not chunks:
            failed_count += 1
            continue
        
        # Get embeddings
        chunk_texts = [c["text"] for c in chunks]
        permanently_failed_chunks = []
        
        for i in range(0, len(chunk_texts), BATCH_SIZE):
            batch_texts = chunk_texts[i:i + BATCH_SIZE]
            embeddings, failed_indices = get_embeddings_batch(batch_texts, EMBEDDING_NIM_URL)
            
            for fail_idx, fail_text, fail_error in failed_indices:
                permanently_failed_chunks.append({
                    "text": fail_text,
                    "metadata": chunks[i + fail_idx].get("metadata", {}),
                    "error": fail_error,
                    "batch_index": i + fail_idx
                })
            
            if embeddings:
                all_embeddings.extend(embeddings)
                all_texts.extend(batch_texts[:len(embeddings)])
                all_sources.extend([filename] * len(embeddings))
                logger.info(f"    ✅ Embedded chunks {i+1}-{i+len(embeddings)}")
            
            time.sleep(0.1)
        
        if permanently_failed_chunks:
            persist_failed_chunks(permanently_failed_chunks, filename, "Embedding failures", collection_name)
        
        success_count += 1
        
        # Bulk insert every 25 files OR 5000 chunks
        should_insert = (idx % 25 == 0) or (len(all_embeddings) >= 5000)
        
        if should_insert and all_embeddings:
            logger.info(f"\n💾 Bulk inserting {len(all_embeddings)} chunks...")
            try:
                collection.insert([all_embeddings, all_texts, all_sources])
                collection.flush()
                logger.info(f"  ✅ Inserted! Collection: {collection.num_entities} chunks\n")
            except Exception as e:
                logger.error(f"  ❌ Bulk insert failed: {e}, splitting...")
                for i in range(0, len(all_embeddings), 2500):
                    end = min(i + 2500, len(all_embeddings))
                    collection.insert([all_embeddings[i:end], all_texts[i:end], all_sources[i:end]])
                    collection.flush()
                    logger.info(f"     ✅ Inserted {i+1}-{end}")
            
            all_embeddings = []
            all_texts = []
            all_sources = []
    
    if all_embeddings:
        logger.info(f"\n💾 Inserting final {len(all_embeddings)} chunks...")
        collection.insert([all_embeddings, all_texts, all_sources])
        collection.flush()
    
    logger.info("\n📊 Loading collection...")
    collection.load()
    
    print()
    print("=" * 80)
    print(f"✅ CONGRESS INGESTION COMPLETE!")
    print("=" * 80)
    print(f"Collection: {collection_name}")
    print(f"Total chunks: {collection.num_entities:,}")
    print(f"Files processed: {success_count}")
    print(f"Files skipped: {skipped_count}")
    print(f"Files failed: {failed_count}")
    print()
    
    return success_count, skipped_count, failed_count


def main():
    collection = os.getenv("COLLECTION_NAME", "congress")
    data_dir = os.getenv("DATA_DIR", "/data/congress")
    pattern = os.getenv("FILE_PATTERN", "*.txt")
    drop = os.getenv("DROP_EXISTING", "false").lower() == "true"
    
    logger.info(f"🎯 Congress Configuration:")
    logger.info(f"   Collection: {collection}")
    logger.info(f"   Data dir: {data_dir}")
    logger.info(f"   Pattern: {pattern}")
    logger.info(f"   Drop existing: {drop}")
    logger.info(f"   Method: RecursiveCharacterTextSplitter")
    logger.info("")
    
    start_time = time.time()
    success, skipped, failed = ingest_directory(
        collection_name=collection,
        data_dir=Path(data_dir),
        file_pattern=pattern,
        drop_existing=drop
    )
    elapsed = time.time() - start_time
    
    print(f"⏱️  Total time: {elapsed/60:.1f} minutes")
    print()
    
    total = success + failed
    if total > 0 and failed > success:
        sys.exit(1)
    else:
        logger.info(f"✅ Success!")
        sys.exit(0)


if __name__ == "__main__":
    main()

