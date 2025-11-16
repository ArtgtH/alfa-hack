#!/usr/bin/env python3
"""
Test script for Finance RAG API
Tests document upload and RAG chat functionality
"""

import json
import os
import sys
from pathlib import Path

import httpx

# API base URL - set via environment variable API_URL or change default
# Example: export API_URL=http://your-hosted-api.com
API_BASE_URL = os.getenv("API_URL", "http://localhost:8000")
API_PREFIX = f"{API_BASE_URL}/api/v1"

print(f"🌐 Testing API at: {API_BASE_URL}")
print(f"📡 API Prefix: {API_PREFIX}\n")

# Test files
TEST_FILES_DIR = Path(__file__).parent / "test_files"
PDF_FILE = TEST_FILES_DIR / "strafi_2024.pdf"
DOCX_FILE = TEST_FILES_DIR / "9115.docx"


def print_response(title: str, response: httpx.Response):
    """Print formatted response"""
    print(f"\n{'='*60}")
    print(f"{title}")
    print(f"{'='*60}")
    print(f"Status: {response.status_code}")
    try:
        data = response.json()
        print(f"Response: {json.dumps(data, indent=2, ensure_ascii=False)}")
    except:
        print(f"Response: {response.text[:500]}")
    print()


async def test_api():
    """Run API tests"""
    async with httpx.AsyncClient(timeout=120.0) as client:
        # Check API health first
        print("🏥 Checking API health...")
        try:
            health_response = await client.get(f"{API_BASE_URL}/health")
            if health_response.status_code == 200:
                print(f"✅ API is healthy: {health_response.json()}\n")
            else:
                print(f"⚠️  API health check returned: {health_response.status_code}\n")
        except Exception as e:
            print(f"❌ Cannot reach API at {API_BASE_URL}: {e}")
            print(f"   Please check if the API is running or set API_URL environment variable")
            print(f"   Example: export API_URL=http://your-api-host:8000")
            return
        # Step 1: Register a test user
        print("🔐 Step 1: Registering test user...")
        register_data = {
            "username": "test_user",
            "email": "test@example.com",
            "password": "testpassword123",
            "role": 0,  # Role.USER as IntEnum
        }
        register_response = await client.post(
            f"{API_PREFIX}/auth/register",
            json=register_data
        )
        print_response("Register User", register_response)
        
        if register_response.status_code not in [200, 201, 400, 409]:
            print("❌ Registration failed!")
            return
        
        # Step 2: Login to get token
        print("🔑 Step 2: Logging in...")
        login_data = {
            "email": "test@example.com",
            "password": "testpassword123"
        }
        login_response = await client.post(
            f"{API_PREFIX}/auth/login",
            json=login_data  # Using JSON for login
        )
        print_response("Login", login_response)
        
        if login_response.status_code != 200:
            print("❌ Login failed!")
            return
        
        token_data = login_response.json()
        token = token_data.get("access_token")
        headers = {"Authorization": f"Bearer {token}"}
        
        # Step 3: Upload PDF document
        print("📄 Step 3: Uploading PDF document...")
        if PDF_FILE.exists():
            with open(PDF_FILE, "rb") as f:
                files = {"file": (PDF_FILE.name, f, "application/pdf")}
                upload_response = await client.post(
                    f"{API_PREFIX}/document",
                    headers=headers,
                    files=files
                )
            print_response("Upload PDF", upload_response)
            
            if upload_response.status_code == 200:
                pdf_doc = upload_response.json()
                pdf_doc_id = pdf_doc.get("document_id")
                print(f"✅ PDF uploaded with ID: {pdf_doc_id}")
            else:
                pdf_doc_id = None
                print("❌ PDF upload failed!")
        else:
            print(f"⚠️  PDF file not found: {PDF_FILE}")
            pdf_doc_id = None
        
        # Step 4: Upload DOCX document
        print("📄 Step 4: Uploading DOCX document...")
        if DOCX_FILE.exists():
            with open(DOCX_FILE, "rb") as f:
                files = {"file": (DOCX_FILE.name, f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
                upload_response = await client.post(
                    f"{API_PREFIX}/document",
                    headers=headers,
                    files=files
                )
            print_response("Upload DOCX", upload_response)
            
            if upload_response.status_code == 200:
                docx_doc = upload_response.json()
                docx_doc_id = docx_doc.get("document_id")
                print(f"✅ DOCX uploaded with ID: {docx_doc_id}")
            else:
                docx_doc_id = None
                print("❌ DOCX upload failed!")
        else:
            print(f"⚠️  DOCX file not found: {DOCX_FILE}")
            docx_doc_id = None
        
        # Step 5: List documents
        print("📋 Step 5: Listing all documents...")
        docs_response = await client.get(
            f"{API_PREFIX}/document",
            headers=headers
        )
        print_response("List Documents", docs_response)
        
        # Step 6: Get a prompt ID (we need this to create a chat)
        # For now, let's try to create a chat with prompt_id=1
        # If that fails, we'll handle it
        print("💬 Step 6: Creating a chat...")
        chat_data = {"prompt_id": 1}  # Assuming prompt_id=1 exists
        chat_response = await client.post(
            f"{API_PREFIX}/chat",
            headers=headers,
            json=chat_data
        )
        print_response("Create Chat", chat_response)
        
        if chat_response.status_code == 201:
            chat_info = chat_response.json()
            chat_id = chat_info.get("chat_id")
            print(f"✅ Chat created with ID: {chat_id}")
        else:
            # Try to get existing chats
            print("⚠️  Chat creation failed, trying to get existing chats...")
            chats_response = await client.get(
                f"{API_PREFIX}/chat",
                headers=headers
            )
            print_response("Get Chats", chats_response)
            
            if chats_response.status_code == 200:
                chats = chats_response.json()
                if chats:
                    chat_id = chats[0].get("chat_id")
                    print(f"✅ Using existing chat ID: {chat_id}")
                else:
                    print("❌ No chats available. Cannot test RAG.")
                    return
            else:
                print("❌ Cannot get chats. Cannot test RAG.")
                return
        
        # Step 7: Test RAG with general question (no documents selected)
        print("🤖 Step 7: Testing RAG - General question (no documents)...")
        message_data = {
            "content": "Привет! Расскажи о себе и своих возможностях.",
            "documents_ids": []
        }
        
        async with client.stream(
            "POST",
            f"{API_PREFIX}/chat/{chat_id}/message",
            headers=headers,
            json=message_data
        ) as response:
            print(f"\n{'='*60}")
            print("RAG Response (General Question)")
            print(f"{'='*60}")
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                full_response = ""
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]  # Remove "data: " prefix
                        try:
                            data = json.loads(data_str)
                            if "done" in data:
                                break
                            if "error" in data:
                                print(f"\n[ERROR] {data['error']}\n")
                                break
                            if "content" in data:
                                content = data["content"]
                                print(content, end="", flush=True)
                                full_response += content
                            if "scenario" in data:
                                print(f"\n\n[Scenario: {data['scenario']}]")
                            if "citations" in data:
                                print(f"\n[Citations: {len(data.get('citations', []))} found]")
                        except json.JSONDecodeError:
                            pass
                print("\n")
            else:
                error_text = await response.aread()
                print(f"Error: {error_text.decode()}")
        
        # Step 8: Test RAG with document-specific question (with documents selected)
        if pdf_doc_id or docx_doc_id:
            print("\n🤖 Step 8: Testing RAG - Document-specific question...")
            selected_docs = []
            if pdf_doc_id:
                selected_docs.append(pdf_doc_id)
            if docx_doc_id:
                selected_docs.append(docx_doc_id)
            
            message_data = {
                "content": "Что содержится в этих документах? Кратко опиши основную информацию.",
                "documents_ids": selected_docs
            }
            
            async with client.stream(
                "POST",
                f"{API_PREFIX}/chat/{chat_id}/message",
                headers=headers,
                json=message_data
            ) as response:
                print(f"\n{'='*60}")
                print("RAG Response (Document Question)")
                print(f"{'='*60}")
                print(f"Status: {response.status_code}")
                
                if response.status_code == 200:
                    full_response = ""
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data_str = line[6:]
                            try:
                                data = json.loads(data_str)
                                if "done" in data:
                                    break
                                if "error" in data:
                                    print(f"\n[ERROR] {data['error']}\n")
                                    break
                                if "content" in data:
                                    content = data["content"]
                                    print(content, end="", flush=True)
                                    full_response += content
                                if "scenario" in data:
                                    print(f"\n\n[Scenario: {data['scenario']}]")
                                if "citations" in data:
                                    citations = data.get("citations", [])
                                    print(f"\n\n[Citations: {len(citations)} found]")
                                    for i, cit in enumerate(citations[:3], 1):
                                        print(f"  {i}. {cit.get('filename', 'Unknown')} (score: {cit.get('score', 0):.3f})")
                            except json.JSONDecodeError:
                                pass
                    print("\n")
                else:
                    error_text = await response.aread()
                    print(f"Error: {error_text.decode()}")
        
        # Step 9: Test search query (finding documents)
        print("\n🔍 Step 9: Testing RAG - Search for documents...")
        message_data = {
            "content": "Найди документы, связанные с отчетностью или финансовыми данными.",
            "documents_ids": []
        }
        
        async with client.stream(
            "POST",
            f"{API_PREFIX}/chat/{chat_id}/message",
            headers=headers,
            json=message_data
        ) as response:
            print(f"\n{'='*60}")
            print("RAG Response (Search Query)")
            print(f"{'='*60}")
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        try:
                            data = json.loads(data_str)
                            if "done" in data:
                                break
                            if "error" in data:
                                print(f"\n[ERROR] {data['error']}\n")
                                break
                            if "content" in data:
                                print(data["content"], end="", flush=True)
                            if "scenario" in data:
                                print(f"\n\n[Scenario: {data['scenario']}]")
                        except json.JSONDecodeError:
                            pass
                print("\n")
        
        print("\n" + "="*60)
        print("✅ Testing completed!")
        print("="*60)


if __name__ == "__main__":
    import asyncio
    try:
        asyncio.run(test_api())
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

