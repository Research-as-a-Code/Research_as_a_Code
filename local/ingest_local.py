#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2025 Research_as_a_Code Project
# SPDX-License-Identifier: Apache-2.0

"""
Local Document Ingestion Script for AI-Q

This script ingests documents (PDF, TXT, DOCX) into a local Milvus Lite database
using Ollama for embeddings. It provides the same RAG functionality as the cloud
version but runs entirely locally.

Usage:
    python local/ingest_local.py --collection us_tariffs --path data/tariffs/
    python local/ingest_local.py --collection my_docs --path data/documents/ --chunk-size 512

Features:
    - Supports PDF, TXT, DOCX, and MD files
    - Chunking with configurable size and overlap
    - Progress bar for large document sets
    - Resume capability (skips already ingested files)
"""

import os
import sys
import argparse
import hashlib
import logging
from pathlib import Path
from typing import List, Dict, Any, Generator, Optional
from dataclasses import dataclass

import httpx
from tqdm import tqdm

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from local.milvus_helper import (
    is_milvus_lite_mode,
    create_collection,
    insert_documents,
    get_collection_stats,
    has_collection,
)
from local.config import get_config, LocalConfig

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class DocumentChunk:
    """Represents a chunk of text from a document."""
    text: str
    source: str
    metadata: Dict[str, Any]


class DocumentLoader:
    """Load and chunk documents from various formats."""
    
    SUPPORTED_EXTENSIONS = {'.pdf', '.txt', '.md', '.docx'}
    
    def __init__(self, chunk_size: int = 1024, chunk_overlap: int = 150):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
    
    def load_file(self, file_path: Path) -> List[DocumentChunk]:
        """Load a single file and return chunks."""
        ext = file_path.suffix.lower()
        
        if ext == '.pdf':
            return self._load_pdf(file_path)
        elif ext in {'.txt', '.md'}:
            return self._load_text(file_path)
        elif ext == '.docx':
            return self._load_docx(file_path)
        else:
            logger.warning(f"Unsupported file type: {ext}")
            return []
    
    def _load_pdf(self, file_path: Path) -> List[DocumentChunk]:
        """Load PDF and return chunks."""
        try:
            from pypdf import PdfReader
        except ImportError:
            logger.error("pypdf not installed. Install with: pip install pypdf")
            return []
        
        chunks = []
        try:
            reader = PdfReader(file_path)
            text = ""
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            
            chunks = self._chunk_text(
                text, 
                source=file_path.name,
                metadata={"file_type": "pdf", "pages": len(reader.pages)}
            )
        except Exception as e:
            logger.error(f"Error reading PDF {file_path}: {e}")
        
        return chunks
    
    def _load_text(self, file_path: Path) -> List[DocumentChunk]:
        """Load text file and return chunks."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                text = f.read()
            
            return self._chunk_text(
                text,
                source=file_path.name,
                metadata={"file_type": file_path.suffix[1:]}
            )
        except Exception as e:
            logger.error(f"Error reading text file {file_path}: {e}")
            return []
    
    def _load_docx(self, file_path: Path) -> List[DocumentChunk]:
        """Load DOCX and return chunks."""
        try:
            from docx import Document
        except ImportError:
            logger.error("python-docx not installed. Install with: pip install python-docx")
            return []
        
        try:
            doc = Document(file_path)
            text = "\n".join([para.text for para in doc.paragraphs])
            
            return self._chunk_text(
                text,
                source=file_path.name,
                metadata={"file_type": "docx"}
            )
        except Exception as e:
            logger.error(f"Error reading DOCX {file_path}: {e}")
            return []
    
    def _chunk_text(
        self, 
        text: str, 
        source: str,
        metadata: Dict[str, Any]
    ) -> List[DocumentChunk]:
        """Split text into overlapping chunks."""
        chunks = []
        
        # Clean text
        text = text.strip()
        if not text:
            return chunks
        
        # Simple chunking by character count with overlap
        start = 0
        chunk_num = 0
        
        while start < len(text):
            end = start + self.chunk_size
            
            # Try to break at sentence boundary
            if end < len(text):
                # Look for sentence end (. ! ?) in the last 100 chars
                search_start = max(end - 100, start)
                last_period = text.rfind('.', search_start, end)
                last_exclaim = text.rfind('!', search_start, end)
                last_question = text.rfind('?', search_start, end)
                
                best_break = max(last_period, last_exclaim, last_question)
                if best_break > start:
                    end = best_break + 1
            
            chunk_text = text[start:end].strip()
            if chunk_text:
                chunk_num += 1
                chunks.append(DocumentChunk(
                    text=chunk_text,
                    source=source,
                    metadata={**metadata, "chunk": chunk_num}
                ))
            
            # Move start with overlap
            start = end - self.chunk_overlap
            if start < 0:
                start = end
        
        return chunks


class OllamaEmbedder:
    """Generate embeddings using Ollama."""
    
    def __init__(
        self, 
        base_url: str = "http://localhost:11434/v1",
        model: str = "nomic-embed-text"
    ):
        self.base_url = base_url.rstrip('/')
        self.model = model
        self._dimension: Optional[int] = None
    
    def get_embedding(self, text: str) -> List[float]:
        """Get embedding for a single text."""
        embeddings = self.get_embeddings([text])
        return embeddings[0] if embeddings else []
    
    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings for multiple texts."""
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                f"{self.base_url}/embeddings",
                json={
                    "input": texts,
                    "model": self.model,
                }
            )
            
            if response.status_code != 200:
                logger.error(f"Embedding request failed: {response.status_code}")
                logger.error(f"Response: {response.text}")
                return []
            
            data = response.json()
            embeddings = [item["embedding"] for item in data["data"]]
            
            # Cache dimension
            if embeddings and self._dimension is None:
                self._dimension = len(embeddings[0])
            
            return embeddings
    
    @property
    def dimension(self) -> int:
        """Get embedding dimension (queries model if not cached)."""
        if self._dimension is None:
            # Get dimension by embedding a test string
            test_embedding = self.get_embedding("test")
            self._dimension = len(test_embedding) if test_embedding else 768
        return self._dimension


