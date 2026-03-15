import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import './StudentAITest.css';

// API URL
const API = process.env.REACT_APP_BACKEND_URL;

const QUESTION_TYPE_LABELS = {
  mcq: 'Multiple Choice',
  true_false: 'True / False',
  fill_blank: 'Fill in the Blank',
  one_word: 'One Word',
  match_following: 'Match the Following',
  short_answer: 'Short Answer',
  long_answer: 'Long Answer',
  numerical: 'Numerical',
};

export default function StudentAITest({ test, userId, onClose }) {
  const [phase, setPhase] = useState('loading'); // loading, taking, submitting, results
  const [questions, setQuestions] = useState([]);
  const [answers, setAnswers] = useState({});
  const [activeQ, setActiveQ] = useState(0);
  const [submissionId, setSubmissionId] = useState(null);
  const [results, setResults] = useState(null);
  const [error, setError] = useState('');
  const [timeLeft, setTimeLeft] = useState(null);
  const [startedAt, setStartedAt] = useState(null);

  // Load test and start attempt
  useEffect(() => {
    const init = async () => {
      try {
        // Check if already submitted — go straight to results
        if (test.submitted) {
          setPhase('loading');
          const res = await axios.get(
            `${API}/api/structured-tests/${test.id}/results/${userId}`,
            { withCredentials: true }
          );
          setResults(res.data);
          setPhase('results');
          return;
        }

        // Start the test
        const startRes = await axios.post(
          `${API}/api/structured-tests/${test.id}/start`,
          {},
          { withCredentials: true }
        );
        setSubmissionId(startRes.data.submission_id);
        setStartedAt(new Date(startRes.data.started_at));

        // Fetch test questions
        const testRes = await axios.get(
          `${API}/api/structured-tests/${test.id}`,
          { withCredentials: true }
        );
        setQuestions(testRes.data.questions || []);
        setTimeLeft(test.duration_minutes * 60);
        setPhase('taking');
      } catch (err) {
        const msg = err.response?.data?.detail || err.message;
        if (msg === 'Test already submitted') {
          // Fetch results
          try {
            const res = await axios.get(
              `${API}/api/structured-tests/${test.id}/results/${userId}`,
              { withCredentials: true }
            );
            setResults(res.data);
            setPhase('results');
          } catch {
            setError('Could not load results.');
            setPhase('results');
          }
        } else {
          setError(msg);
          setPhase('taking');
        }
      }
    };
    init();
  }, [test, userId]);

  // Timer
  useEffect(() => {
    if (phase !== 'taking' || timeLeft === null) return;
    if (timeLeft <= 0) {
      handleSubmit();
      return;
    }
    const timer = setTimeout(() => setTimeLeft(t => t - 1), 1000);
    return () => clearTimeout(timer);
  }, [phase, timeLeft]);

  const formatTime = (s) => {
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return `${m}:${sec.toString().padStart(2, '0')}`;
  };

  const updateAnswer = useCallback((qNum, value) => {
    setAnswers(prev => ({ ...prev, [String(qNum)]: value }));
  }, []);

  const handleSubmit = async () => {
    setPhase('submitting');
    setError('');
    try {
      const res = await axios.post(
        `${API}/api/structured-tests/${test.id}/submit`,
        { answers },
        { withCredentials: true }
      );
      setResults({
        total_score: res.data.total_score,
        max_score: res.data.max_score,
        percentage: res.data.percentage,
        detailed_results: res.data.question_results?.map((qr, i) => ({
          question_number: qr.question_number,
          question_text: questions[i]?.question_text || '',
          question_type: questions[i]?.question_type || '',
          student_answer: answers[String(qr.question_number)] || '',
          marks_awarded: qr.marks_awarded,
          max_marks: qr.max_marks,
          feedback: qr.feedback_json,
          verified: qr.verified,
        })) || [],
        results_available: true,
        time_taken_minutes: res.data.time_taken_minutes,
      });
      setPhase('results');
    } catch (err) {
      setError(err.response?.data?.detail || 'Submission failed');
      setPhase('taking');
    }
  };

  const currentQ = questions[activeQ];
  const answeredCount = Object.keys(answers).filter(k => answers[k] && String(answers[k]).trim()).length;

  // ====== LOADING ======
  if (phase === 'loading') {
    return (
      <div className="sat-container" data-testid="student-ai-test-loading">
        <div className="sat-loading">
          <div className="sat-spinner" />
          <p>Loading test...</p>
        </div>
      </div>
    );
  }

  // ====== SUBMITTING ======
  if (phase === 'submitting') {
    return (
      <div className="sat-container" data-testid="student-ai-test-submitting">
        <div className="sat-loading">
          <div className="sat-spinner" />
          <h3>AI is evaluating your answers...</h3>
          <p>This may take a moment. Please wait.</p>
        </div>
      </div>
    );
  }

  // ====== RESULTS ======
  if (phase === 'results') {
    return <ResultsView results={results} test={test} error={error} onClose={onClose} />;
  }

  // ====== TEST TAKING ======
  return (
    <div className="sat-container" data-testid="student-ai-test-taking">
      {/* Header */}
      <div className="sat-header">
        <button className="sat-back-btn" onClick={onClose} data-testid="sat-back-btn">
          Back
        </button>
        <h2 data-testid="sat-test-title">{test.title}</h2>
        {timeLeft !== null && (
          <div className={`sat-timer ${timeLeft < 300 ? 'warning' : ''}`} data-testid="sat-timer">
            {formatTime(timeLeft)}
          </div>
        )}
      </div>

      {error && <div className="sat-error" data-testid="sat-error">{error}</div>}

      {/* Progress */}
      <div className="sat-progress" data-testid="sat-progress">
        <div className="sat-progress-text">
          {answeredCount}/{questions.length} answered
        </div>
        <div className="sat-progress-bar">
          <div
            className="sat-progress-fill"
            style={{ width: `${(answeredCount / questions.length) * 100}%` }}
          />
        </div>
      </div>

      {/* Question Navigation */}
      <div className="sat-q-nav">
        {questions.map((q, i) => {
          const qNum = String(q.question_number);
          const answered = answers[qNum] && String(answers[qNum]).trim();
          return (
            <button
              key={i}
              className={`sat-q-dot ${i === activeQ ? 'active' : ''} ${answered ? 'answered' : ''}`}
              onClick={() => setActiveQ(i)}
              data-testid={`sat-q-nav-${i}`}
            >
              {i + 1}
            </button>
          );
        })}
      </div>

      {/* Current Question */}
      {currentQ && (
        <div className="sat-question-card" data-testid="sat-question-card">
          <div className="sat-q-meta">
            <span className="sat-q-badge">{QUESTION_TYPE_LABELS[currentQ.question_type] || currentQ.question_type}</span>
            <span className="sat-q-marks">{currentQ.max_marks} marks</span>
          </div>
          <h3 className="sat-q-text" data-testid="sat-question-text">
            Q{currentQ.question_number}. {currentQ.question_text}
          </h3>

          {/* Answer Input by Type */}
          <QuestionInput
            question={currentQ}
            answer={answers[String(currentQ.question_number)] || ''}
            onChange={(val) => updateAnswer(currentQ.question_number, val)}
          />
        </div>
      )}

      {/* Navigation Buttons */}
      <div className="sat-nav-btns">
        <button
          className="sat-nav-btn"
          disabled={activeQ === 0}
          onClick={() => setActiveQ(activeQ - 1)}
          data-testid="sat-prev-btn"
        >
          Previous
        </button>
        {activeQ < questions.length - 1 ? (
          <button
            className="sat-nav-btn primary"
            onClick={() => setActiveQ(activeQ + 1)}
            data-testid="sat-next-btn"
          >
            Next
          </button>
        ) : (
          <button
            className="sat-submit-btn"
            onClick={handleSubmit}
            data-testid="sat-submit-btn"
          >
            Submit Test
          </button>
        )}
      </div>
    </div>
  );
}


