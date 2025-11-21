# TTD-DR Implementation Roadmap

**Date**: November 21, 2025  
**Status**: 📋 Ready for Implementation  
**Goal**: Implement Google's Test-Time Diffusion Deep Researcher alongside UDR

---

## Quick Start Guide

This document provides the step-by-step implementation roadmap for adding TTD-DR as an alternative research strategy to the existing AI-Q + UDR system.

---

## Phase 0: Pre-Implementation Checklist

### Required Understanding
- [x] Google TTD-DR paper concepts understood
- [x] Current UDR implementation analyzed
- [x] LangGraph state management reviewed
- [x] CopilotKit streaming patterns understood

### Design Decisions
- [x] **Strategy Selection**: UI toggle (not automatic)
- [x] **State Management**: Extend existing HackathonAgentState
- [x] **Parallel Implementation**: Keep UDR intact, add TTD-DR alongside
- [x] **Visualization**: Show iterations in real-time

---

## Phase 1: Foundation (Days 1-3)

### Task 1.1: Create Base Abstractions
**File**: `aira/src/aiq_aira/research_strategy_base.py`

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Any, List, Optional

class ResearchStrategyType(Enum):
    SIMPLE_RAG = "simple_rag"
    UDR_DYNAMIC = "udr_dynamic"
    TTD_DR_DYNAMIC = "ttd_dr_dynamic"

@dataclass
class ResearchResult:
    """Common result format for all strategies."""
    success: bool
    final_report: str
    sources: List[Dict[str, Any]]
    metadata: Dict[str, Any]
    error: Optional[str] = None

class BaseResearchStrategy(ABC):
    """Base class for research strategies."""
    
    @abstractmethod
    async def execute(self, 
                     query: str, 
                     context: Dict[str, Any]) -> ResearchResult:
        """Execute the research strategy."""
        pass
    
    @abstractmethod
    def get_strategy_type(self) -> ResearchStrategyType:
        """Return the strategy type."""
        pass
```

### Task 1.2: Create TTD-DR Structure
**Directory**: `aira/src/aiq_aira/ttd_dr/`

```
ttd_dr/
├── __init__.py
├── core.py                 # Main TTD-DR integration
├── components/
│   ├── __init__.py
│   ├── planner.py         # Research plan generator
│   ├── search.py          # Iterative search engine
│   ├── denoiser.py        # Draft denoising logic
│   ├── evolver.py         # Self-evolution algorithm
│   └── synthesizer.py     # Final report generator
├── models.py              # Data models/types
└── prompts.py             # TTD-DR specific prompts
```

### Task 1.3: Update Agent State
**File**: `aira/src/aiq_aira/hackathon_agent.py`

```python
class HackathonAgentState(TypedDict):
    # ... existing fields ...
    
    # Strategy selection (new)
    research_strategy_type: str  # "udr" or "ttd_dr"
    
    # TTD-DR specific fields (new)
    ttd_dr_state: Dict[str, Any]  # Encapsulated TTD-DR state
    ttd_dr_plan: Dict[str, Any]
    ttd_dr_draft: str
    ttd_dr_iterations: List[Dict[str, Any]]
    ttd_dr_search_qa_pairs: List[Tuple[str, str]]
    ttd_dr_convergence_score: float
```

---

## Phase 2: Core TTD-DR Implementation (Days 4-8)

### Task 2.1: Main Integration Module
**File**: `aira/src/aiq_aira/ttd_dr/core.py`

```python
import asyncio
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from ..research_strategy_base import BaseResearchStrategy, ResearchResult
from .components import (
    ResearchPlanner,
    IterativeSearcher,
    DraftDenoiser,
    SelfEvolver,
    ReportSynthesizer
)

logger = logging.getLogger(__name__)

@dataclass
class TTDDRConfig:
    """Configuration for TTD-DR."""
    max_iterations: int = 5
    num_variants: int = 3
    convergence_threshold: float = 0.85
    denoising_temperature: float = 0.7
    enable_self_evolution: bool = True

