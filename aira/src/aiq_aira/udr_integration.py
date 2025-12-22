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
UDR (Universal Deep Research) Integration Module

This module implements the "strategy-as-code" engine from NVIDIA's Universal Deep Research
prototype, adapted as a dynamic tool for the AI-Q Research Assistant.

The core innovation: Converts natural language research plans into executable Python code
that can make calls to NIMs, RAG services, and web search dynamically.
"""

import ast
import asyncio
import logging
import json
import os
import re
import sys
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

import aiohttp
from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.tools import TavilySearchResults
from pymilvus import connections, Collection, utility

logger = logging.getLogger(__name__)


@dataclass
class UDRExecutionResult:
    """Result of executing a UDR strategy."""
    success: bool
    synthesized_report: str
    sources: List[Dict[str, str]]
    execution_log: List[str]
    error: Optional[str] = None


class UDRStrategyCompiler:
    """
    Compiles natural language research strategies into executable Python code.
    
    Based on NVIDIA UDR's strategy-as-code paradigm where:
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

Available Tools (BE CAREFUL WITH DATA TYPES!):

1. search_rag(query: str, collection: str) -> Dict[str, Any]
   Returns: A SINGLE DICT like {{"content": str, "citations": list, "source": "rag"}}
   Usage: result = await search_rag("query", "collection")
          content = result.get("content", "")  # ✅ Can use .get() on dict
  
2. search_web(query: str) -> List[Dict[str, str]]
   Returns: A LIST of dicts like [{{"content": str, "url": str, "title": str}}, ...]
   Usage: results = await search_web("query")  # This is a LIST!
          for item in results:  # ✅ Must iterate through list
              content = item.get("content", "")  # ✅ .get() on each item
          ❌ WRONG: results.get("content")  # ERROR! Can't .get() on list!
  
3. synthesize_findings(data: List[Dict]) -> str
   Takes a list of search results and returns a synthesized report string
   Usage: report = await synthesize_findings([rag_result] + web_results)

CRITICAL REQUIREMENTS:
1. INITIALIZE ALL VARIABLES AT THE START:
   - log = []
   - sources = []
   - report = ""  ← MUST initialize this!
   
2. ONLY await async functions: search_rag(), search_web(), synthesize_findings()

3. DO NOT await: log.append(), sources.append(), variables, or any list/dict operations

4. Use try/except for error handling, but ALWAYS set report in except blocks:
   try:
       report = await synthesize_findings(data)
   except Exception as e:
       report = f"Error: {{{{str(e)}}}}"  ← MUST set report in except!

5. ABSOLUTELY MUST end with a return statement

6. The return MUST be a dict with these EXACT keys: "report", "sources", "log"

7. Do not use imports - tools are pre-loaded in namespace

8. Context dict has these EXACT keys (use them as shown):
   - context["topic"] - the research question/prompt
   - context["collection"] - the RAG collection name to search
   - context["report_organization"] - how to structure the report
   - context["search_web"] - whether to include web search
   NOTE: There is NO "query" key! Use context["topic"] for the question.
   **CRITICAL: Extract values to variables first, DO NOT use f-strings with context!**
   ✅ CORRECT: topic = context["topic"]
              results = await search_web(topic)
   ❌ WRONG: results = await search_web(f"query for {{context['topic']}}")  ← Template error!

9. **THESE ARE THE ONLY 3 TOOLS - DO NOT INVENT OR CALL OTHER FUNCTIONS**

10. **If you need analysis, use synthesize_findings() - it handles ALL synthesis/analysis**

11. **If a plan step doesn't map to a tool, SKIP IT or use synthesize_findings()**

12. **CRITICAL: Handle list vs dict correctly!**
    - search_rag() returns Dict → Use result.get("key")
    - search_web() returns List[Dict] → Use for item in results: item.get("key")
    - ❌ NEVER do: list_result.get("key") → Will cause "list has no attribute 'get'" error!

13. **CRITICAL: These are FUNCTION CALLS, not dictionary keys!**
    - ✅ CORRECT: report = await synthesize_findings(data)  # Function call with ()
    - ❌ WRONG: report = data['synthesize']  # KeyError: 'synthesize'!
    - ❌ WRONG: report = synthesize_findings  # Missing await and ()!
    - Remember: ALWAYS use () to call functions and await for async functions!

