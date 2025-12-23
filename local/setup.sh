#!/bin/bash
# SPDX-FileCopyrightText: Copyright (c) 2025 Research_as_a_Code Project
# SPDX-License-Identifier: Apache-2.0

# ========================================
# Local AI-Q Setup Script
# ========================================
#
# This script sets up the local development environment for AI-Q
# with Ollama for inference and Milvus Lite for vector storage.
#
# Prerequisites:
# - Python 3.10+
# - CUDA-capable GPU (optional, for faster inference)
# - ~10GB disk space for models
#
# Usage:
#   ./local/setup.sh [--preset PRESET_NAME]
#
# Example:
#   ./local/setup.sh --preset workstation_large
#   ./local/setup.sh --preset consumer_high
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default configuration
PRESET="${1:-workstation_large}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo -e "${BLUE}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║          AI-Q Local Development Setup                  ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════╝${NC}"
echo ""

# ----------------------------------------
# Step 1: Check prerequisites
# ----------------------------------------
echo -e "${YELLOW}[1/6] Checking prerequisites...${NC}"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 is required but not found.${NC}"
    echo "Please install Python 3.10 or later."
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "  ✓ Python $PYTHON_VERSION found"

# Check for GPU (nvidia-smi)
if command -v nvidia-smi &> /dev/null; then
    GPU_INFO=$(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null | head -1)
    echo "  ✓ GPU found: $GPU_INFO"
else
    echo -e "${YELLOW}  ⚠ No NVIDIA GPU detected. CPU inference will be used (slower).${NC}"
fi

# Check Ollama
if ! command -v ollama &> /dev/null; then
    echo -e "${RED}Error: Ollama is required but not found.${NC}"
    echo ""
    echo "Install Ollama with:"
    echo "  curl -fsSL https://ollama.ai/install.sh | sh"
    echo ""
    echo "Or visit: https://ollama.ai"
    exit 1
fi
echo "  ✓ Ollama found"

# ----------------------------------------
# Step 2: Set up Python virtual environment
# ----------------------------------------
echo ""
echo -e "${YELLOW}[2/6] Setting up Python virtual environment...${NC}"

cd "$PROJECT_ROOT"

if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    echo "  ✓ Created virtual environment"
else
    echo "  ✓ Virtual environment already exists"
fi

# Activate venv
source .venv/bin/activate
echo "  ✓ Activated virtual environment"

# ----------------------------------------
# Step 3: Install Python dependencies
# ----------------------------------------
echo ""
echo -e "${YELLOW}[3/6] Installing Python dependencies...${NC}"

pip install --upgrade pip -q

if [ -f "requirements-local.txt" ]; then
    pip install -r requirements-local.txt -q
    echo "  ✓ Installed local dependencies"
else
    echo -e "${YELLOW}  ⚠ requirements-local.txt not found, installing core dependencies${NC}"
    pip install pymilvus[lite]>=2.4.0 -q
    pip install langchain-openai>=0.1.0 -q
    pip install fastapi>=0.100.0 -q
    pip install uvicorn>=0.23.0 -q
    pip install aiohttp>=3.9.0 -q
    pip install tavily-python>=0.3.0 -q
    pip install pydantic>=2.0.0 -q
    echo "  ✓ Installed core dependencies"
fi

# Install aira module in editable mode
if [ -d "aira" ]; then
    pip install -e aira/ -q
    echo "  ✓ Installed aira module"
fi

# ----------------------------------------
# Step 4: Start Ollama and pull models
# ----------------------------------------
echo ""
echo -e "${YELLOW}[4/6] Setting up Ollama models...${NC}"

# Check if Ollama is running
if ! pgrep -x "ollama" > /dev/null; then
    echo "  Starting Ollama service..."
    ollama serve &>/dev/null &
    sleep 3
fi

