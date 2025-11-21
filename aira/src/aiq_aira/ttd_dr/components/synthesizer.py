# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Report Synthesizer component for TTD-DR.

Stage 3 of the TTD-DR pipeline: Generates the final polished report
from the converged draft and research history.
"""

import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from ..models import DraftState, ResearchPlan, SearchQAPair
from ..prompts import (
    FINAL_REPORT_SYNTHESIS_PROMPT,
    PARTIAL_RESULT_RECOVERY_PROMPT,
    QUALITY_ASSESSMENT_PROMPT
)

logger = logging.getLogger(__name__)


class ReportSynthesizer:
    """
    Synthesizes the final research report from the converged draft.
    
    This is the final stage that:
    1. Polishes the converged draft
    2. Ensures professional presentation
    3. Adds proper structure and formatting
    4. Integrates all gathered information seamlessly
    5. Provides quality assessment
    """
    
    def __init__(self, llm: BaseChatModel):
        """
        Initialize the report synthesizer.
        
        Args:
            llm: Language model for synthesis
        """
        self.llm = llm
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    async def synthesize(self,
                        draft: DraftState,
                        research_plan: ResearchPlan,
                        search_history: List[SearchQAPair],
                        convergence_scores: List[float]) -> str:
        """
        Generate the final polished report.
        
        Args:
            draft: Converged draft state
            research_plan: Original research plan
            search_history: Complete search history
            convergence_scores: Convergence progression
            
        Returns:
            Final polished report
        """
        self.logger.info(f"Synthesizing final report from draft with {draft.word_count} words")
        
        # Prepare synthesis context
        context = self._prepare_synthesis_context(
            draft,
            research_plan,
            search_history,
            convergence_scores
        )
        
        # Generate final report
        report = await self._generate_final_report(context)
        
        # Post-process the report
        report = self._post_process_report(report)
        
        # Assess quality
        quality_score = await self._assess_report_quality(
            report,
            research_plan.main_topic
        )
        
        self.logger.info(f"Final report generated: {len(report.split())} words, "
                        f"Quality score: {quality_score:.2%}")
        
        # Add metadata footer
        report = self._add_metadata_footer(
            report,
            research_plan,
            search_history,
            convergence_scores,
            quality_score
        )
        
        return report
    
    def _prepare_synthesis_context(self,
                                  draft: DraftState,
                                  research_plan: ResearchPlan,
                                  search_history: List[SearchQAPair],
                                  convergence_scores: List[float]) -> Dict[str, Any]:
        """
        Prepare context for final synthesis.
        
        Args:
            draft: Draft state
            research_plan: Research plan
            search_history: Search history
            convergence_scores: Convergence scores
            
        Returns:
            Synthesis context dictionary
        """
        # Summarize search history
        search_summary = self._summarize_search_history(search_history)
        
        # Calculate statistics
        stats = {
            "iterations": draft.iteration,
            "total_searches": len(search_history),
            "unique_sources": len(set(
                source.get("url", source.get("title", str(i)))
                for qa in search_history
                for i, source in enumerate(qa.sources)
            )),
            "final_convergence": convergence_scores[-1] if convergence_scores else 0,
            "word_count": draft.word_count
        }
        
        return {
            "draft": draft.content,
            "research_plan": research_plan,
            "search_summary": search_summary,
            "stats": stats
        }
    
    def _summarize_search_history(self, 
                                 search_history: List[SearchQAPair]) -> str:
        """
        Create a summary of the search history.
        
        Args:
            search_history: Complete search history
            
        Returns:
            Summary text
        """
        if not search_history:
            return "No searches performed"
        
        # Group by iteration
        iterations = {}
        for qa in search_history:
            if qa.iteration not in iterations:
                iterations[qa.iteration] = []
            iterations[qa.iteration].append(qa)
        
        # Create summary
        summary_parts = []
        for iter_num in sorted(iterations.keys()):
            qa_list = iterations[iter_num]
            summary_parts.append(
                f"Iteration {iter_num}: {len(qa_list)} searches, "
                f"avg confidence {sum(qa.confidence_score for qa in qa_list)/len(qa_list):.2f}"
            )
        
        return f"Conducted {len(search_history)} searches across {len(iterations)} iterations. " + \
               "; ".join(summary_parts)
    
    async def _generate_final_report(self, context: Dict[str, Any]) -> str:
        """
        Generate the final report from context.
        
        Args:
            context: Synthesis context
            
        Returns:
            Final report text
        """
        prompt = FINAL_REPORT_SYNTHESIS_PROMPT.format(
            draft=context["draft"],
            research_plan=json.dumps(context["research_plan"].to_dict(), indent=2),
            search_summary=context["search_summary"],
            iterations=context["stats"]["iterations"],
            convergence=context["stats"]["final_convergence"] * 100
        )
        
        try:
            response = await self.llm.ainvoke([
                SystemMessage(content="""You are an expert report writer creating a final, polished research report.
                Remove all draft markers, ensure professional presentation, and create a cohesive narrative.
                The report should be comprehensive, well-structured, and ready for presentation."""),
                HumanMessage(content=prompt)
            ])
            
            return response.content
            
        except Exception as e:
            self.logger.error(f"Report synthesis failed: {e}")
            # Return cleaned draft as fallback
            return self._clean_draft_fallback(context["draft"])
    
    def _post_process_report(self, report: str) -> str:
        """
        Post-process the report to ensure quality.
        
        Args:
            report: Raw report text
            
        Returns:
            Post-processed report
        """
        # Remove any remaining draft markers
        markers = [
            "[NEEDS RESEARCH]",
            "[UNVERIFIED]",
            "[TODO]",
            "[TBD]",
            "to be determined",
            "more information needed"
        ]
        
        for marker in markers:
            report = report.replace(marker, "")
        
        # Clean up excessive whitespace
        while "\n\n\n" in report:
            report = report.replace("\n\n\n", "\n\n")
        
        # Ensure proper markdown formatting
        lines = report.split('\n')
        processed_lines = []
        
        for line in lines:
            # Ensure headers have proper spacing
            if line.startswith('#'):
                if processed_lines and processed_lines[-1].strip():
                    processed_lines.append('')  # Add blank line before header
                processed_lines.append(line)
                processed_lines.append('')  # Add blank line after header
            else:
                # Avoid duplicate blank lines
                if line.strip() or (processed_lines and processed_lines[-1].strip()):
                    processed_lines.append(line)
        
        report = '\n'.join(processed_lines)
        
        # Ensure report starts with a title if missing
        if not report.strip().startswith('#'):
            report = "# Research Report\n\n" + report
        
        return report.strip()
    
    def _clean_draft_fallback(self, draft: str) -> str:
        """
        Clean the draft as a fallback when synthesis fails.
        
        Args:
            draft: Draft content
            
        Returns:
            Cleaned content
        """
        # Remove markers
        cleaned = draft
        for marker in ["[NEEDS RESEARCH]", "[UNVERIFIED]", "[TODO]", "[TBD]"]:
            cleaned = cleaned.replace(marker, "")
        
        # Add warning header
        warning = """# Research Report (Automatically Generated)

