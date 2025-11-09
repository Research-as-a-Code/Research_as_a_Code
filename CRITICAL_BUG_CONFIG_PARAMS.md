# Critical Bug: Request Parameters Not Passed to Agent

## 🐛 Symptom
Generic template response with placeholders:
```
"[topic in the same language]"
"Please provide the specific questions and topics..."
```

Even when user specifies:
- Topic: "What's the tariff of Reese's Pieces?"
- Collection: "us_tariffs"

## 🔍 Root Cause

**The backend was not passing per-request parameters through the agent config!**

### What Was Happening:

1. **Frontend** sends request:
   ```json
   {
     "topic": "What's the tariff of Reese's Pieces?",
     "collection": "us_tariffs",
     "report_organization": "...",
     "search_web": true
   }
   ```

2. **Backend** received parameters but only put them in `state`:
   ```python
   initial_state = {
       "research_prompt": request.topic,
       "collection": request.collection,
       ...
   }
   
   # BUG: Used static config without request params!
   final_state = await agent_graph.ainvoke(initial_state, agent_config)  # ❌
   ```

3. **Agent nodes** tried to read from `config["configurable"]`:
   ```python
   # nodes.py
   topic = config["configurable"].get("topic")  # ❌ Returns None!
   collection = config["configurable"].get("collection")  # ❌ Returns None!
   ```

4. **Result**: LLM generated generic template because it had no actual topic or collection!

---

## ✅ The Fix

### File: `backend/main.py`

**BEFORE** (lines 218-220):
```python
# Run agent
try:
    final_state = await agent_graph.ainvoke(initial_state, agent_config)  # ❌ Static config
```

**AFTER** (lines 218-233):
```python
# Run agent
try:
    # Create per-request config with request parameters
    request_config = {
        "configurable": {
            **agent_config["configurable"],  # Base config (LLMs, etc.)
            "topic": request.topic,  # ✅ Add topic
            "collection": request.collection,  # ✅ Add collection
            "report_organization": request.report_organization,  # ✅ Add report org
            "search_web": request.search_web  # ✅ Add search flag
        }
    }
    
    logger.info(f"Running agent with collection: {request.collection}, search_web: {request.search_web}")
    
    final_state = await agent_graph.ainvoke(initial_state, request_config)  # ✅ Per-request config
```

---

## 🎯 Why This Matters

### Impact:

| Component | Before Fix | After Fix |
|-----------|------------|-----------|
| **Topic** | None → generic template | Actual user topic |
| **Collection** | None → no RAG search | "us_tariffs" → searches PDFs |
| **Report Org** | None → generic structure | User's requested format |
| **Search Web** | Default (True) | User's choice |

### Example Flow After Fix:

1. User asks: "What's the tariff of Reese's Pieces?"
2. Collection: "us_tariffs"
3. Agent receives both parameters ✅
4. Agent queries RAG for Reese's Pieces in tariff PDFs ✅
5. Agent returns actual tariff info ✅

---

## 📝 Key Concept: LangGraph Config Pattern

LangGraph agents use **two separate data structures**:

### 1. State (mutable data that flows through nodes):
```python
state = {
    "research_prompt": "...",
    "queries": [...],
    "running_summary": "..."
}
```

### 2. Config (immutable parameters passed to all nodes):
```python
config = {
    "configurable": {
        "topic": "...",  # Request params go here!
        "collection": "...",
        "llm": llm_instance
    }
}
```

**Nodes read config via**: `config["configurable"].get("topic")`

**The Fix**: Merge per-request params into config before invoking agent!

---

## 🧪 Testing

**Before Fix:**
- Input: "What's the tariff of Reese's Pieces?" + "us_tariffs"
- Output: Generic template with "[topic in the same language]"

**After Fix:**
- Input: "What's the tariff of Reese's Pieces?" + "us_tariffs"
- Output: Actual tariff information from US Customs PDFs

---

## 📊 Related Issues Fixed

This fix also resolves:
1. ✅ RAG collection parameter not working
2. ✅ Web search toggle not working
3. ✅ Report organization not respected
4. ✅ Generic responses instead of specific answers

---

**Date**: November 9, 2025  
**Status**: ✅ Fixed and deployed  
**Severity**: Critical (system gave useless responses)  
**Files Modified**: 1 (`backend/main.py`)  
**Lines Changed**: 15 lines (added config merge logic)