// ============================================================
// QUESTION INPUT - renders appropriate input for each type
// ============================================================
function QuestionInput({ question, answer, onChange }) {
  const type = question.question_type;

  if (type === 'mcq') {
    const opts = question.objective_data?.options || {};
    return (
      <div className="sat-options" data-testid="sat-mcq-options">
        {Object.entries(opts).map(([key, val]) => (
          <label
            key={key}
            className={`sat-option ${answer === key ? 'selected' : ''}`}
            data-testid={`sat-option-${key}`}
          >
            <input
              type="radio"
              name={`q-${question.question_number}`}
              checked={answer === key}
              onChange={() => onChange(key)}
            />
            <span className="sat-option-key">{key.toUpperCase()}</span>
            <span className="sat-option-text">{val}</span>
          </label>
        ))}
      </div>
    );
  }

  if (type === 'true_false') {
    return (
      <div className="sat-options" data-testid="sat-tf-options">
        {['true', 'false'].map(v => (
          <label
            key={v}
            className={`sat-option ${answer === v ? 'selected' : ''}`}
            data-testid={`sat-tf-${v}`}
          >
            <input
              type="radio"
              name={`q-${question.question_number}`}
              checked={answer === v}
              onChange={() => onChange(v)}
            />
            <span className="sat-option-text">{v.charAt(0).toUpperCase() + v.slice(1)}</span>
          </label>
        ))}
      </div>
    );
  }

  if (type === 'fill_blank' || type === 'one_word') {
    return (
      <input
        className="sat-text-input"
        type="text"
        value={answer}
        onChange={e => onChange(e.target.value)}
        placeholder={type === 'one_word' ? 'Type your answer (one word)' : 'Fill in the blank'}
        data-testid="sat-text-answer"
      />
    );
  }

  if (type === 'match_following') {
    const leftItems = question.objective_data?.pairs_left || [];
    let matchObj = {};
    try { matchObj = typeof answer === 'string' ? JSON.parse(answer) : (answer || {}); } catch { matchObj = {}; }

    return (
      <div className="sat-match-section" data-testid="sat-match-section">
        <p className="sat-match-hint">Match each item on the left with the correct item on the right</p>
        {leftItems.map((left, idx) => (
          <div key={idx} className="sat-match-row">
            <span className="sat-match-left">{left}</span>
            <span className="sat-match-arrow">→</span>
            <input
              className="sat-match-input"
              type="text"
              value={matchObj[String(idx)] || ''}
              onChange={e => {
                const updated = { ...matchObj, [String(idx)]: e.target.value };
                onChange(JSON.stringify(updated));
              }}
              placeholder="Your match"
              data-testid={`sat-match-input-${idx}`}
            />
          </div>
        ))}
      </div>
    );
  }

  // Short answer, long answer, numerical — textarea
  return (
    <textarea
      className="sat-textarea"
      value={answer}
      onChange={e => onChange(e.target.value)}
      placeholder={
        type === 'numerical' ? 'Show your working step by step...' :
        type === 'long_answer' ? 'Write your detailed answer...' :
        'Write your answer...'
      }
      rows={type === 'long_answer' ? 8 : type === 'numerical' ? 6 : 4}
      data-testid="sat-textarea-answer"
    />
  );
}


