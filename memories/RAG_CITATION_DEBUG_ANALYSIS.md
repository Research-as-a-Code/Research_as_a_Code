# RAG Citation Debug Analysis

## Issue Description

When running simple queries, the RAG system returns citations like:
```
Chapter_17.pdf appears: 6 times
Chapter_18.pdf appears: 6 times
```

User suspects the same chunks might be returned multiple times, but that's not the case.

---

## Root Cause Analysis

### **How RAG Search Works:**

1. **Simple RAG generates 3 queries** (from `generate_query` node)
   - Example: "tariff codes for food products..."
   - Example: "case studies of successful tariff negotiations..."
   - Example: (3rd query)

2. **Each query searches Milvus** (`tools.py` lines 77-82):
```python
results = coll.search(
    data=[query_embedding],
    limit=4,  # ← Returns TOP 4 most relevant chunks
    output_fields=["text", "source"]  # ← Each chunk has PDF name
)
```

3. **Each chunk has its source PDF** (line 94):
```python
source = hit.entity.source  # e.g., "Chapter_17.pdf"
```

4. **Results are formatted** (lines 98-99):
```python
content_parts.append(f"[{i+1}] {text}")  # [1], [2], [3], [4]
citations_parts.append(source)  # All 4 PDF names
```

---

## **The Math:**

- **3 queries** × **4 chunks per query** = **12 total chunks**
- Those 12 chunks come from a mix of Chapter_17.pdf and Chapter_18.pdf
- Result from your test:
  - Chapter_17.pdf: 6 chunks
  - Chapter_18.pdf: 6 chunks
  - Total: 12 chunks ✓

---

## **Why Multiple PDFs per Query:**

When you search for "tariff codes for food products", Milvus finds the TOP 4 most relevant chunks based on embedding similarity. Those 4 chunks can come from **different PDFs** because:

1. **Food tariffs span multiple chapters** in the Harmonized Tariff Schedule
2. **Chapter 17**: Sugar and confectionery
3. **Chapter 18**: Cocoa and chocolate products
4. **Chapter 20**: Other food preparations

**Reese's Pieces is a candy** → Could be classified under:
- Chapter 17 (sugar confectionery)
- Chapter 18 (chocolate/cocoa products if they contain chocolate)

So Milvus correctly returns relevant chunks from BOTH chapters because they're both relevant to the query!

---

## **Current Citation Format:**

### For Each Query:
```
QUERY: tariff codes for food products...
ANSWER: 
[1] text from Chapter_17.pdf
[2] text from Chapter_18.pdf  
[3] text from Chapter_17.pdf
[4] text from Chapter_18.pdf

CITATIONS:
Chapter_17.pdf
Chapter_18.pdf
Chapter_17.pdf
Chapter_18.pdf
```

### After Deduplication:
```
- [Chapter_17.pdf] RAG Collection: us_tariffs (6 excerpts)
- [Chapter_18.pdf] RAG Collection: us_tariffs (6 excerpts)
```

This is **correct behavior** - it's just showing that across all 3 queries, we found 6 relevant chunks from each PDF.

---

## **Why The User Sees This:**

Looking at your example:

### Source 1: "tariff codes for food products..."
- Returns 4 chunks: Mix of Chapter_17 and Chapter_18
- Displayed as [1], [2], [3], [4]
- Citations list: Both PDFs

### Source 2: "case studies of successful tariff negotiations..."
- Returns 4 chunks: Mix of Chapter_17 and Chapter_18
- Displayed as [1], [2], [3], [4]
- Citations list: Both PDFs

**This is normal!** Each query independently retrieves the 4 most relevant chunks, and those chunks can come from multiple PDFs.

---

## **Verification:**

To verify the chunks are different, you can:

1. Compare the text content of [1] from Source 1 vs [1] from Source 2
2. They should be different chunks about different aspects
3. The PDF sources tell you which chapter each chunk is from

From your example:
- Source 1, [1]: Talks about "human food consumption... sugar cane"
- Source 2, [1]: Talks about "identical form and package... 65 percent by dry weight"

These are **different chunks** with **different topics**, just both happen to be relevant.

---

## **Why This Design is Correct:**

### Scenario: Query "What's the tariff code for Reese's Pieces?"

**Reese's Pieces could be classified as:**
1. Sugar confectionery (Chapter 17) - if primarily sugar
2. Chocolate/cocoa products (Chapter 18) - if contains chocolate/cocoa
3. Other food preparations (Chapter 20) - as prepared confectionery

**Milvus correctly returns relevant info from multiple chapters** because:
- The proper classification depends on composition (sugar %, cocoa content)
- Multiple chapters have relevant tariff codes
- You need info from both to make an informed decision!

---

## **The Real Question:**

Your query was: "What factors I need to consider (weight, ingredients) when deciding tariff codes for sweets?"

**The answer involves:**
- Chapter 17: Sugar content thresholds
- Chapter 18: Cocoa/chocolate content rules  
- Weight considerations across both

**RAG correctly returns info from BOTH chapters** because that's what you need to answer the question!

---

## **Solutions (If You Want Different Behavior):**

### Option 1: **Per-Chunk Source Attribution** (More Detailed)
Show which PDF each numbered chunk is from:
```
ANSWER:
[1] Chapter_17.pdf - text about sugar...
[2] Chapter_18.pdf - text about cocoa...
[3] Chapter_17.pdf - text about weight...
[4] Chapter_18.pdf - text about packages...
```

### Option 2: **Group by PDF** (Clearer Structure)
```
From Chapter_17.pdf:
[1] text about sugar confectionery...
[2] text about weight classification...

From Chapter_18.pdf:
[1] text about cocoa products...
[2] text about chocolate content...
```

### Option 3: **Keep Current** (Already Good)
The current deduplication already handles this well:
```
- [Chapter_17.pdf] RAG Collection: us_tariffs (6 excerpts)
- [Chapter_18.pdf] RAG Collection: us_tariffs (6 excerpts)
```

This tells you:
- Both chapters are relevant
- Each contributed 6 chunks across all queries
- The chunks are mixed in the answers

---

## **My Recommendation:**

**The current behavior is correct and expected!** 

For food products like Reese's Pieces:
- Multiple tariff chapters ARE relevant
- Milvus is correctly finding the most relevant chunks from each
- The deduplication summary is accurate

**No bug - this is proper behavior for a multi-chapter tariff classification question!**

---

## **Next Steps:**

If you want more granular source attribution, we can:
1. Add inline PDF names to each [1][2][3][4] chunk
2. Group answer chunks by source PDF
3. Show relevance scores per chunk

But the current system is working correctly - it's just that tariff classification **actually requires** information from multiple chapters!

