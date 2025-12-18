# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Evaluator Agent for TTD-DR.

This module implements a programmatic quality evaluator that provides
quantitative metrics for draft quality. It acts as a convergence check,
determining when the draft has reached acceptable quality.

Reference: Fareed Khan's TTD-DR implementation
"""

import logging
from dataclasses import dataclass
from typing import Dict, Any, List, Optional

from pydantic import BaseModel, Field as PydanticField
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI as LangChainChatOpenAI

logger = logging.getLogger(__name__)


# ========================================
# Pydantic Schema for NVIDIA Guided JSON
# ========================================

class EvaluatorOutputSchema(BaseModel):
    """Pydantic schema for evaluator output via guided JSON."""
    accuracy: float = PydanticField(ge=0, le=100, description="Factual correctness score (0-100)")
    completeness: float = PydanticField(ge=0, le=100, description="Coverage score (0-100)")
    coherence: float = PydanticField(ge=0, le=100, description="Logical flow score (0-100)")
    depth: float = PydanticField(ge=0, le=100, description="Analysis depth score (0-100)")
    citation_quality: float = PydanticField(ge=0, le=100, description="Evidence quality score (0-100)")
    overall_score: float = PydanticField(ge=0, le=100, description="Overall quality score (0-100)")
    confidence: float = PydanticField(ge=0, le=1, description="Confidence in assessment (0-1)")
    improvement_suggestions: List[str] = PydanticField(
        default_factory=list,
        description="Specific suggestions for improvement"
    )
    converged: bool = PydanticField(description="Whether draft has reached acceptable quality")
    reasoning: str = PydanticField(default="", description="Brief explanation of scores")


# ========================================
# Original Dataclasses (kept for compatibility)
# ========================================

@dataclass
class QualityMetrics:
    """
    Multi-dimensional quality assessment.
    
    Provides granular scores for different aspects of draft quality.
    """
    # Core metrics (0-100)
    accuracy: float  # Factual correctness
    completeness: float  # Coverage of required topics
    coherence: float  # Logical flow and structure
    depth: float  # Level of detail and analysis
    citation_quality: float  # Quality of evidence/sources
    
    # Derived metrics
    overall_score: float
    confidence: float  # Model's confidence in this assessment
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "accuracy": self.accuracy,
            "completeness": self.completeness,
            "coherence": self.coherence,
            "depth": self.depth,
            "citation_quality": self.citation_quality,
            "overall_score": self.overall_score,
            "confidence": self.confidence
        }
    
    def get_weakest_dimension(self) -> tuple[str, float]:
        """Get the dimension with lowest score."""
        dimensions = {
            "accuracy": self.accuracy,
            "completeness": self.completeness,
            "coherence": self.coherence,
            "depth": self.depth,
            "citation_quality": self.citation_quality
        }
        weakest = min(dimensions.items(), key=lambda x: x[1])
        return weakest


@dataclass
class EvaluationResult:
    """Complete evaluation result."""
    metrics: QualityMetrics
    improvement_suggestions: List[str]
    converged: bool
    iteration_delta: float  # Change from previous iteration
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "metrics": self.metrics.to_dict(),
            "improvement_suggestions": self.improvement_suggestions,
            "converged": self.converged,
            "iteration_delta": self.iteration_delta
        }
    
    def needs_quality_repair(self, threshold: float = 60.0) -> bool:
        """Check if draft needs quality repair."""
        return self.metrics.overall_score < threshold


EVALUATOR_PROMPT = """You are an expert research quality evaluator. Your job is to provide OBJECTIVE, QUANTITATIVE assessment of research draft quality.

IMPORTANT: Be a STRICT grader. LLMs tend to give overly generous scores. A score of 70 should mean "good", 80 should mean "very good", and 90+ should be reserved for exceptional work only.

## Research Brief (The Goal)
{research_brief}

## Current Draft to Evaluate
{draft}

## Evaluation Criteria

Score each dimension from 0-100:

1. **Accuracy** (0-100): How factually correct is the information?
   - 90+: All claims verifiable, no errors detected
   - 70-89: Minor uncertainties, generally accurate
   - 50-69: Some questionable claims or gaps
   - <50: Significant accuracy concerns

2. **Completeness** (0-100): Does the draft cover all required aspects?
   - 90+: Comprehensive coverage, all key areas addressed
   - 70-89: Good coverage, minor gaps
   - 50-69: Moderate gaps in coverage
   - <50: Major topics missing

3. **Coherence** (0-100): How well does it flow and make logical sense?
   - 90+: Excellent structure, clear logical progression
   - 70-89: Good structure, minor flow issues
   - 50-69: Some organizational problems
   - <50: Disorganized, hard to follow

4. **Depth** (0-100): How deep is the analysis?
   - 90+: Expert-level insights, non-obvious conclusions
   - 70-89: Good analysis, some novel insights
   - 50-69: Surface-level treatment
   - <50: Superficial, generic content

5. **Citation Quality** (0-100): How well is evidence used?
   - 90+: Strong evidence throughout, well-cited
   - 70-89: Good evidence, some gaps
   - 50-69: Weak evidence or missing citations
   - <50: Claims largely unsupported

## Previous Score (if available)
Previous overall score: {previous_score}

