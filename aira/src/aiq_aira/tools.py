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

import aiohttp
import asyncio
import json
import os
from urllib.parse import urljoin
from aiq_aira.constants import ASYNC_TIMEOUT, RAG_API_KEY, TAVILY_INCLUDE_DOMAINS
from langgraph.types import StreamWriter
from aiq_aira.utils import get_domain
from langchain_community.tools import TavilySearchResults
from urllib.parse import urljoin
import logging
from typing import Union, List

# Local mode support
try:
    from local.milvus_helper import (
        is_milvus_lite_mode, 
        has_collection as milvus_has_collection,
        search_collection as milvus_search_collection,
    )
    LOCAL_MODE_AVAILABLE = True
except ImportError:
    LOCAL_MODE_AVAILABLE = False
    is_milvus_lite_mode = lambda: False

logger = logging.getLogger(__name__)

async def search_rag(
    session: aiohttp.ClientSession,
    url: str,  # Embedding NIM URL
    prompt: str,
    writer: StreamWriter,
    collection: Union[str, List[str]]
):
    """
    Direct Milvus + NIM search: Gets embeddings from NIM, queries Milvus, returns top results.
    
    Supports single or multiple collections:
    - Single: collection="us_tariffs"
    - Multiple: collection=["us_tariffs", "congress"]
    
    For multiple collections:
    - Searches each with same top_k (4 per collection)
    - Merges results by relevance score (L2 distance)
    - Returns top results across all collections
    """ 
    # Normalize to list for uniform processing
    collections = [collection] if isinstance(collection, str) else collection
    collections = [c for c in collections if c]  # Filter empty strings
    
    if not collections:
        return ("No RAG collection specified", "")
    
    writer({"rag_answer": f"\n Performing RAG search across {len(collections)} collection(s) \n"})
    logger.info(f"RAG SEARCH (Direct Milvus) - collections: {collections}")
    
    try:
        from pymilvus import connections, Collection, utility
        
        # Get embedding model (supports Ollama and NIM)
        embedding_model = os.getenv("EMBEDDING_MODEL", "snowflake/arctic-embed-l")
        
        # Get embedding from embedding service (works with both Ollama and NIM)
        embedding_payload = {
            "input": prompt,
            "model": embedding_model,
        }
        # Only add input_type for NIM (not Ollama)
        if not (LOCAL_MODE_AVAILABLE and is_milvus_lite_mode()):
            embedding_payload["input_type"] = "query"
        
        async with asyncio.timeout(ASYNC_TIMEOUT):
            async with session.post(f"{url}/v1/embeddings", json=embedding_payload) as embed_response:
                embed_response.raise_for_status()
                embed_result = await embed_response.json()
                query_embedding = embed_result["data"][0]["embedding"]
            
            all_hits = []  # List of (result_dict, collection_name) tuples
            
            # Use Milvus Lite helper if in local mode, otherwise use standard pymilvus
            if LOCAL_MODE_AVAILABLE and is_milvus_lite_mode():
                # Milvus Lite mode - use helper functions
                valid_collections = [c for c in collections if milvus_has_collection(c)]
                if not valid_collections:
                    logger.warning(f"None of the collections exist: {collections}")
                    return ("No RAG collections found", "")
                
                if len(valid_collections) < len(collections):
                    missing = set(collections) - set(valid_collections)
                    logger.warning(f"Collections not found: {missing}")
                
                for coll_name in valid_collections:
                    results = milvus_search_collection(
                        collection_name=coll_name,
                        query_embedding=query_embedding,
                        limit=4,
                        output_fields=["text", "source"]
                    )
                    
                    if results:
                        for result in results:
                            # Create a hit-like object for compatibility
                            hit_dict = {
                                "text": result.get("text", ""),
                                "source": result.get("source", "RAG Document"),
                                "distance": result.get("score", 0.0),
                            }
                            all_hits.append((hit_dict, coll_name))
                        logger.info(f"  Found {len(results)} results from {coll_name}")
            else:
                # Standard Milvus standalone mode
                milvus_host = os.getenv("MILVUS_HOST", "milvus.rag-blueprint.svc.cluster.local")
                milvus_port = os.getenv("MILVUS_PORT", "19530")
                connections.connect(alias="default", host=milvus_host, port=milvus_port)
                
                valid_collections = [c for c in collections if utility.has_collection(c)]
                if not valid_collections:
                    logger.warning(f"None of the collections exist: {collections}")
                    return ("No RAG collections found", "")
                
                if len(valid_collections) < len(collections):
                    missing = set(collections) - set(valid_collections)
                    logger.warning(f"Collections not found: {missing}")
                
                for coll_name in valid_collections:
                    coll = Collection(coll_name)
                    coll.load()
                    
                    search_params = {"metric_type": "L2", "params": {"nprobe": 10}}
                    results = coll.search(
                        data=[query_embedding],
                        anns_field="embedding",
                        param=search_params,
                        limit=4,  # Same per-collection limit
                        output_fields=["text", "source"]
                    )
                    
                    if results and len(results[0]) > 0:
                        for hit in results[0]:
                            # Convert to dict format for uniform handling
                            try:
                                text = hit.entity.text if hasattr(hit.entity, 'text') else hit.entity.get('text', '')
                                source = hit.entity.source if hasattr(hit.entity, 'source') else hit.entity.get('source', 'RAG Document')
                            except Exception:
                                text = str(getattr(hit.entity, 'text', ''))
                                source = str(getattr(hit.entity, 'source', 'RAG Document'))
                            
                            hit_dict = {
                                "text": text,
                                "source": source,
                                "distance": hit.distance,
                            }
                            all_hits.append((hit_dict, coll_name))
                        logger.info(f"  Found {len(results[0])} results from {coll_name}")
            
            if not all_hits:
                return ("No relevant documents found", "")
            
            # Sort all hits by relevance (L2 distance - lower is better)
            all_hits.sort(key=lambda x: x[0]["distance"])
            
            # Take top results across all collections (up to 4 × num_collections)
            max_results = min(len(all_hits), 4 * len(valid_collections))
            top_hits = all_hits[:max_results]
            
            logger.info(f"Merged {len(all_hits)} results from {len(valid_collections)} collection(s), returning top {len(top_hits)}")
            
            content_parts = []
            citations_parts = []
            
            # Group chunks by source for clearer presentation
            # Include collection name in grouping for multi-collection searches
            chunks_by_source = {}  # {(collection, source): [(chunk_num, text), ...]}
            
            for i, (hit_dict, coll_name) in enumerate(top_hits):
                # hit_dict is now a dict with "text", "source", "distance" keys
                text = hit_dict.get("text", "")
                source = hit_dict.get("source", f"Doc {i+1}")
                distance = hit_dict.get("distance", 0.0)
                
                # Log with collection context
                logger.info(f"  📄 RAG chunk [{i+1}] from {coll_name}/{source} (distance: {distance:.3f})")
                
                # Group by (collection, source) for multi-collection clarity
                key = (coll_name, source) if len(valid_collections) > 1 else (source,)
                if key not in chunks_by_source:
                    chunks_by_source[key] = []
                chunks_by_source[key].append((i+1, text))
                citations_parts.append(f"{coll_name}/{source}" if len(valid_collections) > 1 else source)
            
            # Format with source attribution
            content_parts = []
            chunk_mapping = []
            
            for key, chunks in chunks_by_source.items():
                # Format source name
                if len(key) == 2:  # Multi-collection: (collection, source)
                    source_label = f"{key[0]}/{key[1]}"
                else:  # Single collection: (source,)
                    source_label = key[0]
                
                content_parts.append(f"\nFrom {source_label}:")
                chunk_numbers = []
                for chunk_num, text in chunks:
                    content_parts.append(f"[{chunk_num}] {text}")
                    chunk_numbers.append(str(chunk_num))
                chunk_mapping.append(f"{source_label} (chunks {', '.join(chunk_numbers)})")

            
            content = "\n".join(content_parts)
            citations_str = "\n".join(chunk_mapping)  # Use the detailed mapping
            
            citations = f"""
---
QUERY: {prompt}
ANSWER: {content}
CITATIONS: {citations_str}
---
"""
            logger.info(f"RAG found {len(top_hits)} results across {len(valid_collections)} collection(s)")
            return (content, citations)
            
    except asyncio.TimeoutError:
        writer({"rag_answer": "Timeout in RAG search"})
        return ("Timeout fetching RAG", "")        
    except Exception as e:
        writer({"rag_answer": f"Error: {str(e)}"})
        logger.error(f"RAG error: {e}", exc_info=True)
        return (f"Error: {e}", "")



