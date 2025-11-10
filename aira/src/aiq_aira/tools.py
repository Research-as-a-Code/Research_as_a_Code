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
from urllib.parse import urljoin
from aiq_aira.constants import ASYNC_TIMEOUT, RAG_API_KEY, TAVILY_INCLUDE_DOMAINS
from langgraph.types import StreamWriter
from aiq_aira.utils import get_domain
from langchain_community.tools import TavilySearchResults
from urllib.parse import urljoin
import logging

logger = logging.getLogger(__name__)

async def search_rag(
    session: aiohttp.ClientSession,
    url: str,  # Embedding NIM URL
    prompt: str,
    writer: StreamWriter,
    collection: str
):
    """
    Direct Milvus + NIM search: Gets embeddings from NIM, queries Milvus, returns top results.
    """ 
    writer({"rag_answer": "\n Performing RAG search with Milvus \n"})
    logger.info(f"RAG SEARCH (Direct Milvus) - collection: {collection}")
    
    try:
        from pymilvus import connections, Collection, utility
        import os
        import json
        
        # Get Milvus connection info
        milvus_host = os.getenv("MILVUS_HOST", "milvus.rag-blueprint.svc.cluster.local")
        milvus_port = os.getenv("MILVUS_PORT", "19530")
        
        # Connect to Milvus
        connections.connect(alias="default", host=milvus_host, port=milvus_port)
        
        # Check if collection exists
        if not utility.has_collection(collection):
            logger.warning(f"Collection '{collection}' does not exist")
            return ("No RAG collection found", "")
        
        # Get embedding from NIM
        embedding_payload = {
            "input": prompt,
            "model": "nvidia/nv-embedqa-e5-v5",
            "input_type": "query"
        }
        
        async with asyncio.timeout(ASYNC_TIMEOUT):
            async with session.post(f"{url}/v1/embeddings", json=embedding_payload) as embed_response:
                embed_response.raise_for_status()
                embed_result = await embed_response.json()
                query_embedding = embed_result["data"][0]["embedding"]
            
            # Query Milvus
            coll = Collection(collection)
            coll.load()
            
            search_params = {"metric_type": "L2", "params": {"nprobe": 10}}
            results = coll.search(
                data=[query_embedding],
                anns_field="embedding",
                param=search_params,
                limit=4,
                output_fields=["text", "source"]
            )
            
            if not results or len(results[0]) == 0:
                return ("No relevant documents found", "")
            
            content_parts = []
            citations_parts = []
            
            for i, hit in enumerate(results[0]):
                text = hit.entity.get("text", "")
                source = hit.entity.get("source", f"Doc {i+1}")
                content_parts.append(f"[{i+1}] {text}")
                citations_parts.append(source)
            
            content = "\n\n".join(content_parts)
            citations_str = "\n".join(citations_parts)
            
            citations = f"""
---
QUERY: {prompt}
ANSWER: {content}
CITATIONS: {citations_str}
---
"""
            logger.info(f"RAG found {len(results[0])} results")
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