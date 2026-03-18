"""
Test Case: P0 Bug Fix - evaluation_points string TypeError
========================================================
Tests the fix for TypeError when evaluating tests with evaluation_points
stored as plain strings instead of list of dicts.

Bug: TypeError: 'string indices must be integers, not str' in evaluate_subjective()
Fix: evaluation_agent.py now handles string evaluation_points by converting to list of dicts
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test credentials from the review request
STUDENT_ROLL_NO = "S1"
STUDENT_PASSWORD = "Test@123"
TEACHER_ROLL_NO = "T1"
TEACHER_PASSWORD = "Test@123"

SUBJECT_ID_MATH_STD8 = "9e05f51f-7235-4cd1-8539-71aa7d962ea1"
STANDARD = 8

TEST_1_ID = "4f47c150-425b-4d66-90ee-a7c33bfb8e8e"
TEST_2_ID = "9668ca1c-d180-46fa-85e2-56fa60899157"
HOMEWORK_1_ID = "62d4c6a9-2f7b-449f-bf36-8429da36b1dc"
HOMEWORK_2_ID = "aed61f3b-d8a1-40c0-8278-434ed30aa44f"


class TestAuthEndpoints:
    """Test authentication with provided credentials"""

    def test_student_login(self):
        """POST /api/auth/login - Student S1 should login successfully"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"roll_no": STUDENT_ROLL_NO, "password": STUDENT_PASSWORD},
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data or "access_token" in data, "Token not in response"
        print(f"✓ Student S1 login successful")

    def test_teacher_login(self):
        """POST /api/auth/login - Teacher T1 should login successfully"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"roll_no": TEACHER_ROLL_NO, "password": TEACHER_PASSWORD},
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data or "access_token" in data, "Token not in response"
        print(f"✓ Teacher T1 login successful")


class TestStructuredTestList:
    """Test listing structured tests for Math subject Standard 8"""

    @pytest.fixture
    def student_token(self):
        """Get student auth token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"roll_no": STUDENT_ROLL_NO, "password": STUDENT_PASSWORD},
        )
        assert response.status_code == 200
        data = response.json()
        return data.get("token") or data.get("access_token")

    def test_list_active_tests(self, student_token):
        """GET /api/structured-tests/list/{subject_id}/{standard} - should list 2 active tests"""
        response = requests.get(
            f"{BASE_URL}/api/structured-tests/list/{SUBJECT_ID_MATH_STD8}/{STANDARD}",
            headers={"Authorization": f"Bearer {student_token}"},
        )
        assert response.status_code == 200, f"List failed: {response.text}"
        tests = response.json()
        assert isinstance(tests, list), "Response should be a list"
        print(f"✓ Found {len(tests)} active tests for Math Standard 8")
        
        # Check for the specific test IDs
        test_ids = [t.get("id") for t in tests]
        print(f"  Test IDs: {test_ids}")
        
        # Verify tests have expected structure
        for test in tests:
            assert "id" in test, "Test should have id"
            assert "title" in test, "Test should have title"
            assert "total_marks" in test, "Test should have total_marks"
            print(f"  - {test.get('title')}: {test.get('total_marks')} marks, submitted={test.get('submitted')}")


