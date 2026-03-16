import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './StudentAITest.css';

const API = process.env.REACT_APP_BACKEND_URL;

const QUESTION_TYPE_LABELS = {
  mcq: 'MCQ', true_false: 'True/False', fill_blank: 'Fill in Blank',
  one_word: 'One Word', match_following: 'Match', short_answer: 'Short Answer',
  long_answer: 'Long Answer', numerical: 'Numerical',
};

export default function StudentAIHomework({ homeworkId, onBack }) {
  const [homework, setHomework] = useState(null);
  const [questions, setQuestions] = useState([]);
  const [answers, setAnswers] = useState({});
  const [hints, setHints] = useState({});
  const [activeQ, setActiveQ] = useState(0);
  const [loading, setLoading] = useState(true);
  const [hintLoading, setHintLoading] = useState(false);
  const [hintContent, setHintContent] = useState({});
  const [completed, setCompleted] = useState(false);

  useEffect(() => {
    loadHomework();
  }, [homeworkId]);

  const loadHomework = async () => {
    try {
      const [hwResp, startResp] = await Promise.all([
        axios.get(`${API}/api/structured-homework/${homeworkId}`),
        axios.post(`${API}/api/structured-homework/${homeworkId}/start`),
      ]);
      setHomework(hwResp.data);
      setQuestions(hwResp.data.questions || []);
      setAnswers(startResp.data.answers || {});
      setHints(startResp.data.hints || {});
    } catch (err) {
      console.error('Failed to load homework:', err);
    }
    setLoading(false);
  };

  const updateAnswer = (qNum, value) => {
    const updated = { ...answers, [String(qNum)]: value };
    setAnswers(updated);
    // Auto-save
    axios.post(`${API}/api/structured-homework/${homeworkId}/save-progress`, {
      answers: updated, hints,
    }).catch(() => {});
  };

  const requestHint = async (qNum) => {
    setHintLoading(true);
    try {
      const resp = await axios.post(`${API}/api/structured-homework/${homeworkId}/hint`, {
        question_number: qNum,
        student_answer: answers[String(qNum)] || '',
      });
      const qKey = String(qNum);
      setHintContent(prev => ({ ...prev, [qKey]: resp.data }));
      setHints(prev => ({
        ...prev,
        [qKey]: {
          hint_used: true,
          answer_revealed: false,
        },
      }));
    } catch (err) {
      console.error('Hint request failed:', err);
    }
    setHintLoading(false);
  };

  const checkAnswer = async (qNum) => {
    setHintLoading(true);
    try {
      const resp = await axios.post(`${API}/api/structured-homework/${homeworkId}/check-answer`, {
        question_number: qNum,
        student_answer: answers[String(qNum)] || '',
      });
      const qKey = String(qNum);
      setHintContent(prev => ({
        ...prev,
        [qKey]: {
          ...prev[qKey],
          checked: true,
          correct: resp.data.correct,
        },
      }));
    } catch (err) {
      console.error('Check answer failed:', err);
    }
    setHintLoading(false);
  };

  const handleComplete = async () => {
    try {
      await axios.post(`${API}/api/structured-homework/${homeworkId}/complete`, {
        answers, hints,
      });
      setCompleted(true);
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to submit');
    }
  };

  if (loading) {
    return (
      <div className="sat-container" data-testid="hw-loading">
        <div className="sat-loading">Loading homework...</div>
      </div>
    );
  }

  if (completed) {
    return (
      <div className="sat-container" data-testid="hw-completed">
        <div className="sat-header">
          <h2>Homework Completed!</h2>
        </div>
        <div style={{ textAlign: 'center', padding: '40px 20px' }}>
          <div style={{ fontSize: '48px', marginBottom: '16px' }}>&#10003;</div>
          <h3 style={{ color: '#48bb78', marginBottom: '12px' }}>Well done!</h3>
          <p style={{ color: 'rgba(255,255,255,0.7)', marginBottom: '24px' }}>
            You have completed "{homework?.title}". Your teacher will be able to see your progress.
          </p>
          <button className="sat-submit-btn" onClick={onBack} data-testid="hw-back-btn">
            Back to Homework
          </button>
        </div>
      </div>
    );
  }

  if (!questions.length) {
    return (
      <div className="sat-container">
        <div className="sat-header">
          <button className="sat-back-btn" onClick={onBack}>Back</button>
          <h2>No questions found</h2>
        </div>
      </div>
    );
  }

  const currentQ = questions[activeQ];
  const qKey = String(currentQ?.question_number);
  const answeredCount = Object.values(answers).filter(v => v && String(v).trim()).length;
  const qHintData = hintContent[qKey];
  const qHints = hints[qKey] || {};

  return (
    <div className="sat-container" data-testid="hw-solver">
      {/* Header */}
      <div className="sat-header">
        <button className="sat-back-btn" onClick={onBack} data-testid="hw-back">Back</button>
        <div className="sat-title-section">
          <h2>{homework?.title}</h2>
          <div className="sat-meta">
            <span>{answeredCount}/{questions.length} answered</span>
            {homework?.deadline && (
              <span>Due: {new Date(homework.deadline).toLocaleDateString()}</span>
            )}
          </div>
        </div>
      </div>

      {/* Progress */}
      <div className="sat-progress-section">
        <div className="sat-progress-bar">
          <div className="sat-progress-fill" style={{ width: `${(answeredCount / questions.length) * 100}%` }} />
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
              data-testid={`hw-q-nav-${i}`}
            >
              {i + 1}
            </button>
          );
        })}
      </div>

      {/* Current Question */}
      {currentQ && (
        <div className="sat-question-card" data-testid="hw-question-card">
          <div className="sat-q-meta">
            <span className="sat-q-badge">{QUESTION_TYPE_LABELS[currentQ.question_type] || currentQ.question_type}</span>
          </div>
          <h3 className="sat-q-text" data-testid="hw-question-text">
            Q{currentQ.question_number}. {currentQ.question_text}
          </h3>

          <QuestionInput
            question={currentQ}
            answer={answers[qKey] || ''}
            onChange={(val) => updateAnswer(currentQ.question_number, val)}
          />

          {/* Hint Section */}
          <div className="hw-hint-section" data-testid="hw-hint-section">
            {!qHintData && !qHints.hint_used && (
              <button
                className="hw-hint-btn"
                onClick={() => requestHint(currentQ.question_number)}
                disabled={hintLoading}
                data-testid="hw-hint-btn"
              >
                {hintLoading ? 'Getting hint...' : 'Need a hint?'}
              </button>
            )}

            {qHintData?.type === 'hint' && (
              <div className="hw-hint-box" data-testid="hw-hint-box">
                <div className="hw-hint-label">Hint</div>
                <p>{qHintData.content}</p>
                {qHintData.checked ? (
                  <div className={`hw-check-result ${qHintData.correct ? 'correct' : 'incorrect'}`} data-testid="hw-check-result">
                    {qHintData.correct ? 'Correct! Well done!' : 'Not quite right. Try again!'}
                  </div>
                ) : (
                  <button
                    className="hw-check-btn"
                    onClick={() => checkAnswer(currentQ.question_number)}
                    disabled={hintLoading || !answers[qKey]?.toString().trim()}
                    data-testid="hw-check-btn"
                  >
                    {hintLoading ? 'Checking...' : 'Check My Answer'}
                  </button>
                )}
              </div>
            )}

            {/* Show hint box on revisit if hint was used */}
            {!qHintData && qHints.hint_used && (
              <button
                className="hw-hint-btn"
                onClick={() => requestHint(currentQ.question_number)}
                disabled={hintLoading}
                style={{ opacity: 0.7 }}
              >
                {hintLoading ? 'Loading...' : 'View Hint Again'}
              </button>
            )}
          </div>
        </div>
      )}

      {/* Navigation */}
      <div className="sat-nav-btns">
        <button
          className="sat-nav-btn"
          disabled={activeQ === 0}
          onClick={() => setActiveQ(activeQ - 1)}
          data-testid="hw-prev-btn"
        >
          Previous
        </button>
        {activeQ < questions.length - 1 ? (
          <button
            className="sat-nav-btn primary"
            onClick={() => setActiveQ(activeQ + 1)}
            data-testid="hw-next-btn"
          >
            Next
          </button>
        ) : (
          <button
            className="sat-submit-btn"
            onClick={handleComplete}
            data-testid="hw-complete-btn"
          >
            Mark as Complete
          </button>
        )}
      </div>
    </div>
  );
}


