#!/usr/bin/env python3
"""
Fix Milvus metadata collections for NVIDIA RAG Blueprint.
This script creates the required metadata_schema collection.
"""

import sys
from pymilvus import connections, Collection, FieldSchema, CollectionSchema, DataType, utility

def main():
    # Connection details
    host = sys.argv[1] if len(sys.argv) > 1 else "localhost"
    port = sys.argv[2] if len(sys.argv) > 2 else "19530"
    
    print(f"Connecting to Milvus at {host}:{port}...")
    connections.connect(host=host, port=port)
    
    # List existing collections
    print("\n=== Existing Collections ===")
    collections = utility.list_collections()
    for coll_name in collections:
        print(f"  - {coll_name}")
        coll = Collection(coll_name)
        print(f"    Schema: {coll.schema}")
        print(f"    Num entities: {coll.num_entities}")
    
    # Check if metadata_schema exists
    if "metadata_schema" not in collections:
        print("\n=== Creating metadata_schema collection ===")
        
        # Define schema for metadata_schema
        # This is based on typical NVIDIA RAG Blueprint requirements
        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=False),
            FieldSchema(name="collection_name", dtype=DataType.VARCHAR, max_length=256),
            FieldSchema(name="document_id", dtype=DataType.VARCHAR, max_length=512),
            FieldSchema(name="filename", dtype=DataType.VARCHAR, max_length=512),
            FieldSchema(name="page_number", dtype=DataType.INT64),
            FieldSchema(name="chunk_id", dtype=DataType.INT64),
            FieldSchema(name="custom_metadata", dtype=DataType.VARCHAR, max_length=2048),
        ]
        
        schema = CollectionSchema(fields=fields, description="Metadata schema for RAG documents")
        collection = Collection(name="metadata_schema", schema=schema)
        
        print(f"✅ Created metadata_schema collection")
        print(f"   Schema: {collection.schema}")
    else:
        print("\n✅ metadata_schema collection already exists")
    
    # Check the main us_tariffs collection
    if "us_tariffs" in collections:
        print("\n=== us_tariffs Collection Details ===")
        coll = Collection("us_tariffs")
        print(f"Schema: {coll.schema}")
        print(f"Num entities: {coll.num_entities}")
        
        # Try to load and check data
        try:
            coll.load()
            print("✅ Collection loaded successfully")
        except Exception as e:
            print(f"❌ Error loading collection: {e}")
    else:
        print("\n❌ us_tariffs collection does not exist")
    
    print("\n=== Done ===")
    connections.disconnect("default")

if __name__ == "__main__":
    main()