# Model presets
case "$PRESET" in
    "workstation_xlarge")
        LLM_MODEL="llama3.1:70b-instruct-q4_K_M"
        EMBEDDING_MODEL="nomic-embed-text"
        ;;
    "workstation_large")
        LLM_MODEL="llama3.1:8b-instruct-q8_0"
        EMBEDDING_MODEL="nomic-embed-text"
        ;;
    "workstation_medium")
        LLM_MODEL="qwen2.5:7b-instruct-q4_K_M"
        EMBEDDING_MODEL="mxbai-embed-large"
        ;;
    "consumer_high")
        LLM_MODEL="llama3.1:8b-instruct-q6_K"
        EMBEDDING_MODEL="nomic-embed-text"
        ;;
    "consumer_mid")
        LLM_MODEL="llama3.2:3b-instruct-q8_0"
        EMBEDDING_MODEL="nomic-embed-text"
        ;;
    "consumer_low")
        LLM_MODEL="qwen2.5:3b-instruct-q4_K_M"
        EMBEDDING_MODEL="all-minilm:l6-v2"
        ;;
    "cpu_only")
        LLM_MODEL="llama3.2:1b-instruct-q4_K_M"
        EMBEDDING_MODEL="all-minilm:l6-v2"
        ;;
    *)
        echo -e "${RED}Unknown preset: $PRESET${NC}"
        echo "Available presets: workstation_xlarge, workstation_large, workstation_medium,"
        echo "                   consumer_high, consumer_mid, consumer_low, cpu_only"
        exit 1
        ;;
esac

echo "  Using preset: $PRESET"
echo "  LLM: $LLM_MODEL"
echo "  Embedding: $EMBEDDING_MODEL"

# Pull models
echo "  Pulling LLM model (this may take a while)..."
ollama pull "$LLM_MODEL"
echo "  ✓ LLM model ready"

echo "  Pulling embedding model..."
ollama pull "$EMBEDDING_MODEL"
echo "  ✓ Embedding model ready"

# ----------------------------------------
# Step 5: Create data directories
# ----------------------------------------
echo ""
echo -e "${YELLOW}[5/6] Creating data directories...${NC}"

mkdir -p "$PROJECT_ROOT/data/milvus"
mkdir -p "$PROJECT_ROOT/data/documents"
echo "  ✓ Created data/milvus directory"
echo "  ✓ Created data/documents directory"

# ----------------------------------------
# Step 6: Create .env file
# ----------------------------------------
echo ""
echo -e "${YELLOW}[6/6] Creating environment configuration...${NC}"

ENV_FILE="$PROJECT_ROOT/.env.local"

if [ -f "$ENV_FILE" ]; then
    echo -e "${YELLOW}  ⚠ $ENV_FILE already exists, backing up to .env.local.bak${NC}"
    cp "$ENV_FILE" "$ENV_FILE.bak"
fi

cat > "$ENV_FILE" << EOF
# AI-Q Local Environment Configuration
# Generated by setup.sh on $(date)

# Ollama Configuration
LLM_BASE_URL=http://localhost:11434/v1
EMBEDDING_BASE_URL=http://localhost:11434/v1
LLM_MODEL=$LLM_MODEL
EMBEDDING_MODEL=$EMBEDDING_MODEL

# Milvus Lite
MILVUS_LITE=true
MILVUS_DATA_PATH=./data/milvus/milvus.db

# Local mode flag
LOCAL_MODE=true

# Optional: Tavily API Key (for web search)
# Get your key at: https://tavily.com
TAVILY_API_KEY=

# Model preset used
MODEL_PRESET=$PRESET
EOF

echo "  ✓ Created $ENV_FILE"

# ----------------------------------------
# Complete!
# ----------------------------------------
echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║          Setup Complete!                               ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "Next steps:"
echo ""
echo "  1. Activate the virtual environment:"
echo -e "     ${BLUE}source .venv/bin/activate${NC}"
echo ""
echo "  2. (Optional) Ingest documents for RAG:"
echo -e "     ${BLUE}python local/ingest_local.py --collection my_docs --path data/documents/${NC}"
echo ""
echo "  3. Start the backend:"
echo -e "     ${BLUE}source .env.local && python -m uvicorn backend.main:app --reload --port 8000${NC}"
echo ""
echo "  4. (Optional) Start the frontend:"
echo -e "     ${BLUE}cd frontend && npm install && npm run dev${NC}"
echo ""
echo "Configuration:"
echo "  - LLM Model: $LLM_MODEL"
echo "  - Embedding Model: $EMBEDDING_MODEL"
echo "  - Milvus: Lite mode (in-process)"
echo "  - Environment: .env.local"
echo ""

