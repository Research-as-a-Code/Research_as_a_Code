#!/usr/bin/env python3
"""
Semantic Chunking Ingestion using LlamaIndex + Docling + NVIDIA NIM

Pipeline:
1. Docling: Extract documents to Markdown (preserves structure)
2. LlamaIndex MarkdownElementNodeParser: Extract tables
3. LlamaIndex SemanticSplitterNodeParser: Semantic text chunking
4. NVIDIA NIM: Generate embeddings
5. Milvus: Index chunks

Key advantages:
- Semantic chunking keeps related content together
- Tables extracted and handled specially
- Better retrieval quality vs simple character splitting
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

# LlamaIndex imports
from llama_index.core import Document
from llama_index.core.embeddings import BaseEmbedding
from llama_index.core.node_parser import (
    MarkdownElementNodeParser,
    SemanticSplitterNodeParser,
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration
MILVUS_HOST = os.getenv("MILVUS_HOST", "milvus-standalone")
MILVUS_PORT = os.getenv("MILVUS_PORT", "19530")
EMBEDDING_NIM_URL = os.getenv("EMBEDDING_NIM_URL", "http://embedding-service.nim.svc.cluster.local:8000")
EMBEDDING_DIM = 1024
BATCH_SIZE = 10

# Failure persistence configuration
FAILURE_LOG_DIR = Path(os.getenv("FAILURE_LOG_DIR", "/data/ingestion_failures"))
FAILURE_LOG_DIR.mkdir(parents=True, exist_ok=True)


class NvidiaNIMEmbedding(BaseEmbedding):
    """
    Custom embedding wrapper for NVIDIA NIM API
    Required by SemanticSplitterNodeParser for semantic similarity calculations
    """
    
    # Pydantic model fields
    api_url: str = "http://embedding-service.nim.svc.cluster.local:8000"
    model_name: str = "snowflake/arctic-embed-l"
    
    def __init__(self, api_url: str = None, model: str = "snowflake/arctic-embed-l", **kwargs):
        if api_url:
            kwargs['api_url'] = api_url
        kwargs['model_name'] = model
        super().__init__(**kwargs)
    
    def _get_query_embedding(self, query: str) -> List[float]:
        """Get embedding for a query (same as text embedding for our use case)"""
        return self._get_text_embedding(query)
    
    def _get_text_embedding(self, text: str) -> List[float]:
        """Get embedding for a single text via NVIDIA NIM API"""
        try:
            response = httpx.post(
                f"{self.api_url}/v1/embeddings",
                json={
                    "input": [text],
                    "model": self.model_name,
                    "input_type": "passage"
                },
                timeout=60.0
            )
            
            if response.status_code == 200:
                result = response.json()
                return result["data"][0]["embedding"]
            else:
                logger.error(f"Embedding API error: {response.status_code}")
                return [0.0] * EMBEDDING_DIM  # Fallback zero vector
                
        except Exception as e:
            logger.error(f"Embedding error: {e}")
            return [0.0] * EMBEDDING_DIM
    
    def _get_text_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings for multiple texts (batched)"""
        return [self._get_text_embedding(text) for text in texts]
    
    async def _aget_query_embedding(self, query: str) -> List[float]:
        """Async version (not implemented, falls back to sync)"""
        return self._get_query_embedding(query)
    
    async def _aget_text_embedding(self, text: str) -> List[float]:
        """Async version (not implemented, falls back to sync)"""
        return self._get_text_embedding(text)


def extract_with_docling(file_path: str) -> str:
    """Extract document to Markdown using Docling"""
    try:
        from docling.document_converter import DocumentConverter
        logger.info(f"    🔍 Extracting with Docling...")
        converter = DocumentConverter()
        result = converter.convert(file_path)
        # Export to Markdown - preserves headers, tables, structure
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


