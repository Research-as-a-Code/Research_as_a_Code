#!/usr/bin/env python3
"""
Tariff PDF Ingestion Script for Milvus

This script:
1. Reads PDF files from data/tariffs/
2. Extracts and chunks text
3. Gets embeddings from NIM
4. Stores in Milvus collection 'us_tariffs'
"""

import os
import sys
import json
import time
from pathlib import Path
from typing import List, Dict
import httpx
from pymilvus import connections, Collection, CollectionSchema, FieldSchema, DataType, utility

# Configuration
MILVUS_HOST = os.getenv("MILVUS_HOST", "milvus.rag-blueprint.svc.cluster.local")
MILVUS_PORT = os.getenv("MILVUS_PORT", "19530")
EMBEDDING_NIM_URL = os.getenv("EMBEDDING_NIM_URL", "http://embedding-service.nim.svc.cluster.local:8000")
COLLECTION_NAME = "us_tariffs"
EMBEDDING_DIM = 1024  # NV-Embed-v1 dimension
CHUNK_SIZE = 500  # Characters per chunk
CHUNK_OVERLAP = 100


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract text from PDF using PyPDF2."""
    try:
        import PyPDF2
        text = ""
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
        return text
    except Exception as e:
        print(f"  ⚠️  Error extracting from {pdf_path}: {e}")
        return ""


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """Split text into overlapping chunks."""
    chunks = []
    start = 0
    text_len = len(text)
    
    while start < text_len:
        end = start + chunk_size
        chunk = text[start:end]
        
        # Clean up chunk
        chunk = chunk.strip()
        if len(chunk) > 50:  # Only keep substantial chunks
            chunks.append(chunk)
        
        start += (chunk_size - overlap)
    
    return chunks


def get_embeddings(texts: List[str], nim_url: str) -> List[List[float]]:
    """Get embeddings from NIM for a batch of texts."""
    try:
        response = httpx.post(
            f"{nim_url}/v1/embeddings",
            json={
                "input": texts,
                "model": "nvidia/nv-embedqa-e5-v5",
                "input_type": "passage"
            },
            timeout=60.0
        )
        response.raise_for_status()
        result = response.json()
        return [item["embedding"] for item in result["data"]]
    except Exception as e:
        print(f"  ❌ Error getting embeddings: {e}")
        return []


def create_milvus_collection():
    """Create or recreate the Milvus collection."""
    print(f"🔧 Setting up Milvus collection: {COLLECTION_NAME}")
    
    # Drop existing collection if it exists
    if utility.has_collection(COLLECTION_NAME):
        print(f"  ⚠️  Collection exists, dropping...")
        utility.drop_collection(COLLECTION_NAME)
    
    # Define schema
    fields = [
        FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=EMBEDDING_DIM),
        FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
        FieldSchema(name="source", dtype=DataType.VARCHAR, max_length=512)
    ]
    
    schema = CollectionSchema(fields, description="US Tariff Code collection")
    collection = Collection(COLLECTION_NAME, schema)
    
    # Create index
    print("  📊 Creating vector index...")
    index_params = {
        "metric_type": "L2",
        "index_type": "IVF_FLAT",
        "params": {"nlist": 128}
    }
    collection.create_index("embedding", index_params)
    
    print(f"  ✅ Collection '{COLLECTION_NAME}' created!")
    return collection


def ingest_pdfs(pdf_dir: str):
    """Main ingestion pipeline."""
    print("🚀 Starting tariff PDF ingestion pipeline...\n")
    
    # Connect to Milvus
    print(f"🔌 Connecting to Milvus at {MILVUS_HOST}:{MILVUS_PORT}")
    connections.connect(alias="default", host=MILVUS_HOST, port=MILVUS_PORT)
    print("  ✅ Connected!\n")
    
    # Create collection
    collection = create_milvus_collection()
    print()
    
    # Get list of PDFs
    pdf_files = sorted(Path(pdf_dir).glob("*.pdf"))
    total_files = len(pdf_files)
    print(f"📚 Found {total_files} PDF files to process\n")
    
    if total_files == 0:
        print("❌ No PDF files found!")
        return
    
    # Process PDFs
    all_embeddings = []
    all_texts = []
    all_sources = []
    batch_size = 10  # Process in batches for embedding API
    
    for idx, pdf_path in enumerate(pdf_files, 1):
        filename = pdf_path.name
        print(f"[{idx}/{total_files}] Processing: {filename}")
        
        # Extract text
        text = extract_text_from_pdf(str(pdf_path))
        if not text or len(text) < 100:
            print(f"  ⚠️  Skipping (insufficient text)")
            continue
        
        # Chunk text
        chunks = chunk_text(text)
        print(f"  📄 Extracted {len(chunks)} chunks")
        
        if not chunks:
            continue
        
        # Get embeddings in batches
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            embeddings = get_embeddings(batch, EMBEDDING_NIM_URL)
            
            if len(embeddings) == len(batch):
                all_embeddings.extend(embeddings)
                all_texts.extend(batch)
                all_sources.extend([filename] * len(batch))
                print(f"  ✅ Embedded chunks {i+1}-{i+len(batch)}")
            else:
                print(f"  ⚠️  Embedding failed for batch {i}")
            
            time.sleep(0.1)  # Rate limiting
        
        # Insert into Milvus every 50 files to avoid memory issues
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
    
    # Load collection
    print("\n📊 Loading collection for querying...")
    collection.load()
    
    # Final stats
    total_entities = collection.num_entities
    print(f"\n" + "="*60)
    print(f"✅ INGESTION COMPLETE!")
    print(f"="*60)
    print(f"Collection: {COLLECTION_NAME}")
    print(f"Total documents: {len(all_sources)}")
    print(f"Total chunks: {total_entities}")
    print(f"Ready for queries!")
    print("="*60 + "\n")


if __name__ == "__main__":
    # Check for PyPDF2
    try:
        import PyPDF2
    except ImportError:
        print("❌ PyPDF2 not installed. Installing...")
        os.system("pip install PyPDF2")
        import PyPDF2
    
    # Run ingestion
    pdf_directory = "data/tariffs"
    if not os.path.exists(pdf_directory):
        print(f"❌ Directory not found: {pdf_directory}")
        sys.exit(1)
    
    try:
        ingest_pdfs(pdf_directory)
    except KeyboardInterrupt:
        print("\n\n⚠️  Ingestion interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error during ingestion: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

