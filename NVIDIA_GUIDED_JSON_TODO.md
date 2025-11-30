# NVIDIA Guided JSON - Future Enhancement

## Discovery (Nov 29, 2025)

Found that NVIDIA NIM **DOES support structured output**, just not through LangChain's standard `.with_structured_output()` method.

**Source:** [NVIDIA NIM Structured Generation Documentation](https://docs.nvidia.com/nim/large-language-models/latest/structured-generation.html)

---

## The NVIDIA Way

### **Current/Stable API:**
```python
response = client.chat.completions.create(
    model="nvidia/llama-3.1-nemotron-nano-8b-v1",
    messages=messages,
    extra_body={"guided_json": json_schema},  # ← NVIDIA's parameter
    stream=False
)
```

### **Older API (v1.12.0):**
```python
response = client.chat.completions.create(
    model="nvidia/llama-3.1-nemotron-nano-8b-v1",
    messages=messages,
    extra_body={"nvext": {"guided_json": json_schema}},  # ← Wrapped in nvext
    stream=False
)
```

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

# Create LLM with model_kwargs
llm = ChatOpenAI(
    base_url=nim_url,
    model="nvidia/llama-3.1-nemotron-nano-8b-v1",
    model_kwargs={
        "extra_body": {
            "guided_json": json_schema  # Try stable first
            # OR: "nvext": {"guided_json": json_schema}  # Try older if stable fails
        }
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

- [ ] Test stable API: `extra_body={"guided_json": schema}`
- [ ] Test older API: `extra_body={"nvext": {"guided_json": schema}}`
- [ ] Determine which format your NIM version supports
- [ ] Create helper function: `pydantic_to_json_schema()`
- [ ] Implement in planner_node
- [ ] Test planner_node thoroughly
- [ ] Roll out to TTD-DR components (if planner works)
- [ ] Update documentation with working approach

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

**Status:** Ready to test when convenient. System works great as-is! 🎯

