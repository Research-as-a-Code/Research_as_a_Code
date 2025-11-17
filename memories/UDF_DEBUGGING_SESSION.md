# UDF (Universal Deep Research) Integration - Debugging Session

**Date**: November 16, 2025  
**Status**: 🟡 In Progress - Code generation working, execution has bugs  
**Session Goal**: Debug and fix the dynamic strategy (UDF) feature for complex research queries

---

## 📋 Background

The AI-Q agent has two research modes:
1. **Simple RAG**: Standard search-and-synthesize for straightforward queries
2. **Dynamic Strategy (UDF)**: Compiles natural language research plans into executable Python code for complex multi-step research

The UDF feature is based on NVIDIA's Universal Deep Research prototype and allows the agent to dynamically generate and execute custom research workflows.

---

## 🎯 Test Query Used

```json
{
  "topic": "What are factors I need to consider (such as weight, important ingredients) when I need to decide tariff codes for various sweets?",
  "report_organization": "Create a comprehensive report with introduction, detailed analysis, and conclusion, perform a deep research. Utilize the tariff collection.",
  "collection_name": "us_tariffs"
}
```

**Expected Behavior**: Agent should:
1. Recognize this as complex (multiple factors, domain-specific)
2. Choose DYNAMIC_STRATEGY
3. Compile a multi-step research plan into Python code
4. Execute the code to search RAG, synthesize findings
5. Return a comprehensive report

---

## ✅ What's Working

### Infrastructure
- ✅ EKS cluster fully operational
- ✅ NIMs (Nemotron Nano 8B, Arctic Embed) healthy
- ✅ Milvus vector DB with `us_tariffs` collection populated
- ✅ Backend (2 pods) and Frontend (2 pods) running
- ✅ All services accessible via LoadBalancers

### Agent Flow
- ✅ **Planner node** correctly identifies complex queries
- ✅ **Strategy selection** works: returns `"strategy": "DYNAMIC_STRATEGY"`
- ✅ **UDF compiler** invoked successfully
- ✅ **LLM generates Python code** for the research strategy
- ✅ **Code extraction** from markdown blocks works

### Recent Improvements (This Session)
1. **Enhanced compiler prompt** (`aira/src/aiq_aira/udf_integration.py`):
   - Added detailed example for tariff research
   - Made return statement requirement more explicit
   - Improved tool documentation
   
2. **Added comprehensive logging**:
   - Compiled code is now logged line-by-line
   - Better error tracking

3. **Added safety net**:
   - Handles `None` returns gracefully
   - Provides fallback error messages

---

## ❌ Current Issue

### Error Message
```
❌ UDF execution failed: object NoneType can't be used in 'await' expression
```

### Root Cause Analysis

The LLM-generated Python code has a bug where it tries to `await` non-async functions. From the streamed tokens, we can see the generated code includes:

```python
# ❌ INCORRECT - append() returns None and is not async
await log.append("Conducting literature review")

# ❌ INCORRECT - await on non-async result
tariff_results = await search_rag(...)
```

**Why this happens**:
- The LLM is being overly cautious about async/await
- The prompt says "All code must be async/await compatible" 
- The LLM interprets this as "await everything"
- But `list.append()` returns `None` and isn't awaitable

### Expected Correct Code
```python
# ✅ CORRECT
log.append("Conducting literature review")  # No await
tariff_results = await search_rag(...)  # Await the async function
```

---

## 🔍 Evidence from Logs

**From streamed tokens** (captured during test):
```
'await', 'log', '.append', '("', 'Conducting', 'literature', 'review', '")\n'
'tariff', '_results', '=', 'await', 'search', '_rag', '(\n'
```

This confirms the LLM is generating:
1. `await log.append(...)` ❌
2. `await search_rag(...)` ✅

The first is the problem.

---

## 📁 Key Files Modified

### 1. `aira/src/aiq_aira/udf_integration.py`

**Changes Made**:
- Improved `STRATEGY_COMPILER_PROMPT` (lines 61-125)
- Added explicit tariff research example
- Enhanced documentation of available tools
- Added logging for compiled code (lines 166-172)
- Safety net for `None` returns (lines 347-353)

**Current Prompt Structure**:
```
Available Tools:
- search_rag(query: str, collection: str) -> Dict[str, Any]
- search_web(query: str) -> List[Dict[str, str]]
- synthesize_findings(data: List[Dict]) -> str

CRITICAL REQUIREMENTS:
1. All code MUST be async/await compatible
2. Use try/except for error handling
3. ABSOLUTELY MUST end with a return statement
4. The return MUST be a dict with keys: "report", "sources", "log"
...

EXAMPLE - Tariff Research:
[Full working example provided]
```

### 2. `infrastructure/kubernetes/deploy-agent.sh`
- Used to rebuild and deploy backend with UDF changes
- Successfully built image: `sha256:bc3e0d57dc8b512e8a61cc23c8fdb252ec5f300d3d9b060249539c68340caba3`

