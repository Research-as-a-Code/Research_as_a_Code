# Progressive Streaming Implementation Guide

## What We Implemented: SIMPLE_RAG Progressive Updates

We just refactored SIMPLE_RAG to show progressive updates instead of all logs at once!

---

## **The Problem:**

### **Before (Atomic Node):**
```
planner → simple_rag (all 3 steps inside) → final_report
              ↓
          [All 8 logs at once when done]
```

**User Experience:**
- Waits 30 seconds
- Suddenly sees all 8 logs appear
- No sense of progress

### **After (Progressive Nodes):**
```
planner → generate_queries → search_sources → synthesize_report → final_report
             ↓ SSE 5s          ↓ SSE 15s        ↓ SSE 25s
          [2 logs]           [2-3 logs]       [2 logs]
```

**User Experience:**
- Sees logs appear every 5-10 seconds ✓
- Can track which step is executing ✓
- Better sense of progress ✓

---

## **Implementation Pattern:**

### **Step 1: Break Node Into Sequential Sub-Nodes**

**Old Code:**
```python
async def simple_rag_pipeline(state, config):
    # Do step 1
    result1 = await step1()
    # Do step 2
    result2 = await step2()
    # Do step 3
    result3 = await step3()
    # Return all logs at once
    return {"logs": [log1, log2, log3, log4, log5, log6]}
```

**New Code:**
```python
async def step1_node(state, config):
    result = await step1()
    return {**result, "logs": [log1, log2]}  # ← Partial logs

async def step2_node(state, config):
    result = await step2()
    return {**result, "logs": [log3, log4]}  # ← Partial logs

async def step3_node(state, config):
    result = await step3()
    return {**result, "logs": [log5, log6]}  # ← Partial logs
```

### **Step 2: Update Graph Construction**

```python
# Add the new nodes
workflow.add_node("step1", step1_node)
workflow.add_node("step2", step2_node)
workflow.add_node("step3", step3_node)

# Connect sequentially
workflow.add_edge("previous_node", "step1")
workflow.add_edge("step1", "step2")
workflow.add_edge("step2", "step3")
workflow.add_edge("step3", "next_node")

# Update routing to point to first step
def route_after_planner(...):
    if condition:
        return "step1"  # ← Start at first step
```

### **Step 3: Update Backend Streaming**

```python
# Add new node names to watch list
watched_nodes = [
    "planner",
    "step1", "step2", "step3",  # New progressive nodes
    "other_nodes",
    "final_report"
]

if event_type == "on_chain_end" and langgraph_node in watched_nodes:
    # Stream this node's completion
    yield f"data: {json.dumps(sse_event)}\n\n"
```

---

## **Key Insight: LangGraph Accumulation**

**The magic is in the state schema:**
```python
class HackathonAgentState(TypedDict):
    logs: Annotated[List[str], operator.add]  # ← operator.add accumulates!
```

**What Happens:**
1. `step1_node` returns: `{"logs": ["log1", "log2"]}`
   - State now has: `logs = ["log1", "log2"]`
   - Frontend shows: 2 logs

2. `step2_node` returns: `{"logs": ["log3", "log4"]}`
   - State now has: `logs = ["log1", "log2", "log3", "log4"]`
   - Frontend shows: 4 logs (accumulated!)

3. `step3_node` returns: `{"logs": ["log5", "log6"]}`
   - State now has: `logs = ["log1", "log2", "log3", "log4", "log5", "log6"]`
   - Frontend shows: 6 logs (fully accumulated!)

**LangGraph automatically accumulates via `operator.add`!**

---

## **How to Apply This to UDR:**

### **Current UDR (All logs at once):**
```python
async def dynamic_strategy_node(state, config):
    logs = []
    logs.append("🔧 Compiling...")
    result = await compile()
    logs.append("✅ Compiled")
    
    logs.append("🔍 Validating...")
    validate()
    logs.append("✅ Validated")
    
    logs.append("⚙️ Executing...")
    exec_result = await execute()
    logs.extend(exec_result.logs)  # Tool calls
    logs.append("✅ Complete")
    
    return {"logs": logs}  # All at once
```

