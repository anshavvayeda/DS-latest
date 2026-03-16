import React, { useState, useCallback } from 'react';
import axios from 'axios';
import './StructuredTestCreator.css';

const API = process.env.REACT_APP_BACKEND_URL;

const QUESTION_TYPES = [
  { value: 'mcq', label: 'Multiple Choice' },
  { value: 'true_false', label: 'True / False' },
  { value: 'fill_blank', label: 'Fill in the Blank' },
  { value: 'one_word', label: 'One Word Answer' },
  { value: 'match_following', label: 'Match the Following' },
  { value: 'short_answer', label: 'Short Answer' },
  { value: 'long_answer', label: 'Long Answer' },
  { value: 'numerical', label: 'Numerical / Step Based' },
];

const NEEDS_MODEL_ANSWER = ['short_answer', 'long_answer', 'numerical'];

const emptyQuestion = () => ({
  question_number: 1,
  question_type: 'mcq',
  question_text: '',
  model_answer: '',
  objective_data: { options: { a: '', b: '', c: '', d: '' }, correct: '' },
});

export default function StructuredHomeworkCreator({ subjectId, subjectName, standard, schoolName, onBack }) {
  const [step, setStep] = useState('setup');
  const [hwInfo, setHwInfo] = useState({ title: '', deadline: '' });
  const [questions, setQuestions] = useState([emptyQuestion()]);
  const [activeQ, setActiveQ] = useState(0);
  const [publishing, setPublishing] = useState(false);
  const [message, setMessage] = useState('');
  const [hwId, setHwId] = useState(null);

  const currentQ = questions[activeQ] || emptyQuestion();

  const updateQuestion = useCallback((field, value) => {
    setQuestions(prev => {
      const updated = [...prev];
      updated[activeQ] = { ...updated[activeQ], [field]: value };
      return updated;
    });
  }, [activeQ]);

  const handleTypeChange = (newType) => {
    const defaults = {};
    if (newType === 'mcq') {
      defaults.objective_data = { options: { a: '', b: '', c: '', d: '' }, correct: '' };
    } else if (newType === 'true_false') {
      defaults.objective_data = { correct: '' };
    } else if (newType === 'fill_blank' || newType === 'one_word') {
      defaults.objective_data = { correct: '' };
    } else if (newType === 'match_following') {
      defaults.objective_data = { pairs: [{ left: '', right: '' }] };
    } else {
      defaults.objective_data = null;
    }
    setQuestions(prev => {
      const updated = [...prev];
      updated[activeQ] = { ...updated[activeQ], question_type: newType, ...defaults };
      return updated;
    });
  };

  const addQuestion = () => {
    const newQ = emptyQuestion();
    newQ.question_number = questions.length + 1;
    setQuestions([...questions, newQ]);
    setActiveQ(questions.length);
  };

  const removeQuestion = (idx) => {
    if (questions.length <= 1) return;
    const updated = questions.filter((_, i) => i !== idx).map((q, i) => ({ ...q, question_number: i + 1 }));
    setQuestions(updated);
    setActiveQ(Math.min(activeQ, updated.length - 1));
  };

  // Match pairs
  const addPair = () => {
    const obj = { ...(currentQ.objective_data || {}) };
    const pairs = [...(obj.pairs || [])];
    pairs.push({ left: '', right: '' });
    obj.pairs = pairs;
    updateQuestion('objective_data', obj);
  };
  const updatePair = (idx, side, value) => {
    const obj = { ...(currentQ.objective_data || {}) };
    const pairs = [...(obj.pairs || [])];
    pairs[idx] = { ...pairs[idx], [side]: value };
    obj.pairs = pairs;
    updateQuestion('objective_data', obj);
  };
  const removePair = (idx) => {
    const obj = { ...(currentQ.objective_data || {}) };
    obj.pairs = (obj.pairs || []).filter((_, i) => i !== idx);
    updateQuestion('objective_data', obj);
  };

  const handleSaveAndPublish = async () => {
    setPublishing(true);
    setMessage('');
    try {
      const resp = await axios.post(`${API}/api/structured-homework`, {
        subject_id: subjectId,
        standard,
        title: hwInfo.title,
        school_name: schoolName,
        deadline: new Date(hwInfo.deadline).toISOString(),
        questions,
      });
      setHwId(resp.data.id);
      setMessage(`Homework published! ${resp.data.question_count} questions.`);
    } catch (err) {
      setMessage('Error: ' + (err.response?.data?.detail || err.message));
    }
    setPublishing(false);
  };

  // ===== RENDER =====

  if (step === 'setup') {
    return (
      <div className="stc-container" data-testid="homework-creator">
        <div className="stc-header">
          <button className="stc-back-btn" onClick={onBack} data-testid="hw-creator-back">Back</button>
          <h2>Create AI Homework</h2>
        </div>
        <div className="stc-setup-form">
          <div className="stc-field">
            <label>Subject</label>
            <div className="stc-readonly-field">{subjectName}</div>
          </div>
          <div className="stc-field">
            <label>Homework Title</label>
            <input
              data-testid="hw-title-input"
              type="text"
              value={hwInfo.title}
              onChange={e => setHwInfo({ ...hwInfo, title: e.target.value })}
              placeholder="e.g. Chapter 5 - Practice Problems"
            />
          </div>
          <div className="stc-field">
            <label>Deadline</label>
            <input
              data-testid="hw-deadline-input"
              type="datetime-local"
              value={hwInfo.deadline}
              onChange={e => setHwInfo({ ...hwInfo, deadline: e.target.value })}
            />
          </div>
          <button
            className="stc-primary-btn"
            data-testid="hw-next-btn"
            disabled={!hwInfo.title || !hwInfo.deadline}
            onClick={() => setStep('questions')}
          >
            Proceed to Add Questions
          </button>
        </div>
      </div>
    );
  }

  if (hwId) {
    return (
      <div className="stc-container">
        <div className="stc-success" data-testid="hw-success">
          <h2>Homework Published!</h2>
          <p>{message}</p>
          <button className="stc-primary-btn" onClick={onBack}>Back to Subject</button>
        </div>
      </div>
    );
  }

  return (
    <div className="stc-container" data-testid="homework-question-editor">
      <div className="stc-header">
        <button className="stc-back-btn" onClick={() => setStep('setup')} data-testid="hw-back-setup">Back to Setup</button>
        <h2>{hwInfo.title || 'New Homework'}</h2>
        <div className="stc-marks-badge" data-testid="hw-question-count">
          {questions.length} question{questions.length > 1 ? 's' : ''}
        </div>
      </div>

      {/* Question Tabs */}
      <div className="stc-q-tabs">
        {questions.map((q, i) => (
          <button
            key={i}
            className={`stc-q-tab ${i === activeQ ? 'active' : ''}`}
            onClick={() => setActiveQ(i)}
            data-testid={`hw-q-tab-${i}`}
          >
            Q{i + 1}
          </button>
        ))}
        <button className="stc-q-tab add" onClick={addQuestion} data-testid="hw-add-q">+</button>
      </div>

      <div className="stc-q-editor">
        {/* Question Header */}
        <div className="stc-section">
          <h3>Question {activeQ + 1}</h3>
          {questions.length > 1 && (
            <button className="stc-remove-btn" onClick={() => removeQuestion(activeQ)} data-testid="hw-remove-q">Remove</button>
          )}
        </div>

        <div className="stc-field">
          <label>Question Type</label>
          <select
            data-testid="hw-q-type"
            value={currentQ.question_type}
            onChange={e => handleTypeChange(e.target.value)}
          >
            {QUESTION_TYPES.map(t => (
              <option key={t.value} value={t.value}>{t.label}</option>
            ))}
          </select>
        </div>

        <div className="stc-field">
          <label>Question Text</label>
          <textarea
            data-testid="hw-q-text"
            value={currentQ.question_text}
            onChange={e => updateQuestion('question_text', e.target.value)}
            placeholder="Enter question text..."
            rows={3}
          />
        </div>

        {/* MCQ Options */}
        {currentQ.question_type === 'mcq' && (
          <div className="stc-section-box">
            <h4>MCQ Options</h4>
            {['a', 'b', 'c', 'd'].map(opt => (
              <div className="stc-field stc-inline" key={opt}>
                <label>Option {opt.toUpperCase()}</label>
                <input
                  data-testid={`hw-option-${opt}`}
                  type="text"
                  value={(currentQ.objective_data?.options || {})[opt] || ''}
                  onChange={e => {
                    const obj = { ...(currentQ.objective_data || {}), options: { ...(currentQ.objective_data?.options || {}) } };
                    obj.options[opt] = e.target.value;
                    updateQuestion('objective_data', obj);
                  }}
                  placeholder={`Option ${opt.toUpperCase()}`}
                />
              </div>
            ))}
            <div className="stc-field">
              <label>Correct Option</label>
              <select
                data-testid="hw-correct-option"
                value={currentQ.objective_data?.correct || ''}
                onChange={e => updateQuestion('objective_data', { ...currentQ.objective_data, correct: e.target.value })}
              >
                <option value="">Select</option>
                {['a', 'b', 'c', 'd'].map(o => <option key={o} value={o}>{o.toUpperCase()}</option>)}
              </select>
            </div>
          </div>
        )}

        {/* True/False */}
        {currentQ.question_type === 'true_false' && (
          <div className="stc-section-box">
            <h4>Correct Answer</h4>
            <div className="stc-radio-group">
              {['true', 'false'].map(v => (
                <label key={v} className="stc-radio">
                  <input
                    type="radio"
                    name={`hw-tf-${activeQ}`}
                    checked={currentQ.objective_data?.correct === v}
                    onChange={() => updateQuestion('objective_data', { correct: v })}
                    data-testid={`hw-tf-${v}`}
                  />
                  {v.charAt(0).toUpperCase() + v.slice(1)}
                </label>
              ))}
            </div>
          </div>
        )}

        {/* Fill / One Word */}
        {(currentQ.question_type === 'fill_blank' || currentQ.question_type === 'one_word') && (
          <div className="stc-section-box">
            <h4>Correct Answer</h4>
            <input
              data-testid="hw-correct-answer"
              type="text"
              value={currentQ.objective_data?.correct || ''}
              onChange={e => updateQuestion('objective_data', { correct: e.target.value })}
              placeholder={currentQ.question_type === 'one_word' ? 'Single word answer' : 'Fill in the blank answer'}
            />
          </div>
        )}

        {/* Match the Following */}
        {currentQ.question_type === 'match_following' && (
          <div className="stc-section-box">
            <h4>Matching Pairs</h4>
            {(currentQ.objective_data?.pairs || []).map((pair, idx) => (
              <div className="stc-pair-row" key={idx}>
                <input
                  data-testid={`hw-match-left-${idx}`}
                  type="text"
                  value={pair.left}
                  onChange={e => updatePair(idx, 'left', e.target.value)}
                  placeholder="Left side"
                />
                <span className="stc-arrow">→</span>
                <input
                  data-testid={`hw-match-right-${idx}`}
                  type="text"
                  value={pair.right}
                  onChange={e => updatePair(idx, 'right', e.target.value)}
                  placeholder="Right side"
                />
                <button className="stc-remove-sm" onClick={() => removePair(idx)}>×</button>
              </div>
            ))}
            <button className="stc-add-btn" onClick={addPair} data-testid="hw-add-pair">+ Add Pair</button>
          </div>
        )}

        {/* Model Answer for subjective types */}
        {NEEDS_MODEL_ANSWER.includes(currentQ.question_type) && (
          <div className="stc-section-box">
            <h4>Model Answer</h4>
            <textarea
              data-testid="hw-model-answer"
              value={currentQ.model_answer || ''}
              onChange={e => updateQuestion('model_answer', e.target.value)}
              placeholder="Enter the ideal answer that represents the expected response..."
              rows={4}
            />
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="stc-actions">
        <button
          className="stc-publish-btn"
          onClick={handleSaveAndPublish}
          disabled={publishing || questions.some(q => !q.question_text)}
          data-testid="hw-publish-btn"
        >
          {publishing ? 'Publishing...' : 'Save & Publish Homework'}
        </button>
      </div>

      {message && (
        <div className={`stc-message ${message.startsWith('Error') ? 'error' : 'success'}`} data-testid="hw-message">
          {message}
        </div>
      )}
    </div>
  );
}
