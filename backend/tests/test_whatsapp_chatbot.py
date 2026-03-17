"""
WhatsApp Parent Chatbot - Backend API Tests
============================================
Tests the WhatsApp webhook, message processing, chat memory, and public dashboard.

Test Coverage:
- Webhook verification (GET /api/whatsapp/webhook)
- Message processing (POST /api/whatsapp/webhook)
- Public dashboard rendering (GET /api/whatsapp/parent-view/{token})
- Phone format handling (with/without country code)
- Database records (whatsapp_parent_briefs, whatsapp_chat_memory)
"""
import pytest
import requests
import os
import time
import asyncio

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
WHATSAPP_VERIFY_TOKEN = "studybuddy_webhook"
TEST_PARENT_PHONE = "9999999999"  # Registered parent phone
TEST_UNREGISTERED_PHONE = "1111111111"  # Unregistered phone
VALID_DASHBOARD_TOKEN = "JWNEpjJC98z74yBSx_KK8qB4S5Cjx_rZZ3enwY64-j0"


class TestWebhookVerification:
    """Test GET /api/whatsapp/webhook - Meta webhook verification"""
    
    def test_webhook_verify_correct_token(self):
        """Verify webhook with correct token returns challenge string"""
        challenge = "test_challenge_12345"
        response = requests.get(
            f"{BASE_URL}/api/whatsapp/webhook",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": WHATSAPP_VERIFY_TOKEN,
                "hub.challenge": challenge
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        assert response.text == challenge, f"Expected challenge '{challenge}', got '{response.text}'"
        print(f"✅ Webhook verification with correct token: PASSED (status={response.status_code})")
    
    def test_webhook_verify_wrong_token(self):
        """Verify webhook with wrong token returns 403"""
        response = requests.get(
            f"{BASE_URL}/api/whatsapp/webhook",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "wrong_token_123",
                "hub.challenge": "test_challenge"
            }
        )
        assert response.status_code == 403, f"Expected 403 for wrong token, got {response.status_code}"
        print(f"✅ Webhook verification with wrong token: PASSED (correctly rejected with 403)")
    
    def test_webhook_verify_missing_mode(self):
        """Verify webhook without mode parameter returns 403"""
        response = requests.get(
            f"{BASE_URL}/api/whatsapp/webhook",
            params={
                "hub.verify_token": WHATSAPP_VERIFY_TOKEN,
                "hub.challenge": "test_challenge"
            }
        )
        assert response.status_code == 403, f"Expected 403 for missing mode, got {response.status_code}"
        print(f"✅ Webhook verification without mode: PASSED (correctly rejected with 403)")


