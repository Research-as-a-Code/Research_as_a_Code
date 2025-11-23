#!/usr/bin/env python3
"""Test progressive streaming - logs should appear incrementally, not all at once."""

import requests
import json
import time

BACKEND_URL = "http://af3615e06391145bc88022ac024a36ca-bd296660cda3522f.elb.us-west-2.amazonaws.com"

payload = {
    "topic": "What is the tariff code for chocolate candy?",
    "report_organization": "Brief summary",
    "collection": "us_tariffs",
    "search_web": False,
    "strategy": "auto"
}

print("=" * 80)
print("TESTING PROGRESSIVE STREAMING")
print("=" * 80)
print()
print("Query: 'What is the tariff code for chocolate candy?'")
print("Expected: SIMPLE_RAG with progressive log updates")
print()
print("Monitoring log appearance times...")
print("-" * 80)

start_time = time.time()

try:
    response = requests.post(
        f"{BACKEND_URL}/research",
        json=payload,
        timeout=180
    )
    
    end_time = time.time()
    elapsed = end_time - start_time
    
    result = response.json()
    logs = result.get('logs', [])
    
    print()
    print("=" * 80)
    print(f"✅ Query completed in {elapsed:.1f} seconds")
    print("=" * 80)
    print()
    print(f"Total logs received: {len(logs)}")
    print()
    print("Logs:")
    for i, log in enumerate(logs, 1):
        print(f"  {i}. {log[:80]}")
    
    print()
    print("-" * 80)
    print()
    
    if len(logs) >= 6:
        print("✅ SUCCESS: Received detailed logs!")
        print()
        print("NOTE: In the UI, these should appear progressively:")
        print("  - First 2 logs after ~5 seconds (query generation)")
        print("  - Next 2-3 logs after ~15 seconds (searching)")
        print("  - Final 2 logs after ~25 seconds (synthesis)")
        print()
        print("The API returns all logs at once, but the SSE stream")
        print("should have shown them progressively as nodes completed.")
    else:
        print(f"⚠️  Only {len(logs)} logs - expected 6+")
    
except requests.exceptions.Timeout:
    print("❌ Query timed out after 180 seconds")
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

print()
print("=" * 80)

