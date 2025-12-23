# SPDX-FileCopyrightText: Copyright (c) 2025 Research_as_a_Code Project
# SPDX-License-Identifier: Apache-2.0

"""
Local Configuration Module for AI-Q Research Assistant

This module provides configurable model presets and settings for running
the AI-Q system locally with Ollama, vLLM, SGLang, or other inference backends.
"""

import os
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from enum import Enum


class InferenceBackend(Enum):
    """Supported inference backends."""
    OLLAMA = "ollama"
    VLLM = "vllm"
    SGLANG = "sglang"
    TENSORRT_LLM = "tensorrt_llm"
    NVIDIA_NIM = "nvidia_nim"


class VectorDBBackend(Enum):
    """Supported vector database backends."""
    MILVUS_LITE = "milvus_lite"
    MILVUS_STANDALONE = "milvus_standalone"
    CHROMADB = "chromadb"
    PGVECTOR = "pgvector"


# Model presets for different GPU configurations
MODEL_PRESETS: Dict[str, Dict[str, str]] = {
    # Workstation GPUs
    "workstation_large": {  # A5000/A6000 (24-48GB VRAM)
        "llm": "llama3.1:8b-instruct-q8_0",
        "embedding": "nomic-embed-text",
        "description": "Full precision 8B model for high-end workstations",
    },
    "workstation_xlarge": {  # A6000 (48GB VRAM)
        "llm": "llama3.1:70b-instruct-q4_K_M",
        "embedding": "nomic-embed-text",
        "description": "70B model quantized for A6000",
    },
    "workstation_medium": {  # A4000 (16GB VRAM)
        "llm": "qwen2.5:7b-instruct-q4_K_M",
        "embedding": "mxbai-embed-large",
        "description": "Efficient 7B model for 16GB GPUs",
    },
    
    # Consumer GPUs
    "consumer_high": {  # RTX 4090/3090 (24GB VRAM)
        "llm": "llama3.1:8b-instruct-q6_K",
        "embedding": "nomic-embed-text",
        "description": "High quality 8B for consumer cards",
    },
    "consumer_mid": {  # RTX 4070/3070 (8-12GB VRAM)
        "llm": "llama3.2:3b-instruct-q8_0",
        "embedding": "nomic-embed-text",
        "description": "Compact 3B model for mid-range GPUs",
    },
    "consumer_low": {  # RTX 3060/4060 (8GB VRAM)
        "llm": "qwen2.5:3b-instruct-q4_K_M",
        "embedding": "all-minilm:l6-v2",
        "description": "Minimal footprint for 8GB GPUs",
    },
    
    # CPU-only fallback
    "cpu_only": {
        "llm": "llama3.2:1b-instruct-q4_K_M",
        "embedding": "all-minilm:l6-v2",
        "description": "CPU-only inference (slow but works)",
    },
}


@dataclass
class LocalConfig:
    """
    Configuration for local AI-Q deployment.
    
    All settings can be overridden via environment variables.
    """
    
    # Inference Backend
    inference_backend: InferenceBackend = field(
        default_factory=lambda: InferenceBackend(
            os.getenv("INFERENCE_BACKEND", "ollama")
        )
    )
    
    # LLM Configuration
    llm_base_url: str = field(
        default_factory=lambda: os.getenv(
            "LLM_BASE_URL", "http://localhost:11434/v1"
        )
    )
    llm_model: str = field(
        default_factory=lambda: os.getenv(
            "LLM_MODEL", "llama3.1:8b-instruct-q8_0"
        )
    )
    
    # Embedding Configuration
    embedding_base_url: str = field(
        default_factory=lambda: os.getenv(
            "EMBEDDING_BASE_URL", "http://localhost:11434/v1"
        )
    )
    embedding_model: str = field(
        default_factory=lambda: os.getenv(
            "EMBEDDING_MODEL", "nomic-embed-text"
        )
    )
    
    # Vector Database Configuration
    vector_db_backend: VectorDBBackend = field(
        default_factory=lambda: VectorDBBackend(
            os.getenv("VECTOR_DB_BACKEND", "milvus_lite")
        )
    )
    milvus_lite_path: str = field(
        default_factory=lambda: os.getenv(
            "MILVUS_DATA_PATH", "./data/milvus/milvus.db"
        )
    )
    milvus_host: str = field(
        default_factory=lambda: os.getenv(
            "MILVUS_HOST", "localhost"
        )
    )
    milvus_port: int = field(
        default_factory=lambda: int(os.getenv("MILVUS_PORT", "19530"))
    )
    
    # Web Search (optional)
    tavily_api_key: Optional[str] = field(
        default_factory=lambda: os.getenv("TAVILY_API_KEY")
    )
    
    # Model Parameters
    llm_temperature: float = field(
        default_factory=lambda: float(os.getenv("LLM_TEMPERATURE", "0.7"))
    )
    llm_max_tokens: int = field(
        default_factory=lambda: int(os.getenv("LLM_MAX_TOKENS", "4096"))
    )
    
    # Embedding dimension (model-dependent)
    embedding_dimension: int = field(
        default_factory=lambda: int(os.getenv("EMBEDDING_DIMENSION", "768"))
    )
    
    @classmethod
    def from_preset(cls, preset_name: str) -> "LocalConfig":
        """
        Create a configuration from a preset name.
        
        Args:
            preset_name: Name of the preset (e.g., "workstation_large")
            
        Returns:
            LocalConfig instance with preset values
        """
        if preset_name not in MODEL_PRESETS:
            available = ", ".join(MODEL_PRESETS.keys())
            raise ValueError(
                f"Unknown preset '{preset_name}'. Available: {available}"
            )
        
        preset = MODEL_PRESETS[preset_name]
        return cls(
            llm_model=preset["llm"],
            embedding_model=preset["embedding"],
        )
    
    @property
    def is_milvus_lite(self) -> bool:
        """Check if using Milvus Lite (in-process) mode."""
        return self.vector_db_backend == VectorDBBackend.MILVUS_LITE
    
    @property
    def is_ollama(self) -> bool:
        """Check if using Ollama as inference backend."""
        return self.inference_backend == InferenceBackend.OLLAMA
    
    def get_embedding_dimension(self) -> int:
        """
        Get the embedding dimension for the configured model.
        
        Common dimensions:
        - nomic-embed-text: 768
        - mxbai-embed-large: 1024
        - all-minilm: 384
        - snowflake/arctic-embed-l: 1024
        """
        dimension_map = {
            "nomic-embed-text": 768,
            "mxbai-embed-large": 1024,
            "all-minilm:l6-v2": 384,
            "snowflake/arctic-embed-l": 1024,
        }
        return dimension_map.get(self.embedding_model, self.embedding_dimension)


# Global config instance (lazy-loaded)
_config: Optional[LocalConfig] = None


def get_config() -> LocalConfig:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        preset = os.getenv("MODEL_PRESET")
        if preset:
            _config = LocalConfig.from_preset(preset)
        else:
            _config = LocalConfig()
    return _config


def reset_config() -> None:
    """Reset the global configuration (useful for testing)."""
    global _config
    _config = None


# Convenience function for checking local mode
def is_local_mode() -> bool:
    """
    Check if running in local mode (vs cloud/Kubernetes).
    
    Local mode is indicated by:
    - MILVUS_LITE=true environment variable
    - Or INFERENCE_BACKEND=ollama
    """
    return (
        os.getenv("MILVUS_LITE", "false").lower() == "true" or
        os.getenv("INFERENCE_BACKEND", "").lower() == "ollama" or
        os.getenv("LOCAL_MODE", "false").lower() == "true"
    )