// ============================================================
// QUESTION INPUT (reuse same patterns as StudentAITest)
// ============================================================
function QuestionInput({ question, answer, onChange }) {
  const type = question.question_type;

  if (type === 'mcq') {
    const opts = question.options || {};
    return (
      <div className="sat-options" data-testid="hw-mcq-options">
        {Object.entries(opts).map(([key, val]) => (
          <label key={key} className={`sat-option ${answer === key ? 'selected' : ''}`}>
            <input type="radio" name={`hw-q-${question.question_number}`} checked={answer === key} onChange={() => onChange(key)} />
            <span className="sat-option-key">{key.toUpperCase()}</span>
            <span className="sat-option-text">{val}</span>
          </label>
        ))}
      </div>
    );
  }

  if (type === 'true_false') {
    return (
      <div className="sat-options" data-testid="hw-tf-options">
        {['true', 'false'].map(v => (
          <label key={v} className={`sat-option ${answer === v ? 'selected' : ''}`}>
            <input type="radio" name={`hw-q-${question.question_number}`} checked={answer === v} onChange={() => onChange(v)} />
            <span className="sat-option-text">{v.charAt(0).toUpperCase() + v.slice(1)}</span>
          </label>
        ))}
      </div>
    );
  }

  if (type === 'fill_blank' || type === 'one_word') {
    return (
      <input className="sat-text-input" type="text" value={answer} onChange={e => onChange(e.target.value)}
        placeholder={type === 'one_word' ? 'Type your answer (one word)' : 'Fill in the blank'} />
    );
  }

  if (type === 'match_following') {
    const leftItems = question.pairs_left || [];
    const rightOptions = question.pairs_right || [];
    let matchObj = {};
    try { matchObj = typeof answer === 'string' ? JSON.parse(answer) : (answer || {}); } catch { matchObj = {}; }
    const usedValues = Object.values(matchObj).filter(v => v);
    return (
      <div className="sat-match-section">
        <p className="sat-match-hint">Match each item on the left with the correct item on the right</p>
        {leftItems.map((left, idx) => (
          <div key={idx} className="sat-match-row">
            <span className="sat-match-left">{left}</span>
            <span className="sat-match-arrow">&rarr;</span>
            <select
              className="sat-match-select"
              value={matchObj[String(idx)] || ''}
              onChange={e => { onChange(JSON.stringify({ ...matchObj, [String(idx)]: e.target.value })); }}
              data-testid={`hw-match-select-${idx}`}
            >
              <option value="">Select match</option>
              {rightOptions.map((right, rIdx) => {
                const isUsed = usedValues.includes(right) && matchObj[String(idx)] !== right;
                return (
                  <option key={rIdx} value={right} disabled={isUsed}>
                    {right}
                  </option>
                );
              })}
            </select>
          </div>
        ))}
      </div>
    );
  }

  return (
    <textarea className="sat-textarea" value={answer} onChange={e => onChange(e.target.value)}
      placeholder={type === 'numerical' ? 'Show your working step by step...' : type === 'long_answer' ? 'Write your detailed answer...' : 'Write your answer...'}
      rows={type === 'long_answer' ? 8 : type === 'numerical' ? 6 : 4} />
  );
}
