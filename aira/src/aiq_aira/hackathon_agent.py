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
Enhanced AI-Q Agent with UDR Integration for Hackathon

This module implements the two-level agentic system described in the design plan:
- Level 1: AI-Q agent (orchestrator) built on LangGraph
- Level 2: UDR dynamic strategy executor (called as a tool by AI-Q)

The agent state is designed to be streamed to CopilotKit for real-time UI visualization.
"""

import logging
import operator
from typing import List, Annotated, TypedDict, Literal, Optional
from dataclasses import dataclass, field

from langgraph.graph import StateGraph, END
from langgraph.types import StreamWriter
from langchain_core.runnables import RunnableConfig
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.language_models import BaseChatModel

from aiq_aira.schema import GeneratedQuery
from aiq_aira.udr_integration import UDRIntegration, UDRExecutionResult
from aiq_aira.nodes import generate_query, web_research, summarize_sources, reflect_on_summary, finalize_summary

logger = logging.getLogger(__name__)


# ========================================
# Enhanced Agent State for CopilotKit
# ========================================

class HackathonAgentState(TypedDict):
    """
    State object for the enhanced AI-Q + UDR agent.
    
    This state is streamed to CopilotKit's useCoAgentStateRender hook
    for real-time visualization in the frontend.
    
    Key innovation: The 'logs' field is an append-only list that captures
    every step of the agentic flow for UI rendering.
    """
    # User inputs
    research_prompt: str
    report_organization: str
    collection: str
    search_web: bool
    strategy: str  # 'udr' or 'ttd_dr'
    
    # Planning phase
    plan: str
    queries: List[GeneratedQuery]
    
    # Execution phase
    web_research_results: List[str]
    citations: str
    running_summary: str
    
    # UDR dynamic strategy phase
    udr_strategy: str
    udr_result: dict
    
    # TTD-DR specific state fields
    ttd_dr_stage: Optional[str]  # 'planning', 'iterating', 'synthesizing', 'complete'
    ttd_dr_iteration: Optional[int]
    ttd_dr_convergence: Optional[List[float]]
    ttd_dr_questions: Optional[List[str]]
    ttd_dr_gaps: Optional[List[str]]
    ttd_dr_improvements: Optional[List[str]]
    
    # Final output
    final_report: str
    
    # Logs for CopilotKit visualization (append-only)
    logs: Annotated[List[str], operator.add]


# ========================================
# Agent Nodes
# ========================================

async def planner_node(state: HackathonAgentState, config: RunnableConfig):
    """
    Planner node: Analyzes the research prompt and decides the strategy.
    
    Decision logic:
    - Complex, multi-domain research → Use dynamic strategy (UDR or TTD-DR based on user selection)
    - Straightforward queries → Use standard AI-Q RAG pipeline
    
    NOTE: Removed 'writer' parameter to fix LangGraph checkpointer compatibility issue.
    """
    logger.info("PLANNER NODE: Analyzing research prompt")
    
    llm = config["configurable"].get("llm")
    prompt_text = state["research_prompt"]
    report_org = state["report_organization"]
    selected_strategy = state.get("strategy", "udr")  # User-selected: 'udr' or 'ttd_dr'
    
    # Planning prompt template with proper variable escaping
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a research planning expert."),
        ("human", """Analyze this research request:

Topic: {topic}
Report Organization: {report_org}

Determine if this requires:
A) SIMPLE_RAG: Standard query-based research (straightforward topic, single domain)
B) DYNAMIC_STRATEGY: Complex multi-step strategy (multiple domains, synthesis needed, cost-benefit analysis)

