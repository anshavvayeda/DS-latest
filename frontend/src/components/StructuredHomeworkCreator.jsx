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
const OBJECTIVE_TYPES = ['mcq', 'true_false', 'fill_blank', 'one_word', 'match_following'];

const emptyQuestion = () => ({
  question_number: 1,
  question_type: 'mcq',
  question_text: '',
  model_answer: '',
  objective_data: { options: { a: '', b: '', c: '', d: '' }, correct: '' },
  evaluation_points: [],
  solution_steps: [],
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
            <label>Class</label>
            <div className="stc-readonly-field">Standard {standard}</div>
          </div>
          <div className="stc-field">
            <label>Homework Title</label>
            <input
              value={hwInfo.title}
              onChange={e => setHwInfo({ ...hwInfo, title: e.target.value })}
              placeholder="e.g. Chapter 5 - Practice Problems"
              className="stc-input"
              data-testid="hw-title-input"
            />
          </div>
          <div className="stc-field">
            <label>Deadline</label>
            <input
              type="datetime-local"
              value={hwInfo.deadline}
              onChange={e => setHwInfo({ ...hwInfo, deadline: e.target.value })}
              className="stc-input"
              data-testid="hw-deadline-input"
            />
          </div>
          <button
            className="stc-publish-btn"
            onClick={() => setStep('questions')}
            disabled={!hwInfo.title || !hwInfo.deadline}
            data-testid="hw-next-btn"
          >
            Next: Add Questions
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
          <button className="stc-publish-btn" onClick={onBack}>Back to Subject</button>
        </div>
      </div>
    );
  }

  return (
    <div className="stc-container" data-testid="homework-question-editor">
      <div className="stc-header">
        <button className="stc-back-btn" onClick={() => setStep('setup')}>Back</button>
        <h2>Add Questions - {hwInfo.title}</h2>
      </div>

      {/* Question tabs */}
      <div className="stc-q-tabs">
        {questions.map((q, i) => (
          <button
            key={i}
            className={`stc-q-tab ${i === activeQ ? 'active' : ''}`}
            onClick={() => setActiveQ(i)}
            data-testid={`hw-q-tab-${i + 1}`}
          >
            Q{i + 1}
          </button>
        ))}
        <button className="stc-q-tab stc-q-add" onClick={addQuestion} data-testid="hw-add-q">+</button>
      </div>

      {/* Question editor */}
      <div className="stc-q-editor">
        <div className="stc-q-header">
          <span>Question {activeQ + 1}</span>
          {questions.length > 1 && (
            <button className="stc-remove-btn" onClick={() => removeQuestion(activeQ)}>Remove</button>
          )}
        </div>

        <div className="stc-field">
          <label>Question Type</label>
          <select
            value={currentQ.question_type}
            onChange={e => handleTypeChange(e.target.value)}
            className="stc-select"
            data-testid="hw-q-type"
          >
            {QUESTION_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
          </select>
        </div>

        <div className="stc-field">
          <label>Question Text</label>
          <textarea
            value={currentQ.question_text}
            onChange={e => updateQuestion('question_text', e.target.value)}
            placeholder="Type the question here..."
            className="stc-textarea"
            rows={3}
            data-testid="hw-q-text"
          />
        </div>

        {/* MCQ Options */}
        {currentQ.question_type === 'mcq' && (
          <div className="stc-options-group">
            <label>Options</label>
            {['a', 'b', 'c', 'd'].map(key => (
              <div key={key} className="stc-option-row">
                <span className="stc-option-label">{key.toUpperCase()}</span>
                <input
                  value={currentQ.objective_data?.options?.[key] || ''}
                  onChange={e => {
                    const obj = { ...(currentQ.objective_data || {}), options: { ...(currentQ.objective_data?.options || {}), [key]: e.target.value } };
                    updateQuestion('objective_data', obj);
                  }}
                  className="stc-input"
                  placeholder={`Option ${key.toUpperCase()}`}
                />
              </div>
            ))}
            <div className="stc-field">
              <label>Correct Answer</label>
              <select
                value={currentQ.objective_data?.correct || ''}
                onChange={e => updateQuestion('objective_data', { ...currentQ.objective_data, correct: e.target.value })}
                className="stc-select"
              >
                <option value="">Select correct option</option>
                {['a', 'b', 'c', 'd'].map(k => <option key={k} value={k}>{k.toUpperCase()}</option>)}
              </select>
            </div>
          </div>
        )}

        {/* True/False */}
        {currentQ.question_type === 'true_false' && (
          <div className="stc-field">
            <label>Correct Answer</label>
            <select
              value={currentQ.objective_data?.correct === true ? 'true' : currentQ.objective_data?.correct === false ? 'false' : ''}
              onChange={e => updateQuestion('objective_data', { correct: e.target.value === 'true' })}
              className="stc-select"
            >
              <option value="">Select</option>
              <option value="true">True</option>
              <option value="false">False</option>
            </select>
          </div>
        )}

        {/* Fill/One word */}
        {(currentQ.question_type === 'fill_blank' || currentQ.question_type === 'one_word') && (
          <div className="stc-field">
            <label>Correct Answer</label>
            <input
              value={currentQ.objective_data?.correct || ''}
              onChange={e => updateQuestion('objective_data', { correct: e.target.value })}
              className="stc-input"
              placeholder="Type the correct answer"
            />
          </div>
        )}

        {/* Match the Following */}
        {currentQ.question_type === 'match_following' && (
          <div className="stc-options-group">
            <label>Match Pairs</label>
            {(currentQ.objective_data?.pairs || []).map((pair, idx) => (
              <div key={idx} className="stc-match-row">
                <input
                  value={pair.left}
                  onChange={e => updatePair(idx, 'left', e.target.value)}
                  className="stc-input"
                  placeholder="Left side"
                />
                <span className="stc-match-arrow">→</span>
                <input
                  value={pair.right}
                  onChange={e => updatePair(idx, 'right', e.target.value)}
                  className="stc-input"
                  placeholder="Right side"
                />
                <button className="stc-remove-btn" onClick={() => removePair(idx)}>×</button>
              </div>
            ))}
            <button className="stc-add-small-btn" onClick={addPair}>+ Add Pair</button>
          </div>
        )}

        {/* Model Answer for subjective */}
        {NEEDS_MODEL_ANSWER.includes(currentQ.question_type) && (
          <div className="stc-field">
            <label>Model Answer</label>
            <textarea
              value={currentQ.model_answer || ''}
              onChange={e => updateQuestion('model_answer', e.target.value)}
              className="stc-textarea"
              rows={4}
              placeholder="The expected answer..."
            />
          </div>
        )}
      </div>

      {/* Status bar */}
      <div className="stc-status-bar">
        <span>{questions.length} question{questions.length > 1 ? 's' : ''}</span>
        {message && <span className="stc-message">{message}</span>}
      </div>

      {/* Publish */}
      <button
        className="stc-publish-btn"
        onClick={handleSaveAndPublish}
        disabled={publishing || questions.some(q => !q.question_text)}
        data-testid="hw-publish-btn"
      >
        {publishing ? 'Publishing...' : 'Save & Publish Homework'}
      </button>
    </div>
  );
}
