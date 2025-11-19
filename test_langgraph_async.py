#!/usr/bin/env python3
"""
Minimal test case to reproduce the LangGraph + nested async issue.

This simulates:
1. A LangGraph node function that calls an async method
2. That method has nested async calls
3. Everything is executed via astream_events()
"""
import asyncio
import logging
from typing import Dict, Any
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestState(TypedDict):
    """Simple state for testing."""
    topic: str
    result: str


class AsyncExecutor:
    """Simulates the UDFStrategyExecutor."""
    
    async def execute_strategy(self, code: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Simulates execute_strategy method.
        This is where execution hangs in the real code!
        """
        import sys
        print("🟡 EXECUTOR execute_strategy ENTERED!", flush=True, file=sys.stderr)
        logger.info("=" * 80)
        logger.info("EXECUTOR: Starting execution")
        logger.info("=" * 80)
        
        # Simulate some async work
        await asyncio.sleep(0.1)
        print("🟡 EXECUTOR: Did some async work!", flush=True, file=sys.stderr)
        
        # Simulate calling nested async functions
        result = await self._nested_async_call()
        print(f"🟡 EXECUTOR: Returning result: {result}", flush=True, file=sys.stderr)
        
        return {"success": True, "report": result}
    
    async def _nested_async_call(self) -> str:
        """Simulates a nested async tool call."""
        await asyncio.sleep(0.1)
        return "Test result from nested async"


class Integration:
    """Simulates UDFIntegration."""
    
    def __init__(self):
        self.executor = AsyncExecutor()
    
    async def execute_dynamic_strategy(self, plan: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Simulates execute_dynamic_strategy.
        Calls the executor which has nested async.
        """
        import sys
        print("🟢 Integration execute_dynamic_strategy called!", flush=True, file=sys.stderr)
        logger.info("Starting dynamic strategy execution")
        print("🟢 About to call executor...", flush=True, file=sys.stderr)
        
        # This is where it hangs in the real code!
        result = await self.executor.execute_strategy(
            code="dummy_code",
            context=context
        )
        
        print(f"🟢 Executor returned! Success: {result['success']}", flush=True, file=sys.stderr)
        return result


# Global integration instance
integration = Integration()


async def dynamic_strategy_node(state: TestState) -> dict:
    """
    Simulates the dynamic_strategy_node from hackathon_agent.py.
    This is a LangGraph node that calls async methods with nested async.
    """
    import sys
    print("🔴 NODE: Starting", flush=True, file=sys.stderr)
    logger.info("NODE: Starting dynamic strategy node")
    
    context = {"topic": state["topic"]}
    
    print("🔵 NODE: About to call integration...", flush=True, file=sys.stderr)
    
    # Call the integration (which calls executor with nested async)
    try:
        print("⏰ NODE: Calling asyncio.wait_for...", flush=True, file=sys.stderr)
        result = await asyncio.wait_for(
            integration.execute_dynamic_strategy(
                plan="test_plan",
                context=context
            ),
            timeout=30.0
        )
        print(f"✅ NODE: Got result! Success: {result['success']}", flush=True, file=sys.stderr)
        
        return {
            "result": result["report"]
        }
    except asyncio.TimeoutError:
        print("❌ NODE: Timeout!", flush=True, file=sys.stderr)
        return {"result": "TIMEOUT"}
    except Exception as e:
        print(f"❌ NODE: Exception: {e}", flush=True, file=sys.stderr)
        import traceback
        traceback.print_exc()
        return {"result": f"ERROR: {e}"}


def create_test_graph():
    """Create a minimal LangGraph to test the issue."""
    workflow = StateGraph(TestState)
    
    # Add the node
    workflow.add_node("dynamic_strategy", dynamic_strategy_node)
    
    # Set entry and exit
    workflow.set_entry_point("dynamic_strategy")
    workflow.add_edge("dynamic_strategy", END)
    
    return workflow.compile()


async def test_with_astream_events():
    """
    Test using astream_events() like the real backend does.
    This is where the issue manifests!
    """
    print("\n" + "=" * 80)
    print("TEST 1: Using astream_events() (REAL SCENARIO)")
    print("=" * 80 + "\n")
    
    graph = create_test_graph()
    initial_state = {"topic": "test topic", "result": ""}
    
    event_count = 0
    async for event in graph.astream_events(initial_state, version="v2"):
        event_count += 1
        event_type = event.get("event", "")
        if event_type in ["on_chain_start", "on_chain_end"]:
            print(f"  Event #{event_count}: {event_type} - {event.get('name', 'N/A')}")
    
    print(f"\n✅ astream_events() completed after {event_count} events\n")


async def test_with_direct_call():
    """
    Test by calling the node directly (NO astream_events).
    This should work fine!
    """
    print("\n" + "=" * 80)
    print("TEST 2: Direct async call (CONTROL)")
    print("=" * 80 + "\n")
    
    state = {"topic": "test topic", "result": ""}
    result = await dynamic_strategy_node(state)
    
    print(f"\n✅ Direct call completed! Result: {result}\n")


async def main():
    """Run both tests."""
    print("\n" + "#" * 80)
    print("# MINIMAL TEST CASE: LangGraph + Nested Async")
    print("#" * 80 + "\n")
    
    # Test 1: With astream_events (where the issue happens)
    await test_with_astream_events()
    
    # Test 2: Direct call (control - should work)
    await test_with_direct_call()
    
    print("\n" + "#" * 80)
    print("# TESTS COMPLETED")
    print("#" * 80 + "\n")


if __name__ == "__main__":
    asyncio.run(main())