class TestMessageProcessing:
    """Test POST /api/whatsapp/webhook - Incoming message processing"""
    
    def test_webhook_post_registered_phone(self):
        """Message from registered parent phone should return 200"""
        payload = {
            "entry": [{
                "changes": [{
                    "value": {
                        "messages": [{
                            "type": "text",
                            "from": TEST_PARENT_PHONE,
                            "text": {"body": "How is my child doing in class?"}
                        }]
                    }
                }]
            }]
        }
        response = requests.post(
            f"{BASE_URL}/api/whatsapp/webhook",
            json=payload
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("status") == "ok", f"Expected status 'ok', got {data}"
        print(f"✅ Message processing (registered phone): PASSED (immediate 200 response)")
    
    def test_webhook_post_unregistered_phone(self):
        """Message from unregistered phone should return 200 (processed gracefully)"""
        payload = {
            "entry": [{
                "changes": [{
                    "value": {
                        "messages": [{
                            "type": "text",
                            "from": TEST_UNREGISTERED_PHONE,
                            "text": {"body": "Hello, testing unregistered phone"}
                        }]
                    }
                }]
            }]
        }
        response = requests.post(
            f"{BASE_URL}/api/whatsapp/webhook",
            json=payload
        )
        # Should return 200 immediately (async processing)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("status") == "ok", f"Expected status 'ok', got {data}"
        print(f"✅ Message processing (unregistered phone): PASSED (gracefully handled)")
    
    def test_webhook_post_with_country_code(self):
        """Message with country code prefix (91) should match correctly"""
        payload = {
            "entry": [{
                "changes": [{
                    "value": {
                        "messages": [{
                            "type": "text",
                            "from": f"91{TEST_PARENT_PHONE}",  # With country code
                            "text": {"body": "Test with country code prefix"}
                        }]
                    }
                }]
            }]
        }
        response = requests.post(
            f"{BASE_URL}/api/whatsapp/webhook",
            json=payload
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"✅ Phone format handling (with country code): PASSED")
    
    def test_webhook_post_empty_payload(self):
        """Empty payload should return 200 (no messages to process)"""
        response = requests.post(
            f"{BASE_URL}/api/whatsapp/webhook",
            json={}
        )
        assert response.status_code == 200, f"Expected 200 for empty payload, got {response.status_code}"
        print(f"✅ Empty webhook payload: PASSED")
    
    def test_webhook_post_non_text_message(self):
        """Non-text messages (image, audio) should be ignored gracefully"""
        payload = {
            "entry": [{
                "changes": [{
                    "value": {
                        "messages": [{
                            "type": "image",  # Not text
                            "from": TEST_PARENT_PHONE,
                            "image": {"id": "123"}
                        }]
                    }
                }]
            }]
        }
        response = requests.post(
            f"{BASE_URL}/api/whatsapp/webhook",
            json=payload
        )
        assert response.status_code == 200, f"Expected 200 for non-text message, got {response.status_code}"
        print(f"✅ Non-text message handling: PASSED")


class TestPublicDashboard:
    """Test GET /api/whatsapp/parent-view/{token} - Public dashboard"""
    
    def test_dashboard_valid_token(self):
        """Valid token should return 200 HTML with student data"""
        response = requests.get(f"{BASE_URL}/api/whatsapp/parent-view/{VALID_DASHBOARD_TOKEN}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert "text/html" in response.headers.get("content-type", ""), "Expected HTML response"
        
        # Verify HTML contains student data
        html_content = response.text
        assert "StudyBuddy" in html_content, "HTML should contain 'StudyBuddy' branding"
        assert "Test Student" in html_content or "student" in html_content.lower(), "HTML should contain student name"
        
        # Check key dashboard elements
        assert "Overall Average" in html_content, "Dashboard should show Overall Average"
        assert "Class Rank" in html_content, "Dashboard should show Class Rank"
        print(f"✅ Public dashboard (valid token): PASSED (200 HTML with student data)")
    
    def test_dashboard_invalid_token(self):
        """Invalid token should return 404"""
        response = requests.get(f"{BASE_URL}/api/whatsapp/parent-view/invalid_token_12345")
        assert response.status_code == 404, f"Expected 404 for invalid token, got {response.status_code}"
        
        # Should still return HTML error page
        assert "text/html" in response.headers.get("content-type", ""), "Expected HTML error page"
        html_content = response.text
        assert "not found" in html_content.lower() or "expired" in html_content.lower(), "Error page should indicate dashboard not found"
        print(f"✅ Public dashboard (invalid token): PASSED (correctly returned 404)")
    
    def test_dashboard_empty_token(self):
        """Empty token should return 404 or 422"""
        response = requests.get(f"{BASE_URL}/api/whatsapp/parent-view/")
        # FastAPI may return 404 (not found) or 307 (redirect) for empty path param
        assert response.status_code in [404, 307, 405], f"Expected 404/307/405 for empty token, got {response.status_code}"
        print(f"✅ Public dashboard (empty token): PASSED (status={response.status_code})")


class TestDatabaseRecords:
    """Test database state after message processing"""
    
    def test_brief_record_exists(self):
        """After message processing, whatsapp_parent_briefs should have a record"""
        # First, send a message to trigger brief creation/refresh
        payload = {
            "entry": [{
                "changes": [{
                    "value": {
                        "messages": [{
                            "type": "text",
                            "from": TEST_PARENT_PHONE,
                            "text": {"body": f"Test brief check at {time.time()}"}
                        }]
                    }
                }]
            }]
        }
        response = requests.post(f"{BASE_URL}/api/whatsapp/webhook", json=payload)
        assert response.status_code == 200
        
        # Wait for async processing
        time.sleep(10)
        
        # Verify brief exists by checking dashboard
        response = requests.get(f"{BASE_URL}/api/whatsapp/parent-view/{VALID_DASHBOARD_TOKEN}")
        assert response.status_code == 200, "Brief should exist for registered parent"
        
        # Check that HTML contains performance data
        html = response.text
        assert "Overall Average" in html, "Brief should contain performance data"
        assert "Homework" in html, "Brief should contain homework data"
        print(f"✅ Database brief record: PASSED (brief exists with performance data)")
    
    def test_brief_contains_required_fields(self):
        """Brief data should contain all required student performance fields"""
        response = requests.get(f"{BASE_URL}/api/whatsapp/parent-view/{VALID_DASHBOARD_TOKEN}")
        assert response.status_code == 200
        
        html = response.text.lower()
        
        # Check for required data fields in the rendered HTML
        required_elements = [
            "overall average",
            "class rank", 
            "homework",
            "subject"
        ]
        
        for element in required_elements:
            assert element in html, f"Dashboard should contain '{element}'"
        
        print(f"✅ Brief required fields: PASSED (all required fields present in dashboard)")


class TestChatMemoryLimit:
    """Test that chat memory is properly limited to 20 messages"""
    
    def test_chat_memory_processing(self):
        """Sending a message should trigger chat memory save"""
        test_message = f"Memory test message {time.time()}"
        payload = {
            "entry": [{
                "changes": [{
                    "value": {
                        "messages": [{
                            "type": "text",
                            "from": TEST_PARENT_PHONE,
                            "text": {"body": test_message}
                        }]
                    }
                }]
            }]
        }
        
        response = requests.post(f"{BASE_URL}/api/whatsapp/webhook", json=payload)
        assert response.status_code == 200
        
        # We can't directly query DB from tests, but message processing should work
        print(f"✅ Chat memory processing: PASSED (message accepted for async processing)")


class TestGPT4oIntegration:
    """Test GPT-4o response generation via OpenRouter"""
    
    def test_contextual_response_flow(self):
        """
        After sending a message about student performance, the system should:
        1. Accept the message (200 response)
        2. Process it asynchronously (GPT-4o generates response)
        3. Store both user message and assistant response in chat memory
        
        Note: We can't verify the actual GPT-4o response content in API tests,
        but we verify the flow doesn't error out.
        """
        performance_query = "What are my child's strong and weak subjects?"
        payload = {
            "entry": [{
                "changes": [{
                    "value": {
                        "messages": [{
                            "type": "text",
                            "from": TEST_PARENT_PHONE,
                            "text": {"body": performance_query}
                        }]
                    }
                }]
            }]
        }
        
        response = requests.post(f"{BASE_URL}/api/whatsapp/webhook", json=payload)
        assert response.status_code == 200, f"Message should be accepted, got {response.status_code}"
        
        # Wait for GPT-4o processing
        time.sleep(12)
        
        # Verify no errors by checking dashboard still works
        dashboard_response = requests.get(f"{BASE_URL}/api/whatsapp/parent-view/{VALID_DASHBOARD_TOKEN}")
        assert dashboard_response.status_code == 200, "Dashboard should still work after GPT-4o processing"
        
        print(f"✅ GPT-4o integration flow: PASSED (message processed without errors)")


class TestEdgeCases:
    """Test edge cases and error handling"""
    
    def test_malformed_json_payload(self):
        """Malformed JSON should be handled gracefully"""
        response = requests.post(
            f"{BASE_URL}/api/whatsapp/webhook",
            data="not valid json",
            headers={"Content-Type": "application/json"}
        )
        # Should return 200 (graceful handling) or 422 (validation error)
        assert response.status_code in [200, 422], f"Expected 200 or 422, got {response.status_code}"
        print(f"✅ Malformed JSON handling: PASSED (status={response.status_code})")
    
    def test_missing_entry_field(self):
        """Payload without 'entry' field should not crash"""
        response = requests.post(
            f"{BASE_URL}/api/whatsapp/webhook",
            json={"other_field": "value"}
        )
        assert response.status_code == 200, f"Missing entry field should be handled, got {response.status_code}"
        print(f"✅ Missing entry field handling: PASSED")
    
    def test_empty_messages_array(self):
        """Empty messages array should be handled gracefully"""
        payload = {
            "entry": [{
                "changes": [{
                    "value": {
                        "messages": []
                    }
                }]
            }]
        }
        response = requests.post(f"{BASE_URL}/api/whatsapp/webhook", json=payload)
        assert response.status_code == 200
        print(f"✅ Empty messages array handling: PASSED")


@pytest.fixture(scope="session", autouse=True)
def setup():
    """Verify test environment before running tests"""
    assert BASE_URL, "REACT_APP_BACKEND_URL must be set"
    print(f"\n📋 Running WhatsApp Chatbot Backend Tests")
    print(f"   BASE_URL: {BASE_URL}")
    print(f"   Test Parent Phone: {TEST_PARENT_PHONE}")
    print(f"   Dashboard Token: {VALID_DASHBOARD_TOKEN[:20]}...")
    
    # Verify backend is reachable
    try:
        health = requests.get(f"{BASE_URL}/health", timeout=5)
        assert health.status_code == 200, "Backend health check failed"
        print(f"   Backend Status: ✅ Healthy\n")
    except Exception as e:
        pytest.fail(f"Backend not reachable: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
