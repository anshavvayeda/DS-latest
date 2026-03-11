import React, { useState, useEffect } from 'react';
import axios from 'axios';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import './StudentContentViewer.css';

const API = process.env.REACT_APP_BACKEND_URL ? `${process.env.REACT_APP_BACKEND_URL}/api` : '/api';

/**
 * StudentContentViewer Component - Phase 4.1 Read-Only Content
 * 
 * CRITICAL RULES:
 * 1. NEVER triggers AI generation
 * 2. Only displays existing content
 * 3. Shows "not available" message if content doesn't exist
 */

// Utility to clean AI content
const cleanAIContent = (text) => {
  if (!text) return '';
  let cleaned = String(text);
  cleaned = cleaned.replace(/\*\*\*/g, '');
  cleaned = cleaned.replace(/\*\*/g, '');
  cleaned = cleaned.replace(/^#{1,6}\s*/gm, '');
  cleaned = cleaned.trim();
  return cleaned;
};

// Formatted content component
const FormattedContent = ({ content, className = '' }) => {
  if (!content) return null;
  const cleaned = cleanAIContent(content);
  
  return (
    <div className={`formatted-content ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkMath]}
        rehypePlugins={[rehypeKatex]}
      >
        {cleaned}
      </ReactMarkdown>
    </div>
  );
};

function StudentContentViewer({ chapter, subject, onBack }) {
  const [activeTab, setActiveTab] = useState('notes');
  const [content, setContent] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  
  // Flashcard state
  const [fcIndex, setFcIndex] = useState(0);
  const [fcFlipped, setFcFlipped] = useState(false);
  
  // Quiz state
  const [selectedQuiz, setSelectedQuiz] = useState(null);
  const [quizQuestion, setQuizQuestion] = useState(0);
  const [selectedAnswer, setSelectedAnswer] = useState(null);
  const [showResult, setShowResult] = useState(false);
  const [score, setScore] = useState(0);
  const [quizComplete, setQuizComplete] = useState(false);

  useEffect(() => {
    if (chapter) {
      loadContent(activeTab);
    }
  }, [chapter, activeTab]);

  const loadContent = async (contentType) => {
    // Video tab doesn't need to load content from API
    // Video URL is already in chapter object
    if (contentType === 'video') {
      setLoading(false);
      return;
    }
    
    setLoading(true);
    setError(null);
    setContent(null);
    
    try {
      // Use the READ-ONLY student endpoint
      const response = await axios.get(
        `${API}/student/chapter/${chapter.id}/content/${contentType === 'notes' ? 'revision_notes' : contentType}`,
        { withCredentials: true }
      );
      
      if (response.data.available) {
        setContent(response.data.content);
      } else {
        setError(response.data.message || 'Content not available yet. Please check back later.');
      }
    } catch (err) {
      console.error('Error loading content:', err);
      setError('Content not available yet. Please check back later.');
    } finally {
      setLoading(false);
    }
  };

  // Reset states when switching tabs
  const handleTabChange = (tab) => {
    setActiveTab(tab);
    setFcIndex(0);
    setFcFlipped(false);
    setSelectedQuiz(null);
    setQuizQuestion(0);
    setSelectedAnswer(null);
    setShowResult(false);
    setScore(0);
    setQuizComplete(false);
  };

  // Render content not available message
  const renderNotAvailable = () => (
    <div className="content-not-available" data-testid="content-not-available">
      <div className="not-available-icon">📚</div>
      <h3>Content Not Available Yet</h3>
      <p>{error || 'Please check back later.'}</p>
      <p className="hint">Your teacher needs to upload and generate content for this chapter.</p>
    </div>
  );

  // Render Video
  const renderVideo = () => {
    // Check if chapter has video_url
    if (!chapter?.video_url) {
      return (
        <div className="not-available" data-testid="video-not-available">
          <div className="na-icon">📹</div>
          <p>No video available for this chapter yet.</p>
          <p className="na-subtitle">Your teacher will add a video soon!</p>
        </div>
      );
    }

    // Helper to check if URL is valid video URL
    const isValidVideoUrl = (url) => {
      if (!url) return false;
      return (
        url.includes('youtube.com') ||
        url.includes('youtu.be') ||
        url.includes('notebooklm.google.com') ||
        url.includes('vimeo.com') ||
        url.includes('drive.google.com')
      );
    };

    if (!isValidVideoUrl(chapter.video_url)) {
      return (
        <div className="not-available">
          <div className="na-icon">⚠️</div>
          <p>Invalid video URL</p>
          <p className="na-subtitle">Please contact your teacher.</p>
        </div>
      );
    }

    return (
      <div className="video-viewer" data-testid="video-viewer">
        <div className="video-container">
          <iframe
            src={chapter.video_url}
            width="100%"
            height="600"
            frameBorder="0"
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
            allowFullScreen
            title={`${chapter.name} - Video`}
          />
        </div>
        <div className="video-info">
          <h3>📹 {chapter.name}</h3>
          <p>Watch this video to learn about {chapter.name}</p>
        </div>
      </div>
    );
  };

  // Render Revision Notes
  const renderNotes = () => {
    if (!content) return renderNotAvailable();
    
    return (
      <div className="revision-notes-viewer" data-testid="revision-notes-viewer">
        {/* Chapter Summary */}
        {content.chapter_summary && (
          <div className="notes-section summary-section">
            <h3>📋 Chapter Summary</h3>
            <FormattedContent content={content.chapter_summary} />
          </div>
        )}
        
        {/* Key Concepts */}
        {content.key_concepts && content.key_concepts.length > 0 && (
          <div className="notes-section">
            <h3>🎯 Key Concepts</h3>
            <div className="concepts-grid">
              {content.key_concepts.map((concept, idx) => (
                <div key={idx} className="concept-card">
                  <h4>{cleanAIContent(concept.title)}</h4>
                  <FormattedContent content={concept.explanation} />
                  {concept.example && (
                    <p className="concept-example">💡 Example: {cleanAIContent(concept.example)}</p>
                  )}
                  {concept.exam_tip && (
                    <p className="exam-tip">📝 Exam tip: {cleanAIContent(concept.exam_tip)}</p>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
        
        {/* Exam Important Points */}
        {content.exam_important_points && content.exam_important_points.length > 0 && (
          <div className="notes-section">
            <h3>⭐ Exam Important Points</h3>
            <div className="important-points">
              {content.exam_important_points.map((point, idx) => (
                <div key={idx} className="important-point">
                  <span className="point-type">{point.type || 'Fact'}</span>
                  <FormattedContent content={point.point} />
                  {point.memory_trick && (
                    <p className="memory-trick">🧠 Remember: {cleanAIContent(point.memory_trick)}</p>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
        
        {/* Definitions */}
        {content.definitions_to_memorize && content.definitions_to_memorize.length > 0 && (
          <div className="notes-section">
            <h3>📖 Definitions to Memorize</h3>
            <div className="definitions-list">
              {content.definitions_to_memorize.map((def, idx) => (
                <div key={idx} className="definition-item">
                  <span className="term">{cleanAIContent(def.term)}</span>
                  <span className="meaning">{cleanAIContent(def.meaning || def.definition)}</span>
                </div>
              ))}
            </div>
          </div>
        )}
        
        {/* Quick Revision Points */}
        {content.quick_revision_points && content.quick_revision_points.length > 0 && (
          <div className="notes-section">
            <h3>🚀 Quick Revision Points</h3>
            <div className="revision-points">
              {content.quick_revision_points.map((point, idx) => (
                <div key={idx} className="revision-point">
                  <span className="point-num">{idx + 1}</span>
                  <FormattedContent content={typeof point === 'string' ? point : point.point} />
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  };

  // Render Flashcards
  const renderFlashcards = () => {
    if (!content || !Array.isArray(content) || content.length === 0) {
      return renderNotAvailable();
    }
    
    const card = content[fcIndex];
    
    return (
      <div className="flashcards-viewer" data-testid="flashcards-viewer">
        <div className="fc-progress">
          <div className="fc-progress-bar">
            <div 
              className="fc-progress-fill"
              style={{ width: `${((fcIndex + 1) / content.length) * 100}%` }}
            />
          </div>
          <span className="fc-progress-text">{fcIndex + 1} / {content.length}</span>
        </div>
        
        <div 
          className={`flashcard ${fcFlipped ? 'flipped' : ''}`}
          onClick={() => setFcFlipped(!fcFlipped)}
          data-testid="flashcard"
        >
          <div className="flashcard-inner">
            <div className="flashcard-front">
              <div className="card-label">Question</div>
              <FormattedContent content={card?.front} />
              <div className="flip-hint">Click to flip</div>
            </div>
            <div className="flashcard-back">
              <div className="card-label">Answer</div>
              <FormattedContent content={card?.back} />
              {card?.hint && (
                <div className="card-hint">💡 {cleanAIContent(card.hint)}</div>
              )}
            </div>
          </div>
        </div>
        
        <div className="fc-navigation">
          <button
            onClick={() => { setFcFlipped(false); setFcIndex(Math.max(0, fcIndex - 1)); }}
            disabled={fcIndex === 0}
            className="fc-nav-btn"
          >
            ← Previous
          </button>
          <button
            onClick={() => { setFcFlipped(false); setFcIndex(Math.min(content.length - 1, fcIndex + 1)); }}
            disabled={fcIndex === content.length - 1}
            className="fc-nav-btn primary"
          >
            Next →
          </button>
        </div>
      </div>
    );
  };

  // Render Quiz
  const renderQuiz = () => {
    if (!content || !content.quizzes || content.quizzes.length === 0) {
      return renderNotAvailable();
    }
    
    // Quiz selection
    if (!selectedQuiz) {
      return (
        <div className="quiz-selection" data-testid="quiz-selection">
          <h3>Select a Quiz</h3>
          <div className="quiz-cards">
            {content.quizzes.map((quiz) => (
              <div
                key={quiz.quiz_id}
                className={`quiz-card difficulty-${quiz.difficulty.toLowerCase()}`}
                onClick={() => {
                  setSelectedQuiz(quiz);
                  setQuizQuestion(0);
                  setScore(0);
                  setQuizComplete(false);
                }}
                data-testid={`quiz-${quiz.quiz_id}`}
              >
                <h4>{quiz.title}</h4>
                <span className={`difficulty-badge ${quiz.difficulty.toLowerCase()}`}>
                  {quiz.difficulty}
                </span>
                <p>{quiz.questions?.length || 0} Questions</p>
                <button className="start-quiz-btn">Start Quiz</button>
              </div>
            ))}
          </div>
        </div>
      );
    }
    
    // Quiz completed
    if (quizComplete) {
      const percentage = Math.round((score / selectedQuiz.questions.length) * 100);
      return (
        <div className="quiz-complete" data-testid="quiz-complete">
          <div className="score-display">
            <h2>{percentage >= 70 ? '🎉 Great Job!' : '💪 Good Try!'}</h2>
            <div className="score-circle">
              <span className="score-num">{score}</span>
              <span className="score-total">/ {selectedQuiz.questions.length}</span>
            </div>
            <p className="score-percent">{percentage}%</p>
          </div>
          <div className="quiz-actions">
            <button onClick={() => {
              setQuizQuestion(0);
              setScore(0);
              setQuizComplete(false);
              setSelectedAnswer(null);
              setShowResult(false);
            }} className="retry-btn">
              🔄 Try Again
            </button>
            <button onClick={() => setSelectedQuiz(null)} className="back-btn">
              ← Back
            </button>
          </div>
        </div>
      );
    }
    
    // Quiz in progress
    const q = selectedQuiz.questions[quizQuestion];
    
    const handleAnswer = (answer) => {
      setSelectedAnswer(answer);
      setShowResult(true);
      if (answer === q.correct_answer) {
        setScore(s => s + 1);
      }
    };
    
    const handleNext = () => {
      if (quizQuestion < selectedQuiz.questions.length - 1) {
        setQuizQuestion(qn => qn + 1);
        setSelectedAnswer(null);
        setShowResult(false);
      } else {
        setQuizComplete(true);
      }
    };
    
    return (
      <div className="quiz-viewer" data-testid="quiz-viewer">
        <div className="quiz-header">
          <button onClick={() => setSelectedQuiz(null)} className="quit-quiz-btn">✕</button>
          <span className="quiz-title">{selectedQuiz.title}</span>
          <span className="quiz-score">Score: {score}</span>
        </div>
        
        <div className="quiz-progress">
          <div className="quiz-progress-bar">
            <div 
              className="quiz-progress-fill"
              style={{ width: `${((quizQuestion + 1) / selectedQuiz.questions.length) * 100}%` }}
            />
          </div>
        </div>
        
        <div className="question-card">
          <div className="question-number">Question {quizQuestion + 1}</div>
          <h3 className="question-text">
            <FormattedContent content={q.question_text || q.question} />
          </h3>
          
          <div className="options-list">
            {(Array.isArray(q.options) ? q.options : []).map((option, idx) => (
              <button
                key={idx}
                className={`option-btn ${
                  showResult 
                    ? option === q.correct_answer 
                      ? 'correct' 
                      : option === selectedAnswer 
                        ? 'incorrect' 
                        : ''
                    : option === selectedAnswer 
                      ? 'selected' 
                      : ''
                }`}
                onClick={() => !showResult && handleAnswer(option)}
                disabled={showResult}
                data-testid={`option-${idx}`}
              >
                <span className="option-letter">{String.fromCharCode(65 + idx)}</span>
                <FormattedContent content={option} />
              </button>
            ))}
          </div>
          
          {showResult && (
            <div className={`result-box ${selectedAnswer === q.correct_answer ? 'correct' : 'incorrect'}`}>
              {selectedAnswer === q.correct_answer ? (
                <p>🎉 Correct!</p>
              ) : (
                <>
                  <p>❌ Incorrect</p>
                  {q.explanation && <FormattedContent content={q.explanation} />}
                </>
              )}
            </div>
          )}
        </div>
        
        <div className="quiz-footer">
          {showResult && (
            <button onClick={handleNext} className="next-question-btn">
              {quizQuestion < selectedQuiz.questions.length - 1 ? 'Next Question →' : 'See Results'}
            </button>
          )}
        </div>
      </div>
    );
  };

  return (
    <div className="student-content-viewer" data-testid="student-content-viewer">
      <div className="viewer-header">
        <button onClick={onBack} className="back-btn" data-testid="content-back-btn">
          ← Back
        </button>
        <div className="header-info">
          <h2>{chapter?.name}</h2>
          <p className="subject-badge">{subject?.name}</p>
        </div>
      </div>
      
      {/* Content Tabs */}
      <div className="content-tabs">
        <button
          className={`tab-btn ${activeTab === 'video' ? 'active' : ''}`}
          onClick={() => handleTabChange('video')}
          data-testid="tab-video"
        >
          📹 Watch Video
        </button>
        <button
          className={`tab-btn ${activeTab === 'notes' ? 'active' : ''}`}
          onClick={() => handleTabChange('notes')}
          data-testid="tab-notes"
        >
          📝 Revision Notes
        </button>
        <button
          className={`tab-btn ${activeTab === 'flashcards' ? 'active' : ''}`}
          onClick={() => handleTabChange('flashcards')}
          data-testid="tab-flashcards"
        >
          🃏 Flashcards
        </button>
        <button
          className={`tab-btn ${activeTab === 'quiz' ? 'active' : ''}`}
          onClick={() => handleTabChange('quiz')}
          data-testid="tab-quiz"
        >
          📋 Practice Quiz
        </button>
      </div>
      
      {/* Content Area */}
      <div className="content-area">
        {loading ? (
          <div className="loading-state">
            <div className="loading-spinner"></div>
            <p>Loading content...</p>
          </div>
        ) : (
          <>
            {activeTab === 'video' && renderVideo()}
            {activeTab === 'notes' && renderNotes()}
            {activeTab === 'flashcards' && renderFlashcards()}
            {activeTab === 'quiz' && renderQuiz()}
          </>
        )}
      </div>
    </div>
  );
}

export default StudentContentViewer;
