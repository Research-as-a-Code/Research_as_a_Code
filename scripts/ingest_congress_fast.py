#!/usr/bin/env python3
"""
FAST Congress Ingestion - Based on working tariff script
Uses batched embeddings and bulk inserts for 100x speedup!
"""

import os
import sys
import time
from pathlib import Path
from typing import List
import httpx
from pymilvus import connections, Collection, CollectionSchema, FieldSchema, DataType, utility

# Configuration
MILVUS_HOST = os.getenv("MILVUS_HOST", "milvus.rag-blueprint.svc.cluster.local")
MILVUS_PORT = os.getenv("MILVUS_PORT", "19530")
EMBEDDING_NIM_URL = os.getenv("EMBEDDING_NIM_URL", "http://embedding-service.nim.svc.cluster.local:8000")
COLLECTION_NAME = "congress"
EMBEDDING_DIM = 1024
CHUNK_SIZE = 500  # Characters per chunk
CHUNK_OVERLAP = 100
BATCH_SIZE = 10  # Embeddings per API call


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """Split text into overlapping chunks"""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()
        if len(chunk) > 50:
            chunks.append(chunk)
        start += (chunk_size - overlap)
    return chunks


def get_embeddings(texts: List[str], nim_url: str) -> List[List[float]]:
    """Get embeddings for a batch of texts (10x faster than one-by-one!)"""
    try:
        response = httpx.post(
            f"{nim_url}/v1/embeddings",
            json={
                "input": texts,  # ← Batch request!
                "model": "snowflake/arctic-embed-l",
                "input_type": "passage"
            },
            timeout=60.0
        )
        
        if response.status_code == 200:
            result = response.json()
            return [item["embedding"] for item in result["data"]]
        else:
            print(f"  ⚠️ Embedding API error: {response.status_code}")
            return []
    except Exception as e:
        print(f"  ⚠️ Embedding error: {e}")
        return []


def create_collection():
    """Create Milvus collection with proper schema"""
    if utility.has_collection(COLLECTION_NAME):
        print(f"  📦 Collection '{COLLECTION_NAME}' already exists")
        return Collection(COLLECTION_NAME)
    
    fields = [
        FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=EMBEDDING_DIM),
        FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
        FieldSchema(name="source", dtype=DataType.VARCHAR, max_length=1024),
    ]
    
    schema = CollectionSchema(fields=fields, description=f"{COLLECTION_NAME} collection")
    collection = Collection(name=COLLECTION_NAME, schema=schema)
    
    # Create HNSW index for fast search
    index_params = {
        "metric_type": "L2",
        "index_type": "HNSW",
        "params": {"M": 16, "efConstruction": 200}
    }
    collection.create_index(field_name="embedding", index_params=index_params)
    print(f"  ✅ Collection '{COLLECTION_NAME}' created!")
    return collection


def ingest_texts(text_dir: str):
    """Main ingestion pipeline - FAST version with batching!"""
    print("🚀 Starting FAST congress ingestion pipeline...\n")
    
    # Connect to Milvus
    print(f"🔌 Connecting to Milvus at {MILVUS_HOST}:{MILVUS_PORT}")
    connections.connect(alias="default", host=MILVUS_HOST, port=MILVUS_PORT)
    print("  ✅ Connected!\n")
    
    # Create collection
    collection = create_collection()
    print()
    
    # Get list of text files
    text_files = sorted(Path(text_dir).glob("*.txt"))
    total_files = len(text_files)
    print(f"📚 Found {total_files} text files to process\n")
    
    if total_files == 0:
        print("❌ No text files found!")
        return
    
    # Accumulate data for bulk insert
    all_embeddings = []
    all_texts = []
    all_sources = []
    
    for idx, txt_path in enumerate(text_files, 1):
        filename = txt_path.name
        print(f"[{idx}/{total_files}] Processing: {filename}")
        
        # Read text
        try:
            with open(txt_path, 'r', encoding='utf-8', errors='ignore') as f:
                text = f.read()
        except Exception as e:
            print(f"  ⚠️ Error reading file: {e}")
            continue
        
        if len(text) < 100:
            print(f"  ⚠️ Skipping (insufficient text)")
            continue
        
        # Chunk text
        chunks = chunk_text(text)
        print(f"  📄 Extracted {len(chunks)} chunks")
        
        if not chunks:
            continue
        
        # Get embeddings in batches (FAST!)
        for i in range(0, len(chunks), BATCH_SIZE):
            batch = chunks[i:i + BATCH_SIZE]
            embeddings = get_embeddings(batch, EMBEDDING_NIM_URL)
            
            if len(embeddings) == len(batch):
                all_embeddings.extend(embeddings)
                all_texts.extend(batch)
                all_sources.extend([filename] * len(batch))
                print(f"  ✅ Embedded chunks {i+1}-{i+len(batch)}")
            else:
                print(f"  ⚠️ Embedding failed for batch {i}")
            
            time.sleep(0.1)  # Brief rate limiting
        
        # Bulk insert every 50 files (EFFICIENT!)
        if idx % 50 == 0 and all_embeddings:
            print(f"\n💾 Inserting {len(all_embeddings)} chunks into Milvus...")
            collection.insert([all_embeddings, all_texts, all_sources])
            collection.flush()
            print(f"  ✅ Inserted! Total so far: {collection.num_entities}\n")
            
            # Clear buffers
            all_embeddings = []
            all_texts = []
            all_sources = []
    
    # Insert remaining
    if all_embeddings:
        print(f"\n💾 Inserting final {len(all_embeddings)} chunks...")
        collection.insert([all_embeddings, all_texts, all_sources])
        collection.flush()
    
    # Load collection for querying
    print("\n📊 Loading collection for querying...")
    collection.load()
    
    # Final stats
    total_entities = collection.num_entities
    print(f"\n{'='*60}")
    print(f"✅ INGESTION COMPLETE!")
    print(f"{'='*60}")
    print(f"Total chunks in '{COLLECTION_NAME}': {total_entities}")
    print(f"Files processed: {total_files}")
    print(f"Average chunks per file: {total_entities/total_files:.1f}")
    print()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Ingest congress texts into Milvus (FAST)")
    parser.add_argument("--data-dir", default="../data/congress", help="Directory with .txt files")
    args = parser.parse_args()
    
    ingest_texts(args.data_dir)