Respond with JSON:
{{"strategy": "SIMPLE_RAG" or "DYNAMIC_STRATEGY", "rationale": "brief explanation", "plan": "if DYNAMIC_STRATEGY, outline the research steps"}}""")
    ])
    
    chain = prompt | llm
    
    # Stream response
    response_text = ""
    
    async for chunk in chain.astream({"topic": prompt_text, "report_org": report_org}):
        response_text += chunk.content
    
    # Parse response
    import json
    from langchain_core.utils.json import parse_json_markdown
    
    try:
        decision = parse_json_markdown(response_text)
        strategy = decision.get("strategy", "SIMPLE_RAG")
        rationale = decision.get("rationale", "")
        plan = decision.get("plan", "")
        
        log_msg = f"✅ Strategy: {strategy}\n💡 Rationale: {rationale}"
        
        return {
            "plan": json.dumps(decision),
            "udr_strategy": plan if strategy == "DYNAMIC_STRATEGY" else "",
            "logs": [log_msg]
        }
    except Exception as e:
        logger.error(f"Planning failed: {e}")
        return {
            "plan": '{"strategy": "SIMPLE_RAG"}',
            "udr_strategy": "",
            "logs": [f"⚠️ Planning error, defaulting to SIMPLE_RAG"]
        }


# ========================================
# Progressive TTD-DR Nodes (Init → Research → Finalize)
# ========================================

async def ttd_dr_init_node(state: HackathonAgentState, config: RunnableConfig):
    """
    TTD-DR Step 1: Initialize and create research plan
    Progressive update: Shows initialization
    """
    logger.info("TTD-DR: Step 1 - Initialize")
    
    ttd_dr_integration = config["configurable"].get("ttd_dr_integration")
    if not ttd_dr_integration:
        return {
            "logs": ["❌ TTD-DR integration not available"],
            "final_report": "Error: TTD-DR not configured"
        }
    
    # Create context
    from aiq_aira.research_strategy_base import ResearchContext
    context = ResearchContext(
        query=state["research_prompt"],
        collection=state.get("collection", "default"),
        search_web=state.get("search_web", True),
        user_preferences={
            "report_organization": state["report_organization"]
        }
    )
    
    step_logs = [
        "🔬 Initializing TTD-DR diffusion process...",
        "📋 Analyzing topic and creating research plan..."
    ]
    
    return {
        "ttd_dr_context": context,
        "ttd_dr_integration_ready": True,
        "logs": step_logs
    }


async def ttd_dr_research_node(state: HackathonAgentState, config: RunnableConfig):
    """
    TTD-DR Step 2: Execute iterative research with diffusion
    Progressive update: Shows research phase completion
    """
    logger.info("TTD-DR: Step 2 - Research Iterations")
    
    ttd_dr_integration = config["configurable"].get("ttd_dr_integration")
    context = state.get("ttd_dr_context")
    
    # Phase-level logs (callback system removed - not functional)
    step_logs = [
        "🔍 Executing iterative TTD-DR research...",
        "🔬 Running diffusion process with convergence tracking"
    ]
    
    # Execute TTD-DR
    try:
        result = await ttd_dr_integration.execute(context)
        
        step_logs.append("✅ Research iterations complete")
        
        return {
            "ttd_dr_result": result,
            "logs": step_logs
        }
        
    except Exception as e:
        logger.error(f"TTD-DR research error: {e}")
        step_logs.append(f"❌ TTD-DR research error: {str(e)}")
        return {
            "logs": step_logs,
            "ttd_dr_result": None
        }


async def ttd_dr_finalize_node(state: HackathonAgentState, config: RunnableConfig):
    """
    TTD-DR Step 3: Format citations and finalize
    Progressive update: Shows finalization
    """
    logger.info("TTD-DR: Step 3 - Finalize")
    
    result = state.get("ttd_dr_result")
    
    if not result or not result.success:
        error = result.error if result else "Unknown error"
        return {
            "logs": [f"❌ TTD-DR failed: {error}"],
            "final_report": f"Research failed: {error}"
        }
    
    step_logs = ["📝 Formatting citations and finalizing report..."]
    
    # Format citations (same logic as before)
    from collections import defaultdict
    rag_doc_counts = defaultdict(int)
    web_sources = []
    
    for idx, src in enumerate(result.sources, 1):
        src_type = src.get('source', src.get('type', 'unknown'))
        
        if src_type == 'rag':
            inner_citations = src.get('citations', [])
            if inner_citations:
                for inner_src in inner_citations:
                    doc_name = inner_src.get('source', f'RAG Document {idx}')
                    rag_doc_counts[doc_name] += 1
            else:
                rag_doc_counts[f'RAG Document {idx}'] += 1
        elif src_type == 'web':
            title = src.get('title', '').strip()
            url = src.get('url', 'N/A')
            if not title and url != 'N/A':
                try:
                    from urllib.parse import urlparse
                    domain = urlparse(url).netloc
                    title = domain or f'Web Source {idx}'
                except:
                    title = f'Web Source {idx}'
            elif not title:
                title = f'Web Source {idx}'
            
            if not any(ws['url'] == url for ws in web_sources):
                web_sources.append({'title': title, 'url': url})
    
    citations_formatted = []
    for doc_name, count in sorted(rag_doc_counts.items()):
        if count > 1:
            citations_formatted.append(f"- [{doc_name}] RAG Collection: {state.get('collection', 'default')} ({count} excerpts)")
        else:
            citations_formatted.append(f"- [{doc_name}] RAG Collection: {state.get('collection', 'default')}")
    
    for ws in web_sources:
        citations_formatted.append(f"- [{ws['title']}] {ws['url']}")
    
    step_logs.append("✅ TTD-DR research completed")
    
    return {
        "final_report": result.final_report,
        "citations": "\n".join(citations_formatted) if citations_formatted else "No sources available",
        "logs": step_logs,
        "ttd_dr_stage": "complete"
    }


# Keep old combined node for reference
async def ttd_dr_strategy_node_OLD(state: HackathonAgentState, config: RunnableConfig):
    """
    TTD-DR Strategy Node: Executes Test-Time Diffusion Deep Researcher.
    
    This implements Google's iterative refinement approach through multiple
    rounds of search and denoising until convergence.
    """
    import asyncio
    import sys
    from aiq_aira.research_strategy_base import ResearchContext
    
    logger.info("TTD-DR STRATEGY NODE: Starting Test-Time Diffusion research")
    
    ttd_dr_integration = config["configurable"].get("ttd_dr_integration")
    if not ttd_dr_integration:
        logger.error("TTD-DR integration not configured")
        return {
            "logs": ["❌ TTD-DR integration not available"],
            "final_report": "Error: TTD-DR not configured"
        }
    
    # Create research context
    context = ResearchContext(
        query=state["research_prompt"],
        collection=state.get("collection", "default"),
        search_web=state.get("search_web", True),
        user_preferences={
            "report_organization": state["report_organization"]
        }
    )
    
    # Track state for UI updates
    async def update_state_callback(stage_info: dict):
        """Callback to stream TTD-DR stage updates to frontend"""
        updates = {}
        
        if "stage" in stage_info:
            updates["ttd_dr_stage"] = stage_info["stage"]
        if "iteration" in stage_info:
            updates["ttd_dr_iteration"] = stage_info["iteration"]
        if "convergence" in stage_info:
            updates["ttd_dr_convergence"] = stage_info["convergence"]
        if "questions" in stage_info:
            updates["ttd_dr_questions"] = stage_info["questions"]
        if "gaps" in stage_info:
            updates["ttd_dr_gaps"] = stage_info["gaps"]
        if "improvements" in stage_info:
            updates["ttd_dr_improvements"] = stage_info["improvements"]
        if "log" in stage_info:
            updates["logs"] = [stage_info["log"]]
        
        # Stream updates (this will be captured by astream_events)
        if updates:
            logger.info(f"TTD-DR state update: {updates}")
            # State updates are handled by returning them
    
    # Execute TTD-DR with streaming updates
    try:
        # Set callback on integration
        ttd_dr_integration.state_callback = update_state_callback
        
        # Execute research
        result = await ttd_dr_integration.execute(context)
        
        if result.success:
            logger.info("✅ TTD-DR research completed successfully")
            
            # Format citations from TTD-DR sources with deduplication
            from collections import defaultdict
            
            logger.info(f"🔍 [TTD-DR] Formatting {len(result.sources)} sources for citations")
            
            # Track RAG documents and their counts
            rag_doc_counts = defaultdict(int)
            web_sources = []  # Web sources remain unique by URL
            
            for idx, src in enumerate(result.sources, 1):
                src_type = src.get('source', src.get('type', 'unknown'))
                logger.info(f"  [TTD-DR] Source {idx}: type={src_type}, keys={list(src.keys())}")
                
                if src_type == 'rag':
                    # RAG source - check for nested citations from actual documents
                    inner_citations = src.get('citations', [])
                    logger.info(f"    [TTD-DR] RAG source has {len(inner_citations)} inner citations")
                    
                    if inner_citations:
                        # Collect and count document names
                        for inner_src in inner_citations:
                            doc_name = inner_src.get('source', f'RAG Document {idx}')
                            logger.info(f"      [TTD-DR] Inner citation: {doc_name}")
                            rag_doc_counts[doc_name] += 1
                    else:
                        # Fallback if no inner citations
                        logger.info(f"    [TTD-DR] No inner citations, using fallback")
                        rag_doc_counts[f'RAG Document {idx}'] += 1
                elif src_type == 'web':
                    # Web source - deduplicate by URL
                    title = src.get('title', '').strip()
                    url = src.get('url', 'N/A')
                    # If no title, extract domain from URL as fallback
                    if not title and url != 'N/A':
                        try:
                            from urllib.parse import urlparse
                            domain = urlparse(url).netloc
                            title = domain or f'Web Source {idx}'
                        except:
                            title = f'Web Source {idx}'
                    elif not title:
                        title = f'Web Source {idx}'
                    
                    # Check if this URL was already added
                    if not any(ws['url'] == url for ws in web_sources):
                        web_sources.append({'title': title, 'url': url})
                else:
                    # Unknown source type
                    web_sources.append({
                        'title': src.get('title', f'Source {idx}'),
                        'url': src.get('url', 'N/A')
                    })
            
            # Format deduplicated citations
            citations_formatted = []
            
            # Add RAG documents (with optional count if >1)
            for doc_name, count in sorted(rag_doc_counts.items()):
                if count > 1:
                    citations_formatted.append(f"- [{doc_name}] RAG Collection: {state.get('collection', 'default')} ({count} excerpts)")
                else:
                    citations_formatted.append(f"- [{doc_name}] RAG Collection: {state.get('collection', 'default')}")
            
            # Add web sources
            for ws in web_sources:
                citations_formatted.append(f"- [{ws['title']}] {ws['url']}")
            
            # Collect all logs: progress updates + completion
            all_ttd_logs = progress_logs.copy() if progress_logs else []
            all_ttd_logs.append("✅ TTD-DR research completed")
            
            return {
                "final_report": result.final_report,
                "citations": "\n".join(citations_formatted) if citations_formatted else "No sources available",
                "logs": all_ttd_logs,
                "ttd_dr_stage": "complete"
            }
        else:
            logger.error(f"TTD-DR failed: {result.error}")
            return {
                "logs": [f"❌ TTD-DR error: {result.error}"],
                "final_report": f"Research failed: {result.error}"
            }
            
    except Exception as e:
        logger.error(f"TTD-DR execution error: {e}")
        return {
            "logs": [f"❌ TTD-DR execution error: {str(e)}"],
            "final_report": f"Error during research: {str(e)}"
        }


# ========================================
# Progressive UDR Nodes (Compile → Validate → Execute)
# ========================================

async def udr_prepare_node(state: HackathonAgentState, config: RunnableConfig):
    """
    UDR Step 1: Prepare context and extract strategy
    Progressive update: Shows preparation phase
    """
    import sys
    logger.info("UDR: Step 1 - Prepare")
    
    # Get UDR integration
    udr_integration = config["configurable"].get("udr_integration")
    if not udr_integration:
        error_msg = "UDR integration not configured"
        logger.error(f"❌ {error_msg}")
        return {
            "udr_result": {"success": False, "error": error_msg},
            "logs": [f"❌ {error_msg}"]
        }
    
    # Extract strategy from plan
    strategy = state.get("udr_strategy", "")
    if isinstance(strategy, dict):
        import json
        strategy = json.dumps(strategy, indent=2)
    
    # Build context
    context = {
        "topic": state["research_prompt"],
        "report_organization": state["report_organization"],
        "collection": state.get("collection", ""),
        "search_web": state.get("search_web", True)
    }
    
    step_logs = [
        "🎯 Preparing UDR execution context...",
        f"📋 Strategy plan extracted ({len(str(strategy))} chars)"
    ]
    
    return {
        "udr_context": context,
        "udr_strategy_text": strategy,
        "logs": step_logs
    }


async def udr_compile_validate_node(state: HackathonAgentState, config: RunnableConfig):
    """
    UDR Step 2: Compile and validate strategy code
    Progressive update: Shows compilation and validation
    """
    logger.info("UDR: Step 2 - Compile & Validate")
    
    udr_integration = config["configurable"].get("udr_integration")
    strategy = state.get("udr_strategy_text", "")
    
    step_logs = ["🔧 Compiling natural language plan to executable Python code..."]
    
    try:
        # Compile
        compiled_code = await udr_integration.compiler.compile_strategy(strategy)
        step_logs.append("✅ Code compilation successful")
        
        # Validate
        step_logs.append("🔍 Validating generated code for safety...")
        is_valid, validation_error = udr_integration.compiler.validate_generated_code(compiled_code)
        
        if not is_valid:
            step_logs.append(f"❌ Validation failed: {validation_error}")
            return {
                "udr_result": {"success": False, "error": validation_error},
                "logs": step_logs
            }
        
        step_logs.append("✅ Code validation passed - safe to execute")
        
        return {
            "udr_compiled_code": compiled_code,
            "logs": step_logs
        }
        
    except Exception as e:
        step_logs.append(f"❌ Compilation failed: {str(e)}")
        return {
            "udr_result": {"success": False, "error": str(e)},
            "logs": step_logs
        }


async def udr_execute_node(state: HackathonAgentState, config: RunnableConfig):
    """
    UDR Step 3: Execute compiled strategy and collect results
    Progressive update: Shows execution phase with tool calls
    """
    import asyncio
    logger.info("UDR: Step 3 - Execute")
    
    udr_integration = config["configurable"].get("udr_integration")
    compiled_code = state.get("udr_compiled_code", "")
    context = state.get("udr_context", {})
    
    step_logs = ["⚙️ Executing compiled strategy code..."]
    
    try:
        result = await asyncio.wait_for(
            udr_integration.executor.execute_strategy(
                compiled_code=compiled_code,
                context=context
            ),
            timeout=300.0
        )
        
        if result.success:
            # Add tool call logs
            if result.execution_log:
                step_logs.extend(result.execution_log)
            
            step_logs.append("✅ UDR strategy execution complete")
            
            # Format citations (same logic as before)
            from collections import defaultdict
            rag_doc_counts = defaultdict(int)
            web_sources = []
            
            for idx, src in enumerate(result.sources, 1):
                src_type = src.get('source', src.get('type', 'unknown'))
                
                if src_type == 'rag':
                    inner_citations = src.get('citations', [])
                    if inner_citations:
                        for inner_src in inner_citations:
                            doc_name = inner_src.get('source', f'RAG Document {idx}')
                            rag_doc_counts[doc_name] += 1
                    else:
                        rag_doc_counts[f'RAG Document {idx}'] += 1
                elif src_type == 'web':
                    title = src.get('title', '').strip()
                    url = src.get('url', 'N/A')
                    if not title and url != 'N/A':
                        try:
                            from urllib.parse import urlparse
                            domain = urlparse(url).netloc
                            title = domain or f'Web Source {idx}'
                        except:
                            title = f'Web Source {idx}'
                    elif not title:
                        title = f'Web Source {idx}'
                    
                    if not any(ws['url'] == url for ws in web_sources):
                        web_sources.append({'title': title, 'url': url})
            
            citations_formatted = []
            for doc_name, count in sorted(rag_doc_counts.items()):
                if count > 1:
                    citations_formatted.append(f"- [{doc_name}] RAG Collection: {state.get('collection', 'default')} ({count} excerpts)")
                else:
                    citations_formatted.append(f"- [{doc_name}] RAG Collection: {state.get('collection', 'default')}")
            
            for ws in web_sources:
                citations_formatted.append(f"- [{ws['title']}] {ws['url']}")
            
            return {
                "udr_result": {
                    "success": True,
                    "report": result.synthesized_report,
                    "sources": result.sources
                },
                "running_summary": result.synthesized_report,
                "citations": "\n".join(citations_formatted) if citations_formatted else "No sources available",
                "logs": step_logs
            }
        else:
            step_logs.append(f"❌ Execution failed: {result.error}")
            return {
                "udr_result": {"success": False, "error": result.error},
                "logs": step_logs
            }
            
    except asyncio.TimeoutError:
        step_logs.append("❌ Execution timed out after 5 minutes")
        return {
            "udr_result": {"success": False, "error": "Timeout"},
            "logs": step_logs
        }
    except Exception as e:
        step_logs.append(f"❌ Execution error: {str(e)}")
        return {
            "udr_result": {"success": False, "error": str(e)},
            "logs": step_logs
        }


# Keep old function for reference but rename to avoid conflicts
async def udr_execute_strategy_node_OLD(state: HackathonAgentState, config: RunnableConfig):
    """
    UDR Dynamic Strategy Node: Executes the UDR strategy-as-code engine.
    
    This is the core innovation - the agent dynamically generates and executes
    a custom research strategy on-the-fly.
    
    NOTE: Removed 'writer' parameter to fix LangGraph checkpointer compatibility issue.
    """
    import asyncio
    import sys
    
    # CRITICAL DEBUG: Use print() to ensure output appears
    print("=" * 80, flush=True, file=sys.stderr)
    print("🔴 DYNAMIC STRATEGY NODE: Starting UDR execution", flush=True, file=sys.stderr)
    print("=" * 80, flush=True, file=sys.stderr)
    
    logger.info("=" * 80)
    logger.info("DYNAMIC STRATEGY NODE: Starting UDR execution")
    logger.info("=" * 80)
    
    # Get UDR integration from config
    print("🔵 Attempting to get udr_integration from config...", flush=True, file=sys.stderr)
    udr_integration: UDRIntegration = config["configurable"].get("udr_integration")
    print(f"🔵 udr_integration: {type(udr_integration)}", flush=True, file=sys.stderr)
    
    if not udr_integration:
        error_msg = "UDR integration not configured"
        logger.error(f"❌ {error_msg}")
        print(f"❌ {error_msg}", flush=True, file=sys.stderr)
        return {
            "udr_result": {"success": False, "error": error_msg},
            "logs": [f"❌ {error_msg}"]
        }
    
    # Execute UDR
    print("🔵 Getting strategy from state...", flush=True, file=sys.stderr)
    strategy = state.get("udr_strategy", "")
    print(f"🔵 strategy length: {len(str(strategy))}", flush=True, file=sys.stderr)
    
    # Convert dict plan to string if needed (LLM sometimes returns structured JSON)
    if isinstance(strategy, dict):
        import json
        strategy = json.dumps(strategy, indent=2)
    
    print("🔵 Building context...", flush=True, file=sys.stderr)
    context = {
        "topic": state["research_prompt"],
        "report_organization": state["report_organization"],
        "collection": state.get("collection", ""),
        "search_web": state.get("search_web", True)
    }
    print(f"🔵 Context built: topic={context['topic'][:50]}...", flush=True, file=sys.stderr)
    
    logger.info("📝 Starting UDR compilation...")
    print("🔵 About to call execute_dynamic_strategy...", flush=True, file=sys.stderr)
    
    try:
        # Add timeout protection for UDR execution (5 minutes max)
        logger.info("⏰ Starting UDR execution with 5-minute timeout...")
        print("⏰ Calling asyncio.wait_for...", flush=True, file=sys.stderr)
        result: UDRExecutionResult = await asyncio.wait_for(
            udr_integration.execute_dynamic_strategy(
                natural_language_plan=strategy,
                context=context
            ),
            timeout=300.0  # 5 minutes
        )
        print(f"✅ execute_dynamic_strategy returned! Success: {result.success}", flush=True, file=sys.stderr)
        logger.info(f"✅ UDR execution completed. Success: {result.success}")
    except asyncio.TimeoutError:
        error_msg = "UDR execution timed out after 5 minutes"
        logger.error(f"❌ {error_msg}")
        return {
            "udr_result": {"success": False, "error": error_msg},
            "running_summary": f"Error: {error_msg}",
            "logs": [f"❌ {error_msg}"]
        }
    except Exception as e:
        error_msg = f"UDR execution exception: {str(e)}"
        logger.error(f"❌ {error_msg}", exc_info=True)
        return {
            "udr_result": {"success": False, "error": str(e)},
            "running_summary": f"Error: {str(e)}",
            "logs": [f"❌ {error_msg}"]
        }
    
    if result.success:
        logger.info(f"✅ UDR SUCCESS: Report length: {len(result.synthesized_report)}, Sources: {len(result.sources)}")
        
        # Format citations with deduplication
        import sys
        from collections import defaultdict
        
        print(f"🔍 [UDR] Formatting {len(result.sources)} sources for citations", flush=True, file=sys.stderr)
        logger.info(f"🔍 Formatting {len(result.sources)} sources for citations")
        
        # Track RAG documents and their counts
        rag_doc_counts = defaultdict(int)
        web_sources = []  # Web sources remain unique by URL
        
        for idx, src in enumerate(result.sources, 1):
            src_type = src.get('source', src.get('type', 'unknown'))
            print(f"  [UDR] Source {idx}: type={src_type}, keys={list(src.keys())}", flush=True, file=sys.stderr)
            logger.info(f"  Source {idx}: type={src_type}, keys={list(src.keys())}")
            
            if src_type == 'rag':
                # RAG source - check for nested citations from actual documents
                inner_citations = src.get('citations', [])
                print(f"    [UDR] RAG source has {len(inner_citations)} inner citations", flush=True, file=sys.stderr)
                logger.info(f"    RAG source has {len(inner_citations)} inner citations")
                
                if inner_citations:
                    # Collect and count document names
                    for inner_src in inner_citations:
                        doc_name = inner_src.get('source', f'RAG Document {idx}')
                        print(f"      [UDR] Inner citation: {doc_name}", flush=True, file=sys.stderr)
                        rag_doc_counts[doc_name] += 1
                else:
                    # Fallback if no inner citations
                    print(f"    [UDR] No inner citations, using fallback", flush=True, file=sys.stderr)
                    rag_doc_counts[f'RAG Document {idx}'] += 1
            elif src_type == 'web':
                # Web source - deduplicate by URL
                title = src.get('title', '').strip()
                url = src.get('url', 'N/A')
                # If no title, extract domain from URL as fallback
                if not title and url != 'N/A':
                    try:
                        from urllib.parse import urlparse
                        domain = urlparse(url).netloc
                        title = domain or f'Web Source {idx}'
                    except:
                        title = f'Web Source {idx}'
                elif not title:
                    title = f'Web Source {idx}'
                
                # Check if this URL was already added
                if not any(ws['url'] == url for ws in web_sources):
                    web_sources.append({'title': title, 'url': url})
            else:
                # Unknown source type
                web_sources.append({
                    'title': src.get('title', f'Source {idx}'),
                    'url': src.get('url', 'N/A')
                })
        
        # Format deduplicated citations
        citations_formatted = []
        
        # Add RAG documents (with optional count if >1)
        for doc_name, count in sorted(rag_doc_counts.items()):
            if count > 1:
                citations_formatted.append(f"- [{doc_name}] RAG Collection: {state.get('collection', 'default')} ({count} excerpts)")
            else:
                citations_formatted.append(f"- [{doc_name}] RAG Collection: {state.get('collection', 'default')}")
        
        # Add web sources
        for ws in web_sources:
            citations_formatted.append(f"- [{ws['title']}] {ws['url']}")
        
        citations_formatted = "\n".join(citations_formatted) if citations_formatted else "No sources available"
        
        # Collect all logs: UDR provides complete orchestration + tool call logs
        all_logs = []
        if result.execution_log:
            # UDR integration returns complete log including:
            # - Compilation, validation, execution steps
            # - Tool calls (search_rag, search_web, synthesize_findings)
            all_logs.extend(result.execution_log)
        # Add completion message
        all_logs.append("✅ UDR strategy execution complete")
        
        return_value = {
            "udr_result": {
                "success": True,
                "report": result.synthesized_report,
                "sources": result.sources
            },
            "running_summary": result.synthesized_report,
            "citations": citations_formatted,
            "logs": all_logs
        }
        logger.info("=" * 80)
        logger.info("DYNAMIC STRATEGY NODE: Returning success result")
        logger.info("=" * 80)
        return return_value
    else:
        error_msg = f"UDR execution failed: {result.error}"
        logger.error(f"❌ {error_msg}")
        return_value = {
            "udr_result": {"success": False, "error": result.error},
            "running_summary": f"UDR Error: {result.error}",
            "logs": [f"❌ {error_msg}"]
        }
        logger.info("=" * 80)
        logger.info("DYNAMIC STRATEGY NODE: Returning error result")
        logger.info("=" * 80)
        return return_value


async def generate_queries_node(state: HackathonAgentState, config: RunnableConfig):
    """
    Step 1 of Simple RAG: Generate research queries
    Progressive update: Logs appear immediately when this step completes
    """
    logger.info("SIMPLE RAG: Step 1 - Generate Queries")
    
    def noop_writer(data):
        pass
    
    # Execute query generation
    query_result = await generate_query(state, config, noop_writer)
    
    # Create progressive logs for this step
    num_queries = len(query_result.get('queries', []))
    step_logs = [
        "🎯 Analyzing topic and generating research queries...",
        f"📝 Generated {num_queries} targeted research questions"
    ]
    
    return {
        **query_result,
        "logs": step_logs
    }


async def search_sources_node(state: HackathonAgentState, config: RunnableConfig):
    """
    Step 2 of Simple RAG: Search RAG and web sources
    Progressive update: Logs appear when searches complete
    """
    logger.info("SIMPLE RAG: Step 2 - Search Sources")
    
    def noop_writer(data):
        pass
    
    # Create progressive logs for this step
    collection = state.get('collection', '')
    search_web = state.get('search_web', True)
    num_queries = len(state.get('queries', []))
    
    step_logs = []
    if collection:
        step_logs.append(f"🔍 Searching RAG collection: {collection}")
    if search_web:
        step_logs.append(f"🌐 Searching web sources for each query")
    
    # Execute search
    research_result = await web_research(state, config, noop_writer)
    
    step_logs.append(f"✅ Completed searches for {num_queries} queries")
    
    return {
        **research_result,
        "logs": step_logs
    }


async def synthesize_report_node(state: HackathonAgentState, config: RunnableConfig):
    """
    Step 3 of Simple RAG: Synthesize final report
    Progressive update: Logs appear when synthesis completes
    """
    logger.info("SIMPLE RAG: Step 3 - Synthesize Report")
    
    def noop_writer(data):
        pass
    
    # Create progressive logs for this step
    step_logs = [
        "📄 Synthesizing comprehensive report from sources...",
        "✅ Simple RAG pipeline complete"
    ]
    
    # Execute synthesis
    summary_result = await summarize_sources(state, config, noop_writer)
    
    return {
        **summary_result,
        "logs": step_logs
    }


async def final_report_node(state: HackathonAgentState, config: RunnableConfig):
    """
    Final report node: Formats and finalizes the report with citations.
    
    This is called regardless of which path (UDR or RAG) was taken.
    
    NOTE: Removed 'writer' parameter to fix LangGraph checkpointer compatibility issue.
    """
    logger.info("FINAL REPORT NODE: Finalizing report")
    
    # Create a no-op writer for AI-Q nodes that still expect it
    def noop_writer(data):
        pass
    
    # Reuse AI-Q's finalization logic
    finalize_result = await finalize_summary(state, config, noop_writer)
    
    final_report = finalize_result.get("final_report", state.get("running_summary", ""))
    
    return {
        "final_report": final_report,
        "logs": ["🎉 Research complete! Report ready for download."]
    }


# ========================================
# Routing Logic
# ========================================

def route_after_planner(state: HackathonAgentState) -> Literal["udr_strategy", "ttd_dr_strategy", "simple_rag"]:
    """
    Routing function: Decides which path to take after planning.
    Now supports routing between UDR and TTD-DR based on user selection.
    """
    import logging
    logger = logging.getLogger("uvicorn")
    
    plan = state.get("plan", "")
    selected_strategy = state.get("strategy", "udr")  # User-selected: 'udr' or 'ttd_dr'
    logger.info(f"🧭 ROUTING: plan field = {plan[:200] if plan else 'EMPTY'}...")
    logger.info(f"🧭 ROUTING: selected_strategy = {selected_strategy}")
    
    try:
        import json
        decision = json.loads(plan)
        strategy = decision.get("strategy", "SIMPLE_RAG")
        logger.info(f"🧭 ROUTING: Parsed strategy = {strategy}")
        
        if strategy == "DYNAMIC_STRATEGY":
            # Route to selected dynamic strategy
            if selected_strategy == "ttd_dr":
                logger.info("🧭 ROUTING: → ttd_dr_strategy node")
                return "ttd_dr_strategy"
            else:
                logger.info("🧭 ROUTING: → udr_strategy node (dynamic_strategy)")
                return "udr_strategy"
        else:
            logger.info("🧭 ROUTING: → simple_rag node")
            return "simple_rag"
    except Exception as e:
        logger.error(f"🧭 ROUTING ERROR: {e}, defaulting to simple_rag")
        return "simple_rag"


# ========================================
# Graph Construction
# ========================================

def create_hackathon_agent_graph() -> StateGraph:
    """
    Creates the enhanced AI-Q + UDR LangGraph for the hackathon.
    
    Graph structure:
    START → Planner → [Dynamic Strategy OR Simple RAG] → Final Report → END
    
    Returns:
        Compiled StateGraph ready for execution
    """
    logger.info("Creating hackathon agent graph")
    
    # Initialize graph with state schema
    workflow = StateGraph(HackathonAgentState)
    
    # Add nodes
    workflow.add_node("planner", planner_node)
    
    # UDR broken into 3 progressive nodes: prepare → compile/validate → execute
    workflow.add_node("udr_prepare", udr_prepare_node)
    workflow.add_node("udr_compile_validate", udr_compile_validate_node)
    workflow.add_node("udr_execute", udr_execute_node)
    
    # TTD-DR broken into 3 progressive nodes: init → research → finalize
    workflow.add_node("ttd_dr_init", ttd_dr_init_node)
    workflow.add_node("ttd_dr_research", ttd_dr_research_node)
    workflow.add_node("ttd_dr_finalize", ttd_dr_finalize_node)
    
    # Simple RAG broken into 3 progressive nodes: queries → search → synthesize
    workflow.add_node("generate_queries", generate_queries_node)
    workflow.add_node("search_sources", search_sources_node)
    workflow.add_node("synthesize_report", synthesize_report_node)
    
    workflow.add_node("final_report", final_report_node)
    
    # Set entry point
    workflow.set_entry_point("planner")
    
    # Add conditional routing after planner
    workflow.add_conditional_edges(
        "planner",
        route_after_planner,
        {
            "udr_strategy": "udr_prepare",  # ← Route to first UDR step
            "ttd_dr_strategy": "ttd_dr_init",  # ← Route to first TTD-DR step
            "simple_rag": "generate_queries"  # ← Route to first SIMPLE_RAG step
        }
    )
    
    # UDR path: 3 sequential nodes for progressive updates
    workflow.add_edge("udr_prepare", "udr_compile_validate")
    workflow.add_edge("udr_compile_validate", "udr_execute")
    workflow.add_edge("udr_execute", "final_report")
    
    # TTD-DR path: 3 sequential nodes for progressive updates
    workflow.add_edge("ttd_dr_init", "ttd_dr_research")
    workflow.add_edge("ttd_dr_research", "ttd_dr_finalize")
    workflow.add_edge("ttd_dr_finalize", "final_report")
    
    # Simple RAG path: 3 sequential nodes for progressive updates
    workflow.add_edge("generate_queries", "search_sources")
    workflow.add_edge("search_sources", "synthesize_report")
    workflow.add_edge("synthesize_report", "final_report")
    
    # Final report goes to END
    workflow.add_edge("final_report", END)
    
    # Re-enable checkpointer for proper async node tracking
    # Without it, astream() completes before async nodes finish
    from langgraph.checkpoint.memory import MemorySaver
    compiled_graph = workflow.compile(checkpointer=MemorySaver())
    
    logger.info("Hackathon agent graph compiled WITH checkpointer for proper streaming")
    return compiled_graph


# ========================================
# Helper: Create Agent with Config
# ========================================

def create_configured_agent(
    reasoning_llm: BaseChatModel,
    instruct_llm: BaseChatModel,
    udr_integration: UDRIntegration,
    ttd_dr_integration: 'TTDDRIntegration',
    rag_url: str,
    num_reflections: int = 2
) -> tuple:
    """
    Creates a fully configured hackathon agent with all dependencies.
    
    Args:
        reasoning_llm: LLM for planning/reasoning (Nemotron)
        instruct_llm: LLM for writing (Llama 3.3)
        udr_integration: UDR integration instance
        ttd_dr_integration: TTD-DR integration instance
        rag_url: RAG service URL
        num_reflections: Number of reflection loops
        
    Returns:
        Tuple of (compiled_graph, default_config)
    """
    graph = create_hackathon_agent_graph()
    
    default_config = {
        "configurable": {
            "llm": reasoning_llm,
            "instruct_llm": instruct_llm,
            "udr_integration": udr_integration,
            "ttd_dr_integration": ttd_dr_integration,
            "rag_url": rag_url,
            "num_reflections": num_reflections,
            "number_of_queries": 3,
            "search_web": True
        }
    }
    
    return graph, default_config

