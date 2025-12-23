# SPDX-FileCopyrightText: Copyright (c) 2025 Research_as_a_Code Project
# SPDX-License-Identifier: Apache-2.0

"""
Milvus Helper Module

Provides a unified interface for both Milvus Lite (in-process) and 
Milvus Standalone (server) deployments.
"""

import os
import logging
from typing import List, Dict, Any, Optional
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# Global client for Milvus Lite mode
_milvus_lite_client = None


def is_milvus_lite_mode() -> bool:
    """Check if running in Milvus Lite mode."""
    return os.getenv("MILVUS_LITE", "false").lower() == "true"


def get_milvus_lite_path() -> str:
    """Get the path for Milvus Lite database file."""
    return os.getenv("MILVUS_DATA_PATH", "./data/milvus/milvus.db")


def get_milvus_lite_client():
    """
    Get or create the Milvus Lite client singleton.
    
    Returns:
        MilvusClient instance for Lite mode
    """
    global _milvus_lite_client
    
    if _milvus_lite_client is None:
        from pymilvus import MilvusClient
        db_path = get_milvus_lite_path()
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        logger.info(f"Initializing Milvus Lite at: {db_path}")
        _milvus_lite_client = MilvusClient(db_path)
    
    return _milvus_lite_client


def reset_milvus_lite_client():
    """Reset the Milvus Lite client (for testing)."""
    global _milvus_lite_client
    if _milvus_lite_client is not None:
        _milvus_lite_client.close()
        _milvus_lite_client = None


@contextmanager
def milvus_connection():
    """
    Context manager for Milvus connection.
    
    Handles both Milvus Lite and standalone modes transparently.
    
    Usage:
        with milvus_connection() as conn:
            # conn is either MilvusClient (lite) or connection alias (standalone)
            pass
    """
    if is_milvus_lite_mode():
        client = get_milvus_lite_client()
        yield client
    else:
        from pymilvus import connections
        
        milvus_host = os.getenv("MILVUS_HOST", "localhost")
        milvus_port = int(os.getenv("MILVUS_PORT", "19530"))
        
        connections.connect(alias="default", host=milvus_host, port=milvus_port)
        yield "default"
        # Note: We don't disconnect as other code may be using the connection


def has_collection(collection_name: str) -> bool:
    """
    Check if a collection exists.
    
    Works with both Milvus Lite and standalone.
    """
    if is_milvus_lite_mode():
        client = get_milvus_lite_client()
        collections = client.list_collections()
        return collection_name in collections
    else:
        from pymilvus import utility, connections
        
        # Ensure connected
        if not connections.has_connection("default"):
            milvus_host = os.getenv("MILVUS_HOST", "localhost")
            milvus_port = int(os.getenv("MILVUS_PORT", "19530"))
            connections.connect(alias="default", host=milvus_host, port=milvus_port)
        
        return utility.has_collection(collection_name)


def search_collection(
    collection_name: str,
    query_embedding: List[float],
    limit: int = 5,
    output_fields: List[str] = None
) -> List[Dict[str, Any]]:
    """
    Search a collection with a query embedding.
    
    Works with both Milvus Lite and standalone.
    
    Args:
        collection_name: Name of the collection to search
        query_embedding: Query vector
        limit: Maximum number of results
        output_fields: Fields to return (default: ["text", "source"])
        
    Returns:
        List of results with 'text', 'source', 'score', 'collection' fields
    """
    if output_fields is None:
        output_fields = ["text", "source"]
    
    results = []
    
    if is_milvus_lite_mode():
        client = get_milvus_lite_client()
        
        # Milvus Lite uses a simpler search API
        search_results = client.search(
            collection_name=collection_name,
            data=[query_embedding],
            limit=limit,
            output_fields=output_fields,
        )
        
        # Format results
        for hits in search_results:
            for hit in hits:
                entity = hit.get("entity", {})
                results.append({
                    "text": entity.get("text", ""),
                    "source": entity.get("source", "RAG Document"),
                    "score": hit.get("distance", 0.0),
                    "collection": collection_name,
                })
    else:
        from pymilvus import Collection, connections
        
        # Ensure connected
        if not connections.has_connection("default"):
            milvus_host = os.getenv("MILVUS_HOST", "localhost")
            milvus_port = int(os.getenv("MILVUS_PORT", "19530"))
            connections.connect(alias="default", host=milvus_host, port=milvus_port)
        
        coll = Collection(collection_name)
        coll.load()
        
        search_params = {"metric_type": "L2", "params": {"nprobe": 10}}
        search_results = coll.search(
            data=[query_embedding],
            anns_field="embedding",
            param=search_params,
            limit=limit,
            output_fields=output_fields
        )
        
        # Format results
        for hits in search_results:
            for hit in hits:
                try:
                    text = hit.entity.text if hasattr(hit.entity, 'text') else hit.entity.get('text', '')
                    source = hit.entity.source if hasattr(hit.entity, 'source') else hit.entity.get('source', 'RAG Document')
                except Exception:
                    text = str(getattr(hit.entity, 'text', ''))
                    source = str(getattr(hit.entity, 'source', 'RAG Document'))
                
                results.append({
                    "text": text,
                    "source": source,
                    "score": hit.score,
                    "collection": collection_name,
                })
    
    return results