class TTDDRIntegration(BaseResearchStrategy):
    """
    Test-Time Diffusion Deep Researcher Implementation.
    
    Based on Google Research: "Deep researcher with test-time diffusion"
    https://research.google/blog/deep-researcher-with-test-time-diffusion/
    """
    
    def __init__(self,
                 llm,
                 rag_url: str,
                 synthesis_llm,
                 config: Optional[TTDDRConfig] = None):
        self.config = config or TTDDRConfig()
        self.planner = ResearchPlanner(llm)
        self.searcher = IterativeSearcher(llm, rag_url)
        self.denoiser = DraftDenoiser(llm)
        self.evolver = SelfEvolver(llm) if self.config.enable_self_evolution else None
        self.synthesizer = ReportSynthesizer(synthesis_llm)
        
    async def execute(self, query: str, context: Dict[str, Any]) -> ResearchResult:
        """
        Execute TTD-DR strategy with iterative refinement.
        """
        try:
            # Stage 1: Generate Research Plan
            logger.info("📋 TTD-DR Stage 1: Generating research plan...")
            research_plan = await self.planner.generate_plan(query, context)
            
            # Initialize draft (noisy starting point)
            logger.info("📝 TTD-DR: Creating initial draft...")
            draft = await self._create_initial_draft(query, research_plan)
            
            # Stage 2: Iterative Search with Denoising
            search_history = []
            convergence_scores = []
            
            for iteration in range(self.config.max_iterations):
                logger.info(f"🔄 TTD-DR Iteration {iteration + 1}/{self.config.max_iterations}")
                
                # 2a: Generate search questions based on current draft
                questions = await self.searcher.generate_questions(
                    draft=draft,
                    plan=research_plan,
                    history=search_history,
                    iteration=iteration
                )
                
                # 2b: Search for answers (with optional self-evolution)
                if self.evolver:
                    answers = await self._search_with_evolution(questions)
                else:
                    answers = await self.searcher.search_answers(questions)
                
                # Store Q&A pairs
                search_history.extend(zip(questions, answers))
                
                # Denoise: Refine draft with new information
                old_draft = draft
                draft = await self.denoiser.denoise(
                    current_draft=draft,
                    new_information=answers,
                    research_plan=research_plan,
                    temperature=self.config.denoising_temperature
                )
                
                # Calculate convergence score
                score = await self._calculate_convergence(old_draft, draft)
                convergence_scores.append(score)
                
                # Check for early convergence
                if score >= self.config.convergence_threshold:
                    logger.info(f"✅ Converged at iteration {iteration + 1}")
                    break
            
            # Stage 3: Generate Final Report
            logger.info("📄 TTD-DR Stage 3: Generating final report...")
            final_report = await self.synthesizer.synthesize(
                draft=draft,
                research_plan=research_plan,
                search_history=search_history,
                convergence_scores=convergence_scores
            )
            
            return ResearchResult(
                success=True,
                final_report=final_report,
                sources=self._extract_sources(search_history),
                metadata={
                    "strategy": "ttd_dr",
                    "iterations": len(convergence_scores),
                    "final_convergence": convergence_scores[-1] if convergence_scores else 0,
                    "research_plan": research_plan,
                    "search_pairs": len(search_history)
                }
            )
            
        except Exception as e:
            logger.error(f"TTD-DR execution failed: {e}", exc_info=True)
            return ResearchResult(
                success=False,
                final_report="",
                sources=[],
                metadata={"strategy": "ttd_dr"},
                error=str(e)
            )
    
    async def _create_initial_draft(self, query: str, plan: Dict) -> str:
        """Create noisy initial draft based on query and plan."""
        # Implementation details...
        pass
    
    async def _search_with_evolution(self, questions: List[str]) -> List[str]:
        """Search with self-evolution to improve answer quality."""
        # Generate initial answers
        initial_answers = await self.searcher.search_answers(questions)
        
        # Apply self-evolution
        evolved_answers = await self.evolver.evolve(
            initial_answers=initial_answers,
            num_variants=self.config.num_variants
        )
        
        return evolved_answers
    
    async def _calculate_convergence(self, old_draft: str, new_draft: str) -> float:
        """Calculate convergence score between drafts."""
        # Implementation: similarity metrics, information gain, etc.
        pass
