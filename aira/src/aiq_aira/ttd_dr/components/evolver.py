# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Self-Evolution component for TTD-DR.

Implements component-wise optimization via self-evolution, where multiple
variants are generated, evaluated, revised, and merged to produce superior results.
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Tuple

from pydantic import BaseModel, Field as PydanticField
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI as LangChainChatOpenAI

from ..models import TTDDRConfig, EvolutionVariant
from ..prompts import (
    VARIANT_GENERATION_PROMPT,
    EVOLUTION_FEEDBACK_PROMPT,
    EVOLUTION_REVISION_PROMPT,
    VARIANT_CROSSOVER_PROMPT
)

logger = logging.getLogger(__name__)


# ========================================
# Pydantic Schemas for NVIDIA Guided JSON
# ========================================

class ScoresSchema(BaseModel):
    """Schema for individual evaluation scores."""
    completeness: float = PydanticField(ge=0, le=10, description="Completeness score (0-10)")
    accuracy: float = PydanticField(ge=0, le=10, description="Accuracy score (0-10)")
    clarity: float = PydanticField(ge=0, le=10, description="Clarity score (0-10)")
    relevance: float = PydanticField(ge=0, le=10, description="Relevance score (0-10)")
    depth: float = PydanticField(ge=0, le=10, description="Depth score (0-10)")


class EvolutionFeedbackSchema(BaseModel):
    """Schema for evolution feedback output."""
    scores: ScoresSchema = PydanticField(description="Individual evaluation scores")
    strengths: List[str] = PydanticField(
        default_factory=list,
        description="List of answer strengths"
    )
    weaknesses: List[str] = PydanticField(
        default_factory=list,
        description="List of answer weaknesses"
    )
    suggestions: List[str] = PydanticField(
        default_factory=list,
        description="List of improvement suggestions"
    )


