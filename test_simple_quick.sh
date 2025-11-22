#!/bin/bash

# Quick SIMPLE_RAG test with a very simple query

BACKEND_URL="http://af3615e06391145bc88022ac024a36ca-bd296660cda3522f.elb.us-west-2.amazonaws.com"

echo "Testing SIMPLE_RAG with quick query..."
echo ""

curl -X POST "${BACKEND_URL}/research" \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "What is the tariff for chocolate?",
    "report_organization": "Very brief answer",
    "collection": "us_tariffs",
    "search_web": false,
    "strategy": "auto"
  }' 2>&1 | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print('✅ Response received')
    print('')
    print('📊 Execution Path:', data.get('execution_path', 'N/A'))
    print('')
    print('📚 CITATIONS:')
    print('-' * 80)
    citations = data.get('citations', 'No citations')
    print(citations)
    print('-' * 80)
    print('')
    
    # Check quality
    if '[unknown]' in citations:
        print('❌ Found [unknown] references')
    elif '[]' in citations and 'http' in citations:
        print('⚠️  Found empty brackets (missing titles)')
    else:
        print('✅ All sources properly formatted!')
    
    print('')
    print('📝 Logs:', data.get('logs', []))
except Exception as e:
    print(f'❌ Error: {e}')
"