```

### Task 2.2: Component Implementation

#### 2.2.1: Research Planner
**File**: `aira/src/aiq_aira/ttd_dr/components/planner.py`

```python
class ResearchPlanner:
    """Stage 1: Generate structured research plan."""
    
    def __init__(self, llm):
        self.llm = llm
        self.prompt_template = RESEARCH_PLAN_PROMPT
    
    async def generate_plan(self, query: str, context: Dict) -> Dict:
        """
        Generate a research plan with key areas to investigate.
        
        Returns:
            {
                "main_topic": str,
                "key_areas": List[str],
                "sub_questions": List[str],
                "expected_sections": List[str],
                "search_strategy": str
            }
        """
        # Implementation...
```

#### 2.2.2: Denoiser
**File**: `aira/src/aiq_aira/ttd_dr/components/denoiser.py`

```python
class DraftDenoiser:
    """Report-level denoising with retrieval."""
    
    DENOISING_PROMPT = """
    Current Draft:
    {current_draft}
    
    New Information:
    {new_information}
    
    Research Plan:
    {research_plan}
    
    Task: Revise the draft by:
    1. Incorporating new factual information
    2. Verifying and correcting existing claims
    3. Filling information gaps
    4. Improving coherence and flow
    5. Maintaining consistency with research plan
    
    Revised Draft:
    """
    
    async def denoise(self, 
                     current_draft: str,
                     new_information: List[str],
                     research_plan: Dict,
                     temperature: float = 0.7) -> str:
        """
        Denoise draft by incorporating new information.
        
        This is the core innovation of TTD-DR: treating the draft
        as a "noisy" signal that gets progressively refined.
        """
        # Format prompt
        # Call LLM with temperature
        # Return revised draft
```

#### 2.2.3: Self-Evolution
**File**: `aira/src/aiq_aira/ttd_dr/components/evolver.py`

```python
class SelfEvolver:
    """Component-wise optimization via self-evolution."""
    
    def __init__(self, llm):
        self.llm = llm
        self.judge_llm = llm  # Could be different model
    
    async def evolve(self, 
                    initial_answers: List[str],
                    num_variants: int = 3) -> List[str]:
        """
        Evolve answers through:
        1. Generate variants
        2. Environmental feedback (LLM-as-judge)
        3. Revision based on feedback
        4. Crossover of best variants
        """
        all_variants = []
        
        for answer in initial_answers:
            # Generate variants
            variants = await self._generate_variants(answer, num_variants)
            
            # Get feedback for each variant
            scored_variants = []
            for variant in variants:
                feedback = await self._get_feedback(variant)
                revised = await self._revise_based_on_feedback(variant, feedback)
                score = feedback["score"]
                scored_variants.append((score, revised))
            
            # Select best variant
            best_variant = max(scored_variants, key=lambda x: x[0])[1]
            all_variants.append(best_variant)
        
        # Crossover: merge best aspects of all variants
        final_answers = await self._crossover(all_variants)
        return final_answers
    
    async def _get_feedback(self, answer: str) -> Dict:
        """LLM-as-judge provides feedback."""
        # Evaluate: helpfulness, comprehensiveness, accuracy
        pass
```

---

## Phase 3: Frontend Implementation (Days 9-11)

### Task 3.1: Strategy Toggle Component
**File**: `frontend/app/components/StrategyToggle.tsx`

```tsx
'use client';

import React from 'react';
import { Code2, Sparkles } from 'lucide-react';

interface StrategyToggleProps {
  value: 'udr' | 'ttd_dr';
  onChange: (value: 'udr' | 'ttd_dr') => void;
  disabled?: boolean;
}

