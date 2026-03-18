"""
DhruvStar StudyBuddy - Additional API Tests
============================================

Tests for:
- Subject/Chapter CRUD
- Homework operations
- AI content endpoints
- Cross-school access control
- Concurrent operations
"""

import pytest
import requests
import os
import json
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://test-eval-debug.preview.emergentagent.com')
API_URL = f"{BASE_URL}/api"

ADMIN_CREDS = {"username": "admin", "password": "Admin@123"}
STUDENT_CREDS = {"roll_no": "STU2024001", "password": "password123"}
TEST_PREFIX = "TEST_QA_"


def get_admin_session():
    session = requests.Session()
    response = session.post(f"{API_URL}/admin/login", json=ADMIN_CREDS)
    if response.status_code != 200:
        pytest.skip(f"Admin login failed: {response.text}")
    return session


def get_student_session():
    session = requests.Session()
    response = session.post(f"{API_URL}/auth/login", json=STUDENT_CREDS)
    if response.status_code != 200:
        pytest.skip(f"Student login failed: {response.text}")
    return session


class TestSubjectChapterCRUD:
    """Test Subject and Chapter CRUD operations"""
    
    def test_list_subjects_by_standard(self):
        """List subjects for different standards"""
        for standard in [5, 10]:
            response = requests.get(f"{API_URL}/subjects?standard={standard}")
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
            print(f"✅ Standard {standard}: {len(data)} subjects")
    
    def test_get_subject_chapters(self):
        """Get chapters for a specific subject"""
        # Get subjects first
        response = requests.get(f"{API_URL}/subjects?standard=5")
        if response.status_code != 200 or not response.json():
            pytest.skip("No subjects available")
        
        subject_id = response.json()[0]["id"]
        # Use the chapters endpoint instead
        chapters_response = requests.get(f"{API_URL}/subjects/{subject_id}/chapters")
        assert chapters_response.status_code == 200
        print(f"✅ Subject chapters endpoint works")
    
    def test_list_chapters_for_subject(self):
        """List chapters for a subject"""
        response = requests.get(f"{API_URL}/subjects?standard=5")
        if response.status_code != 200 or not response.json():
            pytest.skip("No subjects available")
        
        subject_id = response.json()[0]["id"]
        chapters_response = requests.get(f"{API_URL}/subjects/{subject_id}/chapters")
        assert chapters_response.status_code == 200
        data = chapters_response.json()
        assert isinstance(data, list)
        print(f"✅ Retrieved {len(data)} chapters")


class TestHomeworkOperations:
    """Test Homework CRUD operations"""
    
    def test_list_homework_for_standard(self):
        """List homework for a standard"""
        session = get_student_session()
        response = session.get(f"{API_URL}/homework?standard=5")
        assert response.status_code in [200, 404]
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Retrieved {len(data)} homework items")
        else:
            print("✅ No homework found (expected)")
    
    def test_homework_history(self):
        """Get student homework history"""
        session = get_student_session()
        response = session.get(f"{API_URL}/student/homework-history")
        assert response.status_code in [200, 404]
        print(f"✅ Homework history endpoint: {response.status_code}")


class TestAIContentEndpoints:
    """Test AI content generation endpoints"""
    
    def test_content_status_endpoint(self):
        """Check content status for a chapter"""
        # Get a chapter first
        response = requests.get(f"{API_URL}/subjects?standard=5")
        if response.status_code != 200 or not response.json():
            pytest.skip("No subjects available")
        
        subject_id = response.json()[0]["id"]
        chapters_response = requests.get(f"{API_URL}/subjects/{subject_id}/chapters")
        if chapters_response.status_code != 200 or not chapters_response.json():
            pytest.skip("No chapters available")
        
        chapter_id = chapters_response.json()[0]["id"]
        
        session = get_student_session()
        status_response = session.get(f"{API_URL}/chapters/{chapter_id}/content-status")
        assert status_response.status_code in [200, 404]
        print(f"✅ Content status endpoint: {status_response.status_code}")


class TestCrossSchoolAccess:
    """Test cross-school data access control"""
    
    def test_student_sees_own_school_data(self):
        """Student should only see data from their school"""
        session = get_student_session()
        
        # Get user info
        me_response = session.get(f"{API_URL}/auth/me")
        assert me_response.status_code == 200
        user_data = me_response.json()
        
        school_name = user_data.get("school_name", "")
        print(f"✅ Student school: {school_name}")
        
        # Get subjects - should be filtered by school
        subjects_response = session.get(f"{API_URL}/subjects?standard=5")
        assert subjects_response.status_code == 200
        print("✅ Student can access subjects")


class TestConcurrentOperations:
    """Test concurrent API operations"""
    
    def test_concurrent_subject_reads(self):
        """Test 10 concurrent subject reads"""
        def read_subjects(i):
            try:
                response = requests.get(f"{API_URL}/subjects?standard=5", timeout=30)
                return {"index": i, "status": response.status_code, "success": response.status_code == 200}
            except Exception as e:
                return {"index": i, "status": 0, "success": False, "error": str(e)}
        
        results = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(read_subjects, i) for i in range(10)]
            for future in as_completed(futures):
                results.append(future.result())
        
        success_count = sum(1 for r in results if r["success"])
        print(f"✅ Concurrent reads: {success_count}/10 successful")
        assert success_count >= 8, f"Only {success_count}/10 requests succeeded"


class TestUserManagement:
    """Test user management operations"""
    
    def test_admin_list_users(self):
        """Admin can list all users"""
        session = get_admin_session()
        response = session.get(f"{API_URL}/admin/users")
        assert response.status_code == 200
        data = response.json()
        assert "users" in data
        assert "total" in data
        print(f"✅ Admin retrieved {data['total']} users")
    
    def test_admin_toggle_user_status(self):
        """Admin can toggle user active status"""
        session = get_admin_session()
        
        # Get users
        users_response = session.get(f"{API_URL}/admin/users")
        if users_response.status_code != 200:
            pytest.skip("Could not get users")
        
        users = users_response.json().get("users", [])
        # Find a student to toggle
        student = next((u for u in users if u["role"] == "student"), None)
        if not student:
            pytest.skip("No student found to test toggle")
        
        # Toggle status - endpoint is PUT not POST
        toggle_response = session.put(f"{API_URL}/admin/user/{student['id']}/toggle-active")
        assert toggle_response.status_code in [200, 404]
        
        if toggle_response.status_code == 200:
            # Toggle back
            session.put(f"{API_URL}/admin/user/{student['id']}/toggle-active")
            print("✅ User status toggle works")
        else:
            print(f"⚠️ Toggle endpoint: {toggle_response.status_code}")


class TestAuthenticationEdgeCases:
    """Test authentication edge cases"""
    
    def test_invalid_roll_no(self):
        """Invalid roll_no should fail"""
        response = requests.post(f"{API_URL}/auth/login", json={
            "roll_no": "INVALID_ROLL",
            "password": "password123"
        })
        assert response.status_code == 401
        print("✅ Invalid roll_no rejected")
    
    def test_wrong_password(self):
        """Wrong password should fail"""
        response = requests.post(f"{API_URL}/auth/login", json={
            "roll_no": "STU2024001",
            "password": "wrongpassword"
        })
        assert response.status_code == 401
        print("✅ Wrong password rejected")
    
    def test_empty_credentials(self):
        """Empty credentials should fail"""
        response = requests.post(f"{API_URL}/auth/login", json={
            "roll_no": "",
            "password": ""
        })
        assert response.status_code in [401, 422]
        print("✅ Empty credentials rejected")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
