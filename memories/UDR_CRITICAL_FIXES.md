# UDR (Universal Deep Research) Critical Fixes - Nov 19, 2025

## Summary
After extensive debugging, we identified and fixed 4 critical issues preventing the UDR dynamic strategy feature from working. The primary symptom was that research reports never reached the frontend, despite the backend completing successfully.

## Critical Issues & Fixes

### 1. Logger Deadlock in UDR Tool Functions ⚠️ CRITICAL
**Symptom:**
- UDR execution would start (🔶 marker appeared)
- `_search_rag_tool` would be entered (🔷 marker appeared)
- Execution would hang before the first `logger.info()` call
- No subsequent tool execution logs would appear

**Root Cause:**
- `logger.info()` calls inside UDR tool functions (`_search_rag_tool`, `_search_web_tool`, `_synthesize_findings_tool`) caused a deadlock when called from within generated async code executed by LangGraph
- The logging system was likely trying to acquire a lock that was already held by the parent execution context

**Fix:**
```python
# BEFORE (in aira/src/aiq_aira/udr_integration.py)
logger.info(f"UDR Tool Call: search_rag(query='{query[:50]}...', collection='{collection}')")

# AFTER
import sys
print("🔷 _search_rag_tool ENTERED!", flush=True, file=sys.stderr)
print(f"🔷 About to call logger.info with query length: {len(query)}", flush=True, file=sys.stderr)
# Skip logger.info - it causes deadlock!
```

**Files Modified:**
- `aira/src/aiq_aira/udr_integration.py` (lines 377-384, 475-512, 514-578)

**Lesson:** When executing dynamically generated async code with `exec()` + `await`, avoid using Python's standard `logging` module inside functions called from that code. Use direct `print()` to stderr instead.

---

### 2. Event Filtering - Metadata vs Event Name ⚠️ CRITICAL
**Symptom:**
- Browser console showed: `📦 State update from node: planner` (received)
- Browser console showed: `📦 State update from node: dynamic_strategy` with AIMessage keys (wrong data!)
- Browser showed: `⚠️ Stream completed but no final report was received`
- Backend logs showed: `Node completed: planner` but NOT `Node completed: dynamic_strategy` (with the actual node output)

**Root Cause:**
- Backend was filtering events by `event_name`, but LangGraph's `astream_events()` uses different event names for sub-components
- The code generation step (RunnableSequence) completed and was detected as `dynamic_strategy`, but that's NOT the actual node completion
- The real node completion event has `event_name='dynamic_strategy'` but we were catching `event_name='RunnableSequence'` with `metadata.langgraph_node='dynamic_strategy'`

**Fix:**
```python
# BEFORE (in backend/main.py)
if event_type == "on_chain_end" and event_name in ["planner", "simple_rag", "dynamic_strategy", "final_report"]:

# AFTER
event_metadata = event.get("metadata", {})
langgraph_node = event_metadata.get("langgraph_node", event_name)

if event_type == "on_chain_end" and langgraph_node in ["planner", "simple_rag", "dynamic_strategy", "final_report"]:
    logger.info(f"  └─ Node completed: {langgraph_node} (event_name={event_name})")
```

**Files Modified:**
- `backend/main.py` (lines 428-433)

**Lesson:** When using LangGraph's `astream_events()`, always check `metadata.langgraph_node` to identify which graph node an event belongs to, not just the `event_name`.

---

### 3. LangChain Object JSON Serialization Error
**Symptom:**
- Browser console showed: `Error parsing SSE event: Error: Object of type AIMessageChunk is not JSON serializable`
- Backend was detecting node completions but couldn't serialize the output to JSON

**Root Cause:**
- The `dynamic_strategy` node's output contained LangChain objects (`AIMessage`, `AIMessageChunk`, etc.) that can't be directly serialized with `json.dumps()`
- These objects have special methods and metadata that aren't JSON-compatible

**Fix:**
```python
# Added to backend/main.py (lines 438-456)
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

serializable_output = make_serializable(output)
```

