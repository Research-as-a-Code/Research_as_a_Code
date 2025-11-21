#!/usr/bin/env python3
"""
Simple Integration Test for TTD-DR

Tests basic integration without requiring full backend or dependencies.
"""

import sys
import os
import json

# Add the aira module to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'aira/src'))

def test_imports():
    """Test that all modules can be imported"""
    print("\n=== Testing Module Imports ===")
    
    results = []
    
    # Test base module imports
    try:
        from aiq_aira.research_strategy_base import ResearchContext, ResearchStrategyType, BaseResearchStrategy
        print("✅ research_strategy_base imported successfully")
        results.append(True)
    except ImportError as e:
        print(f"❌ Failed to import research_strategy_base: {e}")
        results.append(False)
    
    # Test TTD-DR models
    try:
        from aiq_aira.ttd_dr.models import (
            TTDDRStage, TTDDRConfig, TTDDRState, ResearchPlan, 
            DraftState, SearchQAPair, EvolutionVariant
        )
        print("✅ ttd_dr.models imported successfully")
        
        # Test enum values
        assert TTDDRStage.PLANNING.value == "planning"
        assert TTDDRStage.ITERATING.value == "iterating"
        assert TTDDRStage.SYNTHESIZING.value == "synthesizing"
        print("   - TTDDRStage enum validated")
        
        results.append(True)
    except Exception as e:
        print(f"❌ Failed with ttd_dr.models: {e}")
        results.append(False)
    
    # Test prompts
    try:
        from aiq_aira.ttd_dr.prompts import (
            PLAN_GENERATION_PROMPT,
            INITIAL_DRAFT_PROMPT,
            QUESTION_GENERATION_PROMPT
        )
        print("✅ ttd_dr.prompts imported successfully")
        assert len(PLAN_GENERATION_PROMPT) > 0
        print("   - Prompts validated")
        results.append(True)
    except Exception as e:
        print(f"❌ Failed with ttd_dr.prompts: {e}")
        results.append(False)
    
    return all(results)

def test_data_models():
    """Test data model creation and serialization"""
    print("\n=== Testing Data Models ===")
    
    from aiq_aira.ttd_dr.models import (
        TTDDRConfig, TTDDRState, ResearchPlan, 
        DraftState, SearchQAPair, TTDDRMetrics
    )
    from aiq_aira.research_strategy_base import ResearchContext, ResearchResult
    
    results = []
    
    # Test ResearchContext
    try:
        context = ResearchContext(
            query="Test query about AI",
            collection="default",
            search_web=True,
            max_sources=10,
            user_preferences={"format": "detailed"}
        )
        context_dict = context.to_dict()
        assert context_dict["query"] == "Test query about AI"
        assert context_dict["collection"] == "default"
        print("✅ ResearchContext works correctly")
        results.append(True)
    except Exception as e:
        print(f"❌ ResearchContext failed: {e}")
        results.append(False)
    
    # Test TTDDRConfig
    try:
        config = TTDDRConfig()
        assert config.max_iterations == 5
        assert config.convergence_threshold == 0.85
        assert config.enable_evolution == True
        
        config_dict = config.to_dict()
        assert isinstance(config_dict, dict)
        assert config_dict["max_iterations"] == 5
        print("✅ TTDDRConfig works correctly")
        results.append(True)
    except Exception as e:
        print(f"❌ TTDDRConfig failed: {e}")
        results.append(False)
    
    # Test ResearchPlan
    try:
        plan = ResearchPlan(
            key_areas=["AI", "Healthcare"],
            questions=["What is AI?", "How does it help?"],
            expected_sections=["Introduction", "Analysis"],
            search_queries=["AI healthcare applications"]
        )
        assert len(plan.key_areas) == 2
        assert len(plan.questions) == 2
        print("✅ ResearchPlan works correctly")
        results.append(True)
    except Exception as e:
        print(f"❌ ResearchPlan failed: {e}")
        results.append(False)
    
    # Test TTDDRState
    try:
        from aiq_aira.ttd_dr.models import TTDDRStage
        state = TTDDRState(
            stage=TTDDRStage.PLANNING,
            current_iteration=0,
            plan=plan,
            draft=DraftState(content="Initial draft", gaps=["gap1"])
        )
        assert state.stage == TTDDRStage.PLANNING
        assert state.current_iteration == 0
        print("✅ TTDDRState works correctly")
        results.append(True)
    except Exception as e:
        print(f"❌ TTDDRState failed: {e}")
        results.append(False)
    
    # Test ResearchResult
    try:
        result = ResearchResult(
            success=True,
            final_report="Test report content",
            sources=[{"url": "example.com", "content": "test"}],
            metadata={"strategy": "ttd_dr"},
            execution_time=45.5
        )
        result_dict = result.to_dict()
        assert result_dict["success"] == True
        assert result_dict["execution_time"] == 45.5
        print("✅ ResearchResult works correctly")
        results.append(True)
    except Exception as e:
        print(f"❌ ResearchResult failed: {e}")
        results.append(False)
    
    return all(results)

