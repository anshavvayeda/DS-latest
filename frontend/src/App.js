import React, { useState, useEffect } from 'react';
import axios from 'axios';
import 'katex/dist/katex.min.css';
import '@/App.css';
import '@/components/LearningTools.css';
import '@/components/StudentProfileView.css';
import '@/components/ProfileDropdown.css';
import '@/components/StudentAITest.css';
import '@/components/TeacherUpload.css';
import '@/components/StudentContentViewer.css';
import '@/components/ParentDashboard.css';
import '@/components/TeacherAnalytics.css';
import '@/components/AdminLogin.css';
import '@/components/AdminDashboard.css';
import '@/components/TeacherReviewMode.css';
import '@/components/StructuredTestCreator.css';
import '@/components/HomeworkAnswering.css';

import { API } from '@/utils/helpers';
import AuthScreen from '@/components/AuthScreen';
import Header from '@/components/Header';
import StudentView from '@/components/StudentView';
import TeacherView from '@/components/TeacherView';
import StudentProfileView from '@/components/StudentProfileView';
import ParentDashboard from '@/components/ParentDashboard';
import TeacherAnalytics from '@/components/TeacherAnalytics';
import GalaxyBackground from '@/components/GalaxyBackground';
import AdminLogin from '@/components/AdminLogin';
import AdminDashboard from '@/components/AdminDashboard';

// CRITICAL: Enable credentials (cookies) for all axios requests
axios.defaults.withCredentials = true;

function App() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [view, setView] = useState('student');
  const [showProfileForm, setShowProfileForm] = useState(false);
  const [showParentDashboard, setShowParentDashboard] = useState(false);
  const [showTeacherAnalytics, setShowTeacherAnalytics] = useState(false);
  const [showAdminLogin, setShowAdminLogin] = useState(false);
  const [language, setLanguage] = useState(() => {
    return localStorage.getItem('preferred_language') || 'english';
  });

  // Click sound effect
  useEffect(() => {
    const clickSound = new Audio('/click-sound.mp3');
    clickSound.volume = 0.3;
    const playClickSound = (e) => {
      if (e.isTrusted) {
        clickSound.currentTime = 0;
        clickSound.play().catch(() => {});
      }
    };
    document.addEventListener('click', playClickSound);
    return () => document.removeEventListener('click', playClickSound);
  }, []);

  useEffect(() => { checkAuth(); }, []);

  const checkAuth = async () => {
    try {
      const response = await axios.get(`${API}/auth/me`, { withCredentials: true });
      setUser(response.data);
      if (response.data.token) {
        localStorage.setItem('auth_token', response.data.token);
      }
      if (response.data.role === 'admin') setView('admin');
      else if (response.data.role === 'teacher') setView('teacher');
      else setView('student');
    } catch {
      localStorage.removeItem('auth_token');
    } finally {
      setLoading(false);
    }
  };

  // Axios interceptor for Bearer token fallback
  useEffect(() => {
    const id = axios.interceptors.request.use((config) => {
      const token = localStorage.getItem('auth_token');
      if (token) config.headers.Authorization = `Bearer ${token}`;
      return config;
    }, (err) => Promise.reject(err));
    return () => axios.interceptors.request.eject(id);
  }, []);

  const handleLogout = async () => {
    localStorage.removeItem('auth_token');
    try { await axios.post(`${API}/auth/logout`, {}, { withCredentials: true }); } catch {}
    setUser(null);
    setShowProfileForm(false);
    setShowAdminLogin(false);
    setView('student');
    setShowParentDashboard(false);
    setShowTeacherAnalytics(false);
  };

  const handleLanguageToggle = () => {
    const newLang = language === 'english' ? 'gujarati' : 'english';
    setLanguage(newLang);
    localStorage.setItem('preferred_language', newLang);
  };

  const handleAdminLoginSuccess = (adminUser) => {
    setUser({ ...adminUser, role: 'admin' });
    setView('admin');
    setShowAdminLogin(false);
  };

  if (loading) {
    return <div className="loading"><GalaxyBackground />Loading...</div>;
  }

  if (showAdminLogin && !user) {
    return <AdminLogin onLoginSuccess={handleAdminLoginSuccess} />;
  }

  if (user && user.role === 'admin') {
    return <AdminDashboard onLogout={handleLogout} />;
  }

  if (!user) {
    return (
      <>
        <GalaxyBackground />
        <AuthScreen onSuccess={() => checkAuth()} onAdminLogin={() => setShowAdminLogin(true)} />
      </>
    );
  }

  if (showProfileForm && user.role === 'student') {
    return (
      <>
        <GalaxyBackground />
        <StudentProfileView
          user={user}
          studentProfile={user.student_profile}
          onBack={() => setShowProfileForm(false)}
        />
      </>
    );
  }

  const handleViewProfile = () => {
    if (user.role === 'student') setShowProfileForm(true);
  };

  if (showTeacherAnalytics && user.role === 'teacher') {
    return (
      <div className="app-container">
        <GalaxyBackground />
        <TeacherAnalytics onClose={() => setShowTeacherAnalytics(false)} />
      </div>
    );
  }

  if (showParentDashboard && user.role === 'student') {
    return (
      <div className="app-container">
        <GalaxyBackground />
        <Header
          user={user} view={view} setView={setView}
          onLogout={handleLogout} language={language}
          onLanguageToggle={handleLanguageToggle}
          studentProfile={user?.student_profile}
          onViewProfile={handleViewProfile}
          onParentDashboard={() => setShowParentDashboard(true)}
          onAnalytics={() => setShowTeacherAnalytics(true)}
        />
        <ParentDashboard isFullPage={true} onClose={() => setShowParentDashboard(false)} />
      </div>
    );
  }

  return (
    <div className="app-container">
      <GalaxyBackground />
      <Header
        user={user} view={view} setView={setView}
        onLogout={handleLogout} language={language}
        onLanguageToggle={handleLanguageToggle}
        studentProfile={user?.student_profile}
        onViewProfile={handleViewProfile}
        onParentDashboard={() => setShowParentDashboard(true)}
        onAnalytics={() => setShowTeacherAnalytics(true)}
      />
      {view === 'teacher' ? (
        <TeacherView user={user} language={language} />
      ) : (
        <StudentView
          user={user}
          language={language}
          isTeacherPreview={user.role === 'teacher'}
        />
      )}
    </div>
  );
}

export default App;
