#!/usr/bin/env python3
"""
Test Script for UDR and TTD-DR Strategies

This script tests both research strategies (UDR and TTD-DR) with sample queries
to ensure the integration is working correctly.
"""

import asyncio
import json
import sys
import time
from typing import Dict, Any
import aiohttp
from datetime import datetime

# Configuration
BACKEND_URL = "http://localhost:8000"
TEST_QUERIES = [
    {
        "name": "Simple Query Test",
        "topic": "What are the key features of Python programming language?",
        "complexity": "simple",
        "expected_route": "simple_rag"
    },
    {
        "name": "Complex Query Test",
        "topic": "Analyze the cost-benefit tradeoffs of implementing microservices architecture versus monolithic architecture for a mid-size e-commerce platform",
        "complexity": "complex",
        "expected_route": "dynamic"
    },
    {
        "name": "Multi-Domain Test",
        "topic": "Compare the environmental impact, economic viability, and technological challenges of solar energy versus nuclear fusion as future energy sources",
        "complexity": "complex",
        "expected_route": "dynamic"
    }
]

def print_header(text: str):
    """Print a formatted header"""
    print("\n" + "="*80)
    print(f"  {text}")
    print("="*80)

def print_section(text: str):
    """Print a formatted section"""
    print(f"\n--- {text} ---")

