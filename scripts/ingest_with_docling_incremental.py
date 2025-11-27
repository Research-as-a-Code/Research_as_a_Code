#!/usr/bin/env python3
"""
Enhanced Document Ingestion using Docling (IBM Research)
WITH INCREMENTAL/RESUME CAPABILITY

Key features:
- Queries Milvus for already-ingested files
- Skips files that already have chunks indexed
- Can resume from crashes/restarts without losing progress
- No need to drop collection on restart
"""

import os
import sys
import time
from pathlib import Path
from typing import List, Tuple, Set
import httpx
from pymilvus import connections, Collection, CollectionSchema, FieldSchema, DataType, utility
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration
MILVUS_HOST = os.getenv("MILVUS_HOST", "milvus.rag-blueprint.svc.cluster.local")
MILVUS_PORT = os.getenv("MILVUS_PORT", "19530")
EMBEDDING_NIM_URL = os.getenv("EMBEDDING_NIM_URL", "http://embedding-service.nim.svc.cluster.local:8000")
EMBEDDING_DIM = 1024
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
BATCH_SIZE = 10


def extract_with_docling(file_path: str) -> str:
    """Extract text using Docling for superior PDF segmentation"""
    try:
        from docling.document_converter import DocumentConverter
        logger.info(f"    🔍 Extracting with Docling...")
        converter = DocumentConverter()
        result = converter.convert(file_path)
        text = result.document.export_to_markdown()
        logger.info(f"    ✅ Extracted {len(text)} characters")
        return text
    except Exception as e:
        logger.error(f"    ❌ Docling extraction error: {e}")
        return ""


def fallback_txt_extraction(file_path: str) -> str:
    """Simple text file extraction"""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    except Exception as e:
        logger.error(f"    ❌ Error reading text file: {e}")
        return ""


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """Split text into overlapping chunks"""
    chunks = []
    start = 0
    text_len = len(text)
    
    while start < text_len:
        end = start + chunk_size
        chunk = text[start:end].strip()
        
        if len(chunk) > 50:
            chunks.append(chunk)
        
        start += (chunk_size - overlap)
    
    return chunks


def get_embeddings_batch(texts: List[str], nim_url: str) -> List[List[float]]:
    """Get embeddings from NIM for a batch of texts"""
    try:
        response = httpx.post(
            f"{nim_url}/v1/embeddings",
            json={
                "input": texts,
                "model": "snowflake/arctic-embed-l",
                "input_type": "passage"
            },
            timeout=60.0
        )
        
        if response.status_code == 200:
            result = response.json()
            return [item["embedding"] for item in result["data"]]
        else:
            logger.error(f"    ❌ Embedding API error: {response.status_code}")
            return []
            
    except Exception as e:
        logger.error(f"    ❌ Embedding error: {e}")
        return []


def get_already_ingested_files(collection_name: str) -> Set[str]:
    """
    Query Milvus to find which files are already ingested (with pagination)
    Returns: Set of filenames that have chunks in the collection
    """
    try:
        if not utility.has_collection(collection_name):
            logger.info(f"  📦 Collection '{collection_name}' doesn't exist yet")
            return set()
        
        collection = Collection(collection_name)
        collection.load()
        
        # Query for all unique source filenames with pagination
        logger.info(f"  🔍 Checking for already-ingested files...")
        
        ingested_files = set()
        offset = 0
        page_size = 10000  # Conservative limit (offset+limit must be <16384)
        max_offset = 16000  # Stay within Milvus window limit
        
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
                
                # Add unique sources from this page
                for item in query_result:
                    ingested_files.add(item['source'])
                
                logger.info(f"     Scanned {offset + len(query_result)} chunks, found {len(ingested_files)} unique files so far...")
                
                # If we got less than requested, we're done
                if len(query_result) < page_size:
                    break
                
                offset += len(query_result)
            except Exception as e:
                logger.warning(f"     ⚠️  Error at offset {offset}: {e}")
                break
        
        logger.info(f"  ✅ Found {len(ingested_files)} already-ingested files")
        
        if ingested_files:
            logger.info(f"     Examples: {list(ingested_files)[:5]}")
        
        return ingested_files
        
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
            logger.info(f"  📦 Using existing collection '{collection_name}' (incremental mode)")
            return Collection(collection_name)
    
    # Define schema
    fields = [
        FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=EMBEDDING_DIM),
        FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
        FieldSchema(name="source", dtype=DataType.VARCHAR, max_length=1024),
    ]
    
    schema = CollectionSchema(fields=fields, description=f"{collection_name} collection")
    collection = Collection(name=collection_name, schema=schema)
    
    # Create HNSW index
    index_params = {
        "metric_type": "L2",
        "index_type": "HNSW",
        "params": {"M": 16, "efConstruction": 200}
    }
    collection.create_index(field_name="embedding", index_params=index_params)
    
    logger.info(f"  ✅ Collection '{collection_name}' created with HNSW index")
    return collection


