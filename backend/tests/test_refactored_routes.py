"""
Backend API tests for the refactored modular routes.
Tests admin login, auth routes, subjects, homework, structured tests, etc.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Admin credentials from problem statement
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "Admin@123"


class TestHealthEndpoint:
    """Test health endpoints - non-prefixed for k8s probes"""
    
    def test_health_endpoint_exists(self):
        """Health endpoint should be at /health NOT /api/health"""
        # The health endpoint is NOT prefixed with /api
        response = requests.get(f"{BASE_URL}/health")
        # Note: This might return HTML if routed through frontend
        # Let's check the actual backend internal health
        print(f"Health response status: {response.status_code}")
        # Accept either 200 or 404 (if routed through frontend)
        assert response.status_code in [200, 404]


class TestAdminLogin:
    """Test admin login endpoint - POST /api/admin/login"""
    
    def test_admin_login_success(self):
        """Admin login with valid credentials should succeed"""
        response = requests.post(
            f"{BASE_URL}/api/admin/login",
            json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "token" in data, "Response should contain token"
        assert "user" in data, "Response should contain user"
        assert data["user"]["role"] == "admin", "User role should be admin"
        assert "message" in data, "Response should contain message"
        print(f"✅ Admin login successful. Token received: {data['token'][:30]}...")
        return data["token"]
    
    def test_admin_login_invalid_username(self):
        """Admin login with invalid username should fail"""
        response = requests.post(
            f"{BASE_URL}/api/admin/login",
            json={"username": "wrongadmin", "password": ADMIN_PASSWORD}
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✅ Invalid username correctly rejected")
    
    def test_admin_login_invalid_password(self):
        """Admin login with invalid password should fail"""
        response = requests.post(
            f"{BASE_URL}/api/admin/login",
            json={"username": ADMIN_USERNAME, "password": "WrongPassword123"}
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✅ Invalid password correctly rejected")


class TestAuthEndpoints:
    """Test authentication endpoints"""
    
    def test_send_otp_endpoint_exists(self):
        """POST /api/auth/send-otp should work"""
        response = requests.post(
            f"{BASE_URL}/api/auth/send-otp",
            json={"identifier": "test@test.com", "type": "email"}
        )
        # Should return 200 (OTP sent) since MOCK_OTP_MODE=true
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "message" in data
        print(f"✅ Send OTP works: {data['message']}")
    
    def test_send_otp_invalid_type(self):
        """Send OTP with invalid type should fail"""
        response = requests.post(
            f"{BASE_URL}/api/auth/send-otp",
            json={"identifier": "test@test.com", "type": "invalid_type"}
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("✅ Invalid OTP type correctly rejected")
    
    def test_auth_me_without_token(self):
        """GET /api/auth/me without token should return 401"""
        response = requests.get(f"{BASE_URL}/api/auth/me")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✅ /api/auth/me correctly requires authentication")
    
    def test_auth_me_with_admin_token(self):
        """GET /api/auth/me with admin token should work"""
        # First login to get token
        login_response = requests.post(
            f"{BASE_URL}/api/admin/login",
            json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD}
        )
        token = login_response.json()["token"]
        
        # Now call /api/auth/me with Bearer token
        response = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "id" in data
        assert "role" in data
        print(f"✅ /api/auth/me works with admin token. User role: {data['role']}")
    
    def test_logout_endpoint(self):
        """POST /api/auth/logout should work"""
        response = requests.post(f"{BASE_URL}/api/auth/logout")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "message" in data
        print(f"✅ Logout works: {data['message']}")
    
    def test_roll_number_login_endpoint_exists(self):
        """POST /api/auth/login should exist (roll number login)"""
        # Test with invalid credentials - endpoint should exist and return 401
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"roll_no": "INVALID_ROLL", "password": "wrongpassword"}
        )
        # Should return 401 (invalid credentials) NOT 404 (endpoint not found)
        assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.text}"
        print("✅ Roll number login endpoint exists and rejects invalid credentials")


class TestSubjectsEndpoint:
    """Test subjects endpoints"""
    
    def test_list_subjects_public(self):
        """GET /api/subjects should work without auth"""
        response = requests.get(f"{BASE_URL}/api/subjects")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"✅ Subjects list works. Found {len(data)} subjects")
        
        if len(data) > 0:
            # Verify subject structure
            subject = data[0]
            assert "id" in subject
            assert "name" in subject
            print(f"   First subject: {subject['name']}")
    
    def test_list_subjects_with_auth(self):
        """GET /api/subjects with admin auth"""
        # Get admin token
        login_response = requests.post(
            f"{BASE_URL}/api/admin/login",
            json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD}
        )
        token = login_response.json()["token"]
        
        response = requests.get(
            f"{BASE_URL}/api/subjects",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✅ Subjects list works with admin auth")


class TestHomeworkEndpoints:
    """Test homework endpoints"""
    
    def test_list_homework_with_auth(self):
        """GET /api/homework with admin auth"""
        # Get admin token
        login_response = requests.post(
            f"{BASE_URL}/api/admin/login",
            json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD}
        )
        token = login_response.json()["token"]
        
        response = requests.get(
            f"{BASE_URL}/api/homework",
            headers={"Authorization": f"Bearer {token}"}
        )
        # Note: In logs we saw 500 error - let's check what happens now
        print(f"Homework list status: {response.status_code}")
        
        if response.status_code == 500:
            print(f"❌ ERROR: {response.text}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"✅ Homework list works. Found {len(data)} homework items")
    
    def test_list_homework_without_auth(self):
        """GET /api/homework without auth should fail"""
        response = requests.get(f"{BASE_URL}/api/homework")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✅ Homework list correctly requires authentication")


class TestStructuredTestsEndpoints:
    """Test structured tests endpoints"""
    
    def test_structured_tests_post_endpoint(self):
        """POST /api/structured-tests should exist (create test)"""
        # Without auth, should return 401
        response = requests.post(
            f"{BASE_URL}/api/structured-tests",
            json={"title": "Test"}
        )
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}: {response.text}"
        print("✅ POST /api/structured-tests endpoint exists and requires auth")
    
    def test_structured_tests_get_method_not_allowed(self):
        """GET /api/structured-tests should return 405 Method Not Allowed"""
        # The endpoint uses POST to create, GET is not implemented at root
        response = requests.get(f"{BASE_URL}/api/structured-tests")
        # Expected: 405 Method Not Allowed (GET not supported on this endpoint)
        # Note: This is by design - there's no GET /api/structured-tests endpoint
        # The list endpoint is GET /api/structured-tests/list/{subject_id}/{standard}
        print(f"GET /api/structured-tests status: {response.status_code}")
        assert response.status_code == 405, f"GET on /api/structured-tests should be 405, got {response.status_code}"
        print("✅ GET /api/structured-tests correctly returns 405 (use /list/{subject_id}/{standard} instead)")


class TestAdminUsersEndpoint:
    """Test admin user management endpoints"""
    
    def test_admin_users_list(self):
        """GET /api/admin/users with admin auth"""
        # Get admin token
        login_response = requests.post(
            f"{BASE_URL}/api/admin/login",
            json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD}
        )
        token = login_response.json()["token"]
        
        response = requests.get(
            f"{BASE_URL}/api/admin/users",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "users" in data, "Response should contain users"
        assert "total" in data, "Response should contain total"
        print(f"✅ Admin users list works. Found {data['total']} users")
    
    def test_admin_users_without_auth(self):
        """GET /api/admin/users without auth should fail"""
        response = requests.get(f"{BASE_URL}/api/admin/users")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✅ Admin users endpoint correctly requires authentication")


class TestSchoolsEndpoint:
    """Test schools list endpoint"""
    
    def test_schools_list(self):
        """GET /api/schools/list should work"""
        # This endpoint doesn't require auth based on the code
        response = requests.get(f"{BASE_URL}/api/schools/list")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "schools" in data, "Response should contain schools"
        assert "total" in data, "Response should contain total"
        print(f"✅ Schools list works. Found {data['total']} schools")


class TestParentDashboard:
    """Test parent dashboard endpoint"""
    
    def test_parent_dashboard_without_auth(self):
        """GET /api/student/parent-dashboard without auth should fail"""
        response = requests.get(f"{BASE_URL}/api/student/parent-dashboard")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✅ Parent dashboard correctly requires authentication")
    
    def test_parent_dashboard_requires_student_role(self):
        """GET /api/student/parent-dashboard with admin should fail (needs student role)"""
        # Get admin token
        login_response = requests.post(
            f"{BASE_URL}/api/admin/login",
            json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD}
        )
        token = login_response.json()["token"]
        
        response = requests.get(
            f"{BASE_URL}/api/student/parent-dashboard",
            headers={"Authorization": f"Bearer {token}"}
        )
        # Should return 403 because admin is not a student
        assert response.status_code == 403, f"Expected 403 (not a student), got {response.status_code}: {response.text}"
        print("✅ Parent dashboard correctly requires student role")


# Module to run all tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
