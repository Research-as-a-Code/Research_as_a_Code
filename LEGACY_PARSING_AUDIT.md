# Legacy JSON Parsing Audit

## Locations Using Manual json.loads() Instead of Structured Output

Found **8 locations** that should be converted to structured output for better reliability.

---

## Priority 1: Main Agent Code (hackathon_agent.py)

### ✅ planner_node - FIXED
**Status:** Converted to structured output  
**Impact:** Eliminates NoneType bugs, type-safe planning

---

## Priority 2: TTD-DR Components

### 1. ttd_dr/components/planner.py - Line 115
```python
# Current:
result = json.loads(response)

# Should be:
class ResearchPlanSchema(BaseModel):
    main_topic: str
    key_areas: List[str]
    sub_questions: List[str]
    ...

structured_llm = llm.with_structured_output(ResearchPlanSchema)
plan = await structured_llm.ainvoke(...)
```

**Impact:** Robust research plan generation

---

### 2. ttd_dr/components/search.py - Line 375
```python
# Current:
return json.loads(response)

# Should be:
class QuestionGeneration(BaseModel):
    questions: List[Dict[str, str]]
    gaps_identified: List[str]

structured_llm = llm.with_structured_output(QuestionGeneration)
result = await structured_llm.ainvoke(...)
```

**Impact:** Reliable question generation

---

### 3. ttd_dr/core.py - Line 332
```python
# Current:
plan_data = json.loads(response.content)

# Should be:
class PlanData(BaseModel):
    main_topic: str
    key_areas: List[str]
    sub_questions: List[str]
    expected_sections: List[str]
    search_strategy: str

structured_llm = llm.with_structured_output(PlanData)
plan_data = await structured_llm.ainvoke(...)
```

**Impact:** Eliminates plan generation failures

---

### 4. ttd_dr/core.py - Line 404
```python
# Current:
result = json.loads(response.content)
questions = result["questions"]

# Should be:
class QuestionsResult(BaseModel):
    questions: List[Dict[str, Any]]
    gaps_identified: List[str]

structured_llm = llm.with_structured_output(QuestionsResult)
result = await structured_llm.ainvoke(...)
questions = result.questions  # Type-safe!
```

**Impact:** Reliable iteration questions

---

### 5. ttd_dr/core.py - Line 508
```python
# Current:
result = json.loads(response.content)
return result["convergence_score"] / 100.0

# Should be:
class ConvergenceResult(BaseModel):
    convergence_score: float

structured_llm = llm.with_structured_output(ConvergenceResult)
result = await structured_llm.ainvoke(...)
return result.convergence_score / 100.0
```

**Impact:** Reliable convergence checking

---

### 6. ttd_dr/components/denoiser.py - Line 421
```python
# Current:
result = json.loads(response.content)
return result.get("convergence_score", 50) / 100.0

# Should be:
class ConvergenceScore(BaseModel):
    convergence_score: float = 50.0

structured_llm = llm.with_structured_output(ConvergenceScore)
result = await structured_llm.ainvoke(...)
return result.convergence_score / 100.0
```

**Impact:** Prevents denoising failures

---

### 7. ttd_dr/components/evolver.py - Line 396
```python
# Current:
feedback = json.loads(response)

# Should be:
class EvolutionFeedback(BaseModel):
    fitness_score: float
    strengths: List[str]
    weaknesses: List[str]
    suggestions: List[str]

structured_llm = llm.with_structured_output(EvolutionFeedback)
feedback = await structured_llm.ainvoke(...)
```

**Impact:** Reliable variant evolution

---

## Priority 3: Evaluation Code

### 8. eval/evaluators/coverage_evaluator.py - Line 141
```python
# Current:
response_data = json.loads(response_content)
judgment = response_data["judgment"]

# Should be:
class CoverageJudgment(BaseModel):
    judgment: Literal["Yes", "No"]
    explanation: str

structured_llm = llm.with_structured_output(CoverageJudgment)
result = await structured_llm.ainvoke(...)
judgment = result.judgment
```

**Impact:** Reliable evaluation (less critical, eval code only)

---

## Summary

**Total locations:** 8  
**Priority 1 (Main agent):** 1 - ✅ FIXED  
**Priority 2 (TTD-DR):** 6 - Need fixing  
**Priority 3 (Eval):** 1 - Lower priority

**Why TTD-DR has so many:**
- Complex multi-stage pipeline
- Each stage uses LLM for structured decisions
- All still using manual parsing
- All prone to same NoneType bugs

**Recommendation:**
1. ✅ planner_node fixed (main agent robust now)
2. Fix TTD-DR components (enable TTD-DR to work)
3. Eval code can wait (lower priority)

**Estimated effort:**
- Each location: ~10-15 minutes
- Total for TTD-DR: ~1-2 hours
- High impact on reliability

---

## Benefits of Full Conversion

✅ **Type safety:** Pydantic validation  
✅ **No parsing errors:** Guaranteed valid or exception  
✅ **Better errors:** Clear failure messages  
✅ **IDE support:** Autocomplete, type checking  
✅ **Maintainability:** Self-documenting schemas  
✅ **Robustness:** Eliminates entire class of bugs  

---

**Next Steps:**

1. Deploy current fix (planner_node)
2. Test if TTD-DR works now
3. If still issues, convert TTD-DR components one by one
4. Eval code last (less critical)

