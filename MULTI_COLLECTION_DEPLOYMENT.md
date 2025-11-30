# Multi-Collection Feature - Deployment Guide

## ✅ Code Changes Complete

All code changes for multi-collection support are implemented:
- ✅ `backend/main.py` - Union[str, List[str]] for collection parameter
- ✅ `aira/src/aiq_aira/tools.py` - Multi-collection search with intelligent merging
- ✅ `frontend/app/components/ResearchForm.tsx` - Multi-select UI

---

## ⏸️ Deployment Required

**Status:** Code updated but NOT YET ACTIVE

**Why:** Backend is running from Docker image built before changes

**Error when testing:**
```json
{"detail":[{
  "type":"string_type",
  "loc":["body","collection"],
  "msg":"Input should be a valid string",
  "input":["us_tariffs","congress","sustainability"]
}]}
```

This shows the running backend still expects `str`, not `Union[str, List[str]]`.

---

## Deployment Steps

### **Option A: Rebuild Backend Image** (Recommended)

```bash
cd /home/csaba/repos/AIML/Research_as_a_Code/backend

# Build new image
docker build -t aiq-backend:multi-collection .

# Tag for your registry
docker tag aiq-backend:multi-collection {YOUR_REGISTRY}/aiq-backend:latest

# Push
docker push {YOUR_REGISTRY}/aiq-backend:latest

# Update deployment to use new image
kubectl set image deployment/aiq-agent-backend \
  backend={YOUR_REGISTRY}/aiq-backend:latest \
  -n aiq-agent

# Or trigger rollout (if image:latest)
kubectl rollout restart deployment/aiq-agent-backend -n aiq-agent
```

### **Option B: Direct File Mount** (If Available)

If backend uses volume mounts for code:
```bash
# Just restart to pick up file changes
kubectl rollout restart deployment/aiq-agent-backend -n aiq-agent
```

This only works if backend Dockerfile uses volume mounts for /app

---

## Testing After Deployment

```bash
# Test single collection (should still work)
curl -X POST "http://{YOUR_BACKEND}/research" \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "Test query",
    "collection": "us_tariffs",
    ...
  }'

# Test multiple collections (NEW!)
curl -X POST "http://{YOUR_BACKEND}/research" \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "Cross-domain test",
    "collection": ["us_tariffs", "congress"],
    ...
  }'
```

**Expected:** Both should work without errors

---

## Verification Checklist

After deployment:

- [ ] Single collection query works
- [ ] Multiple collection query works  
- [ ] Frontend shows multi-select UI
- [ ] Citations show collection/source format
- [ ] Results merged by relevance

---

## Files Modified

**Backend:**
```
backend/main.py
  Line 324: collection: Union[str, List[str]]

aira/src/aiq_aira/tools.py  
  Line 26: from typing import Union, List
  Line 35: collection: Union[str, List[str]]
  Lines 49-125: Multi-collection search logic
```

**Frontend:**
```
frontend/app/components/ResearchForm.tsx
  Line 27: Added selectedCollections state
  Line 47: Send array for multiple collections
  Lines 144-177: Multi-select UI with checkboxes
```

---

## Current Status

✅ **Code:** All changes committed  
⏸️ **Backend:** Needs image rebuild  
✅ **Frontend:** Ready (will work when backend deployed)  
✅ **Collections:** All operational (473K chunks)

---

## Quick Deploy (If you have access)

```bash
# From project root
cd backend
docker build -t aiq-backend:latest .
# ... push to your registry ...
kubectl rollout restart deployment/aiq-agent-backend -n aiq-agent
```

Then test with the e-bikes query across all 3 collections!

---

**Once deployed, you'll be able to query across us_tariffs + congress + sustainability simultaneously!** 🎯