### **Progressive UDR (3 nodes):**

```python
async def udr_compile_node(state, config):
    """Step 1: Compile strategy"""
    logs = ["🔧 Compiling natural language plan to Python code..."]
    compiled = await compile()
    logs.append("✅ Code compilation successful")
    return {"compiled_code": compiled, "logs": logs}

async def udr_validate_node(state, config):
    """Step 2: Validate code"""
    logs = ["🔍 Validating generated code..."]
    validate(state['compiled_code'])
    logs.append("✅ Code validation passed")
    return {"logs": logs}

async def udr_execute_node(state, config):
    """Step 3: Execute strategy"""
    logs = ["⚙️ Executing compiled strategy code..."]
    result = await execute(state['compiled_code'])
    logs.extend(result.execution_log)  # Tool calls
    logs.append("✅ UDR strategy execution complete")
    return {**result, "logs": logs}
```

**Then connect:**
```python
workflow.add_edge("planner", "udr_compile")  # When DYNAMIC_STRATEGY selected
workflow.add_edge("udr_compile", "udr_validate")
workflow.add_edge("udr_validate", "udr_execute")
workflow.add_edge("udr_execute", "final_report")
```

---

## **How to Apply This to TTD-DR:**

### **Current TTD-DR (Callback-based):**
```python
async def ttd_dr_strategy_node(state, config):
    progress_logs = []
    
    async def callback(stage_info):
        # Logs collected but not streamed until node completes
        progress_logs.append(...)
    
    result = await ttd_dr.execute(context)
    
    return {"logs": progress_logs}  # All at once
```

### **Progressive TTD-DR (Break by iteration):**

```python
async def ttd_dr_plan_node(state, config):
    """Step 1: Create research plan"""
    plan = await create_plan()
    return {
        "ttd_dr_plan": plan,
        "logs": ["🔬 Created research plan", f"📋 {len(plan.questions)} questions"]
    }

async def ttd_dr_iterate_node(state, config):
    """Step 2: Run single iteration"""
    iteration = state.get('ttd_dr_iteration', 0) + 1
    logs = [f"🔄 Starting Iteration {iteration}"]
    
    # Search
    logs.append("🔍 Searching for answers...")
    results = await search()
    
    # Denoise
    logs.append("✨ Refining draft...")
    draft = await denoise()
    
    # Check convergence
    score = await check_convergence()
    logs.append(f"📊 Convergence: {score:.1%}")
    
    # Decide if we continue
    continue_iterations = score < 0.85 and iteration < 5
    
    return {
        "ttd_dr_iteration": iteration,
        "ttd_dr_convergence": score,
        "continue_iterations": continue_iterations,
        "logs": logs
    }

# Use conditional routing to loop iterations
workflow.add_conditional_edges(
    "ttd_dr_iterate",
    lambda state: "ttd_dr_iterate" if state.get('continue_iterations') else "ttd_dr_finalize",
    {
        "ttd_dr_iterate": "ttd_dr_iterate",  # Loop back
        "ttd_dr_finalize": "ttd_dr_finalize"
    }
)
```

---

## **Benefits:**

| Aspect | Before | After |
|--------|--------|-------|
| **Visibility** | All at once | Progressive |
| **User perception** | Feels slow | See it working |
| **Debugging** | Hard to identify slow steps | Can see which step is slow |
| **UX** | Waiting... | Active progress! |

---

## **Implementation Checklist:**

For any node you want to make progressive:

- [ ] Break into logical sub-steps (2-4 nodes)
- [ ] Each sub-node returns partial logs
- [ ] Connect nodes sequentially with `add_edge`
- [ ] Update routing to point to first sub-node
- [ ] Add node names to backend `watched_nodes` list
- [ ] Test that state accumulates correctly
- [ ] Verify logs appear progressively in UI

---

## **Current Status:**

✅ **SIMPLE_RAG**: Implemented and ready to test!
⏳ **UDR**: Can be improved using same pattern
⏳ **TTD-DR**: Can be improved with iteration-level streaming

**This serves as a working template for improving UDR and TTD-DR!**

