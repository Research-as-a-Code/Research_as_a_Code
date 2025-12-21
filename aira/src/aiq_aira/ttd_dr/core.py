# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Core implementation of TTD-DR (Test-Time Diffusion Deep Researcher).

This module implements Google's test-time diffusion approach for research,
which iteratively refines a draft through denoising with retrieval.

Reference: https://research.google/blog/deep-researcher-with-test-time-diffusion/
"""

import asyncio
import json
import logging
import time
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from pydantic import BaseModel, Field as PydanticField
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI as LangChainChatOpenAI


# ========================================
# Pydantic Schemas for NVIDIA Guided JSON
# ========================================

class ResearchPlanSchema(BaseModel):
    """Schema for research plan output."""
    main_topic: str = PydanticField(description="Main topic of the research")
    key_areas: List[str] = PydanticField(description="Key areas to cover")
    sub_questions: List[str] = PydanticField(description="Sub-questions to answer")
    expected_sections: List[str] = PydanticField(description="Expected sections in final report")
    search_strategy: str = PydanticField(description="Search strategy to use")


class ConvergenceCheckSchema(BaseModel):
    """Schema for convergence check output."""
    convergence_score: float = PydanticField(
        ge=0, le=100,
        description="Convergence score from 0-100"
    )

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
    FINAL_REPORT_SYNTHESIS_PROMPT,
    CRITICAL_FEEDBACK_INJECTION,
    REPAIR_QUESTIONS_PROMPT,
    KNOWLEDGE_BASE_CONTEXT
)
from .components.planner import ResearchPlanner
from .components.search import IterativeSearchEngine
from .components.denoiser import DraftDenoiser
from .components.evolver import SelfEvolver
from .components.synthesizer import ReportSynthesizer
from .components.red_team import RedTeamAgent, RedTeamResult
from .components.evaluator import EvaluatorAgent, EvaluationResult
from .components.context_pruner import ContextPruner
from .debug_logger import TTDDRDebugLogger

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
        
        # Initialize core components
        self.planner = ResearchPlanner(llm)
        self.searcher = IterativeSearchEngine(llm, rag_url, tavily_api_key)
        self.denoiser = DraftDenoiser(llm, self.config)
        self.synthesizer = ReportSynthesizer(self.synthesis_llm)
        
        # Self-correction components (TTD-DR innovation)
        self.red_team = RedTeamAgent(llm)
        self.evaluator = EvaluatorAgent(
            llm, 
            convergence_threshold=self.config.convergence_threshold * 100,
            min_improvement=2.0
        )
        self.context_pruner = ContextPruner(llm)
        
        # Optional self-evolution component
        self.evolver = None
        if self.config.enable_self_evolution:
            self.evolver = SelfEvolver(llm, self.config)
        
        # Metrics tracking
        self.metrics = TTDDRMetrics()
        
        # Extract LLM config for guided_json
        self._base_url = getattr(llm, 'openai_api_base', None) or getattr(llm, 'base_url', None)
        if self._base_url and hasattr(self._base_url, '__str__'):
            self._base_url = str(self._base_url)
        self._model_name = getattr(llm, 'model_name', "nvidia/llama-3.1-nemotron-nano-8b-v1")
        
        # State for self-correction
        self.active_critique = None
        self.needs_quality_repair = False
    
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
    
    def _create_guided_llm_for_plan(self) -> LangChainChatOpenAI:
        """Create LLM with NVIDIA guided_json for research plan generation."""
        json_schema = ResearchPlanSchema.model_json_schema()
        
        return LangChainChatOpenAI(
            base_url=self._base_url,
            model=self._model_name,
            api_key="not-used",
            model_kwargs={
                "extra_body": {"nvext": {"guided_json": json_schema}}
            }
        )
    
    def _create_guided_llm_for_convergence(self) -> LangChainChatOpenAI:
        """Create LLM with NVIDIA guided_json for convergence check."""
        json_schema = ConvergenceCheckSchema.model_json_schema()
        
        return LangChainChatOpenAI(
            base_url=self._base_url,
            model=self._model_name,
            api_key="not-used",
            model_kwargs={
                "extra_body": {"nvext": {"guided_json": json_schema}}
            }
        )
    
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
        # Initialize debug logger
        debug = TTDDRDebugLogger()
        logger.info(f"🔍 TTD-DR Debug log: {debug.get_log_path()}")
        
        # Log initial context
        debug.log_stage("START", iteration=0, 
                       query=context.query,
                       collection=str(context.collection),
                       search_web=context.search_web)
        debug.log_variable("context.query", context.query, "execute_start")
        debug.log_variable("context.collection", context.collection, "execute_start")
        
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
            import sys
            print(f"🔶 TTD-DR CORE: Starting execute, query={context.query[:80]}...", flush=True, file=sys.stderr)
            
            # Stage 1: Generate Research Plan
            logger.info(f"📋 TTD-DR Stage 1: Generating research plan for query: {context.query[:100]}...")
            debug.log_stage("PLAN_GENERATION", iteration=0, query=context.query)
            
            print("🔶 TTD-DR CORE: Calling _generate_research_plan...", flush=True, file=sys.stderr)
            state.research_plan = await self._generate_research_plan(context)
            print(f"🔶 TTD-DR CORE: Plan generated, main_topic={state.research_plan.main_topic[:50] if state.research_plan.main_topic else 'None'}...", flush=True, file=sys.stderr)
            self.metrics.total_llm_calls += 1
            
            # Log what plan contains
            debug.log_variable("plan.main_topic", state.research_plan.main_topic, "after_plan_generation")
            debug.log_variable("original_query", context.query, "after_plan_generation")
            
            # Initialize draft (noisy starting point)
            logger.info("📝 TTD-DR: Creating initial draft...")
            debug.log_stage("INITIAL_DRAFT", iteration=0, query=context.query)
            
            print("🔶 TTD-DR CORE: About to create initial draft...", flush=True, file=sys.stderr)
            state.current_draft = await self._create_initial_draft(context, state.research_plan)
            print(f"🔶 TTD-DR CORE: Initial draft created, length={len(state.current_draft.content) if state.current_draft else 0}", flush=True, file=sys.stderr)
            self.metrics.total_llm_calls += 1
            
            # Log draft preview
            debug.log_variable("initial_draft", state.current_draft.content[:500], "after_initial_draft")
            
            # Stage 2: Iterative Search with Denoising
            logger.info(f"🔄 TTD-DR Stage 2: Beginning iterative refinement (max {self.config.max_iterations} iterations)")
            state.stage = TTDDRStage.ITERATING
            print(f"🔶 TTD-DR CORE: Entering iteration loop (max={self.config.max_iterations})", flush=True, file=sys.stderr)
            
            # ============================================
            # FEEDBACK TRACKING (TTD-DR Enhancement)
            # Store feedback from previous iteration to inject into next denoising
            # ============================================
            prev_red_team_feedback: Optional[str] = None
            prev_evaluator_feedback: Optional[str] = None
            knowledge_base_facts: List[str] = []
            
            for iteration in range(self.config.max_iterations):
                iteration_start = time.time()
                state.iteration = iteration + 1
                
                print(f"🔶 TTD-DR CORE: Starting iteration {state.iteration}", flush=True, file=sys.stderr)
                logger.info(f"🔄 TTD-DR Iteration {state.iteration}/{self.config.max_iterations}")
                debug.log_stage("ITERATION_START", iteration=state.iteration,
                               max_iterations=self.config.max_iterations)
                
                # 2a: Generate search questions based on current draft
                print(f"🔶 TTD-DR CORE: Generating questions for iteration {state.iteration}...", flush=True, file=sys.stderr)
                questions = await self._generate_questions_from_draft(
                    state.current_draft,
                    state.research_plan,
                    state.search_history,
                    iteration
                )
                print(f"🔶 TTD-DR CORE: Generated {len(questions)} questions", flush=True, file=sys.stderr)
                self.metrics.total_llm_calls += len(questions)
                self.metrics.total_search_queries += len(questions)
                
                # 2b: Search for answers (with optional self-evolution)
                print(f"🔶 TTD-DR CORE: Searching for answers...", flush=True, file=sys.stderr)
                answers = await self._search_with_evolution(questions, context)
                print(f"🔶 TTD-DR CORE: Got {len(answers)} answers", flush=True, file=sys.stderr)
                
                # Store Q&A pairs (handle both string and dict question formats)
                for q, a in zip(questions, answers):
                    # Normalize question - handle both string and dict
                    question_text = q if isinstance(q, str) else q.get("question", str(q)) if isinstance(q, dict) else str(q)
                    # Normalize answer - handle both string and dict
                    answer_text = a if isinstance(a, str) else a.get("answer", str(a)) if isinstance(a, dict) else str(a)
                    sources = a.get("sources", []) if isinstance(a, dict) else []
                    confidence = a.get("confidence", 0.8) if isinstance(a, dict) else 0.8
                    
                    state.search_history.append(SearchQAPair(
                        question=question_text,
                        answer=answer_text,
                        sources=sources,
                        iteration=state.iteration,
                        confidence_score=confidence
                    ))
                
                # ============================================
                # DENOISING WITH FEEDBACK INJECTION (TTD-DR Enhancement)
                # Pass Red Team/Evaluator feedback from previous iteration
                # ============================================
                old_draft = state.current_draft
                
                # Log if we're injecting feedback
                if prev_red_team_feedback or prev_evaluator_feedback:
                    print(f"🔶 TTD-DR CORE: Injecting feedback into denoising (Red Team: {bool(prev_red_team_feedback)}, Evaluator: {bool(prev_evaluator_feedback)})", flush=True, file=sys.stderr)
                
                state.current_draft = await self._denoise_draft(
                    state.current_draft,
                    answers,
                    state.research_plan,
                    state.iteration,
                    red_team_feedback=prev_red_team_feedback,
                    evaluator_feedback=prev_evaluator_feedback,
                    knowledge_base_facts=knowledge_base_facts if knowledge_base_facts else None
                )
                self.metrics.total_llm_calls += 1
                
                # ============================================
                # SELF-CORRECTION LOOP (runs in parallel)
                # This is the key TTD-DR innovation from the article
                # Reference: Fareed Khan's TTD-DR implementation
                # ============================================
                
                # Check if any self-correction components are enabled
                run_self_correction = (
                    self.config.enable_red_team or 
                    self.config.enable_evaluator or 
                    self.config.enable_context_pruning
                )
                
                red_team_result = None
                eval_result = None
                pruner_result = None
                
                if run_self_correction:
                    print(f"🔶 TTD-DR CORE: Running self-correction loop...", flush=True, file=sys.stderr)
                    
                    # Prepare research brief for agents
                    research_brief = json.dumps(state.research_plan.to_dict(), indent=2)[:2000]
                    
                    # Build list of parallel tasks based on config
                    parallel_tasks = []
                    task_names = []
                    
                    if self.config.enable_red_team:
                        parallel_tasks.append(self.red_team.critique(
                            state.current_draft.content,
                            research_brief,
                            state.iteration
                        ))
                        task_names.append("red_team")
                    
                    if self.config.enable_evaluator:
                        parallel_tasks.append(self.evaluator.evaluate(
                            state.current_draft.content,
                            research_brief,
                            state.iteration,
                            state.quality_scores[-1] if state.quality_scores else None
                        ))
                        task_names.append("evaluator")
                    
                    if self.config.enable_context_pruning:
                        # Collect raw notes for context pruning
                        raw_notes = "\n\n".join([
                            f"Q: {qa.question}\nA: {qa.answer}" 
                            for qa in state.search_history[-5:]  # Last 5 Q&A pairs
                        ])
                        parallel_tasks.append(self.context_pruner.process_raw_notes(
                            raw_notes,
                            state.research_plan.main_topic,
                            state.iteration
                        ))
                        task_names.append("context_pruner")
                    
                    # Wait for all parallel tasks
                    if parallel_tasks:
                        results = await asyncio.gather(*parallel_tasks, return_exceptions=True)
                        self.metrics.total_llm_calls += len(parallel_tasks)
                        
                        # Map results back to named variables
                        for name, result in zip(task_names, results):
                            if name == "red_team":
                                red_team_result = result
                            elif name == "evaluator":
                                eval_result = result
                            elif name == "context_pruner":
                                pruner_result = result
                
                # ============================================
                # PROCESS SELF-CORRECTION RESULTS
                # Store feedback for injection into NEXT iteration
                # ============================================
                
                # Reset feedback for this iteration
                prev_red_team_feedback = None
                prev_evaluator_feedback = None
                
                # Process Red Team results
                if red_team_result is not None:
                    if isinstance(red_team_result, RedTeamResult):
                        self.active_critique = red_team_result
                        if red_team_result.needs_major_revision:
                            self.needs_quality_repair = True
                            logger.warning(f"🔴 Red Team: Major revision needed (score: {red_team_result.quality_score})")
                            print(f"🔶 TTD-DR: RED TEAM found issues requiring repair", flush=True, file=sys.stderr)
                            # STORE FEEDBACK FOR NEXT ITERATION
                            prev_red_team_feedback = f"Score: {red_team_result.quality_score}/10. Issues: {', '.join(red_team_result.critical_issues[:3])}"
                        else:
                            print(f"🔶 TTD-DR: Red Team PASS (score={red_team_result.quality_score:.1f})", flush=True, file=sys.stderr)
                    elif isinstance(red_team_result, Exception):
                        logger.warning(f"Red Team returned exception: {red_team_result}")
                
                # Process Evaluator results
                if eval_result is not None:
                    if isinstance(eval_result, EvaluationResult):
                        state.quality_scores.append(eval_result.metrics.overall_score)
                        
                        if eval_result.needs_quality_repair():
                            self.needs_quality_repair = True
                            logger.warning(f"📊 Evaluator: Quality repair needed (score: {eval_result.metrics.overall_score})")
                            # STORE FEEDBACK FOR NEXT ITERATION
                            suggestions = "; ".join(eval_result.improvement_suggestions[:3]) if eval_result.improvement_suggestions else "No specific suggestions"
                            prev_evaluator_feedback = f"Overall: {eval_result.metrics.overall_score}/100. Suggestions: {suggestions[:300]}"
                        
                        # Log evaluation details
                        print(f"🔶 TTD-DR: Evaluator score={eval_result.metrics.overall_score:.1f}, converged={eval_result.converged}", flush=True, file=sys.stderr)
                    elif isinstance(eval_result, Exception):
                        logger.warning(f"Evaluator returned exception: {eval_result}")
                
                # Process Context Pruner results - ACCUMULATE FACTS
                if pruner_result is not None:
                    if isinstance(pruner_result, dict):
                        facts_extracted = pruner_result.get("facts_extracted", 0)
                        new_facts = pruner_result.get("facts", [])
                        if new_facts:
                            # Add new facts to knowledge base, keep last 20
                            knowledge_base_facts.extend(new_facts)
                            knowledge_base_facts = knowledge_base_facts[-20:]
                            print(f"🔶 TTD-DR: Context Pruner extracted {facts_extracted} facts (KB size: {len(knowledge_base_facts)})", flush=True, file=sys.stderr)
                    elif isinstance(pruner_result, Exception):
                        logger.warning(f"Context Pruner returned exception: {pruner_result}")
                
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
                
                # Check for early convergence (now also considers Evaluator)
                should_stop = False
                if self.config.early_stop:
                    if convergence_score >= self.config.convergence_threshold:
                        logger.info(f"🎯 Converged at iteration {state.iteration} (convergence: {convergence_score:.2%})")
                        should_stop = True
                    elif eval_result is not None and isinstance(eval_result, EvaluationResult) and eval_result.converged:
                        logger.info(f"🎯 Evaluator indicates convergence at iteration {state.iteration}")
                        should_stop = True
                
                if should_stop:
                    break
            
            # Stage 3: Generate Final Report
            logger.info("📄 TTD-DR Stage 3: Generating final report...")
            debug.log_stage("FINAL_SYNTHESIS", iteration=state.iteration,
                           original_query=context.query,
                           plan_main_topic=state.research_plan.main_topic)
            debug.log_variable("context.query_at_synthesis", context.query, "before_final_synthesis")
            debug.log_variable("plan.main_topic_at_synthesis", state.research_plan.main_topic, "before_final_synthesis")
            
            state.stage = TTDDRStage.SYNTHESIZING
            
            final_report = await self._synthesize_final_report(
                state.current_draft,
                state.research_plan,
                state.search_history,
                state.convergence_scores,
                original_query=context.query  # Pass original query directly!
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
        
        try:
            # Use guided_json for guaranteed structured output
            guided_llm = self._create_guided_llm_for_plan()
            
            response = await guided_llm.ainvoke([
                SystemMessage(content="You are a research planning expert."),
                HumanMessage(content=prompt)
            ])
            
            # Parse with Pydantic (guaranteed valid from guided_json)
            plan_data = ResearchPlanSchema.model_validate_json(response.content)
            return ResearchPlan(
                main_topic=plan_data.main_topic,
                key_areas=plan_data.key_areas,
                sub_questions=plan_data.sub_questions,
                expected_sections=plan_data.expected_sections,
                search_strategy=plan_data.search_strategy
            )
        except Exception as e:
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
        
        try:
            class QuestionsSchema(BaseModel):
                questions: list = PydanticField(description="List of research questions")
                gaps_identified: list = PydanticField(default=[], description="Information gaps")
            
            json_schema = QuestionsSchema.model_json_schema()
            base_url = self.llm.openai_api_base if hasattr(self.llm, 'openai_api_base') else str(self.llm.base_url)
            
            guided_llm = LangChainChatOpenAI(
                base_url=base_url,
                model=self.llm.model_name,
                api_key="not-used",
                model_kwargs={"extra_body": {"nvext": {"guided_json": json_schema}}}
            )
            
            response = await guided_llm.ainvoke([
                SystemMessage(content="You are an expert at identifying research gaps."),
                HumanMessage(content=prompt)
            ])
            
            import sys
            print(f"🔸 TTD-DR QUESTIONS: LLM response = {response.content[:300] if response.content else 'EMPTY'}...", flush=True, file=sys.stderr)
            
            result = QuestionsSchema.model_validate_json(response.content)
            draft.gaps_identified = result.gaps_identified
            print(f"🔸 TTD-DR QUESTIONS: Parsed {len(result.questions)} questions", flush=True, file=sys.stderr)
            
            # Ensure we return at least some questions
            if not result.questions:
                print(f"🔸 TTD-DR QUESTIONS: Empty questions, using fallback", flush=True, file=sys.stderr)
                return [
                    {"question": f"More information about {plan.main_topic}", "purpose": "general", "priority": "high"},
                    {"question": f"What are the key aspects of {plan.main_topic}?", "purpose": "research", "priority": "medium"}
                ]
            
            return result.questions
            
        except Exception as e:
            import sys
            print(f"🔸 TTD-DR QUESTIONS: Exception: {e}", flush=True, file=sys.stderr)
            logger.warning(f"Failed to generate questions: {e}. Using fallback.")
            return [
                {"question": f"More information about {plan.main_topic}", "purpose": "general", "priority": "high"}
            ]
    
    async def _search_with_evolution(self, 
                                    questions: List[Dict[str, Any]],
                                    context: ResearchContext) -> List[Dict[str, Any]]:
        """Search for answers with optional self-evolution."""
        # Normalize questions - handle both string and dict formats
        normalized_questions = []
        for q in questions:
            if isinstance(q, str):
                normalized_questions.append(q)
            elif isinstance(q, dict):
                normalized_questions.append(q.get("question", str(q)))
            else:
                normalized_questions.append(str(q))
        
        # Get initial answers
        answers = await self.searcher.search_multiple(
            questions=normalized_questions,
            collection=context.collection,
            use_web=context.search_web
        )
        
        # Apply self-evolution if enabled
        if self.evolver and self.config.enable_self_evolution:
            evolved_answers = []
            for answer in answers:
                # Normalize answer - handle both string and dict formats
                answer_text = answer if isinstance(answer, str) else answer.get("answer", str(answer)) if isinstance(answer, dict) else str(answer)
                sources = answer.get("sources", []) if isinstance(answer, dict) else []
                confidence = answer.get("confidence", 0.8) if isinstance(answer, dict) else 0.8
                
                evolved = await self.evolver.evolve_answer(answer_text, sources)
                evolved_answers.append({
                    "answer": evolved,
                    "sources": sources,
                    "confidence": confidence * 1.1  # Boost confidence
                })
                
                # Track improvement
                self.metrics.evolution_improvements.append(0.1)  # Simplified metric
            
            return evolved_answers
        
        return answers
    
    async def _denoise_draft(self,
                            current_draft: DraftState,
                            new_information: List[Dict[str, Any]],
                            plan: ResearchPlan,
                            iteration: int,
                            red_team_feedback: Optional[str] = None,
                            evaluator_feedback: Optional[str] = None,
                            knowledge_base_facts: Optional[List[str]] = None) -> DraftState:
        """
        Denoise the draft by incorporating new information.
        
        Key TTD-DR enhancement: Accepts feedback from Red Team and Evaluator
        to guide the denoising process (dynamic prompt injection).
        """
        # Prepare new information summary (handle both string and dict formats)
        # LIMIT answer lengths to prevent context overflow
        info_lines = []
        for info in new_information:
            if isinstance(info, str):
                info_lines.append(f"Information: {info[:1500]}")  # Limit to 1500 chars
            elif isinstance(info, dict):
                question = info.get('question', 'N/A')
                answer = info.get('answer', str(info))[:1500]  # Limit answer to 1500 chars
                info_lines.append(f"Q: {question[:200]}\nA: {answer}")
            else:
                info_lines.append(f"Information: {str(info)[:1500]}")
        info_summary = "\n\n".join(info_lines)
        
        # Add Knowledge Base facts if available (from Context Pruner)
        if knowledge_base_facts:
            kb_context = KNOWLEDGE_BASE_CONTEXT.format(
                facts="\n".join([f"• {fact}" for fact in knowledge_base_facts[:15]])
            )
            info_summary = kb_context + "\n\n" + info_summary
        
        # Build critical feedback injection (from Red Team and/or Evaluator)
        critical_feedback = ""
        if red_team_feedback or evaluator_feedback:
            feedback_details = []
            if red_team_feedback:
                feedback_details.append(f"RED TEAM: {red_team_feedback}")
            if evaluator_feedback:
                feedback_details.append(f"EVALUATOR: {evaluator_feedback}")
            
            critical_feedback = CRITICAL_FEEDBACK_INJECTION.format(
                feedback_details="\n".join(feedback_details),
                iteration=iteration
            )
        
        # Limit draft length to prevent context overflow
        draft_content = current_draft.content[:8000]  # Max 8000 chars for draft
        
        prompt = DENOISING_PROMPT.format(
            current_draft=draft_content,
            new_information=info_summary,
            research_plan=json.dumps(plan.to_dict(), indent=2)[:1500],  # Limit plan
            iteration=iteration,
            convergence_score=current_draft.convergence_score * 100,
            critical_feedback=critical_feedback
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
        if red_team_feedback:
            improvements.append("Addressed Red Team feedback")
        if evaluator_feedback:
            improvements.append("Addressed Evaluator feedback")
        
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
        
        try:
            # Use guided_json for guaranteed structured output
            guided_llm = self._create_guided_llm_for_convergence()
            
            response = await guided_llm.ainvoke([
                SystemMessage(content="You are an expert at assessing document quality."),
                HumanMessage(content=prompt)
            ])
            
            # Parse with Pydantic (guaranteed valid from guided_json)
            result = ConvergenceCheckSchema.model_validate_json(response.content)
            return result.convergence_score / 100.0
        except Exception as e:
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
                                      convergence_scores: List[float],
                                      original_query: str = None) -> str:
        """Generate the final polished report (Stage 3)."""
        # Prepare search summary
        search_summary = f"Conducted {len(search_history)} searches across {draft.iteration} iterations"
        
        # Use original query if provided, otherwise fall back to plan.main_topic
        query_for_prompt = original_query if original_query else plan.main_topic
        
        # Limit draft and plan to prevent context overflow
        prompt = FINAL_REPORT_SYNTHESIS_PROMPT.format(
            query=query_for_prompt,  # Use original query, not LLM's summary
            draft=draft.content[:12000],  # Limit draft to 12000 chars
            research_plan=json.dumps(plan.to_dict(), indent=2)[:2000],  # Limit plan
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
