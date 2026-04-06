# Retrieval Service

Architecture placeholder for a future standalone retrieval microservice.

The current retrieval foundation lives inside `apps/api/app/knowledge/` and runs
in-process with the API server.  It uses:

- **Embedding**: sentence-transformers (`all-MiniLM-L6-v2`) locally
- **Vector store**: prefers Milvus Lite when available, otherwise falls back to ChromaDB; in practice ChromaDB is the default on Windows/macOS and Milvus Lite is typically used on Linux
- **Chunking**: fixed-size character windows from normalized ingestion outputs

A dedicated retrieval service will only be needed when the platform scales
beyond single-process local development.
