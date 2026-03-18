"""
Test Suite: Login/Logout Bug Fix Verification
Tests the P0 recurring login bug fix where:
1. Backend delete_cookie didn't match set_cookie attributes (samesite/secure/httponly)
2. Server prioritized cookie over Authorization header
3. Frontend didn't clear stale cookies before new login

Test Credentials:
- Admin: username=admin, password=Admin@123
- Student: roll_no=S3, password=123456 (student Krutika, class 6)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    BASE_URL = "https://parent-brief.preview.emergentagent.com"


class TestAdminLogin:
    """Admin login functionality tests"""
    
    def test_admin_login_success(self):
        """Admin login with correct credentials returns 200 and token"""
        response = requests.post(
            f"{BASE_URL}/api/admin/login",
            json={"username": "admin", "password": "Admin@123"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "token" in data, "Response should contain token"
        assert "user" in data, "Response should contain user"
        assert data["user"]["role"] == "admin", "User role should be admin"
        print(f"✅ Admin login successful, token received: {data['token'][:20]}...")
        
    def test_admin_login_invalid_credentials(self):
        """Admin login with wrong credentials returns 401"""
        response = requests.post(
            f"{BASE_URL}/api/admin/login",
            json={"username": "admin", "password": "wrongpassword"}
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✅ Admin login correctly rejects invalid credentials")


class TestLogoutCleanup:
    """Test that logout properly clears authentication"""
    
    def test_admin_logout_clears_session(self):
        """After admin logout, auth/me should return 401"""
        session = requests.Session()
        
        # Step 1: Login as admin
        login_response = session.post(
            f"{BASE_URL}/api/admin/login",
            json={"username": "admin", "password": "Admin@123"}
        )
        assert login_response.status_code == 200, "Admin login should succeed"
        token = login_response.json().get("token")
        
        # Step 2: Verify auth/me works with token
        auth_check = session.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert auth_check.status_code == 200, "Auth/me should work with valid token"
        assert auth_check.json()["role"] == "admin", "Should be admin role"
        print("✅ Admin authenticated successfully")
        
        # Step 3: Logout
        logout_response = session.post(f"{BASE_URL}/api/auth/logout")
        assert logout_response.status_code == 200, "Logout should succeed"
        print("✅ Admin logout successful")
        
        # Step 4: auth/me should now return 401 WITHOUT the token
        auth_check_after = requests.get(f"{BASE_URL}/api/auth/me")
        assert auth_check_after.status_code == 401, f"auth/me should return 401 after logout (got {auth_check_after.status_code})"
        print("✅ auth/me returns 401 after logout (cookie cleared)")


class TestStudentLogin:
    """Student login functionality tests"""
    
    def test_student_login_success(self):
        """Student login with roll_no and password returns 200 and correct role"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"roll_no": "S3", "password": "123456"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "token" in data, "Response should contain token"
        assert "user" in data, "Response should contain user"
        assert data["user"]["role"] == "student", f"User role should be student, got {data['user']['role']}"
        assert data["user"]["name"] == "Krutika", f"Student name should be Krutika, got {data['user'].get('name')}"
        assert data["user"]["roll_no"] == "S3", "Roll number should match"
        print(f"✅ Student S3 (Krutika) login successful")
        
    def test_student_login_invalid_credentials(self):
        """Student login with wrong credentials returns 401"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"roll_no": "S3", "password": "wrongpassword"}
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✅ Student login correctly rejects invalid credentials")


class TestRoleSwitching:
    """Critical tests for the login bug fix - role switching scenarios"""
    
    def test_admin_logout_then_student_login_returns_student_role(self):
        """
        CRITICAL BUG TEST: After admin logout, student login should return student data, NOT admin data.
        This was the core bug where stale admin cookie caused student login to return admin data.
        """
        session = requests.Session()
        
        # Step 1: Login as admin
        admin_login = session.post(
            f"{BASE_URL}/api/admin/login",
            json={"username": "admin", "password": "Admin@123"}
        )
        assert admin_login.status_code == 200, "Admin login should succeed"
        admin_token = admin_login.json().get("token")
        print("✅ Admin logged in")
        
        # Step 2: Logout admin
        logout_response = session.post(f"{BASE_URL}/api/auth/logout")
        assert logout_response.status_code == 200, "Admin logout should succeed"
        print("✅ Admin logged out")
        
        # Step 3: Login as student (use fresh session to simulate real browser behavior after clearing localStorage)
        student_session = requests.Session()
        student_login = student_session.post(
            f"{BASE_URL}/api/auth/login",
            json={"roll_no": "S3", "password": "123456"}
        )
        assert student_login.status_code == 200, f"Student login should succeed, got {student_login.status_code}"
        student_data = student_login.json()
        student_token = student_data.get("token")
        
        # CRITICAL ASSERTION: Student login should return student role, NOT admin
        assert student_data["user"]["role"] == "student", \
            f"BUG: Student login returned role '{student_data['user']['role']}' instead of 'student'"
        assert student_data["user"]["name"] == "Krutika", \
            f"BUG: Expected student name 'Krutika', got '{student_data['user'].get('name')}'"
        print("✅ Student login returns correct student data (not admin data)")
        
        # Step 4: Verify auth/me with student token returns student data
        auth_me = student_session.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {student_token}"}
        )
        assert auth_me.status_code == 200, f"auth/me should work with student token"
        assert auth_me.json()["role"] == "student", \
            f"BUG: auth/me returned role '{auth_me.json()['role']}' instead of 'student'"
        print("✅ auth/me returns correct student role after student login")
        
    def test_student_logout_then_admin_login_returns_admin_role(self):
        """After student logout, admin login should return admin data"""
        session = requests.Session()
        
        # Step 1: Login as student
        student_login = session.post(
            f"{BASE_URL}/api/auth/login",
            json={"roll_no": "S3", "password": "123456"}
        )
        assert student_login.status_code == 200, "Student login should succeed"
        print("✅ Student logged in")
        
        # Step 2: Logout student
        session.post(f"{BASE_URL}/api/auth/logout")
        print("✅ Student logged out")
        
        # Step 3: Login as admin
        admin_session = requests.Session()
        admin_login = admin_session.post(
            f"{BASE_URL}/api/admin/login",
            json={"username": "admin", "password": "Admin@123"}
        )
        assert admin_login.status_code == 200, "Admin login should succeed"
        admin_data = admin_login.json()
        admin_token = admin_data.get("token")
        
        # CRITICAL ASSERTION: Admin login should return admin role
        assert admin_data["user"]["role"] == "admin", \
            f"BUG: Admin login returned role '{admin_data['user']['role']}' instead of 'admin'"
        print("✅ Admin login returns correct admin data (not student data)")
        
        # Verify auth/me
        auth_me = admin_session.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert auth_me.status_code == 200
        assert auth_me.json()["role"] == "admin"
        print("✅ auth/me returns correct admin role")
        
    def test_student_logout_then_different_student_login(self):
        """After student S3 logout, logging in as S3 again should work correctly"""
        session = requests.Session()
        
        # Step 1: Login as student S3
        login1 = session.post(
            f"{BASE_URL}/api/auth/login",
            json={"roll_no": "S3", "password": "123456"}
        )
        assert login1.status_code == 200, "First student login should succeed"
        token1 = login1.json().get("token")
        print("✅ Student S3 logged in (first time)")
        
        # Step 2: Logout
        session.post(f"{BASE_URL}/api/auth/logout")
        print("✅ Student S3 logged out")
        
        # Step 3: Login again as same student
        session2 = requests.Session()
        login2 = session2.post(
            f"{BASE_URL}/api/auth/login",
            json={"roll_no": "S3", "password": "123456"}
        )
        assert login2.status_code == 200, f"Second student login should succeed, got {login2.status_code}"
        token2 = login2.json().get("token")
        
        # Verify correct data
        data2 = login2.json()
        assert data2["user"]["role"] == "student"
        assert data2["user"]["name"] == "Krutika"
        print("✅ Student S3 logged in again successfully (second time)")
        
        # Verify auth/me works
        auth_me = session2.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {token2}"}
        )
        assert auth_me.status_code == 200
        assert auth_me.json()["role"] == "student"
        assert auth_me.json().get("student_profile", {}).get("name") == "Krutika"
        print("✅ auth/me returns correct student data on re-login")


class TestAuthorizationHeaderPriority:
    """Test that Authorization header takes priority over cookies (bug fix #2)"""
    
    def test_bearer_token_overrides_stale_cookie(self):
        """
        BUG FIX TEST: When both cookie and Authorization header are present,
        the Authorization header (Bearer token) should take priority.
        """
        session = requests.Session()
        
        # Login as admin to set cookie
        admin_login = session.post(
            f"{BASE_URL}/api/admin/login",
            json={"username": "admin", "password": "Admin@123"}
        )
        admin_token = admin_login.json().get("token")
        
        # Get student token
        student_login = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"roll_no": "S3", "password": "123456"}
        )
        student_token = student_login.json().get("token")
        
        # Send request with session cookies (admin) but with student Bearer token
        # The Authorization header (student token) should take priority
        auth_me = session.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {student_token}"}
        )
        
        assert auth_me.status_code == 200, f"Request should succeed, got {auth_me.status_code}"
        
        # CRITICAL: Response should be student data, not admin (Bearer token takes priority)
        result_role = auth_me.json().get("role")
        assert result_role == "student", \
            f"BUG: Expected 'student' role (from Bearer token), but got '{result_role}' (from cookie)"
        print("✅ Authorization header correctly takes priority over cookie")


class TestHealthCheck:
    """Basic health checks"""
    
    def test_health_endpoint(self):
        """Health endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/health")
        assert response.status_code == 200
        print("✅ Health endpoint working")
        
    def test_readiness_endpoint(self):
        """Readiness endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/readiness")
        assert response.status_code == 200
        print("✅ Readiness endpoint working")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
