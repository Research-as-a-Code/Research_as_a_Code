# Strategy Display Fix - Purple "Strategy Selected" Pane

## ✅ Issue Resolved

The purple "Strategy Selected" subpane was showing "Dynamic UDR Strategy" even when TTD-DR was selected. This was a **cosmetic display issue**, not functional interference.

---

## Root Cause

The frontend wasn't preserving the `strategy` field during state updates from the backend, causing the field to become `undefined`. This made the condition `agentState.strategy !== 'ttd_dr'` always evaluate to `true`, showing the purple pane even for TTD-DR.

---

## The Fix

### File: `frontend/app/components/CopilotAgentDisplay.tsx`

**Line 211 - Added:**
```typescript
strategy: prev.strategy,  // Keep the initially selected strategy
```

This preserves the user's strategy selection throughout the entire execution, ensuring the display logic works correctly.

---

## How It Works Now

### **Design Intent:**

**TTD-DR (Test-Time Diffusion):**
```
┌─────────────────────────────┐
│ TTD-DR Progress Display     │  ← Custom TTD-DR component
│ Stage: Iterating            │
│ Iteration: 2/5              │
│ Convergence: 68%            │
└─────────────────────────────┘

[Purple "Strategy Selected" pane is HIDDEN]
```

**UDR (Universal Deep Research):**
```
┌─────────────────────────────┐
│ Strategy Selected           │  ← Purple pane
│ 🚀 Dynamic UDR Strategy     │
│ {"strategy": "DYNAMIC_...}  │
└─────────────────────────────┘
```

**Simple RAG:**
```
┌─────────────────────────────┐
│ Strategy Selected           │  ← Purple pane
│ 📚 Simple RAG Pipeline      │
│ {"strategy": "SIMPLE_RAG"}  │
└─────────────────────────────┘
```

---

## The Condition Logic

**Line 502:**
```typescript
{agentState.plan && agentState.strategy !== 'ttd_dr' && (
```

**Translation:**
- Show purple pane IF:
  1. There's a plan (complexity was assessed) AND
  2. Strategy is NOT TTD-DR
- Result:
  - ✅ Shows for UDR
  - ✅ Shows for Simple RAG
  - ❌ Hidden for TTD-DR (as intended)

---

## Why TTD-DR Gets Its Own Display

TTD-DR has **different visualization needs**:
- Iteration counter (1/5, 2/5, ...)
- Convergence scores (45%, 68%, 87%)
- Current stage (Planning, Iterating, Synthesizing)
- Questions being researched
- Identified gaps
- Recent improvements

This information doesn't fit the simple "Strategy Selected" format, so TTD-DR uses the dedicated `TTDDRProgressDisplay` component instead.

---

## State Flow

### Initial State (Line 116):
```typescript
setAgentState({ 
  logs: [], 
  queries: [], 
  isProcessing: true,
  strategy: activeStrategy,  // 'udr' or 'ttd_dr'
  ttd_dr_stage: activeStrategy === 'ttd_dr' ? 'planning' : undefined
});
```

### During Updates (Line 205-222):
```typescript
setAgentState(prev => ({
  ...prev,
  currentNode: data.node,
  plan: data.state.plan || prev.plan,
  udr_strategy: data.state.udr_strategy || prev.udr_strategy,
  strategy: prev.strategy,  // ← FIX: Preserve throughout execution
  logs: data.state.logs || prev.logs,
  // ... other fields
}));
```

**The Key:** `strategy: prev.strategy` ensures the field never gets lost during backend updates.

---

## Verification

**Before Fix:**
- User selects TTD-DR
- Strategy set to 'ttd_dr' initially
- Backend updates arrive without strategy field
- Strategy becomes `undefined`
- Condition `agentState.strategy !== 'ttd_dr'` → TRUE (because undefined !== 'ttd_dr')
- ❌ Purple pane shows "Dynamic UDR Strategy" (WRONG!)

**After Fix:**
- User selects TTD-DR
- Strategy set to 'ttd_dr' initially
- Backend updates arrive, but we preserve `prev.strategy`
- Strategy remains 'ttd_dr'
- Condition `agentState.strategy !== 'ttd_dr'` → FALSE
- ✅ Purple pane is HIDDEN (CORRECT!)

---

## Summary

**Issue:** Cosmetic display bug, not functional interference
**Root Cause:** Strategy field not preserved during state updates
**Fix:** Added `strategy: prev.strategy` to state updates
**Result:** 
- ✅ TTD-DR queries now properly hide the purple pane
- ✅ TTD-DR uses its own dedicated progress display
- ✅ UDR and Simple RAG correctly show the purple pane

**Status:** ✅ Fixed and deployed