async def test_strategy(query: Dict[str, Any], strategy: str) -> Dict[str, Any]:
    """
    Test a single strategy with a given query.
    
    Args:
        query: Test query details
        strategy: Either 'udr' or 'ttd_dr'
    
    Returns:
        Test results including timing and response
    """
    print_section(f"Testing {strategy.upper()} Strategy")
    print(f"Query: {query['topic'][:100]}...")
    print(f"Expected complexity: {query['complexity']}")
    
    start_time = time.time()
    
    async with aiohttp.ClientSession() as session:
        try:
            # Prepare request
            request_data = {
                "topic": query["topic"],
                "report_organization": "• Executive Summary\n• Key Findings\n• Detailed Analysis\n• Recommendations",
                "collection": "",
                "search_web": True,
                "strategy": strategy
            }
            
            print(f"\n📤 Sending request to {BACKEND_URL}/research/stream")
            print(f"   Strategy: {strategy}")
            
            # Send streaming request
            async with session.post(
                f"{BACKEND_URL}/research/stream",
                json=request_data,
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    print(f"❌ Error {response.status}: {error_text}")
                    return {
                        "success": False,
                        "error": f"HTTP {response.status}: {error_text}",
                        "duration": time.time() - start_time
                    }
                
                # Process SSE stream
                events_received = []
                final_report = None
                ttd_dr_stages = []
                udr_executed = False
                
                print("\n📥 Receiving events:")
                
                async for line in response.content:
                    line_text = line.decode('utf-8').strip()
                    
                    if not line_text or line_text.startswith(':'):
                        continue
                    
                    if line_text.startswith('data: '):
                        try:
                            data = json.loads(line_text[6:])
                            events_received.append(data)
                            
                            if data.get('type') == 'update':
                                node = data.get('node', 'unknown')
                                print(f"   • Node: {node}")
                                
                                state = data.get('state', {})
                                
                                # Track UDR execution
                                if state.get('udr_strategy'):
                                    udr_executed = True
                                    print(f"     ✓ UDR strategy compiled")
                                
                                # Track TTD-DR progress
                                if state.get('ttd_dr_stage'):
                                    stage = state['ttd_dr_stage']
                                    if stage not in ttd_dr_stages:
                                        ttd_dr_stages.append(stage)
                                        print(f"     ✓ TTD-DR stage: {stage}")
                                
                                if state.get('ttd_dr_iteration'):
                                    print(f"     → Iteration {state['ttd_dr_iteration']}")
                                
                                if state.get('ttd_dr_convergence'):
                                    scores = state['ttd_dr_convergence']
                                    if scores:
                                        print(f"     → Convergence: {scores[-1]:.2%}")
                                
                                # Capture final report
                                if state.get('final_report'):
                                    final_report = state['final_report']
                                    print(f"     ✓ Final report received ({len(final_report)} chars)")
                            
                            elif data.get('type') == 'complete':
                                print(f"   • Research completed")
                                break
                            
                            elif data.get('type') == 'error':
                                print(f"   • ❌ Error: {data.get('message')}")
                                break
                                
                        except json.JSONDecodeError:
                            print(f"   • Warning: Invalid JSON in event")
                            continue
                
                duration = time.time() - start_time
                
                # Analyze results
                result = {
                    "success": final_report is not None,
                    "duration": duration,
                    "events_count": len(events_received),
                    "final_report_length": len(final_report) if final_report else 0,
                    "strategy_executed": strategy
                }
                
                if strategy == 'udr':
                    result["udr_executed"] = udr_executed
                elif strategy == 'ttd_dr':
                    result["ttd_dr_stages"] = ttd_dr_stages
                
                print(f"\n✅ Test completed in {duration:.2f} seconds")
                print(f"   Events received: {len(events_received)}")
                print(f"   Report length: {result['final_report_length']} chars")
                
                if strategy == 'udr' and udr_executed:
                    print(f"   UDR strategy: Executed")
                elif strategy == 'ttd_dr' and ttd_dr_stages:
                    print(f"   TTD-DR stages completed: {', '.join(ttd_dr_stages)}")
                
                return result
                
        except aiohttp.ClientError as e:
            print(f"\n❌ Connection error: {e}")
            return {
                "success": False,
                "error": str(e),
                "duration": time.time() - start_time
            }
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            return {
                "success": False,
                "error": str(e),
                "duration": time.time() - start_time
            }

async def run_tests():
    """Run all test scenarios"""
    print_header(f"Testing Research Strategies - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Check backend availability
    print("\n🔍 Checking backend availability...")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{BACKEND_URL}/health") as response:
                if response.status == 200:
                    print(f"✅ Backend is available at {BACKEND_URL}")
                else:
                    print(f"⚠️ Backend returned status {response.status}")
    except Exception as e:
        print(f"❌ Backend is not available: {e}")
        print(f"   Please ensure the backend is running at {BACKEND_URL}")
        return
    
    # Test each query with both strategies
    all_results = []
    
    for i, query in enumerate(TEST_QUERIES, 1):
        print_header(f"Test {i}/{len(TEST_QUERIES)}: {query['name']}")
        
        # Test with UDR
        udr_result = await test_strategy(query, 'udr')
        all_results.append({
            "query": query['name'],
            "strategy": "udr",
            "result": udr_result
        })
        
        # Brief pause between tests
        await asyncio.sleep(2)
        
        # Test with TTD-DR (only for complex queries)
        if query['complexity'] == 'complex':
            ttd_dr_result = await test_strategy(query, 'ttd_dr')
            all_results.append({
                "query": query['name'],
                "strategy": "ttd_dr",
                "result": ttd_dr_result
            })
            
            # Compare results
            if udr_result['success'] and ttd_dr_result['success']:
                print_section("Strategy Comparison")
                print(f"UDR Duration: {udr_result['duration']:.2f}s")
                print(f"TTD-DR Duration: {ttd_dr_result['duration']:.2f}s")
                print(f"Speed difference: {ttd_dr_result['duration'] - udr_result['duration']:.2f}s")
                print(f"UDR Report size: {udr_result['final_report_length']} chars")
                print(f"TTD-DR Report size: {ttd_dr_result['final_report_length']} chars")
    
    # Final summary
    print_header("Test Summary")
    
    successful_tests = sum(1 for r in all_results if r['result']['success'])
    total_tests = len(all_results)
    
    print(f"\nTotal tests run: {total_tests}")
    print(f"Successful: {successful_tests}")
    print(f"Failed: {total_tests - successful_tests}")
    
    # Group by strategy
    udr_results = [r for r in all_results if r['strategy'] == 'udr']
    ttd_dr_results = [r for r in all_results if r['strategy'] == 'ttd_dr']
    
    if udr_results:
        udr_success = sum(1 for r in udr_results if r['result']['success'])
        udr_avg_time = sum(r['result']['duration'] for r in udr_results) / len(udr_results)
        print(f"\nUDR Strategy:")
        print(f"  Success rate: {udr_success}/{len(udr_results)}")
        print(f"  Average time: {udr_avg_time:.2f}s")
    
    if ttd_dr_results:
        ttd_success = sum(1 for r in ttd_dr_results if r['result']['success'])
        ttd_avg_time = sum(r['result']['duration'] for r in ttd_dr_results) / len(ttd_dr_results)
        print(f"\nTTD-DR Strategy:")
        print(f"  Success rate: {ttd_success}/{len(ttd_dr_results)}")
        print(f"  Average time: {ttd_avg_time:.2f}s")
    
    print("\n" + "="*80)
    print("Testing complete!")

if __name__ == "__main__":
    try:
        asyncio.run(run_tests())
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
