# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Data models for TTD-DR (Test-Time Diffusion Deep Researcher).

This module defines the data structures used throughout the TTD-DR pipeline.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from enum import Enum


class TTDDRStage(Enum):
    """Stages of the TTD-DR process."""
    PLANNING = "planning"
    ITERATING = "iterating"
    SYNTHESIZING = "synthesizing"
    COMPLETE = "complete"


@dataclass
class ResearchPlan:
    """
    Research plan generated in Stage 1.
    
    This structures the research approach and guides
    the iterative search process.
    """
    main_topic: str
    key_areas: List[str]
    sub_questions: List[str]
    expected_sections: List[str]
    search_strategy: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "main_topic": self.main_topic,
            "key_areas": self.key_areas,
            "sub_questions": self.sub_questions,
            "expected_sections": self.expected_sections,
            "search_strategy": self.search_strategy,
            "metadata": self.metadata
        }


@dataclass
class SearchQAPair:
    """
    Question-Answer pair from iterative search.
    
    Represents one cycle of the search process.
    """
    question: str
    answer: str
    sources: List[Dict[str, Any]]
    iteration: int
    confidence_score: float
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "question": self.question,
            "answer": self.answer,
            "sources": self.sources,
            "iteration": self.iteration,
            "confidence_score": self.confidence_score,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class DraftState:
    """
    Represents the evolving draft during denoising.
    
    Tracks the draft content and metadata about its quality
    and convergence.
    """
    content: str
    iteration: int
    convergence_score: float
    gaps_identified: List[str]
    improvements_made: List[str]
    word_count: int
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "content": self.content,
            "iteration": self.iteration,
            "convergence_score": self.convergence_score,
            "gaps_identified": self.gaps_identified,
            "improvements_made": self.improvements_made,
            "word_count": self.word_count
        }


@dataclass
class EvolutionVariant:
    """
    Represents a variant in the self-evolution process.
    
    Multiple variants are generated and evaluated to find
    the best information.
    """
    content: str
    fitness_score: float
    feedback: Dict[str, Any]
    revision_count: int
    parent_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "content": self.content,
            "fitness_score": self.fitness_score,
            "feedback": self.feedback,
            "revision_count": self.revision_count,
            "parent_id": self.parent_id
        }


@dataclass
class TTDDRConfig:
    """
    Configuration for TTD-DR execution.
    
    Controls the behavior of the iterative refinement process.
    """
    # Iteration control
    max_iterations: int = 5
    convergence_threshold: float = 0.85
    early_stop: bool = True
    
    # Self-evolution settings
    enable_self_evolution: bool = True
    num_variants: int = 3
    evolution_rounds: int = 2
    
    # Denoising parameters
    denoising_temperature: float = 0.7
    denoising_strategy: str = "adaptive"  # "aggressive", "conservative", "adaptive"
    
    # Search configuration
    questions_per_iteration: int = 3
    max_search_results: int = 5
    enable_web_search: bool = True
    
    # Quality control
    min_draft_length: int = 500
    max_draft_length: int = 5000
    quality_threshold: float = 0.8
    
    # LLM parameters
    llm_temperature: float = 0.7
    llm_max_tokens: int = 4000
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "max_iterations": self.max_iterations,
            "convergence_threshold": self.convergence_threshold,
            "early_stop": self.early_stop,
            "enable_self_evolution": self.enable_self_evolution,
            "num_variants": self.num_variants,
            "evolution_rounds": self.evolution_rounds,
            "denoising_temperature": self.denoising_temperature,
            "denoising_strategy": self.denoising_strategy,
            "questions_per_iteration": self.questions_per_iteration,
            "max_search_results": self.max_search_results,
            "enable_web_search": self.enable_web_search,
            "min_draft_length": self.min_draft_length,
            "max_draft_length": self.max_draft_length,
            "quality_threshold": self.quality_threshold,
            "llm_temperature": self.llm_temperature,
            "llm_max_tokens": self.llm_max_tokens
        }


@dataclass
class TTDDRState:
    """
    Complete state of a TTD-DR execution.
    
    Tracks all aspects of the iterative research process.
    """
    # Current status
    stage: TTDDRStage
    iteration: int
    
    # Core components
    research_plan: Optional[ResearchPlan]
    current_draft: Optional[DraftState]
    search_history: List[SearchQAPair]
    
    # Evolution tracking
    variants: List[EvolutionVariant]
    
    # Convergence metrics
    convergence_scores: List[float]
    quality_scores: List[float]
    
    # Timing
    start_time: datetime
    end_time: Optional[datetime]
    
    # Errors and warnings
    errors: List[str]
    warnings: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "stage": self.stage.value,
            "iteration": self.iteration,
            "research_plan": self.research_plan.to_dict() if self.research_plan else None,
            "current_draft": self.current_draft.to_dict() if self.current_draft else None,
            "search_history": [qa.to_dict() for qa in self.search_history],
            "variants": [v.to_dict() for v in self.variants],
            "convergence_scores": self.convergence_scores,
            "quality_scores": self.quality_scores,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "errors": self.errors,
            "warnings": self.warnings
        }
    
    def get_latest_convergence(self) -> float:
        """Get the most recent convergence score."""
        return self.convergence_scores[-1] if self.convergence_scores else 0.0
    
    def get_progress_percentage(self, max_iterations: int) -> float:
        """Calculate progress as a percentage."""
        if self.stage == TTDDRStage.COMPLETE:
            return 100.0
        elif self.stage == TTDDRStage.PLANNING:
            return 10.0
        elif self.stage == TTDDRStage.ITERATING:
            return 10.0 + (80.0 * self.iteration / max_iterations)
        elif self.stage == TTDDRStage.SYNTHESIZING:
            return 90.0
        return 0.0


@dataclass
class TTDDRMetrics:
    """
    Performance metrics for TTD-DR execution.
    
    Used for monitoring and optimization.
    """
    total_llm_calls: int = 0
    total_tokens_used: int = 0
    total_search_queries: int = 0
    total_sources_found: int = 0
    evolution_improvements: List[float] = field(default_factory=list)
    denoising_effectiveness: List[float] = field(default_factory=list)
    iteration_times: List[float] = field(default_factory=list)
    
    def get_average_iteration_time(self) -> float:
        """Calculate average time per iteration."""
        return sum(self.iteration_times) / len(self.iteration_times) if self.iteration_times else 0.0
    
    def get_evolution_improvement_rate(self) -> float:
        """Calculate average improvement from evolution."""
        return sum(self.evolution_improvements) / len(self.evolution_improvements) if self.evolution_improvements else 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_llm_calls": self.total_llm_calls,
            "total_tokens_used": self.total_tokens_used,
            "total_search_queries": self.total_search_queries,
            "total_sources_found": self.total_sources_found,
            "average_iteration_time": self.get_average_iteration_time(),
            "evolution_improvement_rate": self.get_evolution_improvement_rate(),
            "iterations_completed": len(self.iteration_times)
        }
