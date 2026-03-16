"""
Data Retention Policy Tests
============================
Tests for the data retention feature that:
1. Auto-deletes detailed AI evaluation reports after 2 months (60 days)
2. Retains scores, rank, and 1-2 sentence improvement summary permanently
3. Background cron job runs every 6 hours (tested separately via logs)
4. Admin-only cleanup endpoint

Test Scenarios:
- GET /api/structured-tests/{test_id}/results/{student_id} returns 'retained_only' field
- DELETE /api/structured-tests/cleanup/expired (admin only) returns proper response
- Non-admin users cannot call the cleanup endpoint (403)
- Student results still show improvement_summary, total_score, max_score, percentage
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "Admin@123"
STUDENT_ROLL_NO = "S3"
STUDENT_PASSWORD = "123456"
TEACHER_ROLL_NO = "T001"
TEACHER_PASSWORD = "123456"

# Known test data
TEST_ID = "7f96e624-d12c-4cbf-9649-921d5ca7d6ce"  # Hindi test, standard 6


@pytest.fixture(scope="function")
def api_session():
    """Fresh requests session for each test - no cookie sharing"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def admin_token():
    """Get admin authentication token"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    response = session.post(f"{BASE_URL}/api/admin/login", json={
        "username": ADMIN_USERNAME,
        "password": ADMIN_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip(f"Admin authentication failed: {response.status_code} - {response.text}")


@pytest.fixture(scope="module")
def student_token():
    """Get student authentication token"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    response = session.post(f"{BASE_URL}/api/auth/login", json={
        "roll_no": STUDENT_ROLL_NO,
        "password": STUDENT_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip(f"Student authentication failed: {response.status_code} - {response.text}")


@pytest.fixture(scope="module")
def student_id(student_token):
    """Get student user ID from /api/auth/me"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    response = session.get(f"{BASE_URL}/api/auth/me", headers={
        "Authorization": f"Bearer {student_token}"
    })
    if response.status_code == 200:
        return response.json().get("id")
    pytest.skip(f"Failed to get student ID: {response.status_code}")


@pytest.fixture(scope="module")
def teacher_token():
    """Get teacher authentication token"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    response = session.post(f"{BASE_URL}/api/auth/login", json={
        "roll_no": TEACHER_ROLL_NO,
        "password": TEACHER_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip(f"Teacher authentication failed: {response.status_code}")


