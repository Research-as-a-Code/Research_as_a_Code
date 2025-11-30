# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Research Planner component for TTD-DR.

Stage 1 of the TTD-DR pipeline: Generates structured research plans
that guide the iterative search and refinement process.
"""

import json
import logging
from typing import Dict, Any, List, Optional
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from ..models import ResearchPlan
from ..prompts import RESEARCH_PLAN_PROMPT

logger = logging.getLogger(__name__)


class ResearchPlanner:
    """
    Generates structured research plans from user queries.
    
    The research plan serves as a roadmap for the entire TTD-DR process,
    defining key areas to investigate, questions to answer, and the
    expected structure of the final report.
    """
    
    def __init__(self, llm: BaseChatModel):
        """
        Initialize the research planner.
        
        Args:
            llm: Language model for plan generation
        """
        self.llm = llm
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    async def generate_plan(self, 
                           query: str, 
                           context: Dict[str, Any]) -> ResearchPlan:
        """
        Generate a comprehensive research plan from a user query.
        
        Args:
            query: The user's research query
            context: Additional context (collection, preferences, etc.)
            
        Returns:
            ResearchPlan with structured approach to the research
        """
        self.logger.info(f"Generating research plan for query: {query[:100]}...")
        
        # Prepare the prompt
        prompt = RESEARCH_PLAN_PROMPT.format(query=query)
        
        # Add any context-specific instructions
        # Handle both dict and ResearchContext object
        collection = context.get("collection") if isinstance(context, dict) else getattr(context, "collection", None)
        if collection:
            # Handle both single string and list of collections
            if isinstance(collection, list):
                coll_str = ", ".join(collection)
                prompt += f"\n\nNote: Focus on information from these collections: {coll_str}"
            else:
                prompt += f"\n\nNote: Focus on information from the {collection} collection."
        
        try:
            # Generate the plan
            response = await self.llm.ainvoke([
                SystemMessage(content="""You are an expert research planner. 
                Create comprehensive, well-structured research plans that guide systematic investigation.
                Always respond with valid JSON."""),
                HumanMessage(content=prompt)
            ])
            
            # Parse the JSON response
            plan_data = self._parse_plan_response(response.content)
            
            # Validate and enhance the plan
            plan = self._create_research_plan(plan_data, query)
            
            self.logger.info(f"Generated plan with {len(plan.key_areas)} key areas and {len(plan.sub_questions)} questions")
            
            return plan
            
        except Exception as e:
            self.logger.error(f"Failed to generate research plan: {e}")
            # Return a fallback plan
            return self._create_fallback_plan(query)
    
    def _parse_plan_response(self, response: str) -> Dict[str, Any]:
        """
        Parse the LLM response into a structured plan.
        
        Args:
            response: Raw LLM response
            
        Returns:
            Parsed plan data dictionary
        """
        try:
            # Try to parse as JSON
            if "```json" in response:
                # Extract JSON from markdown code block
                json_start = response.index("```json") + 7
                json_end = response.index("```", json_start)
                json_str = response[json_start:json_end].strip()
                return json.loads(json_str)
            else:
                # Direct JSON parsing
                return json.loads(response)
                
        except (json.JSONDecodeError, ValueError) as e:
            self.logger.warning(f"Failed to parse JSON response: {e}")
            # Try to extract structure from text
            return self._extract_plan_from_text(response)
    
    def _extract_plan_from_text(self, text: str) -> Dict[str, Any]:
        """
        Extract plan structure from unformatted text.
        
        Args:
            text: Unstructured text response
            
        Returns:
            Best-effort extracted plan data
        """
        lines = text.split('\n')
        plan_data = {
            "main_topic": "",
            "key_areas": [],
            "sub_questions": [],
            "expected_sections": [],
            "search_strategy": "comprehensive"
        }
        
        current_section = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Detect sections
            if "main topic" in line.lower() or "topic:" in line.lower():
                current_section = "main_topic"
                # Try to extract the topic from the same line
                if ":" in line:
                    plan_data["main_topic"] = line.split(":", 1)[1].strip()
            elif "key area" in line.lower():
                current_section = "key_areas"
            elif "question" in line.lower():
                current_section = "sub_questions"
            elif "section" in line.lower():
                current_section = "expected_sections"
            elif "strategy" in line.lower():
                current_section = "search_strategy"
                if ":" in line:
                    plan_data["search_strategy"] = line.split(":", 1)[1].strip()
            # Add content to current section
            elif current_section and line.startswith(('-', '*', '•', '1', '2', '3')):
                content = line.lstrip('-*•0123456789. ').strip()
                if current_section == "main_topic":
                    plan_data["main_topic"] = content
                elif current_section == "search_strategy":
                    plan_data["search_strategy"] = content
                elif current_section in ["key_areas", "sub_questions", "expected_sections"]:
                    plan_data[current_section].append(content)
        
        return plan_data
    
    def _create_research_plan(self, 
                            plan_data: Dict[str, Any], 
                            original_query: str) -> ResearchPlan:
        """
        Create a ResearchPlan object from parsed data.
        
        Args:
            plan_data: Parsed plan data
            original_query: Original user query
            
        Returns:
            Validated ResearchPlan object
        """
        # Ensure all required fields have values
        main_topic = plan_data.get("main_topic", "").strip()
        if not main_topic:
            main_topic = original_query
        
        key_areas = plan_data.get("key_areas", [])
        if not key_areas:
            key_areas = self._generate_default_key_areas(original_query)
        
        sub_questions = plan_data.get("sub_questions", [])
        if not sub_questions:
            sub_questions = self._generate_default_questions(original_query, key_areas)
        
        expected_sections = plan_data.get("expected_sections", [])
        if not expected_sections:
            expected_sections = self._generate_default_sections(key_areas)
        
        search_strategy = plan_data.get("search_strategy", "comprehensive")
        
        # Add metadata
        metadata = {
            "original_query": original_query,
            "plan_quality": self._assess_plan_quality(plan_data)
        }
        
        return ResearchPlan(
            main_topic=main_topic,
            key_areas=key_areas[:5],  # Limit to 5 areas
            sub_questions=sub_questions[:8],  # Limit to 8 questions
            expected_sections=expected_sections,
            search_strategy=search_strategy,
            metadata=metadata
        )
    
    def _generate_default_key_areas(self, query: str) -> List[str]:
        """Generate default key areas based on query."""
        # Simple heuristic-based generation
        areas = ["Background and Context"]
        
        if "compare" in query.lower() or "vs" in query.lower():
            areas.extend(["Comparison Criteria", "Option Analysis"])
        elif "how" in query.lower():
            areas.extend(["Process Overview", "Implementation Steps"])
        elif "why" in query.lower():
            areas.extend(["Causes and Factors", "Implications"])
        else:
            areas.extend(["Current State", "Key Considerations"])
        
        areas.extend(["Analysis and Findings", "Recommendations"])
        
        return areas
    
    def _generate_default_questions(self, query: str, key_areas: List[str]) -> List[str]:
        """Generate default research questions."""
        questions = [query]  # Start with original query
        
        # Add questions for each key area
        for area in key_areas[:3]:
            questions.append(f"What are the key aspects of {area.lower()}?")
        
        # Add standard investigative questions
        questions.extend([
            f"What are the current best practices related to {query[:50]}?",
            f"What challenges or limitations exist?",
            f"What are the future implications?"
        ])
        
        return questions
    
    def _generate_default_sections(self, key_areas: List[str]) -> List[str]:
        """Generate default report sections."""
        sections = ["Executive Summary", "Introduction"]
        
        # Add sections based on key areas
        for area in key_areas:
            if area not in ["Background and Context", "Introduction"]:
                sections.append(area)
        
        sections.extend(["Conclusion", "References"])
        
        return sections
    
    def _assess_plan_quality(self, plan_data: Dict[str, Any]) -> str:
        """
        Assess the quality of the generated plan.
        
        Args:
            plan_data: The plan data to assess
            
        Returns:
            Quality rating: "high", "medium", or "low"
        """
        score = 0
        
        # Check completeness
        if plan_data.get("main_topic"):
            score += 1
        if len(plan_data.get("key_areas", [])) >= 3:
            score += 1
        if len(plan_data.get("sub_questions", [])) >= 5:
            score += 1
        if len(plan_data.get("expected_sections", [])) >= 4:
            score += 1
        if plan_data.get("search_strategy"):
            score += 1
        
        # Determine quality level
        if score >= 4:
            return "high"
        elif score >= 3:
            return "medium"
        else:
            return "low"
    
    def _create_fallback_plan(self, query: str) -> ResearchPlan:
        """
        Create a basic fallback plan when generation fails.
        
        Args:
            query: Original user query
            
        Returns:
            Basic but functional ResearchPlan
        """
        self.logger.warning("Using fallback research plan")
        
        return ResearchPlan(
            main_topic=query,
            key_areas=[
                "Background Information",
                "Current State Analysis", 
                "Key Findings",
                "Implications and Recommendations"
            ],
            sub_questions=[
                query,
                f"What is the background context for {query[:50]}?",
                f"What are the current developments?",
                f"What are the key challenges?",
                f"What are the best practices?",
                f"What are the future implications?"
            ],
            expected_sections=[
                "Introduction",
                "Background",
                "Analysis",
                "Findings",
                "Recommendations",
                "Conclusion"
            ],
            search_strategy="comprehensive",
            metadata={
                "fallback": True,
                "original_query": query
            }
        )
    
    async def refine_plan(self, 
                         plan: ResearchPlan,
                         initial_findings: List[str]) -> ResearchPlan:
        """
        Refine a research plan based on initial findings.
        
        This can be called after the first iteration to adjust
        the plan based on what's been discovered.
        
        Args:
            plan: Current research plan
            initial_findings: Early research findings
            
        Returns:
            Refined ResearchPlan
        """
        # For now, return the same plan
        # This could be enhanced to dynamically adjust based on findings
        return plan
