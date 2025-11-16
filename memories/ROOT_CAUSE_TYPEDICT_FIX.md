# Root Cause Analysis: TypedDict vs Object Attribute Access

## 🐛 Error
```
AttributeError: 'dict' object has no attribute 'queries'
```

## 🔍 Root Cause

**The Problem**: Mixing TypedDict (dict-based) state with object attribute access patterns.

### What Happened:

1. **AI-Q Original Code** likely used Pydantic models or classes for state:
   ```python
   class State:
       queries: List[Query]
   
   # Access worked like this:
   state.queries  # ✅ Works with objects
   ```

2. **Hackathon Integration** used LangGraph's TypedDict for state:
   ```python
   class HackathonAgentState(TypedDict):
       queries: List[GeneratedQuery]
   
   # Must access like this:
   state["queries"]  # ✅ Works with TypedDict
   state.queries     # ❌ AttributeError!
   ```

3. **Result**: Code tried to use object syntax (`state.queries`) on a dictionary.

---

## 📝 Files Fixed

### 1. `aira/src/aiq_aira/nodes.py` (Primary Fix)

**Total changes**: 13 locations

**Pattern**:
```python
# BEFORE (object access) ❌
state.queries
state.web_research_results
state.running_summary
state.citations

# AFTER (dict access) ✅
state["queries"]
state["web_research_results"]
state["running_summary"]
state["citations"]
```

**Functions Fixed**:
- `web_research` (lines 134-136)
- `summarize_sources` (lines 182-183, 195)
- `reflect_on_summary` (lines 220, 252)
- `reflect_on_summary` loop (lines 288-298, 309-315)
- `finalize_summary` (lines 329, 337, 344-346, 359-361)

### 2. `aira/src/aiq_aira/register.py` (Secondary Fix)

**Changes**: 2 functions

```python
# BEFORE ❌
queries_result.queries

# AFTER ✅
queries_result.get("queries", [])
```

---

## 🧪 Why This Matters

### TypedDict in Python:
```python
from typing import TypedDict

class MyState(TypedDict):
    queries: list
    
state = MyState(queries=[])

# These are DIFFERENT:
state["queries"]  # ✅ Returns the list
state.queries     # ❌ AttributeError (TypedDict is still a dict!)
```

### Why LangGraph Uses TypedDict:
1. **Type Safety**: Static type checkers can validate state structure
2. **Serialization**: Easy to convert to/from JSON
3. **Performance**: Dict access is fast
4. **Immutability**: Can track state changes better

---

## 📊 Impact Analysis

### Before Fix:
- **Error Rate**: 100% (all research requests failed)
- **Error Location**: Multiple places in `nodes.py`
- **User Impact**: Complete system failure

### After Fix:
- **Error Rate**: 0% (expected)
- **Code Consistency**: All state access now uses dict syntax
- **Performance**: No change (dict access is just as fast)

---

## ✅ Testing

Test the fix with:

**Frontend URL**: http://af2f4f77d44fb4b41bc00856345951e2-974749261.us-west-2.elb.amazonaws.com

**Example Query**:
- Topic: `Tariff of replacement batteries for a Raritan remote management card`
- Collection: `us_tariffs`

**Expected Flow**:
1. ✅ Query generation (`state["queries"]` works)
2. ✅ Web research (`state["web_research_results"]` works)
3. ✅ Summary (`state["running_summary"]` works)
4. ✅ Final report with citations

---

## 🎯 Key Takeaway

**Always match your state access pattern to your state definition:**

| State Type | Access Pattern | Example |
|------------|----------------|---------|
| **TypedDict** | Dict syntax | `state["key"]` |
| **Pydantic Model** | Attribute syntax | `state.key` |
| **Class** | Attribute syntax | `state.key` |
| **Regular dict** | Dict syntax | `state["key"]` |

---

## 📝 Prevention

To prevent this in the future:

1. **Consistent Type Hints**: Use TypedDict everywhere or Pydantic everywhere
2. **Linting**: Configure pylance/mypy to catch these
3. **Type Checking**: Run `mypy` in CI/CD

---

**Date**: November 9, 2025  
**Status**: ✅ Root cause identified and fixed  
**Files Modified**: 2 (`nodes.py`, `register.py`)  
**Total Changes**: 15 locations
