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
log.append("Searching tariff database")  # NO await
query_text = f"tariff codes for {{{{context['topic']}}}}"

try:
    # search_rag returns Dict - single result
    rag_result = await search_rag(query_text, {{{{context["collection"]}}}})  # YES await
    # ✅ rag_result is a dict, can use .get()
    sources.append({{"type": "rag", "content": rag_result.get("content", "")}})  # NO await
    
    # STEP 3: Search web - returns a LIST of dicts
    if {{{{context["search_web"]}}}}:
        log.append("Searching web")  # NO await
        # search_web returns List[Dict] - multiple results
        web_results = await search_web(query_text)  # YES await - web_results is a LIST!
        
        # ✅ Iterate through the list to access each dict
        for item in web_results:  # NO await - iteration is NOT async
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
    log.append("Synthesizing findings")  # NO await
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
- Use try/except to catch errors and ALWAYS set report in except block
- Make async calls to the tools WITH PARENTHESES: await search_rag()
- CRITICAL: Use () to call functions - they are FUNCTION CALLS, not dict keys!
- CRITICAL: Always await async functions: await search_rag(), await search_web(), await synthesize_findings()
- End with a return statement that returns {{"report": report, "sources": sources, "log": log}}
- DO NOT forget the return statement!
- REMINDER: report MUST be set before the return (either in try or in except)!

CODE:
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
        
        # Log the compiled code (always, not just at DEBUG)
        logger.info("=" * 60)
        logger.info("📝 COMPILED UDF STRATEGY CODE:")
        logger.info("=" * 60)
        for i, line in enumerate(code.split('\n'), 1):
            logger.info(f"{i:3d} | {line}")
        logger.info("=" * 60)
            
        return code
    
    def validate_generated_code(self, code: str) -> tuple[bool, str]:
        """
        Validate generated UDF code before execution.
        
        Checks for:
        - Only allowed function calls (search_rag, search_web, synthesize_findings)
        - No forbidden function calls
        - Valid Python syntax
        
        Args:
            code: The generated Python code to validate
            
        Returns:
            (is_valid, error_message): Tuple of validation result and error message if invalid
        """
        import ast
        
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
        """Tool: Search RAG using direct Milvus + Embedding NIM (same as main agent)."""
        logger.info(f"UDF Tool Call: search_rag(query='{query[:50]}...', collection='{collection}')")
        
        try:
            from pymilvus import connections, Collection, utility
            import os
            
            # Get Milvus connection info
            milvus_host = os.getenv("MILVUS_HOST", "milvus.rag-blueprint.svc.cluster.local")
            milvus_port = os.getenv("MILVUS_PORT", "19530")
            
            # Connect to Milvus
            connections.connect(alias="default", host=milvus_host, port=milvus_port)
            
            # Check if collection exists
            if not utility.has_collection(collection):
                logger.warning(f"Collection '{collection}' does not exist")
                return {
                    "content": f"Collection '{collection}' not found",
                    "citations": [],
                    "source": "rag"
                }
            
            # Get embedding from NIM
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
                return {
                    "content": "No relevant documents found",
                    "citations": [],
                    "source": "rag"
                }
            
            # Format results
            content_parts = []
            citations = []
            
            for i, hit in enumerate(results[0]):
                try:
                    text = hit.entity.text if hasattr(hit.entity, 'text') else hit.entity.get('text', '')
                    source = hit.entity.source if hasattr(hit.entity, 'source') else hit.entity.get('source', f"Doc {i+1}")
                except Exception:
                    text = str(hit.entity.get('text', ''))
                    source = str(hit.entity.get('source', f"Doc {i+1}"))
                
                content_parts.append(f"[{i+1}] {text}")
                citations.append({"source": source, "text": text[:200]})
            
            content = "\n\n".join(content_parts)
            
            logger.info(f"RAG found {len(results[0])} results from collection '{collection}'")
            return {
                "content": content,
                "citations": citations,
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
                    "model": "nvidia/llama-3.1-nemotron-nano-8b-v1",
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
            
            # Validate result format - handle None gracefully
            if result is None:
                logger.warning("UDF code returned None - using fallback with execution log")
                result = {
                    "report": "UDF execution completed but no report was generated. Check execution log for details.",
                    "sources": sources,  # Use captured sources
                    "log": execution_log  # Use captured log
                }
            elif not isinstance(result, dict):
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
        
        # Step 1.5: Validate the generated code
        is_valid, validation_error = self.compiler.validate_generated_code(compiled_code)
        if not is_valid:
            logger.error(f"❌ Generated code validation failed: {validation_error}")
            return UDFExecutionResult(
                success=False,
                synthesized_report=f"Code generation error: {validation_error}\n\nThe LLM tried to use functions that don't exist. Only these tools are available:\n- search_rag(query, collection)\n- search_web(query)\n- synthesize_findings(data)\n\nTip: Try simplifying your query or let the system choose the strategy automatically.",
                sources=[],
                execution_log=["Code validation failed", validation_error],
                error=f"Validation error: {validation_error}"
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