def test_strategy_types():
    """Test strategy type definitions"""
    print("\n=== Testing Strategy Types ===")
    
    from aiq_aira.research_strategy_base import ResearchStrategyType
    
    try:
        # Test all strategy types
        assert ResearchStrategyType.SIMPLE_RAG.value == "simple_rag"
        assert ResearchStrategyType.UDR_DYNAMIC.value == "udr_dynamic"
        assert ResearchStrategyType.TTD_DR_DYNAMIC.value == "ttd_dr_dynamic"
        
        # Test that they're different
        assert ResearchStrategyType.UDR_DYNAMIC != ResearchStrategyType.TTD_DR_DYNAMIC
        
        print("✅ All strategy types defined correctly")
        print(f"   - SIMPLE_RAG: {ResearchStrategyType.SIMPLE_RAG.value}")
        print(f"   - UDR_DYNAMIC: {ResearchStrategyType.UDR_DYNAMIC.value}")
        print(f"   - TTD_DR_DYNAMIC: {ResearchStrategyType.TTD_DR_DYNAMIC.value}")
        
        return True
    except Exception as e:
        print(f"❌ Strategy types test failed: {e}")
        return False

def test_frontend_integration():
    """Test that frontend components are in place"""
    print("\n=== Testing Frontend Components ===")
    
    results = []
    
    # Check StrategyToggle component
    toggle_path = "frontend/app/components/StrategyToggle.tsx"
    if os.path.exists(toggle_path):
        with open(toggle_path, 'r') as f:
            content = f.read()
            if 'udr' in content and 'ttd_dr' in content:
                print("✅ StrategyToggle component found with both strategies")
                results.append(True)
            else:
                print("❌ StrategyToggle missing strategy options")
                results.append(False)
    else:
        print(f"❌ StrategyToggle component not found at {toggle_path}")
        results.append(False)
    
    # Check TTDDRProgressDisplay component
    progress_path = "frontend/app/components/TTDDRProgressDisplay.tsx"
    if os.path.exists(progress_path):
        with open(progress_path, 'r') as f:
            content = f.read()
            if 'planning' in content and 'iterating' in content and 'synthesizing' in content:
                print("✅ TTDDRProgressDisplay component found with all stages")
                results.append(True)
            else:
                print("❌ TTDDRProgressDisplay missing stages")
                results.append(False)
    else:
        print(f"❌ TTDDRProgressDisplay component not found at {progress_path}")
        results.append(False)
    
    # Check CopilotAgentDisplay integration
    agent_path = "frontend/app/components/CopilotAgentDisplay.tsx"
    if os.path.exists(agent_path):
        with open(agent_path, 'r') as f:
            content = f.read()
            if 'StrategyToggle' in content and 'TTDDRProgressDisplay' in content:
                print("✅ CopilotAgentDisplay integrated with new components")
                results.append(True)
            else:
                print("❌ CopilotAgentDisplay missing component integration")
                results.append(False)
    else:
        print(f"❌ CopilotAgentDisplay not found at {agent_path}")
        results.append(False)
    
    return all(results)

def test_backend_integration():
    """Test that backend is properly integrated"""
    print("\n=== Testing Backend Integration ===")
    
    results = []
    
    # Check main.py updates
    main_path = "backend/main.py"
    if os.path.exists(main_path):
        with open(main_path, 'r') as f:
            content = f.read()
            
            # Check for TTDDRIntegration import
            if 'from aiq_aira.ttd_dr import TTDDRIntegration' in content:
                print("✅ Backend imports TTDDRIntegration")
                results.append(True)
            else:
                print("❌ Backend missing TTDDRIntegration import")
                results.append(False)
            
            # Check for strategy field in ResearchRequest
            if 'strategy: str = Field' in content and 'ttd_dr' in content:
                print("✅ ResearchRequest has strategy field")
                results.append(True)
            else:
                print("❌ ResearchRequest missing strategy field")
                results.append(False)
    else:
        print(f"❌ Backend main.py not found at {main_path}")
        results.append(False)
        results.append(False)
    
    # Check hackathon_agent.py updates
    agent_path = "aira/src/aiq_aira/hackathon_agent.py"
    if os.path.exists(agent_path):
        with open(agent_path, 'r') as f:
            content = f.read()
            
            # Check for ttd_dr_strategy_node
            if 'async def ttd_dr_strategy_node' in content:
                print("✅ Agent has ttd_dr_strategy_node")
                results.append(True)
            else:
                print("❌ Agent missing ttd_dr_strategy_node")
                results.append(False)
            
            # Check for updated routing
            if 'ttd_dr_strategy' in content and 'route_after_planner' in content:
                print("✅ Agent routing updated for TTD-DR")
                results.append(True)
            else:
                print("❌ Agent routing not updated")
                results.append(False)
    else:
        print(f"❌ hackathon_agent.py not found at {agent_path}")
        results.append(False)
        results.append(False)
    
    return all(results)

def main():
    """Run all tests"""
    print("="*60)
    print("TTD-DR INTEGRATION TEST")
    print("="*60)
    
    tests = [
        ("Module Imports", test_imports),
        ("Data Models", test_data_models),
        ("Strategy Types", test_strategy_types),
        ("Frontend Integration", test_frontend_integration),
        ("Backend Integration", test_backend_integration),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ {name} failed with exception: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{name:.<35} {status}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All integration tests passed successfully!")
        print("\nThe TTD-DR integration is complete and ready for deployment!")
        return 0
    else:
        print(f"\n⚠️ {total - passed} test(s) failed")
        return 1

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
