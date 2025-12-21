# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Red Team Agent for TTD-DR.

This module implements an adversarial critique mechanism that finds logical
flaws, weak arguments, and potential errors in the draft. It acts as a
"noise reducer" by forcing the main loop to self-correct.

Reference: Fareed Khan's TTD-DR implementation
"""

import logging
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Literal
from enum import Enum

from pydantic import BaseModel, Field as PydanticField
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI as LangChainChatOpenAI

logger = logging.getLogger(__name__)


# ========================================
# Pydantic Schemas for NVIDIA Guided JSON
# ========================================

class CritiqueSchema(BaseModel):
    """Pydantic schema for guided JSON output."""
    severity: Literal["low", "medium", "high", "critical"] = PydanticField(
        description="Severity level of the critique"
    )
    category: Literal["logic", "evidence", "accuracy", "coherence", "bias", "general"] = PydanticField(
        description="Category of the issue"
    )
    description: str = PydanticField(description="Specific description of the flaw")
    location: str = PydanticField(description="Which section or part of the draft")
    suggested_action: str = PydanticField(description="What should be done to fix this")
    confidence: float = PydanticField(ge=0, le=100, description="Confidence in this critique (0-100)")


class RedTeamOutputSchema(BaseModel):
    """Pydantic schema for complete Red Team output."""
    critiques: List[CritiqueSchema] = PydanticField(
        default_factory=list,
        description="List of critiques found in the draft"
    )
    overall_assessment: str = PydanticField(
        description="Brief summary of the draft's major weaknesses"
    )
    needs_major_revision: bool = PydanticField(
        description="Whether the draft needs major revision"
    )
    quality_score: float = PydanticField(
        ge=0, le=100,
        description="Overall quality score (0-100)"
    )


# ========================================
# Original Dataclasses (kept for compatibility)
# ========================================

class CritiqueSeverity(Enum):
    """Severity levels for critiques."""
    LOW = "low"          # Minor issues, polish needed
    MEDIUM = "medium"    # Notable issues, targeted fixes needed
    HIGH = "high"        # Significant flaws, major revision needed
    CRITICAL = "critical"  # Fundamental problems, ground-up rewrite


@dataclass
class Critique:
    """
    Structured feedback from the Red Team agent.
    
    Forces adversarial feedback into a structured format for
    actionable self-correction.
    """
    severity: CritiqueSeverity
    category: str  # "logic", "evidence", "accuracy", "coherence", "bias"
    description: str
    location: str  # Section or area of the draft
    suggested_action: str
    confidence: float  # 0-1 confidence in this critique
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "severity": self.severity.value,
            "category": self.category,
            "description": self.description,
            "location": self.location,
            "suggested_action": self.suggested_action,
            "confidence": self.confidence
        }


@dataclass 
class RedTeamResult:
    """Complete result from Red Team analysis."""
    critiques: List[Critique]
    overall_assessment: str
    needs_major_revision: bool
    quality_score: float  # 0-100
    
    @property
    def critical_issues(self) -> List[str]:
        """Get list of critical issue descriptions for feedback injection."""
        high_priority = self.get_high_priority_critiques()
        return [f"{c.category}: {c.description}" for c in high_priority]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "critiques": [c.to_dict() for c in self.critiques],
            "overall_assessment": self.overall_assessment,
            "needs_major_revision": self.needs_major_revision,
            "quality_score": self.quality_score
        }
    
    def get_high_priority_critiques(self) -> List[Critique]:
        """Get critiques that need immediate attention."""
        return [c for c in self.critiques 
                if c.severity in [CritiqueSeverity.HIGH, CritiqueSeverity.CRITICAL]]
    
    def get_priority_message(self) -> str:
        """Generate a priority message for the Supervisor."""
        high_critiques = self.get_high_priority_critiques()
        if not high_critiques:
            return ""
        
        message = "⚠️ RED TEAM CRITICAL FEEDBACK:\n"
        for c in high_critiques:
            message += f"- [{c.severity.value.upper()}] {c.category}: {c.description}\n"
            message += f"  Action: {c.suggested_action}\n"
        return message


RED_TEAM_PROMPT = """You are an adversarial Red Team analyst. Your SOLE purpose is to find weaknesses, logical flaws, and potential errors in research drafts.

You are NOT here to be helpful or constructive. You are here to ATTACK the draft and expose its weaknesses. Think like a skeptical peer reviewer, a fact-checker, or an opposing counsel.

## Your Analysis Targets

