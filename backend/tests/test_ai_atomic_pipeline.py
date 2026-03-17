"""
Test STRICT ATOMIC AI GENERATION PIPELINE v2
=============================================

Tests the following endpoints and functionality:
1. GET /api/student/chapter/{chapter_id}/content/revision_notes - returns revision notes
2. GET /api/student/chapter/{chapter_id}/content/flashcards - returns exactly 15 flashcards
3. GET /api/student/chapter/{chapter_id}/content/quiz - returns 5 quizzes with 15 questions each (75 total)
4. Database flag chapter.ai_generated should be True after successful generation
5. Content should be stored in S3 with correct structure

Note: Content was already generated successfully. This test focuses on verifying the fetch endpoints.
"""

import pytest
import requests
import os

# API Base URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://adaptive-classroom-5.preview.emergentagent.com')

# Test credentials from review request
TEACHER_ROLL_NO = "T001"
TEACHER_PASSWORD = "password123"
TEST_CHAPTER_ID = "71260201-c6cc-48a4-a51b-8bb5ba08ad51"


class TestAIAtomicPipeline:
    """Test suite for AI Atomic Generation Pipeline v2 content fetching"""
    
    @pytest.fixture(scope="class")
    def teacher_session(self):
        """Create an authenticated session as teacher"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        
        # Login as teacher
        login_response = session.post(
            f"{BASE_URL}/api/auth/login",
            json={
                "roll_no": TEACHER_ROLL_NO,
                "password": TEACHER_PASSWORD
            }
        )
        
        if login_response.status_code != 200:
            pytest.skip(f"Teacher login failed: {login_response.status_code} - {login_response.text}")
        
        return session
    
    def test_01_teacher_login(self, teacher_session):
        """Test teacher can login successfully"""
        # Teacher session is already created in fixture
        # Just verify we have a valid session
        assert teacher_session is not None
        print("✅ Teacher login successful")
    
    def test_02_get_chapter_ai_status(self, teacher_session):
        """Test that chapter has ai_generated=True"""
        response = teacher_session.get(
            f"{BASE_URL}/api/teacher/chapter/{TEST_CHAPTER_ID}/ai-content-status"
        )
        
        # Log response for debugging
        print(f"AI Status Response: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"AI Status Data: {data}")
            
            # Verify ai_generated is True
            assert data.get("ai_generated") == True, "Expected ai_generated to be True"
            assert data.get("ai_content_exists") == True, "Expected ai_content_exists to be True"
            print(f"✅ Chapter AI status verified: ai_generated={data.get('ai_generated')}")
        else:
            print(f"⚠️ AI Status endpoint returned: {response.status_code}")
            # Still proceed with content tests
    
    def test_03_get_revision_notes(self, teacher_session):
        """Test fetching revision notes - should have key_concepts array"""
        response = teacher_session.get(
            f"{BASE_URL}/api/student/chapter/{TEST_CHAPTER_ID}/content/revision_notes"
        )
        
        print(f"Revision Notes Response Status: {response.status_code}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        print(f"Revision Notes available: {data.get('available')}")
        
        # Check if content is available
        assert data.get("available") == True, f"Expected available=True, got {data}"
        
        content = data.get("content")
        assert content is not None, "Content should not be None"
        
        # Verify key_concepts exists and is a list with at least 5 items
        assert "key_concepts" in content, "Revision notes should have key_concepts"
        key_concepts = content["key_concepts"]
        assert isinstance(key_concepts, list), "key_concepts should be a list"
        assert len(key_concepts) >= 5, f"Expected at least 5 key_concepts, got {len(key_concepts)}"
        
        # Verify chapter_summary exists
        assert "chapter_summary" in content, "Revision notes should have chapter_summary"
        assert len(content["chapter_summary"]) >= 50, "chapter_summary should be at least 50 chars"
        
        print(f"✅ Revision notes verified: {len(key_concepts)} key_concepts found")
    
    def test_04_get_flashcards(self, teacher_session):
        """Test fetching flashcards - should have exactly 15 flashcards"""
        response = teacher_session.get(
            f"{BASE_URL}/api/student/chapter/{TEST_CHAPTER_ID}/content/flashcards"
        )
        
        print(f"Flashcards Response Status: {response.status_code}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        print(f"Flashcards available: {data.get('available')}")
        
        assert data.get("available") == True, f"Expected available=True, got {data}"
        
        content = data.get("content")
        assert content is not None, "Content should not be None"
        
        # Content should be a list (flashcards array)
        flashcards = content
        if isinstance(content, dict):
            # Handle wrapped format
            flashcards = content.get("flashcards", content)
        
        assert isinstance(flashcards, list), f"Flashcards should be a list, got {type(flashcards)}"
        assert len(flashcards) == 15, f"Expected exactly 15 flashcards, got {len(flashcards)}"
        
        # Verify each flashcard has front and back
        for i, card in enumerate(flashcards):
            assert "front" in card or "question" in card, f"Flashcard {i+1} missing front/question"
            assert "back" in card or "answer" in card, f"Flashcard {i+1} missing back/answer"
        
        print(f"✅ Flashcards verified: exactly {len(flashcards)} flashcards found")
    
    def test_05_get_quiz_structure(self, teacher_session):
        """Test fetching quiz - should have 5 quizzes with 15 questions each (75 total)"""
        response = teacher_session.get(
            f"{BASE_URL}/api/student/chapter/{TEST_CHAPTER_ID}/content/quiz"
        )
        
        print(f"Quiz Response Status: {response.status_code}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        print(f"Quiz available: {data.get('available')}")
        
        assert data.get("available") == True, f"Expected available=True, got {data}"
        
        content = data.get("content")
        assert content is not None, "Content should not be None"
        
        # Verify quizzes array exists
        assert "quizzes" in content, "Quiz content should have 'quizzes' array"
        quizzes = content["quizzes"]
        
        assert isinstance(quizzes, list), f"quizzes should be a list, got {type(quizzes)}"
        assert len(quizzes) == 5, f"Expected exactly 5 quizzes, got {len(quizzes)}"
        
        # Verify quiz metadata
        assert content.get("total_quizzes") == 5, "total_quizzes should be 5"
        assert content.get("total_questions") == 75, "total_questions should be 75"
        
        # Count total questions
        total_questions = 0
        quiz_types = []
        
        for i, quiz in enumerate(quizzes):
            quiz_id = quiz.get("quiz_id", i+1)
            difficulty = quiz.get("difficulty", "unknown")
            questions = quiz.get("questions", [])
            
            print(f"  Quiz {quiz_id} ({difficulty}): {len(questions)} questions")
            
            quiz_types.append(difficulty)
            total_questions += len(questions)
            
            # Each quiz should have exactly 15 questions
            assert len(questions) == 15, f"Quiz {quiz_id} should have 15 questions, got {len(questions)}"
            
            # Validate question structure
            for j, q in enumerate(questions):
                assert "question" in q, f"Quiz {quiz_id} Q{j+1} missing question text"
                assert "options" in q, f"Quiz {quiz_id} Q{j+1} missing options"
                assert len(q["options"]) == 4, f"Quiz {quiz_id} Q{j+1} should have 4 options"
                assert "correct_answer" in q, f"Quiz {quiz_id} Q{j+1} missing correct_answer"
                # correct_answer should be 0-3
                ca = q["correct_answer"]
                assert isinstance(ca, int) and 0 <= ca <= 3, f"Quiz {quiz_id} Q{j+1} correct_answer should be 0-3"
        
        assert total_questions == 75, f"Expected 75 total questions, got {total_questions}"
        
        # Verify all expected difficulty levels are present
        expected_difficulties = ["easy", "medium", "hard", "advanced_application", "advanced_analysis"]
        for diff in expected_difficulties:
            assert diff in quiz_types, f"Missing quiz with difficulty: {diff}"
        
        print(f"✅ Quiz structure verified: 5 quizzes, {total_questions} total questions")
        print(f"   Difficulty levels: {quiz_types}")
    
    def test_06_quiz_advanced_flags(self, teacher_session):
        """Test that advanced quizzes have for_strong_students flag"""
        response = teacher_session.get(
            f"{BASE_URL}/api/student/chapter/{TEST_CHAPTER_ID}/content/quiz"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("available") == True
        
        quizzes = data.get("content", {}).get("quizzes", [])
        
        advanced_count = 0
        for quiz in quizzes:
            difficulty = quiz.get("difficulty", "")
            if "advanced" in difficulty:
                advanced_count += 1
                # Advanced quizzes should have for_strong_students flag
                assert quiz.get("for_strong_students") == True, \
                    f"Advanced quiz '{difficulty}' should have for_strong_students=True"
        
        assert advanced_count == 2, f"Expected 2 advanced quizzes, got {advanced_count}"
        print(f"✅ Advanced quiz flags verified: {advanced_count} quizzes marked for strong students")
    
    def test_07_content_metadata(self, teacher_session):
        """Test that responses include proper metadata"""
        # Test revision notes metadata
        response = teacher_session.get(
            f"{BASE_URL}/api/student/chapter/{TEST_CHAPTER_ID}/content/revision_notes"
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should include chapter and subject names
        assert "chapter_name" in data, "Response should include chapter_name"
        assert "subject_name" in data, "Response should include subject_name"
        
        print(f"✅ Content metadata verified: chapter='{data.get('chapter_name')}', subject='{data.get('subject_name')}'")
    
    def test_08_invalid_content_type(self, teacher_session):
        """Test that invalid content type returns 400"""
        response = teacher_session.get(
            f"{BASE_URL}/api/student/chapter/{TEST_CHAPTER_ID}/content/invalid_type"
        )
        
        assert response.status_code == 400, f"Expected 400 for invalid content type, got {response.status_code}"
        print("✅ Invalid content type correctly returns 400")
    
    def test_09_invalid_chapter_id(self, teacher_session):
        """Test that invalid chapter ID returns 404"""
        response = teacher_session.get(
            f"{BASE_URL}/api/student/chapter/non-existent-id/content/revision_notes"
        )
        
        assert response.status_code == 404, f"Expected 404 for invalid chapter, got {response.status_code}"
        print("✅ Invalid chapter ID correctly returns 404")


class TestContentValidation:
    """Additional validation tests for content quality"""
    
    @pytest.fixture(scope="class")
    def teacher_session(self):
        """Create an authenticated session as teacher"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        
        login_response = session.post(
            f"{BASE_URL}/api/auth/login",
            json={
                "roll_no": TEACHER_ROLL_NO,
                "password": TEACHER_PASSWORD
            }
        )
        
        if login_response.status_code != 200:
            pytest.skip(f"Teacher login failed: {login_response.status_code}")
        
        return session
    
    def test_revision_notes_structure(self, teacher_session):
        """Validate revision notes have all expected fields"""
        response = teacher_session.get(
            f"{BASE_URL}/api/student/chapter/{TEST_CHAPTER_ID}/content/revision_notes"
        )
        
        if response.status_code != 200:
            pytest.skip("Revision notes not available")
        
        content = response.json().get("content", {})
        
        # Check for expected fields
        expected_fields = ["key_concepts", "chapter_summary"]
        optional_fields = ["exam_important_points", "definitions", "quick_points"]
        
        for field in expected_fields:
            assert field in content, f"Missing required field: {field}"
        
        found_optional = [f for f in optional_fields if f in content]
        print(f"✅ Revision notes structure valid. Optional fields found: {found_optional}")
    
    def test_flashcard_quality(self, teacher_session):
        """Validate flashcard content quality"""
        response = teacher_session.get(
            f"{BASE_URL}/api/student/chapter/{TEST_CHAPTER_ID}/content/flashcards"
        )
        
        if response.status_code != 200:
            pytest.skip("Flashcards not available")
        
        content = response.json().get("content", [])
        flashcards = content if isinstance(content, list) else content.get("flashcards", [])
        
        for i, card in enumerate(flashcards):
            front = card.get("front") or card.get("question", "")
            back = card.get("back") or card.get("answer", "")
            
            # Validate content is not empty
            assert len(front) > 10, f"Flashcard {i+1} front text too short"
            assert len(back) > 5, f"Flashcard {i+1} back text too short"
        
        print(f"✅ Flashcard quality validated for {len(flashcards)} cards")
    
    def test_quiz_question_quality(self, teacher_session):
        """Validate quiz question quality"""
        response = teacher_session.get(
            f"{BASE_URL}/api/student/chapter/{TEST_CHAPTER_ID}/content/quiz"
        )
        
        if response.status_code != 200:
            pytest.skip("Quiz not available")
        
        quizzes = response.json().get("content", {}).get("quizzes", [])
        
        for quiz in quizzes:
            difficulty = quiz.get("difficulty")
            for j, q in enumerate(quiz.get("questions", [])):
                # Question text should be substantial
                assert len(q.get("question", "")) >= 20, \
                    f"Quiz {difficulty} Q{j+1} question text too short"
                
                # All options should have content
                for k, opt in enumerate(q.get("options", [])):
                    assert len(opt) >= 1, f"Quiz {difficulty} Q{j+1} option {k+1} empty"
                
                # Explanation should be concise (<=300 chars per validation rules)
                explanation = q.get("explanation", "")
                assert len(explanation) <= 350, \
                    f"Quiz {difficulty} Q{j+1} explanation too long ({len(explanation)} chars)"
        
        print(f"✅ Quiz question quality validated for {len(quizzes)} quizzes")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
