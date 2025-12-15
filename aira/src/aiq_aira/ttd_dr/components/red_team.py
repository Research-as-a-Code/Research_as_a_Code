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
import json
from dataclasses import dataclass
from typing import Dict, Any, List, Optional
from enum import Enum

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

logger = logging.getLogger(__name__)


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

Respond in JSON format:
{{
    "critiques": [
        {{
            "severity": "low|medium|high|critical",
            "category": "logic|evidence|accuracy|coherence|bias",
            "description": "Specific description of the flaw",
            "location": "Which section or part of the draft",
            "suggested_action": "What should be done to fix this",
            "confidence": 0.0-1.0
        }}
    ],
    "overall_assessment": "Brief summary of the draft's major weaknesses",
    "needs_major_revision": true/false,
    "quality_score": 0-100
}}

Be HARSH. A good Red Team finds problems. An excellent Red Team finds problems others missed.
"""


class RedTeamAgent:
    """
    Red Team agent for adversarial critique.
    
    Runs in parallel with other maintenance tasks after each refinement
    step. Generates structured Critique objects that force the Supervisor
    to address weaknesses.
    """
    
    def __init__(self, llm: BaseChatModel):
        """
        Initialize Red Team agent.
        
        Args:
            llm: Language model for critique generation
        """
        self.llm = llm
        self.logger = logging.getLogger(f"{__name__}.RedTeamAgent")
    
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
            response = await self.llm.ainvoke([
                SystemMessage(content="You are an adversarial Red Team analyst."),
                HumanMessage(content=prompt)
            ])
            
            # Parse JSON response
            result_data = json.loads(response.content)
            
            # Convert to Critique objects
            critiques = []
            for c in result_data.get("critiques", []):
                try:
                    severity = CritiqueSeverity(c.get("severity", "medium"))
                except ValueError:
                    severity = CritiqueSeverity.MEDIUM
                    
                critiques.append(Critique(
                    severity=severity,
                    category=c.get("category", "general"),
                    description=c.get("description", ""),
                    location=c.get("location", "unknown"),
                    suggested_action=c.get("suggested_action", ""),
                    confidence=c.get("confidence", 0.5)
                ))
            
            result = RedTeamResult(
                critiques=critiques,
                overall_assessment=result_data.get("overall_assessment", ""),
                needs_major_revision=result_data.get("needs_major_revision", False),
                quality_score=result_data.get("quality_score", 50.0)
            )
            
            # Log findings
            high_priority = result.get_high_priority_critiques()
            if high_priority:
                self.logger.warning(f"🔴 Red Team found {len(high_priority)} high-priority issues")
            else:
                self.logger.info(f"🔴 Red Team found {len(critiques)} issues (none critical)")
            
            return result
            
        except json.JSONDecodeError as e:
            self.logger.warning(f"Failed to parse Red Team response: {e}")
            # Return a basic critique indicating parsing failed
            return RedTeamResult(
                critiques=[Critique(
                    severity=CritiqueSeverity.MEDIUM,
                    category="general",
                    description="Red Team analysis could not be fully parsed",
                    location="entire draft",
                    suggested_action="Continue refinement",
                    confidence=0.3
                )],
                overall_assessment="Analysis incomplete due to parsing error",
                needs_major_revision=False,
                quality_score=60.0
            )
        except Exception as e:
            self.logger.error(f"Red Team analysis failed: {e}")
            return RedTeamResult(
                critiques=[],
                overall_assessment=f"Analysis failed: {str(e)}",
                needs_major_revision=False,
                quality_score=50.0
            )

