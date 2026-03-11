import React, { useState, useRef, useEffect } from 'react';
import './ProfileDropdown.css';

const ProfileDropdown = ({ user, studentProfile, onLogout, onViewProfile, onParentDashboard, onAnalytics }) => {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const gender = studentProfile?.gender || 'male';
  const name = studentProfile?.name || user?.name || user?.email?.split('@')[0] || (user?.role === 'teacher' ? 'Teacher' : 'Student');
  const initials = name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);

  // Get avatar based on gender
  const getAvatar = () => {
    if (user?.role === 'teacher') {
      return (
        <svg viewBox="0 0 100 100" className="avatar-svg teacher">
          <circle cx="50" cy="50" r="48" fill="#667eea"/>
          <circle cx="50" cy="38" r="18" fill="#FFE0BD"/>
          <ellipse cx="50" cy="85" rx="30" ry="25" fill="#4a5568"/>
          <rect x="35" y="58" width="30" height="8" rx="2" fill="#667eea"/>
          <circle cx="43" cy="35" r="2" fill="#333"/>
          <circle cx="57" cy="35" r="2" fill="#333"/>
          <path d="M44 44 Q50 48 56 44" stroke="#333" strokeWidth="2" fill="none"/>
          <rect x="32" y="20" width="36" height="10" rx="2" fill="#333"/>
        </svg>
      );
    }

    if (gender === 'female') {
      return (
        <svg viewBox="0 0 100 100" className="avatar-svg female">
          <circle cx="50" cy="50" r="48" fill="#ec4899"/>
          <circle cx="50" cy="42" r="22" fill="#FFE0BD"/>
          <ellipse cx="50" cy="90" rx="28" ry="22" fill="#f472b6"/>
          {/* Hair */}
          <path d="M28 42 Q28 15 50 15 Q72 15 72 42 Q72 30 50 30 Q28 30 28 42" fill="#4a3728"/>
          <ellipse cx="28" cy="45" rx="8" ry="12" fill="#4a3728"/>
          <ellipse cx="72" cy="45" rx="8" ry="12" fill="#4a3728"/>
          {/* Eyes */}
          <ellipse cx="42" cy="40" rx="4" ry="5" fill="#333"/>
          <ellipse cx="58" cy="40" rx="4" ry="5" fill="#333"/>
          <circle cx="43" cy="39" r="1.5" fill="#fff"/>
          <circle cx="59" cy="39" r="1.5" fill="#fff"/>
          {/* Smile */}
          <path d="M42 52 Q50 58 58 52" stroke="#e57373" strokeWidth="2.5" fill="none" strokeLinecap="round"/>
          {/* Blush */}
          <ellipse cx="35" cy="48" rx="5" ry="3" fill="#ffb6c1" opacity="0.6"/>
          <ellipse cx="65" cy="48" rx="5" ry="3" fill="#ffb6c1" opacity="0.6"/>
          {/* Hair bow */}
          <circle cx="30" cy="25" r="6" fill="#ff69b4"/>
          <circle cx="24" cy="25" r="4" fill="#ff69b4"/>
          <circle cx="36" cy="25" r="4" fill="#ff69b4"/>
        </svg>
      );
    }

    // Male or other
    return (
      <svg viewBox="0 0 100 100" className="avatar-svg male">
        <circle cx="50" cy="50" r="48" fill="#3b82f6"/>
        <circle cx="50" cy="42" r="22" fill="#FFE0BD"/>
        <ellipse cx="50" cy="90" rx="28" ry="22" fill="#60a5fa"/>
        {/* Hair */}
        <path d="M30 38 Q30 18 50 18 Q70 18 70 38 Q65 28 50 28 Q35 28 30 38" fill="#4a3728"/>
        {/* Eyes */}
        <ellipse cx="42" cy="40" rx="4" ry="5" fill="#333"/>
        <ellipse cx="58" cy="40" rx="4" ry="5" fill="#333"/>
        <circle cx="43" cy="39" r="1.5" fill="#fff"/>
        <circle cx="59" cy="39" r="1.5" fill="#fff"/>
        {/* Smile */}
        <path d="M42 52 Q50 58 58 52" stroke="#e57373" strokeWidth="2.5" fill="none" strokeLinecap="round"/>
        {/* Eyebrows */}
        <path d="M38 32 L46 34" stroke="#4a3728" strokeWidth="2" strokeLinecap="round"/>
        <path d="M62 32 L54 34" stroke="#4a3728" strokeWidth="2" strokeLinecap="round"/>
      </svg>
    );
  };

  return (
    <div className="profile-dropdown-container" ref={dropdownRef}>
      <button 
        className="profile-avatar-btn"
        onClick={() => setIsOpen(!isOpen)}
        data-testid="profile-dropdown-btn"
      >
        <div className="avatar-wrapper">
          {getAvatar()}
        </div>
        <span className="avatar-name">{name.split(' ')[0]}</span>
        <svg className={`dropdown-arrow ${isOpen ? 'open' : ''}`} width="12" height="12" viewBox="0 0 12 12">
          <path d="M3 4.5L6 7.5L9 4.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" fill="none"/>
        </svg>
      </button>

      {isOpen && (
        <div className="profile-dropdown-menu" data-testid="profile-dropdown-menu">
          <div className="dropdown-header">
            <div className="dropdown-avatar">
              {getAvatar()}
            </div>
            <div className="dropdown-user-info">
              <span className="dropdown-name">{name}</span>
              {studentProfile && (
                <span className="dropdown-class">Class {studentProfile.standard}</span>
              )}
              {user?.role === 'teacher' && (
                <span className="dropdown-role">Teacher</span>
              )}
            </div>
          </div>
          
          <div className="dropdown-divider"></div>
          
          <div className="dropdown-menu-items">
            {user?.role === 'student' && (
              <>
                <button 
                  className="dropdown-item"
                  onClick={() => { onViewProfile(); setIsOpen(false); }}
                  data-testid="view-profile-btn"
                >
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
                    <circle cx="12" cy="7" r="4"/>
                  </svg>
                  <span>View Profile</span>
                </button>
                
                <button 
                  className="dropdown-item"
                  onClick={() => { onParentDashboard(); setIsOpen(false); }}
                  data-testid="parent-dashboard-btn"
                >
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
                    <line x1="3" y1="9" x2="21" y2="9"/>
                    <line x1="9" y1="21" x2="9" y2="9"/>
                  </svg>
                  <span>Parent Dashboard</span>
                </button>
              </>
            )}
            
            {user?.role === 'teacher' && (
              <>
                <button 
                  className="dropdown-item"
                  onClick={() => { onAnalytics(); setIsOpen(false); }}
                  data-testid="teacher-analytics-btn"
                >
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <line x1="18" y1="20" x2="18" y2="10"/>
                    <line x1="12" y1="20" x2="12" y2="4"/>
                    <line x1="6" y1="20" x2="6" y2="14"/>
                  </svg>
                  <span>Analytics</span>
                </button>
                
                <button 
                  className="dropdown-item"
                  onClick={() => { onViewProfile(); setIsOpen(false); }}
                  data-testid="teacher-settings-btn"
                >
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <circle cx="12" cy="12" r="3"/>
                    <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>
                  </svg>
                  <span>Settings</span>
                </button>
              </>
            )}
          </div>
          
          <div className="dropdown-divider"></div>
          
          <button 
            className="dropdown-item logout"
            onClick={() => { onLogout(); setIsOpen(false); }}
            data-testid="logout-btn"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
              <polyline points="16 17 21 12 16 7"/>
              <line x1="21" y1="12" x2="9" y2="12"/>
            </svg>
            <span>Logout</span>
          </button>
        </div>
      )}
    </div>
  );
};

export default ProfileDropdown;
