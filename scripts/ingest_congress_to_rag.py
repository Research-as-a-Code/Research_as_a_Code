#!/usr/bin/env python3
"""
Ingest Congress text documents into NVIDIA RAG Blueprint Service
Uses the RAG service's /v1/ingest API to upload and process text files
"""

import os
import sys
import time
import requests
from pathlib import Path
from typing import List
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class CongressRAGIngestion:
    """Handles ingestion of congress text files into NVIDIA RAG Blueprint service"""
    
    def __init__(
        self,
        rag_ingest_url: str = "http://localhost:8081/v1",
        collection_name: str = "congress",
        data_dir: str = "/home/csaba/repos/AIML/Research_as_a_Code/data/congress"
    ):
        # Normalize URL
        self.rag_ingest_url = rag_ingest_url.rstrip('/')
        if not self.rag_ingest_url.endswith('/v1'):
            self.rag_ingest_url = f"{self.rag_ingest_url}/v1"
        
        self.collection_name = collection_name
        self.data_dir = Path(data_dir)
        
        # Test connectivity
        self._test_connection()
    
    def _test_connection(self):
        """Test if the RAG ingest service is reachable"""
        try:
            health_url = self.rag_ingest_url.replace("/v1", "/health")
            response = requests.get(health_url, timeout=5)
            if response.status_code == 200:
                logger.info(f"✅ Connected to RAG ingest service at {self.rag_ingest_url}")
            else:
                logger.warning(f"⚠️ RAG service responded with status {response.status_code}")
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Cannot connect to RAG service: {e}")
            logger.error(f"   Make sure the RAG Blueprint is deployed and accessible")
            logger.error(f"   URL: {self.rag_ingest_url}")
            sys.exit(1)
    
    def create_collection(self) -> bool:
        """Create a new collection in the RAG service"""
        try:
            url = f"{self.rag_ingest_url}/collections"
            payload = [self.collection_name]
            
            response = requests.post(url, json=payload, timeout=30)
            
            if response.status_code in [200, 201]:
                logger.info(f"✅ Collection '{self.collection_name}' created successfully")
                return True
            elif response.status_code == 409:
                logger.info(f"📦 Collection '{self.collection_name}' already exists")
                return True
            else:
                logger.error(f"❌ Failed to create collection: {response.status_code}")
                logger.error(f"   Response: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error creating collection: {e}")
            return False
    
    def ingest_text_file(self, txt_path: Path) -> bool:
        """Ingest a single text file into the RAG service"""
        try:
            import json
            url = f"{self.rag_ingest_url}/documents"
            
            # Read text content
            with open(txt_path, 'r', encoding='utf-8', errors='ignore') as f:
                text_content = f.read()
            
            # Prepare metadata
            metadata = {
                "collection_name": self.collection_name,
                "blocking": False,
                "split_options": {
                    "chunk_size": 1024,
                    "chunk_overlap": 150
                },
                "custom_metadata": [
                    {
                        "filename": txt_path.name,
                        "source": f"Congress Document - {txt_path.name}",
                        "document_id": txt_path.stem
                    }
                ],
                "generate_summary": False
            }
            
            # Create multipart form data
            files = {
                'file': (txt_path.name, text_content, 'text/plain'),
                'metadata': (None, json.dumps(metadata), 'application/json')
            }
            
            response = requests.post(url, files=files, timeout=60)
            
            if response.status_code in [200, 201, 202]:
                logger.info(f"✅ Ingested: {txt_path.name}")
                return True
            else:
                logger.error(f"❌ Failed to ingest {txt_path.name}: {response.status_code}")
                logger.error(f"   Response: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error ingesting {txt_path.name}: {e}")
            return False
    
    def ingest_all_files(self, batch_size: int = 10) -> tuple[int, int]:
        """Ingest all text files from the congress directory"""
        txt_files = sorted(self.data_dir.glob("*.txt"))
        
        if not txt_files:
            logger.error(f"❌ No .txt files found in {self.data_dir}")
            return 0, 0
        
        logger.info(f"📚 Found {len(txt_files)} congress text files to ingest")
        
        success_count = 0
        failed_count = 0
        
        for i, txt_file in enumerate(txt_files, 1):
            logger.info(f"📄 Processing {i}/{len(txt_files)}: {txt_file.name}")
            
            if self.ingest_text_file(txt_file):
                success_count += 1
            else:
                failed_count += 1
            
            # Rate limiting
            if i % batch_size == 0:
                logger.info(f"⏸️ Processed {i} files, pausing for 2 seconds...")
                time.sleep(2)
        
        return success_count, failed_count


def main():
    """Main ingestion workflow"""
    print("=" * 80)
    print("🏛️ Congress Documents → NVIDIA RAG Blueprint Ingestion")
    print("=" * 80)
    print()
    
    # Initialize ingestion service
    rag_ingest_url = os.getenv("RAG_INGEST_URL", "http://localhost:8082/v1")
    ingestion = CongressRAGIngestion(
        rag_ingest_url=rag_ingest_url,
        collection_name="congress"
    )
    
    # Create collection
    print("\n📦 Creating collection...")
    if not ingestion.create_collection():
        logger.error("❌ Failed to create collection. Exiting.")
        sys.exit(1)
    
    # Ingest all files
    print(f"\n📚 Starting ingestion from: {ingestion.data_dir}")
    print("   This will take a while (4747 files)...")
    print()
    
    start_time = time.time()
    success, failed = ingestion.ingest_all_files(batch_size=10)
    elapsed = time.time() - start_time
    
    # Summary
    print()
    print("=" * 80)
    print("📊 Ingestion Summary")
    print("=" * 80)
    print(f"✅ Success: {success}")
    print(f"❌ Failed:  {failed}")
    print(f"📦 Total:   {success + failed}")
    print(f"⏱️  Time:    {elapsed:.1f}s ({elapsed/60:.1f} minutes)")
    print()
    
    if failed > 0:
        print(f"⚠️  {failed} files failed to ingest. Check logs above for details.")
        sys.exit(1)
    else:
        print("✅ All congress documents ingested successfully!")
        print()
        print("🔍 Test query:")
        print(f"   curl -X POST '{rag_ingest_url.replace('/v1', '')}/query' \\")
        print("     -H 'Content-Type: application/json' \\")
        print("     -d '{\"query\": \"voting rights legislation\", \"collection\": \"congress\"}'")


if __name__ == "__main__":
    main()

