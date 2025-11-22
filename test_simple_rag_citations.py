#!/usr/bin/env python3
"""Test citations formatting for SIMPLE_RAG strategy."""

import requests
import json

BACKEND_URL = "http://af3615e06391145bc88022ac024a36ca-bd296660cda3522f.elb.us-west-2.amazonaws.com"

# Simple query that should trigger SIMPLE_RAG (not dynamic strategy)
payload = {
    "topic": "What is the tariff code for chocolate candy?",
    "report_organization": "Brief summary",
    "collection": "us_tariffs",
    "search_web": True,
    "strategy": "auto"  # Let it auto-select (should pick SIMPLE_RAG)
}

print("=" * 80)
print("Testing Citation Formatting - SIMPLE_RAG Strategy")
print("=" * 80)
print()

try:
    print("⏱️  Sending simple query (should trigger SIMPLE_RAG)...")
    response = requests.post(f"{BACKEND_URL}/research", json=payload, timeout=120)
    result = response.json()

    print(f"✅ Response received ({response.status_code})")
    print()

    # Check which strategy was used
    print("🔍 STRATEGY EXECUTED:")
    print(f"   Execution Path: {result.get('execution_path', 'N/A')}")
    print()

    # Extract and display citations
    if "citations" in result:
        citations = result["citations"]
        print("📚 CITATIONS:")
        print("-" * 80)
        print(citations)
        print("-" * 80)
        print()
        
        # Count sources
        num_sources = citations.count('\n- [') if citations.count('\n') > 0 else (1 if citations.startswith('-') else 0)
        print(f"📊 Total sources: {num_sources}")
        
        # Check for [unknown] references
        if "[unknown]" in citations:
            unknown_count = citations.count("[unknown]")
            print(f"❌ WARNING: Found {unknown_count} [unknown] references!")
        else:
            print("✅ All sources have proper names!")
            
        # Check for empty brackets []
        if citations.count('[]') > 0:
            empty_count = citations.count('[]')
            print(f"⚠️  Found {empty_count} empty brackets (missing titles)")
        
    else:
        print("❌ No citations field in response")

    print()
    print("📝 LOGS:")
    for log in result.get("logs", []):
        print(f"   {log}")
    
    print()
    
    # Show first 500 chars of report
    if "final_report" in result:
        report_preview = result["final_report"][:500]
        print("📄 REPORT PREVIEW:")
        print("-" * 80)
        print(report_preview + "...")
        print("-" * 80)
        
except Exception as e:
    print(f"❌ ERROR: {e}")
    import traceback
    traceback.print_exc()

print()
print("=" * 80)

