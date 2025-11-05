#!/usr/bin/env python3
"""
Ingest US Customs Tariff PDFs into NVIDIA RAG Blueprint Service
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


class RAGServiceIngestion:
    """Handles ingestion of tariff PDFs into NVIDIA RAG Blueprint service"""
    
    def __init__(
        self,
        rag_ingest_url: str = "http://rag-server:8082/v1",
        collection_name: str = "us_tariffs",
        tariff_dir: str = "/home/csaba/repos/AIML/Research_as_a_Code/data/tariffs"
    ):
        self.rag_ingest_url = rag_ingest_url
        self.collection_name = collection_name
        self.tariff_dir = Path(tariff_dir)
        
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
            payload = {
                "collection_name": self.collection_name,
                "description": "US Harmonized Tariff Schedule - All 99 chapters"
            }
            
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
            url = f"{self.rag_ingest_url}/documents"
            
            # Open and send the PDF file
            with open(pdf_path, 'rb') as pdf_file:
                files = {
                    'file': (pdf_path.name, pdf_file, 'application/pdf')
                }
                data = {
                    'collection_name': self.collection_name
                }
                
                logger.info(f"📤 Uploading: {pdf_path.name}")
                response = requests.post(url, files=files, data=data, timeout=300)
                
                if response.status_code in [200, 201, 202]:
                    logger.info(f"   ✅ Successfully ingested: {pdf_path.name}")
                    return True
                else:
                    logger.error(f"   ❌ Failed to ingest {pdf_path.name}: {response.status_code}")
                    logger.error(f"      Response: {response.text}")
                    return False
                    
        except Exception as e:
            logger.error(f"   ❌ Error ingesting {pdf_path.name}: {e}")
            return False
    
    def ingest_all_pdfs(self) -> dict:
        """Ingest all tariff PDFs from the directory"""
        pdf_files = sorted(self.tariff_dir.glob("*.pdf"))
        
        if not pdf_files:
            logger.error(f"❌ No PDF files found in {self.tariff_dir}")
            return {"success": 0, "failed": 0, "total": 0}
        
        logger.info(f"📚 Found {len(pdf_files)} PDF files to ingest")
        logger.info(f"📁 Directory: {self.tariff_dir}")
        logger.info("")
        
        # Create collection first
        if not self.create_collection():
            logger.error("❌ Failed to create collection. Aborting.")
            return {"success": 0, "failed": 0, "total": len(pdf_files)}
        
        logger.info("")
        logger.info("🚀 Starting PDF ingestion...")
        logger.info("=" * 60)
        
        success_count = 0
        failed_count = 0
        
        for i, pdf_path in enumerate(pdf_files, 1):
            logger.info(f"[{i}/{len(pdf_files)}] Processing: {pdf_path.name}")
            
            if self.ingest_pdf(pdf_path):
                success_count += 1
            else:
                failed_count += 1
            
            # Small delay to avoid overwhelming the service
            if i < len(pdf_files):
                time.sleep(1)
        
        logger.info("")
        logger.info("=" * 60)
        logger.info("📊 Ingestion Summary:")
        logger.info(f"   ✅ Success: {success_count}")
        logger.info(f"   ❌ Failed:  {failed_count}")
        logger.info(f"   📦 Total:   {len(pdf_files)}")
        
        return {
            "success": success_count,
            "failed": failed_count,
            "total": len(pdf_files)
        }
    
    def test_query(self, query: str) -> dict:
        """Test querying the ingested collection"""
        try:
            # Use the RAG server query endpoint (not ingest)
            rag_server_url = self.rag_ingest_url.replace(":8082", ":8081")
            url = f"{rag_server_url}/generate"
            
            payload = {
                "messages": [{"role": "user", "content": query}],
                "use_knowledge_base": True,
                "enable_citations": True,
                "collection_name": self.collection_name
            }
            
            logger.info(f"🔍 Testing query: {query}")
            response = requests.post(url, json=payload, timeout=60)
            
            if response.status_code == 200:
                # Parse streaming response
                content = ""
                citations = []
                
                for line in response.text.splitlines():
                    if line.startswith("data: "):
                        import json
                        data = json.loads(line[6:])
                        if "choices" in data:
                            content += data["choices"][0]["message"]["content"]
                        if "citations" in data and "results" in data["citations"]:
                            citations.extend(data["citations"]["results"])
                
                logger.info("   ✅ Query successful!")
                logger.info(f"   📄 Response: {content[:200]}...")
                logger.info(f"   📚 Citations: {len(citations)} documents")
                
                return {"content": content, "citations": citations}
            else:
                logger.error(f"   ❌ Query failed: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"   ❌ Error querying: {e}")
            return None


def main():
    """Main ingestion script"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Ingest US tariff PDFs into NVIDIA RAG Blueprint service"
    )
    parser.add_argument(
        "--rag-ingest-url",
        default="http://localhost:8082/v1",
        help="RAG ingest service URL (default: http://localhost:8082/v1)"
    )
    parser.add_argument(
        "--collection-name",
        default="us_tariffs",
        help="Collection name (default: us_tariffs)"
    )
    parser.add_argument(
        "--tariff-dir",
        default="/home/csaba/repos/AIML/Research_as_a_Code/data/tariffs",
        help="Directory containing tariff PDFs"
    )
    parser.add_argument(
        "--test-query",
        action="store_true",
        help="Run test queries after ingestion"
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("📚 US Customs Tariff RAG Ingestion")
    print("   Using NVIDIA RAG Blueprint Service")
    print("=" * 60)
    print()
    
    # Initialize ingestion
    ingestion = RAGServiceIngestion(
        rag_ingest_url=args.rag_ingest_url,
        collection_name=args.collection_name,
        tariff_dir=args.tariff_dir
    )
    
    # Ingest all PDFs
    results = ingestion.ingest_all_pdfs()
    
    # Test queries if requested
    if args.test_query and results["success"] > 0:
        print()
        print("=" * 60)
        print("🧪 Running Test Queries")
        print("=" * 60)
        print()
        
        test_queries = [
            "What is the tariff for replacement batteries?",
            "What's the tariff of Reese's Pieces?",
            "Tariff for computer processors"
        ]
        
        for query in test_queries:
            ingestion.test_query(query)
            print()
            time.sleep(2)
    
    print()
    print("=" * 60)
    print("✅ Ingestion Complete!")
    print("=" * 60)
    print()
    print(f"Collection name: {args.collection_name}")
    print(f"Status: {results['success']}/{results['total']} files ingested")
    print()
    print("Next steps:")
    print("  1. Open the AI-Q Research Assistant UI")
    print("  2. Enter 'us_tariffs' in the RAG Collection field")
    print("  3. Ask tariff questions!")
    print()


if __name__ == "__main__":
    main()