14. **CRITICAL: ALWAYS check list length before accessing indices!**
    - ❌ WRONG: result = results[0]  # IndexError if list is empty!
    - ✅ CORRECT: result = results[0] if len(results) > 0 else {{"content": "No results"}}
    - ✅ CORRECT: if results: result = results[0]
    - ✅ CORRECT: for item in results:  # Safe - iterates 0 times if empty
    - **NEVER access list[index] without checking length first!**

❌ FORBIDDEN - DO NOT USE:
- Calling functions not in the available tools list
- Inventing helper functions (analyze_*, calculate_*, process_*, evaluate_*)
- Using Python standard library (open, json.loads, requests, etc.)
- Any function call other than: search_rag, search_web, synthesize_findings

✅ ALLOWED - YOU CAN USE:
- Variables: log = [], sources = [], data = []
- List operations: log.append(), sources.extend(), list.get()
- Dict operations: {{{{"key": value}}}}, dict.items(), dict.keys(), dict.values()
- String operations: f"string {{{{variable}}}}", str.format(), str.split(), str.strip()
- Python built-ins: str(), len(), range(), enumerate(), min(), max(), sum()
- Control flow: if, for, while
- Exception handling: try/except with str(e) for error messages
- The 3 async tools: search_rag(), search_web(), synthesize_findings()

EXAMPLE - Tariff Research (PAY ATTENTION TO DATA TYPES!):
```python
# STEP 1: Initialize ALL variables at the start (NO await)
log = []
sources = []
report = ""  # ← MUST initialize! Prevents "variable not defined" errors

# STEP 2: Search RAG - returns a SINGLE DICT
# Use context values directly - NO f-strings needed!
topic = context["topic"]
collection_name = context["collection"]

try:
    # search_rag returns Dict - single result with nested citations
    rag_result = await search_rag(topic, collection_name)  # YES await
    # ✅ rag_result is a dict, can use .get()
    # IMPORTANT: Include citations array to preserve document names!
    sources.append({{
        "type": "rag",
        "content": rag_result.get("content", ""),
        "citations": rag_result.get("citations", [])  # ← Preserve document names!
    }})  # NO await
    
    # STEP 3: Search web - returns a LIST of dicts
    if {{{{context["search_web"]}}}}:
        # search_web returns List[Dict] - multiple results
        web_results = await search_web(topic)  # YES await - web_results is a LIST!
        
        # ✅ SAFE: Iterate through list (works even if empty - just does 0 iterations)
        for item in web_results:  # NO await - iteration is NOT async
            # ❌ UNSAFE would be: first_item = web_results[0]  ← IndexError if empty!
            # ✅ Now item is a dict, can use .get()
            sources.append({{
                "type": "web",
                "url": item.get("url", ""),
                "title": item.get("title", ""),
                "content": item.get("content", "")
            }})  # NO await
    else:
        web_results = []
    
    # STEP 4: Synthesize - pass list of all results
    # Combine single dict + list of dicts into one list
    all_data = [rag_result] + web_results  # NO await
    report = await synthesize_findings(all_data)  # YES await
    
except Exception as e:
    log.append(f"Error: {{{{str(e)}}}}")  # NO await
    report = f"Research error: {{{{str(e)}}}}"  # ← Set report in except!

# STEP 5: MANDATORY RETURN
return {{"report": report, "sources": sources, "log": log}}  # NO await
```

Natural Language Strategy:
{strategy}

NOW GENERATE THE CODE:
- Write ONLY the Python function body (no function definition, no imports)
- FIRST LINE: Initialize ALL variables: log = [], sources = [], report = ""
- CRITICAL: Extract context values to variables FIRST: topic = context["topic"], collection_name = context["collection"]
- CRITICAL: DO NOT use f-strings with context dict! Use variables directly!
- Use try/except to catch errors and ALWAYS set report in except block
- Make async calls to the tools WITH PARENTHESES: await search_rag()
- CRITICAL: Use () to call functions - they are FUNCTION CALLS, not dict keys!
- CRITICAL: Always await async functions: await search_rag(), await search_web(), await synthesize_findings()
- CRITICAL: NEVER access list[index] without checking if list has items first!
  - ❌ BAD: result = results[0]  ← Will crash if empty!
  - ✅ GOOD: for item in results:  ← Safe, does 0 iterations if empty
  - ✅ GOOD: if len(results) > 0: result = results[0]
