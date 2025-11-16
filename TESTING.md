# API Testing Guide

This guide explains how to test the Finance RAG API with the provided test files.

## Prerequisites

- Python 3.8+ with `httpx` installed
- Access to the hosted API
- Test files in `test_files/` directory:
  - `strafi_2024.pdf`
  - `9115.docx`

## Quick Start

### Option 1: Using Environment Variable

```bash
export API_URL=http://your-hosted-api.com:8000
python3 test_api.py
```

### Option 2: Using Shell Script

```bash
API_URL=http://your-hosted-api.com:8000 ./run_tests.sh
```

### Option 3: Modify Script Directly

Edit `test_api.py` and change the default `API_BASE_URL`:

```python
API_BASE_URL = os.getenv("API_URL", "http://your-hosted-api.com:8000")
```

## What the Tests Do

The test script performs the following operations:

1. **Health Check** - Verifies API is accessible
2. **User Registration** - Creates a test user account
3. **User Login** - Authenticates and gets JWT token
4. **Upload PDF** - Uploads `strafi_2024.pdf` document
5. **Upload DOCX** - Uploads `9115.docx` document
6. **List Documents** - Retrieves all uploaded documents
7. **Create Chat** - Creates a new chat session
8. **RAG Test 1** - General question without documents
9. **RAG Test 2** - Document-specific question with selected documents
10. **RAG Test 3** - Search query to find relevant documents

## Expected Output

The script will output:
- ✅ Success indicators for each step
- 📄 Response data from API calls
- 🤖 Streaming RAG responses with citations
- ⚠️ Warnings for non-critical issues
- ❌ Errors if something fails

## Troubleshooting

### API Not Accessible

If you see "Cannot reach API", check:
- Is the API running?
- Is the URL correct?
- Are there firewall/network restrictions?

### Authentication Errors

If login fails:
- The test user might already exist (this is OK, the script continues)
- Check API logs for detailed error messages

### Document Upload Fails

If document upload fails:
- Check file permissions
- Verify MinIO/S3 is configured correctly
- Check API logs for parsing errors

### Chat Creation Fails

If chat creation fails:
- The script will try to use existing chats
- Ensure at least one prompt exists in the database
- You may need to create a prompt via admin panel first

## Manual Testing

You can also test manually using curl:

```bash
# 1. Register user
curl -X POST http://your-api/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"test","email":"test@example.com","password":"test123","role":"USER"}'

# 2. Login
curl -X POST http://your-api/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"test123"}'

# 3. Upload document (use token from login)
curl -X POST http://your-api/api/v1/document \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@test_files/strafi_2024.pdf"

# 4. Send message to chat
curl -X POST http://your-api/api/v1/chat/1/message \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"content":"Что в этом документе?","documents_ids":[1]}'
```

## Swagger UI

For interactive testing, visit:
- Swagger UI: `http://your-api/docs`
- ReDoc: `http://your-api/redoc`

