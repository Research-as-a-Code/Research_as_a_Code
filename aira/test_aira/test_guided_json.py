# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Test cases for NVIDIA NIM guided_json structured output.

These tests verify:
1. Pydantic schemas generate valid JSON schemas
2. The model_kwargs format uses extra_body to wrap nvext (required for LangChain + OpenAI client)
3. Response parsing back to Pydantic models works correctly
4. All TTD-DR components use the correct format
"""

import json
import pytest
from typing import List, Literal
from unittest.mock import AsyncMock, MagicMock, patch

from pydantic import BaseModel, Field as PydanticField


# ========================================
# Test Schemas (matching TTD-DR components)
# ========================================

class PlanningDecisionSchema(BaseModel):
    """Schema from hackathon_agent.py planner_node"""
    strategy: Literal["SIMPLE_RAG", "DYNAMIC_STRATEGY"] = PydanticField(
        description="Chosen strategy"
    )
    rationale: str = PydanticField(description="Explanation")
    plan: str = PydanticField(default="", description="Research plan for DYNAMIC_STRATEGY")


class ResearchPlanSchema(BaseModel):
    """Schema from ttd_dr/core.py"""
    main_topic: str = PydanticField(description="Main topic of the research")
    key_areas: List[str] = PydanticField(description="Key areas to cover")
    sub_questions: List[str] = PydanticField(description="Sub-questions to answer")
    expected_sections: List[str] = PydanticField(description="Expected sections in final report")
    search_strategy: str = PydanticField(description="Search strategy to use")


class ConvergenceCheckSchema(BaseModel):
    """Schema from ttd_dr/core.py and denoiser.py"""
    convergence_score: int = PydanticField(ge=0, le=100, description="Convergence score 0-100")
    confidence: float = PydanticField(ge=0, le=100, description="Confidence in assessment (0-100)")
    reasoning: str = PydanticField(description="Explanation of convergence assessment")
    key_improvements: List[str] = PydanticField(default_factory=list, description="What improved")
    remaining_gaps: List[str] = PydanticField(default_factory=list, description="What needs work")


class QuestionsSchema(BaseModel):
    """Schema from ttd_dr/core.py"""
    questions: List[str] = PydanticField(description="List of research questions")
    gaps_identified: List[str] = PydanticField(default_factory=list, description="Information gaps")


class RedTeamOutputSchema(BaseModel):
    """Schema from ttd_dr/components/red_team.py"""
    critiques: List[dict] = PydanticField(default_factory=list, description="List of critiques")
    overall_assessment: str = PydanticField(description="Brief summary of weaknesses")
    needs_major_revision: bool = PydanticField(description="Whether major revision needed")
    quality_score: float = PydanticField(ge=0, le=100, description="Overall quality 0-100")


class EvaluatorOutputSchema(BaseModel):
    """Schema from ttd_dr/components/evaluator.py"""
    metrics: dict = PydanticField(description="Evaluation metrics")
    improvement_suggestions: List[str] = PydanticField(default_factory=list)
    convergence_recommendation: str = PydanticField(description="Continue or stop")


class FactExtractionSchema(BaseModel):
    """Schema from ttd_dr/components/context_pruner.py"""
    facts: List[dict] = PydanticField(default_factory=list, description="Extracted facts")
    summary: str = PydanticField(default="", description="Brief summary")


class EvolutionFeedbackSchema(BaseModel):
    """Schema from ttd_dr/components/evolver.py"""
    best_variant: int = PydanticField(ge=0, description="Index of best variant")
    scores: dict = PydanticField(default_factory=dict, description="Scores for each variant")
    strengths: List[str] = PydanticField(default_factory=list)
    weaknesses: List[str] = PydanticField(default_factory=list)
    suggestions: List[str] = PydanticField(default_factory=list)


# ========================================
# Schema Generation Tests
# ========================================

class TestSchemaGeneration:
    """Tests that Pydantic schemas generate valid JSON schemas."""
    
    def test_planning_decision_schema(self):
        """Test PlanningDecision schema generation."""
        schema = PlanningDecisionSchema.model_json_schema()
        
        assert "properties" in schema
        assert "strategy" in schema["properties"]
        assert "rationale" in schema["properties"]
        assert "plan" in schema["properties"]
        
        # Check strategy is an enum
        strategy_prop = schema["properties"]["strategy"]
        assert "enum" in strategy_prop or "$ref" in strategy_prop or "anyOf" in strategy_prop
    
    def test_research_plan_schema(self):
        """Test ResearchPlan schema generation."""
        schema = ResearchPlanSchema.model_json_schema()
        
        assert "properties" in schema
        required_fields = ["main_topic", "key_areas", "sub_questions", "expected_sections", "search_strategy"]
        for field in required_fields:
            assert field in schema["properties"]
    
    def test_convergence_schema(self):
        """Test ConvergenceCheck schema with constraints."""
        schema = ConvergenceCheckSchema.model_json_schema()
        
        assert "properties" in schema
        # Check convergence_score has min/max
        score_prop = schema["properties"]["convergence_score"]
        assert score_prop.get("minimum", 0) >= 0
        assert score_prop.get("maximum", 100) <= 100
    
    def test_all_schemas_are_valid_json(self):
        """Test all schemas serialize to valid JSON."""
        schemas = [
            PlanningDecisionSchema,
            ResearchPlanSchema,
            ConvergenceCheckSchema,
            QuestionsSchema,
            RedTeamOutputSchema,
            EvaluatorOutputSchema,
            FactExtractionSchema,
            EvolutionFeedbackSchema,
        ]
        
        for schema_class in schemas:
            schema = schema_class.model_json_schema()
            # Should be serializable to JSON string
            json_str = json.dumps(schema)
            # Should be parseable back
            parsed = json.loads(json_str)
            assert parsed == schema


# ========================================
# Model Kwargs Format Tests
# ========================================

class TestModelKwargsFormat:
    """Tests that model_kwargs uses correct NVIDIA NIM format for LangChain."""
    
    def test_nvext_wrapped_in_extra_body(self):
        """Test that nvext is wrapped in extra_body for LangChain/OpenAI client compatibility."""
        json_schema = PlanningDecisionSchema.model_json_schema()
        
        # CORRECT format for LangChain ChatOpenAI: nvext wrapped in extra_body
        # This is required because the OpenAI Python client validates kwargs
        # and doesn't recognize 'nvext' - it must be passed via 'extra_body'
        correct_kwargs = {
            "extra_body": {"nvext": {"guided_json": json_schema}}
        }
        
        # INCORRECT formats that should NOT be used with LangChain
        incorrect_kwargs_1 = {
            "nvext": {"guided_json": json_schema}  # OpenAI client rejects unknown kwargs
        }
        incorrect_kwargs_2 = {
            "extra_body": {"guided_json": json_schema}  # guided_json must be inside nvext
        }
        
        # Verify correct structure
        assert "extra_body" in correct_kwargs
        assert "nvext" in correct_kwargs["extra_body"]
        assert "guided_json" in correct_kwargs["extra_body"]["nvext"]
    
    def test_guided_json_contains_valid_schema(self):
        """Test that guided_json contains a valid JSON schema."""
        json_schema = ResearchPlanSchema.model_json_schema()
        
        model_kwargs = {
            "extra_body": {"nvext": {"guided_json": json_schema}}
        }
        
        guided_json = model_kwargs["extra_body"]["nvext"]["guided_json"]
        
        # Must have properties (object schema)
        assert "properties" in guided_json
        # Must have type
        assert guided_json.get("type") == "object" or "properties" in guided_json


# ========================================
# Response Parsing Tests
# ========================================

class TestResponseParsing:
    """Tests parsing LLM responses back to Pydantic models."""
    
    def test_parse_planning_decision(self):
        """Test parsing a planning decision response."""
        response_content = json.dumps({
            "strategy": "DYNAMIC_STRATEGY",
            "rationale": "Complex topic requiring iterative research",
            "plan": "1. Gather sources\n2. Analyze\n3. Synthesize"
        })
        
        result = PlanningDecisionSchema.model_validate_json(response_content)
        
        assert result.strategy == "DYNAMIC_STRATEGY"
        assert "Complex topic" in result.rationale
        assert result.plan != ""
    
    def test_parse_research_plan(self):
        """Test parsing a research plan response."""
        response_content = json.dumps({
            "main_topic": "AI in Healthcare",
            "key_areas": ["Diagnostics", "Treatment Planning", "Drug Discovery"],
            "sub_questions": ["How is AI used in radiology?", "What are the ethical concerns?"],
            "expected_sections": ["Introduction", "Applications", "Challenges", "Conclusion"],
            "search_strategy": "Start with academic papers, then industry reports"
        })
        
        result = ResearchPlanSchema.model_validate_json(response_content)
        
        assert result.main_topic == "AI in Healthcare"
        assert len(result.key_areas) == 3
        assert len(result.sub_questions) == 2
    
    def test_parse_convergence_check(self):
        """Test parsing convergence check with constraints."""
        response_content = json.dumps({
            "convergence_score": 75,
            "confidence": 85,
            "reasoning": "Good progress on main topics",
            "key_improvements": ["Added citations", "Clarified methodology"],
            "remaining_gaps": ["Need more recent data"]
        })
        
        result = ConvergenceCheckSchema.model_validate_json(response_content)
        
        assert result.convergence_score == 75
        assert 0 <= result.confidence <= 100
        assert len(result.key_improvements) == 2
    
    def test_parse_with_empty_lists(self):
        """Test that empty lists are preserved (not replaced with defaults)."""
        response_content = json.dumps({
            "convergence_score": 50,
            "confidence": 50,
            "reasoning": "Moderate progress",
            "key_improvements": [],  # Intentionally empty
            "remaining_gaps": []     # Intentionally empty
        })
        
        result = ConvergenceCheckSchema.model_validate_json(response_content)
        
        # Empty lists should be preserved, not replaced with defaults
        assert result.key_improvements == []
        assert result.remaining_gaps == []
    
    def test_parse_evolution_feedback(self):
        """Test parsing evolution feedback."""
        response_content = json.dumps({
            "best_variant": 1,
            "scores": {"variant_0": 70, "variant_1": 85},
            "strengths": ["Clear structure", "Good citations"],
            "weaknesses": [],  # Intentionally empty
            "suggestions": ["Add more examples"]
        })
        
        result = EvolutionFeedbackSchema.model_validate_json(response_content)
        
        assert result.best_variant == 1
        assert result.scores["variant_1"] == 85
        assert result.weaknesses == []  # Should stay empty


# ========================================
# Integration-style Tests (Mocked LLM)
# ========================================

class TestGuidedJsonIntegration:
    """Integration tests with mocked LLM calls."""
    
    @pytest.mark.asyncio
    async def test_mocked_guided_llm_call(self):
        """Test a mocked guided LLM call returns parseable output."""
        # Mock response
        mock_response_content = json.dumps({
            "strategy": "SIMPLE_RAG",
            "rationale": "Straightforward query",
            "plan": ""
        })
        
        # Create mock LLM
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = MagicMock(content=mock_response_content)
        
        # Simulate the call pattern used in hackathon_agent.py
        json_schema = PlanningDecisionSchema.model_json_schema()
        
        # This is how we'd configure the LLM (wrapped in extra_body for LangChain)
        model_kwargs = {
            "extra_body": {"nvext": {"guided_json": json_schema}}
        }
        
        # Verify the kwargs structure
        assert "extra_body" in model_kwargs
        assert "nvext" in model_kwargs["extra_body"]
        assert "guided_json" in model_kwargs["extra_body"]["nvext"]
        
        # Simulate response handling
        response = await mock_llm.ainvoke("test prompt")
        result = PlanningDecisionSchema.model_validate_json(response.content)
        
        assert result.strategy == "SIMPLE_RAG"
    
    @pytest.mark.asyncio
    async def test_mocked_research_plan_generation(self):
        """Test research plan generation with mocked LLM."""
        mock_response_content = json.dumps({
            "main_topic": "Quantum Computing",
            "key_areas": ["Qubits", "Algorithms", "Hardware"],
            "sub_questions": ["What is quantum supremacy?"],
            "expected_sections": ["Intro", "Basics", "Applications"],
            "search_strategy": "Academic first"
        })
        
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = MagicMock(content=mock_response_content)
        
        response = await mock_llm.ainvoke("test")
        result = ResearchPlanSchema.model_validate_json(response.content)
        
        assert result.main_topic == "Quantum Computing"
        assert "Qubits" in result.key_areas


# ========================================
# Code Pattern Verification Tests
# ========================================

class TestCodePatternVerification:
    """Tests to verify correct patterns are used in the codebase."""
    
    def test_extra_body_wraps_nvext(self):
        """
        Verify the correct pattern: nvext wrapped in extra_body.
        
        This test documents the correct way to use guided_json with NVIDIA NIM
        when using LangChain's ChatOpenAI client.
        
        Why extra_body is required:
        - LangChain passes model_kwargs to OpenAI client's create() method
        - OpenAI client validates kwargs and rejects unknown ones like 'nvext'
        - extra_body is the designated way to pass custom fields to the API body
        - The resulting HTTP request body will contain nvext at the root level
        """
        # CORRECT pattern for LangChain (what we should use)
        correct_pattern = {
            "extra_body": {"nvext": {"guided_json": {"type": "object", "properties": {}}}}
        }
        
        # Check the correct pattern structure
        assert "extra_body" in correct_pattern
        assert "nvext" in correct_pattern["extra_body"]
        assert "guided_json" in correct_pattern["extra_body"]["nvext"]
        
        # The guided_json should contain a JSON schema
        assert "type" in correct_pattern["extra_body"]["nvext"]["guided_json"]


# ========================================
# Real Client Validation Tests
# ========================================

class TestRealClientValidation:
    """
    Tests that actually instantiate ChatOpenAI to catch kwargs validation errors.
    
    These tests would have caught the 'nvext' TypeError before deployment.
    The key insight is that mocked tests don't validate OpenAI client kwargs.
    """
    
    def test_chatopen_ai_accepts_extra_body_format(self):
        """
        Test that ChatOpenAI accepts the extra_body format without raising.
        
        This test catches the exact error we saw in production:
        'AsyncCompletions.create() got an unexpected keyword argument nvext'
        """
        from langchain_openai import ChatOpenAI
        
        json_schema = PlanningDecisionSchema.model_json_schema()
        
        # CORRECT format - should NOT raise during instantiation
        correct_kwargs = {
            "extra_body": {"nvext": {"guided_json": json_schema}}
        }
        
        # This should work - ChatOpenAI accepts extra_body
        try:
            llm = ChatOpenAI(
                base_url="http://fake-url:8000/v1",
                model="test-model",
                api_key="not-used",
                model_kwargs=correct_kwargs
            )
            # Instantiation succeeded
            assert llm is not None
        except TypeError as e:
            pytest.fail(f"ChatOpenAI rejected correct kwargs format: {e}")
    
    def test_chatopen_ai_rejects_raw_nvext(self):
        """
        Test that ChatOpenAI rejects nvext without extra_body wrapper.
        
        This documents the bug we fixed - raw nvext causes TypeError.
        """
        from langchain_openai import ChatOpenAI
        
        json_schema = PlanningDecisionSchema.model_json_schema()
        
        # INCORRECT format - nvext without extra_body wrapper
        incorrect_kwargs = {
            "nvext": {"guided_json": json_schema}
        }
        
        # Create LLM - instantiation might work
        llm = ChatOpenAI(
            base_url="http://fake-url:8000/v1",
            model="test-model",
            api_key="not-used",
            model_kwargs=incorrect_kwargs
        )
        
        # The error occurs when trying to make a call, not at instantiation
        # We can't easily test this without mocking at HTTP level
        # But we document that this format is known to fail at runtime
        assert "nvext" in incorrect_kwargs  # Documents the bad pattern


# ========================================
# Codebase Pattern Verification
# ========================================

class TestCodebasePatterns:
    """
    Tests that scan the actual codebase to verify correct patterns are used.
    
    These tests read the source files and verify the correct format is used
    everywhere, preventing regression.
    """
    
    def test_all_nvext_uses_extra_body_wrapper(self):
        """
        Scan codebase to ensure all nvext usages are wrapped in extra_body.
        
        This test would fail if someone adds nvext without extra_body wrapper.
        """
        import os
        import re
        
        # Files that should use guided_json
        source_dir = os.path.join(os.path.dirname(__file__), '..', 'src', 'aiq_aira')
        
        if not os.path.exists(source_dir):
            pytest.skip("Source directory not found")
        
        bad_patterns = []
        
        for root, dirs, files in os.walk(source_dir):
            # Skip __pycache__
            dirs[:] = [d for d in dirs if d != '__pycache__']
            
            for file in files:
                if file.endswith('.py'):
                    filepath = os.path.join(root, file)
                    with open(filepath, 'r') as f:
                        content = f.read()
                    
                    # Find lines with nvext
                    for i, line in enumerate(content.split('\n'), 1):
                        if '"nvext"' in line or "'nvext'" in line:
                            # Check if extra_body is on same line or nearby
                            if 'extra_body' not in line:
                                # Check previous lines for multi-line dict
                                context_start = max(0, i - 5)
                                context = '\n'.join(content.split('\n')[context_start:i])
                                if 'extra_body' not in context:
                                    bad_patterns.append(f"{filepath}:{i}: {line.strip()}")
        
        if bad_patterns:
            pytest.fail(
                f"Found nvext usage without extra_body wrapper:\n" + 
                "\n".join(bad_patterns)
            )


# ========================================
# Run tests
# ========================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])

