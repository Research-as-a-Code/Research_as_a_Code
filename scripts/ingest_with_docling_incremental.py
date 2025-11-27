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


def get_embeddings_batch(texts: List[str], nim_url: str, max_retries: int = 3) -> List[List[float]]:
    """
    Get embeddings from NIM for a batch of texts with retry logic and fallback to individual processing
    
    Args:
        texts: List of text chunks to embed
        nim_url: NIM service URL
        max_retries: Number of retry attempts for batch (default: 3)
    
    Returns:
        List of embedding vectors (may be partial if some individual chunks fail)
    """
    # Try batch processing with retries
    for attempt in range(max_retries):
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
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                    logger.warning(f"    ⚠️  Embedding API error {response.status_code}, retry {attempt+1}/{max_retries} in {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                else:
                    logger.warning(f"    ⚠️  Batch embedding failed after {max_retries} retries, trying individual chunks...")
                    # Fall through to individual processing
                    break
                
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                logger.warning(f"    ⚠️  Embedding error: {e}, retry {attempt+1}/{max_retries} in {wait_time}s...")
                time.sleep(wait_time)
                continue
            else:
                logger.warning(f"    ⚠️  Batch embedding failed after {max_retries} retries, trying individual chunks...")
                # Fall through to individual processing
                break
    
    # Fallback: Process each chunk individually
    logger.info(f"    🔧 Processing {len(texts)} chunks individually...")
    embeddings = []
    for idx, text in enumerate(texts, 1):
        try:
            response = httpx.post(
                f"{nim_url}/v1/embeddings",
                json={
                    "input": [text],  # Single chunk
                    "model": "snowflake/arctic-embed-l",
                    "input_type": "passage"
                },
                timeout=60.0
            )
            
            if response.status_code == 200:
                result = response.json()
                embeddings.append(result["data"][0]["embedding"])
                if idx % 5 == 0:  # Log every 5 chunks
                    logger.info(f"       ✅ Individual chunk {idx}/{len(texts)}")
            else:
                logger.error(f"       ❌ Chunk {idx} failed (status {response.status_code})")
                # Continue with other chunks, this one is lost
            
            time.sleep(0.05)  # Small delay to avoid overwhelming API
            
        except Exception as e:
            logger.error(f"       ❌ Chunk {idx} error: {e}")
            # Continue with other chunks
    
    logger.info(f"    ✅ Individual processing: {len(embeddings)}/{len(texts)} chunks succeeded")
    return embeddings


def get_already_ingested_files(collection_name: str, expected_chunk_counts: dict = None) -> Set[str]:
    """
    Query Milvus to find which files are COMPLETELY ingested (with pagination)
    
    Args:
        collection_name: Milvus collection name
        expected_chunk_counts: Optional dict of {filename: expected_chunk_count}
                              If provided, only skip files with matching counts
    
    Returns: Set of filenames that are fully ingested
    """
    try:
        if not utility.has_collection(collection_name):
            logger.info(f"  📦 Collection '{collection_name}' doesn't exist yet")
            return set()
        
        collection = Collection(collection_name)
        collection.load()
        
        # Query for all chunks to get filename → chunk count mapping
        logger.info(f"  🔍 Checking for already-ingested files...")
        
        file_chunk_counts = {}  # {filename: count}
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
                
                # Count chunks per file
                for item in query_result:
                    filename = item['source']
                    file_chunk_counts[filename] = file_chunk_counts.get(filename, 0) + 1
                
                logger.info(f"     Scanned {offset + len(query_result)} chunks, found {len(file_chunk_counts)} unique files so far...")
                
                if len(query_result) < page_size:
                    break
                
                offset += len(query_result)
            except Exception as e:
                logger.warning(f"     ⚠️  Error at offset {offset}: {e}")
                break
        
        # If we have expected counts, filter for complete files only
        if expected_chunk_counts:
            complete_files = set()
            incomplete_files = []
            for filename, actual_count in file_chunk_counts.items():
                expected = expected_chunk_counts.get(filename, 0)
                if expected > 0 and actual_count >= expected:
                    complete_files.add(filename)
                elif expected > 0:
                    incomplete_files.append(f"{filename} ({actual_count}/{expected})")
            
            logger.info(f"  ✅ Found {len(complete_files)} COMPLETE files")
            if incomplete_files:
                logger.info(f"  ⚠️  Found {len(incomplete_files)} INCOMPLETE files (will reprocess)")
                logger.info(f"     Examples: {incomplete_files[:3]}")
            
            return complete_files
        else:
            # No expected counts: use simple filename presence (may include partial files)
            logger.info(f"  ✅ Found {len(file_chunk_counts)} already-ingested files")
            logger.info(f"     ⚠️  WARNING: Not verifying completeness (no expected counts)")
            
            if file_chunk_counts:
                examples = list(file_chunk_counts.keys())[:5]
                logger.info(f"     Examples: {examples}")
            
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
        
        # Bulk insert every 25 files OR when buffer exceeds 5000 chunks
        # (Prevents gRPC message size limit: 64MB)
        should_insert = (idx % 25 == 0) or (len(all_embeddings) >= 5000)
        
        if should_insert and all_embeddings:
            logger.info(f"\n💾 Bulk inserting {len(all_embeddings)} chunks into Milvus...")
            try:
                collection.insert([all_embeddings, all_texts, all_sources])
                collection.flush()
                logger.info(f"  ✅ Inserted! Collection now has {collection.num_entities} total chunks\n")
            except Exception as e:
                logger.error(f"  ❌ Bulk insert failed: {e}")
                logger.info(f"  🔧 Trying smaller batches (2500 chunks at a time)...")
                
                # Split into smaller chunks if bulk insert fails
                chunk_batch_size = 2500
                for i in range(0, len(all_embeddings), chunk_batch_size):
                    end_idx = min(i + chunk_batch_size, len(all_embeddings))
                    try:
                        collection.insert([
                            all_embeddings[i:end_idx],
                            all_texts[i:end_idx],
                            all_sources[i:end_idx]
                        ])
                        collection.flush()
                        logger.info(f"     ✅ Inserted chunks {i+1}-{end_idx}")
                    except Exception as e2:
                        logger.error(f"     ❌ Failed to insert chunks {i+1}-{end_idx}: {e2}")
            
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

