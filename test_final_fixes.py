#!/usr/bin/env python3
"""Test both log accumulation and RAG document name fixes."""

import requests
import json
import time

BACKEND_URL = "http://af3615e06391145bc88022ac024a36ca-bd296660cda3522f.elb.us-west-2.amazonaws.com"

payload = {
    "topic": "What factors I need to consider (such as weight, important ingredients) when I need to decide tariff codes for various sweets? Mention tariff codes or code ranges.",
    "report_organization": "Create a comprehensive report with introduction, detailed analysis, and conclusion. Perform a deep research and must use dynamic strategy. Try to utilize the us_tariff collection as well.",
    "collection": "us_tariffs",
    "search_web": True,
    "strategy": "udr"
}

print("=" * 80)
print("FINAL TEST: Log Accumulation & RAG Document Names")
print("=" * 80)
print()
print("Sending UDR query with us_tariffs collection...")
print()

try:
    response = requests.post(f"{BACKEND_URL}/research", json=payload, timeout=180)
    result = response.json()
    
    print("✅ Response received")
    print()
    
    # Test 1: Log Accumulation
    print("=" * 80)
    print("TEST 1: LOG ACCUMULATION")
    print("=" * 80)
    logs = result.get('logs', [])
    print(f"Total logs: {len(logs)}")
    print()
    if len(logs) > 1:
        print("✅ PASS: Multiple log entries accumulated!")
        for i, log in enumerate(logs, 1):
            print(f"  {i}. {log[:80]}")
    else:
        print(f"❌ FAIL: Only {len(logs)} log entry")
        if logs:
            print(f"  Content: {logs[0]}")
    
    print()
    
    # Test 2: RAG Document Names
    print("=" * 80)
    print("TEST 2: RAG DOCUMENT NAMES")
    print("=" * 80)
    citations = result.get('citations', '')
    print("Citations:")
    print("-" * 80)
    print(citations)
    print("-" * 80)
    print()
    
    # Check for document names
    if "Chapter_" in citations or ".pdf" in citations:
        print("✅ PASS: Found actual document names (Chapter_X.pdf)!")
    elif "[RAG Document 1]" in citations:
        print("⚠️  PARTIAL: Still showing generic 'RAG Document 1'")
        print("   (This means citations array is still empty)")
    else:
        print("❓ UNKNOWN: Check citation format above")
    
    print()
    print("=" * 80)
    
except Exception as e:
    print(f"❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
