# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Citation formatting utilities for research reports.

This module provides a single, reusable helper function for formatting
citations from various source formats (UDR, TTD-DR, web) into a 
consistent markdown format.
"""

from collections import defaultdict
from typing import List
from urllib.parse import urlparse


def format_citations_from_sources(
    sources: List[dict],
    fallback_collection: str = "default"
) -> str:
    """
    Format citations from source list into markdown string.
    
    Handles both UDR format (nested citations) and TTD-DR format (flat with collection at top level).
    
    Args:
        sources: List of source dicts with 'source'/'type', 'citations', 'collection', 'title', 'url' fields
        fallback_collection: Collection name to use if not specified in source
        
    Returns:
        Formatted citation string with each document showing its collection
    """
    rag_doc_counts: dict = defaultdict(int)
    web_sources: List[dict] = []
    
    for idx, src in enumerate(sources, 1):
        src_type = src.get('source', src.get('type', 'unknown'))
        
        if src_type == 'rag':
            inner_citations = src.get('citations', [])
            
            if inner_citations:
                # UDR format: nested citations with document details and collection
                for inner_src in inner_citations:
                    doc_name = inner_src.get('source', f'RAG Document {idx}')
                    doc_collection = inner_src.get('collection', fallback_collection)
                    doc_key = (doc_name, doc_collection)
                    rag_doc_counts[doc_key] += 1
            elif src.get('collection'):
                # TTD-DR format: flat source with collection and title at top level
                doc_name = src.get('title', f'RAG Document {idx}')
                doc_collection = src.get('collection')
                doc_key = (doc_name, doc_collection)
                rag_doc_counts[doc_key] += 1
            else:
                # Fallback if no inner citations and no collection
                rag_doc_counts[(f'RAG Document {idx}', fallback_collection)] += 1
                
        elif src_type == 'web':
            title = src.get('title', '').strip()
            url = src.get('url', 'N/A')
            
            if not title and url != 'N/A':
                try:
                    domain = urlparse(url).netloc
                    title = domain or f'Web Source {idx}'
                except:
                    title = f'Web Source {idx}'
            elif not title:
                title = f'Web Source {idx}'
            
            # Deduplicate by URL
            if not any(ws['url'] == url for ws in web_sources):
                web_sources.append({'title': title, 'url': url})
        else:
            # Unknown source type - treat as web
            web_sources.append({
                'title': src.get('title', f'Source {idx}'),
                'url': src.get('url', 'N/A')
            })
    
    # Format citations
    citations_formatted = []
    
    # Add RAG documents - keys are tuples: (doc_name, collection)
    for (doc_name, doc_collection), count in sorted(rag_doc_counts.items()):
        if count > 1:
            citations_formatted.append(f"- [{doc_name}] RAG Collection: {doc_collection} ({count} excerpts)")
        else:
            citations_formatted.append(f"- [{doc_name}] RAG Collection: {doc_collection}")
    
    # Add web sources
    for ws in web_sources:
        citations_formatted.append(f"- [{ws['title']}] {ws['url']}")
    
    return "\n".join(citations_formatted) if citations_formatted else "No sources available"