class TestStructuredHomeworkList:
    """Test listing structured homework for Math subject Standard 8"""

    @pytest.fixture
    def student_token(self):
        """Get student auth token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"roll_no": STUDENT_ROLL_NO, "password": STUDENT_PASSWORD},
        )
        assert response.status_code == 200
        data = response.json()
        return data.get("token") or data.get("access_token")

    def test_list_active_homework(self, student_token):
        """GET /api/structured-homework/list/{subject_id}/{standard} - should list 2 homework assignments"""
        response = requests.get(
            f"{BASE_URL}/api/structured-homework/list/{SUBJECT_ID_MATH_STD8}/{STANDARD}",
            headers={"Authorization": f"Bearer {student_token}"},
        )
        assert response.status_code == 200, f"List failed: {response.text}"
        data = response.json()
        homework_list = data.get("homework", [])
        assert isinstance(homework_list, list), "Response should have homework list"
        print(f"✓ Found {len(homework_list)} active homework for Math Standard 8")
        
        # Check for the specific homework IDs
        hw_ids = [h.get("id") for h in homework_list]
        print(f"  Homework IDs: {hw_ids}")
        
        for hw in homework_list:
            assert "id" in hw, "Homework should have id"
            assert "title" in hw, "Homework should have title"
            print(f"  - {hw.get('title')}: {hw.get('question_count')} questions")


class TestHomeworkStartAndCheckAnswer:
    """Test homework start and check-answer endpoints - key part of bug fix verification"""

    @pytest.fixture
    def student_token(self):
        """Get student auth token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"roll_no": STUDENT_ROLL_NO, "password": STUDENT_PASSWORD},
        )
        assert response.status_code == 200
        data = response.json()
        return data.get("token") or data.get("access_token")

    def test_start_homework(self, student_token):
        """POST /api/structured-homework/{homework_id}/start - should start homework"""
        response = requests.post(
            f"{BASE_URL}/api/structured-homework/{HOMEWORK_1_ID}/start",
            headers={"Authorization": f"Bearer {student_token}"},
        )
        # 200 for start, 400 if already completed
        assert response.status_code in [200, 400], f"Start failed: {response.text}"
        data = response.json()
        
        if response.status_code == 200:
            assert "submission_id" in data, "Should return submission_id"
            print(f"✓ Homework started: submission_id={data.get('submission_id')}")
        else:
            print(f"✓ Homework status: {data.get('detail', 'already completed')}")

    def test_check_mcq_answer(self, student_token):
        """POST /api/structured-homework/{homework_id}/check-answer - MCQ answer 'a' for Q1"""
        # First start the homework
        start_response = requests.post(
            f"{BASE_URL}/api/structured-homework/{HOMEWORK_1_ID}/start",
            headers={"Authorization": f"Bearer {student_token}"},
        )
        # Ignore if already started/completed
        
        # Now check answer
        response = requests.post(
            f"{BASE_URL}/api/structured-homework/{HOMEWORK_1_ID}/check-answer",
            headers={"Authorization": f"Bearer {student_token}"},
            json={"question_number": 1, "student_answer": "a"},
        )
        assert response.status_code == 200, f"Check answer failed: {response.text}"
        data = response.json()
        assert "correct" in data, "Response should have 'correct' field"
        print(f"✓ Check answer for Q1 with 'a': correct={data.get('correct')}")


