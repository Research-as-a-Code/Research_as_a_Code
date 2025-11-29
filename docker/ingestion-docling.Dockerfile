FROM python:3.11-slim

# Install system dependencies (including OpenGL for Docling)
RUN apt-get update && apt-get install -y \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Pre-install all dependencies
RUN pip install --no-cache-dir \
    pymilvus==2.6.3 \
    httpx==0.28.1 \
    docling==2.63.0 \
    langchain==0.3.14 \
    langchain-text-splitters==0.3.4

# Verify installation
RUN python -c "from docling.document_converter import DocumentConverter; print('✅ Docling installed successfully')" && \
    python -c "from pymilvus import connections; print('✅ Pymilvus installed successfully')" && \
    python -c "import httpx; print('✅ Httpx installed successfully')" && \
    python -c "from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter; print('✅ LangChain installed successfully')"

# Set working directory
WORKDIR /app

# Default command
CMD ["python"]