- End with a return statement that returns {{"report": report, "sources": sources, "log": log}}
- DO NOT forget the return statement!
- REMINDER: report MUST be set before the return (either in try or in except)!

CODE:
"""

    def __init__(self, llm: BaseChatModel):
        """
        Initialize the UDR compiler.
        
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
        logger.info("Compiling UDR strategy from natural language plan")
        
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
        
        # Log the compiled code (always, not just at DEBUG)
        logger.info("=" * 60)
        logger.info("📝 COMPILED UDR STRATEGY CODE:")
        logger.info("=" * 60)
        for i, line in enumerate(code.split('\n'), 1):
            logger.info(f"{i:3d} | {line}")
        logger.info("=" * 60)
            
        return code
    
    def validate_generated_code(self, code: str) -> tuple[bool, str]:
        """
        Validate generated UDR code before execution.
        
        Checks for:
        - Only allowed function calls (search_rag, search_web, synthesize_findings)
        - No forbidden function calls
        - Valid Python syntax
        
        Args:
            code: The generated Python code to validate
            
        Returns:
            (is_valid, error_message): Tuple of validation result and error message if invalid
        """
        # DEBUG: Print the generated code to see what LLM created
        print("=" * 80, flush=True, file=sys.stderr)
        print("🔍 VALIDATING GENERATED UDR CODE:", flush=True, file=sys.stderr)
        print("=" * 80, flush=True, file=sys.stderr)
        for i, line in enumerate(code.split('\n'), 1):
            print(f"{i:3d} | {line}", flush=True, file=sys.stderr)
        print("=" * 80, flush=True, file=sys.stderr)
        
        allowed_functions = {'search_rag', 'search_web', 'synthesize_findings'}
        allowed_methods = {'append', 'extend', 'get', 'strip', 'split', 'join', 'format', 'lower', 'upper', 'items', 'keys', 'values'}
        # Python built-ins that are safe and commonly needed
        allowed_builtins = {'str', 'int', 'float', 'bool', 'len', 'range', 'enumerate', 'zip', 'dict', 'list', 'tuple', 'set', 'min', 'max', 'sum', 'any', 'all'}
        forbidden_patterns = [
            'analyze_', 'calculate_', 'process_', 'evaluate_', 'compute_',
            'import ', 'open(', 'json.', 'requests.', 'urllib', '__'
        ]
        
        # Check for forbidden patterns first (faster)
        code_lower = code.lower()
        for pattern in forbidden_patterns:
            if pattern in code_lower:
                return False, f"Forbidden pattern detected: '{pattern}'. Only use search_rag(), search_web(), synthesize_findings()"
        
        # Parse and validate AST
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return False, f"Syntax error in generated code: {e}"
        
        # Additional validation: Compile in async context (since we wrap in async function)
        try:
            # Wrap in async function like we do at execution time
            wrapped = f"async def _test():\n{chr(10).join('    ' + line for line in code.split(chr(10)))}"
            compile(wrapped, '<string>', 'exec')
        except SyntaxError as e:
            return False, f"Code compilation error (indentation/structure): {str(e)}"
        
        # Check all function calls
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func_name = None
                
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    # Method call like list.append()
                    func_name = node.func.attr
                
                if func_name:
                    # Check if it's an allowed function, method, or built-in
                    if func_name not in allowed_functions and func_name not in allowed_methods and func_name not in allowed_builtins:
                        return False, f"Forbidden function call: '{func_name}()'. Only allowed: {allowed_functions}"
        
        # Check for return statement
        has_return = any(isinstance(node, ast.Return) for node in ast.walk(tree))
        if not has_return:
            return False, "Code must have a return statement returning {'report': ..., 'sources': ..., 'log': ...}"
        
        logger.info("✅ Code validation passed")
        return True, ""