class SelfEvolver:
    """
    Implements self-evolution for answer improvement.
    
    Based on Google's component-wise optimization approach:
    1. Generate multiple variants of an answer
    2. Evaluate each variant (LLM-as-judge)
    3. Revise based on feedback
    4. Crossover best aspects into final answer
    
    This improves answer quality by exploring different approaches
    and combining the best elements.
    """
    
    def __init__(self,
                 llm: BaseChatModel,
                 config: TTDDRConfig,
                 judge_llm: Optional[BaseChatModel] = None):
        """
        Initialize the self-evolver.
        
        Args:
            llm: Language model for generation and revision
            config: TTD-DR configuration
            judge_llm: Optional separate LLM for judging (defaults to llm)
        """
        self.llm = llm
        self.judge_llm = judge_llm or llm
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Extract LLM config for guided_json (use judge_llm for feedback)
        judge = self.judge_llm
        self._base_url = getattr(judge, 'openai_api_base', None) or getattr(judge, 'base_url', None)
        if self._base_url and hasattr(self._base_url, '__str__'):
            self._base_url = str(self._base_url)
        self._model_name = getattr(judge, 'model_name', "nvidia/llama-3.1-nemotron-nano-8b-v1")
    
    def _create_guided_llm_for_feedback(self) -> LangChainChatOpenAI:
        """Create LLM with NVIDIA guided_json for evolution feedback."""
        json_schema = EvolutionFeedbackSchema.model_json_schema()
        
        return LangChainChatOpenAI(
            base_url=self._base_url,
            model=self._model_name,
            api_key="not-used",
            model_kwargs={
                "extra_body": {
                    "nvext": {"guided_json": json_schema}  # NVIDIA NIM v1.12.0 format
                }
            }
        )
    
    async def evolve_answer(self,
                          original_answer: str,
                          sources: List[Dict[str, Any]],
                          question: Optional[str] = None) -> str:
        """
        Evolve an answer through variant generation and selection.
        
        Args:
            original_answer: Initial answer to evolve
            sources: Source documents used
            question: Original question (for context)
            
        Returns:
            Evolved answer incorporating best aspects
        """
        self.logger.info(f"Starting self-evolution with {self.config.num_variants} variants")
        
        # Generate variants
        variants = await self._generate_variants(
            original_answer,
            self.config.num_variants
        )
        
        # Add original as a variant too
        variants.insert(0, EvolutionVariant(
            content=original_answer,
            fitness_score=0.0,
            feedback={},
            revision_count=0
        ))
        
        # Evolution rounds
        for round_num in range(self.config.evolution_rounds):
            self.logger.info(f"Evolution round {round_num + 1}/{self.config.evolution_rounds}")
            
            # Evaluate and revise each variant
            evolved_variants = []
            for variant in variants:
                evolved = await self._evolve_single_variant(
                    variant,
                    question or "Research question",
                    round_num
                )
                evolved_variants.append(evolved)
            
            variants = evolved_variants
        
        # Select and merge best variants
        final_answer = await self._crossover_variants(variants, question)
        
        self.logger.info(f"Evolution complete. Original length: {len(original_answer)}, "
                        f"Final length: {len(final_answer)}")
        
        return final_answer
    
    async def _generate_variants(self,
                                original_answer: str,
                                num_variants: int) -> List[EvolutionVariant]:
        """
        Generate variant versions of an answer.
        
        Args:
            original_answer: Original answer text
            num_variants: Number of variants to generate
            
        Returns:
            List of answer variants
        """
        self.logger.info(f"Generating {num_variants} variants")
        
        variants = []
        
        # Generate variants in parallel
        tasks = []
        for i in range(num_variants):
            tasks.append(self._generate_single_variant(original_answer, i + 1))
        
        variant_contents = await asyncio.gather(*tasks)
        
        for content in variant_contents:
            variants.append(EvolutionVariant(
                content=content,
                fitness_score=0.0,
                feedback={},
                revision_count=0
            ))
        
        return variants
    
    async def _generate_single_variant(self,
                                      original_answer: str,
                                      variant_number: int) -> str:
        """
        Generate a single variant of an answer.
        
        Args:
            original_answer: Original answer
            variant_number: Variant number (for diversity)
            
        Returns:
            Variant content
        """
        # Different strategies for different variants
        if variant_number == 1:
            instruction = "Create a more detailed and comprehensive version."
        elif variant_number == 2:
            instruction = "Create a more concise and focused version."
        elif variant_number == 3:
            instruction = "Create a version with more examples and evidence."
        else:
            instruction = "Create an alternative version with different emphasis."
        
        prompt = f"""{instruction}

Original Answer:
{original_answer}

Variant {variant_number}:"""
        
        try:
            response = await self.llm.ainvoke([
                SystemMessage(content=f"""You are creating variant {variant_number} of an answer.
                {instruction}
                Maintain factual accuracy while exploring different presentation approaches."""),
                HumanMessage(content=prompt)
            ])
            
            return response.content
            
        except Exception as e:
            self.logger.error(f"Failed to generate variant {variant_number}: {e}")
            # Return original with minor modification
            return f"[Variant {variant_number}] {original_answer}"
    
    async def _evolve_single_variant(self,
                                    variant: EvolutionVariant,
                                    question: str,
                                    round_num: int) -> EvolutionVariant:
        """
        Evolve a single variant through feedback and revision.
        
        Args:
            variant: Variant to evolve
            question: Original question
            round_num: Current evolution round
            
        Returns:
            Evolved variant
        """
        # Step 1: Get feedback
        feedback = await self._get_feedback(variant.content, question)
        
        # Step 2: Revise based on feedback
        if feedback["fitness_score"] < 0.9:  # Only revise if not already excellent
            revised_content = await self._revise_variant(
                variant.content,
                feedback
            )
        else:
            revised_content = variant.content
        
        # Create evolved variant
        return EvolutionVariant(
            content=revised_content,
            fitness_score=feedback["fitness_score"],
            feedback=feedback,
            revision_count=variant.revision_count + 1,
            parent_id=str(id(variant))
        )
    
    async def _get_feedback(self,
                           answer: str,
                           question: str) -> Dict[str, Any]:
        """
        Get feedback on an answer variant (LLM-as-judge).
        
        Args:
            answer: Answer to evaluate
            question: Original question
            
        Returns:
            Feedback dictionary with scores and suggestions
        """
        prompt = EVOLUTION_FEEDBACK_PROMPT.format(
            answer=answer,
            question=question
        )
        
        try:
            # Use guided_json for guaranteed structured output
            guided_llm = self._create_guided_llm_for_feedback()
            
            response = await guided_llm.ainvoke([
                SystemMessage(content="""You are an expert judge evaluating answer quality.
                Provide objective, constructive feedback."""),
                HumanMessage(content=prompt)
            ])
            
            # Parse with Pydantic (guaranteed valid from guided_json)
            result = EvolutionFeedbackSchema.model_validate_json(response.content)
            
            # Convert to dictionary and calculate fitness score
            scores = result.scores.model_dump()
            total = sum(scores.values())
            count = len(scores)
            fitness_score = total / (count * 10)  # Normalize to 0-1
            
            return {
                "scores": scores,
                "fitness_score": fitness_score,
                "strengths": result.strengths or ["Good attempt"],
                "weaknesses": result.weaknesses or ["Room for improvement"],
                "suggestions": result.suggestions or ["Continue refining"]
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get feedback: {e}")
            # Return default feedback
            return {
                "scores": {
                    "completeness": 5,
                    "accuracy": 5,
                    "clarity": 5,
                    "relevance": 5,
                    "depth": 5
                },
                "fitness_score": 0.5,
                "strengths": ["Attempt made"],
                "weaknesses": ["Evaluation failed"],
                "suggestions": ["Maintain current approach"]
            }
    
    async def _revise_variant(self,
                             content: str,
                             feedback: Dict[str, Any]) -> str:
        """
        Revise a variant based on feedback.
        
        Args:
            content: Current content
            feedback: Feedback to address
            
        Returns:
            Revised content
        """
        # Format feedback for prompt
        feedback_text = f"""Fitness Score: {feedback['fitness_score']:.1f}/10

Strengths:
{chr(10).join('- ' + s for s in feedback['strengths'])}

Weaknesses:
{chr(10).join('- ' + w for w in feedback['weaknesses'])}

Suggestions:
{chr(10).join('- ' + s for s in feedback['suggestions'])}"""
        
        prompt = EVOLUTION_REVISION_PROMPT.format(
            answer=content,
            feedback=feedback_text
        )
        
        try:
            response = await self.llm.ainvoke([
                SystemMessage(content="""You are revising an answer based on expert feedback.
                Address the weaknesses while maintaining the strengths.
                Implement the suggested improvements."""),
                HumanMessage(content=prompt)
            ])
            
            return response.content
            
        except Exception as e:
            self.logger.error(f"Failed to revise variant: {e}")
            return content  # Return original if revision fails
    
    async def _crossover_variants(self,
                                 variants: List[EvolutionVariant],
                                 question: Optional[str]) -> str:
        """
        Merge the best aspects of multiple variants.
        
        Args:
            variants: List of evolved variants
            question: Original question for context
            
        Returns:
            Final merged answer
        """
        # Sort variants by fitness score
        sorted_variants = sorted(variants, key=lambda v: v.fitness_score, reverse=True)
        
        # Select top variants for crossover
        top_variants = sorted_variants[:min(3, len(sorted_variants))]
        
        self.logger.info(f"Crossover: Merging top {len(top_variants)} variants with scores: " +
                        str([v.fitness_score for v in top_variants]))
        
        # If the best variant is excellent, just return it
        if top_variants[0].fitness_score >= 0.95:
            return top_variants[0].content
        
        # Prepare variants for crossover
        variants_text = []
        for i, variant in enumerate(top_variants, 1):
            variants_text.append(
                f"Variant {i} (Score: {variant.fitness_score:.1f}/10):\n"
                f"{variant.content}\n"
                f"Strengths: {', '.join(variant.feedback.get('strengths', ['N/A']))}"
            )
        
        variants_with_scores = "\n\n---\n\n".join(variants_text)
        
        prompt = VARIANT_CROSSOVER_PROMPT.format(
            variants_with_scores=variants_with_scores
        )
        
        try:
            response = await self.llm.ainvoke([
                SystemMessage(content="""You are merging the best aspects of multiple answer variants.
                Create a superior answer that combines the strengths of each variant.
                Eliminate redundancies and ensure coherent flow."""),
                HumanMessage(content=prompt)
            ])
            
            return response.content
            
        except Exception as e:
            self.logger.error(f"Crossover failed: {e}")
            # Return best variant as fallback
            return top_variants[0].content
    
    def _parse_feedback_response(self, response: str) -> Dict[str, Any]:
        """
        Parse the feedback response from LLM.
        
        Args:
            response: Raw LLM response
            
        Returns:
            Parsed feedback dictionary
        """
        try:
            # Try to parse as JSON
            if "```json" in response:
                json_start = response.index("```json") + 7
                json_end = response.index("```", json_start)
                json_str = response[json_start:json_end].strip()
                feedback = json.loads(json_str)
            else:
                feedback = json.loads(response)
            
            # Normalize fitness score
            if "fitness_score" not in feedback and "scores" in feedback:
                scores = feedback["scores"]
                total = sum(scores.values())
                count = len(scores)
                feedback["fitness_score"] = total / (count * 10)  # Normalize to 0-1
            else:
                feedback["fitness_score"] = feedback.get("fitness_score", 5) / 10
            
            # Ensure required fields
            feedback.setdefault("strengths", ["Good attempt"])
            feedback.setdefault("weaknesses", ["Room for improvement"])
            feedback.setdefault("suggestions", ["Continue refining"])
            
            return feedback
            
        except (json.JSONDecodeError, ValueError) as e:
            self.logger.warning(f"Failed to parse feedback: {e}")
            # Return basic feedback
            return {
                "scores": {
                    "completeness": 5,
                    "accuracy": 5,
                    "clarity": 5,
                    "relevance": 5,
                    "depth": 5
                },
                "fitness_score": 0.5,
                "strengths": ["Content provided"],
                "weaknesses": ["Feedback parsing failed"],
                "suggestions": ["Maintain approach"]
            }
    
    async def evolve_multiple_answers(self,
                                     answers: List[str],
                                     questions: List[str]) -> List[str]:
        """
        Evolve multiple answers in parallel.
        
        Args:
            answers: List of answers to evolve
            questions: Corresponding questions
            
        Returns:
            List of evolved answers
        """
        self.logger.info(f"Evolving {len(answers)} answers in parallel")
        
        # Create evolution tasks
        tasks = []
        for answer, question in zip(answers, questions):
            tasks.append(self.evolve_answer(answer, [], question))
        
        # Execute in parallel
        evolved_answers = await asyncio.gather(*tasks)
        
        return evolved_answers