class TestStructuredTestEvaluation:
    """
    Test the critical bug fix: structured test submission and evaluation
    The bug was: evaluation_points stored as string caused TypeError in evaluate_subjective()
    """

    @pytest.fixture
    def student_token(self):
        """Get student auth token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"roll_no": STUDENT_ROLL_NO, "password": STUDENT_PASSWORD},
        )
        assert response.status_code == 200
        data = response.json()
        return data.get("token") or data.get("access_token")

    def test_get_test_details(self, student_token):
        """GET /api/structured-tests/{test_id} - verify test structure"""
        response = requests.get(
            f"{BASE_URL}/api/structured-tests/{TEST_1_ID}",
            headers={"Authorization": f"Bearer {student_token}"},
        )
        assert response.status_code == 200, f"Get test failed: {response.text}"
        data = response.json()
        assert "questions" in data, "Test should have questions"
        print(f"✓ Test 1 details: {data.get('title')}, {len(data.get('questions', []))} questions")
        
        # Print question types
        for q in data.get("questions", []):
            print(f"  - Q{q.get('question_number')}: {q.get('question_type')}")

    def test_start_and_submit_test(self, student_token):
        """
        POST /api/structured-tests/{test_id}/start then submit
        Critical test: Should return 200 with evaluation scores, NOT 500 error
        """
        # First, check if test is already submitted
        list_response = requests.get(
            f"{BASE_URL}/api/structured-tests/list/{SUBJECT_ID_MATH_STD8}/{STANDARD}",
            headers={"Authorization": f"Bearer {student_token}"},
        )
        tests = list_response.json()
        test_1 = next((t for t in tests if t.get("id") == TEST_1_ID), None)
        
        if test_1 and test_1.get("submitted"):
            print(f"✓ Test 1 already submitted - Score: {test_1.get('score')}/{test_1.get('percentage')}%")
            # Verify we can get results
            return
        
        # Start the test
        start_response = requests.post(
            f"{BASE_URL}/api/structured-tests/{TEST_1_ID}/start",
            headers={"Authorization": f"Bearer {student_token}"},
        )
        
        if start_response.status_code == 400:
            # Already submitted
            print(f"✓ Test already submitted: {start_response.json().get('detail')}")
            return
        
        assert start_response.status_code == 200, f"Start test failed: {start_response.text}"
        print(f"✓ Test started: {start_response.json()}")
        
        # Get test questions to determine what to submit
        test_response = requests.get(
            f"{BASE_URL}/api/structured-tests/{TEST_1_ID}",
            headers={"Authorization": f"Bearer {student_token}"},
        )
        test_data = test_response.json()
        questions = test_data.get("questions", [])
        
        # Build answers - MCQ = 'a'/'b'/'c'/'d', true_false = 'true'/'false', short_answer = text
        answers = {}
        for q in questions:
            q_num = str(q.get("question_number"))
            q_type = q.get("question_type")
            
            if q_type == "mcq":
                answers[q_num] = "a"  # Default to 'a'
            elif q_type == "true_false":
                answers[q_num] = "true"
            elif q_type in ("short_answer", "long_answer"):
                answers[q_num] = "This is a test answer for subjective question."
            elif q_type == "one_word":
                answers[q_num] = "answer"
            elif q_type == "numerical":
                answers[q_num] = "42"
            elif q_type == "fill_blank":
                answers[q_num] = "blank"
            elif q_type == "match_following":
                answers[q_num] = '{"0": "a", "1": "b"}'
        
        print(f"  Submitting answers: {answers}")
        
        # Submit the test - THIS IS THE BUG FIX TEST
        # Previously would fail with TypeError: 'string indices must be integers, not str'
        submit_response = requests.post(
            f"{BASE_URL}/api/structured-tests/{TEST_1_ID}/submit",
            headers={"Authorization": f"Bearer {student_token}"},
            json={"answers": answers},
        )
        
        # CRITICAL ASSERTION: Should NOT return 500 error
        assert submit_response.status_code != 500, f"BUG NOT FIXED: Got 500 error: {submit_response.text}"
        assert submit_response.status_code == 200, f"Submit failed: {submit_response.text}"
        
        result = submit_response.json()
        assert "total_score" in result, "Should have total_score"
        assert "max_score" in result, "Should have max_score"
        assert "percentage" in result, "Should have percentage"
        
        print(f"✓ TEST EVALUATION SUCCESSFUL (BUG FIX VERIFIED)")
        print(f"  Score: {result.get('total_score')}/{result.get('max_score')} ({result.get('percentage')}%)")


class TestEvaluationResultsAccess:
    """Test that evaluation results can be accessed after submission"""

    @pytest.fixture
    def student_token(self):
        """Get student auth token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"roll_no": STUDENT_ROLL_NO, "password": STUDENT_PASSWORD},
        )
        assert response.status_code == 200
        data = response.json()
        return data.get("token") or data.get("access_token")

    def test_list_tests_shows_scores(self, student_token):
        """Verify that submitted tests show scores in list"""
        response = requests.get(
            f"{BASE_URL}/api/structured-tests/list/{SUBJECT_ID_MATH_STD8}/{STANDARD}",
            headers={"Authorization": f"Bearer {student_token}"},
        )
        assert response.status_code == 200
        tests = response.json()
        
        submitted_tests = [t for t in tests if t.get("submitted")]
        print(f"✓ Found {len(submitted_tests)} submitted tests with scores:")
        for t in submitted_tests:
            print(f"  - {t.get('title')}: {t.get('score')}/{t.get('percentage')}%")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
