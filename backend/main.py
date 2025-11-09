# SPDX-FileCopyrightText: Copyright (c) 2025 Research_as_a_Code Project
# SPDX-License-Identifier: Apache-2.0

"""
FastAPI Backend with CopilotKit Integration

This is the main backend service that:
1. Serves the AI-Q + UDF agent via REST API
2. Integrates CopilotKit SDK for real-time state streaming to the frontend
3. Provides endpoints for research generation with agentic flow visualization
"""

import os
import uvicorn
import logging
from typing import Dict, Any, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

# CopilotKit SDK
try:
    from copilotkit import CopilotKit
    from copilotkit.langchain import copilotkit_customize_config
    COPILOTKIT_AVAILABLE = True
except ImportError:
    COPILOTKIT_AVAILABLE = False
    logging.warning("CopilotKit SDK not installed. Install with: pip install copilotkit")

# AI-Q and UDF imports
from aiq_aira.hackathon_agent import create_configured_agent, HackathonAgentState
from aiq_aira.udf_integration import UDFIntegration
from langchain_openai import ChatOpenAI

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ========================================
# Configuration
# ========================================

class Config:
    """Application configuration from environment variables."""
    
    # LLM Endpoints (from design plan Table 1)
    NEMOTRON_NIM_URL = os.getenv("NEMOTRON_NIM_URL", "http://nemotron-nano.nim.svc.cluster.local:8000")
    INSTRUCT_LLM_URL = os.getenv("INSTRUCT_LLM_URL", "http://instruct-llm.nim.svc.cluster.local:8000")
    EMBEDDING_NIM_URL = os.getenv("EMBEDDING_NIM_URL", "http://embedding-service.nim.svc.cluster.local:8000")
    
    # RAG Service
    RAG_SERVER_URL = os.getenv("RAG_SERVER_URL", "http://rag-server:8081/v1")
    
    # Tavily API Key (for web search)
    TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
    
    # NGC API Key (for NIM authentication if needed)
    NGC_API_KEY = os.getenv("NGC_API_KEY", "not-needed")
    
    # Model names (Hackathon-specified Nemotron-Nano-8B)
    NEMOTRON_MODEL = "nvidia/llama-3.1-nemotron-nano-8b-v1"
    INSTRUCT_MODEL = "nvidia/llama-3.1-nemotron-nano-8b-v1"