**Files Modified:**
- `backend/main.py` (lines 438-457)

**Lesson:** Always sanitize objects before JSON serialization, especially when dealing with framework objects (LangChain, LangGraph, etc.). Use recursive conversion with fallback to string representation.

---

### 4. Stream Premature Closure - Keepalive Interval ⚠️ MOST CRITICAL
**Symptom:**
- Backend logs showed: `🔷 Calling Instruct LLM NIM...` (HTTP call starts)
- 10 seconds later: `✅ Agent stream completed after 787 events` (stream closes!)
- Backend logs showed: `✅ execute_dynamic_strategy returned!` **NEVER appeared**
- The Instruct LLM NIM call has a 60-second timeout, but the stream closed after 10 seconds
- Frontend never received the final report because the stream closed before the node returned

**Root Cause:**
- Backend's `keepalive_interval` was set to 10 seconds
- When `astream_events()` doesn't receive any events for 10 seconds, it assumes the stream is done
- The Instruct LLM NIM HTTP call (synthesis step) takes 10-60 seconds and doesn't emit events while waiting
- The stream closes prematurely, and the node's return value is never sent to the frontend

**The Fix (THE KEY TO SUCCESS!):**
```python
# BEFORE (in backend/main.py)
keepalive_interval = 10  # Send keepalive if no event for 10 seconds

# AFTER
keepalive_interval = 120  # Send keepalive if no event for 120 seconds (increased for long HTTP calls)
```

**Files Modified:**
- `backend/main.py` (line 405)

**Lesson:** When using `astream_events()` with nodes that make long-running external API calls (LLM inference, embeddings, web searches, etc.), the `keepalive_interval` MUST be longer than the longest expected API call. Otherwise, the stream will close before the node completes, and the client will never receive the result.

**Additional Context:**
- HTTP calls to NIMs (NVIDIA Inference Microservices) can take 10-60+ seconds depending on:
  - Model size (larger models take longer)
  - Input token count (longer prompts take longer)
  - Server load (shared NIMs may queue requests)
  - Network latency
- In this case, the synthesis step's HTTP POST to the Instruct LLM NIM was taking ~15-20 seconds
- With a 10-second keepalive, the stream would close around the same time the HTTP call was completing
- Increasing to 120 seconds gave plenty of buffer for the HTTP call to complete

---

## Additional Improvements Made

### 5. Synthesis Timeout & Error Handling
**Change:**
```python
# Reduced timeout from 120s to 60s with better error handling
async with session.post(
    f"{self.nemotron_nim_url}/v1/chat/completions",
    headers=headers,
    json=data_payload,
    timeout=aiohttp.ClientTimeout(total=60)  # Reduced from 120 to 60
) as response:
    # ... handle response
except asyncio.TimeoutError:
    print(f"❌ Instruct LLM NIM timed out after 60s", flush=True, file=sys.stderr)
    return "Error: LLM synthesis timed out after 60 seconds"
except Exception as http_error:
    print(f"❌ Instruct LLM NIM HTTP error: {http_error}", flush=True, file=sys.stderr)
    return f"Error: LLM HTTP request failed: {str(http_error)}"
```

**Files Modified:**
- `aira/src/aiq_aira/udr_integration.py` (lines 556-575)

---

## Debugging Techniques That Worked

### 1. Granular Debug Markers
Used emoji markers at different execution levels:
- 🔴 = `dynamic_strategy_node` level
- 🔵 = Node internal operations
- 🟢 = UDR integration level
- 🟡 = UDR executor level
- 🔶 = Inside generated code
- 🔷 = Inside tool functions

This made it easy to trace execution flow and pinpoint exactly where execution stopped.

### 2. Print to stderr with flush
```python
print("🔷 Debug message", flush=True, file=sys.stderr)
```
- `flush=True` ensures immediate output (no buffering)
- `file=sys.stderr` ensures logs appear even if stdout is captured
- More reliable than `logger` in dynamically executed code

