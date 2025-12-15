# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Prompts for TTD-DR (Test-Time Diffusion Deep Researcher).

This module contains all the prompt templates used in the TTD-DR pipeline.
Based on Google Research's "Deep researcher with test-time diffusion" approach.
"""

# Stage 1: Research Plan Generation
RESEARCH_PLAN_PROMPT = """You are a research planning expert. Given a user query, create a comprehensive research plan.

User Query: {query}

Generate a structured research plan that includes:

1. Main Topic: A clear statement of the primary research focus
2. Key Areas: 3-5 major areas that need investigation
3. Sub-questions: 5-8 specific questions to answer
4. Expected Sections: The sections that should appear in the final report
5. Search Strategy: How to approach finding information

Format your response as JSON:
{{
    "main_topic": "...",
    "key_areas": ["area1", "area2", ...],
    "sub_questions": ["q1", "q2", ...],
    "expected_sections": ["Introduction", "Section 1", ...],
    "search_strategy": "..."
}}

Be comprehensive but focused. The plan should guide an iterative research process."""

# Initial Draft Generation
INITIAL_DRAFT_PROMPT = """Create an initial draft report based on the research plan. This is a "noisy" starting point that will be refined.

Research Plan:
{research_plan}

User Query: {query}

IMPORTANT: The draft should address this specific query: {query}
Use the actual topic throughout, do NOT use placeholders like [topic] or [Research Topic].

Write a preliminary draft that:
1. Directly addresses: {query}
2. Covers all expected sections from the plan
3. Uses [NEEDS RESEARCH] only for missing specific data
4. Marks uncertain claims with [UNVERIFIED]
5. Uses the ACTUAL topic from the query, not generic placeholders

This draft will be iteratively refined with real information. Make it specific to the query from the start.

Draft Report:"""

# Stage 2a: Question Generation from Draft
QUESTION_GENERATION_PROMPT = """Analyze the current draft and generate targeted search questions to improve it.

Current Draft:
{draft}

Research Plan:
{plan}

Previous Questions Asked:
{previous_questions}

Iteration: {iteration}

Identify gaps, uncertainties, and areas needing verification in the draft. Generate {num_questions} specific search questions that will most improve the draft quality.

Consider:
1. Information marked as [NEEDS RESEARCH]
2. Claims marked as [UNVERIFIED]
3. Sections that are too brief or vague
4. Missing evidence or examples
5. Contradictions or unclear points

Format as JSON:
{{
    "questions": [
        {{"question": "...", "purpose": "...", "priority": "high/medium/low"}},
        ...
    ],
    "gaps_identified": ["gap1", "gap2", ...]
}}"""

# Stage 2b: Answer Synthesis (after search)
ANSWER_SYNTHESIS_PROMPT = """Synthesize the search results into a comprehensive answer.

Question: {question}

Search Results:
{search_results}

Provide a detailed answer that:
1. Directly addresses the question
2. Integrates information from multiple sources
3. Notes any contradictions or uncertainties
4. Includes specific facts, numbers, or examples when available

Answer:"""

# Denoising Prompt - Core of TTD-DR
DENOISING_PROMPT = """Revise and improve the draft by incorporating new information (denoising step).

Current Draft:
{current_draft}

New Information:
{new_information}

Research Plan:
{research_plan}

Iteration: {iteration}
Current Convergence: {convergence_score}%

Task: Perform a denoising iteration by:

1. **Incorporate New Information**: Add the newly retrieved facts into relevant sections
2. **Verify Claims**: Replace [UNVERIFIED] markers with confirmed information
3. **Fill Gaps**: Replace [NEEDS RESEARCH] with actual content
4. **Improve Coherence**: Enhance flow between paragraphs and sections
5. **Maintain Consistency**: Ensure alignment with the research plan
6. **Remove Noise**: Eliminate speculation and replace with facts

Quality Guidelines:
- Prefer specific facts over generalizations
- Maintain academic/professional tone
- Ensure logical progression of ideas
- Keep focus on the main topic

Output the revised draft with clear improvements. Mark any remaining uncertainties.

Revised Draft:"""

# Self-Evolution: Variant Generation
VARIANT_GENERATION_PROMPT = """Generate {num_variants} alternative versions of this answer to explore different approaches.

Original Answer:
{original_answer}

Create {num_variants} variants that:
1. Maintain factual accuracy
2. Explore different emphasis or structure
3. Vary in detail level or examples used
4. Might include different supporting evidence

Variant {variant_number}:"""

# Self-Evolution: Feedback (LLM-as-Judge)
EVOLUTION_FEEDBACK_PROMPT = """Evaluate this answer variant as an expert judge.

