#!/bin/bash

# SPDX-FileCopyrightText: Copyright (c) 2025 Research_as_a_Code Project
# SPDX-License-Identifier: Apache-2.0

# Test script to verify UDR vs TTD-DR strategy selection

BACKEND_URL="http://af3615e06391145bc88022ac024a36ca-bd296660cda3522f.elb.us-west-2.amazonaws.com"

echo "=================================================="
echo "Testing Strategy Selection: UDR vs TTD-DR"
echo "=================================================="
echo ""

# Test 1: UDR Strategy
echo "Test 1: Running with UDR strategy..."
echo "---------------------------------------"
curl -X POST "${BACKEND_URL}/research" \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "What are the benefits of containerization?",
    "report_organization": "Brief summary",
    "collection": "",
    "search_web": true,
    "strategy": "udr"
  }' 2>&1 | jq -r '.logs[]' | tee /tmp/udr-test.log

echo ""
echo "UDR Test Logs:"
cat /tmp/udr-test.log
echo ""
echo "---------------------------------------"
echo ""

# Small delay
sleep 3

# Test 2: TTD-DR Strategy
echo "Test 2: Running with TTD-DR strategy..."
echo "---------------------------------------"
curl -X POST "${BACKEND_URL}/research" \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "What are the benefits of containerization?",
    "report_organization": "Brief summary",
    "collection": "",
    "search_web": true,
    "strategy": "ttd_dr"
  }' 2>&1 | jq -r '.logs[]' | tee /tmp/ttd-dr-test.log

echo ""
echo "TTD-DR Test Logs:"
cat /tmp/ttd-dr-test.log
echo ""
echo "---------------------------------------"
echo ""

# Compare
echo "=================================================="
echo "COMPARISON:"
echo "=================================================="
echo ""
echo "UDR logs contain:"
grep -i "udr" /tmp/udr-test.log && echo "  ✅ UDR-specific messages found" || echo "  ❌ No UDR messages"
echo ""
echo "TTD-DR logs contain:"
grep -i "ttd" /tmp/ttd-dr-test.log && echo "  ✅ TTD-DR-specific messages found" || echo "  ❌ No TTD-DR messages"
echo ""

echo "=================================================="
echo ""
echo "KEY DIFFERENCES TO LOOK FOR:"
echo ""
echo "UDR (Strategy-as-Code):"
echo "  - Log: '✅ UDR strategy execution complete'"
echo "  - Execution path shows: 'UDR'"
echo "  - Should see compiled strategy code"
echo ""
echo "TTD-DR (Iterative Refinement):"
echo "  - Log: '✅ TTD-DR research completed'"
echo "  - Execution path shows: 'TTD-DR'"
echo "  - Should see iteration progress"
echo ""
echo "=================================================="