### 3. Timestamps in logs
```bash
kubectl logs <pod> --timestamps | grep "🔷"
```
Helped identify timing issues and correlate events.

### 4. Isolating Issues
Created `test_langgraph_async.py` to reproduce the async nesting pattern in isolation, which helped rule out the async execution pattern itself as the issue.

---

## Architecture Notes

### UDR Execution Flow
1. **Planner Node**: Generates natural language plan → routes to `dynamic_strategy`
2. **Dynamic Strategy Node**: 
   - Calls `UDFIntegration.execute_dynamic_strategy()`
   - Generates Python code from NL plan
   - Validates generated code
   - Executes code with `exec()` + `await`
3. **Generated Code**: 
   - Calls `search_rag()` (Milvus + Embedding NIM)
   - Calls `search_web()` (Tavily)
   - Calls `synthesize_findings()` (Instruct LLM NIM)
   - Returns `{"report": ..., "sources": ..., "log": ...}`
4. **Node Returns**: Result passed back through LangGraph
5. **Backend SSE Stream**: Sends result to frontend
6. **Frontend**: Displays report

### Critical Timing Requirements
- Code generation: ~5-10 seconds (Nemotron Nano LLM)
- RAG search: ~2-3 seconds (Milvus + Embedding NIM)
- Web search: ~2-3 seconds (Tavily API)
- Synthesis: **10-60 seconds** (Instruct LLM NIM) ⚠️ LONGEST STEP
- **Total UDR execution: ~20-80 seconds**

**Therefore:**
- `asyncio.wait_for` timeout in node: 300 seconds (5 minutes)
- Backend `keepalive_interval`: 120 seconds
- Synthesis HTTP timeout: 60 seconds

---

## Files Modified Summary

### Critical Fixes:
1. `aira/src/aiq_aira/udr_integration.py` - Logger → print, timeout & error handling
2. `backend/main.py` - Event filtering, JSON serialization, keepalive interval

### Debug Additions:
1. `aira/src/aiq_aira/hackathon_agent.py` - Debug markers in `dynamic_strategy_node`
2. `test_langgraph_async.py` - Isolated test case (can be deleted)

---

## Testing Recommendations

### Test Different Query Types:
1. **Simple queries** (should use simple RAG, not UDR)
2. **Multi-step research** (triggers UDR dynamic strategy)
3. **Web + RAG combined** (tests both data sources)
4. **Long synthesis** (tests timeout handling)

### Monitor These Metrics:
- Time from "🔷 Calling Instruct LLM NIM..." to "🔷 Response status"
- Total UDR execution time (should be < 2 minutes for most queries)
- Stream completion timing (should happen AFTER node returns)

### Red Flags to Watch For:
- ❌ Stream completes before seeing "✅ execute_dynamic_strategy returned!"
- ❌ No 🔷 markers (indicates logger deadlock or tool not being called)
- ❌ Timeout errors after 60 seconds (may need to increase NIM timeout)
- ❌ "Stream completed but no final report was received" (indicates timing issue)

---

## Future Improvements to Consider

1. **Streaming synthesis**: Instead of waiting for full LLM response, stream tokens as they're generated
2. **Progress indicators**: Send intermediate updates during long operations
3. **Caching**: Cache synthesis results for similar queries
4. **Parallel tool calls**: Execute `search_rag` and `search_web` in parallel
5. **Better error recovery**: Retry failed tool calls with exponential backoff

---

## Key Takeaways

1. **Async + Logging = Danger**: Be very careful with Python's logging module in dynamically executed async code
2. **Event Metadata Matters**: Always check `metadata.langgraph_node` when using `astream_events()`
3. **Timing is Everything**: `keepalive_interval` must be longer than longest operation
4. **Always Serialize**: Never assume framework objects are JSON-serializable
5. **Debug Markers**: Emoji markers with timestamps are incredibly effective for tracing execution flow

---

*Document created: November 19, 2025*
*Last tested: UDR working successfully with 120s keepalive interval*

