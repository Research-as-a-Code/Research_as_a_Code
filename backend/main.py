# SPDX-FileCopyrightText: Copyright (c) 2025 Research_as_a_Code Project
# SPDX-License-Identifier: Apache-2.0

"""
FastAPI Backend with CopilotKit Integration

This is the main backend service that:
1. Serves the AI-Q + UDR agent via REST API
2. Integrates CopilotKit SDK for real-time state streaming to the frontend
3. Provides endpoints for research generation with agentic flow visualization
"""

import os
import uvicorn
import logging
from typing import Dict, Any, Optional, Union, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

# CopilotKit SDK
try:
    from copilotkit import CopilotKitRemoteEndpoint
    from copilotkit.integrations.fastapi import add_fastapi_endpoint
    COPILOTKIT_AVAILABLE = True
except ImportError:
    COPILOTKIT_AVAILABLE = False
    logging.warning("CopilotKit SDK not installed. Install with: pip install copilotkit")

# AI-Q and UDR imports
from aiq_aira.hackathon_agent import create_configured_agent, HackathonAgentState
from aiq_aira.udr_integration import UDRIntegration
from aiq_aira.ttd_dr import TTDDRIntegration
from langchain_openai import ChatOpenAI

# Configure logging - use uvicorn's logger to ensure logs appear
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s:     %(message)s',
    handlers=[logging.StreamHandler()]
)
# Use uvicorn's logger for consistency with server logs
logger = logging.getLogger("uvicorn")


# ========================================
# Configuration
# ========================================

class Config:
    """Application configuration from environment variables."""
    
    # LLM Endpoints - Use cluster-local NIMs (deployed in nim namespace)
    # These NIMs were running all along - just had wrong service name!
    NEMOTRON_NIM_URL = os.getenv("NEMOTRON_NIM_URL", "http://instruct-llm-service.nim.svc.cluster.local:8000")
    INSTRUCT_LLM_URL = os.getenv("INSTRUCT_LLM_URL", "http://instruct-llm-service.nim.svc.cluster.local:8000")
    EMBEDDING_NIM_URL = os.getenv("EMBEDDING_NIM_URL", "http://embedding-service.nim.svc.cluster.local:8000")
    
    # RAG uses direct Milvus integration - search_rag expects embedding NIM URL
    RAG_SERVER_URL = os.getenv("RAG_SERVER_URL", "http://embedding-service.nim.svc.cluster.local:8000")
    
    # Tavily API Key (for web search)
    TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
    
    # NGC API Key (for NIM authentication if needed)
    NGC_API_KEY = os.getenv("NGC_API_KEY", "not-needed")
    
    # Model names - Using Nemotron Nano 8B (as specified for hackathon)
    # Reasoning model for planning/analysis
    NEMOTRON_MODEL = "nvidia/llama-3.1-nemotron-nano-8b-v1"
    # Instruct model for writing  
    INSTRUCT_MODEL = "nvidia/llama-3.1-nemotron-nano-8b-v1"


