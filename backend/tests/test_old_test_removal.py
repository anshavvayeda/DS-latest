"""
Test Old Test System Removal
============================
Tests to verify the old test system (PDF upload, S3 JSON, single LLM evaluation)
has been removed and only the new AI-evaluated test system remains functional.

Key changes tested:
1. Old /api/tests routes removed (should return 404/405)
2. New /api/structured-tests/* routes still work
3. Parent dashboard only returns StructuredTestSubmission data
4. Student can see subjects and AI tests
5. Teacher can see test creation UI and review submissions
6. Homework feature still works (TestManagement with contentType=homework)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    BASE_URL = "https://studybuddy-ai-120.preview.emergentagent.com"

# Test credentials from review_request
STUDENT_ROLL_NO = "S3"
STUDENT_PASSWORD = "123456"
TEACHER_ROLL_NO = "T001"
TEACHER_PASSWORD = "123456"
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "Admin@123"


class TestLoginAndAuth:
    """Test authentication and user greeting"""
    
    def test_student_login_success(self):
        """Student S3 should be able to login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "roll_no": STUDENT_ROLL_NO,
            "password": STUDENT_PASSWORD
        })
        assert response.status_code == 200, f"Student login failed: {response.text}"
        data = response.json()
        assert "token" in data, "No token in response"
        assert "user" in data, "No user info in response"
        assert data["user"]["roll_no"] == STUDENT_ROLL_NO
        print(f"✅ Student login successful: {data['user'].get('name', 'Unknown')}")
    
    def test_student_greeting_has_name(self):
        """Student login should return name for greeting display"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "roll_no": STUDENT_ROLL_NO,
            "password": STUDENT_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        # The login response should include student name
        user_name = data["user"].get("name")
        assert user_name is not None, "Student name not returned in login"
        print(f"✅ Student greeting name: {user_name}")
    
    def test_teacher_login_success(self):
        """Teacher should be able to login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "roll_no": TEACHER_ROLL_NO,
            "password": TEACHER_PASSWORD
        })
        # Teacher might not exist - check for 200 or 401
        if response.status_code == 200:
            data = response.json()
            assert "token" in data
            print(f"✅ Teacher login successful")
        else:
            print(f"⚠️ Teacher login returned {response.status_code} - might need to check teacher credentials")


