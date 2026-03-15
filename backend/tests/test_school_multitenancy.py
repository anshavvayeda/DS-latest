"""
Test School-Based Multi-Tenancy Features
=========================================
Tests for:
- GET /api/schools/list - returns list of schools from registered teachers
- POST /api/admin/register-student with role=teacher - requires school_name
- POST /api/admin/register-student with role=student - validates school exists
"""

import pytest
import requests
import os
import uuid

# Use the public URL for testing
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://auto-grading-1.preview.emergentagent.com')
API_BASE = f"{BASE_URL}/api"

# Admin credentials
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "Admin@123"


@pytest.fixture(scope="module")
def admin_session():
    """Create an authenticated admin session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    
    # Login as admin
    response = session.post(
        f"{API_BASE}/admin/login",
        json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD}
    )
    assert response.status_code == 200, f"Admin login failed: {response.text}"
    print(f"Admin logged in successfully")
    return session


class TestSchoolsListEndpoint:
    """Tests for GET /api/schools/list endpoint"""
    
    def test_schools_list_returns_200(self):
        """Test that schools list endpoint returns 200"""
        response = requests.get(f"{API_BASE}/schools/list")
        assert response.status_code == 200
        print(f"Schools list response: {response.json()}")
    
    def test_schools_list_returns_correct_structure(self):
        """Test that schools list returns correct JSON structure"""
        response = requests.get(f"{API_BASE}/schools/list")
        data = response.json()
        
        assert "schools" in data, "Response should contain 'schools' key"
        assert "total" in data, "Response should contain 'total' key"
        assert isinstance(data["schools"], list), "'schools' should be a list"
        assert isinstance(data["total"], int), "'total' should be an integer"
    
    def test_schools_list_contains_expected_schools(self):
        """Test that schools list contains Delhi Public School and Modern Academy"""
        response = requests.get(f"{API_BASE}/schools/list")
        data = response.json()
        schools = data["schools"]
        
        # Check that expected schools are present
        assert "Delhi Public School" in schools, "Delhi Public School should be in the list"
        assert "Modern Academy" in schools, "Modern Academy should be in the list"
        print(f"Schools found: {schools}")
    
    def test_schools_list_is_sorted_alphabetically(self):
        """Test that schools are sorted alphabetically"""
        response = requests.get(f"{API_BASE}/schools/list")
        data = response.json()
        schools = data["schools"]
        
        sorted_schools = sorted(schools)
        assert schools == sorted_schools, "Schools should be sorted alphabetically"


class TestTeacherRegistration:
    """Tests for teacher registration with school_name requirement"""
    
    def test_teacher_registration_requires_school_name(self, admin_session):
        """Test that teacher registration fails without school_name"""
        unique_id = uuid.uuid4().hex[:6]
        payload = {
            "name": f"TEST_Teacher_NoSchool_{unique_id}",
            "school_name": "",  # Empty school name
            "roll_no": f"T_TEST_{unique_id}",
            "phone": f"999{unique_id[:7]}",
            "password": "Test@123",
            "is_active": True,
            "role": "teacher"
        }
        
        response = admin_session.post(f"{API_BASE}/admin/register-student", json=payload)
        assert response.status_code == 400, f"Should fail without school_name, got {response.status_code}"
        
        data = response.json()
        assert "detail" in data
        assert "school" in data["detail"].lower(), f"Error should mention school: {data['detail']}"
        print(f"Correctly rejected teacher without school: {data['detail']}")
    
    def test_teacher_registration_with_school_name_succeeds(self, admin_session):
        """Test that teacher registration with school_name succeeds"""
        unique_id = uuid.uuid4().hex[:6]
        school_name = f"TEST_School_{unique_id}"
        payload = {
            "name": f"TEST_Teacher_{unique_id}",
            "school_name": school_name,
            "roll_no": f"T_TEST_{unique_id}",
            "phone": f"998{unique_id[:7]}",
            "password": "Test@123",
            "is_active": True,
            "role": "teacher"
        }
        
        response = admin_session.post(f"{API_BASE}/admin/register-student", json=payload)
        
        # If duplicate, that's fine - we're testing the validation logic
        if response.status_code == 400 and "already" in response.text.lower():
            print("Teacher already exists (from previous test run)")
            return
        
        assert response.status_code == 200, f"Teacher registration failed: {response.text}"
        
        data = response.json()
        assert "message" in data
        assert "teacher" in data["message"].lower()
        print(f"Teacher registered successfully: {data['message']}")
        
        # Cleanup: Delete the test user
        user_id = data.get("user", {}).get("id")
        if user_id:
            admin_session.delete(f"{API_BASE}/admin/user/{user_id}")
            print(f"Cleaned up test teacher: {user_id}")


class TestStudentRegistration:
    """Tests for student registration with school validation"""
    
    def test_student_registration_requires_existing_school(self, admin_session):
        """Test that student registration fails if school doesn't exist"""
        unique_id = uuid.uuid4().hex[:6]
        payload = {
            "name": f"TEST_Student_BadSchool_{unique_id}",
            "school_name": f"NonExistent_School_{unique_id}",  # School that doesn't exist
            "standard": 10,
            "roll_no": f"S_TEST_{unique_id}",
            "gender": "male",
            "phone": f"997{unique_id[:7]}",
            "password": "Test@123",
            "is_active": True,
            "role": "student"
        }
        
        response = admin_session.post(f"{API_BASE}/admin/register-student", json=payload)
        assert response.status_code == 400, f"Should fail with non-existent school, got {response.status_code}"
        
        data = response.json()
        assert "detail" in data
        error_msg = data["detail"].lower()
        assert "not registered" in error_msg or "teacher" in error_msg, f"Error should mention school not registered: {data['detail']}"
        print(f"Correctly rejected student with non-existent school: {data['detail']}")
    
    def test_student_registration_with_valid_school_succeeds(self, admin_session):
        """Test that student registration with valid school succeeds"""
        unique_id = uuid.uuid4().hex[:6]
        payload = {
            "name": f"TEST_Student_{unique_id}",
            "school_name": "Delhi Public School",  # Existing school
            "standard": 10,
            "roll_no": f"S_TEST_{unique_id}",
            "gender": "male",
            "phone": f"996{unique_id[:7]}",
            "password": "Test@123",
            "is_active": True,
            "role": "student"
        }
        
        response = admin_session.post(f"{API_BASE}/admin/register-student", json=payload)
        
        # If duplicate, that's fine
        if response.status_code == 400 and "already" in response.text.lower():
            print("Student already exists (from previous test run)")
            return
        
        assert response.status_code == 200, f"Student registration failed: {response.text}"
        
        data = response.json()
        assert "message" in data
        assert "student" in data["message"].lower()
        print(f"Student registered successfully: {data['message']}")
        
        # Cleanup: Delete the test user
        user_id = data.get("user", {}).get("id")
        if user_id:
            admin_session.delete(f"{API_BASE}/admin/user/{user_id}")
            print(f"Cleaned up test student: {user_id}")
    
    def test_student_requires_school_name(self, admin_session):
        """Test that student registration fails without school_name"""
        unique_id = uuid.uuid4().hex[:6]
        payload = {
            "name": f"TEST_Student_NoSchool_{unique_id}",
            "school_name": None,  # Missing school
            "standard": 10,
            "roll_no": f"S_TEST_{unique_id}",
            "gender": "male",
            "phone": f"995{unique_id[:7]}",
            "password": "Test@123",
            "is_active": True,
            "role": "student"
        }
        
        response = admin_session.post(f"{API_BASE}/admin/register-student", json=payload)
        assert response.status_code == 400, f"Should fail without school_name, got {response.status_code}"
        print(f"Correctly rejected student without school name")