// ============================================================
// RESULTS VIEW
// ============================================================
function ResultsView({ results, test, error, onClose }) {
  if (error && !results) {
    return (
      <div className="sat-container" data-testid="sat-results-error">
        <div className="sat-header">
          <button className="sat-back-btn" onClick={onClose}>Back</button>
          <h2>Test Results</h2>
        </div>
        <div className="sat-error">{error}</div>
      </div>
    );
  }

  if (!results) return null;

  const score = results.teacher_final_score ?? results.total_score ?? 0;
  const maxScore = results.max_score ?? 0;
  const pct = results.percentage ?? (maxScore > 0 ? Math.round((score / maxScore) * 100) : 0);
  const grade = pct >= 90 ? 'A+' : pct >= 80 ? 'A' : pct >= 70 ? 'B' : pct >= 60 ? 'C' : pct >= 50 ? 'D' : 'F';
  const gradeColor = pct >= 80 ? '#16a34a' : pct >= 60 ? '#d97706' : '#dc2626';

  return (
    <div className="sat-container" data-testid="student-ai-test-results">
      <div className="sat-header">
        <button className="sat-back-btn" onClick={onClose} data-testid="sat-results-back">Back</button>
        <h2>{test.title} — Results</h2>
      </div>

      {/* Score Summary */}
      <div className="sat-score-card" data-testid="sat-score-card">
        <div className="sat-score-main">
          <div className="sat-grade" style={{ color: gradeColor }} data-testid="sat-grade">{grade}</div>
          <div className="sat-score-numbers">
            <div className="sat-score-big" data-testid="sat-score">{score}/{maxScore}</div>
            <div className="sat-score-pct" data-testid="sat-percentage">{pct}%</div>
          </div>
        </div>
        {results.teacher_reviewed && (
          <div className="sat-teacher-badge" data-testid="sat-teacher-reviewed">
            Teacher Reviewed
          </div>
        )}
        {results.improvement_summary && (
          <div className="sat-improvement" data-testid="sat-improvement">
            <strong>Improvement Notes:</strong> {results.improvement_summary}
          </div>
        )}
      </div>

      {/* Per-Question Breakdown */}
      {results.results_available && results.detailed_results?.length > 0 ? (
        <div className="sat-breakdown" data-testid="sat-breakdown">
          <h3>Question-wise Breakdown</h3>
          {results.detailed_results.map((qr, idx) => (
            <QuestionResult key={idx} result={qr} />
          ))}
        </div>
      ) : (
        <div className="sat-info-box" data-testid="sat-no-details">
          Detailed feedback has expired or is not available.
        </div>
      )}
    </div>
  );
}


