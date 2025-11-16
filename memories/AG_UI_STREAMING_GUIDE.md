# 🎯 AG-UI Real-Time Streaming Guide
**Date**: November 10, 2025, 10:50 PM PST

## ✅ Implementation Complete!

Your AI-Q Research Assistant now has **CopilotKit AG-UI real-time streaming** integrated!

---

## 🏗️ What Was Implemented

### Backend (Python)
- **CopilotKit SDK**: Integrated with `LangGraphAGUIAgent`
- **Agent Name**: `ai_q_researcher` (must match frontend)
- **Endpoint**: `/copilotkit/` (Server-Sent Events)
- **State Streaming**: Automatic via LangGraph execution

### Frontend (React/Next.js)
- **CopilotKit Provider**: Added to `layout.tsx`
- **Runtime URL**: `${BACKEND_URL}/copilotkit/` (with trailing slash!)
- **AG-UI Hook**: `useCoAgentStateRender` in `AgentFlowDisplay.tsx`
- **Real-Time Updates**: Subscribes to SSE stream from backend

---

## 🎨 What You'll See in the UI

When you submit a research request, the **"🤖 Agentic Flow"** panel will display:

### 1. Current Phase Indicator
```
🔄 Processing
🤔 Planning Strategy
📋 Query Generation
🔍 Research
📝 Synthesis
🔄 Reflection
📄 Finalization
✅ Complete
```

### 2. Strategy Path
```
🚀 Dynamic UDF Strategy
  OR
📚 Simple RAG Pipeline
```

### 3. Execution Logs (Real-Time)
```
→ ✅ Strategy: SIMPLE_RAG
→ 💡 Rationale: The topic...
→ 📋 Generating research queries
→ 🔍 Conducting research...
→ Processing...  [animated pulse when active]
```

### 4. Generated Queries
```
Generated Queries (3)
1. Query text 1
2. Query text 2
3. Query text 3
```

### 5. Sources Retrieved
```
📚 12 sources collected
```

### 6. Completion Indicator
```
🎉 Research Complete! Report ready (15.2k chars)
```

---

## 🧪 How to Test

### Step 1: Open the Frontend
**URL**: http://af2f4f77d44fb4b41bc00856345951e2-974749261.us-west-2.elb.amazonaws.com

### Step 2: Submit a Research Request
1. Enter topic: "What are the latest developments in AI?"
2. Leave collection empty (or use "us_tariffs" for RAG test)
3. Check "Search Web"
4. Click "Start Research"

### Step 3: Watch the Agentic Flow Panel
You should see:
- ✅ Initial state: "Agent is idle. Submit a research request to begin."
- ✅ Phase changes in real-time as agent processes
- ✅ Logs appearing one by one
- ✅ Animated pulse indicator during active processing
- ✅ Final completion message

### Step 4: Check Browser Console
Open browser DevTools (F12) and check Console tab:
- ✅ No "[Network] No Content" errors
- ✅ No CopilotKit errors
- ✅ SSE connection established (you may see EventSource logs)

---

## 🔧 Technical Details

### SSE Connection Flow
```
Browser (Frontend)
    ↓ [HTTP GET with Accept: text/event-stream]
/copilotkit/ endpoint
    ↓ [Establishes SSE connection]
LangGraphAGUIAgent
    ↓ [Streams state updates as events]
useCoAgentStateRender hook
    ↓ [Receives events and updates UI]
AgentFlowDisplay component
    ↓ [Renders real-time visualization]
```

### Backend SSE Endpoint
```bash
# Test SSE endpoint
curl -N -H "Accept: text/event-stream" \
  "http://af3615e06391145bc88022ac024a36ca-bd296660cda3522f.elb.us-west-2.amazonaws.com/copilotkit/"
```

### Agent State Interface
```typescript
interface AgentState {
  research_prompt: string;
  plan: string;
  queries: Array<{ query: string }>;
  sources: string[];
  final_report: string;
  logs: string[];
  udf_strategy?: string;
  udf_result?: {
    success: boolean;
    sources?: string[];
  };
}
```

---

## 🐛 Troubleshooting

### Issue: Page crashes on load with "[Network] No Content"
**Cause**: Incorrect CopilotKit runtime URL (missing trailing slash)
**Fix**: ✅ Already fixed - uses `/copilotkit/` with trailing slash