class TestDataRetentionResultsAPI:
    """Test GET /api/structured-tests/{test_id}/results/{student_id} for retained_only field"""

    def test_results_api_returns_retained_only_field(self, api_session, student_token, student_id):
        """
        Verify that the results API returns 'retained_only' field.
        For recent tests (< 60 days old), retained_only should be False.
        """
        response = api_session.get(
            f"{BASE_URL}/api/structured-tests/{TEST_ID}/results/{student_id}",
            headers={"Authorization": f"Bearer {student_token}"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify retained_only field exists
        assert "retained_only" in data, f"'retained_only' field missing from response: {data.keys()}"
        
        # For recent tests, retained_only should be False
        assert data["retained_only"] is False, f"Expected retained_only=False for recent tests, got {data['retained_only']}"
        
        print(f"✅ Results API returned retained_only={data['retained_only']}")

    def test_results_api_returns_core_fields_always(self, api_session, student_token, student_id):
        """
        Verify that scores, percentage, improvement_summary are always returned
        regardless of whether detailed results are available.
        """
        response = api_session.get(
            f"{BASE_URL}/api/structured-tests/{TEST_ID}/results/{student_id}",
            headers={"Authorization": f"Bearer {student_token}"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # Core fields that should ALWAYS be present (retained permanently)
        required_fields = ["total_score", "max_score", "percentage", "improvement_summary"]
        
        for field in required_fields:
            assert field in data, f"Required field '{field}' missing from response"
        
        # Verify scores are numeric
        assert isinstance(data["total_score"], (int, float)) or data["total_score"] is None
        assert isinstance(data["max_score"], (int, float)) or data["max_score"] is None
        
        print(f"✅ Core fields present: total_score={data['total_score']}, max_score={data['max_score']}, "
              f"percentage={data['percentage']}, improvement_summary={data.get('improvement_summary', 'N/A')[:50]}...")

    def test_results_available_field_present(self, api_session, student_token, student_id):
        """Verify results_available field is present and True for recent tests"""
        response = api_session.get(
            f"{BASE_URL}/api/structured-tests/{TEST_ID}/results/{student_id}",
            headers={"Authorization": f"Bearer {student_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "results_available" in data, "'results_available' field missing"
        # For recent tests with detailed results
        assert data["results_available"] is True, f"Expected results_available=True for recent tests"
        
        print(f"✅ results_available={data['results_available']}")


class TestCleanupEndpointAdminOnly:
    """Test DELETE /api/structured-tests/cleanup/expired admin-only access"""

    def test_cleanup_endpoint_works_for_admin(self, api_session, admin_token):
        """Admin should be able to call cleanup endpoint successfully"""
        response = api_session.delete(
            f"{BASE_URL}/api/structured-tests/cleanup/expired",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify response format
        assert "message" in data, "'message' field missing from response"
        assert "deleted" in data, "'deleted' field missing from response"
        
        # Verify expected response values
        assert data["message"] == "Retention policy applied", f"Unexpected message: {data['message']}"
        assert isinstance(data["deleted"], int), f"'deleted' should be int, got {type(data['deleted'])}"
        
        # Since no records have expired (all recent), deleted should be 0
        assert data["deleted"] >= 0, f"'deleted' should be >= 0, got {data['deleted']}"
        
        print(f"✅ Admin cleanup successful: message='{data['message']}', deleted={data['deleted']}")

    def test_cleanup_endpoint_returns_403_for_student(self, api_session, student_token):
        """Students should NOT be able to call cleanup endpoint (403 Forbidden)"""
        response = api_session.delete(
            f"{BASE_URL}/api/structured-tests/cleanup/expired",
            headers={"Authorization": f"Bearer {student_token}"}
        )
        
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
        
        print(f"✅ Student correctly denied access (403)")

    def test_cleanup_endpoint_returns_403_for_teacher(self, api_session, teacher_token):
        """Teachers should NOT be able to call cleanup endpoint (403 Forbidden)"""
        response = api_session.delete(
            f"{BASE_URL}/api/structured-tests/cleanup/expired",
            headers={"Authorization": f"Bearer {teacher_token}"}
        )
        
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
        
        print(f"✅ Teacher correctly denied access (403)")

    def test_cleanup_endpoint_returns_401_or_403_unauthenticated(self, api_session):
        """Unauthenticated requests should get 401 or 403 (both are acceptable)"""
        response = api_session.delete(
            f"{BASE_URL}/api/structured-tests/cleanup/expired"
        )
        
        # Both 401 (not authenticated) and 403 (forbidden) are acceptable
        assert response.status_code in [401, 403], f"Expected 401 or 403, got {response.status_code}"
        
        print(f"✅ Unauthenticated request correctly denied ({response.status_code})")


class TestRetainedOnlyBehavior:
    """Test behavior when detailed results have expired (retained_only=True)"""

    def test_results_structure_for_non_expired_test(self, api_session, student_token, student_id):
        """
        For non-expired tests, verify full detailed_results are available.
        This confirms the 'normal' state before retention policy kicks in.
        """
        response = api_session.get(
            f"{BASE_URL}/api/structured-tests/{TEST_ID}/results/{student_id}",
            headers={"Authorization": f"Bearer {student_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Non-expired test should have detailed results
        assert data["retained_only"] is False
        assert data["results_available"] is True
        assert "detailed_results" in data
        assert len(data["detailed_results"]) > 0, "Expected detailed_results to have items"
        
        # Verify detailed result structure
        first_result = data["detailed_results"][0]
        expected_fields = ["question_number", "marks_awarded", "max_marks"]
        for field in expected_fields:
            assert field in first_result, f"Expected '{field}' in detailed_results item"
        
        print(f"✅ Non-expired test has {len(data['detailed_results'])} detailed results")


class TestAPIEndpointsExist:
    """Basic verification that required API endpoints exist and respond"""

    def test_results_endpoint_exists(self, student_token, student_id):
        """Verify results endpoint exists and returns proper structure"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        response = session.get(
            f"{BASE_URL}/api/structured-tests/{TEST_ID}/results/{student_id}",
            headers={"Authorization": f"Bearer {student_token}"}
        )
        
        # Should not be 404
        assert response.status_code != 404, "Results endpoint not found (404)"
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        print(f"✅ Results endpoint exists and returns 200")

    def test_cleanup_endpoint_exists(self, admin_token):
        """Verify cleanup endpoint exists"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        response = session.delete(
            f"{BASE_URL}/api/structured-tests/cleanup/expired",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        # Should not be 404 (method not allowed would be 405)
        assert response.status_code not in [404, 405], "Cleanup endpoint not found or method not allowed"
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        print(f"✅ Cleanup endpoint exists and returns 200")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
