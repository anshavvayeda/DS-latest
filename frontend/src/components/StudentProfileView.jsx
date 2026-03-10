import React from 'react';
import './StudentProfileView.css';

const StudentProfileView = ({ user, studentProfile, onBack }) => {
  const profile = studentProfile || {};
  
  const getGenderIcon = () => {
    switch (profile.gender) {
      case 'female': return '👧';
      case 'male': return '👦';
      default: return '🧒';
    }
  };

  return (
    <div className="profile-view-overlay">
      <div className="profile-view-container">
        {/* Header */}
        <div className="profile-view-header">
          <button 
            type="button" 
            className="back-button-header"
            onClick={onBack}
            data-testid="profile-view-back-btn"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M19 12H5M12 19l-7-7 7-7"/>
            </svg>
            Back
          </button>
          <div className="profile-view-title">
            <h2>Student Profile</h2>
            <p>View your profile information</p>
          </div>
        </div>

        {/* Profile Content */}
        <div className="profile-view-content">
          {!profile.name ? (
            <div className="no-profile-message">
              <div className="no-profile-icon">📋</div>
              <h3>Profile Not Set Up</h3>
              <p>Your profile has not been configured yet. Please contact your administrator to set up your profile.</p>
            </div>
          ) : (
            <>
              {/* Avatar Section */}
              <div className="profile-avatar-section">
                <div className="profile-avatar-large">
                  <span className="avatar-emoji">{getGenderIcon()}</span>
                </div>
                <h3 className="profile-name">{profile.name}</h3>
                <span className="profile-class-badge">Class {profile.standard}</span>
              </div>

              {/* Student Information Section */}
              <div className="profile-section">
                <h4 className="section-title">
                  <span className="section-icon">👤</span>
                  Student Information
                </h4>
                
                <div className="info-grid">
                  <div className="info-item">
                    <label>Full Name</label>
                    <span>{profile.name || '-'}</span>
                  </div>
                  <div className="info-item">
                    <label>Roll Number</label>
                    <span>{profile.roll_no || '-'}</span>
                  </div>
                  <div className="info-item">
                    <label>School Name</label>
                    <span>{profile.school_name || '-'}</span>
                  </div>
                  <div className="info-item">
                    <label>Class</label>
                    <span>{profile.standard ? `Class ${profile.standard}` : '-'}</span>
                  </div>
                  <div className="info-item">
                    <label>Gender</label>
                    <span className="gender-display">
                      {getGenderIcon()} {profile.gender ? profile.gender.charAt(0).toUpperCase() + profile.gender.slice(1) : '-'}
                    </span>
                  </div>
                </div>
              </div>

              {/* Contact Information Section */}
              <div className="profile-section">
                <h4 className="section-title">
                  <span className="section-icon">📱</span>
                  Contact Information
                </h4>
                
                <div className="info-grid">
                  <div className="info-item">
                    <label>Student's Mobile</label>
                    <span>{profile.login_phone ? `+91 ${profile.login_phone}` : '-'}</span>
                  </div>
                  <div className="info-item">
                    <label>Parent's Mobile</label>
                    <span>{profile.parent_phone ? `+91 ${profile.parent_phone}` : '-'}</span>
                  </div>
                  <div className="info-item full-width">
                    <label>Email Address</label>
                    <span>{profile.email || '-'}</span>
                  </div>
                </div>
              </div>

              {/* Footer Note */}
              <div className="profile-footer-note">
                <span className="info-icon">ℹ️</span>
                <p>To update your profile information, please contact your administrator.</p>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default StudentProfileView;