**Note**: This report was automatically generated from research drafts. 
Some sections may be incomplete.

---

"""
        
        return warning + cleaned
    
    async def _assess_report_quality(self,
                                    report: str,
                                    original_query: str) -> float:
        """
        Assess the quality of the final report.
        
        Args:
            report: Final report
            original_query: Original user query
            
        Returns:
            Quality score (0-1)
        """
        prompt = QUALITY_ASSESSMENT_PROMPT.format(
            report=report[:3000],  # Limit for context window
            query=original_query
        )
        
        try:
            response = await self.llm.ainvoke([
                SystemMessage(content="""You are an expert at assessing research report quality.
                Evaluate objectively based on the criteria provided."""),
                HumanMessage(content=prompt)
            ])
            
            # Parse the assessment
            quality_score = self._parse_quality_assessment(response.content)
            
            return quality_score
            
        except Exception as e:
            self.logger.warning(f"Quality assessment failed: {e}")
            # Return default medium quality
            return 0.75
    
    def _parse_quality_assessment(self, assessment: str) -> float:
        """
        Parse quality assessment to extract score.
        
        Args:
            assessment: Assessment text
            
        Returns:
            Quality score (0-1)
        """
        # Look for overall score in various formats
        import re
        
        # Try to find percentage
        percent_match = re.search(r'Overall.*?(\d+)%', assessment, re.IGNORECASE)
        if percent_match:
            return float(percent_match.group(1)) / 100
        
        # Try to find score out of 100
        score_match = re.search(r'Overall.*?(\d+)/100', assessment, re.IGNORECASE)
        if score_match:
            return float(score_match.group(1)) / 100
        
        # Try to find decimal score
        decimal_match = re.search(r'Overall.*?(0\.\d+)', assessment, re.IGNORECASE)
        if decimal_match:
            return float(decimal_match.group(1))
        
        # Count positive indicators
        positive_words = ['excellent', 'comprehensive', 'thorough', 'complete', 
                         'well-structured', 'clear', 'detailed']
        negative_words = ['incomplete', 'missing', 'unclear', 'poor', 
                         'insufficient', 'lacking']
        
        assessment_lower = assessment.lower()
        positive_count = sum(1 for word in positive_words if word in assessment_lower)
        negative_count = sum(1 for word in negative_words if word in assessment_lower)
        
        # Calculate score based on sentiment
        if positive_count + negative_count > 0:
            return positive_count / (positive_count + negative_count)
        
        return 0.75  # Default medium-high quality
    
    def _add_metadata_footer(self,
                            report: str,
                            research_plan: ResearchPlan,
                            search_history: List[SearchQAPair],
                            convergence_scores: List[float],
                            quality_score: float) -> str:
        """
        Add metadata footer to the report.
        
        Args:
            report: Final report
            research_plan: Research plan
            search_history: Search history
            convergence_scores: Convergence scores
            quality_score: Quality assessment score
            
        Returns:
            Report with metadata footer
        """
        # Calculate statistics
        unique_sources = set()
        for qa in search_history:
            for source in qa.sources:
                unique_sources.add(source.get("url", source.get("title", "Unknown")))
        
        footer = f"""

