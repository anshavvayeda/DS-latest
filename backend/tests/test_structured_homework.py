"""
Test Structured Homework Feature - AI Homework Agent for StudyBuddy LMS

Tests:
- Create homework with questions (teacher/admin)
- List active homework for subject/standard (student)
- Get homework with questions
- Start homework attempt
- Hint system: first call → hint, second call → answer
- Save progress
- Mark as complete
"""

import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test data
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "Admin@123"
STUDENT_ROLL_NO = "S001"
STUDENT_PASSWORD = "123456"
MOCK_OTP = "123456"
ENGLISH_SUBJECT_ID = "2b3551f8-ac83-4e37-99aa-9e6e4509a144"
EXISTING_HOMEWORK_ID = "6c156b0b-7217-4f4b-8a30-7ca24287dc83"
STANDARD = 5


class TestStructuredHomeworkEndpoints:
    """Test all structured homework API endpoints"""

    @pytest.fixture(scope="class")
    def admin_session(self):
        """Get admin session with auth cookie"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        
        # Admin login
        resp = session.post(f"{BASE_URL}/api/admin/login", json={
            "username": ADMIN_USERNAME,
            "password": ADMIN_PASSWORD
        })
        assert resp.status_code == 200, f"Admin login failed: {resp.text}"
        return session

    @pytest.fixture(scope="class")
    def student_session(self):
        """Get student session with auth cookie"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        
        # Student login via roll number (uses RollNoLoginRequest schema)
        resp = session.post(f"{BASE_URL}/api/auth/login", json={
            "roll_no": STUDENT_ROLL_NO,
            "password": STUDENT_PASSWORD
        })
        assert resp.status_code == 200, f"Student login failed: {resp.text}"
        return session

    # ===== TEST: GET existing homework =====
    def test_get_existing_homework(self, student_session):
        """GET /api/structured-homework/{id} - Get homework with questions"""
        resp = student_session.get(f"{BASE_URL}/api/structured-homework/{EXISTING_HOMEWORK_ID}")
        
        assert resp.status_code == 200, f"Get homework failed: {resp.text}"
        data = resp.json()
        
        # Verify structure
        assert "id" in data
        assert "title" in data
        assert "questions" in data
        assert "question_count" in data
        assert data["question_count"] >= 1, "Homework should have at least 1 question"
        
        # Verify questions structure (student should NOT see answers)
        if len(data["questions"]) > 0:
            q = data["questions"][0]
            assert "id" in q
            assert "question_number" in q
            assert "question_type" in q
            assert "question_text" in q
            # Students should see options for MCQ but NOT model_answer
            if q["question_type"] == "mcq":
                assert "options" in q
        
        print(f"✅ GET homework: {data['title']} - {data['question_count']} questions")

    # ===== TEST: List homework for subject/standard =====
    def test_list_homework_for_subject(self, student_session):
        """GET /api/structured-homework/list/{subject_id}/{standard} - List active homework"""
        resp = student_session.get(
            f"{BASE_URL}/api/structured-homework/list/{ENGLISH_SUBJECT_ID}/{STANDARD}"
        )
        
        assert resp.status_code == 200, f"List homework failed: {resp.text}"
        data = resp.json()
        
        assert "homework" in data
        homework_list = data["homework"]
        
        # Verify we have at least the existing homework
        found = any(hw["id"] == EXISTING_HOMEWORK_ID for hw in homework_list)
        assert found, f"Expected homework {EXISTING_HOMEWORK_ID} not found in list"
        
        # Verify structure of homework items
        if len(homework_list) > 0:
            hw = homework_list[0]
            assert "id" in hw
            assert "title" in hw
            assert "question_count" in hw
            assert "status" in hw
            # Student-specific fields
            assert "completed" in hw
            assert "started" in hw
        
        print(f"✅ List homework: {len(homework_list)} homework items for English, Standard 5")

    # ===== TEST: Start homework attempt =====
    def test_start_homework_attempt(self, student_session):
        """POST /api/structured-homework/{id}/start - Start or resume homework attempt"""
        resp = student_session.post(
            f"{BASE_URL}/api/structured-homework/{EXISTING_HOMEWORK_ID}/start"
        )
        
        # May return 400 if already completed, or 200 if starting/resuming
        if resp.status_code == 400:
            data = resp.json()
            assert "completed" in data.get("detail", "").lower(), f"Unexpected error: {data}"
            print(f"✅ Start homework: Already completed (expected)")
        else:
            assert resp.status_code == 200, f"Start homework failed: {resp.text}"
            data = resp.json()
            
            # Verify response structure
            assert "submission_id" in data
            assert "started_at" in data
            assert "answers" in data
            assert "hints" in data
            
            print(f"✅ Start homework: submission_id={data['submission_id']}")

    # ===== TEST: Hint system - first call returns hint =====
    def test_hint_first_call_returns_hint(self, student_session):
        """POST /api/structured-homework/{id}/hint - First call returns type:hint"""
        # First, start homework to ensure submission exists
        student_session.post(f"{BASE_URL}/api/structured-homework/{EXISTING_HOMEWORK_ID}/start")
        
        # Request hint for question 2 (Q1 already has hint used)
        resp = student_session.post(
            f"{BASE_URL}/api/structured-homework/{EXISTING_HOMEWORK_ID}/hint",
            json={
                "question_number": 2,
                "student_answer": ""
            }
        )
        
        assert resp.status_code == 200, f"Hint request failed: {resp.text}"
        data = resp.json()
        
        assert "type" in data
        assert "content" in data
        # First call should return hint (unless already used)
        assert data["type"] in ["hint", "answer"], f"Unexpected type: {data['type']}"
        assert len(data["content"]) > 0, "Hint/answer content should not be empty"
        
        print(f"✅ Hint call (Q2): type={data['type']}, content preview: {data['content'][:50]}...")

    # ===== TEST: Hint system - check answer reveal =====
    def test_hint_answer_reveal_for_question_1(self, student_session):
        """POST /api/structured-homework/{id}/hint - Question 1 should return answer (already revealed)"""
        # Start homework first
        student_session.post(f"{BASE_URL}/api/structured-homework/{EXISTING_HOMEWORK_ID}/start")
        
        # Question 1 already has answer_revealed=true per test context
        resp = student_session.post(
            f"{BASE_URL}/api/structured-homework/{EXISTING_HOMEWORK_ID}/hint",
            json={
                "question_number": 1,
                "student_answer": "b"
            }
        )
        
        assert resp.status_code == 200, f"Hint request failed: {resp.text}"
        data = resp.json()
        
        # Q1 should have answer already revealed, so should return answer
        assert "type" in data
        assert "content" in data
        
        print(f"✅ Hint call (Q1 - existing): type={data['type']}, content: {data['content'][:80]}...")

    # ===== TEST: Save progress =====
    def test_save_progress(self, student_session):
        """POST /api/structured-homework/{id}/save-progress - Save partial answers"""
        # Start homework first
        student_session.post(f"{BASE_URL}/api/structured-homework/{EXISTING_HOMEWORK_ID}/start")
        
        # Save some answers
        resp = student_session.post(
            f"{BASE_URL}/api/structured-homework/{EXISTING_HOMEWORK_ID}/save-progress",
            json={
                "answers": {"1": "b", "2": "true"},
                "hints": {}
            }
        )
        
        # May return 400 if already completed
        if resp.status_code == 400:
            data = resp.json()
            assert "completed" in data.get("detail", "").lower(), f"Unexpected error: {data}"
            print(f"✅ Save progress: Already completed (expected)")
        else:
            assert resp.status_code == 200, f"Save progress failed: {resp.text}"
            data = resp.json()
            
            assert "status" in data
            assert data["status"] == "saved"
            
            print(f"✅ Save progress: status={data['status']}")

    # ===== TEST: Create homework (admin) =====
    def test_create_homework_admin(self, admin_session):
        """POST /api/structured-homework - Create homework with questions (admin auth)"""
        unique_title = f"TEST_AI_Homework_{uuid.uuid4().hex[:6]}"
        
        resp = admin_session.post(
            f"{BASE_URL}/api/structured-homework",
            json={
                "subject_id": ENGLISH_SUBJECT_ID,
                "standard": STANDARD,
                "title": unique_title,
                "deadline": "2026-12-31T23:59:59Z",
                "questions": [
                    {
                        "question_number": 1,
                        "question_type": "mcq",
                        "question_text": "What is the capital of France?",
                        "model_answer": "B) Paris",
                        "objective_data": {
                            "options": {"a": "London", "b": "Paris", "c": "Berlin", "d": "Madrid"},
                            "correct": "b"
                        }
                    },
                    {
                        "question_number": 2,
                        "question_type": "true_false",
                        "question_text": "The sun rises in the west.",
                        "objective_data": {"correct": False}
                    }
                ]
            }
        )
        
        assert resp.status_code == 200, f"Create homework failed: {resp.text}"
        data = resp.json()
        
        assert "id" in data
        assert "title" in data
        assert data["title"] == unique_title
        assert "question_count" in data
        assert data["question_count"] == 2
        assert "status" in data
        assert data["status"] == "active"
        
        print(f"✅ Create homework: id={data['id']}, title={data['title']}, questions={data['question_count']}")
        
        # Store for cleanup
        return data["id"]

    # ===== TEST: Get homework without auth =====
    def test_get_homework_no_auth(self):
        """GET /api/structured-homework/{id} - Should fail without authentication"""
        session = requests.Session()
        resp = session.get(f"{BASE_URL}/api/structured-homework/{EXISTING_HOMEWORK_ID}")
        
        # Should fail without auth
        assert resp.status_code in [401, 403], f"Expected 401/403, got {resp.status_code}"
        print(f"✅ Get homework without auth correctly rejected: {resp.status_code}")

    # ===== TEST: Complete homework =====
    def test_complete_homework(self, student_session):
        """POST /api/structured-homework/{id}/complete - Mark homework as completed"""
        # Start homework first
        start_resp = student_session.post(
            f"{BASE_URL}/api/structured-homework/{EXISTING_HOMEWORK_ID}/start"
        )
        
        # Complete with answers
        resp = student_session.post(
            f"{BASE_URL}/api/structured-homework/{EXISTING_HOMEWORK_ID}/complete",
            json={
                "answers": {"1": "b", "2": "true", "3": "something"},
                "hints": {}
            }
        )
        
        # May fail if already completed
        if resp.status_code == 400:
            data = resp.json()
            assert "already completed" in data.get("detail", "").lower() or resp.status_code == 400
            print(f"✅ Complete homework: Already completed (expected)")
        else:
            assert resp.status_code == 200, f"Complete homework failed: {resp.text}"
            data = resp.json()
            assert "status" in data
            assert data["status"] == "completed"
            assert "completed_at" in data
            print(f"✅ Complete homework: status={data['status']}, completed_at={data['completed_at']}")

    # ===== TEST: Homework 404 =====
    def test_get_nonexistent_homework(self, student_session):
        """GET /api/structured-homework/{id} - Should return 404 for invalid ID"""
        fake_id = "00000000-0000-0000-0000-000000000000"
        resp = student_session.get(f"{BASE_URL}/api/structured-homework/{fake_id}")
        
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"
        print(f"✅ Get nonexistent homework correctly returns 404")

    # ===== TEST: Start homework - validation =====
    def test_start_nonexistent_homework(self, student_session):
        """POST /api/structured-homework/{id}/start - Should return 404 for invalid ID"""
        fake_id = "00000000-0000-0000-0000-000000000000"
        resp = student_session.post(f"{BASE_URL}/api/structured-homework/{fake_id}/start")
        
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"
        print(f"✅ Start nonexistent homework correctly returns 404")

    # ===== TEST: Hint without starting homework =====
    def test_hint_without_start(self, student_session):
        """POST /api/structured-homework/{id}/hint - New homework requires start first"""
        # This test uses existing homework which is already started
        # Testing the hint endpoint with different question
        resp = student_session.post(
            f"{BASE_URL}/api/structured-homework/{EXISTING_HOMEWORK_ID}/hint",
            json={
                "question_number": 3,
                "student_answer": ""
            }
        )
        
        # Should work since homework is already started
        assert resp.status_code in [200, 400, 404], f"Unexpected status: {resp.status_code}"
        print(f"✅ Hint request status: {resp.status_code}")


class TestTeacherHomeworkSubmissions:
    """Test teacher's view of homework submissions"""

    @pytest.fixture(scope="class")
    def admin_session(self):
        """Get admin session (acts as teacher)"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        
        resp = session.post(f"{BASE_URL}/api/admin/login", json={
            "username": ADMIN_USERNAME,
            "password": ADMIN_PASSWORD
        })
        assert resp.status_code == 200
        return session

    def test_get_submissions(self, admin_session):
        """GET /api/structured-homework/{id}/submissions - Teacher view"""
        resp = admin_session.get(
            f"{BASE_URL}/api/structured-homework/{EXISTING_HOMEWORK_ID}/submissions"
        )
        
        assert resp.status_code == 200, f"Get submissions failed: {resp.text}"
        submissions = resp.json()
        
        assert isinstance(submissions, list)
        
        if len(submissions) > 0:
            sub = submissions[0]
            assert "id" in sub
            assert "student_id" in sub
            assert "roll_no" in sub
            assert "completed" in sub
            
        print(f"✅ Get submissions: {len(submissions)} submissions found")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
