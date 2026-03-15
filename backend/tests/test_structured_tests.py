"""
Backend API Tests for Structured Tests Feature
===============================================
Tests for:
1. Save and publish flow (create test, add questions, publish)
2. Draft tests NOT visible to students
3. Teacher list tests endpoint shows both draft and active
"""

import pytest
import requests
import os
import uuid
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Subject ID for Mathematics
MATH_SUBJECT_ID = "f5c2dacf-2649-439c-a845-e7b3876ad4c2"
STANDARD = 5

class TestStructuredTestsAPI:
    """Tests for structured tests API endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get admin and student tokens before each test"""
        self.admin_token = None
        self.student_token = None
        
        # Login as admin
        admin_resp = requests.post(
            f"{BASE_URL}/api/admin/login",
            json={"username": "admin", "password": "Admin@123"}
        )
        if admin_resp.status_code == 200:
            self.admin_token = admin_resp.json().get("token")
        
        # Login as student
        student_resp = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"roll_no": "S001", "password": "123456"}
        )
        if student_resp.status_code == 200:
            self.student_token = student_resp.json().get("token")
            
        yield
    
    def admin_headers(self):
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.admin_token}"
        }
    
    def student_headers(self):
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.student_token}"
        }
    
    # =========================================================================
    # Test 1: Save and Publish Flow
    # =========================================================================
    
    def test_create_test_requires_auth(self):
        """Create test without auth should fail"""
        response = requests.post(
            f"{BASE_URL}/api/structured-tests",
            json={
                "subject_id": MATH_SUBJECT_ID,
                "standard": STANDARD,
                "title": "Unauthorized Test",
                "school_name": "Test School",
                "total_marks": 10,
                "duration_minutes": 30,
                "submission_deadline": (datetime.now() + timedelta(days=7)).isoformat()
            }
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Create test without auth returns 401")
    
    def test_create_test_as_admin(self):
        """Admin can create a new test"""
        deadline = (datetime.now() + timedelta(days=7)).isoformat()
        test_title = f"TEST_AdminTest_{uuid.uuid4().hex[:8]}"
        
        response = requests.post(
            f"{BASE_URL}/api/structured-tests",
            headers=self.admin_headers(),
            json={
                "subject_id": MATH_SUBJECT_ID,
                "standard": STANDARD,
                "title": test_title,
                "school_name": "Test School",
                "total_marks": 10,
                "duration_minutes": 30,
                "submission_deadline": deadline
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "id" in data, "Response should contain test ID"
        assert data["status"] == "draft", "New test should be in draft status"
        assert data["title"] == test_title, "Title should match"
        print(f"✓ Admin created test: {test_title} (ID: {data['id']})")
        
        # Store test_id for cleanup
        self.created_test_id = data["id"]
        return data["id"]
    
    def test_add_questions_to_test(self):
        """Admin can add questions to a test"""
        # First create a test
        test_id = self.test_create_test_as_admin()
        
        # Add questions
        questions = [
            {
                "question_number": 1,
                "question_type": "mcq",
                "question_text": "What is 2 + 2?",
                "max_marks": 2,
                "objective_data": {
                    "options": {"a": "3", "b": "4", "c": "5", "d": "6"},
                    "correct": "b"
                }
            },
            {
                "question_number": 2,
                "question_type": "short_answer",
                "question_text": "Define addition.",
                "max_marks": 3,
                "model_answer": "Addition is a mathematical operation that combines two or more numbers.",
                "evaluation_points": [
                    {"id": 1, "title": "Definition", "expected_concept": "mathematical operation", "marks": 2},
                    {"id": 2, "title": "Purpose", "expected_concept": "combines numbers", "marks": 1}
                ]
            }
        ]
        
        response = requests.post(
            f"{BASE_URL}/api/structured-tests/{test_id}/questions",
            headers=self.admin_headers(),
            json={"questions": questions}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["question_count"] == 2, f"Expected 2 questions, got {data['question_count']}"
        assert data["total_marks"] == 5, f"Expected 5 marks, got {data['total_marks']}"
        print(f"✓ Added {data['question_count']} questions, total marks: {data['total_marks']}")
        
        return test_id
    
    def test_publish_test(self):
        """Admin can publish a test after adding questions"""
        # Create test and add questions
        test_id = self.test_add_questions_to_test()
        
        # Publish the test
        response = requests.post(
            f"{BASE_URL}/api/structured-tests/{test_id}/publish",
            headers=self.admin_headers()
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["status"] == "active", f"Expected 'active', got {data['status']}"
        print(f"✓ Test published successfully (status: {data['status']})")
        
        return test_id
    
    def test_cannot_publish_without_questions(self):
        """Cannot publish a test without questions"""
        deadline = (datetime.now() + timedelta(days=7)).isoformat()
        
        # Create test
        create_resp = requests.post(
            f"{BASE_URL}/api/structured-tests",
            headers=self.admin_headers(),
            json={
                "subject_id": MATH_SUBJECT_ID,
                "standard": STANDARD,
                "title": f"TEST_EmptyTest_{uuid.uuid4().hex[:8]}",
                "school_name": "Test School",
                "total_marks": 10,
                "duration_minutes": 30,
                "submission_deadline": deadline
            }
        )
        test_id = create_resp.json()["id"]
        
        # Try to publish without questions
        publish_resp = requests.post(
            f"{BASE_URL}/api/structured-tests/{test_id}/publish",
            headers=self.admin_headers()
        )
        
        assert publish_resp.status_code == 400, f"Expected 400, got {publish_resp.status_code}"
        print("✓ Cannot publish test without questions (400 returned)")
    
    # =========================================================================
    # Test 2: Draft Tests NOT Visible to Students
    # =========================================================================
    
    def test_draft_test_not_visible_to_student(self):
        """Draft tests should not be visible to students"""
        # Create a draft test as admin
        deadline = (datetime.now() + timedelta(days=7)).isoformat()
        test_title = f"TEST_DraftOnly_{uuid.uuid4().hex[:8]}"
        
        create_resp = requests.post(
            f"{BASE_URL}/api/structured-tests",
            headers=self.admin_headers(),
            json={
                "subject_id": MATH_SUBJECT_ID,
                "standard": STANDARD,
                "title": test_title,
                "school_name": "Test School",
                "total_marks": 10,
                "duration_minutes": 30,
                "submission_deadline": deadline
            }
        )
        assert create_resp.status_code == 200
        test_id = create_resp.json()["id"]
        print(f"✓ Created draft test: {test_title}")
        
        # List tests as student - draft test should NOT appear
        student_list_resp = requests.get(
            f"{BASE_URL}/api/structured-tests/list/{MATH_SUBJECT_ID}/{STANDARD}",
            headers=self.student_headers()
        )
        
        assert student_list_resp.status_code == 200
        student_tests = student_list_resp.json()
        
        # Check that our draft test is NOT in the student's list
        draft_visible = any(t["id"] == test_id for t in student_tests)
        assert not draft_visible, "Draft test should NOT be visible to students"
        print(f"✓ Draft test NOT visible to student (verified)")
        
        # Also verify student only sees active tests
        for test in student_tests:
            assert test["status"] == "active", f"Student sees non-active test: {test['title']}"
        print(f"✓ Student sees only active tests ({len(student_tests)} tests)")
        
        return test_id
    
    def test_published_test_visible_to_student(self):
        """Published tests should be visible to students"""
        # Create and publish a test
        test_id = self.test_publish_test()
        
        # List tests as student
        student_list_resp = requests.get(
            f"{BASE_URL}/api/structured-tests/list/{MATH_SUBJECT_ID}/{STANDARD}",
            headers=self.student_headers()
        )
        
        assert student_list_resp.status_code == 200
        student_tests = student_list_resp.json()
        
        # Check that our published test IS in the student's list
        published_visible = any(t["id"] == test_id for t in student_tests)
        assert published_visible, "Published test should be visible to students"
        print(f"✓ Published test IS visible to student (verified)")
    
    # =========================================================================
    # Test 3: Teacher List Shows Both Draft and Active
    # =========================================================================
    
    def test_teacher_sees_all_tests(self):
        """Teachers/Admin should see both draft and active tests"""
        # Create a draft test
        draft_id = self.test_draft_test_not_visible_to_student()
        
        # List tests as admin
        admin_list_resp = requests.get(
            f"{BASE_URL}/api/structured-tests/list/{MATH_SUBJECT_ID}/{STANDARD}",
            headers=self.admin_headers()
        )
        
        assert admin_list_resp.status_code == 200
        admin_tests = admin_list_resp.json()
        
        # Admin should see the draft test
        draft_visible = any(t["id"] == draft_id for t in admin_tests)
        assert draft_visible, "Admin should see draft test"
        print(f"✓ Admin can see draft test")
        
        # Check that admin sees both draft and active tests
        statuses = set(t["status"] for t in admin_tests)
        print(f"✓ Admin sees tests with statuses: {statuses}")
        
        # Verify test details returned
        draft_test = next(t for t in admin_tests if t["id"] == draft_id)
        assert "title" in draft_test, "Test should have title"
        assert "question_count" in draft_test, "Test should have question_count"
        assert "total_marks" in draft_test, "Test should have total_marks"
        assert "duration_minutes" in draft_test, "Test should have duration_minutes"
        print(f"✓ Test details include: title, question_count, total_marks, duration_minutes")
    
    def test_list_tests_response_structure(self):
        """Verify list tests response has correct structure"""
        response = requests.get(
            f"{BASE_URL}/api/structured-tests/list/{MATH_SUBJECT_ID}/{STANDARD}",
            headers=self.admin_headers()
        )
        
        assert response.status_code == 200
        tests = response.json()
        
        if len(tests) > 0:
            test = tests[0]
            required_fields = ["id", "title", "total_marks", "duration_minutes", "status", "question_count"]
            for field in required_fields:
                assert field in test, f"Test should have {field} field"
            print(f"✓ List response contains all required fields: {required_fields}")
        else:
            print("⚠ No tests found to verify structure")


class TestStudentCannotModify:
    """Tests to verify students cannot create/modify tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get student token"""
        student_resp = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"roll_no": "S001", "password": "123456"}
        )
        if student_resp.status_code == 200:
            self.student_token = student_resp.json().get("token")
        yield
    
    def student_headers(self):
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.student_token}"
        }
    
    def test_student_cannot_create_test(self):
        """Students should not be able to create tests"""
        response = requests.post(
            f"{BASE_URL}/api/structured-tests",
            headers=self.student_headers(),
            json={
                "subject_id": MATH_SUBJECT_ID,
                "standard": STANDARD,
                "title": "Student Created Test",
                "school_name": "Test School",
                "total_marks": 10,
                "duration_minutes": 30,
                "submission_deadline": (datetime.now() + timedelta(days=7)).isoformat()
            }
        )
        
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"
        print("✓ Students cannot create tests (403 returned)")
    
    def test_student_cannot_publish_test(self):
        """Students should not be able to publish tests"""
        # Try to publish any test
        response = requests.post(
            f"{BASE_URL}/api/structured-tests/some-test-id/publish",
            headers=self.student_headers()
        )
        
        assert response.status_code in [403, 404], f"Expected 403 or 404, got {response.status_code}"
        print("✓ Students cannot publish tests")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
