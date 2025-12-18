# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Context Pruning for TTD-DR.

This module implements the "Librarian" - a context management component that
extracts valuable facts from raw research notes and clears temporary buffers
to prevent context window overflow.

Reference: Fareed Khan's TTD-DR implementation
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Literal

from pydantic import BaseModel, Field as PydanticField
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI as LangChainChatOpenAI

logger = logging.getLogger(__name__)


# ========================================
# Pydantic Schemas for NVIDIA Guided JSON
# ========================================

class FactSchema(BaseModel):
    """Pydantic schema for a single extracted fact."""
    content: str = PydanticField(description="The atomic fact statement")
    source_title: Optional[str] = PydanticField(default=None, description="Source name if available")
    source_url: Optional[str] = PydanticField(default=None, description="URL if available")
    confidence_score: float = PydanticField(
        ge=0, le=1, default=0.7,
        description="Confidence in this fact (0-1)"
    )
    is_disputed: bool = PydanticField(default=False, description="Whether the fact is disputed")
    category: Literal["background", "current_state", "analysis", "data", "prediction", "general"] = PydanticField(
        default="general",
        description="Category of the fact"
    )


class FactExtractionOutputSchema(BaseModel):
    """Pydantic schema for fact extraction output."""
    extracted_facts: List[FactSchema] = PydanticField(
        default_factory=list,
        description="List of extracted facts"
    )
    notes_processed: bool = PydanticField(default=True, description="Whether notes were processed")
    summary: str = PydanticField(default="", description="Brief summary of what was extracted")


# ========================================
# Original Dataclasses (kept for compatibility)
# ========================================

@dataclass
class Fact:
    """
    Atomic unit of knowledge in the system.
    
    Represents a single, verified piece of information with
    source attribution and confidence scoring.
    """
    content: str
    source_url: Optional[str] = None
    source_title: Optional[str] = None
    confidence_score: float = 0.8
    is_disputed: bool = False
    category: str = "general"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "content": self.content,
            "source_url": self.source_url,
            "source_title": self.source_title,
            "confidence_score": self.confidence_score,
            "is_disputed": self.is_disputed,
            "category": self.category
        }


@dataclass
class KnowledgeBase:
    """
    Long-term structured memory for extracted facts.
    
    Unlike raw notes which are cleared each iteration,
    the knowledge base persists and grows.
    """
    facts: List[Fact] = field(default_factory=list)
    categories: Dict[str, List[int]] = field(default_factory=dict)  # category -> fact indices
    
    def add_fact(self, fact: Fact):
        """Add a fact and index by category."""
        idx = len(self.facts)
        self.facts.append(fact)
        
        if fact.category not in self.categories:
            self.categories[fact.category] = []
        self.categories[fact.category].append(idx)
    
    def get_facts_by_category(self, category: str) -> List[Fact]:
        """Get all facts in a category."""
        if category not in self.categories:
            return []
        return [self.facts[i] for i in self.categories[category]]
    
    def get_high_confidence_facts(self, threshold: float = 0.7) -> List[Fact]:
        """Get facts above confidence threshold."""
        return [f for f in self.facts if f.confidence_score >= threshold]
    
    def to_summary(self, max_facts: int = 20) -> str:
        """Generate a summary of key facts for context."""
        top_facts = sorted(self.facts, key=lambda f: f.confidence_score, reverse=True)[:max_facts]
        return "\n".join([f"- {f.content}" for f in top_facts])
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "facts": [f.to_dict() for f in self.facts],
            "categories": self.categories,
            "total_facts": len(self.facts)
        }


FACT_EXTRACTION_PROMPT = """You are a knowledge extraction specialist (the "Librarian"). Your job is to extract ATOMIC, VALUABLE facts from raw research notes.

## Research Context
Topic: {topic}

## Raw Research Notes to Process
{raw_notes}

## Your Task

Extract the most valuable, atomic facts from these notes. Each fact should be:
1. **Atomic**: A single piece of information, not compound statements
2. **Verifiable**: Something that could be fact-checked
3. **Valuable**: Contributes meaningful information to the research
4. **Attributed**: Include source if mentioned in the notes

Categorize facts into:
- "background": Context and foundational information
- "current_state": Recent developments, current status
- "analysis": Insights, interpretations, expert opinions
- "data": Statistics, numbers, quantitative information
- "prediction": Future outlook, trends
- "general": Other valuable information

Be selective. Quality over quantity. Only extract facts that would be useful in the final report.
"""


