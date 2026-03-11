import React, { useState } from 'react';
import axios from 'axios';
import './AdminLogin.css';

const API = process.env.REACT_APP_BACKEND_URL ? `${process.env.REACT_APP_BACKEND_URL}/api` : '/api';

const AdminLogin = ({ onLoginSuccess }) => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    // CRITICAL: Clear old token first to prevent conflicts
    localStorage.removeItem('auth_token');

    try {
      const response = await axios.post(`${API}/admin/login`, {
        username,
        password
      }, { withCredentials: true });

      // Store token in localStorage as fallback for CORS/HTTP issues
      if (response.data.token) {
        localStorage.setItem('auth_token', response.data.token);
      }

      if (response.data.user) {
        onLoginSuccess(response.data.user);
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Login failed. Please check your credentials.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="admin-login-container" data-testid="admin-login-page">
      <div className="admin-login-card">
        <div className="admin-login-header">
          <div className="admin-icon">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 15v2m-6 4h12a2 2 0 0 0 2-2v-6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2zm10-10V7a4 4 0 0 0-8 0v4h8z"/>
            </svg>
          </div>
          <h1>Admin Login</h1>
          <p>Enter your administrator credentials</p>
        </div>

        {error && (
          <div className="admin-login-error" data-testid="admin-login-error">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="admin-login-form">
          <div className="form-field">
            <label htmlFor="username">Username</label>
            <input
              type="text"
              id="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Enter admin username"
              required
              autoComplete="username"
              data-testid="admin-username-input"
            />
          </div>

          <div className="form-field">
            <label htmlFor="password">Password</label>
            <input
              type="password"
              id="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter admin password"
              required
              autoComplete="current-password"
              data-testid="admin-password-input"
            />
          </div>

          <button 
            type="submit" 
            className="admin-login-btn" 
            disabled={loading}
            data-testid="admin-login-btn"
          >
            {loading ? (
              <span className="loading-spinner">Logging in...</span>
            ) : (
              'Login'
            )}
          </button>
        </form>

        <div className="admin-login-footer">
          <a href="/" className="back-link">← Back to Main Login</a>
        </div>
      </div>
    </div>
  );
};

export default AdminLogin;