### 3. Cluster Management Scripts
- Created `/infrastructure/scripts/sleep-cluster.sh` (smart sleep)
- Created `/infrastructure/scripts/wake-cluster.sh` (quick wake)
- Created `/infrastructure/scripts/monitor-cluster-readiness.sh` (health checks)
- Renamed old scripts to `deep-*` variants for clarity

---

## 🧪 Test Results Timeline

### Test 1: Before improvements
```
Result: ❌ "Strategy must return a dict, got <class 'NoneType'>"
Issue: UDF code didn't include return statement
```

### Test 2: After prompt improvements
```
Result: ❌ "UDF execution completed but no report was generated"
Issue: Hit safety net, code returned None
```

### Test 3: After forcing pod restart
```
Result: ❌ "object NoneType can't be used in 'await' expression"
Issue: Code has `await log.append()` bug
Progress: ✅ At least we're executing now!
```

---

## 🔧 Attempted Fixes

1. ✅ **Improved compiler prompt** - Better examples, clearer requirements
2. ✅ **Added safety net** - Handles None gracefully
3. ✅ **Enhanced logging** - Can see compiled code (in theory)
4. ⏳ **Need to fix**: Prompt doesn't warn against awaiting non-async operations

---

## 🎯 Next Steps to Fix

### Immediate Actions

1. **Update compiler prompt** to explicitly list what NOT to await:
   ```
   DO NOT await these:
   - list.append(), list.extend() 
   - dict operations
   - Variable assignments
   - String operations
   
   ONLY await these:
   - search_rag()
   - search_web()
   - synthesize_findings()
   ```

2. **Add code validation** before execution:
   - Check for `await.*\.append` pattern
   - Warn if found
   - Optionally auto-fix

3. **Improve error messages** to show the actual generated code

4. **Test with simpler query** first:
   ```
   "Tell me about tariff codes for chocolate"
   ```

### Testing Strategy

1. Test with simple query (single RAG lookup)
2. Test with medium query (RAG + web search)
3. Test with complex query (multi-step synthesis)
4. Test error handling
5. Test with actual tariff query

---

## 📊 Cluster Status

```bash
# Backend
kubectl get pods -n aiq-agent -l component=backend
# NAME                                READY   STATUS    RESTARTS   AGE
# aiq-agent-backend-5984f84794-xnlgr   1/1     Running   0          15m
# aiq-agent-backend-5984f84794-zbnj6   1/1     Running   0          15m

# NIMs
kubectl get pods -n nim
# embedding-nim-6d8b578b96-4nlpx      1/1     Running   0          3h
# llama-instruct-nim-ddcdc899-zwtht   1/1     Running   0          3h

# URLs
Backend:  http://af3615e06391145bc88022ac024a36ca-bd296660cda3522f.elb.us-west-2.amazonaws.com
Frontend: http://af2f4f77d44fb4b41bc00856345951e2-974749261.us-west-2.elb.amazonaws.com
```

---

## 💡 Key Insights

1. **UDF infrastructure is solid** - Compiler, executor, integration all working
2. **Prompt engineering is critical** - Small changes in prompt = big changes in generated code
3. **LLMs over-generalize** - "be async" → "await everything"
4. **Need better validation** - Catch common errors before execution
5. **Logging is essential** - Took multiple attempts to see generated code

---

## 📚 References

### NVIDIA UDF Prototype
- Original paper: https://arxiv.org/abs/2509.00244
- GitHub: https://github.com/NVlabs/UniversalDeepResearch
- Key concept: "Strategy-as-Code" - compile natural language plans to executable code

### Files to Reference
- `Designing NVIDIA AI Research Agent.md` - Original architecture design
- `aira/src/aiq_aira/hackathon_agent.py` - Agent graph with UDF node
- `aira/src/aiq_aira/udf_integration.py` - UDF compiler and executor
- `backend/main.py` - FastAPI integration

---

## 🎓 Lessons Learned

1. **Prompt precision matters**: The LLM follows instructions literally, sometimes too literally
2. **Validation before execution**: Catch errors early, fail fast
3. **Streaming debugging**: Watching token streams reveals generation patterns
4. **Infrastructure first**: Having a solid cluster saved hours of debugging
5. **Incremental testing**: Test each component independently before integration

---

## 📝 Commands for Quick Access

```bash
# Test endpoint
curl -X POST "http://<BACKEND_URL>/research/stream" \
  -H "Content-Type: application/json" \
  -d '{"topic": "...", "report_organization": "...", "collection_name": "us_tariffs"}'

# Check logs
kubectl logs -n aiq-agent -l component=backend --tail=500 | grep -A 30 "COMPILED UDF"

# Watch logs live
kubectl logs -n aiq-agent -l component=backend -f

# Restart backend
kubectl rollout restart deployment/aiq-agent-backend -n aiq-agent

# Deploy changes
cd infrastructure/kubernetes && bash deploy-agent.sh
```

---

**Status**: Ready to continue debugging with improved prompt and validation.

