#!/usr/bin/env python3
"""Test citations formatting for UDR and TTD-DR strategies."""

import requests
import json

BACKEND_URL = "http://af3615e06391145bc88022ac024a36ca-bd296660cda3522f.elb.us-west-2.amazonaws.com"

# Test query
payload = {
    "topic": "What factors I need to consider (such as weight, important ingredients) when I need to decide tariff codes for various sweets? Mention tariff codes or code ranges.",
    "report_organization": "Create a comprehensive report with introduction, detailed analysis, and conclusion. Perform a deep research and must use dynamic strategy. Try to utilize the us_tariff collection as well.",
    "collection": "us_tariffs",
    "search_web": True,
    "strategy": "udr"  # Test with UDR first
}

print("=" * 80)
print("Testing Citation Formatting - UDR Strategy")
print("=" * 80)
print()

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
print("=" * 80)