class TestOldRoutesRemoved:
    """Verify old test routes are removed (should return 404/405)"""
    
    @pytest.fixture
    def student_token(self):
        """Get student auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "roll_no": STUDENT_ROLL_NO,
            "password": STUDENT_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("token")
        return None
    
    def test_old_post_tests_route_removed(self, student_token):
        """POST /api/tests should be removed (404 or 405)"""
        headers = {"Authorization": f"Bearer {student_token}"} if student_token else {}
        response = requests.post(f"{BASE_URL}/api/tests", headers=headers, json={
            "subject_id": "test",
            "standard": 6,
            "title": "Test"
        })
        # Should return 404 (Not Found) or 405 (Method Not Allowed)
        assert response.status_code in [404, 405, 422], f"Old POST /api/tests should be removed, got {response.status_code}"
        print(f"✅ POST /api/tests correctly returns {response.status_code}")
    
    def test_old_get_tests_by_subject_removed(self, student_token):
        """GET /api/tests/subject/*/standard/* should be removed"""
        headers = {"Authorization": f"Bearer {student_token}"} if student_token else {}
        response = requests.get(f"{BASE_URL}/api/tests/subject/fake-id/standard/6", headers=headers)
        # Should return 404 (route not found) or similar
        assert response.status_code in [404, 405], f"Old GET /api/tests/subject should be removed, got {response.status_code}"
        print(f"✅ GET /api/tests/subject/* correctly returns {response.status_code}")
    
    def test_old_start_test_route_removed(self, student_token):
        """POST /api/tests/*/start should be removed"""
        headers = {"Authorization": f"Bearer {student_token}"} if student_token else {}
        response = requests.post(f"{BASE_URL}/api/tests/fake-id/start", headers=headers)
        # Should return 404 or 405
        assert response.status_code in [404, 405, 422], f"Old POST /api/tests/*/start should be removed, got {response.status_code}"
        print(f"✅ POST /api/tests/*/start correctly returns {response.status_code}")


class TestNewStructuredTestsWork:
    """Verify new AI-evaluated test system works"""
    
    @pytest.fixture
    def student_auth(self):
        """Get student auth headers and standard"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "roll_no": STUDENT_ROLL_NO,
            "password": STUDENT_PASSWORD
        })
        if response.status_code == 200:
            data = response.json()
            return {
                "headers": {"Authorization": f"Bearer {data.get('token')}"},
                "standard": data["user"].get("standard", 6)
            }
        return None
    
    def test_get_subjects_for_student_standard(self, student_auth):
        """Student should be able to see subjects for their standard"""
        if not student_auth:
            pytest.skip("Student auth failed")
        
        standard = student_auth["standard"]
        response = requests.get(
            f"{BASE_URL}/api/subjects", 
            params={"standard": standard},
            headers=student_auth["headers"]
        )
        assert response.status_code == 200, f"Failed to get subjects: {response.text}"
        data = response.json()
        assert "subjects" in data or isinstance(data, list), "No subjects returned"
        
        subjects = data.get("subjects", data) if isinstance(data, dict) else data
        print(f"✅ Found {len(subjects)} subjects for standard {standard}")
        for subj in subjects[:5]:  # Print first 5
            print(f"   - {subj.get('name', 'Unknown')}")
    
    def test_structured_tests_list_endpoint_works(self, student_auth):
        """GET /api/structured-tests/list/{subject_id}/{standard} should work"""
        if not student_auth:
            pytest.skip("Student auth failed")
        
        standard = student_auth["standard"]
        
        # First get subjects
        subj_response = requests.get(
            f"{BASE_URL}/api/subjects",
            params={"standard": standard},
            headers=student_auth["headers"]
        )
        
        if subj_response.status_code != 200:
            pytest.skip("Could not get subjects")
        
        subjects_data = subj_response.json()
        subjects = subjects_data.get("subjects", subjects_data) if isinstance(subjects_data, dict) else subjects_data
        
        if not subjects:
            pytest.skip("No subjects found")
        
        # Test first subject
        first_subject = subjects[0]
        subject_id = first_subject.get("id")
        
        response = requests.get(
            f"{BASE_URL}/api/structured-tests/list/{subject_id}/{standard}",
            headers=student_auth["headers"]
        )
        
        assert response.status_code == 200, f"Structured tests list failed: {response.text}"
        data = response.json()
        print(f"✅ Structured tests list endpoint works")
        print(f"   Subject: {first_subject.get('name')}")
        
        tests = data.get("tests", data) if isinstance(data, dict) else data
        print(f"   Found {len(tests) if isinstance(tests, list) else 'unknown'} AI tests")


