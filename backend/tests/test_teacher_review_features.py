"""
Teacher Review Mode & Student Greeting API Tests
Tests for:
1. GET /api/structured-tests/{test_id}/submissions - returns submissions with student_name
2. POST /api/structured-tests/{test_id}/review/{student_id} - saves teacher overrides
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEACHER_ROLL_NO = "T001"
TEACHER_PASSWORD = "123456"
STUDENT_ROLL_NO = "S3"
STUDENT_PASSWORD = "123456"

# Test data from existing tests
TEST_ID = "7f96e624-d12c-4cbf-9649-921d5ca7d6ce"  # Hindi test with submissions
STUDENT_ID = "908c1c35-288f-4745-8858-f6cac42599eb"  # Krutika


@pytest.fixture(scope="module")
def teacher_token():
    """Get teacher authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "roll_no": TEACHER_ROLL_NO,
        "password": TEACHER_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip("Teacher authentication failed")


@pytest.fixture(scope="module")
def student_token():
    """Get student authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "roll_no": STUDENT_ROLL_NO,
        "password": STUDENT_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip("Student authentication failed")


class TestStudentLogin:
    """Verify student S3 (Krutika) login works and returns correct profile data"""
    
    def test_student_login_success(self):
        """Student S3 should login successfully with correct data"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "roll_no": STUDENT_ROLL_NO,
            "password": STUDENT_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        
        # Verify correct student data
        assert data["user"]["name"] == "Krutika"
        assert data["user"]["role"] == "student"
        assert data["user"]["standard"] == 6
        assert "token" in data


class TestTeacherSubmissionsAPI:
    """Test GET /api/structured-tests/{test_id}/submissions"""
    
    def test_get_submissions_returns_student_name(self, teacher_token):
        """Submissions list should include student_name field"""
        response = requests.get(
            f"{BASE_URL}/api/structured-tests/{TEST_ID}/submissions",
            headers={"Authorization": f"Bearer {teacher_token}"}
        )
        assert response.status_code == 200
        
        submissions = response.json()
        assert isinstance(submissions, list)
        assert len(submissions) > 0
        
        # Check first submitted submission
        submitted = [s for s in submissions if s.get("submitted")]
        assert len(submitted) > 0
        
        sub = submitted[0]
        # Verify student_name is present
        assert "student_name" in sub, "student_name field missing from submission"
        assert sub["student_name"] == "Krutika"
        
        # Verify other required fields
        assert "roll_no" in sub
        assert sub["roll_no"] == "S3"
        assert "total_score" in sub
        assert "max_score" in sub
        assert "evaluation_status" in sub
        assert "teacher_reviewed" in sub
        assert "submitted_at" in sub
    
    def test_submissions_requires_teacher_auth(self, student_token):
        """Students cannot access submissions endpoint"""
        response = requests.get(
            f"{BASE_URL}/api/structured-tests/{TEST_ID}/submissions",
            headers={"Authorization": f"Bearer {student_token}"}
        )
        assert response.status_code == 403


class TestTeacherReviewAPI:
    """Test POST /api/structured-tests/{test_id}/review/{student_id}"""
    
    def test_get_detailed_results_for_teacher(self, teacher_token):
        """Teacher can get detailed evaluation results"""
        response = requests.get(
            f"{BASE_URL}/api/structured-tests/{TEST_ID}/results/{STUDENT_ID}",
            headers={"Authorization": f"Bearer {teacher_token}"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["results_available"] == True
        assert "detailed_results" in data
        assert len(data["detailed_results"]) > 0
        
        # Verify detailed result structure
        result = data["detailed_results"][0]
        assert "question_number" in result
        assert "question_text" in result
        assert "student_answer" in result
        assert "marks_awarded" in result
        assert "max_marks" in result
        assert "feedback" in result
    
    def test_teacher_review_saves_override(self, teacher_token):
        """Teacher can save review with mark overrides"""
        # Submit a review with override - reset Q3 back to 0 marks
        response = requests.post(
            f"{BASE_URL}/api/structured-tests/{TEST_ID}/review/{STUDENT_ID}",
            headers={"Authorization": f"Bearer {teacher_token}"},
            json={
                "overrides": [
                    {"question_number": 3, "marks": 1, "comment": "Partial credit - close answer (TEST)"}
                ]
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "message" in data
        assert "final_score" in data
        assert "max_score" in data
        assert "percentage" in data
        
        # Verify response contains proper structure
        assert data["max_score"] == 16  # Total marks for this test
        assert isinstance(data["final_score"], (int, float))
        assert isinstance(data["percentage"], (int, float))
    
    def test_review_requires_teacher_auth(self, student_token):
        """Students cannot review submissions"""
        response = requests.post(
            f"{BASE_URL}/api/structured-tests/{TEST_ID}/review/{STUDENT_ID}",
            headers={"Authorization": f"Bearer {student_token}"},
            json={"overrides": []}
        )
        assert response.status_code == 403
    
    def test_submission_marked_as_teacher_reviewed(self, teacher_token):
        """After review, submission should be marked as teacher_reviewed"""
        response = requests.get(
            f"{BASE_URL}/api/structured-tests/{TEST_ID}/submissions",
            headers={"Authorization": f"Bearer {teacher_token}"}
        )
        assert response.status_code == 200
        
        submissions = response.json()
        submitted = [s for s in submissions if s.get("submitted")]
        assert len(submitted) > 0
        
        # Find Krutika's submission
        krutika_sub = next((s for s in submitted if s["roll_no"] == "S3"), None)
        assert krutika_sub is not None
        assert krutika_sub["teacher_reviewed"] == True


class TestStructuredTestsListAPI:
    """Test GET /api/structured-tests/list/{subject_id}/{standard}"""
    
    def test_list_tests_returns_active_tests(self, teacher_token):
        """List endpoint returns active tests for subject/standard"""
        # Hindi subject ID for class 6
        subject_id = "841a6c45-d344-4296-9e87-9075ae616534"
        standard = 6
        
        response = requests.get(
            f"{BASE_URL}/api/structured-tests/list/{subject_id}/{standard}",
            headers={"Authorization": f"Bearer {teacher_token}"}
        )
        assert response.status_code == 200
        
        tests = response.json()
        assert isinstance(tests, list)
        assert len(tests) > 0
        
        # Verify test structure
        test = tests[0]
        assert "id" in test
        assert "title" in test
        assert "total_marks" in test
        assert "question_count" in test
        assert "status" in test
        assert test["status"] == "active"


class TestAPIAvailability:
    """Basic API availability tests"""
    
    def test_api_responds(self):
        """API base responds correctly"""
        # Just verify the login endpoint is reachable
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "roll_no": "invalid",
            "password": "invalid"
        })
        # Should return 401 for invalid credentials, not 404 or 500
        assert response.status_code == 401