export const StrategyToggle: React.FC<StrategyToggleProps> = ({
  value,
  onChange,
  disabled = false
}) => {
  return (
    <div className="bg-gray-900 rounded-xl p-6 border border-gray-800">
      <h3 className="text-lg font-semibold text-gray-100 mb-4">
        Research Strategy
      </h3>
      
      <div className="grid grid-cols-2 gap-4">
        {/* UDR Option */}
        <button
          onClick={() => onChange('udr')}
          disabled={disabled}
          className={`
            p-4 rounded-lg border-2 transition-all
            ${value === 'udr' 
              ? 'border-blue-500 bg-blue-500/10' 
              : 'border-gray-700 hover:border-gray-600'}
            ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
          `}
        >
          <Code2 className={`w-6 h-6 mb-2 ${
            value === 'udr' ? 'text-blue-400' : 'text-gray-400'
          }`} />
          <div className="text-left">
            <h4 className="font-medium text-gray-100">UDR</h4>
            <p className="text-xs text-gray-400 mt-1">
              NVIDIA Strategy-as-Code
            </p>
            <p className="text-xs text-gray-500 mt-2">
              Compiles natural language into executable Python
            </p>
          </div>
        </button>
        
        {/* TTD-DR Option */}
        <button
          onClick={() => onChange('ttd_dr')}
          disabled={disabled}
          className={`
            p-4 rounded-lg border-2 transition-all
            ${value === 'ttd_dr' 
              ? 'border-green-500 bg-green-500/10' 
              : 'border-gray-700 hover:border-gray-600'}
            ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
          `}
        >
          <Sparkles className={`w-6 h-6 mb-2 ${
            value === 'ttd_dr' ? 'text-green-400' : 'text-gray-400'
          }`} />
          <div className="text-left">
            <h4 className="font-medium text-gray-100">TTD-DR</h4>
            <p className="text-xs text-gray-400 mt-1">
              Google Test-Time Diffusion
            </p>
            <p className="text-xs text-gray-500 mt-2">
              Iteratively refines draft through denoising
            </p>
          </div>
        </button>
      </div>
      
      {/* Strategy Description */}
      <div className="mt-4 p-3 bg-gray-800 rounded-lg">
        <p className="text-xs text-gray-400">
          {value === 'udr' ? (
            <>
              <strong>UDR Mode:</strong> Generates and executes Python code 
              to orchestrate research tools. Best for precise, structured queries.
            </>
          ) : (
            <>
              <strong>TTD-DR Mode:</strong> Creates an initial draft then 
              iteratively improves it using retrieved information. Best for 
              comprehensive, exploratory research.
            </>
          )}
        </p>
      </div>
    </div>
  );
};
```

### Task 3.2: TTD-DR Progress Visualizer
**File**: `frontend/app/components/TTDDRProgress.tsx`

```tsx
interface TTDDRProgressProps {
  currentIteration: number;
  maxIterations: number;
  convergenceScores: number[];
  currentStage: 'planning' | 'iterating' | 'synthesizing';
}

