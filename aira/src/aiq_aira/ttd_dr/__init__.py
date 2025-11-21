# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
TTD-DR (Test-Time Diffusion Deep Researcher) Package.

Implementation of Google's test-time diffusion approach for research.
"""

from .core import TTDDRIntegration
from .models import (
    TTDDRConfig,
    TTDDRState,
    TTDDRStage,
    TTDDRMetrics,
    ResearchPlan,
    DraftState,
    SearchQAPair
)

__all__ = [
    "TTDDRIntegration",
    "TTDDRConfig",
    "TTDDRState",
    "TTDDRStage", 
    "TTDDRMetrics",
    "ResearchPlan",
    "DraftState",
    "SearchQAPair"
]