1. **Logical Flaws**: Find reasoning errors, non-sequiturs, and unfounded conclusions
2. **Evidence Gaps**: Identify claims without proper support or verification
3. **Accuracy Issues**: Spot potential factual errors, outdated information, or misrepresentations
4. **Coherence Problems**: Find inconsistencies within the draft, contradictions, or unclear arguments
5. **Bias Detection**: Identify one-sided arguments, missing perspectives, or cherry-picked evidence

## Research Brief (What the report should achieve)
{research_brief}

## Current Draft to Critique
{draft}

## Your Task

Analyze this draft AGGRESSIVELY. Look for:
- Assumptions stated as facts
- Conclusions that don't follow from evidence
- Missing counterarguments
- Oversimplifications
- Generic statements without specifics
- Claims that would not withstand expert scrutiny

Be HARSH. A good Red Team finds problems. An excellent Red Team finds problems others missed.
"""


class RedTeamAgent:
    """
    Red Team agent for adversarial critique.
    
    Runs in parallel with other maintenance tasks after each refinement
    step. Generates structured Critique objects that force the Supervisor
    to address weaknesses.
    
    Uses NVIDIA NIM guided_json for guaranteed structured output.
    """
    
    def __init__(self, llm: BaseChatModel):
        """
        Initialize Red Team agent.
        
        Args:
            llm: Language model for critique generation
        """
        self.llm = llm
        self.logger = logging.getLogger(f"{__name__}.RedTeamAgent")
        
        # Extract LLM config for guided_json
        self._base_url = getattr(llm, 'openai_api_base', None) or getattr(llm, 'base_url', None)
        if self._base_url and hasattr(self._base_url, '__str__'):
            self._base_url = str(self._base_url)
        self._model_name = getattr(llm, 'model_name', "nvidia/llama-3.1-nemotron-nano-8b-v1")
    
    def _create_guided_llm(self) -> LangChainChatOpenAI:
        """Create LLM with NVIDIA guided_json for structured output."""
        json_schema = RedTeamOutputSchema.model_json_schema()
        
        return LangChainChatOpenAI(
            base_url=self._base_url,
            model=self._model_name,
            api_key="not-used",
            model_kwargs={
                "extra_body": {"nvext": {"guided_json": json_schema}}
            }
        )
    
    async def critique(self, 
                      draft: str, 
                      research_brief: str,
                      iteration: int = 0) -> RedTeamResult:
        """
        Generate adversarial critique of the draft.
        
        Args:
            draft: Current draft content
            research_brief: The original research brief/plan
            iteration: Current iteration number
            
        Returns:
            RedTeamResult with structured critiques
        """
        self.logger.info(f"🔴 Red Team analyzing draft (iteration {iteration})...")
        
        prompt = RED_TEAM_PROMPT.format(
            research_brief=research_brief[:2000],  # Limit length
            draft=draft[:8000]  # Limit draft length
        )
        
        try:
            # Use guided_json for guaranteed structured output
            guided_llm = self._create_guided_llm()
            
            response = await guided_llm.ainvoke([
                SystemMessage(content="You are an adversarial Red Team analyst."),
                HumanMessage(content=prompt)
            ])
            
            # Parse with Pydantic (guaranteed valid from guided_json)
            result_data = RedTeamOutputSchema.model_validate_json(response.content)
            
            # Convert to Critique objects
            critiques = []
            for c in result_data.critiques:
                try:
                    severity = CritiqueSeverity(c.severity)
                except ValueError:
                    severity = CritiqueSeverity.MEDIUM
                    
                critiques.append(Critique(
                    severity=severity,
                    category=c.category,
                    description=c.description,
                    location=c.location,
                    suggested_action=c.suggested_action,
                    confidence=c.confidence
                ))
            
            result = RedTeamResult(
                critiques=critiques,
                overall_assessment=result_data.overall_assessment,
                needs_major_revision=result_data.needs_major_revision,
                quality_score=result_data.quality_score
            )
            
            # Log findings
            high_priority = result.get_high_priority_critiques()
            if high_priority:
                self.logger.warning(f"🔴 Red Team found {len(high_priority)} high-priority issues")
            else:
                self.logger.info(f"🔴 Red Team found {len(critiques)} issues (none critical)")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Red Team analysis failed: {e}")
            # Return a basic result on failure
            return RedTeamResult(
                critiques=[Critique(
                    severity=CritiqueSeverity.MEDIUM,
                    category="general",
                    description=f"Red Team analysis failed: {str(e)}",
                    location="entire draft",
                    suggested_action="Continue refinement",
                    confidence=0.3
                )],
                overall_assessment=f"Analysis failed: {str(e)}",
                needs_major_revision=False,
                quality_score=50.0
            )