class ContextPruner:
    """
    Context pruning agent (the "Librarian").
    
    Manages the two-tiered memory system:
    - Temporary scratchpad (raw_notes): Cleared each iteration
    - Permanent knowledge base: Extracted facts persist
    
    This prevents context window overflow while preserving valuable information.
    
    Uses NVIDIA NIM guided_json for guaranteed structured output.
    """
    
    def __init__(self, llm: BaseChatModel, max_context_tokens: int = 8000):
        """
        Initialize Context Pruner.
        
        Args:
            llm: Language model for fact extraction
            max_context_tokens: Maximum context size to maintain
        """
        self.llm = llm
        self.max_context_tokens = max_context_tokens
        self.knowledge_base = KnowledgeBase()
        self.logger = logging.getLogger(f"{__name__}.ContextPruner")
        
        # Tracking metrics
        self.total_notes_processed = 0
        self.total_facts_extracted = 0
        self.bytes_saved = 0
        
        # Extract LLM config for guided_json
        self._base_url = getattr(llm, 'openai_api_base', None) or getattr(llm, 'base_url', None)
        if self._base_url and hasattr(self._base_url, '__str__'):
            self._base_url = str(self._base_url)
        self._model_name = getattr(llm, 'model_name', "nvidia/llama-3.1-nemotron-nano-8b-v1")
    
    def _create_guided_llm(self) -> LangChainChatOpenAI:
        """Create LLM with NVIDIA guided_json for structured output."""
        json_schema = FactExtractionOutputSchema.model_json_schema()
        
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
    
    async def process_raw_notes(self,
                               raw_notes: str,
                               topic: str,
                               iteration: int = 0) -> Dict[str, Any]:
        """
        Process raw notes, extract facts, and clear the buffer.
        
        This is the core pruning operation that:
        1. Extracts valuable facts into the knowledge base
        2. Returns a pruned state update
        
        Args:
            raw_notes: Raw unstructured research notes
            topic: The research topic for context
            iteration: Current iteration number
            
        Returns:
            State update dict with extracted facts and cleared raw_notes
        """
        if not raw_notes or len(raw_notes.strip()) < 50:
            self.logger.info(f"📚 Librarian: No substantial notes to process (iteration {iteration})")
            return {
                "raw_notes": "",  # Clear the buffer
                "facts_extracted": 0
            }
        
        self.logger.info(f"📚 Librarian processing {len(raw_notes)} chars of notes (iteration {iteration})...")
        original_size = len(raw_notes)
        
        prompt = FACT_EXTRACTION_PROMPT.format(
            topic=topic[:500],
            raw_notes=raw_notes[:10000]  # Limit input
        )
        
        try:
            # Use guided_json for guaranteed structured output
            guided_llm = self._create_guided_llm()
            
            response = await guided_llm.ainvoke([
                SystemMessage(content="You are a knowledge extraction specialist."),
                HumanMessage(content=prompt)
            ])
            
            # Parse with Pydantic (guaranteed valid from guided_json)
            result_data = FactExtractionOutputSchema.model_validate_json(response.content)
            
            # Extract facts into knowledge base
            facts_extracted = 0
            fact_contents = []  # Return fact strings for use in denoising
            for fact_schema in result_data.extracted_facts:
                fact = Fact(
                    content=fact_schema.content,
                    source_url=fact_schema.source_url,
                    source_title=fact_schema.source_title,
                    confidence_score=fact_schema.confidence_score,
                    is_disputed=fact_schema.is_disputed,
                    category=fact_schema.category
                )
                self.knowledge_base.add_fact(fact)
                facts_extracted += 1
                # Store content string for immediate use
                fact_contents.append(fact.content)
            
            # Update metrics
            self.total_notes_processed += 1
            self.total_facts_extracted += facts_extracted
            self.bytes_saved += original_size
            
            self.logger.info(
                f"📚 Librarian extracted {facts_extracted} facts, "
                f"knowledge base now has {len(self.knowledge_base.facts)} facts"
            )
            
            return {
                "raw_notes": "",  # Clear the buffer - THIS IS KEY
                "facts_extracted": facts_extracted,
                "facts": fact_contents,  # Return facts for immediate use in denoising
                "knowledge_base_size": len(self.knowledge_base.facts)
            }
            
        except Exception as e:
            self.logger.error(f"Context pruning failed: {e}")
            # Still clear the buffer to prevent overflow
            return {
                "raw_notes": "",
                "facts_extracted": 0,
                "error": str(e)
            }
    
    def get_context_summary(self, max_facts: int = 15) -> str:
        """
        Get a compressed summary of accumulated knowledge.
        
        Used to inject condensed knowledge into prompts.
        """
        return self.knowledge_base.to_summary(max_facts)
    
    def get_facts_for_synthesis(self) -> List[Dict[str, Any]]:
        """Get all high-confidence facts for final synthesis."""
        high_conf = self.knowledge_base.get_high_confidence_facts(0.6)
        return [f.to_dict() for f in high_conf]
    
    def estimate_context_usage(self) -> Dict[str, Any]:
        """Estimate current context usage."""
        facts_text = self.get_context_summary(max_facts=100)
        estimated_tokens = len(facts_text) // 4  # Rough estimate
        
        return {
            "estimated_tokens": estimated_tokens,
            "max_tokens": self.max_context_tokens,
            "usage_percentage": (estimated_tokens / self.max_context_tokens) * 100,
            "total_facts": len(self.knowledge_base.facts),
            "bytes_saved": self.bytes_saved
        }
    
    def reset(self):
        """Reset for new research session."""
        self.knowledge_base = KnowledgeBase()
        self.total_notes_processed = 0
        self.total_facts_extracted = 0
        self.bytes_saved = 0