# Global agent instance
agent_graph = None
agent_config = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize agent on startup with comprehensive error handling."""
    global agent_graph, agent_config
    
    logger.info("=" * 80)
    logger.info("🚀 LIFESPAN STARTUP BEGINNING")
    logger.info("=" * 80)
    
    try:
        logger.info("Step 1/6: Initializing AI-Q + UDR Agent...")
        
        # Create LLM instances
        logger.info("Step 2/6: Creating reasoning LLM...")
        logger.info(f"   Model: {Config.NEMOTRON_MODEL}")
        logger.info(f"   Base URL: {Config.NEMOTRON_NIM_URL}")
        reasoning_llm = ChatOpenAI(
            base_url=f"{Config.NEMOTRON_NIM_URL}/v1",
            api_key=Config.NGC_API_KEY,
            model=Config.NEMOTRON_MODEL,
            temperature=0.5
        )
        # Test the LLM to catch configuration errors early
        # TEMPORARILY DISABLED: Allow startup while NIM is still building
        try:
            test_response = reasoning_llm.invoke("Hello")
            logger.info(f"✅ Reasoning LLM verified: {Config.NEMOTRON_MODEL}")
            logger.info(f"   Test response: {test_response.content[:50]}...")
        except Exception as e:
            logger.warning(f"⚠️ REASONING LLM NOT YET READY (will retry on first request)")
            logger.warning(f"   Model: {Config.NEMOTRON_MODEL}")
            logger.warning(f"   URL: {Config.NEMOTRON_NIM_URL}")
            logger.warning(f"   Error: {type(e).__name__}: {str(e)[:200]}")
            # Don't raise - allow startup to continue
        
        logger.info("Step 3/6: Creating instruct LLM...")
        instruct_llm = ChatOpenAI(
            base_url=f"{Config.INSTRUCT_LLM_URL}/v1",
            api_key=Config.NGC_API_KEY,
            model=Config.INSTRUCT_MODEL,
            temperature=0.0
        )
        logger.info(f"✅ Instruct LLM created: {Config.INSTRUCT_MODEL}")
        
        # Create UDR integration
        logger.info("Step 4/6: Creating UDR integration...")
        udr_integration = UDRIntegration(
            compiler_llm=reasoning_llm,
            rag_url=Config.RAG_SERVER_URL,
            nemotron_nim_url=Config.NEMOTRON_NIM_URL,
            embedding_nim_url=Config.EMBEDDING_NIM_URL,
            tavily_api_key=Config.TAVILY_API_KEY
        )
        logger.info("✅ UDR integration created")
        
        # Create TTD-DR integration
        logger.info("Step 4b/6: Creating TTD-DR integration...")
        ttd_dr_integration = TTDDRIntegration(
            llm=reasoning_llm,
            rag_url=Config.RAG_SERVER_URL,
            synthesis_llm=instruct_llm,
            tavily_api_key=Config.TAVILY_API_KEY
        )
        logger.info("✅ TTD-DR integration created")
        
        # Create configured agent
        logger.info("Step 5/6: Creating configured agent graph...")
        agent_graph, agent_config = create_configured_agent(
            reasoning_llm=reasoning_llm,
            instruct_llm=instruct_llm,
            udr_integration=udr_integration,
            ttd_dr_integration=ttd_dr_integration,
            rag_url=Config.RAG_SERVER_URL,
            num_reflections=2
        )
        logger.info(f"✅ Agent graph created: {type(agent_graph)}")
        logger.info(f"✅ Agent config created: {type(agent_config)}")
        
        logger.info("=" * 80)
        logger.info("✅ AI-Q + UDR Agent initialized successfully")
        logger.info("=" * 80)
        
        # Initialize CopilotKit after agent is created
        logger.info("Step 6/6: Initializing CopilotKit integration...")
        if COPILOTKIT_AVAILABLE:
            try:
                logger.info("Integrating CopilotKit for real-time state streaming")
                
                # Create the LangGraph AGUI agent
                from copilotkit import LangGraphAGUIAgent
                logger.info("✅ LangGraphAGUIAgent imported")
                
                # Create a wrapper class that adds dict_repr() for CopilotKitRemoteEndpoint compatibility
                class CompatibleLangGraphAgent(LangGraphAGUIAgent):
                    """Wrapper to add dict_repr() method for CopilotKitRemoteEndpoint compatibility"""
                    def dict_repr(self):
                        return {
                            "name": self.name,
                            "description": self.description or "",
                            "type": "langgraph"
                        }
                
                langgraph_agent = CompatibleLangGraphAgent(
                    name="ai_q_researcher",  # Must match frontend's useCoAgentStateRender name
                    description="AI-Q Research Assistant with Universal Deep Research",
                    graph=agent_graph,
                    config=agent_config
                )
                logger.info("✅ CompatibleLangGraphAgent instance created")
                
                # Also create a "default" agent that points to the same graph
                # This is needed because CopilotKit frontend looks for "default" when no specific agent is specified
                default_agent = CompatibleLangGraphAgent(
                    name="default",
                    description="AI-Q Research Assistant with Universal Deep Research (default)",
                    graph=agent_graph,
                    config=agent_config
                )
                logger.info("✅ 'default' agent alias created")
                
                # Add compatibility methods if missing (compatibility fixes for copilotkit 0.1.70)
                if not hasattr(langgraph_agent, 'dict_repr'):
                    def dict_repr_method(self):
                        return {
                            'name': self.name,
                            'description': self.description or ''
                        }
                    langgraph_agent.dict_repr = dict_repr_method.__get__(langgraph_agent, type(langgraph_agent))
                    logger.info("✅ Added dict_repr compatibility method")
                
                # Add execute method that wraps the run method
                if not hasattr(langgraph_agent, 'execute'):
                    async def execute_method(self, *, state, config=None, messages, thread_id, node_name=None, actions=None, meta_events=None, **kwargs):
                        """
                        Execute method that wraps LangGraphAGUIAgent.run()
                        This bridges the gap between Agent.execute() and LangGraphAGUIAgent.run()
                        """
                        import uuid
                        import json
                        from ag_ui.core.types import RunAgentInput
                        
                        logger.info(f"✅ execute_method called! thread_id={thread_id}, node_name={node_name}")
                        
                        # Convert CopilotKit format to AG-UI format (using camelCase field names)
                        try:
                            agent_input = RunAgentInput(
                                state=state,
                                messages=messages,
                                threadId=thread_id,
                                runId=str(uuid.uuid4()),  # Generate unique run ID
                                tools=[],  # Empty tools list
                                context=[],  # Empty context list
                                forwardedProps={}  # Empty forwarded props
                            )
                            
                            logger.info("✅ RunAgentInput created successfully, calling agent.run()")
                            
                            # Run the agent and convert events to JSON strings  
                            async for event in self.run(agent_input):
                                # Check if event is already a string or needs serialization
                                if isinstance(event, str):
                                    # Already a string, ensure it has a newline
                                    if not event.endswith("\n"):
                                        yield event + "\n"
                                    else:
                                        yield event
                                else:
                                    # Event is a Pydantic model, serialize it to JSON
                                    event_json = json.dumps(event.model_dump()) + "\n"
                                    yield event_json
                            
                        except Exception as e:
                            logger.error(f"❌ Error in execute_method: {e}", exc_info=True)
                            raise
                    
                    langgraph_agent.execute = execute_method.__get__(langgraph_agent, type(langgraph_agent))
                    logger.info("✅ Added execute compatibility method")
                
                # Initialize CopilotKit RemoteEndpoint with both agents
                logger.info("Creating CopilotKitRemoteEndpoint...")
                copilot_sdk = CopilotKitRemoteEndpoint(agents=[langgraph_agent, default_agent])
                logger.info("✅ CopilotKitRemoteEndpoint created with 'ai_q_researcher' and 'default' agents")
                
                # Add FastAPI endpoint
                logger.info("Adding FastAPI endpoint for CopilotKit...")
                add_fastapi_endpoint(
                    fastapi_app=app,
                    sdk=copilot_sdk,
                    prefix="/copilotkit"
                )
                
                logger.info("=" * 80)
                logger.info("✅ CopilotKit endpoint registered at /copilotkit")
                logger.info("=" * 80)
                
            except Exception as e:
                logger.error("=" * 80)
                logger.error(f"❌ FAILED to initialize CopilotKit: {e}")
                logger.error("=" * 80)
                logger.exception("Full CopilotKit initialization traceback:")
                # Don't raise - allow the app to continue without CopilotKit
        else:
            logger.warning("=" * 80)
            logger.warning("⚠️ CopilotKit not available - real-time streaming disabled")
            logger.warning("=" * 80)
        
        logger.info("=" * 80)
        logger.info("🎉 LIFESPAN STARTUP COMPLETED - Yielding to application")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error("=" * 80)
        logger.error(f"❌ FATAL ERROR during lifespan startup: {e}")
        logger.error("=" * 80)
        logger.exception("Full startup traceback:")
        # Re-raise to prevent the app from starting in a broken state
        raise
    
    yield
    
    logger.info("=" * 80)
    logger.info("🛑 LIFESPAN SHUTDOWN BEGINNING")
    logger.info("=" * 80)
    logger.info("Shutting down...")
    logger.info("=" * 80)
    logger.info("✅ LIFESPAN SHUTDOWN COMPLETE")
    logger.info("=" * 80)


# ========================================
# FastAPI App
# ========================================

app = FastAPI(
    title="AI-Q Research Assistant with UDR",
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


# Debug middleware to log CopilotKit requests/responses
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
import json

class CopilotKitDebugMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if "/copilotkit" in request.url.path:
            # Log request
            body = await request.body()
            logger.info(f"🔍 CopilotKit Request: {request.method} {request.url.path}")
            if body:
                try:
                    body_json = json.loads(body)
                    logger.info(f"🔍 Request body: {json.dumps(body_json, indent=2)[:500]}")
                except:
                    logger.info(f"🔍 Request body (raw): {body[:200]}")
            
            # Get response
            response = await call_next(request)
            
            # Log response status
            logger.info(f"🔍 CopilotKit Response: {response.status_code}")
            
            return response
        return await call_next(request)

app.add_middleware(CopilotKitDebugMiddleware)


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
    collection: Union[str, List[str]] = Field(
        default="",
        description="RAG collection(s) to search - single string or list of collection names"
    )
    search_web: bool = Field(
        default=True,
        description="Whether to include web search"
    )
    strategy: str = Field(
        default="udr",
        description="Research strategy to use: 'udr' (Universal Deep Research) or 'ttd_dr' (Test-Time Diffusion Deep Researcher)"
    )


class ResearchResponse(BaseModel):
    """Response model for research generation."""
    final_report: str
    citations: str
    logs: list[str]
    execution_path: str  # "UDR" or "Simple RAG"


# ========================================
# API Endpoints
# ========================================

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "AI-Q Research Assistant with UDR",
        "copilotkit_enabled": COPILOTKIT_AVAILABLE
    }


@app.get("/copilotkit/info")
async def copilotkit_info_get():
    """
    CopilotKit info endpoint (GET handler for frontend compatibility).
    
    The CopilotKit Python SDK 0.1.x only registers POST handlers,
    but the frontend JavaScript SDK 1.x expects GET for /info.
    This adds GET support for compatibility.
    """
    return {
        "actions": [],
        "agents": [
            {
                "name": "ai_q_researcher",
                "description": "AI-Q Research Assistant with Universal Deep Research"
            },
            {
                "name": "default",
                "description": "AI-Q Research Assistant with Universal Deep Research (default)"
            }
        ],
        "sdkVersion": "0.1.70"
    }


@app.post("/research/stream")
async def generate_research_stream(request: ResearchRequest):
    """
    Generate research report with real-time SSE streaming of agent state.
    
    This endpoint streams intermediate states as Server-Sent Events,
    allowing the frontend to display real-time progress updates.
    """
    from fastapi.responses import StreamingResponse
    import json
    import uuid
    
    if not agent_graph:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    logger.info(f"Streaming research request: {request.topic[:50]}...")
    
    async def event_stream():
        """Generator that yields SSE events with agent state updates."""
        import asyncio
        import time
        
        try:
            # Send initial connection event
            yield f": connected at {time.time()}\n\n"
            
            # Prepare initial state
            initial_state: HackathonAgentState = {
                "research_prompt": request.topic,
                "report_organization": request.report_organization,
                "collection": request.collection,
                "search_web": request.search_web,
                "strategy": request.strategy,  # Pass selected strategy
                "plan": "",
                "queries": [],
                "web_research_results": [],
                "citations": "",
                "running_summary": "",
                "udr_strategy": "",
                "udr_result": {},
                "ttd_dr_stage": None,
                "ttd_dr_iteration": None,
                "ttd_dr_convergence": None,
                "ttd_dr_questions": None,
                "ttd_dr_gaps": None,
                "ttd_dr_improvements": None,
                "final_report": "",
                "logs": []
            }
            
            # Create per-request config
            thread_id = f"research-{uuid.uuid4().hex[:8]}"
            request_config = {
                "configurable": {
                    **agent_config.get("configurable", {}),
                    "thread_id": thread_id,
                    "topic": request.topic,
                    "collection": request.collection,
                    "report_organization": request.report_organization,
                    "search_web": request.search_web,
                    "strategy": request.strategy  # Pass strategy to agent config
                }
            }
            
            logger.info(f"🔄 Starting stream for thread_id={thread_id}")
            
            # Use astream_events() for granular streaming of internal node operations
            # This captures writer() calls and intermediate operations within nodes
            # Regular astream() only yields when nodes RETURN (causing superstep issues)
            keepalive_interval = 120  # Send keepalive if no event for 120 seconds (increased for long HTTP calls)
            agent_stream = agent_graph.astream_events(
                initial_state, 
                request_config,
                version="v2"  # Use v2 for better event structure
            ).__aiter__()
            
            event_count = 0
            while True:
                try:
                    # Wait for next event with timeout
                    logger.debug(f"Waiting for next agent event (received {event_count} so far)...")
                    event = await asyncio.wait_for(agent_stream.__anext__(), timeout=keepalive_interval)
                    event_count += 1
                    logger.info(f"📦 Received event #{event_count} from agent")
                    logger.info(f"  └─ Raw event type: {type(event)}, content: {event}")
                    
                    # Process astream_events() - different structure than astream()
                    event_type = event.get("event", "")
                    event_name = event.get("name", "")
                    event_data_inner = event.get("data", {})
                    
                    # Only process chain_end events (when nodes complete)
                    # Check both event name and metadata for node identification
                    event_metadata = event.get("metadata", {})
                    langgraph_node = event_metadata.get("langgraph_node", event_name)
                    
                    # Watch for all node completions including progressive nodes
                    watched_nodes = [
                        "planner",
                        # Progressive SIMPLE_RAG nodes (3 nodes)
                        "generate_queries", "search_sources", "synthesize_report",
                        # Progressive UDR nodes (3 nodes)
                        "udr_prepare", "udr_compile_validate", "udr_execute",
                        # Progressive TTD-DR nodes (4 nodes - split research phase)
                        "ttd_dr_init", "ttd_dr_start_research", "ttd_dr_execute_iterations", "ttd_dr_finalize",
                        # Final
                        "final_report"
                    ]
                    if event_type == "on_chain_end" and langgraph_node in watched_nodes:
                        logger.info(f"  └─ Node completed: {langgraph_node} (event_name={event_name})")
                        
                        # Get the FULL accumulated state from the graph after this node
                        # This includes logs accumulated via operator.add
                        try:
                            full_state = agent_graph.get_state(request_config)
                            accumulated_state = full_state.values if hasattr(full_state, 'values') else {}
                        except Exception as e:
                            logger.warning(f"Could not get accumulated state: {e}, using output only")
                            accumulated_state = {}
                        
                        # Extract output from the event (node's return value)
                        output = event_data_inner.get("output", {})
                        
                        # Convert LangChain objects to JSON-serializable dicts
                        def make_serializable(obj):
                            """Recursively convert objects to JSON-serializable format."""
                            if hasattr(obj, 'dict'):
                                # LangChain objects with .dict() method
                                return obj.dict()
                            elif hasattr(obj, '__dict__'):
                                # Generic objects with __dict__
                                return {k: make_serializable(v) for k, v in obj.__dict__.items() if not k.startswith('_')}
                            elif isinstance(obj, dict):
                                return {k: make_serializable(v) for k, v in obj.items()}
                            elif isinstance(obj, (list, tuple)):
                                return [make_serializable(item) for item in obj]
                            elif isinstance(obj, (str, int, float, bool, type(None))):
                                return obj
                            else:
                                # Fallback: convert to string
                                return str(obj)
                        
                        # Merge node output with accumulated state (prioritize accumulated logs)
                        serializable_output = make_serializable(output)
                        if accumulated_state:
                            # Include accumulated logs from the full state
                            accumulated_logs = accumulated_state.get('logs', [])
                            if accumulated_logs:
                                serializable_output['logs'] = make_serializable(accumulated_logs)
                        
                        # Send SSE event
                        sse_event = {
                            "node": langgraph_node,
                            "state": serializable_output,
                            "type": "update"
                        }
                        yield f"data: {json.dumps(sse_event)}\n\n"
                        await asyncio.sleep(0)
                    elif event_type == "on_custom_event":
                        # Custom events from writer() calls - log but don't stream to avoid noise
                        logger.debug(f"  └─ Custom event: {event_data_inner}")
                        
                except asyncio.TimeoutError:
                    # No event received within timeout - send keepalive
                    logger.debug(f"⏰ No agent event for {keepalive_interval}s, sending keepalive")
                    yield f": keepalive at {time.time()}\n\n"
                    await asyncio.sleep(0)
                    continue  # Try to get next event
                    
                except StopAsyncIteration:
                    # Agent stream completed
                    logger.info(f"✅ Agent stream completed after {event_count} events")
                    break
            
            # Send final completion event
            logger.info(f"✅ Stream completed for thread_id={thread_id}")
            completion_event = {
                "type": "complete",
                "message": "Research generation complete"
            }
            yield f"data: {json.dumps(completion_event)}\n\n"
            
        except asyncio.CancelledError:
            logger.warning(f"⚠️ Stream cancelled for thread_id={thread_id}")
            raise
        except Exception as e:
            logger.error(f"❌ Stream error for thread_id={thread_id}: {e}", exc_info=True)
            error_event = {
                "type": "error",
                "message": str(e)
            }
            yield f"data: {json.dumps(error_event)}\n\n"
    
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )


@app.post("/research", response_model=ResearchResponse)
async def generate_research(request: ResearchRequest):
    """
    Generate research report using AI-Q + UDR agent.
    
    This endpoint runs the agent synchronously and returns the complete result.
    For real-time streaming, use the /copilotkit endpoint.
    """
    if not agent_graph:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    print(f"🔍 DEBUG: Research request received: {request.topic[:50]}...", flush=True)
    logger.info(f"Research request: {request.topic[:50]}...")
    
    # Prepare initial state
    initial_state: HackathonAgentState = {
        "research_prompt": request.topic,
        "report_organization": request.report_organization,
        "collection": request.collection,
        "search_web": request.search_web,
        "strategy": request.strategy,  # Pass selected strategy
        "plan": "",
        "queries": [],
        "web_research_results": [],
        "citations": "",
        "running_summary": "",
        "udr_strategy": "",
        "udr_result": {},
        "ttd_dr_stage": None,
        "ttd_dr_iteration": None,
        "ttd_dr_convergence": None,
        "ttd_dr_questions": None,
        "ttd_dr_gaps": None,
        "ttd_dr_improvements": None,
        "final_report": "",
        "logs": []
    }
    
    # Run agent
    try:
        # Create per-request config with request parameters
        import uuid
        thread_id = f"research-{uuid.uuid4().hex[:8]}"
        
        # Build request config by merging base agent_config with request params
        if not agent_config or "configurable" not in agent_config:
            logger.error(f"❌ agent_config is invalid: {agent_config}")
            raise ValueError("Agent config not properly initialized")
        
        request_config = {
            "configurable": {
                **agent_config.get("configurable", {}),  # Base config (LLMs, etc.)
                "thread_id": thread_id,  # Required by MemorySaver checkpointer
                "topic": request.topic,
                "collection": request.collection,
                "report_organization": request.report_organization,
                "search_web": request.search_web,
                "strategy": request.strategy  # Pass strategy to agent config
            }
        }
        
        logger.info(f"✅ Request config created with thread_id={thread_id}")
        
        print(f"🔍 DEBUG: Running agent with collection={request.collection}, search_web={request.search_web}, topic={request.topic}", flush=True)
        logger.info(f"Running agent with collection: {request.collection}, search_web: {request.search_web}")
        
        final_state = await agent_graph.ainvoke(initial_state, request_config)
        print(f"🔍 DEBUG: Agent completed, execution_path will be determined", flush=True)
        
        # Determine which path was taken (check TTD-DR, UDR, then Simple RAG)
        if final_state.get("ttd_dr_stage") == "complete":
            execution_path = "TTD-DR"
        elif final_state.get("udr_result", {}).get("success"):
            execution_path = "UDR"
        else:
            execution_path = "Simple RAG"
        
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
║  AI-Q Research Assistant with UDR                        ║
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

