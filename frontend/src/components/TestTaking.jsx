import React, { useState, useEffect, useCallback, useRef } from 'react';
import axios from 'axios';
import QuestionRenderer, { PassageDisplay, SectionHeader } from './QuestionRenderer';
import './TestTaking.css';

const API = process.env.REACT_APP_BACKEND_URL ? `${process.env.REACT_APP_BACKEND_URL}/api` : '/api';

const TestTaking = ({ test, onClose, isTeacherPreview = false }) => {
  const [questions, setQuestions] = useState([]);
  const [answers, setAnswers] = useState({});
  const [loading, setLoading] = useState(true);
  const [timeRemaining, setTimeRemaining] = useState(test.time_remaining_seconds || test.duration_minutes * 60);
  const [submitting, setSubmitting] = useState(false);
  const [testStarted, setTestStarted] = useState(test.started || false);
  const [results, setResults] = useState(null);
  
  // New states for robust error handling
  const [loadError, setLoadError] = useState(null);
  const [retryCount, setRetryCount] = useState(0);
  const [isRetrying, setIsRetrying] = useState(false);
  const maxRetries = 3;
  const retryTimeoutRef = useRef(null);

  useEffect(() => {
    if (testStarted) {
      loadQuestions();
    }
    
    return () => {
      if (retryTimeoutRef.current) {
        clearTimeout(retryTimeoutRef.current);
      }
    };
  }, [testStarted]);

  useEffect(() => {
    if (!testStarted || submitting || results || isTeacherPreview) return;

    const timer = setInterval(() => {
      setTimeRemaining(prev => {
        if (prev <= 1) {
          clearInterval(timer);
          if (!isTeacherPreview) {
            handleAutoSubmit();
          }
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [testStarted, submitting, results, isTeacherPreview]);

  const loadQuestions = async (isManualRetry = false) => {
    if (isManualRetry) {
      setLoadError(null);
      setIsRetrying(true);
    }
    setLoading(true);
    
    try {
      console.log(`📝 Loading questions for test ${test.id} (attempt ${retryCount + 1})`);
      
      const response = await axios.get(`${API}/tests/${test.id}/questions`, {
        withCredentials: true,
        timeout: 30000
      });
      
      if (response.data.error) {
        const errorType = response.data.error_type;
        const message = response.data.message;
        const retryAllowed = response.data.retry_allowed;
        
        console.warn(`⚠️ Backend returned error: ${errorType} - ${message}`);
        
        if (errorType === 'processing' && retryCount < maxRetries) {
          console.log(`⏳ Questions processing, will auto-retry in 3 seconds...`);
          setLoadError({ type: 'processing', message: 'Questions are being prepared. Retrying automatically...' });
          
          retryTimeoutRef.current = setTimeout(() => {
            setRetryCount(prev => prev + 1);
            loadQuestions(true);
          }, 3000);
          return;
        }
        
        if ((errorType === 's3_fetch_failed' || errorType === 'processing') && retryAllowed && retryCount < maxRetries) {
          console.log(`🔄 Transient error, auto-retrying in 2 seconds...`);
          setLoadError({ type: 'retrying', message: 'Loading questions... Please wait.' });
          
          retryTimeoutRef.current = setTimeout(() => {
            setRetryCount(prev => prev + 1);
            loadQuestions(true);
          }, 2000);
          return;
        }
        
        setQuestions([]);
        setLoadError({ 
          type: errorType, 
          message: message,
          canRetry: retryAllowed && retryCount < maxRetries
        });
        return;
      }
      
      const loadedQuestions = response.data.questions || [];
      console.log(`✅ Questions loaded successfully: ${loadedQuestions.length} questions`);
      
      setQuestions(loadedQuestions);
      setLoadError(null);
      setRetryCount(0);
      
    } catch (error) {
      console.error('❌ Network error loading questions:', error);
      
      if (retryCount < maxRetries) {
        console.log(`🔄 Network error, auto-retrying in 2 seconds... (attempt ${retryCount + 1}/${maxRetries})`);
        setLoadError({ type: 'network', message: 'Connection issue. Retrying...' });
        
        retryTimeoutRef.current = setTimeout(() => {
          setRetryCount(prev => prev + 1);
          loadQuestions(true);
        }, 2000);
        return;
      }
      
      setQuestions([]);
      setLoadError({ 
        type: 'network', 
        message: 'Failed to load questions. Please check your connection and try again.',
        canRetry: true
      });
    } finally {
      setLoading(false);
      setIsRetrying(false);
    }
  };

  const handleManualRetry = () => {
    setRetryCount(0);
    loadQuestions(true);
  };

  const startTest = async () => {
    try {
      const response = await axios.post(`${API}/tests/${test.id}/start`, {}, {
        withCredentials: true
      });
      setTimeRemaining(response.data.time_remaining_seconds);
      setTestStarted(true);
    } catch (error) {
      console.error('Error starting test:', error);
      alert(error.response?.data?.detail || 'Failed to start test');
    }
  };

  const handleAnswerChange = (questionNumber, value) => {
    setAnswers(prev => ({
      ...prev,
      [questionNumber]: value
    }));
  };

  const handleAutoSubmit = async () => {
    if (submitting || results) return;
    alert('⏰ Time is up! Submitting your test...');
    await handleSubmit(true);
  };

  const handleSubmit = async (autoSubmit = false) => {
    if (submitting || results) return;
    
    if (!autoSubmit) {
      if (!window.confirm('Are you sure you want to submit your test? You cannot change answers after submission.')) {
        return;
      }
    }

    setSubmitting(true);

    try {
      const response = await axios.post(
        `${API}/tests/${test.id}/submit`,
        new URLSearchParams({
          answers: JSON.stringify(answers)
        }),
        {
          withCredentials: true,
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
        }
      );

      setResults(response.data);
      alert('✅ Test submitted successfully!');
    } catch (error) {
      console.error('Error submitting test:', error);
      alert(error.response?.data?.detail || 'Failed to submit test');
    } finally {
      setSubmitting(false);
    }
  };

  const formatTime = (seconds) => {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    
    if (hours > 0) {
      return `${hours}:${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
    }
    return `${minutes}:${String(secs).padStart(2, '0')}`;
  };

  const getTimerColor = () => {
    if (timeRemaining <= 60) return '#ef4444';
    if (timeRemaining <= 300) return '#f59e0b';
    return '#10b981';
  };

  // Group questions by section
  const getGroupedQuestions = () => {
    const grouped = {};
    questions.forEach(q => {
      const sectionId = q.section_id || 'default';
      if (!grouped[sectionId]) {
        grouped[sectionId] = {
          section_id: sectionId,
          section_title: q.section_title,
          section_instruction: q.section_instruction,
          passage: q.passage,
          questions: []
        };
      }
      grouped[sectionId].questions.push(q);
    });
    return Object.values(grouped);
  };

  if (!testStarted) {
    return (
      <div className="test-start-screen">
        <div className="start-card">
          <h2>📝 {test.title}</h2>
          {isTeacherPreview && (
            <div className="preview-notice" style={{
              background: '#fef3c7',
              color: '#92400e',
              padding: '12px 16px',
              borderRadius: '8px',
              marginBottom: '16px',
              fontWeight: 600,
              fontSize: '14px'
            }}>
              👁️ Preview Mode: You can start and view questions, but submission is disabled.
            </div>
          )}
          <div className="test-info">
            <p><strong>Duration:</strong> {test.duration_minutes} minutes</p>
            <p><strong>Deadline:</strong> {new Date(test.submission_deadline).toLocaleString()}</p>
            <p><strong>Instructions:</strong></p>
            <ul>
              <li>Once you start, the timer begins and cannot be paused</li>
              <li>You must complete within the time limit</li>
              <li>Test will auto-submit when time expires</li>
              <li>You cannot change answers after submission</li>
            </ul>
          </div>
          <div className="start-actions">
            <button onClick={startTest} className="start-btn">
              🚀 Start Test
            </button>
            <button onClick={onClose} className="cancel-btn">
              ← Back
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (results) {
    const percentage = results.percentage !== undefined 
      ? results.percentage 
      : (results.max_score > 0 ? (results.total_score / results.max_score) * 100 : 0);
    
    let stars = 0;
    let trophy = false;
    let message = '';
    
    if (percentage >= 90) {
      stars = 5;
      trophy = true;
      message = '🏆 Outstanding! You are a champion!';
    } else if (percentage >= 80) {
      stars = 4;
      message = '🌟 Excellent work! Keep it up!';
    } else if (percentage >= 70) {
      stars = 3;
      message = '⭐ Good job! You are doing well!';
    } else if (percentage >= 60) {
      stars = 2;
      message = '💪 Not bad! Keep practicing!';
    } else if (percentage > 0) {
      stars = 1;
      message = '📚 Keep learning! You can do better!';
    } else {
      stars = 0;
      message = '🔍 Please review your answers and try again!';
    }
    
    return (
      <div className="test-results">
        <div className="results-card">
          <h2>✅ Test Completed!</h2>
          
          {trophy && (
            <div className="trophy-display" style={{ fontSize: '64px', textAlign: 'center' }}>
              🏆
            </div>
          )}
          
          <div className="stars-display" style={{ textAlign: 'center', fontSize: '32px', margin: '16px 0' }}>
            {Array.from({ length: 5 }).map((_, idx) => (
              <span key={idx}>
                {idx < stars ? '⭐' : '☆'}
              </span>
            ))}
          </div>
          
          <div className="score-display" style={{ textAlign: 'center', margin: '24px 0' }}>
            <div style={{ 
              fontSize: '48px', 
              fontWeight: '700',
              background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent'
            }}>
              {results.total_score !== undefined ? results.total_score.toFixed(1) : '0'}
            </div>
            <div style={{ color: '#64748b' }}>out of {results.max_score !== undefined ? results.max_score : 'N/A'}</div>
            <div style={{ 
              fontSize: '24px', 
              fontWeight: '600', 
              color: '#10b981',
              marginTop: '8px'
            }}>
              {!isNaN(percentage) && isFinite(percentage) ? percentage.toFixed(0) : '0'}%
            </div>
          </div>
          
          <p style={{ textAlign: 'center', fontSize: '18px', color: '#334155' }}>{message}</p>
          
          <div className="test-stats" style={{ 
            background: '#f8fafc', 
            padding: '16px', 
            borderRadius: '10px',
            marginTop: '20px'
          }}>
            <p><strong>Questions:</strong> {results.total_questions || 'N/A'}</p>
            <p><strong>Time Taken:</strong> {results.time_taken_minutes} minutes</p>
            {results.auto_submitted && <p style={{ color: '#f59e0b' }}>⏰ Time expired (auto-submitted)</p>}
          </div>

          <div style={{ marginTop: '24px', textAlign: 'center' }}>
            <button 
              onClick={onClose} 
              style={{
                padding: '12px 32px',
                fontSize: '16px',
                fontWeight: '600',
                background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                color: 'white',
                border: 'none',
                borderRadius: '8px',
                cursor: 'pointer'
              }}
            >
              ← Back to Tests
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (loading || isRetrying) {
    return (
      <div className="test-taking">
        <div className="test-header-fixed">
          <h2>{test.title}</h2>
          <div className="timer" style={{ color: getTimerColor() }}>
            ⏱️ {formatTime(timeRemaining)}
          </div>
        </div>
        <div className="loading-container" data-testid="quiz-loading" style={{ 
          display: 'flex', 
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '60px 20px'
        }}>
          <div className="loading-spinner" style={{
            width: '48px',
            height: '48px',
            border: '4px solid #e2e8f0',
            borderTopColor: '#667eea',
            borderRadius: '50%',
            animation: 'spin 1s linear infinite'
          }}></div>
          <p style={{ marginTop: '20px', color: '#64748b' }}>
            {loadError?.type === 'processing' 
              ? '⏳ Questions are being prepared...' 
              : '📥 Loading questions...'}
          </p>
          {retryCount > 0 && (
            <p style={{ fontSize: '14px', color: '#94a3b8' }}>
              Attempt {retryCount + 1} of {maxRetries + 1}
            </p>
          )}
        </div>
      </div>
    );
  }

  if (loadError && questions.length === 0) {
    return (
      <div className="test-taking">
        <div className="test-header-fixed">
          <h2>{test.title}</h2>
          <div className="timer" style={{ color: getTimerColor() }}>
            ⏱️ {formatTime(timeRemaining)}
          </div>
        </div>
        <div className="error-container" data-testid="quiz-error" style={{
          textAlign: 'center',
          padding: '60px 20px'
        }}>
          <div style={{ fontSize: '48px', marginBottom: '16px' }}>❌</div>
          <p style={{ color: '#ef4444', marginBottom: '20px' }}>{loadError.message}</p>
          {loadError.canRetry && (
            <button 
              onClick={handleManualRetry} 
              data-testid="retry-questions-btn"
              style={{
                padding: '12px 24px',
                background: '#667eea',
                color: 'white',
                border: 'none',
                borderRadius: '8px',
                cursor: 'pointer',
                fontWeight: '600'
              }}
            >
              🔄 Try Again
            </button>
          )}
          <button 
            onClick={onClose} 
            style={{
              padding: '12px 24px',
              background: '#94a3b8',
              color: 'white',
              border: 'none',
              borderRadius: '8px',
              cursor: 'pointer',
              marginLeft: '12px'
            }}
          >
            Close
          </button>
        </div>
      </div>
    );
  }

  const sections = getGroupedQuestions();

  return (
    <div className="test-taking">
      <div className="test-header-fixed">
        <h2>{test.title}</h2>
        <div className="timer" style={{ color: getTimerColor() }}>
          ⏱️ {formatTime(timeRemaining)}
        </div>
      </div>

      {isTeacherPreview && (
        <div style={{
          background: '#fef3c7',
          color: '#92400e',
          padding: '12px 20px',
          textAlign: 'center',
          fontWeight: 600,
          fontSize: '14px',
          borderRadius: '8px',
          margin: '10px 20px',
          border: '2px solid #fbbf24'
        }}>
          👁️ Preview Mode: You can view questions but cannot submit this test
        </div>
      )}

      <div className="test-content" style={{ padding: '20px' }}>
        {questions.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '40px' }}>
            <p>No questions available for this quiz.</p>
            <button 
              onClick={handleManualRetry} 
              style={{
                marginTop: '16px',
                padding: '12px 24px',
                background: '#667eea',
                color: 'white',
                border: 'none',
                borderRadius: '8px',
                cursor: 'pointer'
              }}
            >
              🔄 Refresh
            </button>
          </div>
        ) : (
          <div className="questions-list" data-testid="quiz-questions-list">
            {sections.map((section, sectionIdx) => (
              <div key={section.section_id} className="section-container" style={{ marginBottom: '32px' }}>
                {/* Section Header */}
                {(section.section_instruction || section.section_title) && (
                  <SectionHeader
                    sectionId={section.section_id}
                    sectionTitle={section.section_title}
                    sectionInstruction={section.section_instruction}
                  />
                )}
                
                {/* Passage/Poem for comprehension sections */}
                {section.passage && (
                  <PassageDisplay
                    passage={section.passage}
                    title={section.section_title?.toLowerCase().includes('poem') ? 'Poem' : 'Reading Passage'}
                  />
                )}
                
                {/* Questions in this section */}
                {section.questions.map((q, qIdx) => (
                  <div 
                    key={`${section.section_id}-${q.question_number}`} 
                    className="question-card" 
                    data-testid={`question-${q.question_number}`}
                    style={{ marginBottom: '20px' }}
                  >
                    <QuestionRenderer
                      question={q}
                      answer={answers[q.question_number]}
                      onChange={(value) => handleAnswerChange(q.question_number, value)}
                      disabled={isTeacherPreview}
                      showSection={false}
                      isFirstInSection={qIdx === 0}
                    />
                  </div>
                ))}
              </div>
            ))}
          </div>
        )}

        <div className="submit-section" style={{ textAlign: 'center', padding: '20px 0 40px' }}>
          <button 
            onClick={() => handleSubmit(false)}
            disabled={submitting || questions.length === 0 || isTeacherPreview}
            className="submit-test-btn"
            data-testid="submit-test-btn"
            style={{
              padding: '16px 48px',
              fontSize: '18px',
              fontWeight: '700',
              background: isTeacherPreview ? '#94a3b8' : 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
              color: 'white',
              border: 'none',
              borderRadius: '12px',
              cursor: isTeacherPreview ? 'not-allowed' : 'pointer',
              boxShadow: '0 4px 14px rgba(102, 126, 234, 0.4)',
              opacity: isTeacherPreview || questions.length === 0 ? 0.6 : 1
            }}
          >
            {isTeacherPreview ? '🔒 Submit Disabled (Preview)' : (submitting ? '⏳ Submitting...' : '📤 Submit Test')}
          </button>
        </div>
      </div>
      
      <style>{`
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
};

export default TestTaking;
