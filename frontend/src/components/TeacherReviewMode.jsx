import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './TeacherReviewMode.css';

const API = process.env.REACT_APP_BACKEND_URL ? `${process.env.REACT_APP_BACKEND_URL}/api` : '/api';

function TeacherReviewMode({ testId, testTitle, onClose }) {
  const [submissions, setSubmissions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedSubmission, setSelectedSubmission] = useState(null);
  const [detailedResults, setDetailedResults] = useState(null);
  const [loadingDetails, setLoadingDetails] = useState(false);
  const [overrides, setOverrides] = useState({});
  const [saving, setSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState('');

  useEffect(() => {
    loadSubmissions();
  }, [testId]);

  const loadSubmissions = async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/structured-tests/${testId}/submissions`, { withCredentials: true });
      setSubmissions(res.data || []);
    } catch (err) {
      console.error('Failed to load submissions', err);
    } finally {
      setLoading(false);
    }
  };

  const openSubmission = async (sub) => {
    setSelectedSubmission(sub);
    setLoadingDetails(true);
    setOverrides({});
    setSaveMessage('');
    try {
      const res = await axios.get(`${API}/structured-tests/${testId}/results/${sub.student_id}`, { withCredentials: true });
      setDetailedResults(res.data);
    } catch (err) {
      console.error('Failed to load results', err);
      setDetailedResults(null);
    } finally {
      setLoadingDetails(false);
    }
  };

  const handleOverride = (qNum, field, value) => {
    setOverrides(prev => ({
      ...prev,
      [qNum]: { ...prev[qNum], question_number: qNum, [field]: value }
    }));
  };

  const saveReview = async () => {
    const overrideList = Object.values(overrides).filter(o => o.marks !== undefined);
    if (overrideList.length === 0) {
      setSaveMessage('No changes to save');
      return;
    }
    setSaving(true);
    setSaveMessage('');
    try {
      const res = await axios.post(
        `${API}/structured-tests/${testId}/review/${selectedSubmission.student_id}`,
        { overrides: overrideList },
        { withCredentials: true }
      );
      setSaveMessage(`Saved! Final score: ${res.data.final_score}/${res.data.max_score} (${res.data.percentage}%)`);
      await loadSubmissions();
      // Refresh detailed view
      const updated = await axios.get(`${API}/structured-tests/${testId}/results/${selectedSubmission.student_id}`, { withCredentials: true });
      setDetailedResults(updated.data);
      setOverrides({});
    } catch (err) {
      setSaveMessage('Failed to save review');
    } finally {
      setSaving(false);
    }
  };

  const getScoreColor = (pct) => {
    if (pct >= 80) return '#10b981';
    if (pct >= 60) return '#f59e0b';
    return '#ef4444';
  };

  // Submissions list view
  if (!selectedSubmission) {
    return (
      <div className="trm-container" data-testid="teacher-review-mode">
        <div className="trm-header">
          <button className="trm-back-btn" onClick={onClose} data-testid="trm-back-btn">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M19 12H5M12 19l-7-7 7-7"/></svg>
            Back
          </button>
          <div className="trm-header-info">
            <h2 data-testid="trm-title">Review: {testTitle}</h2>
            <span className="trm-badge">{submissions.filter(s => s.submitted).length} submissions</span>
          </div>
        </div>

        {loading ? (
          <div className="trm-loading">Loading submissions...</div>
        ) : submissions.length === 0 ? (
          <div className="trm-empty">No submissions yet for this test.</div>
        ) : (
          <div className="trm-submissions-list" data-testid="trm-submissions-list">
            <div className="trm-list-header">
              <span>Student</span>
              <span>Score</span>
              <span>Status</span>
              <span>Submitted</span>
              <span></span>
            </div>
            {submissions.filter(s => s.submitted).map(sub => {
              const pct = sub.max_score > 0 ? ((sub.total_score || 0) / sub.max_score * 100) : 0;
              return (
                <div key={sub.id} className="trm-submission-row" data-testid={`trm-submission-${sub.roll_no}`}>
                  <span className="trm-student-name">
                    <span className="trm-roll-badge">{sub.roll_no}</span>
                    {sub.student_name && <span className="trm-name-text">{sub.student_name}</span>}
                  </span>
                  <span className="trm-score" style={{ color: getScoreColor(pct) }}>
                    {sub.total_score ?? '—'}/{sub.max_score} <small>({pct.toFixed(1)}%)</small>
                  </span>
                  <span>
                    {sub.evaluation_status === 'completed' ? (
                      sub.teacher_reviewed ? (
                        <span className="trm-status trm-status-reviewed">Reviewed</span>
                      ) : (
                        <span className="trm-status trm-status-pending">Needs Review</span>
                      )
                    ) : (
                      <span className="trm-status trm-status-evaluating">{sub.evaluation_status}</span>
                    )}
                  </span>
                  <span className="trm-date">
                    {sub.submitted_at ? new Date(sub.submitted_at).toLocaleString() : '—'}
                  </span>
                  <span>
                    {sub.evaluation_status === 'completed' && (
                      <button
                        className="trm-review-btn"
                        onClick={() => openSubmission(sub)}
                        data-testid={`trm-review-btn-${sub.roll_no}`}
                      >
                        {sub.teacher_reviewed ? 'View / Edit' : 'Review'}
                      </button>
                    )}
                  </span>
                </div>
              );
            })}
          </div>
        )}
      </div>
    );
  }

  // Detailed review view
  return (
    <div className="trm-container" data-testid="trm-detail-view">
      <div className="trm-header">
        <button className="trm-back-btn" onClick={() => { setSelectedSubmission(null); setDetailedResults(null); setOverrides({}); setSaveMessage(''); }} data-testid="trm-detail-back">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M19 12H5M12 19l-7-7 7-7"/></svg>
          Back to Submissions
        </button>
        <div className="trm-header-info">
          <h2>Student: {selectedSubmission.student_name || selectedSubmission.roll_no}</h2>
          {detailedResults && (
            <span className="trm-score-summary" style={{ color: getScoreColor(detailedResults.percentage || 0) }}>
              {detailedResults.total_score}/{detailedResults.max_score} ({detailedResults.percentage?.toFixed(1)}%)
              {detailedResults.teacher_reviewed && <span className="trm-reviewed-tag">Teacher Reviewed</span>}
            </span>
          )}
        </div>
      </div>

      {loadingDetails ? (
        <div className="trm-loading">Loading evaluation details...</div>
      ) : !detailedResults ? (
        <div className="trm-empty">Failed to load evaluation results.</div>
      ) : detailedResults.retained_only ? (
        <div className="trm-retained-summary" data-testid="trm-retained-summary">
          <div className="trm-retained-card">
            <div className="trm-retained-header">Detailed Results Expired</div>
            <p className="trm-retained-note">
              Detailed per-question evaluation has been archived per the 2-month retention policy.
              The following summary is retained for annual/half-yearly feedback.
            </p>
            <div className="trm-retained-stats">
              <div className="trm-retained-stat">
                <span className="trm-retained-label">Score</span>
                <span className="trm-retained-value" style={{ color: getScoreColor(detailedResults.percentage || 0) }}>
                  {detailedResults.total_score}/{detailedResults.max_score} ({detailedResults.percentage?.toFixed(1)}%)
                </span>
              </div>
              {detailedResults.improvement_summary && (
                <div className="trm-retained-stat">
                  <span className="trm-retained-label">Areas for Improvement</span>
                  <span className="trm-retained-value trm-retained-improve">{detailedResults.improvement_summary}</span>
                </div>
              )}
            </div>
          </div>
        </div>
      ) : !detailedResults.results_available ? (
        <div className="trm-empty">Detailed evaluation results are not available (may have expired).</div>
      ) : (
        <>
          <div className="trm-questions-list">
            {detailedResults.detailed_results.map((r) => {
              const override = overrides[r.question_number];
              const currentMarks = override?.marks !== undefined ? override.marks : r.marks_awarded;
              return (
                <div key={r.question_number} className="trm-question-card" data-testid={`trm-question-${r.question_number}`}>
                  <div className="trm-q-header">
                    <span className="trm-q-num">Q{r.question_number}</span>
                    <span className="trm-q-type">{r.question_type}</span>
                    <span className="trm-q-marks" style={{ color: getScoreColor((currentMarks / r.max_marks) * 100) }}>
                      {currentMarks}/{r.max_marks}
                    </span>
                  </div>

                  <div className="trm-q-text">{r.question_text}</div>

                  <div className="trm-q-answer-section">
                    <div className="trm-q-label">Student Answer</div>
                    <div className="trm-q-answer">{r.student_answer || <em className="trm-no-answer">No answer provided</em>}</div>
                  </div>

                  {r.feedback && typeof r.feedback === 'object' && (
                    <div className="trm-q-feedback">
                      <div className="trm-q-label">AI Feedback</div>
                      {r.feedback.overall_feedback && <p className="trm-feedback-text">{r.feedback.overall_feedback}</p>}
                      {r.feedback.improvement_suggestions && <p className="trm-feedback-improve">Improve: {r.feedback.improvement_suggestions}</p>}
                    </div>
                  )}

                  {r.teacher_comment && !override?.comment && (
                    <div className="trm-q-teacher-note">
                      <div className="trm-q-label">Previous Teacher Comment</div>
                      <p>{r.teacher_comment}</p>
                    </div>
                  )}

                  <div className="trm-override-section">
                    <div className="trm-q-label">Override Marks</div>
                    <div className="trm-override-row">
                      <input
                        type="number"
                        min="0"
                        max={r.max_marks}
                        step="0.5"
                        placeholder={`${r.marks_awarded}`}
                        value={override?.marks ?? ''}
                        onChange={(e) => handleOverride(r.question_number, 'marks', parseFloat(e.target.value) || 0)}
                        className="trm-marks-input"
                        data-testid={`trm-override-marks-${r.question_number}`}
                      />
                      <span className="trm-max-label">/ {r.max_marks}</span>
                      <input
                        type="text"
                        placeholder="Add a comment (optional)"
                        value={override?.comment ?? ''}
                        onChange={(e) => handleOverride(r.question_number, 'comment', e.target.value)}
                        className="trm-comment-input"
                        data-testid={`trm-override-comment-${r.question_number}`}
                      />
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          <div className="trm-save-bar" data-testid="trm-save-bar">
            {saveMessage && <span className="trm-save-msg">{saveMessage}</span>}
            <button
              className="trm-save-btn"
              onClick={saveReview}
              disabled={saving || Object.keys(overrides).length === 0}
              data-testid="trm-save-btn"
            >
              {saving ? 'Saving...' : 'Save Review'}
            </button>
          </div>
        </>
      )}
    </div>
  );
}

export default TeacherReviewMode;