def semantic_chunk_markdown(markdown_text: str, filename: str, embed_model: BaseEmbedding) -> List[Dict]:
    """
    Apply LlamaIndex semantic chunking to markdown text
    
    Returns:
        List of chunk dicts with {text, type, metadata}
    """
    try:
        # Create LlamaIndex document
        doc = Document(text=markdown_text, metadata={"source": filename})
        
        # Step 1: Extract tables and structured elements
        logger.info(f"    📊 Extracting tables and elements...")
        element_parser = MarkdownElementNodeParser(llm=None, num_workers=1)
        
        # This separates base text nodes from table objects
        base_nodes, table_objects = element_parser.get_nodes_and_objects([doc])
        
        logger.info(f"    📝 Found {len(table_objects)} tables/elements")
        
        # Step 2: Apply semantic splitting to text nodes
        logger.info(f"    🧠 Applying semantic chunking to text...")
        semantic_splitter = SemanticSplitterNodeParser(
            buffer_size=1,  # Number of sentences to group
            breakpoint_percentile_threshold=95,  # Similarity threshold for splits
            embed_model=embed_model
        )
        
        semantic_nodes = semantic_splitter.get_nodes_from_documents(base_nodes)
        logger.info(f"    ✅ Created {len(semantic_nodes)} semantic text chunks")
        
        # Step 3: Combine into final chunks
        chunks = []
        
        # Add table chunks
        for table_node in table_objects:
            chunks.append({
                "text": table_node.get_content(),
                "type": "table",
                "metadata": {"source": filename, "node_type": "table"}
            })
        
        # Add semantic text chunks
        for text_node in semantic_nodes:
            chunks.append({
                "text": text_node.get_content(),
                "type": "text",
                "metadata": {"source": filename, "node_type": "semantic_text"}
            })
        
        logger.info(f"    ✅ Total chunks: {len(chunks)} ({len(table_objects)} tables + {len(semantic_nodes)} text)")
        return chunks
        
    except Exception as e:
        logger.error(f"    ❌ Semantic chunking error: {e}")
        logger.info(f"    ⚠️  Falling back to simple chunking...")
        # Fallback to simple chunking
        return simple_fallback_chunk(markdown_text, filename)


def simple_fallback_chunk(text: str, filename: str, chunk_size: int = 1000, overlap: int = 200) -> List[Dict]:
    """Fallback to simple character-based chunking if semantic fails"""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk_text = text[start:end].strip()
        if len(chunk_text) > 50:
            chunks.append({
                "text": chunk_text,
                "type": "text",
                "metadata": {"source": filename, "node_type": "simple"}
            })
        start += (chunk_size - overlap)
    return chunks


def persist_failed_chunks(chunks: List[Dict], filename: str, error: str, collection_name: str):
    """
    Persist failed chunks to disk for later analysis and replay
    
    Saves to: /data/ingestion_failures/{collection}/{timestamp}_{filename}.json
    """
    try:
        # Create collection-specific failure directory
        failure_dir = FAILURE_LOG_DIR / collection_name
        failure_dir.mkdir(parents=True, exist_ok=True)
        
        # Create failure record
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        failure_file = failure_dir / f"{timestamp}_{filename}.json"
        
        failure_record = {
            "timestamp": datetime.now().isoformat(),
            "collection": collection_name,
            "source_file": filename,
            "error": str(error),
            "chunk_count": len(chunks),
            "chunks": [
                {
                    "text": chunk["text"][:500],  # Store first 500 chars for inspection
                    "full_text": chunk["text"],
                    "type": chunk.get("type", "unknown"),
                    "metadata": chunk.get("metadata", {})
                }
                for chunk in chunks
            ]
        }
        
        with open(failure_file, 'w', encoding='utf-8') as f:
            json.dump(failure_record, f, indent=2, ensure_ascii=False)
        
        logger.info(f"    💾 Failed chunks persisted to: {failure_file}")
        logger.info(f"       {len(chunks)} chunks saved for later analysis")
        
    except Exception as e:
        logger.error(f"    ⚠️  Could not persist failures: {e}")


def get_embeddings_batch(texts: List[str], nim_url: str, max_retries: int = 3) -> List[List[float]]:
    """
    Get embeddings with retry logic and batch-splitting fallback
    """
    # Try batch with retries
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
    
    # Fallback: Individual processing
    logger.info(f"    🔧 Processing {len(texts)} chunks individually...")
    embeddings = []
    failed_indices = []
    
    for idx, text in enumerate(texts, 1):
        try:
            response = httpx.post(
                f"{nim_url}/v1/embeddings",
                json={"input": [text], "model": "snowflake/arctic-embed-l", "input_type": "passage"},
                timeout=60.0
            )
            if response.status_code == 200:
                embeddings.append(response.json()["data"][0]["embedding"])
            else:
                logger.error(f"       ❌ Chunk {idx} failed (status {response.status_code})")
                failed_indices.append((idx, text, f"HTTP {response.status_code}"))
            time.sleep(0.05)
        except Exception as e:
            logger.error(f"       ❌ Chunk {idx} error: {e}")
            failed_indices.append((idx, text, str(e)))
    
    logger.info(f"    ✅ Individual: {len(embeddings)}/{len(texts)} succeeded")
    
    # Return both embeddings and failed chunk info for persistence
    return embeddings, failed_indices


