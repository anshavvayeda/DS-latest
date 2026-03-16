import React, { useState, useEffect } from 'react';
import axios from 'axios';

const API = process.env.REACT_APP_BACKEND_URL ? `${process.env.REACT_APP_BACKEND_URL}/api` : '/api';

// Color coding for performance classification (dark theme colors)
const CLASSIFICATION_COLORS = {
  strong: { bg: '#065f46', border: '#10b981', text: '#6ee7b7', label: 'Strong' },
  average: { bg: '#78350f', border: '#f59e0b', text: '#fbbf24', label: 'Average' },
  weak: { bg: '#7f1d1d', border: '#ef4444', text: '#fca5a5', label: 'Needs Improvement' },
  no_data: { bg: '#374151', border: '#6b7280', text: '#9ca3af', label: 'No Data' }
};

// Simple bar chart using HTML/CSS (reliable rendering, no SVG quirks)
const PerformanceChart = ({ data, subjectName }) => {
  if (!data || data.length === 0) {
    return (
      <div className="chart-empty-dark">
        <p>No test data available yet</p>
      </div>
    );
  }

  const getBarColor = (pct) => {
    if (pct >= 80) return '#10b981';
    if (pct >= 60) return '#f59e0b';
    return '#ef4444';
  };

  return (
    <div className="chart-section-dark">
      <h5 className="chart-title-dark">Test Score History</h5>
      <div className="perf-bar-chart" data-testid={`perf-chart-${subjectName}`}>
        <div className="perf-bar-yaxis">
          <span>100%</span>
          <span>50%</span>
          <span>0%</span>
        </div>
        <div className="perf-bar-area">
          <div className="perf-bar-grid" style={{ bottom: '50%' }} />
          {data.map((d, i) => (
            <div key={i} className="perf-bar-col" title={`${d.test_name}: ${d.percentage}%`}>
              <div className="perf-bar-value" style={{ color: getBarColor(d.percentage) }}>{d.percentage}%</div>
              <div className="perf-bar-track">
                <div
                  className="perf-bar-fill"
                  style={{
                    height: `${Math.max(d.percentage, 3)}%`,
                    background: `linear-gradient(to top, ${getBarColor(d.percentage)}cc, ${getBarColor(d.percentage)})`,
                  }}
                />
                <div
                  className="perf-bar-dot"
                  style={{
                    bottom: `calc(${Math.max(d.percentage, 3)}% - 6px)`,
                    background: getBarColor(d.percentage),
                    boxShadow: `0 0 10px ${getBarColor(d.percentage)}99`,
                  }}
                />
              </div>
              <div className="perf-bar-date">{d.date?.split('T')[0]?.slice(5) || `T${i + 1}`}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

// Colorful progress bar component for dark theme
const ColorfulProgressBar = ({ percentage, label, sublabel, type = 'default' }) => {
  const getGradient = () => {
    if (type === 'syllabus') {
      if (percentage >= 75) return 'linear-gradient(90deg, #10b981 0%, #34d399 100%)';
      if (percentage >= 50) return 'linear-gradient(90deg, #3b82f6 0%, #60a5fa 100%)';
      if (percentage >= 25) return 'linear-gradient(90deg, #f59e0b 0%, #fbbf24 100%)';
      return 'linear-gradient(90deg, #ef4444 0%, #f87171 100%)';
    }
    if (type === 'homework') {
      if (percentage >= 80) return 'linear-gradient(90deg, #10b981 0%, #34d399 100%)';
      if (percentage >= 60) return 'linear-gradient(90deg, #3b82f6 0%, #60a5fa 100%)';
      if (percentage >= 40) return 'linear-gradient(90deg, #f59e0b 0%, #fbbf24 100%)';
      return 'linear-gradient(90deg, #ef4444 0%, #f87171 100%)';
    }
    return 'linear-gradient(90deg, #8b5cf6 0%, #a78bfa 100%)';
  };

  return (
    <div className="colorful-progress-container">
      <div className="colorful-progress-header">
        <span className="colorful-progress-label">{label}</span>
        <span className="colorful-progress-percentage">{percentage}%</span>
      </div>
      <div className="colorful-progress-track">
        <div 
          className="colorful-progress-fill" 
          style={{ 
            width: `${Math.min(percentage, 100)}%`, 
            background: getGradient()
          }}
        />
      </div>
      {sublabel && <span className="colorful-progress-sublabel">{sublabel}</span>}
    </div>
  );
};

// Subject card component with dark theme
const SubjectCard = ({ subject }) => {
  const classification = CLASSIFICATION_COLORS[subject.classification] || CLASSIFICATION_COLORS.no_data;
  
  return (
    <div 
      className="subject-card-dark"
      style={{ 
        backgroundColor: '#1f2937',
        borderColor: classification.border 
      }}
      data-testid={`subject-card-${subject.subject_name}`}
    >
      <div className="subject-header-dark">
        <h4 className="subject-title-dark">{subject.subject_name}</h4>
        <span 
          className="classification-badge-dark"
          style={{ 
            backgroundColor: classification.border, 
            color: '#000' 
          }}
        >
          {classification.label}
        </span>
      </div>
      
      {/* Average Score */}
      <div className="avg-score-dark">
        <span className="avg-label-dark">Average Score:</span>
        <span className="avg-value-dark" style={{ color: classification.text }}>
          {subject.average_score > 0 ? `${subject.average_score}%` : 'N/A'}
        </span>
      </div>
      
      {/* Performance Chart */}
      <PerformanceChart data={subject.test_performance} subjectName={subject.subject_name} />
      
      {/* Syllabus Progress */}
      <div className="section-block-dark">
        <h5 className="section-title-dark">📚 Syllabus Progress</h5>
        <ColorfulProgressBar
          percentage={subject.syllabus_progress.progress_percentage}
          label={`${subject.syllabus_progress.attempted_practice_tests} / ${subject.syllabus_progress.total_practice_tests} practice tests`}
          sublabel={subject.syllabus_progress.chapter_count > 0 
            ? `Based on ${subject.syllabus_progress.chapter_count} chapters`
            : 'No chapters uploaded yet'}
          type="syllabus"
        />
      </div>
      
      {/* Homework Completion */}
      {subject.homework_stats.total_assigned > 0 && (
        <div className="section-block-dark">
          <h5 className="section-title-dark">📝 Homework Completion</h5>
          <ColorfulProgressBar
            percentage={subject.homework_stats.completion_percentage}
            label={`${subject.homework_stats.submitted} / ${subject.homework_stats.total_assigned} submitted`}
            type="homework"
          />
        </div>
      )}
    </div>
  );
};

// Main Parent Dashboard Component
const ParentDashboard = ({ isExpanded, onToggle, isFullPage = false, onClose }) => {
  const [dashboardData, setDashboardData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if ((isFullPage || isExpanded) && !dashboardData) {
      fetchDashboardData();
    }
  }, [isFullPage, isExpanded]);

  const fetchDashboardData = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await axios.get(`${API}/student/parent-dashboard`, { withCredentials: true });
      setDashboardData(response.data);
    } catch (err) {
      console.error('Error fetching parent dashboard:', err);
      setError(err.response?.data?.detail || 'Failed to load dashboard');
    } finally {
      setLoading(false);
    }
  };

  // Full-page dark theme version
  if (isFullPage) {
    return (
      <div className="parent-dashboard-fullpage" data-testid="parent-dashboard-fullpage">
        <div className="fullpage-header">
          <button className="back-btn-dark" onClick={onClose}>
            ← Back
          </button>
          <h2 className="fullpage-title">Parent Academic Dashboard</h2>
        </div>

        {loading && (
          <div className="dashboard-loading-dark">
            <div className="loading-spinner-dark"></div>
            <p>Loading academic overview...</p>
          </div>
        )}
        
        {error && (
          <div className="dashboard-error-dark">
            <p>{error}</p>
            <button onClick={fetchDashboardData} className="retry-btn-dark">Try Again</button>
          </div>
        )}
        
        {dashboardData && !loading && (
          <div className="dashboard-content-dark">
            {/* Student Info Header */}
            <div className="dashboard-header-dark">
              <div className="student-info-card">
                <h3>{dashboardData.student_name}</h3>
                <p>Class {dashboardData.standard} | Roll No: {dashboardData.roll_no}</p>
              </div>
            </div>
            
            {/* Overall Stats Summary */}
            <div className="overall-stats-dark">
              <div className="stat-box-dark blue">
                <span className="stat-value-dark">{dashboardData.overall_stats.total_tests_attempted}</span>
                <span className="stat-label-dark">Tests Taken</span>
              </div>
              <div className="stat-box-dark green">
                <span className="stat-value-dark">{dashboardData.overall_stats.overall_average_score}%</span>
                <span className="stat-label-dark">Avg Score</span>
              </div>
              <div className="stat-box-dark purple">
                <span className="stat-value-dark">{dashboardData.overall_stats.overall_homework_completion}%</span>
                <span className="stat-label-dark">HW Done</span>
              </div>
              <div className="stat-box-dark red">
                <span className="stat-value-dark">{dashboardData.overall_stats.total_missed_homework}</span>
                <span className="stat-label-dark">Pending HW</span>
              </div>
            </div>
            
            {/* Legend */}
            <div className="classification-legend-dark">
              <span className="legend-title-dark">Performance Legend:</span>
              <span className="legend-item-dark strong">
                ● Strong (≥80%)
              </span>
              <span className="legend-item-dark average">
                ● Average (60-79%)
              </span>
              <span className="legend-item-dark weak">
                ● Needs Improvement (&lt;60%)
              </span>
            </div>
            
            {/* Subject-wise Performance */}
            <div className="subjects-performance-dark">
              <h4 className="section-heading-dark">Subject-wise Performance</h4>
              <div className="subjects-grid-dark">
                {dashboardData.subjects.map(subject => (
                  <SubjectCard key={subject.subject_id} subject={subject} />
                ))}
              </div>
            </div>
            
            {/* Missed Homework Alert */}
            {dashboardData.all_missed_homework.length > 0 && (
              <div className="missed-homework-section-dark" data-testid="missed-homework-section">
                <h4 className="section-heading-dark">⚠️ Pending Homework</h4>
                <ul className="missed-homework-list-dark">
                  {dashboardData.all_missed_homework.map((hw, idx) => (
                    <li key={idx} className="missed-homework-item-dark">
                      <span className="hw-subject-dark">{hw.subject}</span>
                      <span className="hw-title-dark">{hw.homework_title}</span>
                      <span className="hw-date-dark">{hw.due_date?.split('T')[0] || 'N/A'}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>
    );
  }

  // Original inline version (kept for compatibility)
  return (
    <div className="parent-dashboard-wrapper" data-testid="parent-dashboard">
      <button 
        className="parent-dashboard-toggle"
        onClick={onToggle}
        data-testid="parent-dashboard-toggle"
      >
        <span className="toggle-icon">{isExpanded ? '▼' : '▶'}</span>
        <span className="toggle-title">Parent Academic Overview</span>
      </button>
      
      {isExpanded && (
        <div className="parent-dashboard-content">
          {loading && (
            <div className="dashboard-loading">
              <div className="loading-spinner"></div>
              <p>Loading academic overview...</p>
            </div>
          )}
          
          {error && (
            <div className="dashboard-error">
              <p>{error}</p>
              <button onClick={fetchDashboardData}>Try Again</button>
            </div>
          )}
          
          {dashboardData && !loading && (
            <>
              <div className="dashboard-header">
                <h3>{dashboardData.student_name}</h3>
                <p>Class {dashboardData.standard} | Roll No: {dashboardData.roll_no}</p>
              </div>
              
              <div className="overall-stats">
                <div className="stat-box">
                  <span className="stat-value">{dashboardData.overall_stats.total_tests_attempted}</span>
                  <span className="stat-label">Tests Taken</span>
                </div>
                <div className="stat-box">
                  <span className="stat-value">{dashboardData.overall_stats.overall_average_score}%</span>
                  <span className="stat-label">Avg Score</span>
                </div>
                <div className="stat-box">
                  <span className="stat-value">{dashboardData.overall_stats.overall_homework_completion}%</span>
                  <span className="stat-label">HW Done</span>
                </div>
                <div className="stat-box warning">
                  <span className="stat-value">{dashboardData.overall_stats.total_missed_homework}</span>
                  <span className="stat-label">Pending HW</span>
                </div>
              </div>
              
              <div className="classification-legend">
                <span className="legend-title">Performance Legend:</span>
                <span className="legend-item" style={{ color: CLASSIFICATION_COLORS.strong.text }}>
                  ● Strong (≥70%)
                </span>
                <span className="legend-item" style={{ color: CLASSIFICATION_COLORS.average.text }}>
                  ● Average (40-69%)
                </span>
                <span className="legend-item" style={{ color: CLASSIFICATION_COLORS.weak.text }}>
                  ● Needs Improvement (&lt;40%)
                </span>
              </div>
              
              <div className="subjects-performance">
                <h4>Subject-wise Performance</h4>
                <div className="subjects-grid">
                  {dashboardData.subjects.map(subject => (
                    <div 
                      key={subject.subject_id}
                      className="subject-performance-card"
                      style={{ 
                        backgroundColor: CLASSIFICATION_COLORS[subject.classification]?.bg || '#f3f4f6',
                        borderColor: CLASSIFICATION_COLORS[subject.classification]?.border || '#9ca3af'
                      }}
                      data-testid={`subject-card-${subject.subject_name}`}
                    >
                      <div className="subject-header">
                        <h4 className="subject-title">{subject.subject_name}</h4>
                        <span 
                          className="classification-badge"
                          style={{ 
                            backgroundColor: CLASSIFICATION_COLORS[subject.classification]?.border || '#9ca3af',
                            color: '#fff'
                          }}
                        >
                          {CLASSIFICATION_COLORS[subject.classification]?.label || 'No Data'}
                        </span>
                      </div>
                      
                      <div className="avg-score">
                        <span className="avg-label">Average Score:</span>
                        <span className="avg-value" style={{ color: CLASSIFICATION_COLORS[subject.classification]?.text || '#6b7280' }}>
                          {subject.average_score > 0 ? `${subject.average_score}%` : 'N/A'}
                        </span>
                      </div>
                      
                      <PerformanceChart data={subject.test_performance} subjectName={subject.subject_name} />
                      
                      <div className="section-block">
                        <h5>Syllabus Progress</h5>
                        <ColorfulProgressBar
                          percentage={subject.syllabus_progress.progress_percentage}
                          label={`${subject.syllabus_progress.attempted_practice_tests} / ${subject.syllabus_progress.total_practice_tests} practice tests`}
                          sublabel={subject.syllabus_progress.chapter_count > 0 
                            ? `Based on ${subject.syllabus_progress.chapter_count} chapters`
                            : 'No chapters uploaded yet'}
                          type="syllabus"
                        />
                      </div>
                      
                      {subject.homework_stats.total_assigned > 0 && (
                        <div className="section-block">
                          <h5>Homework Completion</h5>
                          <ColorfulProgressBar
                            percentage={subject.homework_stats.completion_percentage}
                            label={`${subject.homework_stats.submitted} / ${subject.homework_stats.total_assigned} submitted`}
                            type="homework"
                          />
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
              
              {dashboardData.all_missed_homework.length > 0 && (
                <div className="missed-homework-alert" data-testid="missed-homework-section">
                  <h4>Pending Homework</h4>
                  <ul className="missed-homework-list">
                    {dashboardData.all_missed_homework.map((hw, idx) => (
                      <li key={idx} className="missed-homework-item">
                        <span className="hw-subject">{hw.subject}</span>
                        <span className="hw-title">{hw.homework_title}</span>
                        <span className="hw-date">{hw.due_date?.split('T')[0] || 'N/A'}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
};

export default ParentDashboard;