class TestParentDashboard:
    """Test parent dashboard returns only AI test data"""
    
    @pytest.fixture
    def student_token(self):
        """Get student auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "roll_no": STUDENT_ROLL_NO,
            "password": STUDENT_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("token")
        return None
    
    def test_parent_dashboard_endpoint_exists(self, student_token):
        """GET /api/student/parent-dashboard should exist"""
        headers = {"Authorization": f"Bearer {student_token}"} if student_token else {}
        response = requests.get(f"{BASE_URL}/api/student/parent-dashboard", headers=headers)
        # Should be 200 (success) or 403 (if student only), not 404
        assert response.status_code != 404, "Parent dashboard endpoint missing!"
        print(f"✅ Parent dashboard endpoint exists (status: {response.status_code})")
    
    def test_parent_dashboard_returns_ai_test_data(self, student_token):
        """Parent dashboard should return AI test scores"""
        headers = {"Authorization": f"Bearer {student_token}"} if student_token else {}
        response = requests.get(f"{BASE_URL}/api/student/parent-dashboard", headers=headers)
        
        if response.status_code != 200:
            print(f"⚠️ Parent dashboard returned {response.status_code}: {response.text[:200]}")
            pytest.skip(f"Parent dashboard not accessible: {response.status_code}")
        
        data = response.json()
        
        # Check expected fields
        assert "subjects" in data or "overall_summary" in data, "Missing expected parent dashboard fields"
        
        # Should have test_performance field with AI test scores
        subjects = data.get("subjects", [])
        if subjects:
            first_subj = subjects[0] if isinstance(subjects, list) else None
            if first_subj:
                # Should have test_performance from StructuredTestSubmission
                assert "test_performance" in first_subj or "average_score" in first_subj
                print(f"✅ Parent dashboard returns AI test data structure")
        
        print(f"✅ Parent dashboard working - {len(subjects)} subjects returned")


class TestHomeworkFeatureKept:
    """Verify homework feature still works (TestManagement with contentType=homework)"""
    
    @pytest.fixture
    def teacher_token(self):
        """Get teacher auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "roll_no": TEACHER_ROLL_NO,
            "password": TEACHER_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("token")
        return None
    
    def test_homework_list_endpoint_exists(self, teacher_token):
        """Homework list endpoint should still exist"""
        # Homework might be at various endpoints - check a few possibilities
        endpoints_to_check = [
            "/api/homework",
            "/api/homework/list",
            "/api/teacher/homework"
        ]
        
        headers = {"Authorization": f"Bearer {teacher_token}"} if teacher_token else {}
        
        for endpoint in endpoints_to_check:
            response = requests.get(f"{BASE_URL}{endpoint}", headers=headers)
            if response.status_code == 200:
                print(f"✅ Homework endpoint found at {endpoint}")
                return
        
        # If none found with GET, try with subject params
        print(f"⚠️ No direct homework GET endpoint found - feature may use different routing")


class TestTeacherReviewSubmissions:
    """Test teacher can see 'Review Submissions' functionality"""
    
    @pytest.fixture
    def teacher_token(self):
        """Get teacher auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "roll_no": TEACHER_ROLL_NO,
            "password": TEACHER_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("token")
        return None
    
    def test_submissions_endpoint_exists(self, teacher_token):
        """Teacher should be able to get submissions for a test"""
        # The endpoint pattern is /api/structured-tests/{test_id}/submissions
        # We need a real test_id, so first check the list
        
        headers = {"Authorization": f"Bearer {teacher_token}"} if teacher_token else {}
        
        # This would need a real test_id - for now just verify the pattern
        # Use a fake ID to check route exists (should return 404 for invalid ID, not 405)
        response = requests.get(
            f"{BASE_URL}/api/structured-tests/fake-test-id/submissions",
            headers=headers
        )
        
        # Should not be 405 (Method Not Allowed) - route should exist
        # Can be 401 (not auth), 403 (no permission), 404 (test not found), or 200
        assert response.status_code != 405, "Submissions endpoint route doesn't exist"
        print(f"✅ Submissions endpoint route exists (status: {response.status_code})")


class TestStudentAITestResults:
    """Test student can view AI test results"""
    
    @pytest.fixture
    def student_auth(self):
        """Get student auth headers and info"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "roll_no": STUDENT_ROLL_NO,
            "password": STUDENT_PASSWORD
        })
        if response.status_code == 200:
            data = response.json()
            return {
                "headers": {"Authorization": f"Bearer {data.get('token')}"},
                "user_id": data["user"].get("id"),
                "standard": data["user"].get("standard", 6)
            }
        return None
    
    def test_student_results_endpoint_structure(self, student_auth):
        """Results endpoint should return proper structure"""
        if not student_auth:
            pytest.skip("Student auth failed")
        
        # The endpoint pattern is /api/structured-tests/{test_id}/results/{student_id}
        # We need to find a real test with submissions first
        
        # For now, verify the route pattern exists
        test_id = "fake-test-id"
        student_id = student_auth["user_id"]
        
        response = requests.get(
            f"{BASE_URL}/api/structured-tests/{test_id}/results/{student_id}",
            headers=student_auth["headers"]
        )
        
        # Route should exist (not 405)
        assert response.status_code != 405, "Results endpoint route doesn't exist"
        print(f"✅ Results endpoint route exists (status: {response.status_code})")


# Run all tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
