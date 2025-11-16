# API Endpoints

All application routes live under the FastAPI backend defined in `backend/src/main.py`. Business APIs share the prefix `/api/v1` unless noted otherwise.

## Health
- `GET /health` – readiness probe that runs `SELECT 1` against the database.

## Auth (`/api/v1/auth`)
| Method | Path | Description |
| --- | --- | --- |
| POST | /api/v1/auth/register | Create a user (hashes password, rejects duplicate email/username). |
| POST | /api/v1/auth/login | Verify credentials and issue a JWT access token. |
| GET | /api/v1/auth/me | Return the authenticated user profile. |

## Chat (`/api/v1/chat`)
| Method | Path | Description |
| --- | --- | --- |
| GET | /api/v1/chat | List chats that belong to the current user. |
| GET | /api/v1/chat/{chat_id} | Fetch a single chat plus messages (owner-only). |
| POST | /api/v1/chat | Create a chat from a stored prompt (returns expanded chat, 201). |
| DELETE | /api/v1/chat/{chat_id} | Soft-delete a chat by marking it inactive. |
| POST | /api/v1/chat/{chat_id}/message | Append a user message, persist it, then stream the AI reply via Server-Sent Events. |

## Document (`/api/v1/document`)
| Method | Path | Description |
| --- | --- | --- |
| GET | /api/v1/document | List parsed documents uploaded by the user. |
| GET | /api/v1/document/{document_id} | Retrieve metadata + content for a specific user-owned document. |
| POST | /api/v1/document | Upload a file; backend stores it and runs `process_document`. |
| DELETE | /api/v1/document/{document_id} | Remove a document if the user owns it. |

## Admin Panel
- Web UI served by SQLAdmin at `/admin`. Uses form-based login and the standard FastAPI session middleware to manage admin-only CRUD for users, prompts, chats, messages, and documents.
