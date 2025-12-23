# Local AI-Q Research Assistant

Run AI-Q entirely on your local machine with Ollama for inference and Milvus Lite for vector storage. No cloud services or Kubernetes required.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    Local Machine (Workstation GPU)              │
│                                                                 │
│  ┌──────────────────────┐     ┌──────────────────────┐         │
│  │    Ollama Native     │     │    Python Backend    │         │
│  │  ┌────────────────┐  │     │  ┌────────────────┐  │         │
│  │  │  LLM Models    │  │◄────┤  │  FastAPI       │  │         │
│  │  │  Llama 3.1 8B  │  │     │  │  main.py       │  │         │
│  │  └────────────────┘  │     │  └────────────────┘  │         │
│  │  ┌────────────────┐  │     │  ┌────────────────┐  │         │
│  │  │  Embedding     │  │◄────┤  │  AIRA Module   │  │         │
│  │  │  nomic-embed   │  │     │  │  UDR + TTD-DR  │  │         │
│  │  └────────────────┘  │     │  └────────────────┘  │         │
│  └──────────────────────┘     │  ┌────────────────┐  │         │
│         :11434/v1             │  │  Milvus Lite   │  │         │
│                               │  │  In-Process DB │  │         │
│                               │  └────────────────┘  │         │
│                               └──────────────────────┘         │
│                                        :8000                    │
│                                          ▲                      │
│  ┌──────────────────────────────────────┼───────────────────┐  │
│  │              Next.js Frontend (Optional)                 │  │
│  │                      npm run dev                          │  │
│  └───────────────────────────────────────────────────────────┘  │
│                              :3000                              │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Prerequisites

- **Python 3.10+**
- **Ollama** - Install from https://ollama.ai
- **GPU** (recommended) - NVIDIA GPU with 8GB+ VRAM, or Apple Silicon

### 2. One-Command Setup

```bash
# Run the setup script with your GPU preset
./local/setup.sh workstation_large    # A5000/A6000/RTX 4090 (24GB+)
./local/setup.sh consumer_high        # RTX 4090/3090 (24GB)
./local/setup.sh consumer_mid         # RTX 4070/3070 (8-12GB)
./local/setup.sh cpu_only             # No GPU
```

The setup script will:
- Check prerequisites
- Create a Python virtual environment
- Install dependencies
- Pull required Ollama models
- Create data directories
- Generate `.env.local` configuration

### 3. Start the Backend

```bash
source .venv/bin/activate
source .env.local
python -m uvicorn backend.main:app --reload --port 8000
```

### 4. (Optional) Start the Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000 in your browser.

## Model Presets

Choose a preset based on your GPU VRAM:

| Preset | GPU | VRAM | LLM Model | Embedding Model |
|--------|-----|------|-----------|-----------------|
| `workstation_xlarge` | A6000 | 48GB | llama3.1:70b-instruct-q4_K_M | nomic-embed-text |
| `workstation_large` | A5000/RTX 4090 | 24GB | llama3.1:8b-instruct-q8_0 | nomic-embed-text |
| `workstation_medium` | A4000 | 16GB | qwen2.5:7b-instruct-q4_K_M | mxbai-embed-large |
| `consumer_high` | RTX 4090/3090 | 24GB | llama3.1:8b-instruct-q6_K | nomic-embed-text |
| `consumer_mid` | RTX 4070/3070 | 8-12GB | llama3.2:3b-instruct-q8_0 | nomic-embed-text |
| `consumer_low` | RTX 3060/4060 | 8GB | qwen2.5:3b-instruct-q4_K_M | all-minilm:l6-v2 |
| `cpu_only` | None | N/A | llama3.2:1b-instruct-q4_K_M | all-minilm:l6-v2 |

## Document Ingestion

Ingest your documents into the local vector database:

```bash
# Basic usage
python local/ingest_local.py --collection my_docs --path data/documents/

# With custom chunking
python local/ingest_local.py \
    --collection research_papers \
    --path ~/papers/ \
    --chunk-size 512 \
    --chunk-overlap 100

# With specific embedding model
python local/ingest_local.py \
    --collection my_docs \
    --path data/ \
    --embedding-model mxbai-embed-large
```

### Supported File Formats

- PDF (`.pdf`)
- Plain text (`.txt`)
- Markdown (`.md`)
- Word documents (`.docx`)

## Configuration

### Environment Variables

Copy `local/env.example` to `.env.local` and customize:

```bash
# Ollama endpoints
LLM_BASE_URL=http://localhost:11434/v1
EMBEDDING_BASE_URL=http://localhost:11434/v1

# Model selection
LLM_MODEL=llama3.1:8b-instruct-q8_0
EMBEDDING_MODEL=nomic-embed-text

# Milvus Lite
MILVUS_LITE=true
MILVUS_DATA_PATH=./data/milvus/milvus.db

# Local mode flag
LOCAL_MODE=true

# Optional: Web search
TAVILY_API_KEY=your-key-here
```

### Using the Configuration API

```python
from local.config import get_config, LocalConfig, MODEL_PRESETS

# Get current configuration
config = get_config()
print(config.llm_model)
print(config.embedding_model)

# Create config from preset
config = LocalConfig.from_preset("consumer_high")

# Check mode
print(config.is_milvus_lite)  # True
print(config.is_ollama)       # True
```

## File Structure

```
local/
├── README.md           # This file
├── __init__.py         # Module exports
├── config.py           # Configuration system with model presets
├── milvus_helper.py    # Milvus Lite/Standalone abstraction layer
├── ingest_local.py     # Document ingestion script
├── setup.sh            # One-command setup script
└── env.example         # Environment template
```

## How It Works

### Mode Detection

The system automatically detects local mode through environment variables:

```python
# Any of these enables local mode:
LOCAL_MODE=true
MILVUS_LITE=true
INFERENCE_BACKEND=ollama
```

### Milvus Abstraction

The `milvus_helper.py` module provides a unified interface:

```python
from local.milvus_helper import (
    has_collection,
    search_collection,
    create_collection,
    insert_documents,
)

# Works the same whether using Milvus Lite or Standalone
if has_collection("my_docs"):
    results = search_collection(
        "my_docs",
        query_embedding,
        limit=5
    )
```

### Embedding Compatibility

Ollama uses the OpenAI-compatible API but doesn't require `input_type`:

```python
# Cloud mode (NVIDIA NIM)
payload = {"input": text, "model": "snowflake/arctic-embed-l", "input_type": "query"}

# Local mode (Ollama)
payload = {"input": text, "model": "nomic-embed-text"}
```

This is handled automatically by the modified `udr_integration.py`, `search.py`, and `tools.py`.

## Alternative Backends

### Using vLLM Instead of Ollama

```bash
# Start vLLM server
python -m vllm.entrypoints.openai.api_server \
    --model meta-llama/Llama-3.1-8B-Instruct \
    --port 8000

# Update .env.local
INFERENCE_BACKEND=vllm
LLM_BASE_URL=http://localhost:8000/v1
```

### Using SGLang

```bash
# Start SGLang server
python -m sglang.launch_server \
    --model-path meta-llama/Llama-3.1-8B-Instruct \
    --port 30000

# Update .env.local
INFERENCE_BACKEND=sglang
LLM_BASE_URL=http://localhost:30000/v1
```

### Using Remote Milvus

```bash
# In .env.local
MILVUS_LITE=false
MILVUS_HOST=localhost
MILVUS_PORT=19530
VECTOR_DB_BACKEND=milvus_standalone
```

## Troubleshooting

### Ollama Connection Issues

```bash
# Check if Ollama is running
curl http://localhost:11434/api/version

# Start Ollama if not running
ollama serve
```

### Model Not Found

```bash
# List installed models
ollama list

# Pull missing model
ollama pull llama3.1:8b-instruct-q8_0
```

### Out of Memory

Choose a smaller model preset or use quantization:

```bash
# Instead of q8_0, use q4_K_M for 50% less memory
LLM_MODEL=llama3.1:8b-instruct-q4_K_M
```

### Milvus Lite Database Locked

If you see "database locked" errors:

```bash
# Remove the lock file
rm -f data/milvus/milvus.db.lock

# Or use a fresh database
MILVUS_DATA_PATH=./data/milvus/new_milvus.db
```

## Performance Tips

1. **GPU Memory**: Use quantized models (q4_K_M, q6_K) to fit larger models in VRAM
2. **Batch Size**: Reduce `--batch-size` in ingestion for lower memory usage
3. **Chunk Size**: Smaller chunks (512) improve retrieval precision but increase storage
4. **Context Length**: Ollama defaults to 2048 tokens; increase with `num_ctx` in modelfile

## Comparison: Local vs Cloud

| Feature | Local Mode | Cloud (Kubernetes) |
|---------|------------|-------------------|
| Setup Time | ~10 minutes | ~1 hour |
| Cost | Free (your hardware) | Cloud GPU costs |
| Privacy | Data stays local | Data in cloud |
| Performance | Depends on GPU | Consistent |
| Scalability | Single machine | Multi-node |
| Maintenance | Self-managed | Infrastructure as code |

## License

Apache-2.0 - See LICENSE file in project root.

