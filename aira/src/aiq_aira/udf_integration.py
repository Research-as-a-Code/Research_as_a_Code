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
UDF (Universal Deep Research) Integration Module

This module implements the "strategy-as-code" engine from NVIDIA's Universal Deep Research
prototype, adapted as a dynamic tool for the AI-Q Research Assistant.

The core innovation: Converts natural language research plans into executable Python code
that can make calls to NIMs, RAG services, and web search dynamically.
"""

import asyncio
import logging
import json
import re
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
import aiohttp

logger = logging.getLogger(__name__)


@dataclass
class UDFExecutionResult:
    """Result of executing a UDF strategy."""
    success: bool
    synthesized_report: str
    sources: List[Dict[str, str]]
    execution_log: List[str]
    error: Optional[str] = None


class UDFStrategyCompiler:
    """
    Compiles natural language research strategies into executable Python code.
    
    Based on NVIDIA UDF's strategy-as-code paradigm where:
    1. The AI agent writes a multi-step research plan in natural language
    2. The compiler converts it to Python code with actual tool calls
    3. The code executes in a controlled environment
    4. Results are synthesized and returned
    """
    
    # Strategy-to-code compilation prompt
    STRATEGY_COMPILER_PROMPT = """You are a Python code generator for research automation.

Given a natural language research strategy, convert it into executable Python code that:
1. Makes async calls to search tools (RAG and web search)
2. Synthesizes findings into a structured report
3. Tracks all sources and citations

Available Tools:
- search_rag(query: str, collection: str) -> Dict[str, Any]
- search_web(query: str) -> List[Dict[str, str]]
- synthesize_findings(data: List[Dict]) -> str

IMPORTANT RULES:
- All code must be async/await compatible
- Use try/except for error handling
- Return a dict with keys: 'report', 'sources', 'log'
- Do not use imports - tools are pre-loaded
- Keep code under 50 lines

Natural Language Strategy:
{strategy}