// ============================================================
// SINGLE QUESTION RESULT
// ============================================================
function QuestionResult({ result }) {
  const [expanded, setExpanded] = useState(false);
  const pct = result.max_marks > 0 ? (result.marks_awarded / result.max_marks) * 100 : 0;
  const statusColor = pct >= 80 ? '#16a34a' : pct >= 40 ? '#d97706' : '#dc2626';
  const statusLabel = pct >= 80 ? 'Correct' : pct >= 40 ? 'Partial' : pct === 0 ? 'Incorrect' : 'Needs Work';
  const feedback = result.feedback || {};

  return (
    <div className="sat-qr-card" data-testid={`sat-qr-${result.question_number}`}>
      <div className="sat-qr-header" onClick={() => setExpanded(!expanded)}>
        <div className="sat-qr-left">
          <span className="sat-qr-num">Q{result.question_number}</span>
          <span className="sat-qr-type">{QUESTION_TYPE_LABELS[result.question_type] || result.question_type}</span>
          <span className="sat-qr-status" style={{ background: statusColor }}>{statusLabel}</span>
        </div>
        <div className="sat-qr-right">
          <span className="sat-qr-marks" style={{ color: statusColor }}>
            {result.marks_awarded}/{result.max_marks}
          </span>
          <span className={`sat-qr-chevron ${expanded ? 'open' : ''}`}>&#9660;</span>
        </div>
      </div>

      {expanded && (
        <div className="sat-qr-body" data-testid={`sat-qr-body-${result.question_number}`}>
          {result.question_text && (
            <div className="sat-qr-section">
              <label>Question</label>
              <p>{result.question_text}</p>
            </div>
          )}
          <div className="sat-qr-section">
            <label>Your Answer</label>
            <p className="sat-qr-answer">{result.student_answer || '(No answer provided)'}</p>
          </div>

          {/* Overall Feedback */}
          {feedback.overall_feedback && (
            <div className="sat-qr-section">
              <label>Feedback</label>
              <p>{feedback.overall_feedback}</p>
            </div>
          )}

          {/* Evaluation Points (subjective) */}
          {feedback.evaluation_points?.length > 0 && (
            <div className="sat-qr-section">
              <label>Rubric Breakdown</label>
              <div className="sat-rubric-list">
                {feedback.evaluation_points.map((ep, i) => (
                  <div key={i} className={`sat-rubric-item ${ep.covered ? 'covered' : 'missed'}`}>
                    <span className="sat-rubric-icon">{ep.covered ? '\u2713' : '\u2717'}</span>
                    <div className="sat-rubric-content">
                      <strong>{ep.title}</strong>
                      <span className="sat-rubric-marks">{ep.marks_given}/{result.max_marks > 0 ? '' : ''}marks</span>
                      {ep.explanation && <p>{ep.explanation}</p>}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Steps Evaluation (numerical) */}
          {feedback.steps_evaluation?.length > 0 && (
            <div className="sat-qr-section">
              <label>Step-by-Step Evaluation</label>
              <div className="sat-rubric-list">
                {feedback.steps_evaluation.map((step, i) => (
                  <div key={i} className={`sat-rubric-item ${step.completed ? 'covered' : 'missed'}`}>
                    <span className="sat-rubric-icon">{step.completed ? '\u2713' : '\u2717'}</span>
                    <div className="sat-rubric-content">
                      <strong>{step.title}</strong>
                      <span className="sat-rubric-marks">{step.marks_given} marks</span>
                      {step.explanation && <p>{step.explanation}</p>}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Match details */}
          {feedback.match_details?.length > 0 && (
            <div className="sat-qr-section">
              <label>Match Results</label>
              <div className="sat-rubric-list">
                {feedback.match_details.map((m, i) => (
                  <div key={i} className={`sat-rubric-item ${m.matched ? 'covered' : 'missed'}`}>
                    <span className="sat-rubric-icon">{m.matched ? '\u2713' : '\u2717'}</span>
                    <div className="sat-rubric-content">
                      <strong>{m.left}</strong> → {m.matched ? m.correct_right : <><s>{m.student_right}</s> (Correct: {m.correct_right})</>}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Correct answer for objective */}
          {feedback.correct_answer && !feedback.correct && (
            <div className="sat-qr-section">
              <label>Correct Answer</label>
              <p className="sat-correct-answer">{feedback.correct_answer}</p>
            </div>
          )}

          {/* Improvement suggestions */}
          {feedback.improvement_suggestions && (
            <div className="sat-qr-section">
              <label>How to Improve</label>
              <p className="sat-improvement-text">{feedback.improvement_suggestions}</p>
            </div>
          )}

          {/* Teacher comment */}
          {result.teacher_comment && (
            <div className="sat-qr-section teacher-comment">
              <label>Teacher Comment</label>
              <p>{result.teacher_comment}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