async def search_tavily(prompt: str, writer: StreamWriter):
    """
    Example of a fallback web search using Tavily Search Tool
    """
    logger.info("TAVILY SEARCH")
    writer({"web_answer": "\n Performing web search \n"})
    try: 
        all_results = []

        # explicitly query sets of domains
        if len(TAVILY_INCLUDE_DOMAINS) > 0:
            domain_chunks = [TAVILY_INCLUDE_DOMAINS[i:i+5] for i in range(0, len(TAVILY_INCLUDE_DOMAINS), 5)]
            for domain_chunk in domain_chunks:
                tool = TavilySearchResults(
                    max_results=2,  # optimization try more than one search result
                    search_depth="advanced",
                    include_answer=True,
                    include_raw_content=False,
                    include_images=False,
                    include_domains=domain_chunk,
                    # exclude_domains=[...], 
                )
                try:
                    async with asyncio.timeout(ASYNC_TIMEOUT):
                        chunk_results = await tool.ainvoke({"query": prompt})
                        all_results.extend(chunk_results)
                except asyncio.TimeoutError:
                    writer({"web_answer": f"""
    --------
    The Tavily request for {prompt} to domains {domain_chunk} timed out
    --------                                
                    """
                    })
        
        # query at least a few different domains        
        if len(TAVILY_INCLUDE_DOMAINS) == 0:
            seen_domains = []
            for i in range(2):
                tool = TavilySearchResults(
                    max_results=2,  # optimization try more than one search result
                    search_depth="advanced",
                    include_answer=True,
                    include_raw_content=False,
                    include_images=False,
                    exclude_domains=seen_domains, 
                    )
                try:
                    async with asyncio.timeout(ASYNC_TIMEOUT):
                        chunk_results = await tool.ainvoke({"query": prompt})
                        all_results.extend(chunk_results)
                        seen_domains.extend([get_domain(r["url"]) for r in chunk_results])
                except asyncio.TimeoutError:
                    writer({"web_answer": f"""
        --------
        The Tavily request for {prompt} to domains {domain_chunk} timed out
        --------                                
                    """
                    })
        
        return all_results
    
    except Exception as e:
        writer({"web_answer": f"""
--------
Error searching web for {prompt} using Tavily with {TAVILY_INCLUDE_DOMAINS}
--------                                
                """
                })
        logger.warning(f"TAVILY SEARCH FAILED {e}")
        return [{"url": "", "content": ""}]