Answer:
{answer}

Original Question:
{question}

Evaluate on these criteria (1-10 scale):
1. **Completeness**: Does it fully address the question?
2. **Accuracy**: Are the facts correct and verifiable?
3. **Clarity**: Is it well-written and easy to understand?
4. **Relevance**: Does it stay focused on the topic?
5. **Depth**: Does it provide sufficient detail?

Provide:
1. Scores for each criterion
2. Overall fitness score (average)
3. Specific strengths
4. Specific weaknesses
5. Suggestions for improvement

Format as JSON:
{{
    "scores": {{
        "completeness": 0-10,
        "accuracy": 0-10,
        "clarity": 0-10,
        "relevance": 0-10,
        "depth": 0-10
    }},
    "fitness_score": 0-10,
    "strengths": ["..."],
    "weaknesses": ["..."],
    "suggestions": ["..."]
}}"""

# Self-Evolution: Revision Based on Feedback
EVOLUTION_REVISION_PROMPT = """Revise this answer based on the feedback received.

Original Answer:
{answer}

Feedback:
{feedback}

Revise the answer to:
1. Address the identified weaknesses
2. Implement the suggested improvements
3. Maintain the identified strengths
4. Improve the overall fitness score

Revised Answer:"""

# Self-Evolution: Crossover (Merge Best Variants)
VARIANT_CROSSOVER_PROMPT = """Merge the best aspects of these answer variants into a superior combined version.

Variants with Fitness Scores:
{variants_with_scores}

Create a merged answer that:
1. Combines the strongest points from each variant
2. Eliminates redundancies
3. Maintains coherent flow
4. Maximizes information quality

Merged Answer:"""

# Convergence Check
CONVERGENCE_CHECK_PROMPT = """Assess the convergence between two draft versions.

Previous Draft:
{previous_draft}

Current Draft:
{current_draft}

Evaluate:
1. Information completeness (0-100%)
2. Factual accuracy improvement (0-100%)
3. Structural coherence (0-100%)
4. Gap resolution rate (0-100%)
5. Overall quality improvement (0-100%)

Also identify:
- Remaining gaps or uncertainties
- Areas still needing research
- Quality of improvements made

Format as JSON:
{{
    "scores": {{
        "completeness": 0-100,
        "accuracy_improvement": 0-100,
        "coherence": 0-100,
        "gap_resolution": 0-100,
        "overall_improvement": 0-100
    }},
    "convergence_score": 0-100,
    "remaining_gaps": ["..."],
    "improvements_made": ["..."],
    "continue_iterating": true/false
}}"""

# Stage 3: Final Report Synthesis
FINAL_REPORT_SYNTHESIS_PROMPT = """CRITICAL INSTRUCTION: Generate a report about "{query}".

BANNED: Do NOT use any of these placeholders: [topic], [Report Title], [Question], [Research Topic], [Name], [Date], or any brackets with generic text.

REQUIRED: Use the ACTUAL topic "{query}" throughout the report.

Source Material:
{draft}

Search Summary: {search_summary}
Iterations: {iterations}, Convergence: {convergence}%

Write a polished, final report that:

1. TITLE: Create a specific title about "{query}" (NOT "[Report Title]")
2. INTRODUCTION: Open with what this report covers about "{query}"
3. BODY: Include actual findings about "{query}" from the source material
4. CONCLUSION: Summarize key findings about "{query}"

REMEMBER: The topic is "{query}". Replace ALL placeholders with actual content.

Begin the report now:
Remember: Use the ACTUAL topic "{query}" throughout, never use generic [topic] placeholders.

Final Report:"""

# Error Recovery Prompts
PARTIAL_RESULT_RECOVERY_PROMPT = """The research process was interrupted. Generate a report from partial results.

Completed Iterations: {iterations}
Current Draft:
{draft}

Information Gathered:
{search_history}

Create the best possible report from the available information, noting any limitations or gaps.

Report:"""

# Quality Assessment
QUALITY_ASSESSMENT_PROMPT = """Assess the quality of this research report.

Report:
{report}

Original Query:
{query}

Evaluate:
1. Query Coverage: Does it answer the original question? (0-100)
2. Factual Accuracy: Are claims supported by evidence? (0-100)
3. Completeness: Are all important aspects covered? (0-100)
4. Organization: Is it well-structured and logical? (0-100)
5. Clarity: Is it easy to read and understand? (0-100)

Overall Quality Score: (0-100)

Provide brief justification for each score."""