def create_collection(
    collection_name: str,
    dimension: int = 768,
    metric_type: str = "L2"
) -> bool:
    """
    Create a new collection.
    
    Works with both Milvus Lite and standalone.
    
    Args:
        collection_name: Name for the new collection
        dimension: Embedding dimension
        metric_type: Distance metric (L2, IP, COSINE)
        
    Returns:
        True if created successfully
    """
    if is_milvus_lite_mode():
        from pymilvus import MilvusClient, DataType
        
        client = get_milvus_lite_client()
        
        # Check if already exists
        if collection_name in client.list_collections():
            logger.info(f"Collection '{collection_name}' already exists")
            return True
        
        # Create schema
        schema = client.create_schema(auto_id=True, enable_dynamic_field=True)
        schema.add_field("id", DataType.INT64, is_primary=True)
        schema.add_field("text", DataType.VARCHAR, max_length=65535)
        schema.add_field("source", DataType.VARCHAR, max_length=512)
        schema.add_field("embedding", DataType.FLOAT_VECTOR, dim=dimension)
        
        # Create index params
        index_params = client.prepare_index_params()
        index_params.add_index(
            field_name="embedding",
            index_type="FLAT",  # Use FLAT for Lite mode (small datasets)
            metric_type=metric_type
        )
        
        client.create_collection(
            collection_name=collection_name,
            schema=schema,
            index_params=index_params
        )
        
        logger.info(f"Created collection '{collection_name}' with dimension {dimension}")
        return True
    else:
        from pymilvus import (
            Collection, CollectionSchema, FieldSchema, 
            DataType, connections, utility
        )
        
        # Ensure connected
        if not connections.has_connection("default"):
            milvus_host = os.getenv("MILVUS_HOST", "localhost")
            milvus_port = int(os.getenv("MILVUS_PORT", "19530"))
            connections.connect(alias="default", host=milvus_host, port=milvus_port)
        
        # Check if already exists
        if utility.has_collection(collection_name):
            logger.info(f"Collection '{collection_name}' already exists")
            return True
        
        # Define schema
        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="source", dtype=DataType.VARCHAR, max_length=512),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dimension),
        ]
        schema = CollectionSchema(fields=fields, description=f"RAG collection: {collection_name}")
        
        # Create collection
        collection = Collection(name=collection_name, schema=schema)
        
        # Create index
        index_params = {
            "metric_type": metric_type,
            "index_type": "IVF_FLAT",
            "params": {"nlist": 128}
        }
        collection.create_index("embedding", index_params)
        
        logger.info(f"Created collection '{collection_name}' with dimension {dimension}")
        return True


def insert_documents(
    collection_name: str,
    texts: List[str],
    embeddings: List[List[float]],
    sources: List[str]
) -> int:
    """
    Insert documents into a collection.
    
    Args:
        collection_name: Target collection
        texts: List of document texts
        embeddings: List of embedding vectors
        sources: List of source identifiers
        
    Returns:
        Number of documents inserted
    """
    if len(texts) != len(embeddings) != len(sources):
        raise ValueError("texts, embeddings, and sources must have the same length")
    
    if is_milvus_lite_mode():
        client = get_milvus_lite_client()
        
        data = [
            {"text": text, "source": source, "embedding": emb}
            for text, source, emb in zip(texts, sources, embeddings)
        ]
        
        result = client.insert(collection_name=collection_name, data=data)
        return len(data)
    else:
        from pymilvus import Collection, connections
        
        # Ensure connected
        if not connections.has_connection("default"):
            milvus_host = os.getenv("MILVUS_HOST", "localhost")
            milvus_port = int(os.getenv("MILVUS_PORT", "19530"))
            connections.connect(alias="default", host=milvus_host, port=milvus_port)
        
        collection = Collection(collection_name)
        
        data = [texts, sources, embeddings]
        result = collection.insert(data)
        collection.flush()
        
        return result.insert_count


def list_collections() -> List[str]:
    """List all available collections."""
    if is_milvus_lite_mode():
        client = get_milvus_lite_client()
        return client.list_collections()
    else:
        from pymilvus import utility, connections
        
        # Ensure connected
        if not connections.has_connection("default"):
            milvus_host = os.getenv("MILVUS_HOST", "localhost")
            milvus_port = int(os.getenv("MILVUS_PORT", "19530"))
            connections.connect(alias="default", host=milvus_host, port=milvus_port)
        
        return utility.list_collections()


def get_collection_stats(collection_name: str) -> Dict[str, Any]:
    """Get statistics for a collection."""
    if is_milvus_lite_mode():
        client = get_milvus_lite_client()
        stats = client.get_collection_stats(collection_name)
        return {
            "row_count": stats.get("row_count", 0),
            "collection_name": collection_name,
        }
    else:
        from pymilvus import Collection, connections
        
        # Ensure connected
        if not connections.has_connection("default"):
            milvus_host = os.getenv("MILVUS_HOST", "localhost")
            milvus_port = int(os.getenv("MILVUS_PORT", "19530"))
            connections.connect(alias="default", host=milvus_host, port=milvus_port)
        
        collection = Collection(collection_name)
        collection.load()
        
        return {
            "row_count": collection.num_entities,
            "collection_name": collection_name,
        }

