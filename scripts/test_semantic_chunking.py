#!/usr/bin/env python3
"""
Local test script for semantic chunking - debug before cluster deployment

Tests semantic_chunk_markdown() function on 1-2 sample files with verbose logging
"""

import sys
from pathlib import Path
from typing import List, Dict

# Add verbose logging
import logging
logging.basicConfig(
    level=logging.DEBUG,  # DEBUG for maximum verbosity
    format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
)
logger = logging.getLogger(__name__)

# Import LlamaIndex
try:
    from llama_index.core import Document
    from llama_index.core.embeddings import BaseEmbedding
    from llama_index.core.node_parser import (
        MarkdownElementNodeParser,
        SemanticSplitterNodeParser,
    )
    logger.info("✅ LlamaIndex imports successful")
except ImportError as e:
    logger.error(f"❌ LlamaIndex import failed: {e}")
    logger.info("Install with: pip install llama-index-core")
    sys.exit(1)

# Import Docling
try:
    from docling.document_converter import DocumentConverter
    logger.info("✅ Docling import successful")
except ImportError as e:
    logger.error(f"❌ Docling import failed: {e}")
    sys.exit(1)


class MockEmbeddingModel(BaseEmbedding):
    """Mock embedding model for testing (doesn't call real API)"""
    
    embed_dim: int = 1024
    
    def _get_query_embedding(self, query: str) -> List[float]:
        return [0.1] * self.embed_dim
    
    def _get_text_embedding(self, text: str) -> List[float]:
        logger.debug(f"Mock embedding for text ({len(text)} chars)")
        return [0.1] * self.embed_dim
    
    async def _aget_query_embedding(self, query: str) -> List[float]:
        return self._get_query_embedding(query)


def extract_with_docling(file_path: str) -> str:
    """Extract document to Markdown using Docling"""
    try:
        logger.info(f"🔍 Extracting {file_path} with Docling...")
        converter = DocumentConverter()
        result = converter.convert(file_path)
        markdown_text = result.document.export_to_markdown()
        logger.info(f"✅ Extracted {len(markdown_text)} characters as Markdown")
        logger.debug(f"First 500 chars: {markdown_text[:500]}")
        return markdown_text
    except Exception as e:
        logger.error(f"❌ Docling extraction error: {e}", exc_info=True)
        return ""


def semantic_chunk_markdown_debug(markdown_text: str, filename: str, embed_model: BaseEmbedding) -> List[Dict]:
    """
    Debug version of semantic chunking with extensive logging
    """
    logger.info(f"🧠 Starting semantic chunking for {filename}")
    logger.info(f"   Input: {len(markdown_text)} characters")
    
    try:
        # Create LlamaIndex document
        logger.debug("Creating LlamaIndex Document...")
        doc = Document(text=markdown_text, metadata={"source": filename})
        logger.info(f"✅ Document created")
        
        # Step 1: Extract tables and elements
        logger.info(f"📊 Extracting tables and elements...")
        element_parser = MarkdownElementNodeParser(llm=None, num_workers=1)
        
        try:
            logger.debug("Calling get_nodes_and_objects...")
            base_nodes, table_objects = element_parser.get_nodes_and_objects([doc])
            logger.info(f"✅ Found {len(table_objects)} tables/elements")
            logger.info(f"✅ Got {len(base_nodes)} base text nodes")
            
            for i, table in enumerate(table_objects):
                logger.debug(f"   Table {i+1}: {len(table.get_content())} chars")
                
        except Exception as e:
            logger.error(f"❌ Table extraction failed: {e}", exc_info=True)
            logger.info("   Falling back to treating entire document as text...")
            base_nodes = [doc]
            table_objects = []
        
        # Step 2: Apply semantic splitting
        logger.info(f"🧠 Applying semantic chunking to {len(base_nodes)} text nodes...")
        
        try:
            logger.debug("Creating SemanticSplitterNodeParser...")
            semantic_splitter = SemanticSplitterNodeParser(
                buffer_size=2,  # Group 2 sentences before comparing
                breakpoint_percentile_threshold=75,  # Lower threshold = more splits (was 95)
                embed_model=embed_model
            )
            logger.info(f"   Semantic splitter config: buffer=2, threshold=75")
            logger.debug("Calling get_nodes_from_documents...")
            semantic_nodes = semantic_splitter.get_nodes_from_documents(base_nodes)
            logger.info(f"✅ Created {len(semantic_nodes)} semantic text chunks")
            
            for i, node in enumerate(semantic_nodes[:3]):  # Show first 3
                logger.debug(f"   Chunk {i+1}: {len(node.get_content())} chars - {node.get_content()[:100]}...")
                
        except Exception as e:
            logger.error(f"❌ Semantic splitting failed: {e}", exc_info=True)
            logger.info("   Falling back to simple chunking...")
            # Fallback
            semantic_nodes = base_nodes
        
        # Step 3: Combine into final chunks
        logger.info(f"📦 Combining results...")
        chunks = []
        
        # Add table chunks
        for table_node in table_objects:
            content = table_node.get_content()
            chunks.append({
                "text": content,
                "type": "table",
                "metadata": {"source": filename, "node_type": "table"}
            })
            logger.debug(f"   Added table chunk: {len(content)} chars")
        
        # Add semantic text chunks
        for text_node in semantic_nodes:
            content = text_node.get_content()
            chunks.append({
                "text": content,
                "type": "text",
                "metadata": {"source": filename, "node_type": "semantic_text"}
            })
            logger.debug(f"   Added text chunk: {len(content)} chars")
        
        logger.info(f"✅ Total chunks: {len(chunks)} ({len(table_objects)} tables + {len(semantic_nodes)} text)")
        return chunks
        
    except Exception as e:
        logger.error(f"❌ Semantic chunking COMPLETELY failed: {e}", exc_info=True)
        logger.info(f"   Returning EMPTY list")
        return []


def test_file(file_path: str):
    """Test semantic chunking on a single file"""
    print("=" * 80)
    print(f"Testing: {file_path}")
    print("=" * 80)
    print()
    
    # Step 1: Extract with Docling
    markdown_text = extract_with_docling(file_path)
    
    if not markdown_text:
        logger.error("❌ Extraction failed, skipping semantic test")
        return
    
    print()
    
    # Step 2: Apply semantic chunking
    mock_embed = MockEmbeddingModel()
    chunks = semantic_chunk_markdown_debug(markdown_text, Path(file_path).name, mock_embed)
    
    print()
    print("=" * 80)
    print(f"RESULTS:")
    print("=" * 80)
    print(f"Total chunks: {len(chunks)}")
    print(f"Tables: {sum(1 for c in chunks if c['type'] == 'table')}")
    print(f"Text: {sum(1 for c in chunks if c['type'] == 'text')}")
    print()
    
    if chunks:
        print("Sample chunks:")
        for i, chunk in enumerate(chunks[:3], 1):
            print(f"\n  Chunk {i} ({chunk['type']}):")
            print(f"    Length: {len(chunk['text'])} chars")
            print(f"    Preview: {chunk['text'][:200]}...")
    else:
        print("⚠️  NO CHUNKS PRODUCED!")
    
    print()


def main():
    if len(sys.argv) < 2:
        print("Usage: python test_semantic_chunking.py <pdf_file1> [pdf_file2] ...")
        print("Example: python test_semantic_chunking.py data/tariffs/Chapter_17.pdf")
        sys.exit(1)
    
    for file_path in sys.argv[1:]:
        test_file(file_path)
        print("\n")


if __name__ == "__main__":
    main()