Generate ONLY the Python function body (no function definition, no imports). Start directly with the code:
"""

    def __init__(self, llm: BaseChatModel):
        """
        Initialize the UDF compiler.
        
        Args:
            llm: The language model to use for strategy compilation
        """
        self.llm = llm
        
    async def compile_strategy(self, natural_language_plan: str) -> str:
        """
        Compile a natural language research strategy into Python code.
        
        Args:
            natural_language_plan: Natural language description of research steps
            
        Returns:
            Executable Python code as a string
        """
        logger.info("Compiling UDF strategy from natural language plan")
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an expert Python code generator."),
            ("human", self.STRATEGY_COMPILER_PROMPT)
        ])
        
        chain = prompt | self.llm
        
        response = await chain.ainvoke({"strategy": natural_language_plan})
        
        # Extract code from response
        code = response.content.strip()
        
        # Remove markdown code blocks if present
        if "```python" in code:
            code = code.split("```python")[1].split("```")[0].strip()
        elif "```" in code:
            code = code.split("```")[1].split("```")[0].strip()
            
        logger.debug(f"Compiled strategy code:\n{code}")
        return code


class UDFStrategyExecutor:
    """
    Executes compiled Python code in a controlled environment with access to research tools.
    
    This provides the "sandbox" where UDF-generated code runs, with access to:
    - RAG search via internal NIM services
    - Web search via Tavily
    - LLM-based synthesis
    """
    
    def __init__(
        self,
        rag_url: str,
        nemotron_nim_url: str,
        embedding_nim_url: str,
        tavily_api_key: Optional[str] = None
    ):
        """
        Initialize the UDF executor with access to necessary services.
        
        Args:
            rag_url: URL of the RAG service
            nemotron_nim_url: URL of the Nemotron reasoning NIM
            embedding_nim_url: URL of the embedding NIM
            tavily_api_key: Optional Tavily API key for web search
        """
        self.rag_url = rag_url
        self.nemotron_nim_url = nemotron_nim_url
        self.embedding_nim_url = embedding_nim_url
        self.tavily_api_key = tavily_api_key
        
    async def _search_rag_tool(self, query: str, collection: str) -> Dict[str, Any]:
        """Tool: Search RAG for information."""
        logger.info(f"UDF Tool Call: search_rag(query='{query[:50]}...', collection='{collection}')")
        
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": "Bearer not-needed"  # Placeholder for internal calls
                }
                data = {
                    "messages": [{"role": "user", "content": query}],
                    "use_knowledge_base": True,
                    "enable_citations": True,
                    "collection_name": collection
                }
                
                async with session.post(
                    f"{self.rag_url}/generate",
                    headers=headers,
                    json=data,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as response:
                    response.raise_for_status()
                    raw_result = await response.text()
                    
                    # Parse streaming response
                    content = ""
                    citations = []
                    for line in raw_result.splitlines():
                        if line.startswith("data: "):
                            event_data = json.loads(line[6:])
                            content += event_data.get("choices", [{}])[0].get("message", {}).get("content", "")
                            if "citations" in event_data:
                                citations.extend(event_data["citations"].get("results", []))
                    
                    return {
                        "content": content,
                        "citations": citations,
                        "source": "rag"
                    }
        except Exception as e:
            logger.error(f"RAG search failed: {e}")
            return {
                "content": f"Error searching RAG: {str(e)}",
                "citations": [],
                "source": "rag"
            }
    
    async def _search_web_tool(self, query: str) -> List[Dict[str, str]]:
        """Tool: Search web using Tavily."""
        logger.info(f"UDF Tool Call: search_web(query='{query[:50]}...')")
        
        if not self.tavily_api_key:
            logger.warning("Tavily API key not set, returning empty results")
            return []
        
        try:
            from langchain_community.tools import TavilySearchResults
            
            tool = TavilySearchResults(
                max_results=3,
                search_depth="advanced",
                include_answer=True,
                api_key=self.tavily_api_key
            )
            
            results = await tool.ainvoke({"query": query})
            
            return [
                {
                    "content": r.get("content", ""),
                    "url": r.get("url", ""),
                    "title": r.get("title", ""),
                    "source": "web"
                }
                for r in results
            ]
        except Exception as e:
            logger.error(f"Web search failed: {e}")
            return []
    
    async def _synthesize_findings_tool(self, data: List[Dict]) -> str:
        """Tool: Synthesize research findings using Nemotron NIM."""
        logger.info(f"UDF Tool Call: synthesize_findings(data with {len(data)} items)")
        
        # Prepare synthesis prompt
        findings_text = "\n\n".join([
            f"Source {i+1} ({item.get('source', 'unknown')}):\n{item.get('content', '')}"
            for i, item in enumerate(data)
        ])
        
        synthesis_prompt = f"""Synthesize the following research findings into a coherent report:

{findings_text}

Create a structured report that:
1. Integrates information from all sources
2. Highlights key insights
3. Maintains factual accuracy
4. Cites sources appropriately

Report:"""
        
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": "Bearer not-needed"
                }
                data_payload = {
                    "model": "nvidia/llama-3.3-nemotron-super-49b-v1.5",
                    "messages": [
                        {"role": "user", "content": synthesis_prompt}
                    ],
                    "max_tokens": 2000,
                    "temperature": 0.7
                }
                
                async with session.post(
                    f"{self.nemotron_nim_url}/v1/chat/completions",
                    headers=headers,
                    json=data_payload,
                    timeout=aiohttp.ClientTimeout(total=120)
                ) as response:
                    response.raise_for_status()
                    result = await response.json()
                    
                    return result["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"Synthesis failed: {e}")
            return f"Error synthesizing findings: {str(e)}"
    
    async def execute_strategy(self, compiled_code: str, context: Dict[str, Any]) -> UDFExecutionResult:
        """
        Execute the compiled strategy code in a controlled environment.
        
        Args:
            compiled_code: Python code to execute
            context: Context variables (e.g., collection name, topic)
            
        Returns:
            UDFExecutionResult with the synthesized report and metadata
        """
        logger.info("Executing UDF strategy code")
        
        execution_log = []
        sources = []
        
        # Create the execution namespace with available tools
        namespace = {
            "search_rag": self._search_rag_tool,
            "search_web": self._search_web_tool,
            "synthesize_findings": self._synthesize_findings_tool,
            "context": context,
            "execution_log": execution_log,
            "sources": sources,
            "json": json,
            "asyncio": asyncio,
            "logger": logger
        }
        
        try:
            # Wrap code in an async function
            wrapped_code = f"""
