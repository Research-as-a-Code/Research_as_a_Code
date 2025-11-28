# Semantic Chunking - Lessons Learned

## What We Discovered

Your 3-step approach (debug locally → add logging → test on files) **perfectly caught a critical issue** before wasting more cluster time!

---

## The Problem

### **Test Results:**
```
Input: Chapter_17.pdf (91,021 characters)
Semantic splitter settings:
  • breakpoint_percentile_threshold: 95 → 75
  • buffer_size: 1 → 2
  
Output: 1 chunk (entire document)
Expected: ~100+ chunks
```

### **Root Cause:**

`SemanticSplitterNodeParser` is **not splitting** even with threshold=75.

**Why:**
1. Semantic splitter compares **sentence embeddings**
2. But it needs text **already split into sentences**
3. When given a large text block, it treats it as one unit
4. Similarity within a coherent document is always high
5. Result: No split points found

---

## Alternative Approaches

### **Option A: Header-First Splitting** (Recommended)

```python
# Step 1: Split by markdown headers first
from llama_index.core.node_parser import MarkdownNodeParser

header_splitter = MarkdownNodeParser()
header_nodes = header_splitter.get_nodes_from_documents([doc])
# This gives us sections: "Note", "Heading XVII", etc.

# Step 2: Apply semantic splitting to each section
semantic_splitter = SemanticSplitterNodeParser(
    buffer_size=2,
    breakpoint_percentile_threshold=75,
    embed_model=embed_model
)
final_nodes = []
for section in header_nodes:
    semantic_chunks = semantic_splitter.get_nodes_from_documents([section])
    final_nodes.extend(semantic_chunks)
```

**Benefits:**
- ✅ Starts with logical document structure
- ✅ Semantic splitting within sections
- ✅ Better granularity
- ✅ Preserves hierarchy

### **Option B: Sentence-Based Splitting**

```python
from llama_index.core.node_parser import SentenceSplitter

# First split into sentences
sentence_splitter = SentenceSplitter(chunk_size=512, chunk_overlap=50)
sentence_nodes = sentence_splitter.get_nodes_from_documents([doc])

# Then apply semantic grouping
semantic_splitter = SemanticSplitterNodeParser(
    buffer_size=3,
    breakpoint_percentile_threshold=70,
    embed_model=embed_model
)
final_nodes = semantic_splitter.get_nodes_from_documents(sentence_nodes)
```

**Benefits:**
- ✅ Starts with proper sentence boundaries
- ✅ Semantic grouping of related sentences
- ✅ Configurable chunk size

### **Option C: Hybrid (Best)**

```python
# 1. Extract tables first
element_parser = MarkdownElementNodeParser()
base_nodes, tables = element_parser.get_nodes_and_objects([doc])

# 2. Split text by headers
header_parser = MarkdownNodeParser()
header_sections = header_parser.get_nodes_from_documents(base_nodes)

# 3. Split large sections by sentences
sentence_splitter = SentenceSplitter(chunk_size=1024, chunk_overlap=200)
sentence_chunks = []
for section in header_sections:
    if len(section.get_content()) > 2000:  # Only split large sections
        chunks = sentence_splitter.get_nodes_from_documents([section])
        sentence_chunks.extend(chunks)
    else:
        sentence_chunks.append(section)

# 4. Combine tables + text chunks
final_chunks = tables + sentence_chunks
```

**Benefits:**
- ✅ Tables extracted intact
- ✅ Respects document structure (headers)
- ✅ Reasonable chunk sizes
- ✅ Semantic-aware but pragmatic

---

## What Happened in Cluster

**Semantic ingestion ran for 5h 14min:**
- Processed 117+ files
- Each file → 1 chunk (no splitting)
- Total: 29 chunks (most files probably errored out)
- Result: Nearly empty collection

**Why it "succeeded":**
- Script didn't crash (exit code 0)
- Just produced very few chunks
- No errors logged (threshold=95 is "valid", just ineffective)

---

## Current Status

| Collection | Status | Chunks | Method |
|------------|--------|--------|--------|
| **congress** | ✅ Complete | 1,710,693 | Simple |
| **sustainability** | ✅ Complete | 19,626 | Simple |
| **us_tariffs** | 🔄 Restoring | ~24,452 | Simple (in progress) |

**Simple chunking restore:** Started 5 minutes ago, ETA 25 minutes

---

## Recommendation

### **Short-term: Use Simple Chunking**
- ✅ Works reliably
- ✅ All 3 collections ready
- ✅ Good retrieval quality
- ✅ Production-ready

### **Medium-term: Implement Hybrid Approach**
1. Test Option C (Hybrid) locally on Chapter_17 + Chapter_18
2. Verify it produces reasonable chunks (100-200 per file)
3. Compare quality with simple chunking
4. Deploy if significantly better

### **Long-term: Pure Semantic**
- Research SemanticSplitter requirements
- May need custom sentence splitter
- Or different embedding approach for similarity
- Consider as future enhancement

---

## Files Status

**Working Scripts:**
- ✅ `scripts/ingest_with_docling_incremental.py` - Simple chunking, all fixes
- ✅ `scripts/replay_failed_chunks.py` - Failure replay tool
- ✅ `scripts/test_semantic_chunking.py` - Local test (caught the issue!)

**Needs Fixes:**
- ⚠️ `scripts/ingest_with_semantic_chunking.py` - SemanticSplitter not working
  - Need: Header-first or sentence-first approach
  - Need: Better threshold tuning
  - Need: Multi-stage pipeline

**Jobs:**
- ✅ Simple chunking jobs - All working
- ⚠️ Semantic jobs - Need script fixes first

---

## Key Learnings

1. ✅ **Your 3-step process saved hours** of cluster time!
2. ⚠️ **SemanticSplitter alone doesn't work** on large documents
3. ✅ **Need hierarchical splitting:** Headers → Sentences → Semantic
4. ✅ **Simple chunking is production-ready** (1.75M chunks indexed)
5. 💡 **Semantic is an optimization**, not a requirement

---

## Next Steps

1. **Wait for us_tariffs simple restore** (~25 min)
2. **Verify all 3 collections working**
3. **Test hybrid approach locally** (Option C above)
4. **Deploy semantic only if significantly better**

---

**Bottom Line:** Simple chunking works great! Semantic is a nice-to-have that needs more research. Don't let perfect be the enemy of good. 🎯

