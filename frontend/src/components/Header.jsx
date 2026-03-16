import React from 'react';
import { translateBatch } from '@/utils/helpers';
import ProfileDropdown from '@/components/ProfileDropdown';

function Header({ user, view, setView, onLogout, language, onLanguageToggle, studentProfile, onViewProfile, onParentDashboard, onAnalytics }) {
  const [headerTranslations, setHeaderTranslations] = React.useState({});
  
  React.useEffect(() => {
    const translateHeader = async () => {
      if (language === 'gujarati') {
        const texts = ['Student', 'Teacher', 'Logout'];
        const translations = await translateBatch(texts, language, 'ui');
        setHeaderTranslations(translations);
      } else {
        setHeaderTranslations({});
      }
    };
    translateHeader();
  }, [language]);
  
  const t = (text) => headerTranslations[text] || text;
  
  return (
    <header className="app-header">
      <div className="header-left">
        <img 
          src="/studybuddy-icon.png" 
          alt="StudyBuddy" 
          className="app-header-logo"
        />
      </div>
      <div className="header-right">
        {/* Language Toggle Button - Coming Soon */}
        <button 
          disabled
          className="language-toggle-btn language-toggle-disabled" 
          data-testid="language-toggle"
          title="Multi-language support coming soon!"
          style={{ position: 'relative', cursor: 'not-allowed', opacity: 0.7 }}
        >
          🌐 English
          <span className="new-badge">NEW</span>
        </button>
        
        {user.role === 'teacher' && (
          <div className="view-toggle">
            <button
              className={`toggle-btn ${view === 'student' ? 'active' : ''}`}
              onClick={() => setView('student')}
              data-testid="student-tab"
            >
              🎓 {t('Student')}
            </button>
            <button
              className={`toggle-btn ${view === 'teacher' ? 'active' : ''}`}
              onClick={() => setView('teacher')}
              data-testid="teacher-tab"
            >
              📖 {t('Teacher')}
            </button>
          </div>
        )}
        
        {/* Profile Dropdown */}
        <ProfileDropdown 
          user={user}
          studentProfile={studentProfile}
          onLogout={onLogout}
          onViewProfile={onViewProfile}
          onParentDashboard={onParentDashboard}
          onAnalytics={onAnalytics}
        />
      </div>
    </header>
  );
}

export default Header;
