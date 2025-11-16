# SSE (Server-Sent Events) Investigation

## Current Status: STABLE WITHOUT SSE ✅

The application is now running **reliably without CopilotKit SSE streaming**. The page load crash is eliminated.

- **Frontend**: `http://af2f4f77d44fb4b41bc00856345951e2-974749261.us-west-2.elb.amazonaws.com`
- **Backend**: `http://af3615e06391145bc88022ac024a36ca-bd296660cda3522f.elb.us-west-2.amazonaws.com`
- **Communication**: Synchronous HTTP POST to `/research` endpoint
- **Agent Flow Panel**: Shows static "idle" message (no real-time updates)

---

## Problem Summary

When CopilotKit was enabled, the frontend experienced a **JavaScript crash on page load**:

```
CopilotKit Error (hidden in production): CombinedError: [Network] No Content
at ek (65-8abdbeff6e1d9a29.js:351:2267)
at eO (65-8abdbeff6e1d9a29.js:351:5422)
```

Additionally, research requests would **hang indefinitely** without returning results.

---

## Investigation Findings

### 1. Version Compatibility ✅
- **Frontend NPM packages**: `@copilotkit/react-core: ^1.0.0`  
- **Backend Python package**: `copilotkit==0.1.70`  
- **Verdict**: These are **designed to work together** despite different version numbers. NPM and PyPI have separate versioning schemes. ✅

### 2. Backend Endpoint Status ✅
- The `/copilotkit/` endpoint **IS responding correctly**:
  ```bash
  curl -X POST http://backend/copilotkit/ -H "Content-Type: application/json" -d '{"messages":[],"state":{}}'
  # Returns: {"actions":[],"agents":[{"name":"ai_q_researcher",...}],"sdkVersion":"0.1.70"}
  ```
- Backend logs confirm requests are received: `POST /copilotkit/ HTTP/1.1" 200 OK`
- **Verdict**: Backend integration is correct. ✅

### 3. Frontend Connection Attempt ✅
- CopilotKit **DOES make the initial POST** request to `/copilotkit/` on page load
- The request succeeds (200 OK)
- **But then**: CopilotKit crashes with "[Network] No Content"
- **Hypothesis**: CopilotKit expects the response to **open an SSE stream**, but the backend closes the connection after sending JSON

### 4. SSE Protocol Mismatch ⚠️
The root cause appears to be a **protocol expectation mismatch**:

- CopilotKit frontend expects: **Server-Sent Events (SSE)** stream
- Backend returns: **Regular JSON response**
- CopilotKit sees the closed connection and throws "[Network] No Content"

The backend uses `add_fastapi_endpoint()` from CopilotKit SDK, which should handle SSE automatically, but something in the flow isn't working as expected.

---

## What's Missing

Based on the investigation, here's what we haven't yet identified:

1. **How to properly trigger SSE streaming** through CopilotKit's protocol
   - Does the initial POST need specific headers?
   - Does CopilotKit need to make a follow-up request to start streaming?
   - Is there a missing configuration in `CopilotKit` React component or `add_fastapi_endpoint()`?

2. **Why the "[Network] No Content" error**
   - The response IS returning content (JSON with agent info)
   - But CopilotKit interprets it as "No Content"
   - This suggests CopilotKit is looking for a different response format

3. **Proper AG-UI integration patterns**
   - We haven't found clear examples of CopilotKit + LangGraphAGUIAgent + FastAPI SSE streaming
   - Official docs may have specific setup requirements we're missing

---

## Next Steps to Enable SSE

### Option A: Deep Dive into CopilotKit Protocol
1. Use browser DevTools Network tab to inspect the exact request/response when CopilotKit tries to connect
2. Check if there are specific headers CopilotKit sets (e.g., `Accept: text/event-stream`)
3. Compare with working CopilotKit examples from official docs/repos

### Option B: Test SSE Independently
1. Create a minimal test endpoint that returns proper SSE format:
   ```python
   @app.get("/test-sse")
   async def test_sse():
       async def event_generator():
           for i in range(5):
               yield f"data: {{\"message\": \"Event {i}\"}}\n\n"
               await asyncio.sleep(1)
       return StreamingResponse(event_generator(), media_type="text/event-stream")
   ```
2. Test with `curl` and browser `EventSource` API
3. Verify SSE basics work before adding CopilotKit

### Option C: Check CopilotKit Source Code
1. Look at `@copilotkit/react-core` source on GitHub
2. Find where it establishes SSE connection
3. Identify what it expects from the server response
4. Adjust backend accordingly

### Option D: Simplify and Use Custom SSE
1. Remove CopilotKit entirely (already done ✅)
2. Implement custom SSE endpoint: `/research-stream`
3. Use native `EventSource` API on frontend
4. Stream agent state updates manually
5. **Pro**: Full control, easier to debug  
   **Con**: More code to write and maintain

---

## Recommended Approach

For the **hackathon demo**, I recommend:

1. **Keep the current stable version** (synchronous HTTP) ✅ Already deployed
2. **Test SSE independently** (Option B) to verify infrastructure supports it
3. **Deep dive CopilotKit protocol** (Option A) using browser DevTools
4. **If SSE remains blocked**, implement custom streaming (Option D) post-hackathon

The synchronous version is **fully functional** for the demo. Real-time streaming is a nice-to-have enhancement but not critical for core functionality.

---

## Files Modified

### Removed CopilotKit (Current Stable Version)
- `frontend/package.json`: Removed `@copilotkit/react-core` and `@copilotkit/react-ui`
- `frontend/app/layout.tsx`: Removed `<CopilotKit>` wrapper
- `frontend/app/components/AgentFlowDisplay.tsx`: Simplified to static "idle" message

### Backend (SSE Endpoint Still Present)
- `backend/main.py`: `/copilotkit/` endpoint is functional via `add_fastapi_endpoint()`
- `backend/requirements.txt`: Still has `copilotkit==0.1.70`

---

## Testing the Stable Version

```bash
# Test research endpoint (synchronous)
curl -X POST "http://af3615e06391145bc88022ac024a36ca-bd296660cda3522f.elb.us-west-2.amazonaws.com/research" \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "What are typical import duties for electronics from China?",
    "report_organization": "Create a comprehensive report",
    "collection": "",
    "search_web": true
  }'
```

Expected: Returns full JSON response with `final_report`, `citations`, `execution_path`, etc.

---

## Conclusion

SSE investigation revealed that the backend endpoint is working, versions are compatible, but there's a protocol mismatch preventing SSE streaming. The application now runs **stably without SSE** using synchronous HTTP. Further SSE work can continue post-hackathon as an enhancement.

---

**Status**: ✅ Application stable and functional for hackathon demo  
**Next**: Deploy official NVIDIA RAG Blueprint to fix RAG collection functionality

