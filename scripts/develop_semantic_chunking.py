#!/usr/bin/env python3
"""
Develop optimal semantic chunking - match simple chunking granularity with better semantics
Target: ~100-200 chunks per file, ~800-1200 chars each
"""

import sys
from pathlib import Path
from typing import List, Dict

from llama_index.core import Document
from llama_index.core.embeddings import BaseEmbedding
from llama_index.core.node_parser import (
    MarkdownElementNodeParser,
    MarkdownNodeParser,
    SentenceSplitter,
)
from docling.document_converter import DocumentConverter


class FastMockEmbedding(BaseEmbedding):
    """Fast mock - no API calls"""
    embed_dim: int = 1024
    
    def _get_query_embedding(self, query: str) -> List[float]:
        return [float(hash(query + str(i)) % 100) / 100 for i in range(self.embed_dim)]
    
    def _get_text_embedding(self, text: str) -> List[float]:
        return self._get_query_embedding(text)
    
    async def _aget_query_embedding(self, query: str) -> List[float]:
        return self._get_query_embedding(query)


def simple_chunk(text: str, chunk_size=1000, overlap=200) -> List[str]:
    """Reference: Simple chunking"""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()
        if len(chunk) > 50:
            chunks.append(chunk)
        start += (chunk_size - overlap)
    return chunks


def optimized_semantic_chunking(markdown: str, filename: str) -> List[Dict]:
    """
    OPTIMIZED: Match simple granularity with semantic awareness
    
    Strategy:
    1. Extract tables (keep intact)
    2. Split by headers (preserve structure)
    3. Use SentenceSplitter with simple params (1000/200)
    4. Result: Similar count to simple, but semantically aware
    """
    print(f"\n  🎯 OPTIMIZED Semantic Chunking")
    print("  " + "=" * 60)
    
    doc = Document(text=markdown, metadata={"source": filename})
    
    # Step 1: Extract tables
    element_parser = MarkdownElementNodeParser(llm=None, num_workers=1)
    base_nodes, table_objects = element_parser.get_nodes_and_objects([doc])
    print(f"  Step 1: {len(table_objects)} tables extracted")
    
    # Step 2: Split by headers (preserves structure)
    header_splitter = MarkdownNodeParser()
    header_sections = header_splitter.get_nodes_from_documents(base_nodes)
    print(f"  Step 2: {len(header_sections)} header sections")
    
    # Step 3: Use SentenceSplitter with SIMPLE params (1000/200)
    # This gives us similar granularity but respects sentence boundaries
    sentence_splitter = SentenceSplitter(
        chunk_size=1000,  # Match simple
        chunk_overlap=200,  # Match simple
        separator=" "  # Split on spaces/sentences
    )
    
    text_chunks = []
    for section in header_sections:
        # Always split to maintain granularity
        sub_chunks = sentence_splitter.get_nodes_from_documents([section])
        text_chunks.extend(sub_chunks)
    
    print(f"  Step 3: {len(text_chunks)} text chunks")
    
    # Combine
    chunks = []
    for table in table_objects:
        chunks.append({"text": table.get_content(), "type": "table"})
    for text_node in text_chunks:
        chunks.append({"text": text_node.get_content(), "type": "text"})
    
    print(f"  Final: {len(chunks)} chunks ({len(table_objects)} tables + {len(text_chunks)} text)")
    if chunks:
        avg_size = sum(len(c['text']) for c in chunks) / len(chunks)
        print(f"  Avg size: {avg_size:.0f} chars")
    
    return chunks


def compare_approaches(file_path: str):
    """Compare chunking approaches"""
    
    print("=" * 80)
    print(f"📄 File: {Path(file_path).name}")
    print("=" * 80)
    
    # Extract
    print("\n🔍 Docling Extraction...")
    converter = DocumentConverter()
    result = converter.convert(file_path)
    markdown = result.document.export_to_markdown()
    print(f"  ✅ {len(markdown):,} characters")
    
    # Simple baseline
    print("\n📊 BASELINE: Simple Chunking (1000 chars, 200 overlap)")
    print("-" * 80)
    simple_chunks = simple_chunk(markdown, 1000, 200)
    print(f"  Chunks: {len(simple_chunks)}")
    print(f"  Avg size: {sum(len(c) for c in simple_chunks) / len(simple_chunks):.0f} chars")
    
    # Optimized semantic
    print("\n🎯 OPTIMIZED: Semantic Chunking")
    print("-" * 80)
    semantic_chunks = optimized_semantic_chunking(markdown, Path(file_path).name)
    
    # Comparison
    print("\n" + "=" * 80)
    print("📊 COMPARISON")
    print("=" * 80)
    print(f"Simple:   {len(simple_chunks)} chunks, avg {sum(len(c) for c in simple_chunks) / len(simple_chunks):.0f} chars")
    print(f"Semantic: {len(semantic_chunks)} chunks, avg {sum(len(c['text']) for c in semantic_chunks) / len(semantic_chunks):.0f} chars" if semantic_chunks else "Semantic: FAILED")
    print(f"Ratio:    {len(semantic_chunks) / len(simple_chunks):.2f}x")
    print()
    
    if len(semantic_chunks) >= len(simple_chunks) * 0.8:  # Within 20%
        print("✅ GOOD: Semantic produces similar granularity!")
    elif len(semantic_chunks) >= len(simple_chunks) * 0.5:  # Within 50%
        print("⚠️  OK: Semantic produces fewer but larger chunks")
    else:
        print("❌ TOO FEW: Semantic needs more aggressive splitting")
    
    # Show samples
    if semantic_chunks:
        print("\n📄 Sample Semantic Chunks:")
        print("-" * 80)
        for i, chunk in enumerate(semantic_chunks[:3], 1):
            print(f"\n  Chunk {i} ({chunk['type']}, {len(chunk['text'])} chars):")
            print(f"    {chunk['text'][:150]}...")
    
    return semantic_chunks


def main():
    if len(sys.argv) < 2:
        print("Usage: python develop_semantic_chunking.py <pdf_file> [pdf_file2] ...")
        print("Example: python develop_semantic_chunking.py data/tariffs/Chapter_17.pdf data/tariffs/Chapter_18.pdf")
        sys.exit(1)
    
    for file_path in sys.argv[1:]:
        if not Path(file_path).exists():
            print(f"❌ Not found: {file_path}")
            continue
        
        compare_approaches(file_path)
        print("\n\n")


if __name__ == "__main__":
    main()