### Issue: No real-time updates, only see final result
**Possible Causes**:
1. Browser console shows SSE connection error
2. Backend not emitting state updates
3. Agent name mismatch (frontend vs backend)

**Debug Steps**:
```bash
# 1. Check backend logs for SSE activity
kubectl logs -n aiq-agent -l component=backend --tail=100 | grep -i sse

# 2. Test /copilotkit/ endpoint
curl -s http://BACKEND_URL/copilotkit/ -H "Content-Type: application/json" -d '{"messages":[]}'

# 3. Check agent name in backend
kubectl logs -n aiq-agent -l component=backend --tail=100 | grep "ai_q_researcher"
```

### Issue: AgentFlowDisplay shows "Agent is idle" even during processing
**Cause**: CopilotKit not receiving state updates via SSE
**Fix**: Check that:
- Agent name matches: `ai_q_researcher` (both frontend and backend)
- Runtime URL has trailing slash: `/copilotkit/`
- Backend is using `LangGraphAGUIAgent` wrapper

---

## 📊 Verification Checklist

- ✅ Page loads without crashes (HTTP 200)
- ✅ No "[Network] No Content" error in console
- ✅ Backend `/copilotkit/` endpoint returns valid JSON
- ✅ Backend `/research` endpoint works correctly
- ✅ AgentFlowDisplay component has `useCoAgentStateRender`
- ✅ Layout.tsx has CopilotKit provider with correct URL
- ✅ Agent name matches in backend and frontend

---

## 🎯 Expected Behavior

### Before Research Request
```
🤖 Agentic Flow
  Agent is idle. Submit a research request to begin.
  ✨ Real-time AG-UI streaming enabled via SSE
```

### During Research (Real-Time Updates)
```
🤖 Agentic Flow

Current Phase
🔄 🔍 Research  ●  [pulsing dot]
Node: web_research

Strategy Selected
🚀 Dynamic UDF Strategy
Plan: The research will explore...

Execution Log (12 entries)
→ ✅ Strategy: SIMPLE_RAG
→ 💡 Rationale: The topic...
→ 📋 Generating research queries
→ 🔍 Conducting research...
→ Processing...  [animated]

Generated Queries (3)
1. What are the latest AI developments...
2. How are large language models...
3. What breakthroughs have occurred...

Sources Retrieved
📚 12 sources collected
```

### After Completion
```
Current Phase
✅ Complete

🎉 Research Complete! Report ready (15.2k chars)
```

---

## 🔗 URLs and Resources

| Resource | URL |
|----------|-----|
| Frontend | http://af2f4f77d44fb4b41bc00856345951e2-974749261.us-west-2.elb.amazonaws.com |
| Backend API | http://af3615e06391145bc88022ac024a36ca-bd296660cda3522f.elb.us-west-2.amazonaws.com |
| CopilotKit Endpoint | http://af3615e06391145bc88022ac024a36ca-bd296660cda3522f.elb.us-west-2.amazonaws.com/copilotkit/ |
| Research Endpoint | http://af3615e06391145bc88022ac024a36ca-bd296660cda3522f.elb.us-west-2.amazonaws.com/research |

---

## 📚 Files Modified

### Backend
- `backend/main.py` - CopilotKit SDK integration (already configured)

### Frontend
- `frontend/package.json` - Added CopilotKit dependencies v1.3.0
- `frontend/app/layout.tsx` - Added CopilotKit provider
- `frontend/app/components/AgentFlowDisplay.tsx` - Implemented `useCoAgentStateRender`
- `frontend/Dockerfile` - Changed to `npm install` for new dependencies

---

## 🎉 Summary

**Implementation Status**: ✅ COMPLETE

Your application now has:
- ✅ Real-time agent state visualization
- ✅ SSE streaming from backend to frontend
- ✅ Phase-by-phase execution tracking
- ✅ Live log updates
- ✅ Visual indicators for current activity
- ✅ No page load crashes
- ✅ Stable CopilotKit integration

**Next Steps**:
1. Open the frontend URL in your browser
2. Submit a research request
3. Watch the Agentic Flow panel update in real-time!

---

**Enjoy your real-time agentic workflow visualization!** 🚀

