# Environment Variables

This document lists all environment variables required to run the Finance RAG application.

## Required Variables

### Application Core
- `APP_NAME` - Application name (e.g., `finance`)
- `SECRET_KEY` - Secret key for JWT token signing (use a strong random string)
- `ADMIN_SECRET_KEY` - Secret key for admin panel session management

### Database (PostgreSQL)
- `DB_NAME` - Database name (e.g., `finance`)
- `DB_HOST` - Database host (e.g., `postgres` for Docker, `localhost` for local)
- `DB_PORT` - Database port (default: `5432`)
- `DB_USER` - Database username (e.g., `postgres`)
- `DB_PASSWORD` - Database password

### Optional Application Settings
- `ALGORITHM` - JWT algorithm (default: `HS256`)
- `ACCESS_TOKEN_EXPIRE_HOURS` - JWT token expiration in hours (default: `24`)
- `LOG_LEVEL` - Logging level (default: `INFO`, options: `DEBUG`, `INFO`, `WARNING`, `ERROR`)
- `JSON_LOGS` - Enable JSON logging format (default: `false`)
- `ADD_BASE_ADMIN` - Create default admin user on startup (default: `false`)

## OpenRouter API (for LLM and Embeddings)

### Required for RAG Agent
- `OPENROUTER_API_KEY` - Your OpenRouter API key (required for chat and embeddings)

### Chat Model Configuration
- `OPENROUTER_CHAT_MODEL` - Chat model identifier (default: `qwen/qwen3-235b-a22b-2507`)
  - Examples: `qwen/qwen3-235b-a22b-2507`, `qwen/qwen3-14b`, `anthropic/claude-3-opus`
- `OPENROUTER_CHAT_URL` - Override chat API endpoint (optional, defaults to OpenRouter)
- `OPENROUTER_CHAT_TIMEOUT_SECONDS` - Chat request timeout (default: `60.0`)

### Embedding Model Configuration
- `OPENROUTER_EMBED_MODEL` - Embedding model identifier (default: `qwen/qwen3-embedding-8b`)
  - Examples: `qwen/qwen3-embedding-8b`, `openai/text-embedding-3-small`
- `OPENROUTER_EMBED_URL` - Override embeddings API endpoint (optional, defaults to OpenRouter)
- `OPENROUTER_TIMEOUT_SECONDS` - Embedding request timeout (default: `30.0`)

### Optional OpenRouter Settings
- `OPENROUTER_HTTP_REFERER` - HTTP referer header for OpenRouter (optional)
- `OPENROUTER_APP_TITLE` - Application title header (defaults to `APP_NAME`)

## Qdrant Vector Database

### Required for Vector Search
- `QDRANT_URL` - Qdrant server URL (e.g., `http://178.72.149.75:6333`)
  - Required for document indexing and vector search
  - If not set, vector search will be disabled

### Optional Qdrant Settings
- `QDRANT_COLLECTION_NAME` - Collection name for document chunks (default: `document_chunks`)
- `QDRANT_BATCH_SIZE` - Batch size for upserting vectors (default: `64`)

## MinIO S3 Storage

### Required for Document Storage
- `MINIO_ENDPOINT` - MinIO API endpoint (e.g., `http://178.72.149.75:9000`)
- `MINIO_ACCESS_KEY` - MinIO access key (e.g., `minioadmin`)
- `MINIO_SECRET_KEY` - MinIO secret key (e.g., `minioadmin`)

### Optional MinIO Settings
- `MINIO_BUCKET_NAME` - Bucket name for documents (default: `documents`)
- `MINIO_PUBLIC_ENDPOINT` - Public URL for document links (e.g., `http://178.72.149.75:9001`)
  - If not set, defaults to `MINIO_ENDPOINT`
- `MINIO_REGION` - S3 region (optional)
- `MINIO_USE_SSL` - Use HTTPS for MinIO (default: `false`)

## Example `.env` File

```bash
# Application Core
APP_NAME=finance
SECRET_KEY=your-secret-key-here-change-in-production
ADMIN_SECRET_KEY=your-admin-secret-key-here-change-in-production

# Database
DB_NAME=finance
DB_HOST=postgres
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=postgres

# Logging
LOG_LEVEL=INFO
JSON_LOGS=false
ADD_BASE_ADMIN=true

# OpenRouter (Required for RAG)
OPENROUTER_API_KEY=sk-or-v1-...
OPENROUTER_CHAT_MODEL=qwen/qwen3-235b-a22b-2507
OPENROUTER_EMBED_MODEL=qwen/qwen3-embedding-8b
OPENROUTER_CHAT_TIMEOUT_SECONDS=60.0
OPENROUTER_TIMEOUT_SECONDS=30.0

# Qdrant (Required for Vector Search)
QDRANT_URL=http://178.72.149.75:6333
QDRANT_COLLECTION_NAME=document_chunks
QDRANT_BATCH_SIZE=64

# MinIO (Required for Document Storage)
MINIO_ENDPOINT=http://178.72.149.75:9000
MINIO_PUBLIC_ENDPOINT=http://178.72.149.75:9001
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET_NAME=documents
MINIO_USE_SSL=false
```

## Docker Compose Example

For Docker Compose, add these to the `api` service `environment` section:

```yaml
services:
  api:
    environment:
      # ... existing variables ...
      
      # OpenRouter
      OPENROUTER_API_KEY: ${OPENROUTER_API_KEY}
      OPENROUTER_CHAT_MODEL: ${OPENROUTER_CHAT_MODEL:-qwen/qwen3-235b-a22b-2507}
      OPENROUTER_EMBED_MODEL: ${OPENROUTER_EMBED_MODEL:-qwen/qwen3-embedding-8b}
      
      # Qdrant
      QDRANT_URL: ${QDRANT_URL:-http://178.72.149.75:6333}
      
      # MinIO
      MINIO_ENDPOINT: ${MINIO_ENDPOINT:-http://178.72.149.75:9000}
      MINIO_PUBLIC_ENDPOINT: ${MINIO_PUBLIC_ENDPOINT:-http://178.72.149.75:9001}
      MINIO_ACCESS_KEY: ${MINIO_ACCESS_KEY:-minioadmin}
      MINIO_SECRET_KEY: ${MINIO_SECRET_KEY:-minioadmin}
```

## Feature Flags

The following features are **optional** and will gracefully degrade if not configured:

- **Vector Search**: Disabled if `QDRANT_URL` is not set
- **Document Embeddings**: Disabled if `OPENROUTER_API_KEY` is not set
- **Document Storage**: Will fail if `MINIO_ENDPOINT` is not set (required for uploads)

## Security Notes

1. **Never commit** `.env` files or secrets to version control
2. Use strong, random values for `SECRET_KEY` and `ADMIN_SECRET_KEY` in production
3. Rotate `OPENROUTER_API_KEY` regularly if compromised
4. Use environment-specific values (development, staging, production)
5. Consider using secrets management tools (AWS Secrets Manager, HashiCorp Vault, etc.) for production

