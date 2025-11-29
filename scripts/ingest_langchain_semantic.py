#!/usr/bin/env python3
"""
LangChain-Based Semantic Ingestion with Docling + NVIDIA NIM

Pipeline:
1. Docling: Extract to Markdown (preserves structure)
2. LangChain MarkdownHeaderTextSplitter: Split by headers
3. LangChain RecursiveCharacterTextSplitter: Split sections (1000/200)
4. NVIDIA NIM: Generate embeddings with retry + fallback
5. Milvus: Index with size-aware bulk inserts

Features:
- Incremental ingestion (survives restarts)
- Retry logic (3 attempts, exponential backoff)
- Batch-splitting fallback (individual chunks)
- Failure persistence (to /data/ingestion_failures/)
- Size-aware bulk inserts (prevents gRPC crashes)
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

# LangChain imports
from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter
)

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


def extract_with_docling(file_path: str) -> str:
    """Extract document to Markdown using Docling"""
    try:
        from docling.document_converter import DocumentConverter
        logger.info(f"    🔍 Extracting with Docling...")
        converter = DocumentConverter()
        result = converter.convert(file_path)
        markdown_text = result.document.export_to_markdown()
        logger.info(f"    ✅ Extracted {len(markdown_text)} characters as Markdown")
        return markdown_text
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


def semantic_chunk_langchain(markdown_text: str, filename: str) -> List[Dict]:
    """
    Apply LangChain semantic chunking to markdown text
    
    Strategy:
    1. Split by markdown headers (H1, H2, H3)
    2. Split each section with RecursiveCharacterTextSplitter (1000/200)
    3. Result: Structure-aware chunks with good granularity
    
    Returns:
        List of chunk dicts with {text, metadata}
    """
    try:
        logger.info(f"    🧠 Applying LangChain semantic chunking...")
        
        # Step 1: Split by headers
        headers_to_split_on = [
            ("#", "Header 1"),
            ("##", "Header 2"),
            ("###", "Header 3"),
        ]
        
        header_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=headers_to_split_on,
            strip_headers=False  # Keep headers in chunks for context
        )
        
        header_sections = header_splitter.split_text(markdown_text)
        logger.info(f"    📋 Split into {len(header_sections)} header sections")
        
        # Step 2: Split each section with character splitter
        char_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
        
        final_chunks = []
        for section in header_sections:
            sub_chunks = char_splitter.split_text(section.page_content)
            # Preserve header metadata
            for chunk_text in sub_chunks:
                final_chunks.append({
                    "text": chunk_text,
                    "metadata": {
                        "source": filename,
                        **section.metadata  # Include header hierarchy
                    }
                })
        
        logger.info(f"    ✅ Created {len(final_chunks)} semantic chunks")
        logger.info(f"       Avg size: {sum(len(c['text']) for c in final_chunks) / len(final_chunks):.0f} chars")
        
        return final_chunks
        
    except Exception as e:
        logger.error(f"    ❌ Semantic chunking error: {e}")
        logger.info(f"    ⚠️  Falling back to simple chunking...")
        return simple_fallback_chunk(markdown_text, filename)


def simple_fallback_chunk(text: str, filename: str, chunk_size: int = 1000, overlap: int = 200) -> List[Dict]:
    """Fallback to simple character-based chunking"""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk_text = text[start:end].strip()
        if len(chunk_text) > 50:
            chunks.append({
                "text": chunk_text,
                "metadata": {"source": filename, "chunking": "simple_fallback"}
            })
        start += (chunk_size - overlap)
    
    logger.info(f"    ⚠️  Fallback: {len(chunks)} simple chunks")
    return chunks


def persist_failed_chunks(chunks: List[Dict], filename: str, error: str, collection_name: str):
    """Persist failed chunks to disk for later replay"""
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
            "chunks": chunks  # Full chunks with all info
        }
        
        with open(failure_file, 'w', encoding='utf-8') as f:
            json.dump(failure_record, f, indent=2, ensure_ascii=False)
        
        logger.info(f"    💾 Failed chunks persisted to: {failure_file.name}")
        logger.info(f"       {len(chunks)} chunks saved for later replay")
        
    except Exception as e:
        logger.error(f"    ⚠️  Could not persist failures: {e}")


def get_embeddings_batch(texts: List[str], nim_url: str, max_retries: int = 3) -> Tuple[List[List[float]], List[Tuple]]:
    """
    Get embeddings with 4-tier recovery:
    1. Batch with retry (3 attempts, exponential backoff)
    2. Individual chunk processing
    3. Returns: (embeddings, failed_indices)
    """
    # Tier 1: Try batch with retries
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
                return [item["embedding"] for item in result["data"]], []
            elif attempt < max_retries - 1:
                wait_time = 2 ** attempt
                logger.warning(f"    ⚠️  API error {response.status_code}, retry {attempt+1}/{max_retries} in {wait_time}s...")
                time.sleep(wait_time)
            else:
                logger.warning(f"    ⚠️  Batch failed after {max_retries} retries, trying individually...")
                break
                
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                logger.warning(f"    ⚠️  Error: {e}, retry {attempt+1}/{max_retries} in {wait_time}s...")
                time.sleep(wait_time)
            else:
                logger.warning(f"    ⚠️  Batch failed, trying individually...")
                break
    
    # Tier 2: Individual processing
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
    """Query Milvus for already-ingested files (with pagination)"""
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
    file_pattern: str = "*.pdf",
    drop_existing: bool = False
) -> Tuple[int, int, int]:
    """Main LangChain semantic ingestion pipeline"""
    
    print("🚀 LangChain Semantic Chunking Ingestion")
    print("=" * 80)
    print(f"Collection: {collection_name}")
    print(f"Data directory: {data_dir}")
    print(f"Method: MarkdownHeader + RecursiveCharacter (1000/200)")
    print(f"Expected: ~144 chunks per file (vs ~114 simple)")
    print()
    
    # Connect to Milvus
    logger.info(f"🔌 Connecting to Milvus at {MILVUS_HOST}:{MILVUS_PORT}")
    connections.connect(alias="default", host=MILVUS_HOST, port=MILVUS_PORT)
    logger.info("  ✅ Connected!")
    
    # Create/get collection
    collection = create_collection(collection_name, drop_existing)
    
    # Get already-ingested files
    already_ingested = set()
    if not drop_existing:
        already_ingested = get_already_ingested_files(collection_name)
    
    print()
    
    # Get files
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
    
    # Process files
    all_embeddings = []
    all_texts = []
    all_sources = []
    
    success_count = 0
    skipped_count = len(already_ingested)
    failed_count = 0
    
    for idx, file_path in enumerate(files, 1):
        filename = file_path.name
        logger.info(f"📄 [{idx}/{len(files)}] Processing: {filename}")
        
        # Extract to markdown
        if file_path.suffix.lower() in ['.pdf', '.docx', '.doc']:
            markdown_text = extract_with_docling(str(file_path))
        elif file_path.suffix.lower() == '.txt':
            markdown_text = fallback_txt_extraction(str(file_path))
        else:
            logger.warning(f"    ⚠️  Unsupported file type")
            failed_count += 1
            continue
        
        if not markdown_text or len(markdown_text) < 100:
            logger.warning(f"    ⚠️  Insufficient text extracted")
            failed_count += 1
            continue
        
        # Apply LangChain semantic chunking
        chunks = semantic_chunk_langchain(markdown_text, filename)
        
        if not chunks:
            failed_count += 1
            continue
        
        # Get embeddings for chunks in batches
        chunk_texts = [c["text"] for c in chunks]
        permanently_failed_chunks = []
        
        for i in range(0, len(chunk_texts), BATCH_SIZE):
            batch_texts = chunk_texts[i:i + BATCH_SIZE]
            embeddings, failed_indices = get_embeddings_batch(batch_texts, EMBEDDING_NIM_URL)
            
            # Track permanently failed chunks
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
        
        # Persist permanently failed chunks if any
        if permanently_failed_chunks:
            persist_failed_chunks(permanently_failed_chunks, filename, "Embedding failures", collection_name)
        
        success_count += 1
        
        # Bulk insert every 25 files OR 5000 chunks (gRPC limit protection)
        should_insert = (idx % 25 == 0) or (len(all_embeddings) >= 5000)
        
        if should_insert and all_embeddings:
            logger.info(f"\n💾 Bulk inserting {len(all_embeddings)} chunks...")
            try:
                collection.insert([all_embeddings, all_texts, all_sources])
                collection.flush()
                logger.info(f"  ✅ Inserted! Collection: {collection.num_entities} total chunks\n")
            except Exception as e:
                logger.error(f"  ❌ Bulk insert failed: {e}, splitting...")
                # Split into smaller batches
                for i in range(0, len(all_embeddings), 2500):
                    end = min(i + 2500, len(all_embeddings))
                    collection.insert([
                        all_embeddings[i:end],
                        all_texts[i:end],
                        all_sources[i:end]
                    ])
                    collection.flush()
                    logger.info(f"     ✅ Inserted chunks {i+1}-{end}")
            
            all_embeddings = []
            all_texts = []
            all_sources = []
    
    # Insert remaining
    if all_embeddings:
        logger.info(f"\n💾 Inserting final {len(all_embeddings)} chunks...")
        collection.insert([all_embeddings, all_texts, all_sources])
        collection.flush()
    
    logger.info("\n📊 Loading collection for search...")
    collection.load()
    
    total_entities = collection.num_entities
    print()
    print("=" * 80)
    print(f"✅ LANGCHAIN SEMANTIC INGESTION COMPLETE!")
    print("=" * 80)
    print(f"Collection: {collection_name}")
    print(f"Total chunks: {total_entities}")
    print(f"Files processed (new): {success_count}")
    print(f"Files skipped: {skipped_count}")
    print(f"Files failed: {failed_count}")
    print()
    
    return success_count, skipped_count, failed_count


def main():
    collection = os.getenv("COLLECTION_NAME", "us_tariffs")
    data_dir = os.getenv("DATA_DIR", "/data")
    pattern = os.getenv("FILE_PATTERN", "*.pdf")
    drop = os.getenv("DROP_EXISTING", "false").lower() == "true"
    
    logger.info(f"🎯 LangChain Semantic Configuration:")
    logger.info(f"   Collection: {collection}")
    logger.info(f"   Data dir: {data_dir}")
    logger.info(f"   Pattern: {pattern}")
    logger.info(f"   Drop existing: {drop}")
    logger.info(f"   Method: MarkdownHeader + RecursiveChar")
    logger.info("")
    
    start_time = time.time()
    success, skipped, failed = ingest_directory(
        collection_name=collection,
        data_dir=Path(data_dir),
        file_pattern=pattern,
        drop_existing=drop
    )
    elapsed = time.time() - start_time
    
    print(f"⏱️  Total time: {elapsed:.1f}s ({elapsed/60:.1f} minutes)")
    print()
    
    # Exit successfully unless majority failed
    total = success + failed
    if total > 0 and failed > success:
        logger.error(f"❌ Majority failed ({failed}/{total})")
        sys.exit(1)
    else:
        logger.info(f"✅ Ingestion successful!")
        sys.exit(0)


if __name__ == "__main__":
    main()