def ingest_directory(
    collection_name: str,
    data_dir: Path,
    file_pattern: str = "*.pdf",
    drop_existing: bool = False,
    incremental: bool = True
) -> Tuple[int, int, int]:
    """
    Main ingestion pipeline with incremental support
    
    Returns:
        (success_count, skipped_count, failed_count)
    """
    
    print("🚀 Enhanced Document Ingestion with Docling (INCREMENTAL MODE)")
    print("=" * 80)
    print(f"Collection: {collection_name}")
    print(f"Data directory: {data_dir}")
    print(f"File pattern: {file_pattern}")
    print(f"Chunk size: {CHUNK_SIZE} chars, Overlap: {CHUNK_OVERLAP}")
    print(f"Incremental: {incremental}")
    print()
    
    # Connect to Milvus
    logger.info(f"🔌 Connecting to Milvus at {MILVUS_HOST}:{MILVUS_PORT}")
    connections.connect(alias="default", host=MILVUS_HOST, port=MILVUS_PORT)
    logger.info("  ✅ Connected!")
    
    # Create/get collection
    collection = create_collection(collection_name, drop_existing)
    
    # Get already-ingested files if incremental mode
    already_ingested = set()
    if incremental and not drop_existing:
        already_ingested = get_already_ingested_files(collection_name)
    
    print()
    
    # Get files
    files = sorted(data_dir.glob(file_pattern))
    total_files = len(files)
    logger.info(f"📚 Found {total_files} files total")
    
    if already_ingested:
        files_to_process = [f for f in files if f.name not in already_ingested]
        logger.info(f"  ⏭️  Skipping {len(already_ingested)} already-ingested files")
        logger.info(f"  ✅ Will process {len(files_to_process)} new files")
        files = files_to_process
    
    if not files:
        logger.info("✅ All files already ingested!")
        return 0, len(already_ingested), 0
    
    print()
    
    # Accumulate for bulk insert
    all_embeddings = []
    all_texts = []
    all_sources = []
    
    success_count = 0
    skipped_count = len(already_ingested)
    failed_count = 0
    
    for idx, file_path in enumerate(files, 1):
        filename = file_path.name
        logger.info(f"📄 [{idx}/{len(files)}] Processing: {filename}")
        
        # Extract text based on file type
        if file_path.suffix.lower() in ['.pdf', '.docx', '.doc']:
            text = extract_with_docling(str(file_path))
        elif file_path.suffix.lower() == '.txt':
            text = fallback_txt_extraction(str(file_path))
        else:
            logger.warning(f"    ⚠️  Unsupported file type: {file_path.suffix}")
            failed_count += 1
            continue
        
        if not text or len(text) < 100:
            logger.warning(f"    ⚠️  Insufficient text extracted, skipping")
            failed_count += 1
            continue
        
        # Chunk text
        chunks = chunk_text(text)
        logger.info(f"    📝 Split into {len(chunks)} chunks")
        
        if not chunks:
            failed_count += 1
            continue
        
        # Get embeddings in batches
        for i in range(0, len(chunks), BATCH_SIZE):
            batch = chunks[i:i + BATCH_SIZE]
            embeddings = get_embeddings_batch(batch, EMBEDDING_NIM_URL)
            
            if len(embeddings) == len(batch):
                all_embeddings.extend(embeddings)
                all_texts.extend(batch)
                all_sources.extend([filename] * len(batch))
                logger.info(f"    ✅ Embedded chunks {i+1}-{i+len(batch)}")
            else:
                logger.warning(f"    ⚠️  Embedding failed for batch {i}")
            
            time.sleep(0.1)
        
        success_count += 1
        
        # Bulk insert every 50 files
        if idx % 50 == 0 and all_embeddings:
            logger.info(f"\n💾 Bulk inserting {len(all_embeddings)} chunks into Milvus...")
            collection.insert([all_embeddings, all_texts, all_sources])
            collection.flush()
            logger.info(f"  ✅ Inserted! Collection now has {collection.num_entities} total chunks\n")
            
            # Clear buffers
            all_embeddings = []
            all_texts = []
            all_sources = []
    
    # Insert remaining
    if all_embeddings:
        logger.info(f"\n💾 Inserting final {len(all_embeddings)} chunks...")
        collection.insert([all_embeddings, all_texts, all_sources])
        collection.flush()
    
    # Load collection for querying
    logger.info("\n📊 Loading collection for search...")
    collection.load()
    
    # Final stats
    total_entities = collection.num_entities
    print()
    print("=" * 80)
    print(f"✅ INGESTION COMPLETE!")
    print("=" * 80)
    print(f"Collection: {collection_name}")
    print(f"Total chunks in collection: {total_entities}")
    print(f"Files processed (new): {success_count}")
    print(f"Files skipped (already indexed): {skipped_count}")
    print(f"Files failed: {failed_count}")
    if success_count > 0:
        print(f"Average chunks per file: {(total_entities-skipped_count*160)/success_count:.1f}")
    print()
    
    return success_count, skipped_count, failed_count


