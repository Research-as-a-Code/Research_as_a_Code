# UDR Error: Function Not Defined

## Error Summary

**Date**: November 17, 2025  
**Error Type**: UDR Execution Failure  
**Status**: ❌ Function hallucination by LLM

## Error Message

```
❌ UDR execution failed: name 'analyze_cost_benefit_report' is not defined
```

**Full Error Context from Logs**:
```json
{
  "udr_result": {
    "success": false,
    "error": "name 'analyze_cost_benefit_report' is not defined"
  }
}
```

## Query That Triggered the Error

**Research Topic**: "What factors I need to consider (such as weight, important ingredients) when I need to decide tariff codes for various sweets and other popular food gifts?"

**Report Organization**: "Create a comprehensive report with introduction, detailed analysis, and conclusion. Perform a deep research and must use dynamic strategy. Try to utilize the us_tariff collection as well."

**Strategy Selected**: `DYNAMIC_STRATEGY`

**UDR Plan Generated**:
```json
{
  "step1": {"title": "Research Overview", "description": "Understand the research request, the topic, and the required report organization."},
  "step2": {"title": "Domain Identification", "description": "Identify the domains involved, such as food science, economics, and logistics, to plan the research steps."},
  "step3": {"title": "Data Collection", "description": "Use the us_tariff collection and other reliable sources to gather data on weight, important ingredients, and other relevant factors for sweets and popular food gifts."},
  "step4": {"title": "Analysis and Synthesis", "description": "Conduct a detailed analysis of the collected data, considering factors like cost, quality, and transportation needs. Synthesize the information to develop a comprehensive strategy for tariff codes."},
  "step5": {"title": "Cost-Benefit Analysis", "description": "Perform a cost-benefit analysis to determine the optimal tariff codes based on the synthesized information."},
  "step6": {"title": "Report Creation", "description": "Create a comprehensive report with an introduction, detailed analysis, and conclusion based on the research findings."}
}
```

## Root Cause

The LLM code generator **hallucinated a function** called `analyze_cost_benefit_report()` that doesn't exist in the available tool namespace.

### Available Tools (Actual)
The UDR executor provides only these 3 tools:
1. `search_rag(query: str, collection: str)` - Search RAG/Milvus
2. `search_web(query: str)` - Web search
3. `synthesize_findings(data: List[Dict])` - Synthesize results

### What the LLM Tried to Use
The generated Python code likely tried to call:
- ❌ `analyze_cost_benefit_report()` - **Does NOT exist**

This is a **code generation hallucination** where the LLM invented a function name based on the plan's mention of "Cost-Benefit Analysis" in step5.

## Why This Happened

### 1. Misleading Plan
The planner suggested a step called "Cost-Benefit Analysis", which implied there should be a tool for it. The UDR compiler then tried to match this conceptual step to a non-existent function.

### 2. LLM Instruction Following
The UDR compiler LLM saw:
- Plan mentions: "Perform a cost-benefit analysis"
- Plan step5: "Cost-Benefit Analysis"
- LLM assumed: There must be a function for this

### 3. Insufficient Tool Validation
The compiler prompt doesn't strongly emphasize:
- "These are the ONLY 3 functions available"
- "DO NOT invent or call functions not in the list"
- "If the plan requires analysis, use `synthesize_findings()` instead"

## Impact

- ✅ **System Resilience**: The agent **recovered gracefully**
  - UDR failed with clear error message
  - System fell back to generating final report anyway
  - User got a report (though generic, not using UDR results)

- ❌ **UDR Feature**: Dynamic strategy didn't execute properly
  - No actual RAG searches performed
  - No web searches performed
  - No data synthesis
  - Report was generic (LLM knowledge only, no tools used)

## Fixes Needed

### Fix 1: Strengthen Compiler Prompt (High Priority)

**Location**: `aira/src/aiq_aira/udr_integration.py` - `STRATEGY_COMPILER_PROMPT`

**Add Explicit Constraints**:
```python
CRITICAL REQUIREMENTS:
1. ONLY await async functions: search_rag(), search_web(), synthesize_findings()
2. DO NOT await: log.append(), sources.append(), variables, or any list/dict operations
3. Use try/except for error handling
4. ABSOLUTELY MUST end with a return statement
5. The return MUST be a dict with these EXACT keys: "report", "sources", "log"
6. Do not use imports - tools are pre-loaded in namespace
7. **THESE ARE THE ONLY 3 TOOLS - DO NOT INVENT OR CALL OTHER FUNCTIONS**
8. **If you need analysis, use synthesize_findings() - it handles all synthesis**
9. **If a plan step doesn't map to a tool, SKIP IT or use synthesize_findings()**
```

