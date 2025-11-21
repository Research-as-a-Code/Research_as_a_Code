# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Base abstractions for research strategies.

This module provides the common interface for different research strategies:
- UDR (Universal Deep Research) - NVIDIA's strategy-as-code approach
- TTD-DR (Test-Time Diffusion Deep Researcher) - Google's iterative refinement approach
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class ResearchStrategyType(Enum):
    """Available research strategy types."""
    SIMPLE_RAG = "simple_rag"
    UDR_DYNAMIC = "udr_dynamic"
    TTD_DR_DYNAMIC = "ttd_dr_dynamic"


@dataclass
class ResearchResult:
    """
    Common result format for all research strategies.
    
    This provides a unified interface regardless of the underlying
    research approach (UDR, TTD-DR, or simple RAG).
    """
    success: bool
    final_report: str
    sources: List[Dict[str, Any]]
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    execution_time: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "success": self.success,
            "final_report": self.final_report,
            "sources": self.sources,
            "metadata": self.metadata,
            "error": self.error,
            "execution_time": self.execution_time
        }


@dataclass
class ResearchContext:
    """
    Context passed to research strategies.
    
    Contains all the information needed by a strategy to execute,
    including the query, data sources, and configuration.
    """
    query: str
    collection: str = "default"
    search_web: bool = True
    max_sources: int = 10
    user_preferences: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for passing to strategies."""
        return {
            "query": self.query,
            "collection": self.collection,
            "search_web": self.search_web,
            "max_sources": self.max_sources,
            "user_preferences": self.user_preferences
        }


class BaseResearchStrategy(ABC):
    """
    Base class for all research strategies.
    
    This abstract base class defines the interface that all research
    strategies must implement, ensuring consistency across different
    approaches.
    """
    
    def __init__(self, name: str):
        """
        Initialize the research strategy.
        
        Args:
            name: Human-readable name for the strategy
        """
        self.name = name
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    @abstractmethod
    async def execute(self, 
                     context: ResearchContext) -> ResearchResult:
        """
        Execute the research strategy.
        
        This is the main entry point for running a research task.
        Each strategy implements this differently:
        - UDR: Compiles and executes code
        - TTD-DR: Iteratively refines a draft
        - Simple RAG: Direct retrieval and synthesis
        
        Args:
            context: Research context with query and configuration
            
        Returns:
            ResearchResult with the final report and metadata
        """
        pass
    
    @abstractmethod
    def get_strategy_type(self) -> ResearchStrategyType:
        """
        Return the strategy type identifier.
        
        Returns:
            The ResearchStrategyType enum value
        """
        pass
    
    @abstractmethod
    async def validate_context(self, context: ResearchContext) -> Tuple[bool, Optional[str]]:
        """
        Validate that the context is suitable for this strategy.
        
        Args:
            context: Research context to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        pass
    
    def get_capabilities(self) -> Dict[str, Any]:
        """
        Return the capabilities of this strategy.
        
        This helps the router decide which strategy to use.
        
        Returns:
            Dictionary describing what this strategy can do
        """
        return {
            "name": self.name,
            "type": self.get_strategy_type().value,
            "supports_web_search": True,
            "supports_rag": True,
            "supports_iteration": False,
            "typical_latency": "unknown",
            "quality_level": "unknown"
        }
    
    async def estimate_cost(self, context: ResearchContext) -> Dict[str, Any]:
        """
        Estimate the cost of running this strategy.
        
        Args:
            context: Research context
            
        Returns:
            Dictionary with cost estimates (tokens, time, dollars)
        """
        return {
            "estimated_tokens": 0,
            "estimated_time_seconds": 0,
            "estimated_cost_usd": 0.0,
            "confidence": "low"
        }


class ResearchStrategyRouter:
    """
    Routes research requests to the appropriate strategy.
    
    This class decides which research strategy to use based on:
    - User preference (if specified)
    - Query complexity
    - Available resources
    - Performance requirements
    """
    
    def __init__(self, strategies: Dict[ResearchStrategyType, BaseResearchStrategy]):
        """
        Initialize the router with available strategies.
        
        Args:
            strategies: Dictionary mapping strategy types to instances
        """
        self.strategies = strategies
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    async def route(self, 
                   context: ResearchContext,
                   preferred_strategy: Optional[ResearchStrategyType] = None) -> BaseResearchStrategy:
        """
        Route to the appropriate research strategy.
        
        Args:
            context: Research context
            preferred_strategy: User's preferred strategy (if any)
            
        Returns:
            The selected research strategy instance
        """
        # If user specified a preference, honor it if available
        if preferred_strategy and preferred_strategy in self.strategies:
            strategy = self.strategies[preferred_strategy]
            is_valid, error = await strategy.validate_context(context)
            if is_valid:
                self.logger.info(f"Using preferred strategy: {preferred_strategy.value}")
                return strategy
            else:
                self.logger.warning(f"Preferred strategy {preferred_strategy.value} invalid: {error}")
        
        # Otherwise, select based on complexity analysis
        complexity = await self._analyze_complexity(context)
        
        if complexity < 0.3:
            # Simple query - use RAG
            if ResearchStrategyType.SIMPLE_RAG in self.strategies:
                self.logger.info("Routing to SIMPLE_RAG based on low complexity")
                return self.strategies[ResearchStrategyType.SIMPLE_RAG]
        
        # Complex query - use dynamic strategy (default to UDR)
        if ResearchStrategyType.UDR_DYNAMIC in self.strategies:
            self.logger.info("Routing to UDR_DYNAMIC as default for complex query")
            return self.strategies[ResearchStrategyType.UDR_DYNAMIC]
        
        # Fallback to TTD-DR if UDR not available
        if ResearchStrategyType.TTD_DR_DYNAMIC in self.strategies:
            self.logger.info("Routing to TTD_DR_DYNAMIC as fallback")
            return self.strategies[ResearchStrategyType.TTD_DR_DYNAMIC]
        
        # Last resort - simple RAG
        self.logger.warning("No suitable strategy found, defaulting to SIMPLE_RAG")
        return self.strategies.get(
            ResearchStrategyType.SIMPLE_RAG,
            list(self.strategies.values())[0]  # Any available strategy
        )
    
    async def _analyze_complexity(self, context: ResearchContext) -> float:
        """
        Analyze query complexity to determine routing.
        
        Args:
            context: Research context
            
        Returns:
            Complexity score between 0 (simple) and 1 (complex)
        """
        query = context.query.lower()
        
        # Simple heuristics for now
        complexity = 0.0
        
        # Check for complex indicators
        if any(word in query for word in ['analyze', 'compare', 'evaluate', 'assess']):
            complexity += 0.3
        if any(word in query for word in ['comprehensive', 'detailed', 'thorough', 'deep']):
            complexity += 0.2
        if 'and' in query or ',' in query:  # Multiple parts
            complexity += 0.2
        if len(query) > 100:  # Long query
            complexity += 0.2
        if any(word in query for word in ['cost', 'benefit', 'trade-off', 'pros', 'cons']):
            complexity += 0.2
        
        # Check for simple indicators
        if any(word in query for word in ['what is', 'what are', 'define', 'list']):
            complexity -= 0.3
        if len(query) < 50:  # Short query
            complexity -= 0.1
        
        # Normalize to [0, 1]
        complexity = max(0.0, min(1.0, complexity))
        
        self.logger.info(f"Query complexity: {complexity:.2f}")
        return complexity
