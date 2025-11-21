# UDR → UDR Comprehensive Renaming Plan

**Date**: November 21, 2025  
**Status**: ✅ **COMPLETE**  
**Reason**: Correct NVIDIA terminology - Universal Deep Research (UDR), not UDF

---

## Background

NVIDIA's official acronym is **UDR** (Universal Deep Research), as documented at:
- https://research.nvidia.com/labs/lpr/udr/
- ArXiv paper: "Universal Deep Research (UDR): A Prototype Framework..."

We've been incorrectly using **UDR** throughout the codebase.

---

## Renaming Strategy

### Phase 1: Core Python Module (CRITICAL)
**File**: `aira/src/aiq_aira/udr_integration.py` → `udr_integration.py`

**Class/Function Renames:**
- `UDFExecutionResult` → `UDRExecutionResult`
- `UDFStrategyCompiler` → `UDRStrategyCompiler`
- `UDFStrategyExecutor` → `UDRStrategyExecutor`
- `UDFIntegration` → `UDRIntegration`
- All comments/docstrings: `UDR` → `UDR`

### Phase 2: Python Imports (CRITICAL)
**Files that import from udr_integration.py:**

1. **`aira/src/aiq_aira/hackathon_agent.py`**
   - `from aiq_aira.udr_integration import ...` → `udr_integration`
   - `UDFIntegration` → `UDRIntegration`
   - `UDFExecutionResult` → `UDRExecutionResult`
   - Function: `dynamic_strategy_node` - update comments/logs
   - State field: Consider keeping `dynamic_strategy` (doesn't mention UDR)

2. **`backend/main.py`**
   - `from aiq_aira.udr_integration import UDFIntegration` → `UDRIntegration`
   - Variable: `udr_integration` → `udr_integration`
   - Config param: `"udr_integration"` → `"udr_integration"`
   - All log messages referencing UDR

3. **`test_langgraph_async.py`**
   - Import statements
   - Test variable names

### Phase 3: Documentation Files
**Memory files to rename:**

- `UDF_CRITICAL_FIXES.md` → `UDR_CRITICAL_FIXES.md`
- `UDF_VALIDATOR_BUILTIN_FIX.md` → `UDR_VALIDATOR_BUILTIN_FIX.md`
- `UDF_UNBOUNDLOCALERROR_FIX.md` → `UDR_UNBOUNDLOCALERROR_FIX.md`
- `UDF_VALIDATION_FIX_COMPLETE.md` → `UDR_VALIDATION_FIX_COMPLETE.md`
- `UDF_ERROR_ANALYZE_COST_BENEFIT.md` → `UDR_ERROR_ANALYZE_COST_BENEFIT.md`
- `UDF_BREAKTHROUGH.md` → `UDR_BREAKTHROUGH.md`
- `UDF_DEBUGGING_SESSION.md` → `UDR_DEBUGGING_SESSION.md`
- `UDF_DEBUGGING_SUMMARY.md` → `UDR_DEBUGGING_SUMMARY.md`
- `DEPLOYMENT_COMPLETE_UDF_VALIDATION.md` → `DEPLOYMENT_COMPLETE_UDR_VALIDATION.md`

**Content updates in:**
- All renamed memory files (internal UDR → UDR)
- `SESSION_FINAL_SUMMARY.md`
- `DEPLOYMENT_STATUS_FINAL.md`
- `MILVUS_CONNECTIVITY_ISSUE.md`
- Other memory files with UDR references

### Phase 4: Main Documentation
**Files to update:**

1. **`README.md`**
   - Title: "with Universal Deep Research (UDR)" → "(UDR)"
   - Section headers
   - All text references

2. **`IMPLEMENTATION_SUMMARY.md`**
   - Architecture descriptions
   - File references: `udr_integration.py` → `udr_integration.py`

3. **`QUICKSTART.md`**
   - Any UDR references

4. **Design documents:**
   - `Designing NVIDIA AI Research Agent.md`
   - `cursor/design_plan.md`

### Phase 5: Frontend (User-Facing)
**Files to update:**

1. **`frontend/app/page.tsx`**
   - Display text: "Universal Deep Research (UDR)" → "(UDR)"

2. **`frontend/app/components/CopilotAgentDisplay.tsx`**
   - Comments and display text

3. **`frontend/app/components/AgentFlowDisplay.tsx`**
   - Node labels and descriptions

### Phase 6: Infrastructure
**Files to check (may not need changes):**

1. **Kubernetes:**
   - `infrastructure/kubernetes/agent-deployment.yaml`
   - `infrastructure/kubernetes/deploy-agent.sh`
   - Only if they reference the Python module path

2. **Docker:**
   - `backend/Dockerfile` - Check COPY commands

3. **Scripts:**
   - `infrastructure/scripts/monitor-cluster-readiness.sh`

---

## Implementation Order

1. ✅ **Create this plan document**
2. 🔄 **Phase 1**: Rename Python module + update all internal references
3. 🔄 **Phase 2**: Update all Python imports (backend, agent, tests)
4. 🔄 **Phase 3**: Rename memory files
5. 🔄 **Phase 4**: Update main documentation
6. 🔄 **Phase 5**: Update frontend
7. 🔄 **Phase 6**: Check infrastructure files
8. ✅ **Test**: Verify backend starts and UDR feature works
9. ✅ **Commit**: Single atomic commit with all changes

---

## Risk Assessment

**Risk Level**: Medium-High  
**Why**: Touches critical production code + 54 files

**Mitigation:**
- ✅ No external API contracts change (internal refactor)
- ✅ State dictionary keys remain compatible
- ✅ No database schema changes
- ⚠️ Kubernetes deployment may need restart
- ⚠️ Any running sessions will reference old UDR logs

**Rollback Plan:**
- Git revert if issues detected
- Old commit hash will be documented

---

## Testing Checklist

After implementation:

- [ ] Backend starts without import errors
- [ ] Frontend builds successfully
- [ ] UDR dynamic strategy executes
- [ ] Logs show "UDR" not "UDR"
- [ ] No broken links in documentation
- [ ] Git status clean (all files committed)

---

## Files Summary

**Total Files to Modify**: 54  
**Critical Files** (imports): 3  
**Documentation Files**: 51  

**Estimated Time**: 30-45 minutes  
**Confidence**: High (automated find-replace + manual verification)

---

Status: Ready to implement

