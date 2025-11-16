# Document Vector Pipeline

The document upload flow now parses, chunks, embeds, and indexes each file for retrieval.

## Processing Stages
- **Parsing**: `DocumentUploadPipeline` feeds the raw upload into `UnstructuredDocumentParser`, which wraps the `unstructured.partition.auto` pipeline (default `fast` strategy, hi-res only when `UNSTRUCTURED_ENABLE_HI_RES=1` **and** dependencies are present) to convert binary inputs (PDF, DOCX, PPTX, etc.) into Markdown plus optional section metadata (`MarkdownDocument`).
- **Chunking**: `ChunkSplitter` uses LangChain's `RecursiveCharacterTextSplitter` (configured for markdown separators) to turn the parsed content into ordered `DocumentChunkPayload` entries.
- **Persistence**: Each payload is stored as a `DocumentChunk` via `DocumentChunkRepository`. The pipeline keeps a `ChunkRecord` pairing the persisted chunk with its metadata.
- **Vectorization**: `DocumentVectorManager` calls `OpenRouterEmbeddingClient` to embed chunk text. Embeddings are upserted to Qdrant through `QdrantVectorStore`, attaching payload metadata (`document_id`, `chunk_serial`, etc.) for filtered search.

## Configuration
Environment variables (all optional unless noted) are read via `config.Settings`:

| Variable | Description | Default |
| --- | --- | --- |
| `OPENROUTER_API_KEY` | API key for OpenRouter embeddings. When unset, embedding is skipped. | – |
| `OPENROUTER_EMBED_MODEL` | Embedding model name. | `openai/text-embedding-3-large` |
| `OPENROUTER_EMBED_URL` | Override base embeddings URL. | `https://openrouter.ai/api/v1/embeddings` |
| `OPENROUTER_HTTP_REFERER` | Optional referer header. | – |
| `OPENROUTER_APP_TITLE` | Optional app title header (defaults to `APP_NAME`). | – |
| `OPENROUTER_TIMEOUT_SECONDS` | Request timeout in seconds. | `30.0` |
| `QDRANT_URL` | Qdrant endpoint (e.g. `http://178.72.149.75:6333`). Required for indexing. | – |
| `QDRANT_COLLECTION_NAME` | Target collection name. | `document_chunks` |
| `QDRANT_BATCH_SIZE` | Upsert batch size. | `64` |
| `MINIO_ENDPOINT` | MinIO endpoint (e.g. `http://178.72.149.75:9000`). Required for uploads. | – |
| `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` | MinIO credentials. | – |
| `MINIO_BUCKET_NAME` | Bucket used for stored documents. | `documents` |
| `MINIO_PUBLIC_ENDPOINT` | Optional public base URL for download links (defaults to endpoint). | – |
| `MINIO_USE_SSL` | Whether to use HTTPS when endpoint omits scheme. | `False` |

## Runtime Notes
- The pipeline logs and continues if embeddings or Qdrant are disabled (missing config) but surfaces errors for partial failures.
- Qdrant collections are created lazily when missing; dimension mismatches are logged.
- Each point uses the chunk's database `chunk_id` as the point id to keep vectors aligned with persisted chunks.
- Documents are uploaded to MinIO under `user-<id>/YYYY/MM/DD/<uuid>.<ext>`; the resulting URL is stored on the document record for downstream downloads.

## Vector Search
- `DocumentVectorManager.search_chunks` embeds the query via OpenRouter and issues a filtered Qdrant search.
- Filters enforce the requesting user (`user_id`) and optionally narrow to specific `document_id` values.
- The service returns ordered results with `DocumentChunk` instances, similarity scores, and payload metadata ready for downstream ranking or display.