def get_already_ingested_files(collection_name: str) -> Set[str]:
    """Query Milvus for already-ingested files"""
    try:
        if not utility.has_collection(collection_name):
            return set()
        
        collection = Collection(collection_name)
        collection.load()
        
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
    """Main semantic ingestion pipeline"""
    
    print("🚀 Semantic Chunking Ingestion (LlamaIndex + Docling)")
    print("=" * 80)
    print(f"Collection: {collection_name}")
    print(f"Data directory: {data_dir}")
    print(f"Method: Semantic splitting + table extraction")
    print()
    
    # Connect to Milvus
    logger.info(f"🔌 Connecting to Milvus at {MILVUS_HOST}:{MILVUS_PORT}")
    connections.connect(alias="default", host=MILVUS_HOST, port=MILVUS_PORT)
    logger.info("  ✅ Connected!")
    
    # Create/get collection
    collection = create_collection(collection_name, drop_existing)
    
    # Initialize NVIDIA NIM embedding model for LlamaIndex
    logger.info(f"🧠 Initializing NVIDIA NIM embedding model...")
    embed_model = NvidiaNIMEmbedding(api_url=EMBEDDING_NIM_URL)
    logger.info("  ✅ Embedding model ready")
    
    # Get already-ingested files
    already_ingested = set()
    if not drop_existing:
        logger.info(f"  🔍 Checking for already-ingested files...")
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
        
        # Apply semantic chunking
        chunks = semantic_chunk_markdown(markdown_text, filename, embed_model)
        
        if not chunks:
            failed_count += 1
            continue
        
        # Get embeddings for chunks in batches
        chunk_texts = [c["text"] for c in chunks]
        permanently_failed_chunks = []  # Track chunks that failed all attempts
        
        for i in range(0, len(chunk_texts), BATCH_SIZE):
            batch_texts = chunk_texts[i:i + BATCH_SIZE]
            result = get_embeddings_batch(batch_texts, EMBEDDING_NIM_URL)
            
            # Handle return value (may include failed_indices from individual fallback)
            if isinstance(result, tuple):
                embeddings, failed_indices = result
                # Track permanently failed chunks
                for fail_idx, fail_text, fail_error in failed_indices:
                    permanently_failed_chunks.append({
                        "text": fail_text,
                        "type": chunks[i + fail_idx - 1].get("type", "unknown"),
                        "metadata": chunks[i + fail_idx - 1].get("metadata", {}),
                        "error": fail_error,
                        "batch_index": i + fail_idx
                    })
            else:
                embeddings = result
            
            if len(embeddings) == len(batch_texts):
                all_embeddings.extend(embeddings)
                all_texts.extend(batch_texts)
                all_sources.extend([filename] * len(batch_texts))
                logger.info(f"    ✅ Embedded chunks {i+1}-{i+len(batch_texts)}")
            elif len(embeddings) > 0:
                # Partial success from individual processing
                all_embeddings.extend(embeddings)
                all_texts.extend(batch_texts[:len(embeddings)])
                all_sources.extend([filename] * len(embeddings))
                logger.info(f"    ⚠️  Partial: {len(embeddings)}/{len(batch_texts)} chunks embedded")
            else:
                logger.warning(f"    ❌ Complete failure for batch {i}")
            
            time.sleep(0.1)
        
        # Persist permanently failed chunks if any
        if permanently_failed_chunks:
            persist_failed_chunks(permanently_failed_chunks, filename, "Embedding failures", collection)
        
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
    print(f"✅ SEMANTIC INGESTION COMPLETE!")
    print("=" * 80)
    print(f"Collection: {collection_name}")
    print(f"Total chunks: {total_entities}")
    print(f"Files processed (new): {success_count}")
    print(f"Files skipped: {skipped_count}")
    print(f"Files failed: {failed_count}")
    print()
    
    return success_count, skipped_count, failed_count


def main():
    collection = os.getenv("COLLECTION_NAME", "sustainability")
    data_dir = os.getenv("DATA_DIR", "/data")
    pattern = os.getenv("FILE_PATTERN", "*.pdf")
    drop = os.getenv("DROP_EXISTING", "false").lower() == "true"
    
    logger.info(f"🎯 Semantic Chunking Configuration:")
    logger.info(f"   Collection: {collection}")
    logger.info(f"   Data dir: {data_dir}")
    logger.info(f"   Pattern: {pattern}")
    logger.info(f"   Drop existing: {drop}")
    logger.info(f"   Method: LlamaIndex Semantic Splitter")
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