class TestSchoolCreationFlow:
    """Test the complete flow: Teacher creates school namespace, student can register"""
    
    def test_new_school_appears_in_list_after_teacher_registration(self, admin_session):
        """Test that registering a teacher creates a new school in the schools list"""
        unique_id = uuid.uuid4().hex[:6]
        new_school_name = f"TEST_New_School_{unique_id}"
        
        # First, check schools list
        before_response = requests.get(f"{API_BASE}/schools/list")
        before_schools = before_response.json()["schools"]
        assert new_school_name not in before_schools, "Test school should not exist yet"
        
        # Register a teacher with the new school
        teacher_payload = {
            "name": f"TEST_Teacher_NewSchool_{unique_id}",
            "school_name": new_school_name,
            "roll_no": f"T_NS_{unique_id}",
            "phone": f"994{unique_id[:7]}",
            "password": "Test@123",
            "is_active": True,
            "role": "teacher"
        }
        
        reg_response = admin_session.post(f"{API_BASE}/admin/register-student", json=teacher_payload)
        assert reg_response.status_code == 200, f"Teacher registration failed: {reg_response.text}"
        
        teacher_id = reg_response.json().get("user", {}).get("id")
        
        # Now check that the new school appears in the list
        after_response = requests.get(f"{API_BASE}/schools/list")
        after_schools = after_response.json()["schools"]
        assert new_school_name in after_schools, f"New school should appear in list: {after_schools}"
        print(f"New school '{new_school_name}' now appears in schools list")
        
        # Now try registering a student in that school
        student_payload = {
            "name": f"TEST_Student_NewSchool_{unique_id}",
            "school_name": new_school_name,
            "standard": 8,
            "roll_no": f"S_NS_{unique_id}",
            "gender": "female",
            "phone": f"993{unique_id[:7]}",
            "password": "Test@123",
            "is_active": True,
            "role": "student"
        }
        
        student_response = admin_session.post(f"{API_BASE}/admin/register-student", json=student_payload)
        assert student_response.status_code == 200, f"Student registration failed: {student_response.text}"
        
        student_id = student_response.json().get("user", {}).get("id")
        print(f"Student successfully registered in new school")
        
        # Cleanup
        if student_id:
            admin_session.delete(f"{API_BASE}/admin/user/{student_id}")
        if teacher_id:
            admin_session.delete(f"{API_BASE}/admin/user/{teacher_id}")
        print("Test data cleaned up")


class TestAdminUsersListBySchool:
    """Test that admin users list properly groups by school"""
    
    def test_admin_users_returns_school_name(self, admin_session):
        """Test that admin users endpoint returns school_name for users"""
        response = admin_session.get(f"{API_BASE}/admin/users")
        assert response.status_code == 200
        
        data = response.json()
        assert "users" in data
        
        # Check that users have school_name field
        for user in data["users"]:
            if user.get("role") in ["teacher", "student"]:
                assert "school_name" in user, f"User {user.get('name')} should have school_name field"
        
        print(f"All users have school_name field")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
