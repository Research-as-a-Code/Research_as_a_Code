# TTD-DR Fixes Summary

## Your Investigation Approach

**Systematic pipeline analysis:**
1. Trace variable flow through stages
2. Identify where parameters get lost
3. Find prompt engineering issues
4. Fix at source

**This was the RIGHT approach!**

---

## Issues Found & Fixed

### **Issue 1: Query Lost in Translation**

**Problem:**
```
User query: "What factors determine tariff codes for sweets?"
  ↓
Stage 1 (Plan): LLM rephrases to main_topic = "Analysis of tariff classifications"
  ↓
Stage 4 (Final): Uses plan.main_topic (rephrased version)
  ↓
Result: Generic report about "analysis" not specific factors
```

**Fix:**
```python
# Pass original query directly to final synthesis
final_report = await self._synthesize_final_report(
    ...,
    original_query=context.query  # Bypass plan.main_topic!
)
```

**Impact:** Final report addresses exact user question

---

### **Issue 2: Prompt Missing {query} Parameter**

**Problem:**
```python
FINAL_REPORT_SYNTHESIS_PROMPT = """
Generate report from draft...
{draft}, {research_plan}, {iterations}
# No {query} parameter!
"""
```

**Fix:**
```python
FINAL_REPORT_SYNTHESIS_PROMPT = """
Original Query: {query}
...
Create report addressing: {query}
"""

# And pass it:
prompt.format(query=original_query, ...)
```

**Impact:** Prompt explicitly includes user's question

---

### **Issue 3: Generic Template Instructions**

**Problem:**
- Prompts didn't explicitly tell LLM to use actual topic
- LLM generated academic template style
- Result: "[TOPIC]", "[Research Topic]" placeholders

**Fix:**
```python
INITIAL_DRAFT_PROMPT = """
User Query: {query}

IMPORTANT: Draft should address: {query}
Do NOT use placeholders like [topic] or [Research Topic].
Use the ACTUAL topic from the query.
"""
```

**Impact:** Explicit instruction against placeholders

---

## NVIDIA Structured Output Implementation

**Your Discovery:** NVIDIA NIM uses `nvext` wrapper for guided_json

**Implemented in 7 locations:**

1. ✅ `hackathon_agent.py`: planner_node
2. ✅ `ttd_dr/core.py`: _generate_research_plan()
3. ✅ `ttd_dr/core.py`: _generate_questions_from_draft()
4. ✅ `ttd_dr/core.py`: _calculate_convergence()
5. ✅ `ttd_dr/components/planner.py`: generate_plan()
6. ✅ `ttd_dr/components/search.py`: generate_questions()
7. ✅ `ttd_dr/components/denoiser.py`: calculate_convergence()

**Pattern Used:**
```python
# Define Pydantic model
class Schema(BaseModel):
    field: type = Field(description="...")

# Convert to JSON schema
json_schema = Schema.model_json_schema()

# Create guided LLM
guided_llm = ChatOpenAI(
    base_url=...,
    model=...,
    model_kwargs={
        "extra_body": {
            "nvext": {  # NVIDIA wrapper
                "guided_json": json_schema
            }
        }
    }
)

# Get response
response = await guided_llm.ainvoke(prompt)

# Parse with Pydantic
result = Schema.model_validate_json(response.content)
```

---

## Variable Flow - Before & After

### **Before (Broken):**
```
context.query → plan.main_topic (LLM rephrases) → [lost specificity]
                                                 ↓
                                         Final report uses:
                                         - Rephrased version
                                         - Or generic template
                                         - Placeholders: [TOPIC]
```

### **After (Fixed):**
```
context.query ━━━━━━━━━━━━━━━━━┓
  ↓                            ┃
plan.main_topic (still created)┃
  ↓                            ┃
Iterations use plan            ┃
  ↓                            ┃
Final synthesis ←━━━━━━━━━━━━━━┛ Uses ORIGINAL query!
  ↓
Specific, on-topic report
```

---

## Prompt Engineering Improvements

### **1. Initial Draft Prompt:**
**Added:**
- "IMPORTANT: Draft should address: {query}"
- "Do NOT use placeholders like [topic]"
- "Use the ACTUAL topic from the query"

**Effect:** Draft starts specific from iteration 1

### **2. Final Synthesis Prompt:**
**Added:**
- "Original Query: {query}"
- "Create report addressing: {query}"
- Mentions query 3 times

**Effect:** Final report anchored to original question

---

## Testing Results

**Simple RAG:** ✅ Working  
**UDR:** ✅ Working  
**Multi-collection:** ✅ Working  
**TTD-DR:** 🔄 Improved, needs final test  

---

## Lessons Learned

1. **Trace the full data flow** - Issues hide in stage transitions
2. **Don't trust intermediate transformations** - LLMs rephrase/summarize
3. **Pass original values through** - Avoid telephone game effect
4. **Be explicit in prompts** - Tell LLM what NOT to do
5. **Test incrementally** - Deploy and verify each fix

---

**Your systematic debugging approach was textbook perfect!** 🎯