class UDRStrategyExecutor:
    """
    Executes compiled Python code in a controlled environment with access to research tools.
    
    This provides the "sandbox" where UDR-generated code runs, with access to:
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
        Initialize the UDR executor with access to necessary services.
        
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
        """Tool: Search RAG using direct Milvus + Embedding NIM (same as main agent).
        
        Supports multiple collections passed as comma-separated string.
        """
        print("🔷 _search_rag_tool ENTERED!", flush=True, file=sys.stderr)
        print(f"🔷 Query: {query[:50]}..., Collection(s): {collection}", flush=True, file=sys.stderr)
        
        try:
            # Get Milvus connection info
            milvus_host = os.getenv("MILVUS_HOST", "milvus.rag-blueprint.svc.cluster.local")
            milvus_port = os.getenv("MILVUS_PORT", "19530")
            
            # Connect to Milvus
            connections.connect(alias="default", host=milvus_host, port=milvus_port)
            
            # Parse multiple collections (comma-separated)
            collection_names = [c.strip() for c in collection.split(',') if c.strip()]
            print(f"🔷 Parsed {len(collection_names)} collection(s): {collection_names}", flush=True, file=sys.stderr)
            
            # Get embedding from NIM (do this once)
            async with aiohttp.ClientSession() as session:
                embedding_payload = {
                    "input": query,
                    "model": "snowflake/arctic-embed-l",
                    "input_type": "query"
                }
                
                async with session.post(
                    f"{self.embedding_nim_url}/v1/embeddings",
                    json=embedding_payload,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as embed_response:
                    embed_response.raise_for_status()
                    embed_result = await embed_response.json()
                    query_embedding = embed_result["data"][0]["embedding"]
            
            # Search all collections and aggregate results
            all_content_parts = []
            all_citations = []
            results_per_collection = max(2, 6 // len(collection_names))  # Distribute results evenly
            
            for coll_name in collection_names:
                # Check if collection exists
                if not utility.has_collection(coll_name):
                    logger.warning(f"Collection '{coll_name}' does not exist, skipping")
                    print(f"🔷 Collection '{coll_name}' does not exist, skipping", flush=True, file=sys.stderr)
                    continue
                
                # Query this collection
                coll = Collection(coll_name)
                coll.load()
                
                search_params = {"metric_type": "L2", "params": {"nprobe": 10}}
                results = coll.search(
                    data=[query_embedding],
                    anns_field="embedding",
                    param=search_params,
                    limit=results_per_collection,
                    output_fields=["text", "source"]
                )
                
                if results and len(results[0]) > 0:
                    print(f"🔷 Collection '{coll_name}': found {len(results[0])} results", flush=True, file=sys.stderr)
                    for i, hit in enumerate(results[0]):
                        try:
                            text = hit.entity.text if hasattr(hit.entity, 'text') else hit.entity.get('text', '')
                            source = hit.entity.source if hasattr(hit.entity, 'source') else hit.entity.get('source', f"Doc {i+1}")
                        except Exception:
                            text = str(hit.entity.get('text', ''))
                            source = str(hit.entity.get('source', f"Doc {i+1}"))
                        
                        all_content_parts.append(f"[{coll_name}/{source}] {text}")
                        # Include collection name so we know which collection each document came from
                        all_citations.append({"source": source, "collection": coll_name, "text": text[:200]})
            
            if not all_content_parts:
                return {
                    "content": "No relevant documents found in any collection",
                    "citations": [],
                    "source": "rag"
                }
            
            content = "\n\n".join(all_content_parts)
            
            logger.info(f"RAG found {len(all_citations)} results across {len(collection_names)} collection(s)")
            print(f"🔷 Total: {len(all_citations)} results across {len(collection_names)} collection(s)", flush=True, file=sys.stderr)
            return {
                "content": content,
                "citations": all_citations,
                "source": "rag"
            }
            
        except Exception as e:
            logger.error(f"RAG search failed: {e}", exc_info=True)
            return {
                "content": f"Error searching RAG: {str(e)}",
                "citations": [],
                "source": "rag"
            }
    
    async def _search_web_tool(self, query: str) -> List[Dict[str, str]]:
        """Tool: Search web using Tavily."""
        print(f"🔷 _search_web_tool called with query length: {len(query)}", flush=True, file=sys.stderr)
        # Add to execution log for UI visibility
        if hasattr(self, '_current_execution_log') and self._current_execution_log is not None:
            self._current_execution_log.append(f"🌐 Tool call: search_web()")
            print(f"🔷 Added to execution_log, now has {len(self._current_execution_log)} entries", flush=True, file=sys.stderr)
        
        if not self.tavily_api_key:
            print("⚠️  Tavily API key not set, returning empty results", flush=True, file=sys.stderr)
            return []
        
        try:
            print("🔷 Creating Tavily tool...", flush=True, file=sys.stderr)
            tool = TavilySearchResults(
                max_results=3,
                search_depth="advanced",
                include_answer=True,
                api_key=self.tavily_api_key
            )
            
            print("🔷 Calling Tavily API...", flush=True, file=sys.stderr)
            results = await tool.ainvoke({"query": query})
            print(f"🔷 Tavily returned {len(results) if isinstance(results, list) else 'unknown'} results", flush=True, file=sys.stderr)
            
            formatted_results = [
                {
                    "content": r.get("content", ""),
                    "url": r.get("url", ""),
                    "title": r.get("title", ""),
                    "source": "web"
                }
                for r in results
            ]
            print(f"🔷 search_web() completed with {len(formatted_results)} results", flush=True, file=sys.stderr)
            return formatted_results
        except Exception as e:
            print(f"❌ Web search failed: {e}", flush=True, file=sys.stderr)
            return []
    
    async def _synthesize_findings_tool(self, data: List[Dict]) -> str:
        """Tool: Synthesize research findings using Nemotron NIM."""
        print(f"🔷 _synthesize_findings_tool called with {len(data)} items", flush=True, file=sys.stderr)
        # Add to execution log for UI visibility
        if hasattr(self, '_current_execution_log') and self._current_execution_log is not None:
            self._current_execution_log.append(f"📝 Tool call: synthesize_findings({len(data)} sources)")
            print(f"🔷 Added to execution_log, now has {len(self._current_execution_log)} entries", flush=True, file=sys.stderr)
        
        # Prepare synthesis prompt
        print("🔷 Preparing findings text...", flush=True, file=sys.stderr)
        findings_text = "\n\n".join([
            f"Source {i+1} ({item.get('source', 'unknown')}):\n{item.get('content', '')}"
            for i, item in enumerate(data)
        ])
        print(f"🔷 Findings text length: {len(findings_text)} chars", flush=True, file=sys.stderr)
        
        synthesis_prompt = f"""Synthesize the following research findings into a coherent report:

