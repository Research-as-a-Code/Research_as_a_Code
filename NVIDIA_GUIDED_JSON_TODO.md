# NVIDIA Guided JSON - Implementation Guide

## Discovery (Nov 29, 2025)

Found that NVIDIA NIM **DOES support structured output**, just not through LangChain's standard `.with_structured_output()` method.

**Source:** [NVIDIA NIM Structured Generation Documentation](https://docs.nvidia.com/nim/large-language-models/latest/structured-generation.html)

---

## The NVIDIA Way

### ✅ **VERIFIED WORKING FORMAT (Dec 21, 2025):**

For **direct API calls**, `nvext` must be at the **ROOT level** of the request body:
```python
response = client.chat.completions.create(
    model="nvidia/llama-3.1-nemotron-nano-8b-v1",
    messages=messages,
    extra_body={"nvext": {"guided_json": json_schema}},  # ← Use extra_body for OpenAI client
)
```

### **For LangChain ChatOpenAI:**
Use `model_kwargs` with `extra_body` to pass NVIDIA-specific parameters:
```python
llm = ChatOpenAI(
    base_url=nim_url,
    model="nvidia/llama-3.1-nemotron-nano-8b-v1",
    model_kwargs={
        "extra_body": {"nvext": {"guided_json": json_schema}}  # ← MUST use extra_body!
    }
)
```

### ❌ **FORMATS THAT DON'T WORK:**
```python
# Direct nvext fails - OpenAI client doesn't recognize it
model_kwargs={"nvext": {...}}  # ❌ AsyncCompletions.create() got unexpected kwarg 'nvext'

# guided_json without nvext wrapper
extra_body={"guided_json": json_schema}  # ❌ Must be nested in nvext
```

**Tested on:** NIM LLM API v1.8.4, vLLM backend, llama-3.1-nemotron-nano-8b-v1

**Reference:** [NIM 1.12.0 Structured Generation](https://docs.nvidia.com/nim/large-language-models/1.12.0/structured-generation.html)

---

## Implementation Approach

### **For LangChain ChatOpenAI:**

```python
from pydantic import BaseModel

# Define Pydantic model
class PlanningDecision(BaseModel):
    strategy: str
    rationale: str
    plan: str = ""

# Convert to JSON schema
json_schema = PlanningDecision.model_json_schema()

# Create LLM with model_kwargs - MUST use extra_body to wrap nvext!
llm = ChatOpenAI(
    base_url=nim_url,
    model="nvidia/llama-3.1-nemotron-nano-8b-v1",
    model_kwargs={
        "extra_body": {"nvext": {"guided_json": json_schema}}  # ← Correct format
    }
)

# Use normally
response = await llm.ainvoke(prompt)
# Response will be valid JSON matching schema!

# Parse back to Pydantic
result = PlanningDecision.model_validate_json(response.content)
```

---

## Testing Plan

### **Step 1: Local Test (needs cluster access)**
```python
# Test both formats to see which your NIM version supports
# From backend pod or with port-forward
```

### **Step 2: Implement in One Location**
- Start with planner_node (most critical)
- Test thoroughly
- Verify no errors

### **Step 3: Roll Out to All Locations**
If successful:
- hackathon_agent.py: planner_node
- ttd_dr/components/planner.py
- ttd_dr/core.py (3 locations)
- ttd_dr/components/denoiser.py
- ttd_dr/components/evolver.py

---

## Benefits

✅ **Type safety:** Guaranteed valid JSON  
✅ **No parsing errors:** NIM validates at generation time  
✅ **Better reliability:** Eliminates NoneType bugs  
✅ **Pydantic integration:** Easy model conversion  
✅ **Performance:** xgrammar backend is fast  

---

## Current Workaround

**Manual parsing works fine:**
- ✅ Proven in production
- ✅ Has error handling
- ✅ No blocking issues
- ⚠️ Just less elegant

**This is a quality-of-life improvement, not critical.**

---

## Implementation Checklist

- [x] Test stable API: `extra_body={"guided_json": schema}` → ❌ Does NOT work
- [x] Test older API: `extra_body={"nvext": {"guided_json": schema}}` → ✅ WORKS with LangChain!
- [x] Test root-level: `model_kwargs={"nvext": {...}}` → ❌ OpenAI client rejects unknown kwargs
- [x] Determine which format your NIM version supports → `extra_body` wrapper required for LangChain
- [x] Implement in planner_node → Updated to use `model_kwargs={"extra_body": {"nvext": {...}}}`
- [x] Roll out to TTD-DR components:
  - core.py (3 locations)
  - evaluator.py
  - planner.py
  - denoiser.py
  - red_team.py
  - context_pruner.py
  - search.py
  - evolver.py
- [x] Update documentation with working approach
- [x] Update test cases to reflect correct format

---

## Notes

**Why LangChain's `.with_structured_output()` failed:**
- Uses OpenAI's `response_format` parameter
- NVIDIA NIM doesn't support that parameter
- Needs NVIDIA-specific `guided_json` instead

**Key insight:**
- NVIDIA has their own structured output API
- It's more powerful (regex, grammar support too!)
- Just needs different integration approach

---

## Estimated Effort

**If guided_json works:**
- Testing: 30 minutes
- Implementation: 1-2 hours
- High value improvement

**If it doesn't work:**
- Keep current manual parsing (works fine)
- Document as API limitation
- No changes needed

---

**Status:** ✅ **COMPLETED** (December 21, 2025)

All TTD-DR components updated with correct `extra_body` wrapper format. Deployed and verified working on EKS cluster with:
- NIM LLM API with TensorRT-LLM backend
- `nvidia/llama-3.1-nemotron-nano-8b-v1` model
- 16K context, 32 max batch size

**Key learnings:**
1. LangChain's ChatOpenAI passes `model_kwargs` to OpenAI client's `create()` method
2. OpenAI client validates kwargs and rejects unknown ones like `nvext`
3. Must use `extra_body` to pass NVIDIA-specific parameters: `model_kwargs={"extra_body": {"nvext": {"guided_json": schema}}}`
4. The `extra_body` contents are added to the HTTP request body, putting `nvext` at root level as NVIDIA expects 🎯

