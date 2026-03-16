import React, { useState } from 'react';
import axios from 'axios';
import { API, extractErrorMessage } from '@/utils/helpers';

function AuthScreen({ onSuccess, onAdminLogin }) {
  const [view, setView] = useState('login'); // 'login', 'register', 'resetRequest', 'resetConfirm'
  const [rollNo, setRollNo] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  
  // Registration state
  const [regName, setRegName] = useState('');
  const [regSchool, setRegSchool] = useState('');
  const [regPhone, setRegPhone] = useState('');
  const [regEmail, setRegEmail] = useState('');
  const [regRollNo, setRegRollNo] = useState('');
  const [regPassword, setRegPassword] = useState('');
  const [regConfirmPassword, setRegConfirmPassword] = useState('');
  
  // Reset password state
  const [oldPassword, setOldPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [otp, setOtp] = useState('');
  const [otpSent, setOtpSent] = useState(false);
  const [userName, setUserName] = useState('');

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    
    // CRITICAL: Clear old token AND stale cookie before new login
    localStorage.removeItem('auth_token');
    try {
      await axios.post(`${API}/auth/logout`, {}, { withCredentials: true });
    } catch (_) { /* ignore — just clearing stale cookie */ }
    
    try {
      const response = await axios.post(
        `${API}/auth/login`,
        { roll_no: rollNo, password },
        { withCredentials: true }
      );
      
      // Store new token
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

  const handleTeacherRegistration = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setMessage('');
    
    // Validation
    if (regPassword !== regConfirmPassword) {
      setError('Passwords do not match');
      setLoading(false);
      return;
    }
    
    if (regPassword.length < 6) {
      setError('Password must be at least 6 characters');
      setLoading(false);
      return;
    }
    
    try {
      await axios.post(`${API}/auth/register-teacher`, {
        name: regName,
        school_name: regSchool,
        phone: regPhone,
        email: regEmail || null,
        roll_no: regRollNo,
        password: regPassword,
        role: 'teacher'
      });
      
      setMessage('Registration successful! You can now login with your roll number and password.');
      // Clear form
      setRegName('');
      setRegSchool('');
      setRegPhone('');
      setRegEmail('');
      setRegRollNo('');
      setRegPassword('');
      setRegConfirmPassword('');
      
      // Switch to login view after 2 seconds
      setTimeout(() => {
        setView('login');
        setMessage('');
      }, 2000);
    } catch (err) {
      setError(extractErrorMessage(err, 'Registration failed'));
    } finally {
      setLoading(false);
    }
  };

  const requestResetOTP = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setMessage('');
    
    try {
      const response = await axios.post(`${API}/auth/request-reset-otp`, { roll_no: rollNo });
      setOtpSent(true);
      setUserName(response.data.name);
      setMessage(response.data.message);
    } catch (err) {
      setError(extractErrorMessage(err, 'Failed to send OTP'));
    } finally {
      setLoading(false);
    }
  };

  const handleResetPassword = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setMessage('');
    
    if (newPassword !== confirmPassword) {
      setError('New passwords do not match');
      setLoading(false);
      return;
    }
    
    if (newPassword.length < 6) {
      setError('Password must be at least 6 characters');
      setLoading(false);
      return;
    }
    
    try {
      await axios.post(`${API}/auth/reset-password`, {
        roll_no: rollNo,
        old_password: oldPassword,
        otp: otp,
        new_password: newPassword
      });
      setMessage('Password reset successfully! Please login with your new password.');
      
      // Reset all fields and go back to login after delay
      setTimeout(() => {
        setRollNo('');
        setPassword('');
        setOldPassword('');
        setNewPassword('');
        setConfirmPassword('');
        setOtp('');
        setOtpSent(false);
        setError('');
        setMessage('');
        setUserName('');
        setView('login');
      }, 2000);
    } catch (err) {
      setError(extractErrorMessage(err, 'Password reset failed'));
    } finally {
      setLoading(false);
    }
  };

  // Login View
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
              onClick={() => { setError(''); setView('resetRequest'); }}
              className="auth-link-button"
              data-testid="reset-password-link"
            >
              Forgot Password?
            </button>
            <button 
              type="button"
              onClick={() => { setError(''); setMessage(''); setView('register'); }}
              className="auth-link-button"
              data-testid="register-link"
            >
              Register as Teacher
            </button>
          </div>
          
          {/* Admin Login Link */}
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

  // Teacher Registration View
  if (view === 'register') {
    return (
      <div className="auth-container">
        <div className="auth-card">
          <img 
            src="/studybuddy-icon.png" 
            alt="StudyBuddy Logo" 
            className="auth-logo-img"
          />
          <h2 className="auth-title">Teacher Registration</h2>
          <p className="auth-subtitle">Register as a teacher to create your school namespace</p>
          
          <form onSubmit={handleTeacherRegistration} className="auth-form">
            <div className="form-group">
              <label>Full Name *</label>
              <input
                type="text"
                placeholder="Enter your full name"
                value={regName}
                onChange={(e) => setRegName(e.target.value)}
                required
                className="auth-input"
                data-testid="reg-name-input"
              />
            </div>
            
            <div className="form-group">
              <label>School Name *</label>
              <input
                type="text"
                placeholder="Enter school name"
                value={regSchool}
                onChange={(e) => setRegSchool(e.target.value)}
                required
                className="auth-input"
                data-testid="reg-school-input"
              />
            </div>
            
            <div className="form-group">
              <label>Roll Number / Employee ID *</label>
              <input
                type="text"
                placeholder="Enter your roll/employee number"
                value={regRollNo}
                onChange={(e) => setRegRollNo(e.target.value)}
                required
                className="auth-input"
                data-testid="reg-rollno-input"
              />
            </div>
            
            <div className="form-group">
              <label>Phone Number *</label>
              <input
                type="tel"
                placeholder="Enter phone number"
                value={regPhone}
                onChange={(e) => setRegPhone(e.target.value)}
                required
                className="auth-input"
                data-testid="reg-phone-input"
              />
            </div>
            
            <div className="form-group">
              <label>Email (Optional)</label>
              <input
                type="email"
                placeholder="Enter email"
                value={regEmail}
                onChange={(e) => setRegEmail(e.target.value)}
                className="auth-input"
                data-testid="reg-email-input"
              />
            </div>
            
            <div className="form-group">
              <label>Password * (min 6 characters)</label>
              <input
                type="password"
                placeholder="Create password"
                value={regPassword}
                onChange={(e) => setRegPassword(e.target.value)}
                required
                minLength={6}
                className="auth-input"
                data-testid="reg-password-input"
              />
            </div>
            
            <div className="form-group">
              <label>Confirm Password *</label>
              <input
                type="password"
                placeholder="Confirm password"
                value={regConfirmPassword}
                onChange={(e) => setRegConfirmPassword(e.target.value)}
                required
                className="auth-input"
                data-testid="reg-confirm-password-input"
              />
            </div>
            
            {error && <p className="auth-error">{error}</p>}
            {message && <p className="auth-success">{message}</p>}
            
            <button 
              type="submit" 
              disabled={loading} 
              className="auth-button"
              data-testid="register-submit-button"
            >
              {loading ? 'Registering...' : 'Register'}
            </button>
            
            <button 
              type="button"
              onClick={() => { setError(''); setMessage(''); setView('login'); }}
              className="auth-button-secondary"
            >
              Back to Login
            </button>
          </form>
        </div>
      </div>
    );
  }

  // Reset Password Request View (Enter Roll No to get OTP)
  if (view === 'resetRequest' && !otpSent) {
    return (
      <div className="auth-container">
        <div className="auth-card">
          <img 
            src="/studybuddy-icon.png" 
            alt="StudyBuddy Logo" 
            className="auth-logo-img"
          />
          <h2 className="auth-title">Reset Password</h2>
          <p className="auth-subtitle">Enter your roll number to receive OTP</p>
          
          <form onSubmit={requestResetOTP} className="auth-form">
            <div className="form-group">
              <label>Roll Number</label>
              <input
                type="text"
                placeholder="Enter your roll number"
                value={rollNo}
                onChange={(e) => setRollNo(e.target.value)}
                required
                className="auth-input"
                data-testid="reset-rollno-input"
              />
            </div>
            
            {error && <p className="auth-error">{error}</p>}
            {message && <p className="auth-success">{message}</p>}
            
            <button 
              type="submit" 
              disabled={loading} 
              className="auth-button"
              data-testid="request-otp-button"
            >
              {loading ? 'Sending OTP...' : 'Send OTP'}
            </button>
            
            <button 
              type="button"
              onClick={() => { setError(''); setMessage(''); setView('login'); }}
              className="auth-button-secondary"
            >
              Back to Login
            </button>
          </form>
        </div>
      </div>
    );
  }

  // Reset Password Confirm View (Enter old password, OTP, new password)
  if (view === 'resetRequest' && otpSent) {
    return (
      <div className="auth-container">
        <div className="auth-card">
          <img 
            src="/studybuddy-icon.png" 
            alt="StudyBuddy Logo" 
            className="auth-logo-img"
          />
          <h2 className="auth-title">Reset Password</h2>
          <p className="auth-subtitle">
            {userName ? `Hello ${userName}! ` : ''}Enter your details to reset password
          </p>
          
          <form onSubmit={handleResetPassword} className="auth-form">
            <div className="form-group">
              <label>Current Password</label>
              <input
                type="password"
                placeholder="Enter current password"
                value={oldPassword}
                onChange={(e) => setOldPassword(e.target.value)}
                required
                className="auth-input"
                data-testid="old-password-input"
              />
            </div>
            
            <div className="form-group">
              <label>OTP</label>
              <input
                type="text"
                placeholder="Enter 6-digit OTP"
                value={otp}
                onChange={(e) => setOtp(e.target.value)}
                required
                maxLength={6}
                className="auth-input"
                data-testid="otp-input"
              />
            </div>
            
            <div className="form-group">
              <label>New Password</label>
              <input
                type="password"
                placeholder="Enter new password (min 6 chars)"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required
                minLength={6}
                className="auth-input"
                data-testid="new-password-input"
              />
            </div>
            
            <div className="form-group">
              <label>Confirm New Password</label>
              <input
                type="password"
                placeholder="Confirm new password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                className="auth-input"
                data-testid="confirm-password-input"
              />
            </div>
            
            {error && <p className="auth-error">{error}</p>}
            {message && <p className="auth-success">{message}</p>}
            
            <button 
              type="submit" 
              disabled={loading} 
              className="auth-button"
              data-testid="reset-password-button"
            >
              {loading ? 'Resetting...' : 'Reset Password'}
            </button>
            
            <button 
              type="button"
              onClick={() => { setOtpSent(false); setError(''); setMessage(''); }}
              className="auth-button-secondary"
            >
              Back
            </button>
          </form>
          
          <div className="auth-demo-credentials">
            <p className="demo-title">Test OTP: 123456</p>
          </div>
        </div>
      </div>
    );
  }

  return null;
}

export default AuthScreen;