{findings_text}

Create a structured report that:
1. Integrates information from all sources
2. Highlights key insights
3. Maintains factual accuracy
4. Cites sources appropriately

Report:"""
        print(f"🔷 Synthesis prompt length: {len(synthesis_prompt)} chars", flush=True, file=sys.stderr)
        
        try:
            print(f"🔷 Opening HTTP session to {self.nemotron_nim_url}...", flush=True, file=sys.stderr)
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": "Bearer not-needed"
                }
                data_payload = {
                    "model": "nvidia/llama-3.1-nemotron-nano-8b-v1",
                    "messages": [
                        {"role": "user", "content": synthesis_prompt}
                    ],
                    "max_tokens": 2000,
                    "temperature": 0.7
                }
                
                print("🔷 Calling Instruct LLM NIM...", flush=True, file=sys.stderr)
                try:
                    async with session.post(
                        f"{self.nemotron_nim_url}/v1/chat/completions",
                        headers=headers,
                        json=data_payload,
                        timeout=aiohttp.ClientTimeout(total=60)  # Reduced from 120 to 60
                    ) as response:
                        print(f"🔷 Response status: {response.status}", flush=True, file=sys.stderr)
                        response.raise_for_status()
                        result = await response.json()
                        synthesized = result["choices"][0]["message"]["content"]
                        print(f"🔷 synthesize_findings() completed. Report length: {len(synthesized)} chars", flush=True, file=sys.stderr)
                        return synthesized
                except asyncio.TimeoutError:
                    print(f"❌ Instruct LLM NIM timed out after 60s", flush=True, file=sys.stderr)
                    return "Error: LLM synthesis timed out after 60 seconds"
                except Exception as http_error:
                    print(f"❌ Instruct LLM NIM HTTP error: {http_error}", flush=True, file=sys.stderr)
                    return f"Error: LLM HTTP request failed: {str(http_error)}"
        except Exception as e:
            print(f"❌ Synthesis failed: {e}", flush=True, file=sys.stderr)
            return f"Error synthesizing findings: {str(e)}"
    
    async def execute_strategy(self, compiled_code: str, context: Dict[str, Any]) -> UDRExecutionResult:
        """
        Execute the compiled strategy code in a controlled environment.
        
        Args:
            compiled_code: Python code to execute
            context: Context variables (e.g., collection name, topic)
            
        Returns:
            UDRExecutionResult with the synthesized report and metadata
        """
        print("🟡 EXECUTOR execute_strategy ENTERED!", flush=True, file=sys.stderr)
        print("🟡 About to call logger.info line 1...", flush=True, file=sys.stderr)
        logger.info("=" * 80)
        print("🟡 Called logger.info line 1, about to call line 2...", flush=True, file=sys.stderr)
        logger.info("UDR EXECUTOR: Starting strategy execution")
        print("🟡 Called logger.info line 2, about to call line 3...", flush=True, file=sys.stderr)
        logger.info(f"  Context: topic='{context.get('topic', 'N/A')[:50]}...', collection='{context.get('collection', 'N/A')}'")
        print("🟡 Called logger.info line 3, about to call line 4...", flush=True, file=sys.stderr)
        logger.info("=" * 80)
        print("🟡 All logger.info calls complete!", flush=True, file=sys.stderr)
        
        print("🟡 Creating execution_log and sources...", flush=True, file=sys.stderr)
        execution_log = []
        sources = []
        
        # Make execution_log accessible to tools for progress tracking
        self._current_execution_log = execution_log
        
        print("🟡 About to create namespace dict...", flush=True, file=sys.stderr)
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
        print("🟡 Namespace created successfully!", flush=True, file=sys.stderr)
        
        print("🟡 Entering try block...", flush=True, file=sys.stderr)
        try:
            # Wrap code in an async function
            print("🟡 About to log 'Wrapping code'...", flush=True, file=sys.stderr)
            logger.info("📦 Wrapping code in async function...")
            print("🟡 Logged 'Wrapping code'!", flush=True, file=sys.stderr)
            print(f"🟡 compiled_code length: {len(compiled_code)}", flush=True, file=sys.stderr)
            print("🟡 About to create wrapped_code string...", flush=True, file=sys.stderr)
            wrapped_code = f"""
