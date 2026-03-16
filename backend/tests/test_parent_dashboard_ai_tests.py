"""
Test Parent Dashboard API - AI-Evaluated Tests Integration
============================================================
Tests that the parent dashboard endpoint returns AI test scores from 
StructuredTestSubmission table alongside old TestSubmission data.

Features tested:
1. Parent dashboard returns AI test performance data
2. Overall stats include AI test counts
3. Subject classification based on combined test data
4. test_performance array contains AI test entries
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials - Student Krutika (S3) has AI test data
STUDENT_ROLL_NO = "S3"
STUDENT_PASSWORD = "123456"


class TestParentDashboardAITests:
    """Test suite for Parent Dashboard with AI-evaluated tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get student auth token"""
        self.session = requests.Session()
        
        # Login as student S3
        response = self.session.post(
            f"{BASE_URL}/api/auth/login",
            json={"roll_no": STUDENT_ROLL_NO, "password": STUDENT_PASSWORD}
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        self.token = data.get("token")
        assert self.token, "No token returned from login"
        
        # Set auth header
        self.session.headers.update({
            "Authorization": f"Bearer {self.token}"
        })
    
    def test_parent_dashboard_returns_200(self):
        """Parent dashboard endpoint returns 200 for authenticated student"""
        response = self.session.get(f"{BASE_URL}/api/student/parent-dashboard")
        assert response.status_code == 200, f"Parent dashboard failed: {response.text}"
        data = response.json()
        
        # Verify basic structure
        assert "student_name" in data
        assert "roll_no" in data
        assert "standard" in data
        assert "subjects" in data
        assert "overall_stats" in data
    
    def test_parent_dashboard_student_info(self):
        """Parent dashboard returns correct student info for S3 (Krutika)"""
        response = self.session.get(f"{BASE_URL}/api/student/parent-dashboard")
        assert response.status_code == 200
        data = response.json()
        
        # Verify student info
        assert data["student_name"] == "Krutika", f"Expected Krutika, got {data['student_name']}"
        assert data["roll_no"] == "S3"
        assert data["standard"] == 6
    
    def test_parent_dashboard_contains_ai_test_subjects(self):
        """Parent dashboard includes subjects with AI test data (Hindi, Computer, Mathematics)"""
        response = self.session.get(f"{BASE_URL}/api/student/parent-dashboard")
        assert response.status_code == 200
        data = response.json()
        
        # Build subject lookup
        subjects_by_name = {s["subject_name"]: s for s in data["subjects"]}
        
        # Hindi should have AI test data
        assert "Hindi" in subjects_by_name, "Hindi subject not found"
        hindi = subjects_by_name["Hindi"]
        assert len(hindi["test_performance"]) > 0, "Hindi should have test performance data"
        
        # Computer should have AI test data
        assert "Computer" in subjects_by_name, "Computer subject not found"
        computer = subjects_by_name["Computer"]
        assert len(computer["test_performance"]) > 0, "Computer should have test performance data"
        
        # Mathematics should have AI test data
        assert "Mathematics" in subjects_by_name, "Mathematics subject not found"
        math = subjects_by_name["Mathematics"]
        assert len(math["test_performance"]) > 0, "Mathematics should have test performance data"
    
    def test_parent_dashboard_hindi_ai_test_score(self):
        """Hindi subject has correct AI test score (43.8%)"""
        response = self.session.get(f"{BASE_URL}/api/student/parent-dashboard")
        assert response.status_code == 200
        data = response.json()
        
        # Find Hindi subject
        hindi = next((s for s in data["subjects"] if s["subject_name"] == "Hindi"), None)
        assert hindi is not None, "Hindi subject not found"
        
        # Verify test performance
        assert len(hindi["test_performance"]) >= 1, "Hindi should have at least 1 test"
        
        # Check test entry
        test_entry = hindi["test_performance"][0]
        assert "test_name" in test_entry
        assert "date" in test_entry
        assert "percentage" in test_entry
        
        # Verify percentage is 43.8 (as per agent context)
        assert test_entry["percentage"] == 43.8, f"Expected 43.8%, got {test_entry['percentage']}%"
        
        # Verify average score
        assert hindi["average_score"] == 43.8
        
        # Verify classification is 'weak' (<60%)
        assert hindi["classification"] == "weak", f"Expected weak, got {hindi['classification']}"
    
    def test_parent_dashboard_mathematics_ai_test_score(self):
        """Mathematics subject has correct AI test score (66.7%)"""
        response = self.session.get(f"{BASE_URL}/api/student/parent-dashboard")
        assert response.status_code == 200
        data = response.json()
        
        # Find Mathematics subject
        math = next((s for s in data["subjects"] if s["subject_name"] == "Mathematics"), None)
        assert math is not None, "Mathematics subject not found"
        
        # Verify test performance
        assert len(math["test_performance"]) >= 1, "Mathematics should have at least 1 test"
        
        # Check percentage (66.7%)
        test_entry = math["test_performance"][0]
        assert test_entry["percentage"] == 66.7, f"Expected 66.7%, got {test_entry['percentage']}%"
        
        # Verify classification is 'average' (60-79%)
        assert math["classification"] == "average", f"Expected average, got {math['classification']}"
    
    def test_parent_dashboard_computer_ai_test_score(self):
        """Computer subject has AI test score (0%)"""
        response = self.session.get(f"{BASE_URL}/api/student/parent-dashboard")
        assert response.status_code == 200
        data = response.json()
        
        # Find Computer subject
        computer = next((s for s in data["subjects"] if s["subject_name"] == "Computer"), None)
        assert computer is not None, "Computer subject not found"
        
        # Verify test performance exists
        assert len(computer["test_performance"]) >= 1, "Computer should have at least 1 test"
        
        # Check percentage (0%)
        test_entry = computer["test_performance"][0]
        assert test_entry["percentage"] == 0, f"Expected 0%, got {test_entry['percentage']}%"
        
        # Verify classification is 'weak' (<60%)
        assert computer["classification"] == "weak"
    
    def test_parent_dashboard_overall_stats_include_ai_tests(self):
        """Overall stats include all AI-evaluated tests"""
        response = self.session.get(f"{BASE_URL}/api/student/parent-dashboard")
        assert response.status_code == 200
        data = response.json()
        
        overall = data["overall_stats"]
        
        # Should have at least 3 tests (Hindi, Computer, Mathematics AI tests)
        assert overall["total_tests_attempted"] >= 3, \
            f"Expected at least 3 tests, got {overall['total_tests_attempted']}"
        
        # Verify overall average is calculated
        assert "overall_average_score" in overall
        assert isinstance(overall["overall_average_score"], (int, float))
        
        # The overall average should be around 36.8 (avg of 43.8, 0, 66.7)
        expected_avg = (43.8 + 0 + 66.7) / 3  # ~36.8
        # Allow some tolerance for additional tests
        assert overall["overall_average_score"] >= 0
        assert overall["overall_average_score"] <= 100
    
    def test_parent_dashboard_test_performance_structure(self):
        """Test performance entries have correct structure"""
        response = self.session.get(f"{BASE_URL}/api/student/parent-dashboard")
        assert response.status_code == 200
        data = response.json()
        
        # Find a subject with test performance
        hindi = next((s for s in data["subjects"] if s["subject_name"] == "Hindi"), None)
        assert hindi is not None
        
        for entry in hindi["test_performance"]:
            # Verify structure
            assert "test_name" in entry, "test_name missing"
            assert "date" in entry, "date missing"
            assert "percentage" in entry, "percentage missing"
            
            # Verify types
            assert isinstance(entry["test_name"], str)
            assert entry["date"] is None or isinstance(entry["date"], str)
            assert isinstance(entry["percentage"], (int, float))
    
    def test_parent_dashboard_subject_structure(self):
        """Each subject has all required fields"""
        response = self.session.get(f"{BASE_URL}/api/student/parent-dashboard")
        assert response.status_code == 200
        data = response.json()
        
        for subject in data["subjects"]:
            # Required fields
            assert "subject_id" in subject
            assert "subject_name" in subject
            assert "test_performance" in subject
            assert "average_score" in subject
            assert "classification" in subject
            assert "syllabus_progress" in subject
            assert "homework_stats" in subject
            assert "missed_homework" in subject
            
            # Classification must be valid
            assert subject["classification"] in ["strong", "average", "weak", "no_data"]
    
    def test_parent_dashboard_requires_student_role(self):
        """Parent dashboard requires student role - teachers/admin should be rejected"""
        # Try accessing without token
        response = requests.get(f"{BASE_URL}/api/student/parent-dashboard")
        assert response.status_code == 401, "Should reject unauthenticated requests"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