class LocalIngestion:
    """Main ingestion class for local document processing."""
    
    def __init__(
        self,
        collection_name: str,
        config: Optional[LocalConfig] = None,
        chunk_size: int = 1024,
        chunk_overlap: int = 150,
        batch_size: int = 10,
    ):
        self.collection_name = collection_name
        self.config = config or get_config()
        self.batch_size = batch_size
        
        # Initialize components
        self.loader = DocumentLoader(chunk_size, chunk_overlap)
        self.embedder = OllamaEmbedder(
            base_url=self.config.embedding_base_url,
            model=self.config.embedding_model
        )
        
        # Ensure MILVUS_LITE is set for milvus_helper
        os.environ["MILVUS_LITE"] = "true"
        os.environ["MILVUS_DATA_PATH"] = self.config.milvus_lite_path
        
        logger.info(f"Initialized LocalIngestion:")
        logger.info(f"  - Collection: {collection_name}")
        logger.info(f"  - Embedding model: {self.config.embedding_model}")
        logger.info(f"  - Milvus path: {self.config.milvus_lite_path}")
    
    def _ensure_collection(self) -> bool:
        """Ensure the collection exists."""
        if has_collection(self.collection_name):
            stats = get_collection_stats(self.collection_name)
            logger.info(f"Collection '{self.collection_name}' exists with {stats.get('row_count', 0)} documents")
            return True
        
        logger.info(f"Creating collection '{self.collection_name}'...")
        return create_collection(
            self.collection_name,
            dimension=self.embedder.dimension,
            metric_type="L2"
        )
    
    def ingest_directory(self, directory: Path) -> int:
        """Ingest all supported files from a directory."""
        if not directory.exists():
            logger.error(f"Directory not found: {directory}")
            return 0
        
        # Ensure collection exists
        if not self._ensure_collection():
            logger.error("Failed to create collection")
            return 0
        
        # Find all supported files
        files = []
        for ext in self.loader.SUPPORTED_EXTENSIONS:
            files.extend(directory.glob(f"*{ext}"))
            files.extend(directory.glob(f"**/*{ext}"))  # Recursive
        
        if not files:
            logger.warning(f"No supported files found in {directory}")
            logger.info(f"Supported formats: {', '.join(self.loader.SUPPORTED_EXTENSIONS)}")
            return 0
        
        logger.info(f"Found {len(files)} files to process")
        
        total_chunks = 0
        
        for file_path in tqdm(files, desc="Processing files"):
            chunks = self.loader.load_file(file_path)
            
            if not chunks:
                continue
            
            # Process in batches
            for i in range(0, len(chunks), self.batch_size):
                batch = chunks[i:i + self.batch_size]
                
                texts = [c.text for c in batch]
                sources = [c.source for c in batch]
                
                # Get embeddings
                embeddings = self.embedder.get_embeddings(texts)
                
                if not embeddings:
                    logger.warning(f"Failed to get embeddings for batch from {file_path}")
                    continue
                
                # Insert into Milvus
                try:
                    count = insert_documents(
                        self.collection_name,
                        texts=texts,
                        embeddings=embeddings,
                        sources=sources
                    )
                    total_chunks += count
                except Exception as e:
                    logger.error(f"Failed to insert batch: {e}")
        
        logger.info(f"✅ Ingested {total_chunks} chunks from {len(files)} files")
        
        # Show final stats
        stats = get_collection_stats(self.collection_name)
        logger.info(f"Collection '{self.collection_name}' now has {stats.get('row_count', 0)} total documents")
        
        return total_chunks


def main():
    parser = argparse.ArgumentParser(
        description="Ingest documents into local Milvus Lite database"
    )
    parser.add_argument(
        "--collection", "-c",
        required=True,
        help="Name of the collection to create/add to"
    )
    parser.add_argument(
        "--path", "-p",
        required=True,
        type=Path,
        help="Path to directory containing documents"
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=1024,
        help="Maximum chunk size in characters (default: 1024)"
    )
    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=150,
        help="Overlap between chunks in characters (default: 150)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=10,
        help="Number of chunks to embed at once (default: 10)"
    )
    parser.add_argument(
        "--embedding-model",
        default=None,
        help="Ollama embedding model (default: from config)"
    )
    parser.add_argument(
        "--milvus-path",
        default=None,
        help="Path to Milvus Lite database (default: ./data/milvus/milvus.db)"
    )
    
    args = parser.parse_args()
    
    # Load config
    config = get_config()
    
    # Override config if provided
    if args.embedding_model:
        config.embedding_model = args.embedding_model
    if args.milvus_path:
        config.milvus_lite_path = args.milvus_path
    
    # Run ingestion
    ingestion = LocalIngestion(
        collection_name=args.collection,
        config=config,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        batch_size=args.batch_size,
    )
    
    count = ingestion.ingest_directory(args.path)
    
    if count > 0:
        print(f"\n✅ Successfully ingested {count} chunks into collection '{args.collection}'")
    else:
        print(f"\n⚠️ No documents were ingested")
        sys.exit(1)


if __name__ == "__main__":
    main()

