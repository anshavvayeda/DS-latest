import React, { useState, useEffect, useCallback } from 'react';
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
const NEEDS_EVAL_POINTS = ['short_answer', 'long_answer'];
const NEEDS_STEPS = ['numerical'];
const OBJECTIVE_TYPES = ['mcq', 'true_false', 'fill_blank', 'one_word', 'match_following'];

const emptyQuestion = () => ({
  question_number: 1,
  question_type: 'mcq',
  question_text: '',
  max_marks: 1,
  model_answer: '',
  objective_data: { options: { a: '', b: '', c: '', d: '' }, correct: '' },
  evaluation_points: [],
  solution_steps: [],
});

export default function StructuredTestCreator({ subjectId, subjectName, standard, schoolName, onBack }) {
  const [step, setStep] = useState('setup'); // setup, questions, preview
  const [testInfo, setTestInfo] = useState({
    title: '',
    duration_minutes: 60,
    submission_deadline: '',
  });
  const [questions, setQuestions] = useState([emptyQuestion()]);
  const [activeQ, setActiveQ] = useState(0);
  const [testId, setTestId] = useState(null);
  const [saving, setSaving] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [message, setMessage] = useState('');

  const currentQ = questions[activeQ] || emptyQuestion();

  const totalMarks = questions.reduce((sum, q) => sum + (parseFloat(q.max_marks) || 0), 0);

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

    if (NEEDS_EVAL_POINTS.includes(newType) && (!currentQ.evaluation_points || currentQ.evaluation_points.length === 0)) {
      defaults.evaluation_points = [{ id: 1, title: '', expected_concept: '', marks: 1 }];
    }
    if (NEEDS_STEPS.includes(newType) && (!currentQ.solution_steps || currentQ.solution_steps.length === 0)) {
      defaults.solution_steps = [{ id: 1, title: '', expected: '', marks: 1 }];
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

  // Evaluation Points
  const addEvalPoint = () => {
    const pts = [...(currentQ.evaluation_points || [])];
    pts.push({ id: pts.length + 1, title: '', expected_concept: '', marks: 1 });
    updateQuestion('evaluation_points', pts);
  };
  const updateEvalPoint = (idx, field, value) => {
    const pts = [...(currentQ.evaluation_points || [])];
    pts[idx] = { ...pts[idx], [field]: value };
    updateQuestion('evaluation_points', pts);
  };
  const removeEvalPoint = (idx) => {
    const pts = (currentQ.evaluation_points || []).filter((_, i) => i !== idx).map((p, i) => ({ ...p, id: i + 1 }));
    updateQuestion('evaluation_points', pts);
  };

  // Solution Steps
  const addStep = () => {
    const steps = [...(currentQ.solution_steps || [])];
    steps.push({ id: steps.length + 1, title: '', expected: '', marks: 1 });
    updateQuestion('solution_steps', steps);
  };
  const updateStep = (idx, field, value) => {
    const steps = [...(currentQ.solution_steps || [])];
    steps[idx] = { ...steps[idx], [field]: value };
    updateQuestion('solution_steps', steps);
  };
  const removeStep = (idx) => {
    const steps = (currentQ.solution_steps || []).filter((_, i) => i !== idx).map((s, i) => ({ ...s, id: i + 1 }));
    updateQuestion('solution_steps', steps);
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

  // Marks tracker for eval points / steps
  const allocatedMarks = (() => {
    if (NEEDS_EVAL_POINTS.includes(currentQ.question_type)) {
      return (currentQ.evaluation_points || []).reduce((s, p) => s + (parseFloat(p.marks) || 0), 0);
    }
    if (NEEDS_STEPS.includes(currentQ.question_type)) {
      return (currentQ.solution_steps || []).reduce((s, p) => s + (parseFloat(p.marks) || 0), 0);
    }
    return parseFloat(currentQ.max_marks) || 0;
  })();

  const handleSave = async () => {
    setSaving(true);
    setMessage('');
    try {
      let tid = testId;
      if (!tid) {
        const resp = await axios.post(`${API}/api/structured-tests`, {
          subject_id: subjectId,
          standard,
          title: testInfo.title,
          school_name: schoolName,
          total_marks: totalMarks,
          duration_minutes: testInfo.duration_minutes,
          submission_deadline: new Date(testInfo.submission_deadline).toISOString(),
        });
        tid = resp.data.id;
        setTestId(tid);
      }
      await axios.post(`${API}/api/structured-tests/${tid}/questions`, { questions });
      setMessage('Draft saved! Test is NOT yet visible to students.');
      setSaving(false);
      return tid;
    } catch (err) {
      setMessage('Error: ' + (err.response?.data?.detail || err.message));
      setSaving(false);
      return null;
    }
  };

  const handlePublish = async () => {
    setPublishing(true);
    setMessage('');
    try {
      // ALWAYS save questions first (whether draft exists or not)
      const tid = await handleSave();
      if (!tid) {
        setMessage('Error: Could not save test before publishing.');
        setPublishing(false);
        return;
      }
      await axios.post(`${API}/api/structured-tests/${tid}/publish`);
      setMessage('Test published! Students can now take it.');
    } catch (err) {
      setMessage('Error: ' + (err.response?.data?.detail || err.message));
    }
    setPublishing(false);
  };

  // ===== RENDER =====

  if (step === 'setup') {
    return (
      <div className="stc-container" data-testid="structured-test-creator">
        <div className="stc-header">
          <button className="stc-back-btn" onClick={onBack} data-testid="stc-back-btn">Back</button>
          <h2>Create AI-Evaluated Test</h2>
        </div>
        <div className="stc-setup-form">
          <div className="stc-field">
            <label>Subject</label>
            <div className="stc-readonly-field">{subjectName}</div>
          </div>
          <div className="stc-field">
            <label>Test Title</label>
            <input
              data-testid="stc-title-input"
              type="text"
              value={testInfo.title}
              onChange={e => setTestInfo({ ...testInfo, title: e.target.value })}
              placeholder="e.g. Math Chapter 3 - Unit Test"
            />
          </div>
          <div className="stc-row">
            <div className="stc-field">
              <label>Duration (minutes)</label>
              <input
                data-testid="stc-duration-input"
                type="number"
                value={testInfo.duration_minutes}
                onChange={e => setTestInfo({ ...testInfo, duration_minutes: parseInt(e.target.value) || 60 })}
              />
            </div>
            <div className="stc-field">
              <label>Submission Deadline</label>
              <input
                data-testid="stc-deadline-input"
                type="datetime-local"
                value={testInfo.submission_deadline}
                onChange={e => setTestInfo({ ...testInfo, submission_deadline: e.target.value })}
              />
            </div>
          </div>
          <button
            className="stc-primary-btn"
            data-testid="stc-proceed-btn"
            disabled={!testInfo.title || !testInfo.submission_deadline}
            onClick={() => setStep('questions')}
          >
            Proceed to Add Questions
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="stc-container" data-testid="structured-test-questions">
      <div className="stc-header">
        <button className="stc-back-btn" onClick={() => setStep('setup')} data-testid="stc-back-setup">Back to Setup</button>
        <h2>{testInfo.title || 'New Test'}</h2>
        <div className="stc-marks-badge" data-testid="stc-total-marks">
          Total: {totalMarks} marks | {questions.length} questions
        </div>
      </div>

      {/* Question Tabs */}
      <div className="stc-q-tabs">
        {questions.map((q, i) => (
          <button
            key={i}
            className={`stc-q-tab ${i === activeQ ? 'active' : ''}`}
            onClick={() => setActiveQ(i)}
            data-testid={`stc-q-tab-${i}`}
          >
            Q{i + 1}
          </button>
        ))}
        <button className="stc-q-tab add" onClick={addQuestion} data-testid="stc-add-question">+</button>
      </div>

      <div className="stc-q-editor">
        {/* STEP 1: Basic Info */}
        <div className="stc-section">
          <h3>Question {activeQ + 1}</h3>
          {questions.length > 1 && (
            <button className="stc-remove-btn" onClick={() => removeQuestion(activeQ)} data-testid="stc-remove-q">Remove</button>
          )}
        </div>

        <div className="stc-field">
          <label>Question Type</label>
          <select
            data-testid="stc-qtype-select"
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
            data-testid="stc-qtext-input"
            value={currentQ.question_text}
            onChange={e => updateQuestion('question_text', e.target.value)}
            placeholder="Enter question text..."
            rows={3}
          />
        </div>

        <div className="stc-field" style={{ maxWidth: 200 }}>
          <label>Maximum Marks</label>
          <input
            data-testid="stc-maxmarks-input"
            type="number"
            min={0.5}
            step={0.5}
            value={currentQ.max_marks}
            onChange={e => updateQuestion('max_marks', parseFloat(e.target.value) || 0)}
          />
        </div>

        {/* STEP 5: Objective Data */}
        {currentQ.question_type === 'mcq' && (
          <div className="stc-section-box">
            <h4>MCQ Options</h4>
            {['a', 'b', 'c', 'd'].map(opt => (
              <div className="stc-field stc-inline" key={opt}>
                <label>Option {opt.toUpperCase()}</label>
                <input
                  data-testid={`stc-option-${opt}`}
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
                data-testid="stc-correct-option"
                value={currentQ.objective_data?.correct || ''}
                onChange={e => updateQuestion('objective_data', { ...currentQ.objective_data, correct: e.target.value })}
              >
                <option value="">Select</option>
                {['a', 'b', 'c', 'd'].map(o => <option key={o} value={o}>{o.toUpperCase()}</option>)}
              </select>
            </div>
          </div>
        )}

        {currentQ.question_type === 'true_false' && (
          <div className="stc-section-box">
            <h4>Correct Answer</h4>
            <div className="stc-radio-group">
              {['true', 'false'].map(v => (
                <label key={v} className="stc-radio">
                  <input
                    type="radio"
                    name={`tf-${activeQ}`}
                    checked={currentQ.objective_data?.correct === v}
                    onChange={() => updateQuestion('objective_data', { correct: v })}
                    data-testid={`stc-tf-${v}`}
                  />
                  {v.charAt(0).toUpperCase() + v.slice(1)}
                </label>
              ))}
            </div>
          </div>
        )}

        {(currentQ.question_type === 'fill_blank' || currentQ.question_type === 'one_word') && (
          <div className="stc-section-box">
            <h4>Correct Answer</h4>
            <input
              data-testid="stc-correct-answer"
              type="text"
              value={currentQ.objective_data?.correct || ''}
              onChange={e => updateQuestion('objective_data', { correct: e.target.value })}
              placeholder={currentQ.question_type === 'one_word' ? 'Single word answer' : 'Fill in the blank answer'}
            />
          </div>
        )}

        {currentQ.question_type === 'match_following' && (
          <div className="stc-section-box">
            <h4>Matching Pairs</h4>
            {(currentQ.objective_data?.pairs || []).map((pair, idx) => (
              <div className="stc-pair-row" key={idx}>
                <input
                  data-testid={`stc-match-left-${idx}`}
                  type="text"
                  value={pair.left}
                  onChange={e => updatePair(idx, 'left', e.target.value)}
                  placeholder="Left side"
                />
                <span className="stc-arrow">→</span>
                <input
                  data-testid={`stc-match-right-${idx}`}
                  type="text"
                  value={pair.right}
                  onChange={e => updatePair(idx, 'right', e.target.value)}
                  placeholder="Right side"
                />
                <button className="stc-remove-sm" onClick={() => removePair(idx)}>×</button>
              </div>
            ))}
            <button className="stc-add-btn" onClick={addPair} data-testid="stc-add-pair">+ Add Pair</button>
          </div>
        )}

        {/* STEP 2: Model Answer */}
        {NEEDS_MODEL_ANSWER.includes(currentQ.question_type) && (
          <div className="stc-section-box">
            <h4>Model Answer</h4>
            <textarea
              data-testid="stc-model-answer"
              value={currentQ.model_answer || ''}
              onChange={e => updateQuestion('model_answer', e.target.value)}
              placeholder="Enter the ideal answer that represents the expected response..."
              rows={4}
            />
          </div>
        )}

        {/* STEP 3: Evaluation Points */}
        {NEEDS_EVAL_POINTS.includes(currentQ.question_type) && (
          <div className="stc-section-box">
            <h4>Evaluation Points</h4>
            <p className="stc-hint">Define how marks should be awarded. AI will check each point independently.</p>
            {(currentQ.evaluation_points || []).map((ep, idx) => (
              <div className="stc-eval-point" key={idx}>
                <div className="stc-ep-header">
                  <span>Point {idx + 1}</span>
                  <button className="stc-remove-sm" onClick={() => removeEvalPoint(idx)}>×</button>
                </div>
                <div className="stc-field">
                  <label>Title</label>
                  <input
                    data-testid={`stc-ep-title-${idx}`}
                    type="text"
                    value={ep.title}
                    onChange={e => updateEvalPoint(idx, 'title', e.target.value)}
                    placeholder="e.g. Definition of concept"
                  />
                </div>
                <div className="stc-field">
                  <label>Expected Concept</label>
                  <textarea
                    data-testid={`stc-ep-concept-${idx}`}
                    value={ep.expected_concept}
                    onChange={e => updateEvalPoint(idx, 'expected_concept', e.target.value)}
                    placeholder="What the student should mention..."
                    rows={2}
                  />
                </div>
                <div className="stc-field" style={{ maxWidth: 120 }}>
                  <label>Marks</label>
                  <input
                    data-testid={`stc-ep-marks-${idx}`}
                    type="number"
                    min={0.5}
                    step={0.5}
                    value={ep.marks}
                    onChange={e => updateEvalPoint(idx, 'marks', parseFloat(e.target.value) || 0)}
                  />
                </div>
              </div>
            ))}
            <button className="stc-add-btn" onClick={addEvalPoint} data-testid="stc-add-eval-point">+ Add Evaluation Point</button>
            <div className={`stc-marks-tracker ${allocatedMarks !== parseFloat(currentQ.max_marks) ? 'mismatch' : 'match'}`}>
              Allocated: {allocatedMarks} / {currentQ.max_marks} marks
            </div>
          </div>
        )}

        {/* STEP 4: Numerical Steps */}
        {NEEDS_STEPS.includes(currentQ.question_type) && (
          <div className="stc-section-box">
            <h4>Solution Steps</h4>
            <p className="stc-hint">Define each step of the solution. AI will check each step independently.</p>
            {(currentQ.solution_steps || []).map((s, idx) => (
              <div className="stc-eval-point" key={idx}>
                <div className="stc-ep-header">
                  <span>Step {idx + 1}</span>
                  <button className="stc-remove-sm" onClick={() => removeStep(idx)}>×</button>
                </div>
                <div className="stc-field">
                  <label>Step Title</label>
                  <input
                    data-testid={`stc-step-title-${idx}`}
                    type="text"
                    value={s.title}
                    onChange={e => updateStep(idx, 'title', e.target.value)}
                    placeholder="e.g. Write formula"
                  />
                </div>
                <div className="stc-field">
                  <label>Expected Expression</label>
                  <input
                    data-testid={`stc-step-expected-${idx}`}
                    type="text"
                    value={s.expected}
                    onChange={e => updateStep(idx, 'expected', e.target.value)}
                    placeholder="e.g. Area = pi * r^2"
                  />
                </div>
                <div className="stc-field" style={{ maxWidth: 120 }}>
                  <label>Marks</label>
                  <input
                    data-testid={`stc-step-marks-${idx}`}
                    type="number"
                    min={0.5}
                    step={0.5}
                    value={s.marks}
                    onChange={e => updateStep(idx, 'marks', parseFloat(e.target.value) || 0)}
                  />
                </div>
              </div>
            ))}
            <button className="stc-add-btn" onClick={addStep} data-testid="stc-add-step">+ Add Step</button>
            <div className={`stc-marks-tracker ${allocatedMarks !== parseFloat(currentQ.max_marks) ? 'mismatch' : 'match'}`}>
              Allocated: {allocatedMarks} / {currentQ.max_marks} marks
            </div>
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="stc-actions">
        <button
          className="stc-save-btn"
          onClick={handleSave}
          disabled={saving}
          data-testid="stc-save-btn"
        >
          {saving ? 'Saving...' : 'Save Draft'}
        </button>
        <button
          className="stc-publish-btn"
          onClick={handlePublish}
          disabled={publishing || questions.some(q => !q.question_text)}
          data-testid="stc-publish-btn"
        >
          {publishing ? 'Publishing...' : 'Save & Publish'}
        </button>
      </div>

      {message && (
        <div className={`stc-message ${message.startsWith('Error') ? 'error' : 'success'}`} data-testid="stc-message">
          {message}
        </div>
      )}
    </div>
  );
}
