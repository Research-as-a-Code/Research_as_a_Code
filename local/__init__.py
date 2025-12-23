# SPDX-FileCopyrightText: Copyright (c) 2025 Research_as_a_Code Project
# SPDX-License-Identifier: Apache-2.0

"""
Local deployment module for AI-Q Research Assistant.

This module provides configuration and utilities for running AI-Q locally
with Ollama, Milvus Lite, and other local inference solutions.
"""

from .config import (
    LocalConfig,
    get_config,
    reset_config,
    is_local_mode,
    MODEL_PRESETS,
    InferenceBackend,
    VectorDBBackend,
)

from .milvus_helper import (
    is_milvus_lite_mode,
    has_collection,
    search_collection,
    create_collection,
    insert_documents,
    list_collections,
    get_collection_stats,
    milvus_connection,
)

__all__ = [
    # Config
    "LocalConfig",
    "get_config",
    "reset_config",
    "is_local_mode",
    "MODEL_PRESETS",
    "InferenceBackend",
    "VectorDBBackend",
    # Milvus
    "is_milvus_lite_mode",
    "has_collection",
    "search_collection",
    "create_collection",
    "insert_documents",
    "list_collections",
    "get_collection_stats",
    "milvus_connection",
]

