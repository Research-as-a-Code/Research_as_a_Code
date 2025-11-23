# Strategy Architecture - Corrected Understanding

## ✅ Correct Architecture Understanding

Thanks to user feedback, we now have the correct understanding of the strategy selection flow.

---

## 🏗️ **The Actual Architecture**

### **Two-Level Decision Process:**

```
Step 1: PLANNER NODE
└─ Analyzes complexity
   ├─ Simple query → SIMPLE_RAG
   └─ Complex query → DYNAMIC_STRATEGY
   
Step 2: ROUTER (if DYNAMIC_STRATEGY)
└─ Based on user selection:
   ├─ User selected "udr" → UDR Strategy Node
   └─ User selected "ttd_dr" → TTD-DR Strategy Node
```

### **Key Insight:**

**Both UDR and TTD-DR are "Dynamic Strategies"!**

They both:
- ✅ Require complexity analysis (DYNAMIC_STRATEGY)
- ✅ Handle multi-step, multi-domain research
- ✅ Perform synthesis across multiple sources
- ✅ Are triggered by the same complexity threshold

The difference is **HOW** they execute:
- **UDR**: Strategy-as-code (compile → execute)
- **TTD-DR**: Iterative refinement (draft → denoise → converge)

---

## 🎨 **Corrected Display Behavior**

### **Purple "Strategy Selected" Pane**

**Now shows for ALL strategies** (not hidden for TTD-DR):

#### For TTD-DR:
```
┌─────────────────────────────┐
│ Strategy Selected           │
│ 🔬 Dynamic TTD-DR Strategy  │  ← Now says TTD-DR!
│ {"strategy": "DYNAMIC_...}  │
└─────────────────────────────┘
```

#### For UDR:
```
┌─────────────────────────────┐
│ Strategy Selected           │
│ 🚀 Dynamic UDR Strategy     │
│ {"strategy": "DYNAMIC_...}  │
└─────────────────────────────┘
```

#### For Simple RAG:
```
┌─────────────────────────────┐
│ Strategy Selected           │
│ 📚 Simple RAG Pipeline      │
│ {"strategy": "SIMPLE_RAG"}  │
└─────────────────────────────┘
```

---

## 📋 **What Changed**

### File: `frontend/app/components/CopilotAgentDisplay.tsx`

#### Before (WRONG):
```typescript
{/* Hidden for TTD-DR */}
{agentState.plan && agentState.strategy !== 'ttd_dr' && (
  <div>
    {agentState.udr_strategy ? (
      "Dynamic UDR Strategy"
    ) : (
      "Simple RAG Pipeline"
    )}
  </div>
)}
```

**Problem:** Purple pane hidden for TTD-DR (incorrect architecture understanding)

#### After (CORRECT):
```typescript
{/* Shows for ALL strategies */}
{agentState.plan && (
  <div>
    {agentState.strategy === 'ttd_dr' ? (
      "🔬 Dynamic TTD-DR Strategy"
    ) : agentState.udr_strategy || agentState.strategy === 'udr' ? (
      "🚀 Dynamic UDR Strategy"
    ) : (
      "📚 Simple RAG Pipeline"
    )}
  </div>
)}
```

**Fixed:** Purple pane shows for ALL strategies with correct text!

---

## 🔄 **Strategy Flow Example**

### Example Query: "Compare tariff codes for different types of candy with cost analysis"

**Step 1 - Planner:**
```
Input: "Compare tariff codes... with cost analysis"
Analysis: Complex, multi-domain, requires synthesis
Decision: DYNAMIC_STRATEGY ✅
```

**Step 2 - Router:**
```
User selected: TTD-DR
DYNAMIC_STRATEGY + TTD-DR selection
→ Routes to: ttd_dr_strategy node ✅
```

**Display:**
```
Purple Pane: "🔬 Dynamic TTD-DR Strategy"
TTD-DR Progress: Shows iterations, convergence, etc.
```

---

## 🎯 **Strategy Icons**

| Strategy | Icon | Color | Meaning |
|----------|------|-------|---------|
| **TTD-DR** | 🔬 | Blue | Scientific/iterative approach |
| **UDR** | 🚀 | Green | Fast execution (NVIDIA) |
| **Simple RAG** | 📚 | Purple | Standard pipeline |

---

## ✅ **Why Both Displays for TTD-DR?**

When TTD-DR is active, you'll see **TWO** subpanes:

### 1. Purple "Strategy Selected" (Shows routing decision)
- Confirms that DYNAMIC_STRATEGY was chosen
- Shows it branched to TTD-DR
- Displays the plan overview

### 2. TTD-DR Progress Display (Shows execution details)
- Current iteration (1/5, 2/5, etc.)
- Convergence scores (45%, 68%, 87%)
- Current stage (Planning, Iterating, Synthesizing)
- Questions, gaps, improvements

**This is intentional!** Both provide different information:
- Purple pane: **Why** this path was chosen
- TTD-DR pane: **What** is happening during execution

---

## 📊 **Comparison: UDR vs TTD-DR Display**

| Display Component | UDR | TTD-DR |
|------------------|-----|--------|
| Purple "Strategy Selected" | ✅ Shows "Dynamic UDR Strategy" | ✅ Shows "Dynamic TTD-DR Strategy" |
| Custom Progress Display | ❌ None (uses standard logs) | ✅ TTD-DR Progress Display |
| Execution Logs | ✅ Blue pane | ✅ Blue pane |
| Plan Preview | ✅ In purple pane | ✅ In purple pane |

---

## ✅ **Fixed!**

- ✅ Purple pane now shows for TTD-DR (correct!)
- ✅ Text says "Dynamic TTD-DR Strategy" (not "UDR")
- ✅ Icon changed to 🔬 (microscope) for scientific approach
- ✅ Strategy field preserved throughout execution
- ✅ No functional interference - this was always just cosmetic

**Both UDR and TTD-DR are properly displayed as "Dynamic Strategies" with their own specific implementations!** 🎉