# Global agent instance
agent_graph = None
agent_config = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize agent on startup."""
    global agent_graph, agent_config
    
    logger.info("Initializing AI-Q + UDF Agent...")
    
    # Create LLM instances
    reasoning_llm = ChatOpenAI(
        base_url=f"{Config.NEMOTRON_NIM_URL}/v1",
        api_key=Config.NGC_API_KEY,
        model=Config.NEMOTRON_MODEL,
        temperature=0.5
    )
    
    instruct_llm = ChatOpenAI(
        base_url=f"{Config.INSTRUCT_LLM_URL}/v1",
        api_key=Config.NGC_API_KEY,
        model=Config.INSTRUCT_MODEL,
        temperature=0.0
    )
    
    # Create UDF integration
    udf_integration = UDFIntegration(
        compiler_llm=reasoning_llm,
        rag_url=Config.RAG_SERVER_URL,
        nemotron_nim_url=Config.NEMOTRON_NIM_URL,
        embedding_nim_url=Config.EMBEDDING_NIM_URL,
        tavily_api_key=Config.TAVILY_API_KEY
    )
    
    # Create configured agent
    agent_graph, agent_config = create_configured_agent(
        reasoning_llm=reasoning_llm,
        instruct_llm=instruct_llm,
        udf_integration=udf_integration,
        rag_url=Config.RAG_SERVER_URL,
        num_reflections=2
    )
    
    logger.info("✅ AI-Q + UDF Agent initialized successfully")
    
    yield
    
    logger.info("Shutting down...")


# ========================================
# FastAPI App
# ========================================

app = FastAPI(
    title="AI-Q Research Assistant with UDF",
    description="Enhanced NVIDIA AI-Q agent with Universal Deep Research for the AWS & NVIDIA Hackathon",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ========================================
# Request/Response Models
# ========================================

class ResearchRequest(BaseModel):
    """Request model for research generation."""
    topic: str = Field(..., description="Research topic or question")
    report_organization: str = Field(
        ..., 
        description="Desired report structure (e.g., 'Create a report with introduction, analysis, and conclusion')"
    )
    collection: str = Field(
        default="",
        description="Optional RAG collection to search"
    )
    search_web: bool = Field(
        default=True,
        description="Whether to include web search"
    )


class ResearchResponse(BaseModel):
    """Response model for research generation."""
    final_report: str
    citations: str
    logs: list[str]
    execution_path: str  # "UDF" or "Simple RAG"


# ========================================
# API Endpoints
# ========================================

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "AI-Q Research Assistant with UDF",
        "copilotkit_enabled": COPILOTKIT_AVAILABLE
    }


@app.post("/research", response_model=ResearchResponse)
async def generate_research(request: ResearchRequest):
    """
    Generate research report using AI-Q + UDF agent.
    
    This endpoint runs the agent synchronously and returns the complete result.
    For real-time streaming, use the /copilotkit endpoint.
    """
    if not agent_graph:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    logger.info(f"Research request: {request.topic[:50]}...")
    
    # Prepare initial state
    initial_state: HackathonAgentState = {
        "research_prompt": request.topic,
        "report_organization": request.report_organization,
        "collection": request.collection,
        "search_web": request.search_web,
        "plan": "",
        "queries": [],
        "web_research_results": [],
        "citations": "",
        "running_summary": "",
        "udf_strategy": "",
        "udf_result": {},
        "final_report": "",
        "logs": []
    }
    
    # Run agent
    try:
        final_state = await agent_graph.ainvoke(initial_state, agent_config)
        
        # Determine which path was taken
        execution_path = "UDF" if final_state.get("udf_result", {}).get("success") else "Simple RAG"
        
        return ResearchResponse(
            final_report=final_state.get("final_report", ""),
            citations=final_state.get("citations", ""),
            logs=final_state.get("logs", []),
            execution_path=execution_path
        )
    except Exception as e:
        logger.error(f"Research generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Research generation failed: {str(e)}")


# ========================================
# CopilotKit Integration
# ========================================

if COPILOTKIT_AVAILABLE:
    logger.info("Integrating CopilotKit for real-time state streaming")
    
    # Initialize CopilotKit SDK
    copilot = CopilotKit()
    
    # Add LangGraph endpoint
    # This creates a /copilotkit POST endpoint that streams agent state
    copilot.add_langgraph_endpoint(
        app_id="ai_q_researcher",  # Must match frontend's useCoAgentStateRender name
        endpoint="/copilotkit",
        graph=lambda: agent_graph,  # Pass graph factory
        config_factory=lambda: agent_config
    )
    
    # Include CopilotKit router in FastAPI app
    app.include_router(copilot.router)
    
    logger.info("✅ CopilotKit endpoint registered at POST /copilotkit")
else:
    logger.warning("⚠️ CopilotKit not available - real-time streaming disabled")


# ========================================
# Legacy AI-Q Compatibility Endpoints
# ========================================

@app.post("/generate_query")
async def generate_query_legacy(request: Dict[str, Any]):
    """Legacy endpoint for query generation (AI-Q compatibility)."""
    # This endpoint maintains compatibility with the original AI-Q frontend
    # if someone wants to use it without CopilotKit
    raise HTTPException(
        status_code=501,
        detail="Use /research or /copilotkit endpoints for the hackathon demo"
    )


# ========================================
# Main
# ========================================

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    
    logger.info(f"""
╔══════════════════════════════════════════════════════════╗
║  AI-Q Research Assistant with UDF                        ║
║  AWS & NVIDIA Hackathon Edition                          ║
╠══════════════════════════════════════════════════════════╣
║  🚀 Starting server on port {port}                       ║
║  📡 CopilotKit: {'✅ Enabled' if COPILOTKIT_AVAILABLE else '❌ Disabled'}                          ║
║  🧠 Nemotron NIM: {Config.NEMOTRON_NIM_URL[:30]}...       ║
║  📚 RAG Service: {Config.RAG_SERVER_URL[:35]}...        ║
╚══════════════════════════════════════════════════════════╝
    """)
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level="info"
    )

