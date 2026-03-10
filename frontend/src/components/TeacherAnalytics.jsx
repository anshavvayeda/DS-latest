import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './TeacherAnalytics.css';

const API = process.env.REACT_APP_BACKEND_URL ? `${process.env.REACT_APP_BACKEND_URL}/api` : '/api';

const TeacherAnalytics = ({ onClose }) => {
  const [standards, setStandards] = useState([1, 2, 3, 4, 5, 6, 7, 8, 9, 10]);
  const [selectedStandard, setSelectedStandard] = useState(5);
  const [analyticsData, setAnalyticsData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [showCategoryModal, setShowCategoryModal] = useState(null); // 'strong', 'average', 'weak', or null

  useEffect(() => {
    if (selectedStandard) {
      fetchAnalytics();
    }
  }, [selectedStandard]);

  const fetchAnalytics = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await axios.get(`${API}/teacher/analytics/${selectedStandard}`, {
        withCredentials: true
      });
      setAnalyticsData(response.data);
    } catch (err) {
      console.error('Error fetching analytics:', err);
      setError(err.response?.data?.detail || 'Failed to load analytics');
    } finally {
      setLoading(false);
    }
  };

  const getClassificationColor = (classification) => {
    switch (classification) {
      case 'strong':
        return '#10b981'; // Green
      case 'average':
        return '#f59e0b'; // Yellow
      case 'weak':
        return '#ef4444'; // Red
      default:
        return '#6b7280'; // Gray
    }
  };

  const getClassificationBg = (classification) => {
    switch (classification) {
      case 'strong':
        return 'rgba(16, 185, 129, 0.1)';
      case 'average':
        return 'rgba(245, 158, 11, 0.1)';
      case 'weak':
        return 'rgba(239, 68, 68, 0.1)';
      default:
        return 'rgba(107, 114, 128, 0.1)';
    }
  };

  const getStudentsByClassification = (classification) => {
    if (!analyticsData) return [];
    return analyticsData.students.filter(
      student => student.overall_classification === classification && student.overall_average > 0
    ).sort((a, b) => b.overall_average - a.overall_average);
  };

  const CategoryModal = ({ category, onClose }) => {
    const students = getStudentsByClassification(category);
    const categoryTitles = {
      strong: '💪 Strong Students (≥80%)',
      average: '📈 Average Students (60-79%)',
      weak: '📉 Weak Students (<60%)'
    };

    return (
      <div className="modal-overlay" onClick={onClose}>
        <div className="modal-content" onClick={(e) => e.stopPropagation()}>
          <div className="modal-header">
            <h3>{categoryTitles[category]}</h3>
            <button onClick={onClose} className="modal-close-btn">✕</button>
          </div>
          <div className="modal-body">
            {students.length === 0 ? (
              <p className="no-students">No students in this category</p>
            ) : (
              <table className="category-table">
                <thead>
                  <tr>
                    <th>Rank</th>
                    <th>Roll No</th>
                    <th>Student Name</th>
                    <th>Overall Average</th>
                  </tr>
                </thead>
                <tbody>
                  {students.map((student, index) => (
                    <tr key={student.roll_no}>
                      <td className="rank-cell">#{index + 1}</td>
                      <td className="roll-cell">{student.roll_no}</td>
                      <td className="name-cell">{student.student_name}</td>
                      <td 
                        className="score-cell"
                        style={{
                          color: getClassificationColor(category),
                          fontWeight: '700'
                        }}
                      >
                        {student.overall_average.toFixed(2)}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </div>
    );
  };

  if (loading) {
    return (
      <div className="analytics-container">
        <div className="analytics-header">
          <h2>📊 Teacher Analytics Dashboard</h2>
          <button onClick={onClose} className="close-btn">✕</button>
        </div>
        <div className="loading-state">
          <div className="spinner"></div>
          <p>Loading analytics...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="analytics-container">
        <div className="analytics-header">
          <h2>📊 Teacher Analytics Dashboard</h2>
          <button onClick={onClose} className="close-btn">✕</button>
        </div>
        <div className="error-state">
          <p>❌ {error}</p>
          <button onClick={fetchAnalytics} className="retry-btn">Try Again</button>
        </div>
      </div>
    );
  }

  return (
    <div className="analytics-container">
      {/* Header */}
      <div className="analytics-header">
        <h2>📊 Teacher Analytics Dashboard</h2>
        <button onClick={onClose} className="close-btn">✕</button>
      </div>

      {/* Standard Selector */}
      <div className="standard-selector">
        <label>Select Standard:</label>
        <select 
          value={selectedStandard} 
          onChange={(e) => setSelectedStandard(parseInt(e.target.value))}
          className="standard-dropdown"
        >
          {standards.map(std => (
            <option key={std} value={std}>Class {std}</option>
          ))}
        </select>
      </div>

      {analyticsData && (
        <>
          {/* Summary Cards */}
          <div className="summary-cards">
            <div className="summary-card strong">
              <div className="card-icon">💪</div>
              <div className="card-content">
                <h3>{analyticsData.summary.strong_count}</h3>
                <p>Strong Students</p>
                <small>≥80% Average</small>
                {analyticsData.summary.strong_count > 0 && (
                  <button 
                    className="view-details-btn"
                    onClick={() => setShowCategoryModal('strong')}
                  >
                    View Details
                  </button>
                )}
              </div>
            </div>

            <div className="summary-card average">
              <div className="card-icon">📈</div>
              <div className="card-content">
                <h3>{analyticsData.summary.average_count}</h3>
                <p>Average Students</p>
                <small>60-79% Average</small>
                {analyticsData.summary.average_count > 0 && (
                  <button 
                    className="view-details-btn"
                    onClick={() => setShowCategoryModal('average')}
                  >
                    View Details
                  </button>
                )}
              </div>
            </div>

            <div className="summary-card weak">
              <div className="card-icon">📉</div>
              <div className="card-content">
                <h3>{analyticsData.summary.weak_count}</h3>
                <p>Weak Students</p>
                <small>&lt;60% Average</small>
                {analyticsData.summary.weak_count > 0 && (
                  <button 
                    className="view-details-btn"
                    onClick={() => setShowCategoryModal('weak')}
                  >
                    View Details
                  </button>
                )}
              </div>
            </div>

            <div className="summary-card total">
              <div className="card-icon">👥</div>
              <div className="card-content">
                <h3>{analyticsData.summary.total_students}</h3>
                <p>Total Students</p>
                <small>Class {selectedStandard}</small>
              </div>
            </div>
          </div>

          {/* Top 3 Students */}
          {analyticsData.top_performers && analyticsData.top_performers.length > 0 && (
            <div className="top-performers-section">
              <h3>🏆 Top 3 Performers</h3>
              <div className="top-performers-grid">
                {analyticsData.top_performers.map((student, index) => (
                  <div key={student.roll_no} className={`top-performer-card rank-${index + 1}`}>
                    <div className="rank-badge">{index === 0 ? '🥇' : index === 1 ? '🥈' : '🥉'}</div>
                    <h4>{student.student_name}</h4>
                    <p className="roll-no">Roll No: {student.roll_no}</p>
                    <div className="overall-average">
                      <span className="label">Overall Average:</span>
                      <span className="value">{student.overall_average.toFixed(2)}%</span>
                    </div>
                    
                    <div className="subject-breakdown">
                      <h5>Subject-wise Performance:</h5>
                      <div className="subjects-grid">
                        {student.subject_wise_performance.map(subj => (
                          <div key={subj.subject_name} className="subject-item">
                            <span className="subject-name">{subj.subject_name}</span>
                            <span 
                              className="subject-percentage"
                              style={{ 
                                color: getClassificationColor(subj.classification),
                                fontWeight: '600'
                              }}
                            >
                              {subj.percentage.toFixed(1)}%
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Top 3 Students - Above the table */}
          {analyticsData.top_performers && analyticsData.top_performers.length > 0 && (
            <div className="top-performers-compact">
              <h3>🏆 Top 3 Performers (Overall Average)</h3>
              <div className="top-3-list">
                {analyticsData.top_performers.map((student, index) => (
                  <div key={student.roll_no} className="top-3-item">
                    <span className="top-3-rank">{index === 0 ? '🥇' : index === 1 ? '🥈' : '🥉'}</span>
                    <span className="top-3-name">{student.student_name}</span>
                    <span className="top-3-roll">(Roll: {student.roll_no})</span>
                    <span className="top-3-score">{student.overall_average.toFixed(2)}%</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* All Students Performance Table */}
          <div className="students-table-section">
            <h3>📋 All Students Performance (Roll No. Order)</h3>
            <div className="table-wrapper">
              <table className="analytics-table">
                <thead>
                  <tr>
                    <th>Roll No</th>
                    <th>Student Name</th>
                    {analyticsData.subjects.map(subject => (
                      <th key={subject}>{subject}</th>
                    ))}
                    <th>Overall Avg</th>
                  </tr>
                </thead>
                <tbody>
                  {analyticsData.students.map(student => (
                    <tr key={student.roll_no}>
                      <td className="roll-cell">{student.roll_no}</td>
                      <td className="name-cell">{student.student_name}</td>
                      {analyticsData.subjects.map(subject => {
                        const subjectData = student.subjects[subject];
                        if (!subjectData || subjectData.total_tests === 0) {
                          return <td key={subject} className="no-data-cell">-</td>;
                        }
                        return (
                          <td 
                            key={subject} 
                            className="percentage-cell"
                            style={{
                              backgroundColor: getClassificationBg(subjectData.classification),
                              color: getClassificationColor(subjectData.classification),
                              fontWeight: '600'
                            }}
                          >
                            {subjectData.percentage.toFixed(1)}%
                            <span className="test-count">({subjectData.total_tests} tests)</span>
                          </td>
                        );
                      })}
                      <td className="overall-cell" style={{ fontWeight: '700' }}>
                        {student.overall_average > 0 ? `${student.overall_average.toFixed(1)}%` : '-'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {/* Category Modal */}
      {showCategoryModal && (
        <CategoryModal 
          category={showCategoryModal} 
          onClose={() => setShowCategoryModal(null)} 
        />
      )}
    </div>
  );
};

export default TeacherAnalytics;
