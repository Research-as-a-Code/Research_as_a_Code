# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Unit tests for the format_citations_from_sources helper function.

This tests the citation formatting logic that handles:
1. UDR format: nested citations with collection info
2. TTD-DR format: flat sources with collection at top level
3. Web sources with URL deduplication
4. Multi-collection support
"""

import pytest
from aiq_aira.citation_utils import format_citations_from_sources


# ========================================
# Test UDR Format (nested citations)
# ========================================

class TestUDRFormat:
    """Tests for UDR-style sources with nested citations array."""
    
    def test_single_rag_source_with_citations(self):
        """UDR returns nested citations with document info."""
        sources = [{
            "source": "rag",
            "citations": [
                {"source": "Chapter_17.pdf", "collection": "us_tariffs", "text": "sample text"}
            ]
        }]
        
        result = format_citations_from_sources(sources)
        
        assert "Chapter_17.pdf" in result
        assert "us_tariffs" in result
        assert "RAG Collection: us_tariffs" in result
    
    def test_multiple_citations_same_document(self):
        """Multiple citations from same document should show excerpt count."""
        sources = [{
            "source": "rag",
            "citations": [
                {"source": "Chapter_17.pdf", "collection": "us_tariffs", "text": "excerpt 1"},
                {"source": "Chapter_17.pdf", "collection": "us_tariffs", "text": "excerpt 2"},
                {"source": "Chapter_17.pdf", "collection": "us_tariffs", "text": "excerpt 3"}
            ]
        }]
        
        result = format_citations_from_sources(sources)
        
        assert "Chapter_17.pdf" in result
        assert "(3 excerpts)" in result
    
    def test_multiple_collections_distinct_documents(self):
        """Documents from different collections should each show their collection."""
        sources = [{
            "source": "rag",
            "citations": [
                {"source": "tariff_doc.pdf", "collection": "us_tariffs", "text": "tariff text"},
                {"source": "congress_bill.txt", "collection": "congress", "text": "bill text"},
                {"source": "eco_report.pdf", "collection": "sustainability", "text": "eco text"}
            ]
        }]
        
        result = format_citations_from_sources(sources)
        
        assert "tariff_doc.pdf" in result
        assert "RAG Collection: us_tariffs" in result
        assert "congress_bill.txt" in result
        assert "RAG Collection: congress" in result
        assert "eco_report.pdf" in result
        assert "RAG Collection: sustainability" in result
    
    def test_fallback_collection_used_when_missing(self):
        """When citation lacks collection, fallback should be used."""
        sources = [{
            "source": "rag",
            "citations": [
                {"source": "document.pdf", "text": "no collection specified"}
            ]
        }]
        
        result = format_citations_from_sources(sources, fallback_collection="default_coll")
        
        assert "document.pdf" in result
        assert "RAG Collection: default_coll" in result


# ========================================
# Test TTD-DR Format (flat with collection at top level)
# ========================================

class TestTTDDRFormat:
    """Tests for TTD-DR-style sources with collection at top level."""
    
    def test_flat_source_with_collection(self):
        """TTD-DR returns flat sources with collection and title at top level."""
        sources = [{
            "type": "rag",
            "collection": "us_tariffs",
            "title": "Chapter_99.pdf",
            "snippet": "tariff info"
        }]
        
        result = format_citations_from_sources(sources)
        
        assert "Chapter_99.pdf" in result
        assert "RAG Collection: us_tariffs" in result
    
    def test_multiple_flat_sources_different_collections(self):
        """Multiple TTD-DR sources from different collections."""
        sources = [
            {"type": "rag", "collection": "us_tariffs", "title": "tariff.pdf"},
            {"type": "rag", "collection": "congress", "title": "bill.txt"},
            {"type": "rag", "collection": "sustainability", "title": "report.pdf"}
        ]
        
        result = format_citations_from_sources(sources)
        
        # Each document should show its own collection
        lines = result.split('\n')
        assert len(lines) == 3
        
        assert any("tariff.pdf" in line and "us_tariffs" in line for line in lines)
        assert any("bill.txt" in line and "congress" in line for line in lines)
        assert any("report.pdf" in line and "sustainability" in line for line in lines)


# ========================================
# Test Web Sources
# ========================================

class TestWebSources:
    """Tests for web source formatting and deduplication."""
    
    def test_web_source_with_title_and_url(self):
        """Web sources should show title and URL."""
        sources = [{
            "source": "web",
            "title": "Example Article",
            "url": "https://example.com/article"
        }]
        
        result = format_citations_from_sources(sources)
        
        assert "Example Article" in result
        assert "https://example.com/article" in result
    
    def test_web_source_extracts_domain_when_no_title(self):
        """When title is missing, domain should be extracted from URL."""
        sources = [{
            "source": "web",
            "title": "",
            "url": "https://www.example.com/path/to/article"
        }]
        
        result = format_citations_from_sources(sources)
        
        assert "www.example.com" in result
        assert "https://www.example.com/path/to/article" in result
    
    def test_duplicate_web_urls_deduplicated(self):
        """Duplicate URLs should be deduplicated."""
        sources = [
            {"source": "web", "title": "Article 1", "url": "https://example.com/article"},
            {"source": "web", "title": "Article 2", "url": "https://example.com/article"},  # Same URL
            {"source": "web", "title": "Different", "url": "https://other.com/different"}
        ]
        
        result = format_citations_from_sources(sources)
        
        # Should only have 2 entries (one deduplicated)
        lines = [line for line in result.split('\n') if line.strip()]
        assert len(lines) == 2
        
        # Count occurrences of the duplicate URL
        assert result.count("https://example.com/article") == 1


# ========================================
# Test Mixed Sources (RAG + Web)
# ========================================

class TestMixedSources:
    """Tests for mixed RAG and web sources."""
    
    def test_mixed_rag_and_web_sources(self):
        """Both RAG and web sources should be formatted correctly."""
        sources = [
            {
                "source": "rag",
                "citations": [
                    {"source": "document.pdf", "collection": "us_tariffs", "text": "rag text"}
                ]
            },
            {
                "source": "web",
                "title": "Web Article",
                "url": "https://example.com/article"
            }
        ]
        
        result = format_citations_from_sources(sources)
        
        # RAG source
        assert "document.pdf" in result
        assert "RAG Collection: us_tariffs" in result
        
        # Web source
        assert "Web Article" in result
        assert "https://example.com/article" in result
    
    def test_realistic_udr_output(self):
        """Test with realistic UDR output structure."""
        sources = [
            {
                "source": "rag",
                "content": "Tariff information about e-bikes...",
                "citations": [
                    {"source": "Chapter_99.pdf", "collection": "us_tariffs", "text": "99.1234..."},
                    {"source": "Chapter_99.pdf", "collection": "us_tariffs", "text": "99.5678..."},
                    {"source": "109_hr_6111.txt", "collection": "congress", "text": "Bill text..."}
                ]
            },
            {
                "source": "web",
                "title": "E-bike Tariffs Guide",
                "url": "https://electricbikereport.com/tariffs",
                "content": "Web content..."
            },
            {
                "source": "web",
                "title": "Industry News",
                "url": "https://bicycleretailer.com/news",
                "content": "More content..."
            }
        ]
        
        result = format_citations_from_sources(sources, fallback_collection="default")
        
        lines = result.split('\n')
        
        # Should have 4 lines: 2 RAG docs + 2 web sources
        assert len(lines) == 4
        
        # Chapter_99.pdf should show (2 excerpts)
        assert any("Chapter_99.pdf" in line and "(2 excerpts)" in line for line in lines)
        
        # Each collection should be shown correctly
        assert any("us_tariffs" in line for line in lines)
        assert any("congress" in line for line in lines)


# ========================================
# Test Edge Cases
# ========================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""
    
    def test_empty_sources_list(self):
        """Empty sources should return 'No sources available'."""
        result = format_citations_from_sources([])
        assert result == "No sources available"
    
    def test_rag_source_without_citations_or_collection(self):
        """RAG source with no citations and no collection should use fallback."""
        sources = [{
            "source": "rag",
            "content": "Some content but no citations array"
        }]
        
        result = format_citations_from_sources(sources, fallback_collection="my_default")
        
        assert "RAG Document 1" in result
        assert "my_default" in result
    
    def test_unknown_source_type_treated_as_web(self):
        """Unknown source types should be treated as web sources."""
        sources = [{
            "source": "unknown_type",
            "title": "Unknown Source",
            "url": "https://unknown.com"
        }]
        
        result = format_citations_from_sources(sources)
        
        assert "Unknown Source" in result
        assert "https://unknown.com" in result
    
    def test_type_field_instead_of_source_field(self):
        """Should handle 'type' field as alternative to 'source' field."""
        sources = [{
            "type": "rag",  # Using 'type' instead of 'source'
            "collection": "test_coll",
            "title": "Test Doc"
        }]
        
        result = format_citations_from_sources(sources)
        
        assert "Test Doc" in result
        assert "test_coll" in result
    
    def test_web_source_with_na_url(self):
        """Web source with N/A URL should handle gracefully."""
        sources = [{
            "source": "web",
            "title": "No URL Source",
            "url": "N/A"
        }]
        
        result = format_citations_from_sources(sources)
        
        assert "No URL Source" in result
        assert "N/A" in result


# ========================================
# Test Output Format
# ========================================

class TestOutputFormat:
    """Tests for the exact output format."""
    
    def test_rag_format_with_single_excerpt(self):
        """RAG citation format: '- [doc_name] RAG Collection: collection_name'"""
        sources = [{
            "source": "rag",
            "citations": [{"source": "doc.pdf", "collection": "test"}]
        }]
        
        result = format_citations_from_sources(sources)
        
        assert result == "- [doc.pdf] RAG Collection: test"
    
    def test_rag_format_with_multiple_excerpts(self):
        """RAG citation format with count: '- [doc_name] RAG Collection: collection_name (N excerpts)'"""
        sources = [{
            "source": "rag",
            "citations": [
                {"source": "doc.pdf", "collection": "test", "text": "1"},
                {"source": "doc.pdf", "collection": "test", "text": "2"}
            ]
        }]
        
        result = format_citations_from_sources(sources)
        
        assert result == "- [doc.pdf] RAG Collection: test (2 excerpts)"
    
    def test_web_format(self):
        """Web citation format: '- [title] url'"""
        sources = [{
            "source": "web",
            "title": "My Article",
            "url": "https://example.com"
        }]
        
        result = format_citations_from_sources(sources)
        
        assert result == "- [My Article] https://example.com"
    
    def test_output_sorted_alphabetically(self):
        """RAG citations should be sorted alphabetically by (doc_name, collection)."""
        sources = [{
            "source": "rag",
            "citations": [
                {"source": "zebra.pdf", "collection": "a_coll", "text": "z"},
                {"source": "apple.pdf", "collection": "b_coll", "text": "a"},
                {"source": "middle.pdf", "collection": "a_coll", "text": "m"}
            ]
        }]
        
        result = format_citations_from_sources(sources)
        lines = result.split('\n')
        
        # Should be sorted: (apple.pdf, b_coll), (middle.pdf, a_coll), (zebra.pdf, a_coll)
        assert "apple.pdf" in lines[0]
        assert "middle.pdf" in lines[1]
        assert "zebra.pdf" in lines[2]

