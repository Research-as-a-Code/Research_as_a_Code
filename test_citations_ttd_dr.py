#!/usr/bin/env python3
"""Test citations formatting for TTD-DR strategy."""

import requests
import json

BACKEND_URL = "http://af3615e06391145bc88022ac024a36ca-bd296660cda3522f.elb.us-west-2.amazonaws.com"

# Test query with TTD-DR
payload = {
    "topic": "What are the key benefits of microservices architecture?",
    "report_organization": "Create a brief comprehensive report. Use dynamic strategy.",
    "collection": "",
    "search_web": True,
    "strategy": "ttd_dr"  # Test with TTD-DR
}

print("=" * 80)
print("Testing Citation Formatting - TTD-DR Strategy")
print("=" * 80)
print()

try:
    response = requests.post(f"{BACKEND_URL}/research", json=payload, timeout=180)
    result = response.json()

    print("📊 RESPONSE STATUS:", response.status_code)
    print()

    # Extract and display citations
    if "citations" in result:
        print("📚 CITATIONS:")
        print("-" * 80)
        print(result["citations"])
        print("-" * 80)
        print()
        
        # Check for [unknown] references
        if "[unknown]" in result["citations"]:
            print("❌ WARNING: Found [unknown] references!")
        else:
            print("✅ All sources have proper names!")
    else:
        print("❌ No citations field in response")

    print()
    print("📝 LOGS:")
    for log in result.get("logs", []):
        print(f"   {log}")

    print()
    print("🔍 STRATEGY EXECUTED:")
    print(f"   Execution Path: {result.get('execution_path', 'N/A')}")
    
except Exception as e:
    print(f"❌ ERROR: {e}")

print()
print("=" * 80)

