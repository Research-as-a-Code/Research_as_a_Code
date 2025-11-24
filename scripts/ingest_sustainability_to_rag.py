#!/usr/bin/env python3
"""
Ingest Sustainability PDFs into NVIDIA RAG Blueprint Service
Uses the RAG service's /v1/ingest API to upload and process PDFs
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


class SustainabilityRAGIngestion:
    """Handles ingestion of sustainability PDFs into NVIDIA RAG Blueprint service"""
    
    def __init__(
        self,
        rag_ingest_url: str = "http://localhost:8081/v1",
        collection_name: str = "sustainability",
        data_dir: str = "/home/csaba/repos/AIML/Research_as_a_Code/data/sustainability"
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
    
    def ingest_pdf(self, pdf_path: Path) -> bool:
        """Ingest a single PDF file into the RAG service"""
        try:
            import json
            url = f"{self.rag_ingest_url}/documents"
            
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
                        "filename": pdf_path.name,
                        "source": pdf_path.name,
                        "document_type": "sustainability_research"
                    }
                ],
                "generate_summary": False
            }
            
            # Read PDF file
            with open(pdf_path, 'rb') as pdf_file:
                files = {
                    'file': (pdf_path.name, pdf_file, 'application/pdf'),
                    'metadata': (None, json.dumps(metadata), 'application/json')
                }
                
                response = requests.post(url, files=files, timeout=60)
            
            if response.status_code in [200, 201, 202]:
                logger.info(f"✅ Ingested: {pdf_path.name}")
                return True
            else:
                logger.error(f"❌ Failed to ingest {pdf_path.name}: {response.status_code}")
                logger.error(f"   Response: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error ingesting {pdf_path.name}: {e}")
            return False
    
    def ingest_all_pdfs(self, batch_size: int = 5) -> tuple[int, int]:
        """Ingest all PDFs from the sustainability directory"""
        pdf_files = sorted(self.data_dir.glob("*.pdf"))
        
        if not pdf_files:
            logger.error(f"❌ No .pdf files found in {self.data_dir}")
            return 0, 0
        
        logger.info(f"📚 Found {len(pdf_files)} sustainability PDFs to ingest")
        
        success_count = 0
        failed_count = 0
        
        for i, pdf_file in enumerate(pdf_files, 1):
            logger.info(f"📄 Processing {i}/{len(pdf_files)}: {pdf_file.name}")
            
            if self.ingest_pdf(pdf_file):
                success_count += 1
            else:
                failed_count += 1
            
            # Rate limiting - PDFs take longer to process
            if i % batch_size == 0:
                logger.info(f"⏸️ Processed {i} PDFs, pausing for 5 seconds...")
                time.sleep(5)
        
        return success_count, failed_count


def main():
    """Main ingestion workflow"""
    print("=" * 80)
    print("🌱 Sustainability PDFs → NVIDIA RAG Blueprint Ingestion")
    print("=" * 80)
    print()
    
    # Initialize ingestion service
    rag_ingest_url = os.getenv("RAG_INGEST_URL", "http://localhost:8082/v1")
    ingestion = SustainabilityRAGIngestion(
        rag_ingest_url=rag_ingest_url,
        collection_name="sustainability"
    )
    
    # Create collection
    print("\n📦 Creating collection...")
    if not ingestion.create_collection():
        logger.error("❌ Failed to create collection. Exiting.")
        sys.exit(1)
    
    # Ingest all PDFs
    print(f"\n📚 Starting ingestion from: {ingestion.data_dir}")
    print("   This will take a while (79 PDFs, ~324MB)...")
    print()
    
    start_time = time.time()
    success, failed = ingestion.ingest_all_pdfs(batch_size=5)
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
        print(f"⚠️  {failed} PDFs failed to ingest. Check logs above for details.")
        sys.exit(1)
    else:
        print("✅ All sustainability PDFs ingested successfully!")
        print()
        print("🔍 Test query:")
        print(f"   curl -X POST '{rag_ingest_url.replace('/v1', '')}/query' \\")
        print("     -H 'Content-Type: application/json' \\")
        print("     -d '{\"query\": \"sustainable development goals\", \"collection\": \"sustainability\"}'")


if __name__ == "__main__":
    main()