async def _udf_execute():
    import sys
    print("🔶 INSIDE _udf_execute()! Generated code is starting...", flush=True, file=sys.stderr)
    try:
        {compiled_code.replace(chr(10), chr(10) + '        ')}
    except Exception as e:
        print(f"🔶 EXCEPTION in generated code: {{type(e).__name__}}: {{str(e)}}", flush=True, file=sys.stderr)
        raise
"""
            print("🟡 wrapped_code created!", flush=True, file=sys.stderr)
            
            # Compile and execute
            print("🟡 About to log 'Compiling'...", flush=True, file=sys.stderr)
            logger.info("🔧 Compiling wrapped code...")
            print("🟡 About to exec()...", flush=True, file=sys.stderr)
            exec(wrapped_code, namespace)
            print("🟡 exec() completed!", flush=True, file=sys.stderr)
            logger.info("▶️  Executing async function...")
            print("🟡 About to await _udf_execute()...", flush=True, file=sys.stderr)
            result = await namespace["_udf_execute"]()
            print("🟡 _udf_execute() completed!", flush=True, file=sys.stderr)
            logger.info(f"✅ Execution completed. Result type: {type(result)}")
            
            # Validate result format - handle None gracefully
            if result is None:
                logger.warning("UDR code returned None - using fallback with execution log")
                result = {
                    "report": "UDR execution completed but no report was generated. Check execution log for details.",
                    "sources": sources,  # Use captured sources
                    "log": execution_log  # Use captured log
                }
            elif not isinstance(result, dict):
                raise ValueError(f"Strategy must return a dict, got {type(result)}")
            
            logger.info(f"📊 Report length: {len(result.get('report', ''))}, Sources: {len(result.get('sources', []))}")
            # Use the execution_log from namespace (contains tool calls), not from result
            final_log = execution_log if execution_log else result.get("log", [])
            print(f"🟡 Final execution_log has {len(final_log)} entries", flush=True, file=sys.stderr)
            logger.info(f"📋 Execution log entries: {len(final_log)}")
            logger.info("=" * 80)
            logger.info("UDR EXECUTOR: Returning success")
            logger.info("=" * 80)
            return UDRExecutionResult(
                success=True,
                synthesized_report=result.get("report", ""),
                sources=result.get("sources", []),
                execution_log=final_log
            )
            
        except Exception as e:
            logger.error(f"❌ UDR execution failed: {e}", exc_info=True)
            logger.info("=" * 80)
            logger.info("UDR EXECUTOR: Returning error")
            logger.info("=" * 80)
            return UDRExecutionResult(
                success=False,
                synthesized_report="",
                sources=[],
                execution_log=execution_log,
                error=str(e)
            )


class UDRIntegration:
    """
    High-level UDR integration for AI-Q agent.
    
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
        Initialize UDR integration.
        
        Args:
            compiler_llm: LLM for compiling strategies
            rag_url: RAG service URL
            nemotron_nim_url: Nemotron NIM URL
            embedding_nim_url: Embedding NIM URL
            tavily_api_key: Optional Tavily API key
        """
        self.compiler = UDRStrategyCompiler(compiler_llm)
        self.executor = UDRStrategyExecutor(
            rag_url=rag_url,
            nemotron_nim_url=nemotron_nim_url,
            embedding_nim_url=embedding_nim_url,
            tavily_api_key=tavily_api_key
        )
    
    async def execute_dynamic_strategy(
        self,
        natural_language_plan: str,
        context: Optional[Dict[str, Any]] = None
    ) -> UDRExecutionResult:
        """
        Execute a natural language research strategy dynamically.
        
        This is the main entry point that the AI-Q agent will call.
        
        Args:
            natural_language_plan: Natural language description of research strategy
            context: Optional context (collection name, topic, etc.)
            
        Returns:
            UDRExecutionResult with synthesized findings
        """
        print("🟢 UDR execute_dynamic_strategy called!", flush=True, file=sys.stderr)
        logger.info("Starting UDR dynamic strategy execution")
        print("🟢 About to compile strategy...", flush=True, file=sys.stderr)
        
        # Track high-level steps
        orchestration_log = []
        
        # Step 1: Compile the strategy
        orchestration_log.append("🔧 Compiling natural language plan to Python code...")
        try:
            compiled_code = await self.compiler.compile_strategy(natural_language_plan)
            orchestration_log.append("✅ Code compilation successful")
        except Exception as e:
            logger.error(f"Strategy compilation failed: {e}")
            orchestration_log.append(f"❌ Compilation failed: {str(e)}")
            return UDRExecutionResult(
                success=False,
                synthesized_report="",
                sources=[],
                execution_log=orchestration_log,
                error=f"Compilation error: {str(e)}"
            )
        
        # Step 1.5: Validate the generated code
        orchestration_log.append("🔍 Validating generated code...")
        is_valid, validation_error = self.compiler.validate_generated_code(compiled_code)
        if not is_valid:
            logger.error(f"❌ Generated code validation failed: {validation_error}")
            orchestration_log.append(f"❌ Validation failed: {validation_error}")
            return UDRExecutionResult(
                success=False,
                synthesized_report=f"Code generation error: {validation_error}\n\nThe LLM tried to use functions that don't exist. Only these tools are available:\n- search_rag(query, collection)\n- search_web(query)\n- synthesize_findings(data)\n\nTip: Try simplifying your query or let the system choose the strategy automatically.",
                sources=[],
                execution_log=orchestration_log,
                error=f"Validation error: {validation_error}"
            )
        orchestration_log.append("✅ Code validation passed")
        
        # Step 2: Execute the compiled code
        orchestration_log.append("⚙️ Executing compiled strategy code...")
        print("🟢 Compilation done! About to execute code...", flush=True, file=sys.stderr)
        result = await self.executor.execute_strategy(
            compiled_code=compiled_code,
            context=context or {}
        )
        
        # Merge orchestration logs with execution logs (tool calls)
        if result.success:
            all_logs = orchestration_log + (result.execution_log if result.execution_log else [])
            result.execution_log = all_logs
            print(f"🟢 Merged logs: {len(all_logs)} total entries", flush=True, file=sys.stderr)
        else:
            result.execution_log = orchestration_log
        print(f"🟢 Execution returned! Success: {result.success}, Logs: {len(result.execution_log)}", flush=True, file=sys.stderr)
        
        logger.info(f"UDR execution completed. Success: {result.success}")
        return result


# Tool wrapper for LangGraph integration
async def execute_dynamic_strategy_tool(
    natural_language_plan: str,
    udr_integration: UDRIntegration,
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    LangGraph tool wrapper for UDR dynamic strategy execution.
    
    This function is registered as a tool in the AI-Q LangGraph agent.
    
    Args:
        natural_language_plan: Natural language research strategy
        udr_integration: UDR integration instance
        context: Optional execution context
        
    Returns:
        Dictionary with execution results
    """
    result = await udr_integration.execute_dynamic_strategy(
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

