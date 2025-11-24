#!/home/csaba/repos/AIML/Research_as_a_Code/venv/bin/python
"""
Ingest documents directly into Milvus using pymilvus (same as backend)
Uses the same approach as the AI-Q agent for consistency
"""

import os
import sys
import time
import asyncio
import aiohttp
from pathlib import Path
from typing import List
import logging
from pymilvus import connections, Collection, utility, CollectionSchema, FieldSchema, DataType

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class DirectMilvusIngestion:
    """Ingest documents directly into Milvus (same method as backend)"""
    
    def __init__(
        self,
        collection_name: str,
        milvus_host: str = "localhost",
        milvus_port: str = "19530",
        embedding_url: str = "http://localhost:8000"
    ):
        self.collection_name = collection_name
        self.milvus_host = milvus_host
        self.milvus_port = milvus_port
        self.embedding_url = embedding_url
        
        # Connect to Milvus
        connections.connect(alias="default", host=milvus_host, port=milvus_port)
        logger.info(f"✅ Connected to Milvus at {milvus_host}:{milvus_port}")
    
    def create_collection_if_needed(self):
        """Create collection with same schema as backend uses"""
        if utility.has_collection(self.collection_name):
            logger.info(f"📦 Collection '{self.collection_name}' already exists")
            return
        
        # Define schema (matching backend's RAG collection structure)
        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=1024),
            FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="source", dtype=DataType.VARCHAR, max_length=1024),
        ]
        
        schema = CollectionSchema(fields=fields, description=f"{self.collection_name} collection")
        collection = Collection(name=self.collection_name, schema=schema)
        
        # Create index
        index_params = {
            "metric_type": "L2",
            "index_type": "HNSW",
            "params": {"M": 16, "efConstruction": 200}
        }
        collection.create_index(field_name="embedding", index_params=index_params)
        
        logger.info(f"✅ Collection '{self.collection_name}' created with index")
    
    async def get_embedding(self, text: str) -> List[float]:
        """Get embedding from NIM service (same as backend)"""
        async with aiohttp.ClientSession() as session:
            payload = {
                "input": text,
                "model": "snowflake/arctic-embed-l",
                "input_type": "passage"
            }
            
            async with session.post(
                f"{self.embedding_url}/v1/embeddings",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                response.raise_for_status()
                result = await response.json()
                return result["data"][0]["embedding"]
    
    async def ingest_text(self, text: str, source: str) -> bool:
        """Ingest a single text chunk"""
        try:
            # Get embedding
            embedding = await self.get_embedding(text)
            
            # Insert into Milvus
            collection = Collection(self.collection_name)
            data = [
                [embedding],
                [text[:65535]],  # Truncate to max length
                [source]
            ]
            
            collection.insert(data)
            collection.flush()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error ingesting chunk from {source}: {e}")
            return False
    
    async def ingest_file(self, file_path: Path, chunk_size: int = 1024) -> bool:
        """Ingest a file with chunking"""
        try:
            # Read file
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Simple chunking (split by paragraphs or size)
            chunks = self._chunk_text(content, chunk_size)
            
            logger.info(f"  📝 Split into {len(chunks)} chunks")
            
            # Ingest each chunk
            success_count = 0
            for i, chunk in enumerate(chunks):
                if await self.ingest_text(chunk, file_path.name):
                    success_count += 1
                
                # Rate limit
                if (i + 1) % 10 == 0:
                    await asyncio.sleep(0.5)
            
            logger.info(f"  ✅ Ingested {success_count}/{len(chunks)} chunks from {file_path.name}")
            return success_count == len(chunks)
            
        except Exception as e:
            logger.error(f"❌ Error ingesting {file_path.name}: {e}")
            return False
    
    def _chunk_text(self, text: str, chunk_size: int) -> List[str]:
        """Simple text chunking"""
        chunks = []
        words = text.split()
        
        current_chunk = []
        current_size = 0
        
        for word in words:
            current_chunk.append(word)
            current_size += len(word) + 1
            
            if current_size >= chunk_size:
                chunks.append(' '.join(current_chunk))
                current_chunk = []
                current_size = 0
        
        if current_chunk:
            chunks.append(' '.join(current_chunk))
        
        return chunks


async def ingest_directory(
    collection_name: str,
    data_dir: Path,
    file_pattern: str = "*.txt",
    milvus_host: str = "localhost",
    embedding_url: str = "http://localhost:8000"
):
    """Ingest all files from a directory"""
    
    ingestion = DirectMilvusIngestion(
        collection_name=collection_name,
        milvus_host=milvus_host,
        embedding_url=embedding_url
    )
    
    # Create collection
    ingestion.create_collection_if_needed()
    
    # Get files
    files = sorted(data_dir.glob(file_pattern))
    logger.info(f"📚 Found {len(files)} files to ingest")
    
    success = 0
    failed = 0
    
    for i, file_path in enumerate(files, 1):
        logger.info(f"📄 Processing {i}/{len(files)}: {file_path.name}")
        
        if await ingestion.ingest_file(file_path):
            success += 1
        else:
            failed += 1
        
        # Batch pause
        if i % 50 == 0:
            logger.info(f"⏸️  Processed {i} files, pausing...")
            await asyncio.sleep(2)
    
    return success, failed


def main():
    """Main ingestion workflow"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Ingest documents into Milvus")
    parser.add_argument("collection", help="Collection name (e.g., congress, sustainability)")
    parser.add_argument("data_dir", help="Directory containing files")
    parser.add_argument("--pattern", default="*.txt", help="File pattern (default: *.txt)")
    parser.add_argument("--milvus-host", default="localhost", help="Milvus host")
    parser.add_argument("--embedding-url", default="http://localhost:8000", help="Embedding NIM URL")
    
    args = parser.parse_args()
    
    print("=" * 80)
    print(f"📥 Ingesting {args.collection} → Milvus")
    print("=" * 80)
    print()
    
    start_time = time.time()
    success, failed = asyncio.run(ingest_directory(
        collection_name=args.collection,
        data_dir=Path(args.data_dir),
        file_pattern=args.pattern,
        milvus_host=args.milvus_host,
        embedding_url=args.embedding_url
    ))
    elapsed = time.time() - start_time
    
    print()
    print("=" * 80)
    print("📊 Ingestion Summary")
    print("=" * 80)
    print(f"✅ Success: {success}")
    print(f"❌ Failed:  {failed}")
    print(f"⏱️  Time:    {elapsed:.1f}s ({elapsed/60:.1f} min)")
    print()
    
    if failed == 0:
        print(f"✅ All documents ingested into '{args.collection}' collection!")
    else:
        print(f"⚠️  {failed} files failed")
        sys.exit(1)


if __name__ == "__main__":
    main()

