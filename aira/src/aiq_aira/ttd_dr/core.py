# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Core implementation of TTD-DR (Test-Time Diffusion Deep Researcher).

This module implements Google's test-time diffusion approach for research,
which iteratively refines a draft through denoising with retrieval.

Reference: https://research.google/blog/deep-researcher-with-test-time-diffusion/
"""

import asyncio
import logging
import time
import json
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from ..research_strategy_base import (
    BaseResearchStrategy, 
    ResearchStrategyType,
    ResearchContext,
    ResearchResult
)
from .models import (
    TTDDRConfig,
    TTDDRState,
    TTDDRStage,
    TTDDRMetrics,
    ResearchPlan,
    DraftState,
    SearchQAPair
)
from .prompts import (
    RESEARCH_PLAN_PROMPT,
    INITIAL_DRAFT_PROMPT,
    QUESTION_GENERATION_PROMPT,
    DENOISING_PROMPT,
    CONVERGENCE_CHECK_PROMPT,
    FINAL_REPORT_SYNTHESIS_PROMPT
)
from .components.planner import ResearchPlanner
from .components.search import IterativeSearchEngine
from .components.denoiser import DraftDenoiser
from .components.evolver import SelfEvolver
from .components.synthesizer import ReportSynthesizer

logger = logging.getLogger(__name__)


class TTDDRIntegration(BaseResearchStrategy):
    """
    Test-Time Diffusion Deep Researcher Implementation.
    
    This class implements the core TTD-DR algorithm which treats research
    report generation as a diffusion process, starting with a "noisy" draft
    and progressively refining it through iterations of information retrieval
    and denoising.
    
    Key innovations:
    1. Report-level denoising with retrieval
    2. Component-wise self-evolution
    3. Convergence-based early stopping
    """
    
    def __init__(self,
                 llm: BaseChatModel,
                 rag_url: str,
                 synthesis_llm: Optional[BaseChatModel] = None,
                 config: Optional[TTDDRConfig] = None,
                 tavily_api_key: Optional[str] = None):
        """
        Initialize TTD-DR integration.
        
        Args:
            llm: Primary language model for planning and denoising
            rag_url: URL for RAG service
            synthesis_llm: Optional separate LLM for synthesis (defaults to llm)
            config: TTD-DR configuration
            tavily_api_key: Optional API key for web search
        """
        super().__init__(name="TTD-DR (Test-Time Diffusion)")
        
        self.llm = llm
        self.synthesis_llm = synthesis_llm or llm
        self.config = config or TTDDRConfig()
        
        # Initialize components
        self.planner = ResearchPlanner(llm)
        self.searcher = IterativeSearchEngine(llm, rag_url, tavily_api_key)
        self.denoiser = DraftDenoiser(llm, self.config)
        self.synthesizer = ReportSynthesizer(self.synthesis_llm)
        
        # Optional self-evolution component
        self.evolver = None
        if self.config.enable_self_evolution:
            self.evolver = SelfEvolver(llm, self.config)
        
        # Metrics tracking
        self.metrics = TTDDRMetrics()
    
    def get_strategy_type(self) -> ResearchStrategyType:
        """Return the strategy type."""
        return ResearchStrategyType.TTD_DR_DYNAMIC
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Return TTD-DR capabilities."""
        return {
            "name": self.name,
            "type": self.get_strategy_type().value,
            "supports_web_search": True,
            "supports_rag": True,
            "supports_iteration": True,
            "typical_latency": "45-90 seconds",
            "quality_level": "excellent",
            "approach": "iterative_refinement"
        }
    
    async def validate_context(self, context: ResearchContext) -> Tuple[bool, Optional[str]]:
        """Validate the research context."""
        if not context.query:
            return False, "Query is required"
        
        if len(context.query) < 10:
            return False, "Query too short for meaningful research"
        
        return True, None
    
    async def estimate_cost(self, context: ResearchContext) -> Dict[str, Any]:
        """Estimate execution cost."""
        # Rough estimates based on typical usage
        query_complexity = len(context.query) / 50  # Simple heuristic
        
        estimated_iterations = min(self.config.max_iterations, 3 + int(query_complexity))
        llm_calls_per_iteration = 4 if self.config.enable_self_evolution else 3
        
        total_llm_calls = 2 + (estimated_iterations * llm_calls_per_iteration) + 1  # plan + iterations + synthesis
        estimated_tokens = total_llm_calls * 2000  # Average tokens per call
        
        return {
            "estimated_tokens": estimated_tokens,
            "estimated_time_seconds": 15 + (estimated_iterations * 12),
            "estimated_cost_usd": estimated_tokens * 0.00002,  # Rough pricing
            "confidence": "medium",
            "estimated_iterations": estimated_iterations
        }
    
    async def execute(self, context: ResearchContext) -> ResearchResult:
        """
        Execute the TTD-DR research strategy.
        
        This is the main entry point that orchestrates the entire
        test-time diffusion process.
        
        Args:
            context: Research context with query and configuration
            
        Returns:
            ResearchResult with final report and metadata
        """
        start_time = time.time()
        
        # Initialize state
        state = TTDDRState(
            stage=TTDDRStage.PLANNING,
            iteration=0,
            research_plan=None,
            current_draft=None,
            search_history=[],
            variants=[],
            convergence_scores=[],
            quality_scores=[],
            start_time=datetime.now(),
            end_time=None,
            errors=[],
            warnings=[]
        )
        
        try:
            # Stage 1: Generate Research Plan
            logger.info(f"📋 TTD-DR Stage 1: Generating research plan for query: {context.query[:100]}...")
            state.research_plan = await self._generate_research_plan(context)
            self.metrics.total_llm_calls += 1
            
            # Initialize draft (noisy starting point)
            logger.info("📝 TTD-DR: Creating initial draft...")
            state.current_draft = await self._create_initial_draft(context, state.research_plan)
            self.metrics.total_llm_calls += 1
            
            # Stage 2: Iterative Search with Denoising
            logger.info(f"🔄 TTD-DR Stage 2: Beginning iterative refinement (max {self.config.max_iterations} iterations)")
            state.stage = TTDDRStage.ITERATING
            
            for iteration in range(self.config.max_iterations):
                iteration_start = time.time()
                state.iteration = iteration + 1
                
                logger.info(f"🔄 TTD-DR Iteration {state.iteration}/{self.config.max_iterations}")
                
                # 2a: Generate search questions based on current draft
                questions = await self._generate_questions_from_draft(
                    state.current_draft,
                    state.research_plan,
                    state.search_history,
                    iteration
                )
                self.metrics.total_llm_calls += len(questions)
                self.metrics.total_search_queries += len(questions)
                
                # 2b: Search for answers (with optional self-evolution)
                answers = await self._search_with_evolution(questions, context)
                
                # Store Q&A pairs
                for q, a in zip(questions, answers):
                    state.search_history.append(SearchQAPair(
                        question=q["question"],
                        answer=a["answer"],
                        sources=a.get("sources", []),
                        iteration=state.iteration,
                        confidence_score=a.get("confidence", 0.8)
                    ))
                
                # Denoise: Refine draft with new information
                old_draft = state.current_draft
                state.current_draft = await self._denoise_draft(
                    state.current_draft,
                    answers,
                    state.research_plan,
                    state.iteration
                )
                self.metrics.total_llm_calls += 1
                
                # Calculate convergence score
                convergence_score = await self._calculate_convergence(
                    old_draft.content,
                    state.current_draft.content
                )
                state.convergence_scores.append(convergence_score)
                self.metrics.denoising_effectiveness.append(convergence_score)
                
                # Track iteration time
                iteration_time = time.time() - iteration_start
                self.metrics.iteration_times.append(iteration_time)
                
                logger.info(f"✅ Iteration {state.iteration} complete. Convergence: {convergence_score:.2%}, Time: {iteration_time:.1f}s")
                
                # Check for early convergence
                if self.config.early_stop and convergence_score >= self.config.convergence_threshold:
                    logger.info(f"🎯 Converged at iteration {state.iteration} (score: {convergence_score:.2%})")
                    break
            
            # Stage 3: Generate Final Report
            logger.info("📄 TTD-DR Stage 3: Generating final report...")
            state.stage = TTDDRStage.SYNTHESIZING
            
            final_report = await self._synthesize_final_report(
                state.current_draft,
                state.research_plan,
                state.search_history,
                state.convergence_scores
            )
            self.metrics.total_llm_calls += 1
            
            # Mark completion
            state.stage = TTDDRStage.COMPLETE
            state.end_time = datetime.now()
            
            # Prepare result
            execution_time = time.time() - start_time
            
            return ResearchResult(
                success=True,
                final_report=final_report,
                sources=self._extract_sources(state.search_history),
                metadata={
                    "strategy": "ttd_dr",
                    "iterations_completed": state.iteration,
                    "final_convergence": state.convergence_scores[-1] if state.convergence_scores else 0,
                    "research_plan": state.research_plan.to_dict(),
                    "search_pairs": len(state.search_history),
                    "metrics": self.metrics.to_dict(),
                    "execution_time": execution_time
                },
                execution_time=execution_time
            )
            
        except Exception as e:
            logger.error(f"TTD-DR execution failed: {e}", exc_info=True)
            state.errors.append(str(e))
            
            # Try to salvage partial results
            if state.current_draft and state.current_draft.content:
                partial_report = await self._generate_partial_report(state)
                return ResearchResult(
                    success=False,
                    final_report=partial_report,
                    sources=self._extract_sources(state.search_history),
                    metadata={
                        "strategy": "ttd_dr",
                        "error": str(e),
                        "partial_result": True,
                        "iterations_completed": state.iteration
                    },
                    error=str(e),
                    execution_time=time.time() - start_time
                )
            
            return ResearchResult(
                success=False,
                final_report="",
                sources=[],
                metadata={"strategy": "ttd_dr"},
                error=str(e),
                execution_time=time.time() - start_time
            )
    
    async def _generate_research_plan(self, context: ResearchContext) -> ResearchPlan:
        """Generate the research plan (Stage 1)."""
        prompt = RESEARCH_PLAN_PROMPT.format(query=context.query)
        
        response = await self.llm.ainvoke([
            SystemMessage(content="You are a research planning expert."),
            HumanMessage(content=prompt)
        ])
        
        try:
            # Parse JSON response
            plan_data = json.loads(response.content)
            return ResearchPlan(
                main_topic=plan_data["main_topic"],
                key_areas=plan_data["key_areas"],
                sub_questions=plan_data["sub_questions"],
                expected_sections=plan_data["expected_sections"],
                search_strategy=plan_data["search_strategy"]
            )
        except (json.JSONDecodeError, KeyError) as e:
            # Fallback to basic plan
            logger.warning(f"Failed to parse research plan: {e}. Using fallback.")
            return ResearchPlan(
                main_topic=context.query,
                key_areas=["Background", "Current State", "Analysis", "Implications"],
                sub_questions=[context.query],
                expected_sections=["Introduction", "Main Content", "Conclusion"],
                search_strategy="comprehensive"
            )
    
    async def _create_initial_draft(self, context: ResearchContext, plan: ResearchPlan) -> DraftState:
        """Create the initial noisy draft."""
        prompt = INITIAL_DRAFT_PROMPT.format(
            research_plan=json.dumps(plan.to_dict(), indent=2),
            query=context.query
        )
        
        response = await self.llm.ainvoke([
            SystemMessage(content="You are a research writer creating an initial draft."),
            HumanMessage(content=prompt)
        ])
        
        draft_content = response.content
        
        # Identify initial gaps
        gaps = []
        if "[NEEDS RESEARCH]" in draft_content:
            gaps.append("Information gaps marked for research")
        if "[UNVERIFIED]" in draft_content:
            gaps.append("Unverified claims need validation")
        
        return DraftState(
            content=draft_content,
            iteration=0,
            convergence_score=0.0,
            gaps_identified=gaps,
            improvements_made=["Initial draft created"],
            word_count=len(draft_content.split())
        )
    
    async def _generate_questions_from_draft(self, 
                                            draft: DraftState,
                                            plan: ResearchPlan,
                                            history: List[SearchQAPair],
                                            iteration: int) -> List[Dict[str, Any]]:
        """Generate search questions based on draft gaps (Stage 2a)."""
        # Get previously asked questions to avoid repetition
        previous_questions = [qa.question for qa in history[-10:]]  # Last 10 questions
        
        prompt = QUESTION_GENERATION_PROMPT.format(
            draft=draft.content[:3000],  # Limit draft length
            plan=json.dumps(plan.to_dict(), indent=2),
            previous_questions=json.dumps(previous_questions),
            iteration=iteration + 1,
            num_questions=self.config.questions_per_iteration
        )
        
        response = await self.llm.ainvoke([
            SystemMessage(content="You are an expert at identifying research gaps."),
            HumanMessage(content=prompt)
        ])
        
        try:
            result = json.loads(response.content)
            questions = result["questions"]
            
            # Update draft gaps
            draft.gaps_identified = result.get("gaps_identified", [])
            
            return questions
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to parse questions: {e}. Using fallback.")
            # Fallback to simple questions
            return [
                {"question": f"More information about {plan.main_topic}", "purpose": "general", "priority": "high"}
            ]
    
    async def _search_with_evolution(self, 
                                    questions: List[Dict[str, Any]],
                                    context: ResearchContext) -> List[Dict[str, Any]]:
        """Search for answers with optional self-evolution."""
        # Get initial answers
        answers = await self.searcher.search_multiple(
            questions=[q["question"] for q in questions],
            collection=context.collection,
            use_web=context.search_web
        )
        
        # Apply self-evolution if enabled
        if self.evolver and self.config.enable_self_evolution:
            evolved_answers = []
            for answer in answers:
                evolved = await self.evolver.evolve_answer(
                    answer["answer"],
                    answer.get("sources", [])
                )
                evolved_answers.append({
                    "answer": evolved,
                    "sources": answer.get("sources", []),
                    "confidence": answer.get("confidence", 0.8) * 1.1  # Boost confidence
                })
                
                # Track improvement
                self.metrics.evolution_improvements.append(0.1)  # Simplified metric
            
            return evolved_answers
        
        return answers
    
    async def _denoise_draft(self,
                            current_draft: DraftState,
                            new_information: List[Dict[str, Any]],
                            plan: ResearchPlan,
                            iteration: int) -> DraftState:
        """Denoise the draft by incorporating new information."""
        # Prepare new information summary
        info_summary = "\n\n".join([
            f"Q: {info.get('question', 'N/A')}\nA: {info['answer']}"
            for info in new_information
        ])
        
        prompt = DENOISING_PROMPT.format(
            current_draft=current_draft.content,
            new_information=info_summary,
            research_plan=json.dumps(plan.to_dict(), indent=2),
            iteration=iteration,
            convergence_score=current_draft.convergence_score * 100
        )
        
        response = await self.llm.ainvoke([
            SystemMessage(content="You are an expert at refining research drafts."),
            HumanMessage(content=prompt)
        ])
        
        revised_content = response.content
        
        # Track improvements
        improvements = []
        if "[NEEDS RESEARCH]" not in revised_content and "[NEEDS RESEARCH]" in current_draft.content:
            improvements.append("Filled research gaps")
        if "[UNVERIFIED]" not in revised_content and "[UNVERIFIED]" in current_draft.content:
            improvements.append("Verified claims")
        if len(revised_content) > len(current_draft.content) * 1.1:
            improvements.append("Added substantial content")
        
        return DraftState(
            content=revised_content,
            iteration=iteration,
            convergence_score=current_draft.convergence_score,  # Updated separately
            gaps_identified=[],  # Will be updated in next question generation
            improvements_made=improvements,
            word_count=len(revised_content.split())
        )
    
    async def _calculate_convergence(self, old_draft: str, new_draft: str) -> float:
        """Calculate convergence score between drafts."""
        prompt = CONVERGENCE_CHECK_PROMPT.format(
            previous_draft=old_draft[:2000],  # Limit length
            current_draft=new_draft[:2000]
        )
        
        response = await self.llm.ainvoke([
            SystemMessage(content="You are an expert at assessing document quality."),
            HumanMessage(content=prompt)
        ])
        
        try:
            result = json.loads(response.content)
            return result["convergence_score"] / 100.0
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to parse convergence: {e}. Using heuristic.")
            # Simple heuristic based on length and markers
            length_ratio = len(new_draft) / max(len(old_draft), 1)
            has_gaps = "[NEEDS RESEARCH]" in new_draft or "[UNVERIFIED]" in new_draft
            
            if length_ratio > 1.05 and not has_gaps:
                return 0.8
            elif length_ratio > 1.02:
                return 0.6
            else:
                return 0.4
    
    async def _synthesize_final_report(self,
                                      draft: DraftState,
                                      plan: ResearchPlan,
                                      search_history: List[SearchQAPair],
                                      convergence_scores: List[float]) -> str:
        """Generate the final polished report (Stage 3)."""
        # Prepare search summary
        search_summary = f"Conducted {len(search_history)} searches across {draft.iteration} iterations"
        
        prompt = FINAL_REPORT_SYNTHESIS_PROMPT.format(
            draft=draft.content,
            research_plan=json.dumps(plan.to_dict(), indent=2),
            search_summary=search_summary,
            iterations=draft.iteration,
            convergence=convergence_scores[-1] * 100 if convergence_scores else 0
        )
        
        response = await self.synthesis_llm.ainvoke([
            SystemMessage(content="You are an expert report writer."),
            HumanMessage(content=prompt)
        ])
        
        return response.content
    
    async def _generate_partial_report(self, state: TTDDRState) -> str:
        """Generate a report from partial results (error recovery)."""
        if not state.current_draft:
            return "Research could not be completed due to an error."
        
        partial_report = f"""# Research Report (Partial Results)

**Note**: This report was generated from incomplete research due to an interruption.

## Research Plan
Topic: {state.research_plan.main_topic if state.research_plan else 'Unknown'}
Iterations Completed: {state.iteration}/{self.config.max_iterations}

## Current Findings

{state.current_draft.content}

## Limitations
- Research was interrupted at iteration {state.iteration}
- Some sections may be incomplete or unverified
- Final synthesis was not performed
"""
        
        return partial_report
    
    def _extract_sources(self, search_history: List[SearchQAPair]) -> List[Dict[str, Any]]:
        """Extract unique sources from search history."""
        sources = []
        seen = set()
        
        for qa in search_history:
            for source in qa.sources:
                # Create unique identifier
                source_id = f"{source.get('url', '')}:{source.get('title', '')}"
                if source_id not in seen:
                    seen.add(source_id)
                    sources.append(source)
        
        return sources