def main():
    # Get parameters from environment variables (for Kubernetes ConfigMap usage)
    collection = os.getenv("COLLECTION_NAME", "us_tariffs")
    data_dir = os.getenv("DATA_DIR", "/data")
    pattern = os.getenv("FILE_PATTERN", "*.pdf")
    drop = os.getenv("DROP_EXISTING", "false").lower() == "true"
    
    # Incremental mode: enabled unless drop=true
    incremental = not drop
    
    logger.info(f"🎯 Configuration:")
    logger.info(f"   Collection: {collection}")
    logger.info(f"   Data dir: {data_dir}")
    logger.info(f"   Pattern: {pattern}")
    logger.info(f"   Drop existing: {drop}")
    logger.info(f"   Incremental mode: {incremental}")
    logger.info("")
    
    start_time = time.time()
    success, skipped, failed = ingest_directory(
        collection_name=collection,
        data_dir=Path(data_dir),
        file_pattern=pattern,
        drop_existing=drop,
        incremental=incremental
    )
    elapsed = time.time() - start_time
    
    print(f"⏱️  Total time: {elapsed:.1f}s ({elapsed/60:.1f} minutes)")
    print()
    
    # Only fail if MOST files failed (>50%)
    total_attempted = success + failed
    if total_attempted > 0 and failed > success:
        logger.error(f"❌ Majority of files failed ({failed}/{total_attempted})")
        sys.exit(1)
    elif failed > 0:
        logger.warning(f"⚠️  {failed} files failed, but {success} succeeded")
        sys.exit(0)  # Success despite some failures
    else:
        logger.info(f"✅ All processed files successful!")
        sys.exit(0)


if __name__ == "__main__":
    main()