export const TTDDRProgress: React.FC<TTDDRProgressProps> = ({
  currentIteration,
  maxIterations,
  convergenceScores,
  currentStage
}) => {
  return (
    <div className="bg-gray-900 rounded-lg p-4">
      <h4 className="text-sm font-medium text-gray-300 mb-3">
        TTD-DR Progress
      </h4>
      
      {/* Stage Indicator */}
      <div className="flex items-center gap-2 mb-4">
        <StageIndicator stage="planning" current={currentStage} />
        <StageIndicator stage="iterating" current={currentStage} />
        <StageIndicator stage="synthesizing" current={currentStage} />
      </div>
      
      {/* Iteration Progress */}
      {currentStage === 'iterating' && (
        <div>
          <div className="flex justify-between text-xs text-gray-400 mb-2">
            <span>Iteration {currentIteration}/{maxIterations}</span>
            <span>Convergence: {(convergenceScores[currentIteration-1] * 100).toFixed(1)}%</span>
          </div>
          
          {/* Convergence Chart */}
          <div className="h-20 flex items-end gap-1">
            {convergenceScores.map((score, i) => (
              <div
                key={i}
                className="flex-1 bg-green-500/30 border border-green-500"
                style={{ height: `${score * 100}%` }}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
```

---

## Phase 4: Integration & Testing (Days 12-14)

### Task 4.1: Update Main Agent
**File**: `aira/src/aiq_aira/hackathon_agent.py`

```python
async def dynamic_strategy_router(state: HackathonAgentState, config: RunnableConfig):
    """Route to appropriate dynamic strategy based on selection."""
    
    strategy_type = state.get("research_strategy_type", "udr")
    
    if strategy_type == "ttd_dr":
        return await ttd_dr_strategy_node(state, config)
    else:
        return await udr_strategy_node(state, config)

async def ttd_dr_strategy_node(state: HackathonAgentState, config: RunnableConfig):
    """Execute TTD-DR strategy."""
    
    logger.info("🔬 Starting TTD-DR execution...")
    
    ttd_dr_integration = config["configurable"].get("ttd_dr_integration")
    if not ttd_dr_integration:
        return {
            "ttd_dr_result": {"success": False, "error": "TTD-DR not configured"},
            "running_summary": "TTD-DR integration not available"
        }
    
    # Execute TTD-DR
    result = await ttd_dr_integration.execute(
        query=state["messages"][0],
        context={
            "collection": state.get("collection", "default"),
            "search_web": state.get("search_web", True)
        }
    )
    
    return {
        "ttd_dr_result": result.__dict__,
        "running_summary": result.final_report if result.success else f"Error: {result.error}",
        "final_report": result.final_report if result.success else ""
    }
```

### Task 4.2: Backend API Updates
**File**: `backend/main.py`

```python
# Initialize both integrations
udr_integration = UDRIntegration(...)
ttd_dr_integration = TTDDRIntegration(
    llm=reasoning_llm,
    rag_url=Config.RAG_SERVER_URL,
    synthesis_llm=instruct_llm,
    config=TTDDRConfig(
        max_iterations=5,
        num_variants=3,
        convergence_threshold=0.85
    )
)

@app.post("/research/stream")
async def research_stream(request: ResearchRequest):
    """Stream research with selected strategy."""
    
    # Determine integration
    if request.strategy == "ttd_dr":
        integration = ttd_dr_integration
        strategy_type = ResearchStrategyType.TTD_DR_DYNAMIC
    else:
        integration = udr_integration
        strategy_type = ResearchStrategyType.UDR_DYNAMIC
    
    # Update config
    config = {
        "configurable": {
            "research_strategy_type": request.strategy,
            f"{request.strategy}_integration": integration,
            # ... other config
        }
    }
```

---

## Phase 5: Testing & Validation (Days 15-16)

### Test Scenarios

#### Scenario 1: Simple Query Comparison
```python
query = "What are the tariff codes for chocolate products?"

# Test both strategies
udr_result = await test_udr(query)
ttd_result = await test_ttd_dr(query)

# Compare: speed, quality, sources used
```

#### Scenario 2: Complex Multi-hop Query
```python
query = """
Compare NIMs deployment on EKS vs on-premise, including:
1. Cost analysis
2. Performance benchmarks  
3. Maintenance requirements
4. Security implications
"""

# TTD-DR should excel here with iterative refinement
```

#### Scenario 3: Convergence Testing
```python
# Test early convergence
simple_query = "What is NVIDIA NIM?"

# Should converge in 1-2 iterations
```

---

## Deployment Checklist

### Pre-deployment
- [ ] All unit tests passing
- [ ] Integration tests complete
- [ ] Performance benchmarks meet targets
- [ ] UI/UX review complete
- [ ] Documentation updated

### Deployment Steps
1. [ ] Deploy backend with both integrations
2. [ ] Deploy frontend with toggle
3. [ ] Feature flag: Start with 10% users
4. [ ] Monitor metrics (latency, quality, errors)
5. [ ] Gradual rollout to 100%

### Post-deployment
- [ ] A/B test results analysis
- [ ] User feedback collection
- [ ] Performance optimization
- [ ] Documentation refinement

---

## Success Criteria

### Technical Metrics
- ✅ Both strategies functional
- ✅ Latency < 60s for complex queries
- ✅ Error rate < 1%
- ✅ Convergence in 3-5 iterations

### User Metrics
- ✅ 50%+ users try both strategies
- ✅ Clear preference emerges from data
- ✅ Quality ratings improve
- ✅ User understands difference

---

## Risk Mitigation

### Risk 1: High Latency
**Mitigation**: 
- Cache intermediate results
- Parallel processing where possible
- Early convergence detection

### Risk 2: LLM Costs
**Mitigation**:
- Configurable iteration limits
- Reuse evaluations across variants
- Implement cost tracking

### Risk 3: User Confusion
**Mitigation**:
- Clear UI explanations
- Default to simpler strategy
- Progressive disclosure of details

---

**Status**: ✅ Ready for Implementation  
**Next Action**: Review and approve plan, then begin Phase 1