async def _udf_execute():
    {compiled_code.replace(chr(10), chr(10) + '    ')}
"""
            
            # Compile and execute
            exec(wrapped_code, namespace)
            result = await namespace["_udf_execute"]()
            
            # Validate result format
            if not isinstance(result, dict):
                raise ValueError(f"Strategy must return a dict, got {type(result)}")
            
            return UDFExecutionResult(
                success=True,
                synthesized_report=result.get("report", ""),
                sources=result.get("sources", []),
                execution_log=result.get("log", [])
            )
            
        except Exception as e:
            logger.error(f"UDF execution failed: {e}", exc_info=True)
            return UDFExecutionResult(
                success=False,
                synthesized_report="",
                sources=[],
                execution_log=execution_log,
                error=str(e)
            )


class UDFIntegration:
    """
    High-level UDF integration for AI-Q agent.
    
    This is the main interface that the AI-Q LangGraph agent uses to invoke
    dynamic research strategies.
    """
    
    def __init__(
        self,
        compiler_llm: BaseChatModel,
        rag_url: str,
        nemotron_nim_url: str,
        embedding_nim_url: str,
        tavily_api_key: Optional[str] = None
    ):
        """
        Initialize UDF integration.
        
        Args:
            compiler_llm: LLM for compiling strategies
            rag_url: RAG service URL
            nemotron_nim_url: Nemotron NIM URL
            embedding_nim_url: Embedding NIM URL
            tavily_api_key: Optional Tavily API key
        """
        self.compiler = UDFStrategyCompiler(compiler_llm)
        self.executor = UDFStrategyExecutor(
            rag_url=rag_url,
            nemotron_nim_url=nemotron_nim_url,
            embedding_nim_url=embedding_nim_url,
            tavily_api_key=tavily_api_key
        )
    
    async def execute_dynamic_strategy(
        self,
        natural_language_plan: str,
        context: Optional[Dict[str, Any]] = None
    ) -> UDFExecutionResult:
        """
        Execute a natural language research strategy dynamically.
        
        This is the main entry point that the AI-Q agent will call.
        
        Args:
            natural_language_plan: Natural language description of research strategy
            context: Optional context (collection name, topic, etc.)
            
        Returns:
            UDFExecutionResult with synthesized findings
        """
        logger.info("Starting UDF dynamic strategy execution")
        
        # Step 1: Compile the strategy
        try:
            compiled_code = await self.compiler.compile_strategy(natural_language_plan)
        except Exception as e:
            logger.error(f"Strategy compilation failed: {e}")
            return UDFExecutionResult(
                success=False,
                synthesized_report="",
                sources=[],
                execution_log=[],
                error=f"Compilation error: {str(e)}"
            )
        
        # Step 2: Execute the compiled code
        result = await self.executor.execute_strategy(
            compiled_code=compiled_code,
            context=context or {}
        )
        
        logger.info(f"UDF execution completed. Success: {result.success}")
        return result


# Tool wrapper for LangGraph integration
async def execute_dynamic_strategy_tool(
    natural_language_plan: str,
    udf_integration: UDFIntegration,
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    LangGraph tool wrapper for UDF dynamic strategy execution.
    
    This function is registered as a tool in the AI-Q LangGraph agent.
    
    Args:
        natural_language_plan: Natural language research strategy
        udf_integration: UDF integration instance
        context: Optional execution context
        
    Returns:
        Dictionary with execution results
    """
    result = await udf_integration.execute_dynamic_strategy(
        natural_language_plan=natural_language_plan,
        context=context
    )
    
    return {
        "success": result.success,
        "report": result.synthesized_report,
        "sources": result.sources,
        "log": result.execution_log,
        "error": result.error
    }

