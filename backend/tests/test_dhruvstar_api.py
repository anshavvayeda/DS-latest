"""
Backend API Tests for DhruvStar School Application
Tests the key features:
- Student and Teacher login flows
- Teacher Analytics API
- Parent Dashboard API
- Subject listing with grid support
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://fullstack-study.preview.emergentagent.com')

# Test credentials from the review request
TEACHER_PHONE = "9999900001"
STUDENT_PHONE = "9999900002"
OTP = "123456"


class TestHealthAndBasicAPIs:
    """Test basic health and connectivity"""
    
    def test_health_endpoint(self):
        """Test health endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        print(f"✅ Health endpoint OK: {data}")
    
    def test_readiness_endpoint(self):
        """Test readiness endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/readiness")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "ready"
        print(f"✅ Readiness endpoint OK: {data}")


class TestAuthenticationFlows:
    """Test OTP-based authentication for teacher and student"""
    
    def test_teacher_send_otp(self):
        """Teacher: Send OTP should succeed"""
        response = requests.post(
            f"{BASE_URL}/api/auth/send-otp",
            json={"identifier": TEACHER_PHONE, "type": "phone"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "OTP sent" in data.get("message", "")
        print(f"✅ Teacher OTP sent: {data}")
    
    def test_student_send_otp(self):
        """Student: Send OTP should succeed"""
        response = requests.post(
            f"{BASE_URL}/api/auth/send-otp",
            json={"identifier": STUDENT_PHONE, "type": "phone"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "OTP sent" in data.get("message", "")
        print(f"✅ Student OTP sent: {data}")
    
    def test_teacher_verify_otp_and_login(self):
        """Teacher: Verify OTP and get auth cookie"""
        # First send OTP
        requests.post(
            f"{BASE_URL}/api/auth/send-otp",
            json={"identifier": TEACHER_PHONE, "type": "phone"}
        )
        
        # Then verify
        session = requests.Session()
        response = session.post(
            f"{BASE_URL}/api/auth/verify-otp",
            json={"identifier": TEACHER_PHONE, "code": OTP}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("message") == "Login successful"
        assert data.get("user", {}).get("role") == "teacher"
        print(f"✅ Teacher logged in: {data.get('user')}")
        return session
    
    def test_student_verify_otp_and_login(self):
        """Student: Verify OTP and get auth cookie"""
        # First send OTP
        requests.post(
            f"{BASE_URL}/api/auth/send-otp",
            json={"identifier": STUDENT_PHONE, "type": "phone"}
        )
        
        # Then verify
        session = requests.Session()
        response = session.post(
            f"{BASE_URL}/api/auth/verify-otp",
            json={"identifier": STUDENT_PHONE, "code": OTP}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("message") == "Login successful"
        assert data.get("user", {}).get("role") == "student"
        print(f"✅ Student logged in: {data.get('user')}")
        return session


class TestTeacherAnalyticsAPI:
    """Test Teacher Analytics dashboard API - verifies student categories and top performers"""
    
    @pytest.fixture
    def teacher_session(self):
        """Create authenticated teacher session"""
        # Send OTP
        requests.post(
            f"{BASE_URL}/api/auth/send-otp",
            json={"identifier": TEACHER_PHONE, "type": "phone"}
        )
        # Verify OTP
        session = requests.Session()
        response = session.post(
            f"{BASE_URL}/api/auth/verify-otp",
            json={"identifier": TEACHER_PHONE, "code": OTP}
        )
        assert response.status_code == 200
        return session
    
    def test_get_teacher_analytics_for_class_5(self, teacher_session):
        """Teacher Analytics API should return summary, top performers, and students list"""
        response = teacher_session.get(f"{BASE_URL}/api/teacher/analytics/5")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify structure - Summary
        assert "summary" in data
        assert "total_students" in data["summary"]
        assert "strong_count" in data["summary"]
        assert "average_count" in data["summary"]
        assert "weak_count" in data["summary"]
        
        # Verify structure - Top performers
        assert "top_performers" in data
        assert isinstance(data["top_performers"], list)
        
        # Verify structure - Students list
        assert "students" in data
        assert isinstance(data["students"], list)
        
        # Verify structure - Subjects
        assert "subjects" in data
        assert isinstance(data["subjects"], list)
        
        print(f"✅ Teacher Analytics API response:")
        print(f"   - Total students: {data['summary']['total_students']}")
        print(f"   - Strong: {data['summary']['strong_count']}")
        print(f"   - Average: {data['summary']['average_count']}")
        print(f"   - Weak: {data['summary']['weak_count']}")
        print(f"   - Top performers: {len(data['top_performers'])}")
        print(f"   - Subjects: {data['subjects']}")
        
        # If there are top performers, verify structure
        if len(data["top_performers"]) > 0:
            top = data["top_performers"][0]
            assert "student_name" in top
            assert "roll_no" in top
            assert "overall_average" in top
            assert "subject_wise_performance" in top
            print(f"   - Top performer: {top['student_name']} ({top['overall_average']:.1f}%)")
    
    def test_teacher_analytics_unauthenticated_fails(self):
        """Analytics API should require authentication"""
        response = requests.get(f"{BASE_URL}/api/teacher/analytics/5")
        assert response.status_code == 401
        print("✅ Analytics API correctly requires authentication")


class TestParentDashboardAPI:
    """Test Parent Dashboard API - verifies student performance data"""
    
    @pytest.fixture
    def student_session(self):
        """Create authenticated student session"""
        # Send OTP
        requests.post(
            f"{BASE_URL}/api/auth/send-otp",
            json={"identifier": STUDENT_PHONE, "type": "phone"}
        )
        # Verify OTP
        session = requests.Session()
        response = session.post(
            f"{BASE_URL}/api/auth/verify-otp",
            json={"identifier": STUDENT_PHONE, "code": OTP}
        )
        assert response.status_code == 200
        return session
    
    def test_get_parent_dashboard_data(self, student_session):
        """Parent Dashboard API should return student performance overview"""
        response = student_session.get(f"{BASE_URL}/api/student/parent-dashboard")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify student info
        assert "student_name" in data
        assert "standard" in data
        assert "roll_no" in data
        
        # Verify overall stats
        assert "overall_stats" in data
        stats = data["overall_stats"]
        assert "total_tests_attempted" in stats
        assert "overall_average_score" in stats
        assert "overall_homework_completion" in stats
        assert "total_missed_homework" in stats
        
        # Verify subjects list
        assert "subjects" in data
        assert isinstance(data["subjects"], list)
        
        print(f"✅ Parent Dashboard API response:")
        print(f"   - Student: {data['student_name']}")
        print(f"   - Class: {data['standard']}")
        print(f"   - Roll No: {data['roll_no']}")
        print(f"   - Tests taken: {stats['total_tests_attempted']}")
        print(f"   - Average score: {stats['overall_average_score']}%")
        print(f"   - Subjects: {len(data['subjects'])}")
        
        # Verify subject structure if any exist
        if len(data["subjects"]) > 0:
            subj = data["subjects"][0]
            assert "subject_name" in subj
            assert "average_score" in subj
            assert "classification" in subj
            print(f"   - First subject: {subj['subject_name']} ({subj['average_score']}%)")
    
    def test_parent_dashboard_unauthenticated_fails(self):
        """Parent Dashboard API should require authentication"""
        response = requests.get(f"{BASE_URL}/api/student/parent-dashboard")
        assert response.status_code == 401
        print("✅ Parent Dashboard API correctly requires authentication")


class TestSubjectsAPI:
    """Test Subjects listing API - verifies 2x3 grid can render"""
    
    @pytest.fixture
    def student_session(self):
        """Create authenticated student session"""
        requests.post(
            f"{BASE_URL}/api/auth/send-otp",
            json={"identifier": STUDENT_PHONE, "type": "phone"}
        )
        session = requests.Session()
        session.post(
            f"{BASE_URL}/api/auth/verify-otp",
            json={"identifier": STUDENT_PHONE, "code": OTP}
        )
        return session
    
    def test_get_subjects_for_standard_5(self, student_session):
        """Subjects API should return list for standard 5"""
        response = student_session.get(f"{BASE_URL}/api/subjects?standard=5")
        
        assert response.status_code == 200
        data = response.json()
        
        # Should be a list of subjects
        assert isinstance(data, list)
        
        print(f"✅ Subjects API for Class 5:")
        print(f"   - Total subjects: {len(data)}")
        
        # Verify each subject has required fields
        for subj in data:
            assert "id" in subj
            assert "name" in subj
            assert "standard" in subj
            print(f"   - {subj['name']} (Class {subj['standard']})")
        
        # For 2x3 grid layout, we need at least up to 6 subjects
        print(f"   - Grid layout ready: {'Yes' if len(data) <= 6 else 'May need scroll'}")


class TestStudentProfile:
    """Test Student Profile API"""
    
    @pytest.fixture
    def student_session(self):
        """Create authenticated student session"""
        requests.post(
            f"{BASE_URL}/api/auth/send-otp",
            json={"identifier": STUDENT_PHONE, "type": "phone"}
        )
        session = requests.Session()
        session.post(
            f"{BASE_URL}/api/auth/verify-otp",
            json={"identifier": STUDENT_PHONE, "code": OTP}
        )
        return session
    
    def test_get_student_profile(self, student_session):
        """Student profile API should return profile details"""
        response = student_session.get(f"{BASE_URL}/api/student/profile")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify profile fields
        assert "name" in data
        assert "roll_no" in data
        assert "standard" in data
        assert "school_name" in data
        
        print(f"✅ Student Profile:")
        print(f"   - Name: {data['name']}")
        print(f"   - Roll No: {data['roll_no']}")
        print(f"   - Class: {data['standard']}")
        print(f"   - School: {data['school_name']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
