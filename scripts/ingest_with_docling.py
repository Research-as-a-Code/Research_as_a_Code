#!/usr/bin/env python3
"""
Enhanced Document Ingestion using Docling (IBM Research)
Provides superior PDF extraction with better segmentation

Supports:
- PDFs with advanced layout understanding
- Text files
- DOCX files
- All collections: tariffs, congress, sustainability
"""

import os
import sys
import time
from pathlib import Path
from typing import List, Tuple
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
CHUNK_SIZE = 1000  # Tokens/chars per chunk (increased from 500 for research papers)
CHUNK_OVERLAP = 200  # Overlap for context preservation
BATCH_SIZE = 10  # Embeddings per API call


def extract_with_docling(file_path: str) -> str:
    """
    Extract text using Docling for superior PDF segmentation
    
    Docling advantages over PyPDF2:
    - Better layout understanding
    - Improved table extraction
    - Smart heading detection
    - Enhanced structure preservation
    """
    try:
        from docling.document_converter import DocumentConverter
        
        logger.info(f"    🔍 Extracting with Docling...")
        
        # Initialize Docling converter
        converter = DocumentConverter()
        
        # Convert document
        result = converter.convert(file_path)
        
        # Get markdown representation (preserves structure)
        text = result.document.export_to_markdown()
        
        logger.info(f"    ✅ Extracted {len(text)} characters")
        return text
        
    except ImportError:
        logger.error("❌ Docling not installed! Install with: pip install docling")
        sys.exit(1)
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
    """
    Split text into overlapping chunks
    
    Using character-based chunking:
    - Simple and reliable
    - Works for any document type
    - Preserves context with overlap
    """
    chunks = []
    start = 0
    text_len = len(text)
    
    while start < text_len:
        end = start + chunk_size
        chunk = text[start:end].strip()
        
        if len(chunk) > 50:  # Only keep substantial chunks
            chunks.append(chunk)
        
        start += (chunk_size - overlap)
    
    return chunks


def get_embeddings_batch(texts: List[str], nim_url: str) -> List[List[float]]:
    """
    Get embeddings from NIM for a batch of texts (10x faster than sequential!)
    
    Uses: snowflake/arctic-embed-l (text-only, 1024 dimensions)
    """
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
            logger.error(f"    ❌ Embedding API error: {response.status_code}")
            return []
            
    except Exception as e:
        logger.error(f"    ❌ Embedding error: {e}")
        return []


def create_collection(collection_name: str, drop_existing: bool = False):
    """Create or get Milvus collection"""
    
    if utility.has_collection(collection_name):
        if drop_existing:
            logger.warning(f"  ⚠️  Dropping existing collection '{collection_name}'...")
            utility.drop_collection(collection_name)
        else:
            logger.info(f"  📦 Using existing collection '{collection_name}'")
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
    
    # Create HNSW index for fast similarity search
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
    drop_existing: bool = False
) -> Tuple[int, int]:
    """
    Main ingestion pipeline using Docling
    
    Args:
        collection_name: Milvus collection name
        data_dir: Directory containing documents
        file_pattern: File glob pattern
        drop_existing: Whether to drop existing collection
        
    Returns:
        (success_count, failed_count)
    """
    
    print("🚀 Enhanced Document Ingestion with Docling")
    print("=" * 80)
    print(f"Collection: {collection_name}")
    print(f"Data directory: {data_dir}")
    print(f"File pattern: {file_pattern}")
    print(f"Chunk size: {CHUNK_SIZE} chars")
    print(f"Overlap: {CHUNK_OVERLAP} chars")
    print(f"Batch size: {BATCH_SIZE} chunks per embedding call")
    print()
    
    # Connect to Milvus
    logger.info(f"🔌 Connecting to Milvus at {MILVUS_HOST}:{MILVUS_PORT}")
    connections.connect(alias="default", host=MILVUS_HOST, port=MILVUS_PORT)
    logger.info("  ✅ Connected!")
    
    # Create/get collection
    collection = create_collection(collection_name, drop_existing)
    print()
    
    # Get files
    files = sorted(data_dir.glob(file_pattern))
    total_files = len(files)
    logger.info(f"📚 Found {total_files} files to process")
    
    if total_files == 0:
        logger.error(f"❌ No files matching '{file_pattern}' found in {data_dir}")
        return 0, 0
    
    print()
    
    # Accumulate for bulk insert
    all_embeddings = []
    all_texts = []
    all_sources = []
    
    success_count = 0
    failed_count = 0
    
    for idx, file_path in enumerate(files, 1):
        filename = file_path.name
        logger.info(f"📄 [{idx}/{total_files}] Processing: {filename}")
        
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
        
        # Get embeddings in batches (FAST!)
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
            
            time.sleep(0.1)  # Rate limiting
        
        success_count += 1
        
        # Bulk insert every 50 files (EFFICIENT!)
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
    print(f"Total chunks: {total_entities}")
    print(f"Files processed: {success_count}/{total_files}")
    print(f"Failed: {failed_count}")
    print(f"Average chunks per file: {total_entities/success_count:.1f}")
    print()
    
    return success_count, failed_count


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Ingest documents into Milvus using Docling for extraction"
    )
    parser.add_argument("collection", help="Collection name (e.g., us_tariffs, congress, sustainability)")
    parser.add_argument("data_dir", help="Directory containing documents")
    parser.add_argument("--pattern", default="*.pdf", help="File pattern (default: *.pdf)")
    parser.add_argument("--drop", action="store_true", help="Drop existing collection before ingesting")
    parser.add_argument("--chunk-size", type=int, default=CHUNK_SIZE, help=f"Chunk size (default: {CHUNK_SIZE})")
    parser.add_argument("--overlap", type=int, default=CHUNK_OVERLAP, help=f"Chunk overlap (default: {CHUNK_OVERLAP})")
    
    args = parser.parse_args()
    
    # Update globals if specified
    global CHUNK_SIZE, CHUNK_OVERLAP
    CHUNK_SIZE = args.chunk_size
    CHUNK_OVERLAP = args.overlap
    
    start_time = time.time()
    success, failed = ingest_directory(
        collection_name=args.collection,
        data_dir=Path(args.data_dir),
        file_pattern=args.pattern,
        drop_existing=args.drop
    )
    elapsed = time.time() - start_time
    
    print(f"⏱️  Total time: {elapsed:.1f}s ({elapsed/60:.1f} minutes)")
    print()
    
    if failed > 0:
        logger.warning(f"⚠️  {failed} files failed to process")
        sys.exit(1)
    else:
        logger.info(f"✅ All {success} files processed successfully!")


if __name__ == "__main__":
    main()

