"""
Backend API Tests for StudyBuddy - Testing Auth and Parent Dashboard
Tests: Teacher login, Student login, Parent Dashboard API, Logout
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    BASE_URL = "https://homework-ui-sync.preview.emergentagent.com"

class TestHealthCheck:
    """Health check tests"""
    
    def test_health_endpoint(self):
        """Test basic health endpoint"""
        response = requests.get(f"{BASE_URL}/health")
        assert response.status_code == 200, f"Health check failed: {response.text}"
        data = response.json()
        assert data.get("status") == "healthy"
        print("✅ Health check passed")


class TestTeacherAuth:
    """Teacher authentication flow tests"""
    
    def test_teacher_send_otp(self):
        """Test sending OTP to teacher phone"""
        response = requests.post(
            f"{BASE_URL}/api/auth/send-otp",
            json={"identifier": "9999900001", "type": "phone"}
        )
        assert response.status_code == 200, f"Send OTP failed: {response.text}"
        data = response.json()
        assert "message" in data
        assert data["identifier"] == "9999900001"
        print("✅ Teacher Send OTP passed")
    
    def test_teacher_verify_otp(self):
        """Test verifying OTP for teacher"""
        session = requests.Session()
        
        # Send OTP first
        send_resp = session.post(
            f"{BASE_URL}/api/auth/send-otp",
            json={"identifier": "9999900001", "type": "phone"}
        )
        assert send_resp.status_code == 200, f"Send OTP failed: {send_resp.text}"
        
        # Verify OTP with mock value 123456
        verify_resp = session.post(
            f"{BASE_URL}/api/auth/verify-otp",
            json={"identifier": "9999900001", "code": "123456"}
        )
        assert verify_resp.status_code == 200, f"Verify OTP failed: {verify_resp.text}"
        data = verify_resp.json()
        
        # Check response structure
        assert "user" in data, "Response missing user object"
        assert data["user"]["role"] == "teacher", f"Expected teacher role, got {data['user']['role']}"
        assert data["user"]["phone"] == "9999900001"
        print("✅ Teacher Verify OTP passed - Role:", data["user"]["role"])
        return session
    
    def test_teacher_me_endpoint(self):
        """Test /auth/me endpoint for teacher"""
        session = requests.Session()
        
        # Login
        session.post(f"{BASE_URL}/api/auth/send-otp", json={"identifier": "9999900001", "type": "phone"})
        session.post(f"{BASE_URL}/api/auth/verify-otp", json={"identifier": "9999900001", "code": "123456"})
        
        # Get me
        me_resp = session.get(f"{BASE_URL}/api/auth/me")
        assert me_resp.status_code == 200, f"Get me failed: {me_resp.text}"
        data = me_resp.json()
        assert data["role"] == "teacher"
        print("✅ Teacher /auth/me passed")
    
    def test_teacher_logout(self):
        """Test logout for teacher"""
        session = requests.Session()
        
        # Login
        session.post(f"{BASE_URL}/api/auth/send-otp", json={"identifier": "9999900001", "type": "phone"})
        session.post(f"{BASE_URL}/api/auth/verify-otp", json={"identifier": "9999900001", "code": "123456"})
        
        # Verify logged in
        me_resp = session.get(f"{BASE_URL}/api/auth/me")
        assert me_resp.status_code == 200
        
        # Logout
        logout_resp = session.post(f"{BASE_URL}/api/auth/logout")
        assert logout_resp.status_code == 200, f"Logout failed: {logout_resp.text}"
        
        # Verify logged out - should get 401
        me_resp2 = session.get(f"{BASE_URL}/api/auth/me")
        assert me_resp2.status_code == 401, "Should be logged out"
        print("✅ Teacher logout passed")


class TestStudentAuth:
    """Student authentication flow tests"""
    
    def test_student_send_otp(self):
        """Test sending OTP to student phone"""
        response = requests.post(
            f"{BASE_URL}/api/auth/send-otp",
            json={"identifier": "9999900002", "type": "phone"}
        )
        assert response.status_code == 200, f"Send OTP failed: {response.text}"
        data = response.json()
        assert "message" in data
        assert data["identifier"] == "9999900002"
        print("✅ Student Send OTP passed")
    
    def test_student_verify_otp(self):
        """Test verifying OTP for student"""
        session = requests.Session()
        
        # Send OTP first
        send_resp = session.post(
            f"{BASE_URL}/api/auth/send-otp",
            json={"identifier": "9999900002", "type": "phone"}
        )
        assert send_resp.status_code == 200
        
        # Verify OTP with mock value 123456
        verify_resp = session.post(
            f"{BASE_URL}/api/auth/verify-otp",
            json={"identifier": "9999900002", "code": "123456"}
        )
        assert verify_resp.status_code == 200, f"Verify OTP failed: {verify_resp.text}"
        data = verify_resp.json()
        
        # Check response structure
        assert "user" in data, "Response missing user object"
        assert data["user"]["role"] == "student", f"Expected student role, got {data['user']['role']}"
        print("✅ Student Verify OTP passed - Role:", data["user"]["role"])
        return session
    
    def test_student_profile(self):
        """Test getting student profile"""
        session = requests.Session()
        
        # Login
        session.post(f"{BASE_URL}/api/auth/send-otp", json={"identifier": "9999900002", "type": "phone"})
        session.post(f"{BASE_URL}/api/auth/verify-otp", json={"identifier": "9999900002", "code": "123456"})
        
        # Get profile
        profile_resp = session.get(f"{BASE_URL}/api/student/profile")
        assert profile_resp.status_code == 200, f"Get profile failed: {profile_resp.text}"
        data = profile_resp.json()
        
        assert "name" in data
        assert "roll_no" in data
        assert "standard" in data
        print(f"✅ Student profile passed - Name: {data['name']}, Standard: {data['standard']}")


class TestParentDashboard:
    """Parent Dashboard API tests"""
    
    def test_parent_dashboard_endpoint(self):
        """Test parent dashboard returns data with correct structure"""
        session = requests.Session()
        
        # Login as student
        session.post(f"{BASE_URL}/api/auth/send-otp", json={"identifier": "9999900002", "type": "phone"})
        session.post(f"{BASE_URL}/api/auth/verify-otp", json={"identifier": "9999900002", "code": "123456"})
        
        # Get parent dashboard
        dashboard_resp = session.get(f"{BASE_URL}/api/student/parent-dashboard")
        assert dashboard_resp.status_code == 200, f"Parent dashboard failed: {dashboard_resp.text}"
        data = dashboard_resp.json()
        
        # Verify response structure
        assert "student_name" in data, "Missing student_name"
        assert "standard" in data, "Missing standard"
        assert "roll_no" in data, "Missing roll_no"
        assert "subjects" in data, "Missing subjects"
        assert "overall_stats" in data, "Missing overall_stats"
        
        print(f"✅ Parent dashboard passed - Student: {data['student_name']}")
        print(f"   Subjects: {len(data['subjects'])}")
        print(f"   Overall stats: {data['overall_stats']}")
        return data
    
    def test_parent_dashboard_subject_structure(self):
        """Test subject data structure in parent dashboard"""
        session = requests.Session()
        
        # Login as student
        session.post(f"{BASE_URL}/api/auth/send-otp", json={"identifier": "9999900002", "type": "phone"})
        session.post(f"{BASE_URL}/api/auth/verify-otp", json={"identifier": "9999900002", "code": "123456"})
        
        # Get parent dashboard
        dashboard_resp = session.get(f"{BASE_URL}/api/student/parent-dashboard")
        data = dashboard_resp.json()
        
        if data["subjects"]:
            subject = data["subjects"][0]
            assert "subject_name" in subject, "Missing subject_name"
            assert "test_performance" in subject, "Missing test_performance"
            assert "average_score" in subject, "Missing average_score"
            assert "classification" in subject, "Missing classification"
            assert "syllabus_progress" in subject, "Missing syllabus_progress"
            
            print(f"✅ Subject structure verified")
            print(f"   Subject: {subject['subject_name']}")
            print(f"   Classification: {subject['classification']}")
            print(f"   Test performance entries: {len(subject['test_performance'])}")
            
            # Check test_performance structure (for line chart data)
            if subject['test_performance']:
                perf = subject['test_performance'][0]
                assert "percentage" in perf, "Missing percentage in test_performance"
                assert "date" in perf, "Missing date in test_performance"
                print(f"   First test score: {perf['percentage']}%")


class TestSubjects:
    """Subject API tests"""
    
    def test_get_subjects_for_standard(self):
        """Test getting subjects for a specific standard"""
        session = requests.Session()
        
        # Login as student
        session.post(f"{BASE_URL}/api/auth/send-otp", json={"identifier": "9999900002", "type": "phone"})
        session.post(f"{BASE_URL}/api/auth/verify-otp", json={"identifier": "9999900002", "code": "123456"})
        
        # Get subjects for standard 5 (based on test data)
        subjects_resp = session.get(f"{BASE_URL}/api/subjects?standard=5")
        assert subjects_resp.status_code == 200, f"Get subjects failed: {subjects_resp.text}"
        data = subjects_resp.json()
        
        assert isinstance(data, list), "Subjects should be a list"
        print(f"✅ Subjects API passed - Found {len(data)} subjects")
        
        for subj in data:
            print(f"   - {subj['name']} (Standard {subj['standard']})")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
