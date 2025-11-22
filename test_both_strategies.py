#!/usr/bin/env python3
"""Test citations for both UDR and TTD-DR with same query."""

import requests
import json

BACKEND_URL = "http://af3615e06391145bc88022ac024a36ca-bd296660cda3522f.elb.us-west-2.amazonaws.com"

# Complex query that will trigger dynamic strategy
base_payload = {
    "topic": "What factors I need to consider (such as weight, important ingredients) when I need to decide tariff codes for various sweets? Mention tariff codes or code ranges.",
    "report_organization": "Create a comprehensive report with introduction, detailed analysis, and conclusion. Perform a deep research and must use dynamic strategy. Try to utilize the us_tariff collection as well.",
    "collection": "us_tariffs",
    "search_web": True
}

def test_strategy(strategy_name):
    print("=" * 80)
    print(f"Testing {strategy_name.upper()} Strategy")
    print("=" * 80)
    print()
    
    payload = {**base_payload, "strategy": strategy_name}
    
    try:
        print(f"⏱️  Sending request (timeout: 180s)...")
        response = requests.post(f"{BACKEND_URL}/research", json=payload, timeout=180)
        result = response.json()

        print(f"✅ Response received ({response.status_code})")
        print()

        # Extract and display citations
        if "citations" in result:
            citations = result["citations"]
            print("📚 CITATIONS:")
            print("-" * 80)
            if len(citations) > 500:
                print(citations[:500] + "\n... (truncated)")
            else:
                print(citations)
            print("-" * 80)
            print()
            
            # Count sources
            num_sources = citations.count('\n- [')
            print(f"📊 Total sources: {num_sources}")
            
            # Check for [unknown] references
            if "[unknown]" in citations:
                unknown_count = citations.count("[unknown]")
                print(f"❌ WARNING: Found {unknown_count} [unknown] references!")
            else:
                print("✅ All sources have proper names!")
        else:
            print("❌ No citations field in response")

        print()
        print("📝 LOGS:")
        for log in result.get("logs", []):
            print(f"   {log}")

        print()
        
        return True
        
    except requests.exceptions.Timeout:
        print(f"⏱️  ❌ Request timed out after 180 seconds")
        print(f"   (TTD-DR may take longer due to iterative refinement)")
        return False
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False
    
    print()

# Test both strategies
print("\n\n")
test_strategy("udr")
print("\n\n")

print("⏳ Waiting 5 seconds before next test...")
import time
time.sleep(5)

test_strategy("ttd_dr")

print()
print("=" * 80)
print("✅ Testing Complete")
print("=" * 80)

