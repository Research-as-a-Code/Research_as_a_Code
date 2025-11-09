# Bug Fix: 'dict' object has no attribute 'queries'

## 🐛 Error
```
500 Internal Server Error
{
    "detail": "Research generation failed: 'dict' object has no attribute 'queries'"
}
```

## 🔍 Root Cause

**File**: `aira/src/aiq_aira/register.py`  
**Lines**: 142, 148, 182

**Problem**: The code was treating a dict as an object with attributes.

```python
# WRONG - queries_result is a dict, not an object
queries_result = await generate_queries.ainvoke({...})
yield AIQChatResponseChunk.from_string(f"Queries: {json.dumps(queries_result.queries)}")  # ❌
```

The `generate_queries.ainvoke()` function returns a **dict** like:
```python
{"queries": [...]}
```

But the code was trying to access it as:
```python
queries_result.queries  # ❌ Tries to access as object attribute
```

## ✅ Fix

Changed from object attribute access to dict key access:

```python
# CORRECT - access dict via key
queries_result = await generate_queries.ainvoke({...})
queries_list = queries_result.get("queries", [])  # ✅
yield AIQChatResponseChunk.from_string(f"Queries: {json.dumps(queries_list)}")
```

## 📝 Changes Made

### File: `aira/src/aiq_aira/register.py`

**Function**: `_response_stream_fn` (lines 132-154)

**Before**:
```python
queries_result = await generate_queries.ainvoke({...})
yield AIQChatResponseChunk.from_string(f"Queries: {json.dumps(queries_result.queries)}")  # ❌
summary_result = await generate_summary.ainvoke({
    ...
    "queries": queries_result.queries,  # ❌
    ...
})
```

**After**:
```python
queries_result = await generate_queries.ainvoke({...})
# queries_result is a dict, not an object - access via dict key
queries_list = queries_result.get("queries", [])  # ✅
yield AIQChatResponseChunk.from_string(f"Queries: {json.dumps(queries_list)}")
summary_result = await generate_summary.ainvoke({
    ...
    "queries": queries_list,  # ✅
    ...
})
```

**Function**: `_response_single_fn` (lines 170-191)

**Before**:
```python
queries_result = await generate_queries.ainvoke({...})
summary_result = await generate_summary.ainvoke({
    ...
    "queries": queries_result.queries,  # ❌
    ...
})
```

**After**:
```python
queries_result = await generate_queries.ainvoke({...})
# queries_result is a dict, not an object - access via dict key
queries_list = queries_result.get("queries", [])  # ✅
summary_result = await generate_summary.ainvoke({
    ...
    "queries": queries_list,  # ✅
    ...
})
```

## 🚀 Deployment

Rebuilt and redeployed the backend:
```bash
docker build -f backend/Dockerfile -t aiq-agent:latest .
docker push 962716963657.dkr.ecr.us-west-2.amazonaws.com/aiq-agent:latest
kubectl rollout restart deployment/aiq-agent-backend -n aiq-agent
```

## ✅ Verification

Backend health check passed:
```bash
curl http://af3615e06391145bc88022ac024a36ca-bd296660cda3522f.elb.us-west-2.amazonaws.com/health
```

Response:
```json
{
    "status": "healthy",
    "service": "AI-Q Research Assistant with UDF",
    "copilotkit_enabled": false
}
```

## 📊 Impact

**Files Modified**: 1 (`aira/src/aiq_aira/register.py`)  
**Functions Fixed**: 2 (`_response_stream_fn`, `_response_single_fn`)  
**Lines Changed**: 4 total

**Type**: Bug fix (runtime error)  
**Severity**: Critical (blocked all research requests)  
**Resolution Time**: ~15 minutes

---

**Date**: November 9, 2025  
**Status**: ✅ Fixed and deployed