---

## Research Metadata

- **Research Method**: TTD-DR (Test-Time Diffusion Deep Researcher)
- **Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- **Iterations**: {len(convergence_scores)}
- **Convergence**: {convergence_scores[-1]*100:.1f}% (threshold: 85%)
- **Total Searches**: {len(search_history)}
- **Unique Sources**: {len(unique_sources)}
- **Quality Score**: {quality_score*100:.0f}%
- **Word Count**: {len(report.split())}

### Research Plan Summary
- **Topic**: {research_plan.main_topic}
- **Key Areas**: {', '.join(research_plan.key_areas[:3])}
- **Strategy**: {research_plan.search_strategy}
"""
        
        return report + footer
    
    async def generate_partial_report(self,
                                     draft: Optional[DraftState],
                                     research_plan: Optional[ResearchPlan],
                                     search_history: List[SearchQAPair],
                                     error: str) -> str:
        """
        Generate a report from partial results (error recovery).
        
        Args:
            draft: Partial draft (if available)
            research_plan: Research plan (if available)
            search_history: Any completed searches
            error: Error that occurred
            
        Returns:
            Best possible report from partial results
        """
        self.logger.warning(f"Generating partial report due to error: {error}")
        
        if not draft or not draft.content:
            # No draft available - create minimal report
            return self._create_minimal_report(research_plan, search_history, error)
        
        # Try to salvage the draft
        prompt = PARTIAL_RESULT_RECOVERY_PROMPT.format(
            iterations=draft.iteration,
            draft=draft.content,
            search_history=self._summarize_search_history(search_history)
        )
        
        try:
            response = await self.llm.ainvoke([
                SystemMessage(content="""You are creating a report from incomplete research.
                Make the best of available information and clearly note limitations."""),
                HumanMessage(content=prompt)
            ])
            
            report = response.content
            
        except Exception as e:
            self.logger.error(f"Partial report generation failed: {e}")
            report = self._clean_draft_fallback(draft.content)
        
        # Add error notice
        error_notice = f"""
## Important Notice

This report was generated from incomplete research due to an interruption:
- Error: {error}
- Completed Iterations: {draft.iteration if draft else 0}
- Some sections may be incomplete or based on preliminary findings
"""
        
        return report + error_notice
    
    def _create_minimal_report(self,
                              research_plan: Optional[ResearchPlan],
                              search_history: List[SearchQAPair],
                              error: str) -> str:
        """
        Create a minimal report when no draft is available.
        
        Args:
            research_plan: Research plan if available
            search_history: Any completed searches
            error: Error that occurred
            
        Returns:
            Minimal report
        """
        report = f"""# Research Report (Incomplete)

## Error Occurred

The research process was interrupted due to an error:
{error}

## Research Plan

"""
        
        if research_plan:
            report += f"""Topic: {research_plan.main_topic}

Key Areas Identified:
{chr(10).join('- ' + area for area in research_plan.key_areas)}

Research Questions:
{chr(10).join('1. ' + q for q in research_plan.sub_questions[:5])}
"""
        else:
            report += "Research plan was not completed.\n"
        
        if search_history:
            report += f"""

## Partial Findings

{len(search_history)} searches were completed before interruption:

"""
            for qa in search_history[:5]:
                report += f"""
**Q**: {qa.question}
**A**: {qa.answer[:200]}...
"""
        
        report += """

## Limitations

This report is incomplete due to the processing error. The findings above represent
only partial research results and should not be considered comprehensive.
"""
        
        return report
