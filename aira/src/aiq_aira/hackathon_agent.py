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
Enhanced AI-Q Agent with UDF Integration for Hackathon

This module implements the two-level agentic system described in the design plan:
- Level 1: AI-Q agent (orchestrator) built on LangGraph
- Level 2: UDF dynamic strategy executor (called as a tool by AI-Q)

The agent state is designed to be streamed to CopilotKit for real-time UI visualization.
"""

import logging
import operator
from typing import List, Annotated, TypedDict, Literal
from dataclasses import dataclass, field

from langgraph.graph import StateGraph, END
from langgraph.types import StreamWriter
from langchain_core.runnables import RunnableConfig
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.language_models import BaseChatModel

from aiq_aira.schema import GeneratedQuery
from aiq_aira.udf_integration import UDFIntegration, UDFExecutionResult
from aiq_aira.nodes import generate_query, web_research, summarize_sources, reflect_on_summary, finalize_summary

logger = logging.getLogger(__name__)


# ========================================
# Enhanced Agent State for CopilotKit
# ========================================

class HackathonAgentState(TypedDict):
    """
    State object for the enhanced AI-Q + UDF agent.
    
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
    
    # Planning phase
    plan: str
    queries: List[GeneratedQuery]
    
    # Execution phase
    web_research_results: List[str]
    citations: str
    running_summary: str
    
    # UDF dynamic strategy phase
    udf_strategy: str
    udf_result: dict
    
    # Final output
    final_report: str
    
    # Logs for CopilotKit visualization (append-only)
    logs: Annotated[List[str], operator.add]


# ========================================
# Agent Nodes
# ========================================

async def planner_node(state: HackathonAgentState, config: RunnableConfig, writer: StreamWriter):
    """
    Planner node: Analyzes the research prompt and decides the strategy.
    
    Decision logic:
    - Complex, multi-domain research → Use UDF dynamic strategy
    - Straightforward queries → Use standard AI-Q RAG pipeline
    """
    logger.info("PLANNER NODE: Analyzing research prompt")
    
    llm = config["configurable"].get("llm")
    prompt_text = state["research_prompt"]
    report_org = state["report_organization"]
    
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
    writer({"logs": ["🤔 Analyzing research complexity..."]})
    
    async for chunk in chain.astream({"topic": prompt_text, "report_org": report_org}):
        response_text += chunk.content
        writer({"logs": [chunk.content]})
    
    # Parse response
    import json
    from langchain_core.utils.json import parse_json_markdown
    
    try:
        decision = parse_json_markdown(response_text)
        strategy = decision.get("strategy", "SIMPLE_RAG")
        rationale = decision.get("rationale", "")
        plan = decision.get("plan", "")
        
        log_msg = f"✅ Strategy: {strategy}\n💡 Rationale: {rationale}"
        writer({"logs": [log_msg]})
        
        return {
            "plan": json.dumps(decision),
            "udf_strategy": plan if strategy == "DYNAMIC_STRATEGY" else "",
            "logs": [log_msg]
        }
    except Exception as e:
        logger.error(f"Planning failed: {e}")
        return {
            "plan": '{"strategy": "SIMPLE_RAG"}',
            "udf_strategy": "",
            "logs": [f"⚠️ Planning error, defaulting to SIMPLE_RAG"]
        }


async def dynamic_strategy_node(state: HackathonAgentState, config: RunnableConfig, writer: StreamWriter):
    """
    UDF Dynamic Strategy Node: Executes the UDF strategy-as-code engine.
    
    This is the core innovation - the agent dynamically generates and executes
    a custom research strategy on-the-fly.
    """
    logger.info("DYNAMIC STRATEGY NODE: Executing UDF")
    
    writer({"logs": ["🚀 Executing dynamic UDF strategy..."]})
    
    # Get UDF integration from config
    udf_integration: UDFIntegration = config["configurable"].get("udf_integration")
    
    if not udf_integration:
        error_msg = "UDF integration not configured"
        logger.error(error_msg)
        return {
            "udf_result": {"success": False, "error": error_msg},
            "logs": [f"❌ {error_msg}"]
        }
    
    # Execute UDF
    strategy = state.get("udf_strategy", "")
    
    # Convert dict plan to string if needed (LLM sometimes returns structured JSON)
    if isinstance(strategy, dict):
        import json
        strategy = json.dumps(strategy, indent=2)
    
    context = {
        "topic": state["research_prompt"],
        "report_organization": state["report_organization"],
        "collection": state.get("collection", ""),
        "search_web": state.get("search_web", True)
    }
    
    writer({"logs": ["📝 Compiling strategy to executable code..."]})
    
    result: UDFExecutionResult = await udf_integration.execute_dynamic_strategy(
        natural_language_plan=strategy,
        context=context
    )
    
    if result.success:
        writer({"logs": [
            "✅ UDF execution completed successfully",
            f"📊 Synthesized report ({len(result.synthesized_report)} chars)",
            f"📚 Retrieved {len(result.sources)} sources"
        ]})
        
        # Format citations
        citations_formatted = "\n".join([
            f"- [{src.get('source', 'unknown')}] {src.get('url', src.get('title', 'N/A'))}"
            for src in result.sources
        ])
        
        return {
            "udf_result": {
                "success": True,
                "report": result.synthesized_report,
                "sources": result.sources
            },
            "running_summary": result.synthesized_report,
            "citations": citations_formatted,
            "logs": ["✅ UDF strategy execution complete"]
        }
    else:
        error_msg = f"UDF execution failed: {result.error}"
        writer({"logs": [f"❌ {error_msg}"]})
        return {
            "udf_result": {"success": False, "error": result.error},
            "logs": [f"❌ {error_msg}"]
        }


