import React, { useState } from 'react';
import axios from 'axios';
import { API, extractErrorMessage } from '@/utils/helpers';

function AuthScreen({ onSuccess, onAdminLogin }) {
  const [view, setView] = useState('login');
  const [rollNo, setRollNo] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    localStorage.removeItem('auth_token');
    try {
      await axios.post(`${API}/auth/logout`, {}, { withCredentials: true });
    } catch (_) { /* ignore */ }

    try {
      const response = await axios.post(
        `${API}/auth/login`,
        { roll_no: rollNo, password },
        { withCredentials: true }
      );

      if (response.data.token) {
        localStorage.setItem('auth_token', response.data.token);
      }

      onSuccess();
    } catch (err) {
      setError(extractErrorMessage(err, 'Login failed. Check your roll number and password.'));
    } finally {
      setLoading(false);
    }
  };

  if (view === 'login') {
    return (
      <div className="auth-container">
        <div className="auth-card">
          <img
            src="/studybuddy-icon.png"
            alt="StudyBuddy Logo"
            className="auth-logo-img"
          />

          <form onSubmit={handleLogin} className="auth-form">
            <div className="form-group">
              <label>Roll Number</label>
              <input
                type="text"
                placeholder="Enter your roll number"
                value={rollNo}
                onChange={(e) => setRollNo(e.target.value)}
                required
                className="auth-input"
                data-testid="rollno-input"
              />
            </div>

            <div className="form-group">
              <label>Password</label>
              <input
                type="password"
                placeholder="Enter your password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="auth-input"
                data-testid="password-input"
              />
            </div>

            {error && <p className="auth-error" data-testid="auth-error">{error}</p>}

            <button
              type="submit"
              disabled={loading}
              className="auth-button"
              data-testid="login-button"
            >
              {loading ? 'Logging in...' : 'Login'}
            </button>
          </form>

          <div className="auth-links">
            <button
              type="button"
              onClick={() => { setError(''); setView('forgotInfo'); }}
              className="auth-link-button"
              data-testid="reset-password-link"
            >
              Forgot Password?
            </button>
          </div>

          <div className="admin-login-link">
            <button
              type="button"
              onClick={onAdminLogin}
              className="admin-link-btn"
              data-testid="admin-login-link"
            >
              Admin Login
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (view === 'forgotInfo') {
    return (
      <div className="auth-container">
        <div className="auth-card">
          <img
            src="/studybuddy-icon.png"
            alt="StudyBuddy Logo"
            className="auth-logo-img"
          />
          <h2 className="auth-title">Forgot Password?</h2>
          <p className="auth-subtitle" style={{ lineHeight: 1.7, marginBottom: '24px' }}>
            Please contact your school administrator to reset your password.
            The admin can reset it from the Admin Dashboard.
          </p>

          <button
            type="button"
            onClick={() => { setError(''); setView('login'); }}
            className="auth-button"
            data-testid="back-to-login-btn"
          >
            Back to Login
          </button>
        </div>
      </div>
    );
  }

  return null;
}

export default AuthScreen;