Remember: Be STRICT. Average work gets average scores. This counteracts LLM tendency toward generosity.
"""


class EvaluatorAgent:
    """
    Evaluator agent for programmatic quality assessment.
    
    Runs after each refinement step to provide quantitative feedback.
    Determines convergence and triggers quality repair when needed.
    
    Uses NVIDIA NIM guided_json for guaranteed structured output.
    """
    
    def __init__(self, 
                 llm: BaseChatModel,
                 convergence_threshold: float = 85.0,
                 min_improvement: float = 2.0):
        """
        Initialize Evaluator agent.
        
        Args:
            llm: Language model for evaluation
            convergence_threshold: Score above which draft is considered converged
            min_improvement: Minimum improvement between iterations to continue
        """
        self.llm = llm
        self.convergence_threshold = convergence_threshold
        self.min_improvement = min_improvement
        self.score_history: List[float] = []
        self.logger = logging.getLogger(f"{__name__}.EvaluatorAgent")
        
        # Extract LLM config for guided_json
        self._base_url = getattr(llm, 'openai_api_base', None) or getattr(llm, 'base_url', None)
        if self._base_url and hasattr(self._base_url, '__str__'):
            self._base_url = str(self._base_url)
        self._model_name = getattr(llm, 'model_name', "nvidia/llama-3.1-nemotron-nano-8b-v1")
    
    def _create_guided_llm(self) -> LangChainChatOpenAI:
        """Create LLM with NVIDIA guided_json for structured output."""
        json_schema = EvaluatorOutputSchema.model_json_schema()
        
        return LangChainChatOpenAI(
            base_url=self._base_url,
            model=self._model_name,
            api_key="not-used",
            model_kwargs={
                "extra_body": {
                    "nvext": {"guided_json": json_schema}  # NVIDIA NIM v1.12.0 format
                }
            }
        )
    
    async def evaluate(self,
                      draft: str,
                      research_brief: str,
                      iteration: int = 0,
                      previous_score: Optional[float] = None) -> EvaluationResult:
        """
        Evaluate draft quality.
        
        Args:
            draft: Current draft content
            research_brief: The original research brief/plan
            iteration: Current iteration number
            previous_score: Score from previous iteration
            
        Returns:
            EvaluationResult with metrics and convergence status
        """
        self.logger.info(f"📊 Evaluator analyzing draft (iteration {iteration})...")
        
        prev_score_str = str(previous_score) if previous_score is not None else "N/A (first evaluation)"
        
        prompt = EVALUATOR_PROMPT.format(
            research_brief=research_brief[:2000],
            draft=draft[:8000],
            previous_score=prev_score_str
        )
        
        try:
            # Use guided_json for guaranteed structured output
            guided_llm = self._create_guided_llm()
            
            response = await guided_llm.ainvoke([
                SystemMessage(content="You are a strict research quality evaluator."),
                HumanMessage(content=prompt)
            ])
            
            # Parse with Pydantic (guaranteed valid from guided_json)
            result_data = EvaluatorOutputSchema.model_validate_json(response.content)
            
            # Build metrics
            metrics = QualityMetrics(
                accuracy=result_data.accuracy,
                completeness=result_data.completeness,
                coherence=result_data.coherence,
                depth=result_data.depth,
                citation_quality=result_data.citation_quality,
                overall_score=result_data.overall_score,
                confidence=result_data.confidence
            )
            
            # Calculate iteration delta
            delta = 0.0
            if previous_score is not None:
                delta = metrics.overall_score - previous_score
            
            # Store score for history
            self.score_history.append(metrics.overall_score)
            
            # Determine convergence
            converged = self._check_convergence(metrics, delta)
            
            result = EvaluationResult(
                metrics=metrics,
                improvement_suggestions=result_data.improvement_suggestions,
                converged=converged or result_data.converged,
                iteration_delta=delta
            )
            
            # Log evaluation
            self.logger.info(
                f"📊 Evaluation: Score={metrics.overall_score:.1f} "
                f"(Δ{delta:+.1f}), Converged={converged}"
            )
            
            # Log weakest dimension
            weakest, score = metrics.get_weakest_dimension()
            if score < 60:
                self.logger.warning(f"📊 Weakest dimension: {weakest} ({score:.1f})")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Evaluation failed: {e}")
            return EvaluationResult(
                metrics=QualityMetrics(
                    accuracy=50.0,
                    completeness=50.0,
                    coherence=50.0,
                    depth=50.0,
                    citation_quality=50.0,
                    overall_score=50.0,
                    confidence=0.0
                ),
                improvement_suggestions=[f"Evaluation error: {str(e)}"],
                converged=False,
                iteration_delta=0.0
            )
    
    def _check_convergence(self, metrics: QualityMetrics, delta: float) -> bool:
        """
        Check if the draft has converged.
        
        Convergence happens when:
        1. Score exceeds threshold, OR
        2. Improvement between iterations is below minimum
        """
        # High quality convergence
        if metrics.overall_score >= self.convergence_threshold:
            self.logger.info(f"📊 Converged: Score {metrics.overall_score:.1f} >= threshold {self.convergence_threshold}")
            return True
        
        # Stagnation convergence (only after 2+ iterations)
        if len(self.score_history) >= 2 and abs(delta) < self.min_improvement:
            self.logger.info(f"📊 Converged: Improvement {delta:.1f} < minimum {self.min_improvement}")
            return True
        
        return False
    
    def get_improvement_trend(self) -> str:
        """Get a description of the improvement trend."""
        if len(self.score_history) < 2:
            return "insufficient_data"
        
        recent_delta = self.score_history[-1] - self.score_history[-2]
        
        if recent_delta > 5:
            return "improving_rapidly"
        elif recent_delta > 0:
            return "improving_slowly"
        elif recent_delta < -5:
            return "declining_rapidly"
        elif recent_delta < 0:
            return "declining_slowly"
        else:
            return "stagnant"
    
    def reset(self):
        """Reset score history for new evaluation session."""
        self.score_history = []
