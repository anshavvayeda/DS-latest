"""
Test Admin Features - StudyBuddy Backend Tests
Tests admin login, user registration, user management APIs.

Test credentials from environment:
- Admin: admin / Admin@123
- Test data phones: 9876543212 (Student@123), 9111111111, 9111111112 (Bulk@123)
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL').rstrip('/')


class TestAdminAuthentication:
    """Test admin login/logout flows"""
    
    def test_admin_login_success(self):
        """Test admin login with valid credentials"""
        session = requests.Session()
        response = session.post(
            f"{BASE_URL}/api/admin/login",
            json={"username": "admin", "password": "Admin@123"}
        )
        print(f"Admin login response: {response.status_code} - {response.json()}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Admin login successful"
        assert data["user"]["role"] == "admin"
        assert data["user"]["username"] == "admin"
        
        # Verify cookie is set
        assert "auth_token" in session.cookies
        print("✅ Admin login successful with cookie set")
    
    def test_admin_login_invalid_password(self):
        """Test admin login with wrong password"""
        response = requests.post(
            f"{BASE_URL}/api/admin/login",
            json={"username": "admin", "password": "wrongpassword"}
        )
        print(f"Invalid password response: {response.status_code}")
        
        assert response.status_code == 401
        assert "Invalid admin credentials" in response.json().get("detail", "")
        print("✅ Invalid password correctly rejected")
    
    def test_admin_login_invalid_username(self):
        """Test admin login with wrong username"""
        response = requests.post(
            f"{BASE_URL}/api/admin/login",
            json={"username": "wronguser", "password": "Admin@123"}
        )
        print(f"Invalid username response: {response.status_code}")
        
        assert response.status_code == 401
        print("✅ Invalid username correctly rejected")


@pytest.fixture(scope="class")
def admin_session():
    """Create and authenticate admin session"""
    session = requests.Session()
    response = session.post(
        f"{BASE_URL}/api/admin/login",
        json={"username": "admin", "password": "Admin@123"}
    )
    if response.status_code != 200:
        pytest.skip(f"Admin login failed: {response.status_code} - {response.text}")
    print(f"✅ Admin session created")
    return session


class TestAdminStudentRegistration:
    """Test single student registration via admin"""
    
    def test_register_student_success(self, admin_session):
        """Test registering a new student via admin"""
        # Generate unique phone/roll_no to avoid conflicts
        unique_id = str(uuid.uuid4())[:8]
        test_phone = f"91000{unique_id[:5]}"
        test_roll = f"TEST_ROLL_{unique_id}"
        
        payload = {
            "name": f"Test Student {unique_id}",
            "school_name": "Test School",
            "standard": 5,
            "roll_no": test_roll,
            "gender": "male",
            "phone": test_phone,
            "email": f"test_{unique_id}@test.com",
            "parent_phone": "",
            "password": "TestPass@123",
            "is_active": True,
            "role": "student"
        }
        
        response = admin_session.post(
            f"{BASE_URL}/api/admin/register-student",
            json=payload
        )
        print(f"Register student response: {response.status_code} - {response.json()}")
        
        assert response.status_code == 200
        data = response.json()
        assert "Student registered successfully" in data["message"]
        assert data["user"]["phone"] == test_phone
        assert data["user"]["role"] == "student"
        assert data["user"]["roll_no"] == test_roll
        print(f"✅ Student registered: {data['user']['id']}")
        
        # Store for cleanup
        return data["user"]["id"]
    
    def test_register_teacher_success(self, admin_session):
        """Test registering a teacher via admin"""
        unique_id = str(uuid.uuid4())[:8]
        test_phone = f"92000{unique_id[:5]}"
        
        payload = {
            "name": f"Test Teacher {unique_id}",
            "school_name": "Test School",
            "standard": 1,  # Required but not used for teachers
            "roll_no": f"TEACH_{unique_id}",
            "gender": "female",
            "phone": test_phone,
            "email": f"teacher_{unique_id}@test.com",
            "parent_phone": "",
            "password": "TeachPass@123",
            "is_active": True,
            "role": "teacher"
        }
        
        response = admin_session.post(
            f"{BASE_URL}/api/admin/register-student",
            json=payload
        )
        print(f"Register teacher response: {response.status_code} - {response.json()}")
        
        assert response.status_code == 200
        data = response.json()
        assert "Teacher registered successfully" in data["message"]
        assert data["user"]["role"] == "teacher"
        print(f"✅ Teacher registered: {data['user']['id']}")
    
    def test_register_duplicate_phone_fails(self, admin_session):
        """Test that duplicate phone registration fails"""
        # First registration
        unique_id = str(uuid.uuid4())[:8]
        test_phone = f"93000{unique_id[:5]}"
        
        payload = {
            "name": "First User",
            "school_name": "Test School",
            "standard": 5,
            "roll_no": f"FIRST_{unique_id}",
            "gender": "male",
            "phone": test_phone,
            "password": "FirstPass@123",
            "is_active": True,
            "role": "student"
        }
        
        admin_session.post(f"{BASE_URL}/api/admin/register-student", json=payload)
        
        # Second registration with same phone
        payload["name"] = "Duplicate User"
        payload["roll_no"] = f"DUP_{unique_id}"
        
        response = admin_session.post(
            f"{BASE_URL}/api/admin/register-student",
            json=payload
        )
        print(f"Duplicate phone response: {response.status_code}")
        
        assert response.status_code == 400
        assert "already registered" in response.json().get("detail", "").lower()
        print("✅ Duplicate phone correctly rejected")


class TestAdminBulkRegistration:
    """Test bulk student registration via admin"""
    
    def test_bulk_register_success(self, admin_session):
        """Test bulk registration of multiple students"""
        unique_id = str(uuid.uuid4())[:8]
        
        students = [
            {
                "name": f"Bulk Student 1 {unique_id}",
                "school_name": "Bulk Test School",
                "standard": 6,
                "roll_no": f"BULK1_{unique_id}",
                "gender": "male",
                "phone": f"94001{unique_id[:4]}",
                "password": "BulkPass@123",
                "is_active": True,
                "role": "student"
            },
            {
                "name": f"Bulk Student 2 {unique_id}",
                "school_name": "Bulk Test School",
                "standard": 6,
                "roll_no": f"BULK2_{unique_id}",
                "gender": "female",
                "phone": f"94002{unique_id[:4]}",
                "password": "BulkPass@123",
                "is_active": True,
                "role": "student"
            }
        ]
        
        response = admin_session.post(
            f"{BASE_URL}/api/admin/bulk-register",
            json={"students": students}
        )
        print(f"Bulk register response: {response.status_code} - {response.json()}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert data["success_count"] >= 1
        print(f"✅ Bulk registration: {data['success_count']}/{data['total']} succeeded")


class TestAdminUserManagement:
    """Test user list, toggle active, and delete APIs"""
    
    def test_list_users(self, admin_session):
        """Test listing all users"""
        response = admin_session.get(f"{BASE_URL}/api/admin/users")
        print(f"List users response: {response.status_code} - Total: {response.json().get('total', 0)}")
        
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "users" in data
        assert isinstance(data["users"], list)
        print(f"✅ User list retrieved: {data['total']} users")
    
    def test_list_users_filter_by_role(self, admin_session):
        """Test filtering users by role"""
        response = admin_session.get(f"{BASE_URL}/api/admin/users?role=student")
        print(f"Filter by role response: {response.status_code}")
        
        assert response.status_code == 200
        data = response.json()
        
        # All returned users should be students
        for user in data["users"]:
            assert user["role"] == "student"
        print(f"✅ Role filter working: {data['total']} students")
    
    def test_list_users_filter_by_status(self, admin_session):
        """Test filtering users by active status"""
        response = admin_session.get(f"{BASE_URL}/api/admin/users?is_active=true")
        print(f"Filter by status response: {response.status_code}")
        
        assert response.status_code == 200
        data = response.json()
        
        for user in data["users"]:
            assert user["is_active"] == True
        print(f"✅ Status filter working: {data['total']} active users")
    
    def test_toggle_user_active(self, admin_session):
        """Test toggling user active status"""
        # First create a user to toggle
        unique_id = str(uuid.uuid4())[:8]
        payload = {
            "name": f"Toggle User {unique_id}",
            "school_name": "Test School",
            "standard": 5,
            "roll_no": f"TOGGLE_{unique_id}",
            "gender": "male",
            "phone": f"95000{unique_id[:5]}",
            "password": "TogglePass@123",
            "is_active": True,
            "role": "student"
        }
        
        create_response = admin_session.post(
            f"{BASE_URL}/api/admin/register-student",
            json=payload
        )
        
        if create_response.status_code != 200:
            pytest.skip(f"Failed to create test user: {create_response.text}")
        
        user_id = create_response.json()["user"]["id"]
        
        # Toggle to deactivate
        toggle_response = admin_session.put(
            f"{BASE_URL}/api/admin/user/{user_id}/toggle-active"
        )
        print(f"Toggle response: {toggle_response.status_code} - {toggle_response.json()}")
        
        assert toggle_response.status_code == 200
        data = toggle_response.json()
        assert data["is_active"] == False
        assert "deactivated" in data["message"].lower()
        print(f"✅ User deactivated successfully")
        
        # Toggle again to activate
        toggle_response2 = admin_session.put(
            f"{BASE_URL}/api/admin/user/{user_id}/toggle-active"
        )
        
        assert toggle_response2.status_code == 200
        assert toggle_response2.json()["is_active"] == True
        print(f"✅ User reactivated successfully")
    
    def test_delete_user(self, admin_session):
        """Test deleting a user"""
        # Create a user to delete
        unique_id = str(uuid.uuid4())[:8]
        payload = {
            "name": f"Delete User {unique_id}",
            "school_name": "Test School",
            "standard": 5,
            "roll_no": f"DELETE_{unique_id}",
            "gender": "male",
            "phone": f"96000{unique_id[:5]}",
            "password": "DeletePass@123",
            "is_active": True,
            "role": "student"
        }
        
        create_response = admin_session.post(
            f"{BASE_URL}/api/admin/register-student",
            json=payload
        )
        
        if create_response.status_code != 200:
            pytest.skip(f"Failed to create test user: {create_response.text}")
        
        user_id = create_response.json()["user"]["id"]
        
        # Delete the user
        delete_response = admin_session.delete(
            f"{BASE_URL}/api/admin/user/{user_id}"
        )
        print(f"Delete response: {delete_response.status_code} - {delete_response.json()}")
        
        assert delete_response.status_code == 200
        assert "deleted" in delete_response.json()["message"].lower()
        print(f"✅ User deleted successfully")
        
        # Verify user is gone from list
        list_response = admin_session.get(f"{BASE_URL}/api/admin/users")
        users = list_response.json()["users"]
        user_ids = [u["id"] for u in users]
        assert user_id not in user_ids
        print(f"✅ Deleted user no longer in list")


class TestPasswordLogin:
    """Test password-based login for admin-registered users"""
    
    def test_password_login_success(self, admin_session):
        """Test login with phone and password for admin-registered user"""
        # Create a user with password
        unique_id = str(uuid.uuid4())[:8]
        test_phone = f"97000{unique_id[:5]}"
        test_password = "LoginTest@123"
        
        payload = {
            "name": f"Login Test User {unique_id}",
            "school_name": "Test School",
            "standard": 5,
            "roll_no": f"LOGIN_{unique_id}",
            "gender": "male",
            "phone": test_phone,
            "password": test_password,
            "is_active": True,
            "role": "student"
        }
        
        create_response = admin_session.post(
            f"{BASE_URL}/api/admin/register-student",
            json=payload
        )
        
        if create_response.status_code != 200:
            pytest.skip(f"Failed to create test user: {create_response.text}")
        
        # Now login with password
        login_session = requests.Session()
        login_response = login_session.post(
            f"{BASE_URL}/api/auth/login-password",
            json={"phone": test_phone, "password": test_password}
        )
        print(f"Password login response: {login_response.status_code} - {login_response.json()}")
        
        assert login_response.status_code == 200
        data = login_response.json()
        assert data["message"] == "Login successful"
        assert data["user"]["phone"] == test_phone
        assert data["user"]["role"] == "student"
        print(f"✅ Password login successful")
    
    def test_password_login_wrong_password(self, admin_session):
        """Test password login with wrong password fails"""
        # Use existing test user
        unique_id = str(uuid.uuid4())[:8]
        test_phone = f"98000{unique_id[:5]}"
        
        payload = {
            "name": f"Wrong Pass User {unique_id}",
            "school_name": "Test School",
            "standard": 5,
            "roll_no": f"WRONG_{unique_id}",
            "gender": "male",
            "phone": test_phone,
            "password": "CorrectPass@123",
            "is_active": True,
            "role": "student"
        }
        
        admin_session.post(f"{BASE_URL}/api/admin/register-student", json=payload)
        
        # Try to login with wrong password
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login-password",
            json={"phone": test_phone, "password": "WrongPassword@123"}
        )
        print(f"Wrong password response: {login_response.status_code}")
        
        assert login_response.status_code == 401
        print(f"✅ Wrong password correctly rejected")
    
    def test_password_login_inactive_user(self, admin_session):
        """Test password login for inactive user fails"""
        # Create and deactivate a user
        unique_id = str(uuid.uuid4())[:8]
        test_phone = f"99000{unique_id[:5]}"
        
        payload = {
            "name": f"Inactive User {unique_id}",
            "school_name": "Test School",
            "standard": 5,
            "roll_no": f"INACTIVE_{unique_id}",
            "gender": "male",
            "phone": test_phone,
            "password": "InactivePass@123",
            "is_active": True,
            "role": "student"
        }
        
        create_response = admin_session.post(
            f"{BASE_URL}/api/admin/register-student",
            json=payload
        )
        
        if create_response.status_code != 200:
            pytest.skip(f"Failed to create test user")
        
        user_id = create_response.json()["user"]["id"]
        
        # Deactivate the user
        admin_session.put(f"{BASE_URL}/api/admin/user/{user_id}/toggle-active")
        
        # Try to login
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login-password",
            json={"phone": test_phone, "password": "InactivePass@123"}
        )
        print(f"Inactive user login response: {login_response.status_code}")
        
        assert login_response.status_code == 403
        assert "not active" in login_response.json().get("detail", "").lower()
        print(f"✅ Inactive user login correctly rejected")


class TestOTPLoginStillWorks:
    """Verify OTP login still works alongside password login"""
    
    def test_otp_login_teacher(self):
        """Test OTP login for teacher still works"""
        session = requests.Session()
        
        # Send OTP
        send_response = session.post(
            f"{BASE_URL}/api/auth/send-otp",
            json={"identifier": "9999900001", "type": "phone"}
        )
        print(f"Send OTP response: {send_response.status_code}")
        assert send_response.status_code == 200
        
        # Verify OTP
        verify_response = session.post(
            f"{BASE_URL}/api/auth/verify-otp",
            json={"identifier": "9999900001", "code": "123456"}
        )
        print(f"Verify OTP response: {verify_response.status_code} - {verify_response.json()}")
        
        assert verify_response.status_code == 200
        data = verify_response.json()
        assert data["message"] == "Login successful"
        assert data["user"]["role"] == "teacher"
        print(f"✅ OTP login for teacher working")
    
    def test_otp_login_student(self):
        """Test OTP login for student still works"""
        session = requests.Session()
        
        # Send OTP
        send_response = session.post(
            f"{BASE_URL}/api/auth/send-otp",
            json={"identifier": "9999900002", "type": "phone"}
        )
        assert send_response.status_code == 200
        
        # Verify OTP
        verify_response = session.post(
            f"{BASE_URL}/api/auth/verify-otp",
            json={"identifier": "9999900002", "code": "123456"}
        )
        print(f"Verify OTP response: {verify_response.status_code}")
        
        assert verify_response.status_code == 200
        data = verify_response.json()
        assert data["user"]["role"] == "student"
        print(f"✅ OTP login for student working")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