**Add Warning Section**:
```python
❌ FORBIDDEN:
- Calling functions not in the available tools list
- Inventing helper functions (analyze_*, calculate_*, process_*)
- Using Python standard library functions (open, json.loads, etc.)
- Any function call other than: search_rag, search_web, synthesize_findings

✅ ALLOWED:
- Variables: log = [], sources = [], data = []
- List operations: log.append(), sources.extend()
- String operations: f"string {variable}"
- Dict operations: {"key": value}
- Control flow: if, for, while
- Exception handling: try/except
```

### Fix 2: Add Code Validator (Medium Priority)

**New Function**: `validate_generated_code(code: str) -> tuple[bool, str]`

```python
def validate_generated_code(code: str) -> tuple[bool, str]:
    """
    Validate generated UDR code before execution.
    
    Returns: (is_valid, error_message)
    """
    allowed_functions = {'search_rag', 'search_web', 'synthesize_findings'}
    
    # Parse the code to find function calls
    import ast
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                    if func_name not in allowed_functions and func_name not in {'append', 'extend', 'get'}:
                        return False, f"Forbidden function call: {func_name}(). Only allowed: {allowed_functions}"
        return True, ""
    except SyntaxError as e:
        return False, f"Syntax error in generated code: {e}"
```

**Usage in `execute_dynamic_strategy()`**:
```python
# After compilation
is_valid, error_msg = validate_generated_code(strategy_code)
if not is_valid:
    logger.error(f"Generated code validation failed: {error_msg}")
    return {
        "report": f"Code generation error: {error_msg}. Retrying with simpler approach.",
        "sources": [],
        "log": ["Code validation failed"]
    }
```

### Fix 3: Improve Error Messages (Low Priority)

When UDR fails, include:
1. What function was attempted
2. List of available functions
3. Suggestion to user: "Your query may be too complex for dynamic strategy. Try simpler wording or use simple RAG."

## Workaround for Users

If you encounter "function not defined" errors:

### Option 1: Simplify Query
Remove mentions of specific analysis types:
- ❌ "perform cost-benefit analysis"
- ❌ "analyze the trade-offs"
- ❌ "calculate the optimal"
- ✅ "what factors to consider"
- ✅ "provide information about"

### Option 2: Remove "must use dynamic strategy"
Let the planner decide - it might choose SIMPLE_RAG which works reliably.

### Option 3: Be More Specific About Tools
If forcing dynamic strategy, mention:
- "Search the tariff database"
- "Search the web for additional sources"
- "Synthesize the findings"

(These map directly to available tools)

## Testing Recommendations

### Test Case 1: Valid UDR Query
```json
{
  "topic": "What are tariff codes for chocolate products?",
  "report_organization": "Search the tariff database, search the web for examples, and synthesize findings into a report",
  "collection": "us_tariffs"
}
```
**Expected**: UDR successfully calls search_rag(), search_web(), synthesize_findings()

### Test Case 2: Intentionally Trigger Error (Before Fix)
```json
{
  "topic": "Perform cost-benefit analysis of tariff codes for sweets",
  "report_organization": "Must use dynamic strategy with detailed analysis",
  "collection": "us_tariffs"
}
```
**Expected**: Error - "function not defined" (before fix), graceful handling (after fix)

### Test Case 3: Complex Valid Query
```json
{
  "topic": "Compare tariff codes for different types of confectionery",
  "report_organization": "Search tariff data, find web sources about HS codes, and create comprehensive comparison",
  "collection": "us_tariffs"
}
```
**Expected**: Multi-step UDR execution with multiple tool calls

## Priority

**Priority**: Medium-High

**Why Not Critical**:
- System recovered gracefully (no crash)
- User still got a report
- Simple RAG works perfectly
- Only affects complex dynamic strategy queries

**Why Important**:
- UDR is a key differentiating feature
- User explicitly requested "dynamic strategy"
- Reduces trust in the system if it fails

## Implementation Plan

1. **Immediate** (5 min): Update compiler prompt with explicit constraints
2. **Short-term** (15 min): Add code validator function
3. **Medium-term** (30 min): Add comprehensive test suite for UDR code generation
4. **Long-term** (1 hr): Consider adding few-shot examples to compiler prompt

## Files to Modify

- `/home/csaba/repos/AIML/Research_as_a_Code/aira/src/aiq_aira/udr_integration.py`
  - Update `STRATEGY_COMPILER_PROMPT`
  - Add `validate_generated_code()` function
  - Update `execute_dynamic_strategy()` to use validator

## Related Issues

- See: `/memories/UDF_DEBUGGING_SESSION.md` - Previous UDR fixes
- See: `/memories/UDF_BREAKTHROUGH.md` - Initial UDR success
- See: `/memories/DEPLOYMENT_STATUS_FINAL.md` - Current system status

---

**Status**: Documented ✅  
**Fix Required**: Yes  
**Estimated Time**: 20-30 minutes  
**Impact**: Medium (UDR feature reliability)

