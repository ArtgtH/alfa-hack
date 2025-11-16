# Quick API Test Guide

## Test Your Hosted API

### Option 1: Set Environment Variable
```bash
export API_URL=http://your-hosted-api-url:8000
python3 test_api.py
```

### Option 2: Pass URL Directly
```bash
API_URL=http://your-hosted-api-url:8000 python3 test_api.py
```

### Option 3: Use Shell Script
```bash
API_URL=http://your-hosted-api-url:8000 ./run_tests.sh
```

## What Gets Tested

1. ✅ **Health Check** - API availability
2. ✅ **User Registration** - Create test user
3. ✅ **User Login** - Get JWT token
4. ✅ **Upload PDF** - `strafi_2024.pdf` (57KB)
5. ✅ **Upload DOCX** - `9115.docx` (13KB)
6. ✅ **List Documents** - Get all uploaded documents
7. ✅ **Create Chat** - Start chat session
8. ✅ **RAG Test 1** - General question (no documents)
9. ✅ **RAG Test 2** - Document-specific question
10. ✅ **RAG Test 3** - Search query for documents

## Example Output

The script will show:
- ✅ Success indicators
- 📄 API responses
- 🤖 Streaming RAG answers with citations
- ⚠️ Warnings for non-critical issues
- ❌ Errors if something fails

## Manual Test Commands

If you prefer manual testing with curl:

```bash
# Set your API URL
API_URL="http://your-api-url:8000"

# 1. Register
curl -X POST $API_URL/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"test","email":"test@example.com","password":"test123","role":"USER"}'

# 2. Login (save token)
TOKEN=$(curl -s -X POST $API_URL/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"test123"}' | jq -r '.access_token')

# 3. Upload PDF
curl -X POST $API_URL/api/v1/document \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@test_files/strafi_2024.pdf"

# 4. Upload DOCX
curl -X POST $API_URL/api/v1/document \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@test_files/9115.docx"

# 5. Send message (replace CHAT_ID with actual ID)
curl -X POST $API_URL/api/v1/chat/1/message \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"content":"Что содержится в документах?","documents_ids":[1,2]}' \
  --no-buffer
```

## Troubleshooting

- **Connection failed**: Check if API is running and URL is correct
- **401 Unauthorized**: Check if token is valid
- **404 Not Found**: Check if endpoints are correct
- **500 Internal Error**: Check API logs for details

