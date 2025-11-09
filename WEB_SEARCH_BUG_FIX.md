# Critical Bug Fix: Web Search Not Triggered with Empty Collection

## 🐛 The Bug

**Symptom**: Generic template responses even when web search was enabled and collection was empty.

**User Query**: "What are typical import duties for electronics from China?"
- Collection: `<empty>`
- Web Search: `Yes`
- Result: Generic template without actual data ❌

## 🔍 Root Cause

### The Flawed Logic (Before Fix)

**File**: `aira/src/aiq_aira/search_utils.py` lines 155-162

```python
# Optionally run a web search if the query is not relevant.
web_answer, web_citation = None, None
if search_web:
    if relevancy["score"] == "no":          # ❌ Only checks relevancy
        result = await search_tavily(query, writer)
    else:
        result = await dummy()               # ❌ Does nothing!
```

### The Problem Flow:

1. **User submits query** with `collection=""` (empty) and `search_web=True`
2. **Agent calls RAG service** with empty collection (line 148)
3. **RAG returns empty/generic result** (no documents to search)
4. **LLM checks relevancy** of empty result
5. **LLM scores it as "yes"** (because no error occurred, just no data)
6. **Web search is SKIPPED** ❌ (line 162: `dummy()` does nothing)
7. **Agent proceeds with empty data** → generates generic template

### Why This Happened:

The code assumed:
- If relevancy score = "no" → use web search
- If relevancy score = "yes" → RAG was good, no need for web search

But when collection is empty:
- RAG doesn't fail (no error)
- RAG doesn't return "irrelevant" data (returns nothing)
- LLM sees nothing and scores it as "relevant" (no contradiction found)
- **Web search never triggers!** ❌

## ✅ The Fix

**File**: `aira/src/aiq_aira/search_utils.py` lines 155-162

```python
# Optionally run a web search if the query is not relevant.
web_answer, web_citation = None, None
if search_web:
    # If no collection specified OR RAG answer not relevant, use web search
    if not collection or relevancy["score"] == "no":  # ✅ Added collection check
        result = await search_tavily(query, writer)
    else:
        result = await dummy()
```

### What Changed:

**Before**:
```python
if relevancy["score"] == "no":
```

**After**:
```python
if not collection or relevancy["score"] == "no":
```

### New Logic:

Web search is triggered when:
1. **No collection specified** (`collection=""` or `collection=None`) ✅
   OR
2. **RAG answer was not relevant** (`relevancy["score"] == "no"`) ✅

This ensures web search always runs when the user doesn't specify a RAG collection.

## 📊 Impact

| Scenario | Before Fix | After Fix |
|----------|-----------|-----------|
| **Empty collection + web search** | Generic template ❌ | Real Tavily results ✅ |
| **Valid collection + relevant RAG** | Uses RAG ✅ | Uses RAG ✅ |
| **Valid collection + irrelevant RAG** | Falls back to Tavily ✅ | Falls back to Tavily ✅ |
| **Empty collection + no web search** | Generic template ✅ | Generic template ✅ |

## 🧪 Testing

**Test Query**: "What are typical import duties for electronics from China?"

**Before Fix**:
```
Collection: <empty>
Web Search: Yes
Result: "This report provides a comprehensive analysis of [Research Topic]..."  ❌
```

**After Fix**:
```
Collection: <empty>
Web Search: Yes
Result: Actual import duty data from Tavily web search  ✅
```

## 🎯 Why The Infrastructure Was Correct

You asked: "Why didn't the Tavily key make it from my local env to the deployment?"

**Answer**: It DID! The infrastructure code was correct:

1. ✅ `agent-deployment.yaml` had `TAVILY_API_KEY: "${TAVILY_API_KEY}"`
2. ✅ `deploy-agent.sh` exported `TAVILY_API_KEY` 
3. ✅ Secret was created with your key
4. ✅ Deployment mounted the secret

**Proof**:
```bash
$ kubectl get secret aiq-agent-secrets -o jsonpath='{.data.TAVILY_API_KEY}' | base64 -d
tvly-dev-9mX5nZ...  # ✅ Your key was there!
```

The issue wasn't the Tavily key - **it was the application logic** not calling Tavily when it should have.

## 🚀 Resolution

1. ✅ Fixed logic in `search_utils.py` to check for empty collection
2. ✅ Rebuilt Docker image
3. ✅ Pushed to ECR
4. ✅ Restarted backend deployment
5. ✅ Web search now works with empty collection

## 📝 Lessons Learned

1. **Environment variables were configured correctly** from the start
2. **The bug was in application logic**, not infrastructure
3. **Always check if optional parameters exist** before checking their values
4. **Empty != Invalid**: An empty collection should trigger different behavior than an invalid one

---

**Date**: November 9, 2025  
**Status**: ✅ Fixed and deployed  
**Severity**: Critical (system gave useless responses when RAG not used)  
**Files Modified**: 1 (`aira/src/aiq_aira/search_utils.py`)  
**Lines Changed**: 1 line (added collection check)  
**Impact**: Web search now works correctly when no RAG collection specified
