import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './StudentPerformanceDashboard.css';

const API = process.env.REACT_APP_BACKEND_URL
  ? `${process.env.REACT_APP_BACKEND_URL}/api`
  : '/api';

const TYPE_LABELS = {
  mcq: 'MCQ',
  true_false: 'True/False',
  fill_blank: 'Fill Blank',
  one_word: 'One Word',
  match_following: 'Match',
  short_answer: 'Short Answer',
  long_answer: 'Long Answer',
  numerical: 'Numerical',
};

export default function StudentPerformanceDashboard({ subjectId, subjectName, onClose }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchPerformance = async () => {
      try {
        const url = subjectId
          ? `${API}/structured-tests/student/performance?subject_id=${subjectId}`
          : `${API}/structured-tests/student/performance`;
        const res = await axios.get(url, { withCredentials: true });
        setData(res.data);
      } catch (err) {
        setError(err.response?.data?.detail || 'Failed to load performance data');
      } finally {
        setLoading(false);
      }
    };
    fetchPerformance();
  }, [subjectId]);

  if (loading) {
    return (
      <div className="spd-container" data-testid="spd-loading">
        <div className="spd-loading"><div className="spd-spinner" /><p>Loading performance data...</p></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="spd-container" data-testid="spd-error">
        <div className="spd-header">
          <button className="spd-back" onClick={onClose} data-testid="spd-back">Back</button>
          <h2>{subjectName ? `${subjectName} — Performance` : 'Performance Dashboard'}</h2>
        </div>
        <div className="spd-error">{error}</div>
      </div>
    );
  }

  if (!data || data.total_tests === 0) {
    return (
      <div className="spd-container" data-testid="spd-empty">
        <div className="spd-header">
          <button className="spd-back" onClick={onClose} data-testid="spd-back">Back</button>
          <h2>{subjectName ? `${subjectName} — Performance` : 'Performance Dashboard'}</h2>
        </div>
        <div className="spd-empty-state">
          <div className="spd-empty-icon">&#9472;</div>
          <h3>No test results yet</h3>
          <p>Complete AI-evaluated tests to see your performance trends here.</p>
        </div>
      </div>
    );
  }

  const trendColor = data.recent_improvement > 0 ? '#22c55e' : data.recent_improvement < 0 ? '#ef4444' : '#94a3b8';
  const trendIcon = data.recent_improvement > 0 ? '\u25B2' : data.recent_improvement < 0 ? '\u25BC' : '\u2501';

  // Find max score for chart scaling
  const maxPct = 100;

  return (
    <div className="spd-container" data-testid="spd-dashboard">
      {/* Summary Cards */}
      <div className="spd-summary" data-testid="spd-summary">
        <div className="spd-stat-card">
          <div className="spd-stat-value" data-testid="spd-total-tests">{data.total_tests}</div>
          <div className="spd-stat-label">Tests Taken</div>
        </div>
        <div className="spd-stat-card accent">
          <div className="spd-stat-value" data-testid="spd-avg-pct">{data.average_percentage}%</div>
          <div className="spd-stat-label">Average Score</div>
        </div>
        <div className="spd-stat-card success">
          <div className="spd-stat-value" data-testid="spd-best-pct">{data.best_percentage}%</div>
          <div className="spd-stat-label">Best Score</div>
        </div>
        <div className="spd-stat-card" style={{ borderTopColor: trendColor }}>
          <div className="spd-stat-value" style={{ color: trendColor }} data-testid="spd-trend">
            {trendIcon} {data.recent_improvement !== null ? `${Math.abs(data.recent_improvement)}%` : 'N/A'}
          </div>
          <div className="spd-stat-label">Recent Trend</div>
        </div>
      </div>

      {/* Score Trend Chart */}
      {data.tests_timeline.length >= 1 && (
        <div className="spd-chart-card" data-testid="spd-trend-chart">
          <h3>Score Trend</h3>
          <div className="spd-chart">
            <div className="spd-chart-y-axis">
              <span>100%</span>
              <span>75%</span>
              <span>50%</span>
              <span>25%</span>
              <span>0%</span>
            </div>
            <div className="spd-chart-area">
              {/* Grid lines */}
              <div className="spd-grid-line" style={{ bottom: '75%' }} />
              <div className="spd-grid-line" style={{ bottom: '50%' }} />
              <div className="spd-grid-line" style={{ bottom: '25%' }} />

              {/* Bars */}
              <div className="spd-bars">
                {data.tests_timeline.map((t, i) => {
                  const h = Math.max(2, (t.percentage / maxPct) * 100);
                  const barColor = t.percentage >= 80 ? '#22c55e' : t.percentage >= 60 ? '#eab308' : t.percentage >= 40 ? '#f97316' : '#ef4444';
                  return (
                    <div key={i} className="spd-bar-group" title={`${t.test_title}\n${t.score}/${t.max_score} (${t.percentage}%)`}>
                      <div className="spd-bar" style={{ height: `${h}%`, background: barColor }} data-testid={`spd-bar-${i}`}>
                        <span className="spd-bar-label">{t.percentage}%</span>
                      </div>
                      <div className="spd-bar-date">{new Date(t.date).toLocaleDateString('en-IN', { day: '2-digit', month: 'short' })}</div>
                    </div>
                  );
                })}
              </div>

              {/* Trend line overlay */}
              <svg className="spd-trend-line" viewBox={`0 0 ${data.tests_timeline.length * 60} 200`} preserveAspectRatio="none">
                <polyline
                  fill="none"
                  stroke="rgba(102,126,234,0.8)"
                  strokeWidth="3"
                  points={data.tests_timeline.map((t, i) => {
                    const x = i * 60 + 30;
                    const y = 200 - (t.percentage / maxPct) * 200;
                    return `${x},${y}`;
                  }).join(' ')}
                />
                {data.tests_timeline.map((t, i) => {
                  const x = i * 60 + 30;
                  const y = 200 - (t.percentage / maxPct) * 200;
                  return <circle key={i} cx={x} cy={y} r="5" fill="#667eea" stroke="white" strokeWidth="2" />;
                })}
              </svg>
            </div>
          </div>
        </div>
      )}

      {/* Subject Breakdown - only show when NOT filtered by subject */}
      {!subjectId && data.subject_breakdown.length > 0 && (
        <div className="spd-section" data-testid="spd-subjects">
          <h3>Subject-wise Performance</h3>
          <div className="spd-subject-cards">
            {data.subject_breakdown.map((s, i) => (
              <div key={i} className="spd-subject-card" data-testid={`spd-subject-${i}`}>
                <div className="spd-subject-name">{s.subject}</div>
                <div className="spd-subject-stats">
                  <div className="spd-subject-bar-bg">
                    <div
                      className="spd-subject-bar-fill"
                      style={{ width: `${s.average_percentage}%`, background: s.average_percentage >= 70 ? '#22c55e' : s.average_percentage >= 50 ? '#eab308' : '#ef4444' }}
                    />
                  </div>
                  <span className="spd-subject-pct">{s.average_percentage}%</span>
                </div>
                <div className="spd-subject-meta">
                  <span>{s.tests_taken} test{s.tests_taken > 1 ? 's' : ''}</span>
                  <span>Best: {s.best_percentage}%</span>
                  <span>Latest: {s.latest_percentage}%</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Question Type Analysis */}
      {data.question_type_stats.length > 0 && (
        <div className="spd-section" data-testid="spd-question-types">
          <h3>Strengths & Weaknesses by Question Type</h3>
          <div className="spd-qt-list">
            {data.question_type_stats.map((qt, i) => {
              const isStrength = qt.accuracy_percentage >= 70;
              const isWeak = qt.accuracy_percentage < 40;
              return (
                <div key={i} className={`spd-qt-row ${isStrength ? 'strength' : isWeak ? 'weakness' : ''}`} data-testid={`spd-qt-${qt.type}`}>
                  <div className="spd-qt-left">
                    <span className="spd-qt-tag">{isStrength ? '\u2713' : isWeak ? '!' : '\u2022'}</span>
                    <span className="spd-qt-name">{TYPE_LABELS[qt.type] || qt.type}</span>
                    <span className="spd-qt-count">{qt.questions_attempted} Q</span>
                  </div>
                  <div className="spd-qt-right">
                    <div className="spd-qt-bar-bg">
                      <div
                        className="spd-qt-bar-fill"
                        style={{ width: `${qt.accuracy_percentage}%`, background: isStrength ? '#22c55e' : isWeak ? '#ef4444' : '#eab308' }}
                      />
                    </div>
                    <span className="spd-qt-pct">{qt.accuracy_percentage}%</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Recent Tests Timeline */}
      {data.tests_timeline.length > 0 && (
        <div className="spd-section" data-testid="spd-timeline">
          <h3>Recent Tests</h3>
          <div className="spd-timeline-list">
            {[...data.tests_timeline].reverse().map((t, i) => {
              const grade = t.percentage >= 90 ? 'A+' : t.percentage >= 80 ? 'A' : t.percentage >= 70 ? 'B' : t.percentage >= 60 ? 'C' : t.percentage >= 50 ? 'D' : 'F';
              const gradeColor = t.percentage >= 80 ? '#22c55e' : t.percentage >= 60 ? '#eab308' : '#ef4444';
              return (
                <div key={i} className="spd-timeline-item" data-testid={`spd-timeline-${i}`}>
                  <div className="spd-tl-grade" style={{ background: gradeColor }}>{grade}</div>
                  <div className="spd-tl-info">
                    <div className="spd-tl-title">{t.test_title}</div>
                    <div className="spd-tl-meta">
                      <span>{t.subject}</span>
                      <span>{new Date(t.date).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })}</span>
                    </div>
                  </div>
                  <div className="spd-tl-score">
                    <div className="spd-tl-marks">{t.score}/{t.max_score}</div>
                    <div className="spd-tl-pct">{t.percentage}%</div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
