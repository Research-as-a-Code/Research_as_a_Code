# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Iterative Search Engine component for TTD-DR.

Stage 2 of the TTD-DR pipeline: Generates questions and searches for answers
based on the evolving draft and research plan.
"""

import asyncio
import json
import logging
import httpx
from typing import Dict, Any, List, Optional, Literal

from pydantic import BaseModel, Field as PydanticField
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI as LangChainChatOpenAI

from ..models import ResearchPlan, DraftState, SearchQAPair
from ..prompts import QUESTION_GENERATION_PROMPT, ANSWER_SYNTHESIS_PROMPT

logger = logging.getLogger(__name__)


# ========================================
# Pydantic Schema for NVIDIA Guided JSON
# ========================================

class QuestionSchema(BaseModel):
    """Schema for a single research question."""
    question: str = PydanticField(description="The research question")
    purpose: str = PydanticField(description="Why this question is important")
    priority: Literal["high", "medium", "low"] = PydanticField(
        default="medium",
        description="Priority level of the question"
    )


class QuestionsOutputSchema(BaseModel):
    """Schema for question generation output."""
    questions: List[QuestionSchema] = PydanticField(
        default_factory=list,
        description="List of research questions"
    )
    gaps_identified: List[str] = PydanticField(
        default_factory=list,
        description="Gaps identified in the current draft"
    )


class IterativeSearchEngine:
    """
    Handles iterative search based on draft gaps and research plan.
    
    This component:
    1. Analyzes the current draft to identify information gaps
    2. Generates targeted search questions
    3. Searches multiple sources (RAG, web)
    4. Synthesizes answers from search results
    """
    
    def __init__(self, 
                 llm: BaseChatModel,
                 rag_url: str,
                 tavily_api_key: Optional[str] = None):
        """
        Initialize the search engine.
        
        Args:
            llm: Language model for question generation and synthesis
            rag_url: URL for RAG service
            tavily_api_key: Optional API key for web search
        """
        self.llm = llm
        self.rag_url = rag_url.rstrip('/')
        self.tavily_api_key = tavily_api_key
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # HTTP client for API calls
        self.client = httpx.AsyncClient(timeout=30.0)
        
        # Extract LLM config for guided_json
        self._base_url = getattr(llm, 'openai_api_base', None) or getattr(llm, 'base_url', None)
        if self._base_url and hasattr(self._base_url, '__str__'):
            self._base_url = str(self._base_url)
        self._model_name = getattr(llm, 'model_name', "nvidia/llama-3.1-nemotron-nano-8b-v1")
    
    def _create_guided_llm_for_questions(self) -> LangChainChatOpenAI:
        """Create LLM with NVIDIA guided_json for question generation."""
        json_schema = QuestionsOutputSchema.model_json_schema()
        
        return LangChainChatOpenAI(
            base_url=self._base_url,
            model=self._model_name,
            api_key="not-used",
            model_kwargs={
                "extra_body": {
                    "nvext": {"guided_json": json_schema}  # NVIDIA NIM v1.12.0 format
                }
            }
        )
    
    async def generate_questions(self,
                                draft: DraftState,
                                plan: ResearchPlan,
                                history: List[SearchQAPair],
                                iteration: int,
                                num_questions: int = 3) -> List[Dict[str, Any]]:
        """
        Generate search questions based on the current draft state.
        
        Args:
            draft: Current draft state
            plan: Research plan
            history: Previous Q&A pairs
            iteration: Current iteration number
            num_questions: Number of questions to generate
            
        Returns:
            List of question dictionaries with question, purpose, and priority
        """
        self.logger.info(f"Generating {num_questions} questions for iteration {iteration}")
        
        # Get previously asked questions to avoid repetition
        previous_questions = [qa.question for qa in history[-10:]] if history else []
        
        # Prepare prompt
        prompt = QUESTION_GENERATION_PROMPT.format(
            draft=draft.content[:3000],  # Limit draft length for context window
            plan=json.dumps(plan.to_dict(), indent=2),
            previous_questions=json.dumps(previous_questions),
            iteration=iteration,
            num_questions=num_questions
        )
        
        try:
            # Use guided_json for guaranteed structured output
            guided_llm = self._create_guided_llm_for_questions()
            
            response = await guided_llm.ainvoke([
                SystemMessage(content="""You are an expert at identifying research gaps and generating targeted questions.
                Focus on information that will most improve the draft quality."""),
                HumanMessage(content=prompt)
            ])
            
            # Parse with Pydantic (guaranteed valid from guided_json)
            result = QuestionsOutputSchema.model_validate_json(response.content)
            
            # Update draft with identified gaps
            if result.gaps_identified:
                draft.gaps_identified = result.gaps_identified
            
            questions = [q.model_dump() for q in result.questions]
            
            # Ensure we have the requested number of questions
            while len(questions) < num_questions:
                questions.append({
                    "question": f"Additional information about {plan.main_topic}",
                    "purpose": "general expansion",
                    "priority": "medium"
                })
            
            self.logger.info(f"Generated {len(questions)} questions with priorities: " +
                           str([q.get('priority', 'medium') for q in questions]))
            
            return questions[:num_questions]
            
        except Exception as e:
            self.logger.error(f"Failed to generate questions: {e}")
            # Return fallback questions
            return self._generate_fallback_questions(plan, num_questions)
    
    async def search_multiple(self,
                            questions: List[str],
                            collection: str = "default",
                            use_web: bool = True) -> List[Dict[str, Any]]:
        """
        Search for answers to multiple questions.
        
        Args:
            questions: List of questions to search for
            collection: RAG collection to search
            use_web: Whether to include web search
            
        Returns:
            List of answer dictionaries with answer text and sources
        """
        self.logger.info(f"Searching for answers to {len(questions)} questions")
        
        # Process questions in parallel
        tasks = []
        for question in questions:
            tasks.append(self._search_single_question(question, collection, use_web))
        
        answers = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        processed_answers = []
        for i, answer in enumerate(answers):
            if isinstance(answer, Exception):
                self.logger.error(f"Search failed for question {i}: {answer}")
                processed_answers.append({
                    "question": questions[i],
                    "answer": f"Search failed: {str(answer)}",
                    "sources": [],
                    "confidence": 0.3
                })
            else:
                processed_answers.append(answer)
        
        return processed_answers
    
    async def _search_single_question(self,
                                     question: str,
                                     collection: str,
                                     use_web: bool) -> Dict[str, Any]:
        """
        Search for answer to a single question.
        
        Args:
            question: Question to search for
            collection: RAG collection
            use_web: Whether to use web search
            
        Returns:
            Answer dictionary
        """
        sources = []
        search_results = []
        
        # Search RAG
        try:
            rag_results = await self._search_rag(question, collection)
            if rag_results:
                search_results.extend(rag_results)
                sources.extend([{
                    "type": "rag",
                    "collection": collection,
                    "title": r.get("title", "RAG Document"),
                    "url": r.get("url", ""),
                    "snippet": r.get("snippet", "")[:200]
                } for r in rag_results[:3]])
        except Exception as e:
            self.logger.warning(f"RAG search failed: {e}")
        
        # Search web if enabled
        if use_web and self.tavily_api_key:
            try:
                web_results = await self._search_web(question)
                if web_results:
                    search_results.extend(web_results)
                    sources.extend([{
                        "type": "web",
                        "title": r.get("title", "Web Result"),
                        "url": r.get("url", ""),
                        "snippet": r.get("snippet", "")[:200]
                    } for r in web_results[:2]])
            except Exception as e:
                self.logger.warning(f"Web search failed: {e}")
        
        # Synthesize answer from results
        import sys
        print(f"🔸 TTD-DR SEARCH: Synthesizing answer from {len(search_results)} results", flush=True, file=sys.stderr)
        if search_results:
            answer = await self._synthesize_answer(question, search_results)
            print(f"🔸 TTD-DR SEARCH: Answer synthesized, len={len(answer) if answer else 0}", flush=True, file=sys.stderr)
            confidence = 0.8 if len(sources) > 2 else 0.6
        else:
            answer = "No relevant information found for this question."
            confidence = 0.2
        
        return {
            "question": question,
            "answer": answer,
            "sources": sources,
            "confidence": confidence
        }
    
    async def _search_rag(self, query: str, collection: str) -> List[Dict[str, Any]]:
        """
        Search the RAG system using direct Milvus connection.
        
        Args:
            query: Search query
            collection: Collection to search
            
        Returns:
            List of search results
        """
        import sys
        print(f"🔸 TTD-DR SEARCH: _search_rag called, query={query[:50]}..., collection={collection}", flush=True, file=sys.stderr)
        
        # Log tool call for UI visibility
        self.logger.info(f"🔍 [TTD-DR] Tool Call: search_rag(collection='{collection}')")
        
        try:
            import os
            import asyncio
            from pymilvus import connections, Collection, utility
            
            # Connect to Milvus
            milvus_host = os.getenv("MILVUS_HOST", "milvus-standalone.rag-blueprint.svc.cluster.local")
            milvus_port = int(os.getenv("MILVUS_PORT", "19530"))
            
            # Run Milvus operations in thread pool (pymilvus is sync)
            def _sync_search():
                print(f"🔸 TTD-DR SEARCH: Connecting to Milvus at {milvus_host}:{milvus_port}", flush=True, file=sys.stderr)
                connections.connect(alias="default", host=milvus_host, port=milvus_port)
                
                # Check if collection exists
                print(f"🔸 TTD-DR SEARCH: Checking collection '{collection}' exists", flush=True, file=sys.stderr)
                if not utility.has_collection(collection):
                    self.logger.warning(f"Collection '{collection}' does not exist")
                    print(f"🔸 TTD-DR SEARCH: Collection not found!", flush=True, file=sys.stderr)
                    return []
                
                print(f"🔸 TTD-DR SEARCH: Loading collection", flush=True, file=sys.stderr)
                coll = Collection(collection)
                coll.load()
                
                # Get embedding for query using embedding NIM
                print(f"🔸 TTD-DR SEARCH: Getting embedding...", flush=True, file=sys.stderr)
                embedding = self._get_embedding_sync(query)
                print(f"🔸 TTD-DR SEARCH: Got embedding, len={len(embedding) if embedding else 0}", flush=True, file=sys.stderr)
                if not embedding:
                    self.logger.warning("Failed to get embedding for query")
                    return []
                
                # Search Milvus
                print(f"🔸 TTD-DR SEARCH: Executing Milvus search...", flush=True, file=sys.stderr)
                search_params = {"metric_type": "L2", "params": {"nprobe": 10}}
                results = coll.search(
                    data=[embedding],
                    anns_field="embedding",  # Match UDR field name
                    param=search_params,
                    limit=5,
                    output_fields=["text", "source"]
                )
                print(f"🔸 TTD-DR SEARCH: Milvus search done, got {len(results)} result sets", flush=True, file=sys.stderr)
                
                # Format results (match UDR's approach)
                formatted = []
                for hits in results:
                    print(f"🔸 TTD-DR SEARCH: Processing {len(hits)} hits", flush=True, file=sys.stderr)
                    for hit in hits:
                        try:
                            text = hit.entity.text if hasattr(hit.entity, 'text') else hit.entity.get('text')
                            source = hit.entity.source if hasattr(hit.entity, 'source') else hit.entity.get('source')
                        except Exception:
                            text = str(getattr(hit.entity, 'text', ''))
                            source = str(getattr(hit.entity, 'source', 'RAG Document'))
                        
                        formatted.append({
                            "title": source or "RAG Document",
                            "snippet": text or "",
                            "content": text or "",
                            "score": hit.score,
                            "url": ""
                        })
                
                print(f"🔸 TTD-DR SEARCH: Returning {len(formatted)} formatted results", flush=True, file=sys.stderr)
                return formatted
            
            return await asyncio.to_thread(_sync_search)
                
        except Exception as e:
            self.logger.error(f"RAG search error: {e}")
            return []
    
    def _get_embedding_sync(self, text: str) -> List[float]:
        """Get embedding from embedding NIM (synchronous for thread pool)."""
        import httpx
        import os
        
        embedding_url = os.getenv("EMBEDDING_NIM_URL", "http://embedding-service.nim.svc.cluster.local:8000")
        
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    f"{embedding_url}/v1/embeddings",
                    json={
                        "input": [text],
                        "model": "snowflake/arctic-embed-l",
                        "input_type": "query"  # Required by arctic-embed-l
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return data["data"][0]["embedding"]
                else:
                    self.logger.error(f"Embedding request failed: {response.status_code}")
                    return []
        except Exception as e:
            self.logger.error(f"Embedding error: {e}")
            return []
    
    async def _search_web(self, query: str) -> List[Dict[str, Any]]:
        """
        Search the web using Tavily API.
        
        Args:
            query: Search query
            
        Returns:
            List of web search results
        """
        # Log tool call for UI visibility
        self.logger.info(f"🌐 [TTD-DR] Tool Call: search_web()")
        
        if not self.tavily_api_key:
            return []
        
        try:
            from tavily import TavilyClient
            
            client = TavilyClient(api_key=self.tavily_api_key)
            response = await asyncio.to_thread(
                client.search,
                query=query,
                max_results=5,
                include_answer=True
            )
            
            results = []
            for result in response.get("results", []):
                results.append({
                    "title": result.get("title", ""),
                    "url": result.get("url", ""),
                    "snippet": result.get("content", ""),
                    "score": result.get("score", 0.5)
                })
            
            return results
            
        except ImportError:
            self.logger.warning("Tavily package not installed, skipping web search")
            return []
        except Exception as e:
            self.logger.error(f"Web search error: {e}")
            return []
    
    async def _synthesize_answer(self, 
                                question: str,
                                search_results: List[Dict[str, Any]]) -> str:
        """
        Synthesize a comprehensive answer from search results.
        
        Args:
            question: Original question
            search_results: Raw search results
            
        Returns:
            Synthesized answer text
        """
        # Log synthesis for UI visibility
        self.logger.info(f"📝 [TTD-DR] Tool Call: synthesize_answer({len(search_results)} results)")
        # Format search results
        formatted_results = []
        for i, result in enumerate(search_results[:5], 1):
            formatted_results.append(
                f"Result {i}:\n"
                f"Title: {result.get('title', 'N/A')}\n"
                f"Content: {result.get('snippet', result.get('content', 'N/A'))[:500]}\n"
            )
        
        search_results_text = "\n---\n".join(formatted_results)
        
        # Generate synthesis prompt
        prompt = ANSWER_SYNTHESIS_PROMPT.format(
            question=question,
            search_results=search_results_text
        )
        
        try:
            response = await self.llm.ainvoke([
                SystemMessage(content="""You are an expert at synthesizing information from multiple sources.
                Provide comprehensive, accurate answers that directly address the question."""),
                HumanMessage(content=prompt)
            ])
            
            return response.content
            
        except Exception as e:
            self.logger.error(f"Answer synthesis failed: {e}")
            # Return best raw result
            if search_results:
                return search_results[0].get("snippet", search_results[0].get("content", ""))
            return "Unable to synthesize answer from search results."
    
    def _parse_questions_response(self, response: str) -> Dict[str, Any]:
        """
        Parse the questions generation response.
        
        Args:
            response: Raw LLM response
            
        Returns:
            Parsed questions data
        """
        try:
            # Try to parse as JSON
            if "```json" in response:
                json_start = response.index("```json") + 7
                json_end = response.index("```", json_start)
                json_str = response[json_start:json_end].strip()
                return json.loads(json_str)
            else:
                return json.loads(response)
                
        except (json.JSONDecodeError, ValueError) as e:
            self.logger.warning(f"Failed to parse questions response: {e}")
            # Extract questions from text
            return self._extract_questions_from_text(response)
    
    def _extract_questions_from_text(self, text: str) -> Dict[str, Any]:
        """
        Extract questions from unformatted text.
        
        Args:
            text: Unstructured text
            
        Returns:
            Extracted questions data
        """
        questions = []
        gaps = []
        
        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            if line.endswith('?'):
                questions.append({
                    "question": line,
                    "purpose": "extracted from text",
                    "priority": "medium"
                })
            elif "gap" in line.lower() or "missing" in line.lower():
                gaps.append(line)
        
        return {
            "questions": questions,
            "gaps_identified": gaps
        }
    
    def _generate_fallback_questions(self, 
                                    plan: ResearchPlan,
                                    num_questions: int) -> List[Dict[str, Any]]:
        """
        Generate fallback questions when normal generation fails.
        
        Args:
            plan: Research plan
            num_questions: Number of questions needed
            
        Returns:
            Fallback questions
        """
        questions = []
        
        # Generate questions from sub_questions in plan
        for i, sq in enumerate(plan.sub_questions[:num_questions]):
            questions.append({
                "question": sq,
                "purpose": "from research plan",
                "priority": "high" if i == 0 else "medium"
            })
        
        # Fill remaining with generic questions
        while len(questions) < num_questions:
            questions.append({
                "question": f"More details about {plan.main_topic}",
                "purpose": "general expansion",
                "priority": "low"
            })
        
        return questions[:num_questions]
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