async def simple_rag_pipeline(state: HackathonAgentState, config: RunnableConfig, writer: StreamWriter):
    """
    Simple RAG pipeline: Uses the standard AI-Q query → research → summarize flow.
    
    This reuses the existing AI-Q nodes.
    """
    logger.info("SIMPLE RAG PIPELINE: Running standard AI-Q flow")
    
    writer({"logs": ["📋 Generating research queries..."]})
    
    # Step 1: Generate queries (reuse AI-Q node)
    query_result = await generate_query(state, config, writer)
    state.update(query_result)
    
    writer({"logs": [f"✅ Generated {len(state.get('queries', []))} queries"]})
    
    # Step 2: Web research (reuse AI-Q node)
    writer({"logs": ["🔍 Conducting research..."]})
    research_result = await web_research(state, config, writer)
    state.update(research_result)
    
    writer({"logs": ["✅ Research complete"]})
    
    # Step 3: Summarize (reuse AI-Q node)
    writer({"logs": ["📝 Synthesizing report..."]})
    summary_result = await summarize_sources(state, config, writer)
    state.update(summary_result)
    
    writer({"logs": ["✅ Report synthesized"]})
    
    return {
        "running_summary": state.get("running_summary", ""),
        "citations": state.get("citations", ""),
        "logs": ["✅ Simple RAG pipeline complete"]
    }


async def final_report_node(state: HackathonAgentState, config: RunnableConfig, writer: StreamWriter):
    """
    Final report node: Formats and finalizes the report with citations.
    
    This is called regardless of which path (UDF or RAG) was taken.
    """
    logger.info("FINAL REPORT NODE: Finalizing report")
    
    writer({"logs": ["📄 Finalizing report with citations..."]})
    
    # Reuse AI-Q's finalization logic
    finalize_result = await finalize_summary(state, config, writer)
    
    final_report = finalize_result.get("final_report", state.get("running_summary", ""))
    
    writer({"logs": ["✅ Report finalized and ready!"]})
    
    return {
        "final_report": final_report,
        "logs": ["🎉 Research complete! Report ready for download."]
    }


# ========================================
# Routing Logic
# ========================================

def route_after_planner(state: HackathonAgentState) -> Literal["dynamic_strategy", "simple_rag"]:
    """
    Routing function: Decides which path to take after planning.
    """
    import logging
    logger = logging.getLogger("uvicorn")
    
    plan = state.get("plan", "")
    logger.info(f"🧭 ROUTING: plan field = {plan[:200] if plan else 'EMPTY'}...")
    
    try:
        import json
        decision = json.loads(plan)
        strategy = decision.get("strategy", "SIMPLE_RAG")
        logger.info(f"🧭 ROUTING: Parsed strategy = {strategy}")
        
        if strategy == "DYNAMIC_STRATEGY":
            logger.info("🧭 ROUTING: → dynamic_strategy node")
            return "dynamic_strategy"
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
    Creates the enhanced AI-Q + UDF LangGraph for the hackathon.
    
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
    workflow.add_node("dynamic_strategy", dynamic_strategy_node)
    workflow.add_node("simple_rag", simple_rag_pipeline)
    workflow.add_node("final_report", final_report_node)
    
    # Set entry point
    workflow.set_entry_point("planner")
    
    # Add conditional routing after planner
    workflow.add_conditional_edges(
        "planner",
        route_after_planner,
        {
            "dynamic_strategy": "dynamic_strategy",
            "simple_rag": "simple_rag"
        }
    )
    
    # Both paths converge to final report
    workflow.add_edge("dynamic_strategy", "final_report")
    workflow.add_edge("simple_rag", "final_report")
    
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
    udf_integration: UDFIntegration,
    rag_url: str,
    num_reflections: int = 2
) -> tuple:
    """
    Creates a fully configured hackathon agent with all dependencies.
    
    Args:
        reasoning_llm: LLM for planning/reasoning (Nemotron)
        instruct_llm: LLM for writing (Llama 3.3)
        udf_integration: UDF integration instance
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
            "udf_integration": udf_integration,
            "rag_url": rag_url,
            "num_reflections": num_reflections,
            "number_of_queries": 3,
            "search_web": True
        }
    }
    
    return graph, default_config

