# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Draft Denoiser component for TTD-DR.

Core innovation of TTD-DR: Treats the draft as a "noisy" signal that gets
progressively refined through iterations of information incorporation.
"""

import logging
import re
from typing import Dict, Any, List, Optional, Tuple
from difflib import SequenceMatcher

from pydantic import BaseModel, Field as PydanticField
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI as LangChainChatOpenAI

from ..models import DraftState, ResearchPlan, TTDDRConfig
from ..prompts import DENOISING_PROMPT, CONVERGENCE_CHECK_PROMPT

logger = logging.getLogger(__name__)


# ========================================
# Pydantic Schema for NVIDIA Guided JSON
# ========================================

class ConvergenceCheckSchema(BaseModel):
    """Schema for convergence assessment output."""
    convergence_score: float = PydanticField(
        ge=0, le=100,
        description="Convergence score from 0-100 (100 = fully converged)"
    )
    reasoning: str = PydanticField(
        default="",
        description="Brief explanation of the assessment"
    )


class DraftDenoiser:
    """
    Performs report-level denoising with retrieval.
    
    This is the core innovation of TTD-DR - treating report generation
    as a diffusion process where a noisy draft is progressively refined
    by incorporating retrieved information.
    
    Key responsibilities:
    1. Incorporate new information into the draft
    2. Verify and correct existing claims
    3. Fill information gaps
    4. Improve coherence and flow
    5. Track convergence toward final quality
    """
    
    def __init__(self, 
                 llm: BaseChatModel,
                 config: TTDDRConfig):
        """
        Initialize the denoiser.
        
        Args:
            llm: Language model for denoising
            config: TTD-DR configuration
        """
        self.llm = llm
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Extract LLM config for guided_json
        self._base_url = getattr(llm, 'openai_api_base', None) or getattr(llm, 'base_url', None)
        if self._base_url and hasattr(self._base_url, '__str__'):
            self._base_url = str(self._base_url)
        self._model_name = getattr(llm, 'model_name', "nvidia/llama-3.1-nemotron-nano-8b-v1")
    
    def _create_guided_llm_for_convergence(self) -> LangChainChatOpenAI:
        """Create LLM with NVIDIA guided_json for convergence assessment."""
        json_schema = ConvergenceCheckSchema.model_json_schema()
        
        return LangChainChatOpenAI(
            base_url=self._base_url,
            model=self._model_name,
            api_key="not-used",
            model_kwargs={
                "extra_body": {"nvext": {"guided_json": json_schema}}
            }
        )
    
    async def denoise(self,
                     current_draft: DraftState,
                     new_information: List[Dict[str, Any]],
                     research_plan: ResearchPlan,
                     iteration: int,
                     temperature: Optional[float] = None) -> DraftState:
        """
        Perform one denoising iteration on the draft.
        
        This is the core operation that refines the draft by incorporating
        new information and improving quality.
        
        Args:
            current_draft: Current draft state
            new_information: New information from searches
            research_plan: Research plan guiding the process
            iteration: Current iteration number
            temperature: Optional temperature override
            
        Returns:
            Refined DraftState
        """
        self.logger.info(f"Denoising iteration {iteration} with {len(new_information)} new pieces of information")
        
        # Prepare the denoising prompt
        prompt = self._prepare_denoising_prompt(
            current_draft,
            new_information,
            research_plan,
            iteration
        )
        
        # Select denoising strategy
        strategy = self._select_denoising_strategy(
            current_draft,
            iteration
        )
        
        # Apply denoising
        revised_content = await self._apply_denoising(
            prompt,
            strategy,
            temperature or self.config.denoising_temperature
        )
        
        # Analyze improvements
        improvements = self._analyze_improvements(
            current_draft.content,
            revised_content
        )
        
        # Identify remaining gaps
        gaps = self._identify_gaps(revised_content)
        
        # Create new draft state
        new_draft = DraftState(
            content=revised_content,
            iteration=iteration,
            convergence_score=current_draft.convergence_score,  # Updated separately
            gaps_identified=gaps,
            improvements_made=improvements,
            word_count=len(revised_content.split())
        )
        
        self.logger.info(f"Denoising complete. Word count: {current_draft.word_count} → {new_draft.word_count}")
        self.logger.info(f"Improvements: {improvements}")
        self.logger.info(f"Remaining gaps: {len(gaps)}")
        
        return new_draft
    
    async def calculate_convergence(self,
                                  old_draft: str,
                                  new_draft: str) -> float:
        """
        Calculate convergence score between two draft versions.
        
        Convergence indicates how much the draft has stabilized
        and whether further iterations are needed.
        
        Args:
            old_draft: Previous draft content
            new_draft: New draft content
            
        Returns:
            Convergence score between 0 and 1
        """
        self.logger.info("Calculating convergence score...")
        
        # Use LLM-based assessment for accurate convergence
        try:
            score = await self._llm_convergence_assessment(old_draft, new_draft)
        except Exception as e:
            self.logger.warning(f"LLM convergence assessment failed: {e}, using heuristic")
            score = self._heuristic_convergence(old_draft, new_draft)
        
        self.logger.info(f"Convergence score: {score:.2%}")
        return score
    
    def _prepare_denoising_prompt(self,
                                 current_draft: DraftState,
                                 new_information: List[Dict[str, Any]],
                                 research_plan: ResearchPlan,
                                 iteration: int) -> str:
        """
        Prepare the denoising prompt with all necessary information.
        
        Args:
            current_draft: Current draft
            new_information: New information to incorporate
            research_plan: Research plan
            iteration: Iteration number
            
        Returns:
            Formatted prompt string
        """
        # Format new information
        info_sections = []
        for i, info in enumerate(new_information, 1):
            question = info.get("question", "N/A")
            answer = info.get("answer", "N/A")
            sources = info.get("sources", [])
            
            source_list = ", ".join([s.get("title", "Unknown") for s in sources[:3]])
            
            info_sections.append(
                f"Information {i}:\n"
                f"Question: {question}\n"
                f"Answer: {answer}\n"
                f"Sources: {source_list}\n"
            )
        
        new_info_text = "\n---\n".join(info_sections)
        
        # Create prompt
        prompt = DENOISING_PROMPT.format(
            current_draft=current_draft.content,
            new_information=new_info_text,
            research_plan=json.dumps(research_plan.to_dict(), indent=2),
            iteration=iteration,
            convergence_score=current_draft.convergence_score * 100
        )
        
        return prompt
    
    def _select_denoising_strategy(self,
                                  current_draft: DraftState,
                                  iteration: int) -> str:
        """
        Select the denoising strategy based on current state.
        
        Args:
            current_draft: Current draft
            iteration: Iteration number
            
        Returns:
            Strategy name: "aggressive", "conservative", or "adaptive"
        """
        if self.config.denoising_strategy != "adaptive":
            return self.config.denoising_strategy
        
        # Adaptive strategy selection
        if iteration <= 1:
            # Early iterations: aggressive to incorporate maximum information
            return "aggressive"
        elif current_draft.convergence_score > 0.7:
            # High convergence: conservative to preserve quality
            return "conservative"
        else:
            # Middle ground: balanced approach
            return "adaptive"
    
    async def _apply_denoising(self,
                              prompt: str,
                              strategy: str,
                              temperature: float) -> str:
        """
        Apply the denoising transformation.
        
        Args:
            prompt: Denoising prompt
            strategy: Strategy to use
            temperature: LLM temperature
            
        Returns:
            Denoised content
        """
        # Adjust system message based on strategy
        if strategy == "aggressive":
            system_msg = """You are an aggressive editor who boldly incorporates new information 
            and makes substantial improvements. Don't hesitate to rewrite sections completely
            if the new information provides better content."""
        elif strategy == "conservative":
            system_msg = """You are a conservative editor who carefully preserves existing quality
            while selectively incorporating only the most valuable new information.
            Make minimal changes unless absolutely necessary."""
        else:  # adaptive
            system_msg = """You are a balanced editor who judiciously incorporates new information
            while preserving the existing structure and flow. Make improvements where they
            add clear value."""
        
        try:
            response = await self.llm.ainvoke(
                [
                    SystemMessage(content=system_msg),
                    HumanMessage(content=prompt)
                ],
                temperature=temperature
            )
            
            return response.content
            
        except Exception as e:
            self.logger.error(f"Denoising failed: {e}")
            # Return original content as fallback
            return prompt.split("Current Draft:")[1].split("New Information:")[0].strip()
    
    def _analyze_improvements(self,
                            old_content: str,
                            new_content: str) -> List[str]:
        """
        Analyze what improvements were made.
        
        Args:
            old_content: Previous content
            new_content: New content
            
        Returns:
            List of improvements made
        """
        improvements = []
        
        # Check for gap filling
        old_gaps = old_content.count("[NEEDS RESEARCH]")
        new_gaps = new_content.count("[NEEDS RESEARCH]")
        if new_gaps < old_gaps:
            improvements.append(f"Filled {old_gaps - new_gaps} research gaps")
        
        # Check for verification
        old_unverified = old_content.count("[UNVERIFIED]")
        new_unverified = new_content.count("[UNVERIFIED]")
        if new_unverified < old_unverified:
            improvements.append(f"Verified {old_unverified - new_unverified} claims")
        
        # Check for content expansion
        old_words = len(old_content.split())
        new_words = len(new_content.split())
        if new_words > old_words * 1.1:
            improvements.append(f"Expanded content by {new_words - old_words} words")
        
        # Check for new sections
        old_sections = self._count_sections(old_content)
        new_sections = self._count_sections(new_content)
        if new_sections > old_sections:
            improvements.append(f"Added {new_sections - old_sections} new sections")
        
        # Check for citations/sources
        old_sources = old_content.count("Source:") + old_content.count("source:")
        new_sources = new_content.count("Source:") + new_content.count("source:")
        if new_sources > old_sources:
            improvements.append(f"Added {new_sources - old_sources} source citations")
        
        if not improvements:
            improvements.append("Refined existing content")
        
        return improvements
    
    def _identify_gaps(self, content: str) -> List[str]:
        """
        Identify remaining gaps in the content.
        
        Args:
            content: Draft content
            
        Returns:
            List of identified gaps
        """
        gaps = []
        
        # Check for explicit gap markers
        if "[NEEDS RESEARCH]" in content:
            count = content.count("[NEEDS RESEARCH]")
            gaps.append(f"{count} sections still need research")
        
        if "[UNVERIFIED]" in content:
            count = content.count("[UNVERIFIED]")
            gaps.append(f"{count} claims remain unverified")
        
        # Check for placeholder text
        placeholders = [
            "to be determined",
            "more information needed",
            "further research required",
            "details pending",
            "[TODO]",
            "[TBD]"
        ]
        
        for placeholder in placeholders:
            if placeholder.lower() in content.lower():
                gaps.append(f"Contains placeholder: '{placeholder}'")
        
        # Check for very short sections
        sections = content.split('\n\n')
        short_sections = [s for s in sections if 10 < len(s.split()) < 30]
        if short_sections:
            gaps.append(f"{len(short_sections)} sections appear incomplete")
        
        # Check for missing expected sections from plan
        # (This would need the research plan for full implementation)
        
        return gaps
    
    def _count_sections(self, content: str) -> int:
        """
        Count the number of sections in the content.
        
        Args:
            content: Draft content
            
        Returns:
            Number of sections
        """
        # Count markdown headers
        headers = len(re.findall(r'^#+\s', content, re.MULTILINE))
        
        # Also count section breaks
        breaks = content.count('\n\n\n')
        
        return max(headers, breaks + 1)
    
    async def _llm_convergence_assessment(self,
                                         old_draft: str,
                                         new_draft: str) -> float:
        """
        Use LLM to assess convergence between drafts.
        
        Args:
            old_draft: Previous draft
            new_draft: New draft
            
        Returns:
            Convergence score (0-1)
        """
        # Limit content length for prompt
        old_preview = old_draft[:2000] if len(old_draft) > 2000 else old_draft
        new_preview = new_draft[:2000] if len(new_draft) > 2000 else new_draft
        
        prompt = CONVERGENCE_CHECK_PROMPT.format(
            previous_draft=old_preview,
            current_draft=new_preview
        )
        
        # Use guided_json for guaranteed structured output
        guided_llm = self._create_guided_llm_for_convergence()
        
        response = await guided_llm.ainvoke([
            SystemMessage(content="""You are an expert at assessing document quality and convergence.
            Evaluate the improvement between drafts accurately."""),
            HumanMessage(content=prompt)
        ])
        
        # Parse with Pydantic (guaranteed valid from guided_json)
        result = ConvergenceCheckSchema.model_validate_json(response.content)
        
        return result.convergence_score / 100.0
    
    def _heuristic_convergence(self,
                              old_draft: str,
                              new_draft: str) -> float:
        """
        Calculate convergence using heuristics.
        
        Args:
            old_draft: Previous draft
            new_draft: New draft
            
        Returns:
            Convergence score (0-1)
        """
        score = 0.0
        
        # Similarity ratio (high similarity = high convergence)
        similarity = SequenceMatcher(None, old_draft, new_draft).ratio()
        score += similarity * 0.3
        
        # Gap resolution (fewer gaps = higher convergence)
        old_gaps = old_draft.count("[NEEDS RESEARCH]") + old_draft.count("[UNVERIFIED]")
        new_gaps = new_draft.count("[NEEDS RESEARCH]") + new_draft.count("[UNVERIFIED]")
        if old_gaps > 0:
            gap_resolution = 1.0 - (new_gaps / old_gaps)
        else:
            gap_resolution = 0.8 if new_gaps == 0 else 0.5
        score += gap_resolution * 0.3
        
        # Content growth (moderate growth = good)
        old_words = len(old_draft.split())
        new_words = len(new_draft.split())
        growth_ratio = new_words / max(old_words, 1)
        
        if 1.02 <= growth_ratio <= 1.15:
            score += 0.3  # Healthy growth
        elif growth_ratio < 1.02:
            score += 0.35  # Stable (high convergence)
        else:
            score += 0.2  # Too much growth (still evolving)
        
        # Structure stability (section count)
        old_sections = self._count_sections(old_draft)
        new_sections = self._count_sections(new_draft)
        if old_sections == new_sections:
            score += 0.1  # Stable structure
        
        return min(score, 1.0)
