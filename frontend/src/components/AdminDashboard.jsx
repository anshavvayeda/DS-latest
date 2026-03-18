import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './AdminDashboard.css';

const API = process.env.REACT_APP_BACKEND_URL ? `${process.env.REACT_APP_BACKEND_URL}/api` : '/api';

// Helper function to extract error message from FastAPI/Pydantic error responses
const extractErrorMessage = (err, fallbackMessage = 'An error occurred') => {
  const errorData = err?.response?.data?.detail;
  if (Array.isArray(errorData)) {
    // Pydantic validation errors come as array of objects with 'msg' field
    return errorData.map(e => e.msg || e.message || JSON.stringify(e)).join(', ');
  } else if (typeof errorData === 'object' && errorData !== null) {
    return errorData.msg || errorData.message || JSON.stringify(errorData);
  } else if (typeof errorData === 'string') {
    return errorData;
  }
  return err?.message || fallbackMessage;
};

// Single Student Registration Form
const StudentRegistrationForm = ({ onSuccess, onCancel }) => {
  const [formData, setFormData] = useState({
    name: '',
    school_name: '',
    standard: '',
    roll_no: '',
    gender: 'male',
    phone: '',
    email: '',
    parent_phone: '',
    password: '',
    confirmPassword: '',
    is_active: true,
    role: 'student'
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [availableSchools, setAvailableSchools] = useState([]);
  const [loadingSchools, setLoadingSchools] = useState(false);

  // Fetch available schools when role changes to student
  useEffect(() => {
    const fetchSchools = async () => {
      if (formData.role !== 'student') return;
      
      setLoadingSchools(true);
      try {
        const response = await axios.get(`${API}/schools/list`, { withCredentials: true });
        setAvailableSchools(response.data.schools || []);
      } catch (err) {
        console.error('Failed to fetch schools:', err);
        setAvailableSchools([]);
      } finally {
        setLoadingSchools(false);
      }
    };
    
    fetchSchools();
  }, [formData.role]);

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    // Validation
    if (formData.password !== formData.confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    if (formData.password.length < 6) {
      setError('Password must be at least 6 characters');
      return;
    }
    
    // For teachers, validate school is provided
    if (formData.role === 'teacher' && (!formData.school_name || !formData.school_name.trim())) {
      setError('School name is required for teachers');
      return;
    }
    
    // For students, validate school is selected
    if (formData.role === 'student' && !formData.school_name) {
      setError('Please select a school. If your school is not listed, a teacher must be registered first.');
      return;
    }

    setLoading(true);
    try {
      const payload = {
        name: formData.name,
        school_name: formData.school_name,
        standard: formData.role === 'student' ? parseInt(formData.standard) : null,
        roll_no: formData.roll_no,
        gender: formData.gender,
        phone: formData.phone,
        email: formData.email || null,
        parent_phone: formData.parent_phone || formData.phone,
        password: formData.password,
        is_active: formData.is_active,
        role: formData.role
      };

      const response = await axios.post(`${API}/admin/register-student`, payload, { withCredentials: true });
      onSuccess(response.data);
    } catch (err) {
      setError(extractErrorMessage(err, 'Registration failed'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="registration-form-container">
      <h3>Register New User</h3>
      {error && <div className="form-error">{error}</div>}
      
      <form onSubmit={handleSubmit} className="registration-form">
        <div className="form-row">
          <div className="form-group">
            <label>Name *</label>
            <input
              type="text"
              name="name"
              value={formData.name}
              onChange={handleChange}
              required
              placeholder="Full Name"
              data-testid="reg-name-input"
            />
          </div>
          <div className="form-group">
            <label>Role *</label>
            <select name="role" value={formData.role} onChange={handleChange} required data-testid="reg-role-select">
              <option value="student">Student</option>
              <option value="teacher">Teacher</option>
              <option value="maintenance">Maintenance</option>
            </select>
          </div>
        </div>

        <div className="form-row">
          <div className="form-group">
            <label>Phone Number *</label>
            <input
              type="tel"
              name="phone"
              value={formData.phone}
              onChange={handleChange}
              required
              placeholder="10-digit phone"
              pattern="[0-9]{10}"
              data-testid="reg-phone-input"
            />
          </div>
          <div className="form-group">
            <label>Roll Number / ID *</label>
            <input
              type="text"
              name="roll_no"
              value={formData.roll_no}
              onChange={handleChange}
              required
              placeholder={formData.role === 'student' ? 'e.g., S001' : formData.role === 'teacher' ? 'e.g., T001' : 'e.g., M001'}
              data-testid="reg-rollno-input"
            />
          </div>
        </div>

        <div className="form-row">
          <div className="form-group">
            <label>Email</label>
            <input
              type="email"
              name="email"
              value={formData.email}
              onChange={handleChange}
              placeholder="email@example.com"
              data-testid="reg-email-input"
            />
          </div>
          {/* School field for teacher (text input, mandatory) */}
          {formData.role === 'teacher' && (
            <div className="form-group">
              <label>School Name *</label>
              <input
                type="text"
                name="school_name"
                value={formData.school_name}
                onChange={handleChange}
                required
                placeholder="Enter School Name"
                data-testid="reg-school-input"
              />
            </div>
          )}
          {/* For maintenance, optional school */}
          {formData.role === 'maintenance' && (
            <div className="form-group">
              <label>School/Organization</label>
              <input
                type="text"
                name="school_name"
                value={formData.school_name}
                onChange={handleChange}
                placeholder="School or Organization Name"
              />
            </div>
          )}
        </div>

        {formData.role === 'student' && (
          <>
            <div className="form-row">
              <div className="form-group">
                <label>School Name *</label>
                {loadingSchools ? (
                  <div className="loading-schools">Loading schools...</div>
                ) : availableSchools.length === 0 ? (
                  <div className="no-schools-message" data-testid="no-schools-message">
                    <p className="warning-text">Your school is not registered with us. Contact Admin for further help.</p>
                    <p className="hint-text">A teacher from your school must be registered first.</p>
                  </div>
                ) : (
                  <select 
                    name="school_name" 
                    value={formData.school_name} 
                    onChange={handleChange} 
                    required
                    data-testid="reg-school-select"
                  >
                    <option value="">Select School</option>
                    {availableSchools.map(school => (
                      <option key={school} value={school}>{school}</option>
                    ))}
                  </select>
                )}
              </div>
              <div className="form-group">
                <label>Standard (Class) *</label>
                <select name="standard" value={formData.standard} onChange={handleChange} required data-testid="reg-standard-select">
                  <option value="">Select Class</option>
                  {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12].map(n => (
                    <option key={n} value={n}>Class {n}</option>
                  ))}
                </select>
              </div>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label>Gender *</label>
                <select name="gender" value={formData.gender} onChange={handleChange} required data-testid="reg-gender-select">
                  <option value="male">Male</option>
                  <option value="female">Female</option>
                  <option value="other">Other</option>
                </select>
              </div>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label>Parent's Phone</label>
                <input
                  type="tel"
                  name="parent_phone"
                  value={formData.parent_phone}
                  onChange={handleChange}
                  placeholder="Parent's phone (optional)"
                  pattern="[0-9]{10}"
                />
              </div>
            </div>
          </>
        )}

        <div className="form-row">
          <div className="form-group">
            <label>Password *</label>
            <input
              type="password"
              name="password"
              value={formData.password}
              onChange={handleChange}
              required
              placeholder="Min 6 characters"
              minLength={6}
              data-testid="reg-password-input"
            />
          </div>
          <div className="form-group">
            <label>Confirm Password *</label>
            <input
              type="password"
              name="confirmPassword"
              value={formData.confirmPassword}
              onChange={handleChange}
              required
              placeholder="Confirm password"
              data-testid="reg-confirm-password-input"
            />
          </div>
        </div>

        <div className="form-row">
          <div className="form-group checkbox-group">
            <label>
              <input
                type="checkbox"
                name="is_active"
                checked={formData.is_active}
                onChange={handleChange}
              />
              <span>Account Active (can login)</span>
            </label>
          </div>
        </div>

        <div className="form-actions">
          <button type="button" className="btn-cancel" onClick={onCancel}>Cancel</button>
          <button 
            type="submit" 
            className="btn-submit" 
            disabled={loading || (formData.role === 'student' && availableSchools.length === 0)}
            data-testid="reg-submit-btn"
          >
            {loading ? 'Registering...' : 'Register User'}
          </button>
        </div>
      </form>
    </div>
  );
};

// Bulk Registration Component
const BulkRegistration = ({ onSuccess, onCancel }) => {
  const [students, setStudents] = useState([{
    name: '', school_name: '', standard: '', roll_no: '', gender: 'male',
    phone: '', email: '', parent_phone: '', password: '', is_active: true, role: 'student'
  }]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [results, setResults] = useState(null);

  const addRow = () => {
    setStudents([...students, {
      name: '', school_name: students[0]?.school_name || '', standard: students[0]?.standard || '',
      roll_no: '', gender: 'male', phone: '', email: '', parent_phone: '',
      password: '', is_active: true, role: 'student'
    }]);
  };

  const removeRow = (index) => {
    if (students.length > 1) {
      setStudents(students.filter((_, i) => i !== index));
    }
  };

  const updateStudent = (index, field, value) => {
    const updated = [...students];
    updated[index][field] = value;
    setStudents(updated);
  };

  const handleBulkSubmit = async () => {
    setError('');
    setResults(null);

    // Validate all students
    for (let i = 0; i < students.length; i++) {
      const s = students[i];
      if (!s.name || !s.phone || !s.password || !s.roll_no || !s.standard || !s.school_name) {
        setError(`Row ${i + 1}: Please fill all required fields`);
        return;
      }
      if (s.password.length < 6) {
        setError(`Row ${i + 1}: Password must be at least 6 characters`);
        return;
      }
    }

    setLoading(true);
    try {
      const payload = {
        students: students.map(s => ({
          ...s,
          standard: parseInt(s.standard),
          parent_phone: s.parent_phone || s.phone
        }))
      };

      const response = await axios.post(`${API}/admin/bulk-register`, payload, { withCredentials: true });
      setResults(response.data);
      if (response.data.failure_count === 0) {
        setTimeout(() => onSuccess(response.data), 2000);
      }
    } catch (err) {
      setError(extractErrorMessage(err, 'Bulk registration failed'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bulk-registration-container">
      <h3>Bulk Student Registration</h3>
      {error && <div className="form-error">{error}</div>}
      
      {results && (
        <div className={`bulk-results ${results.failure_count > 0 ? 'has-errors' : 'success'}`}>
          <p>{results.success_count} registered successfully, {results.failure_count} failed</p>
          {results.results.filter(r => r.status === 'failed').map((r, i) => (
            <div key={i} className="result-error">
              {r.name} ({r.phone}): {r.error}
            </div>
          ))}
        </div>
      )}

      <div className="bulk-table-container">
        <table className="bulk-table">
          <thead>
            <tr>
              <th>Name *</th>
              <th>Phone *</th>
              <th>Roll No *</th>
              <th>Class *</th>
              <th>School *</th>
              <th>Gender</th>
              <th>Password *</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {students.map((student, index) => (
              <tr key={index}>
                <td>
                  <input
                    type="text"
                    value={student.name}
                    onChange={(e) => updateStudent(index, 'name', e.target.value)}
                    placeholder="Name"
                  />
                </td>
                <td>
                  <input
                    type="tel"
                    value={student.phone}
                    onChange={(e) => updateStudent(index, 'phone', e.target.value)}
                    placeholder="Phone"
                    pattern="[0-9]{10}"
                  />
                </td>
                <td>
                  <input
                    type="text"
                    value={student.roll_no}
                    onChange={(e) => updateStudent(index, 'roll_no', e.target.value)}
                    placeholder="Roll No"
                  />
                </td>
                <td>
                  <select
                    value={student.standard}
                    onChange={(e) => updateStudent(index, 'standard', e.target.value)}
                  >
                    <option value="">Class</option>
                    {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12].map(n => (
                      <option key={n} value={n}>{n}</option>
                    ))}
                  </select>
                </td>
                <td>
                  <input
                    type="text"
                    value={student.school_name}
                    onChange={(e) => updateStudent(index, 'school_name', e.target.value)}
                    placeholder="School"
                  />
                </td>
                <td>
                  <select
                    value={student.gender}
                    onChange={(e) => updateStudent(index, 'gender', e.target.value)}
                  >
                    <option value="male">M</option>
                    <option value="female">F</option>
                    <option value="other">O</option>
                  </select>
                </td>
                <td>
                  <input
                    type="password"
                    value={student.password}
                    onChange={(e) => updateStudent(index, 'password', e.target.value)}
                    placeholder="Password"
                  />
                </td>
                <td>
                  <button 
                    type="button" 
                    className="btn-remove-row"
                    onClick={() => removeRow(index)}
                    disabled={students.length === 1}
                  >
                    X
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="bulk-actions">
        <button type="button" className="btn-add-row" onClick={addRow}>
          + Add Row
        </button>
      </div>

      <div className="form-actions">
        <button type="button" className="btn-cancel" onClick={onCancel}>Cancel</button>
        <button type="button" className="btn-submit" onClick={handleBulkSubmit} disabled={loading}>
          {loading ? 'Registering...' : `Register ${students.length} User(s)`}
        </button>
      </div>
    </div>
  );
};

// User List Component with School Grouping (Accordion)
const UserList = ({ users, onRefresh, onToggleActive, onDelete }) => {
  const [filter, setFilter] = useState({ role: '', standard: '', is_active: '' });
  const [expandedSchools, setExpandedSchools] = useState({});
  const [viewMode, setViewMode] = useState('school'); // 'school' or 'flat'

  const filteredUsers = users.filter(user => {
    if (filter.role && user.role !== filter.role) return false;
    if (filter.standard && user.standard !== parseInt(filter.standard)) return false;
    if (filter.is_active !== '' && user.is_active !== (filter.is_active === 'true')) return false;
    return true;
  });

  // Group users by school
  const groupedBySchool = filteredUsers.reduce((groups, user) => {
    const school = user.school_name || 'No School Assigned';
    if (!groups[school]) {
      groups[school] = { teachers: [], students: [], maintenance: [] };
    }
    if (user.role === 'teacher') {
      groups[school].teachers.push(user);
    } else if (user.role === 'student') {
      groups[school].students.push(user);
    } else {
      groups[school].maintenance.push(user);
    }
    return groups;
  }, {});

  // Sort schools alphabetically, but put "No School Assigned" at the end
  const sortedSchools = Object.keys(groupedBySchool).sort((a, b) => {
    if (a === 'No School Assigned') return 1;
    if (b === 'No School Assigned') return -1;
    return a.localeCompare(b);
  });

  const toggleSchool = (school) => {
    setExpandedSchools(prev => ({
      ...prev,
      [school]: !prev[school]
    }));
  };

  const expandAll = () => {
    const expanded = {};
    sortedSchools.forEach(school => { expanded[school] = true; });
    setExpandedSchools(expanded);
  };

  const collapseAll = () => {
    setExpandedSchools({});
  };

  const renderUserRow = (user) => (
    <tr key={user.id} className={!user.is_active ? 'inactive-row' : ''}>
      <td>{user.name || '-'}</td>
      <td>{user.phone}</td>
      <td>{user.roll_no || '-'}</td>
      <td>{user.standard || '-'}</td>
      <td>
        <span className={`role-badge ${user.role}`}>
          {user.role}
        </span>
      </td>
      <td>
        <span className={`status-badge ${user.is_active ? 'active' : 'inactive'}`}>
          {user.is_active ? 'Active' : 'Inactive'}
        </span>
      </td>
      <td className="action-buttons">
        <button
          className={`btn-toggle ${user.is_active ? 'deactivate' : 'activate'}`}
          onClick={() => onToggleActive(user.id, user.is_active)}
        >
          {user.is_active ? 'Deactivate' : 'Activate'}
        </button>
        <button
          className="btn-delete"
          onClick={() => {
            if (window.confirm(`Delete ${user.name || user.phone}?`)) {
              onDelete(user.id);
            }
          }}
        >
          Delete
        </button>
      </td>
    </tr>
  );

  return (
    <div className="user-list-container">
      <div className="list-header">
        <h3>Registered Users ({filteredUsers.length})</h3>
        <div className="header-actions">
          <div className="view-toggle-group">
            <button 
              className={`view-btn ${viewMode === 'school' ? 'active' : ''}`}
              onClick={() => setViewMode('school')}
              data-testid="view-by-school-btn"
            >
              By School
            </button>
            <button 
              className={`view-btn ${viewMode === 'flat' ? 'active' : ''}`}
              onClick={() => setViewMode('flat')}
              data-testid="view-flat-btn"
            >
              All Users
            </button>
          </div>
          <button className="btn-refresh" onClick={onRefresh}>Refresh</button>
        </div>
      </div>

      <div className="list-filters">
        <select value={filter.role} onChange={(e) => setFilter({ ...filter, role: e.target.value })}>
          <option value="">All Roles</option>
          <option value="student">Students</option>
          <option value="teacher">Teachers</option>
          <option value="maintenance">Maintenance</option>
        </select>
        <select value={filter.standard} onChange={(e) => setFilter({ ...filter, standard: e.target.value })}>
          <option value="">All Classes</option>
          {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12].map(n => (
            <option key={n} value={n}>Class {n}</option>
          ))}
        </select>
        <select value={filter.is_active} onChange={(e) => setFilter({ ...filter, is_active: e.target.value })}>
          <option value="">All Status</option>
          <option value="true">Active</option>
          <option value="false">Inactive</option>
        </select>
        {viewMode === 'school' && (
          <div className="accordion-controls">
            <button className="btn-expand-all" onClick={expandAll}>Expand All</button>
            <button className="btn-collapse-all" onClick={collapseAll}>Collapse All</button>
          </div>
        )}
      </div>

      {viewMode === 'school' ? (
        <div className="school-accordion" data-testid="school-accordion">
          {sortedSchools.length === 0 ? (
            <div className="no-data">No users found</div>
          ) : (
            sortedSchools.map(school => {
              const schoolData = groupedBySchool[school];
              const totalUsers = schoolData.teachers.length + schoolData.students.length + schoolData.maintenance.length;
              const isExpanded = expandedSchools[school];
              
              return (
                <div key={school} className="school-section" data-testid={`school-section-${school.replace(/\s+/g, '-').toLowerCase()}`}>
                  <div 
                    className={`school-header ${isExpanded ? 'expanded' : ''}`}
                    onClick={() => toggleSchool(school)}
                  >
                    <div className="school-info">
                      <span className="expand-icon">{isExpanded ? '▼' : '▶'}</span>
                      <h4 className="school-name">{school}</h4>
                      <span className="school-stats">
                        {schoolData.teachers.length > 0 && (
                          <span className="stat-badge teachers">{schoolData.teachers.length} Teacher{schoolData.teachers.length !== 1 ? 's' : ''}</span>
                        )}
                        {schoolData.students.length > 0 && (
                          <span className="stat-badge students">{schoolData.students.length} Student{schoolData.students.length !== 1 ? 's' : ''}</span>
                        )}
                        {schoolData.maintenance.length > 0 && (
                          <span className="stat-badge maintenance">{schoolData.maintenance.length} Maintenance</span>
                        )}
                      </span>
                    </div>
                    <span className="total-users">{totalUsers} user{totalUsers !== 1 ? 's' : ''}</span>
                  </div>
                  
                  {isExpanded && (
                    <div className="school-content">
                      {/* Teachers Section */}
                      {schoolData.teachers.length > 0 && (
                        <div className="role-section">
                          <h5 className="role-title">Teachers</h5>
                          <table className="user-table compact">
                            <thead>
                              <tr>
                                <th>Name</th>
                                <th>Phone</th>
                                <th>Roll No</th>
                                <th>Class</th>
                                <th>Role</th>
                                <th>Status</th>
                                <th>Actions</th>
                              </tr>
                            </thead>
                            <tbody>
                              {schoolData.teachers.map(renderUserRow)}
                            </tbody>
                          </table>
                        </div>
                      )}
                      
                      {/* Students Section */}
                      {schoolData.students.length > 0 && (
                        <div className="role-section">
                          <h5 className="role-title">Students</h5>
                          <table className="user-table compact">
                            <thead>
                              <tr>
                                <th>Name</th>
                                <th>Phone</th>
                                <th>Roll No</th>
                                <th>Class</th>
                                <th>Role</th>
                                <th>Status</th>
                                <th>Actions</th>
                              </tr>
                            </thead>
                            <tbody>
                              {schoolData.students.map(renderUserRow)}
                            </tbody>
                          </table>
                        </div>
                      )}
                      
                      {/* Maintenance Section */}
                      {schoolData.maintenance.length > 0 && (
                        <div className="role-section">
                          <h5 className="role-title">Maintenance</h5>
                          <table className="user-table compact">
                            <thead>
                              <tr>
                                <th>Name</th>
                                <th>Phone</th>
                                <th>Roll No</th>
                                <th>Class</th>
                                <th>Role</th>
                                <th>Status</th>
                                <th>Actions</th>
                              </tr>
                            </thead>
                            <tbody>
                              {schoolData.maintenance.map(renderUserRow)}
                            </tbody>
                          </table>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
      ) : (
        <div className="user-table-container">
          <table className="user-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Phone</th>
                <th>Roll No</th>
                <th>Class</th>
                <th>School</th>
                <th>Role</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredUsers.length === 0 ? (
                <tr>
                  <td colSpan="8" className="no-data">No users found</td>
                </tr>
              ) : (
                filteredUsers.map(user => (
                  <tr key={user.id} className={!user.is_active ? 'inactive-row' : ''}>
                    <td>{user.name || '-'}</td>
                    <td>{user.phone}</td>
                    <td>{user.roll_no || '-'}</td>
                    <td>{user.standard || '-'}</td>
                    <td>{user.school_name || '-'}</td>
                    <td>
                      <span className={`role-badge ${user.role}`}>
                        {user.role}
                      </span>
                    </td>
                    <td>
                      <span className={`status-badge ${user.is_active ? 'active' : 'inactive'}`}>
                        {user.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    <td className="action-buttons">
                      <button
                        className={`btn-toggle ${user.is_active ? 'deactivate' : 'activate'}`}
                        onClick={() => onToggleActive(user.id, user.is_active)}
                      >
                        {user.is_active ? 'Deactivate' : 'Activate'}
                      </button>
                      <button
                        className="btn-delete"
                        onClick={() => {
                          if (window.confirm(`Delete ${user.name || user.phone}?`)) {
                            onDelete(user.id);
                          }
                        }}
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

// Edit User Profile Component
const EditUserProfile = ({ onCancel }) => {
  const [searchRollNo, setSearchRollNo] = useState('');
  const [foundUser, setFoundUser] = useState(null);
  const [editData, setEditData] = useState({});
  const [searching, setSearching] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [availableSchools, setAvailableSchools] = useState([]);

  useEffect(() => {
    const fetchSchools = async () => {
      try {
        const res = await axios.get(`${API}/schools/list`, { withCredentials: true });
        setAvailableSchools(res.data.schools || []);
      } catch (err) {
        console.error('Failed to fetch schools:', err);
      }
    };
    fetchSchools();
  }, []);

  const searchUser = async () => {
    if (!searchRollNo.trim()) return;
    setSearching(true);
    setError('');
    setFoundUser(null);
    try {
      const res = await axios.get(`${API}/admin/search-user/${searchRollNo.trim()}`, { withCredentials: true });
      setFoundUser(res.data);
      setEditData({
        name: res.data.name || '',
        school_name: res.data.school_name || '',
        standard: res.data.standard || '',
        role: res.data.role || 'student',
        email: res.data.email || '',
        phone: res.data.phone || '',
        parent_phone: res.data.parent_phone || '',
        gender: res.data.gender || 'other',
        is_active: res.data.is_active !== false,
      });
    } catch (err) {
      setError(extractErrorMessage(err, 'User not found'));
    } finally {
      setSearching(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    setError('');
    setSuccess('');
    try {
      const payload = { ...editData };
      if (payload.standard) payload.standard = parseInt(payload.standard);
      payload.login_phone = payload.phone;
      delete payload.phone;
      const res = await axios.put(`${API}/admin/update-user/${foundUser.roll_no}`, payload, { withCredentials: true });
      setSuccess(res.data.message);
      setFoundUser({ ...foundUser, ...res.data.user });
      setTimeout(() => setSuccess(''), 4000);
    } catch (err) {
      setError(extractErrorMessage(err, 'Update failed'));
    } finally {
      setSaving(false);
    }
  };

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setEditData(prev => ({ ...prev, [name]: type === 'checkbox' ? checked : value }));
  };

  return (
    <div className="form-container" data-testid="edit-user-form">
      <div className="form-header">
        <h3>Edit User Profile</h3>
        <button className="btn-cancel" onClick={onCancel}>Back</button>
      </div>
      <p className="tab-description">Search for a user by roll number and edit their details</p>

      <div className="search-user-section">
        <div className="search-row">
          <input
            type="text"
            placeholder="Enter Roll Number (e.g., S001, teacher4)"
            value={searchRollNo}
            onChange={(e) => setSearchRollNo(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && searchUser()}
            className="search-input"
            data-testid="edit-user-rollno-input"
          />
          <button onClick={searchUser} disabled={searching} className="btn-search" data-testid="edit-user-search-btn">
            {searching ? 'Searching...' : 'Search'}
          </button>
        </div>
      </div>

      {error && <div className="form-error">{error}</div>}
      {success && <div className="form-success" style={{background:'rgba(34,197,94,0.15)',color:'#22c55e',padding:'12px',borderRadius:'8px',marginBottom:'16px',fontWeight:'600'}}>{success}</div>}

      {foundUser && (
        <div className="edit-user-fields" style={{marginTop:'20px'}}>
          <div className="form-row">
            <div className="form-group">
              <label>Name</label>
              <input type="text" name="name" value={editData.name} onChange={handleChange} className="form-input" data-testid="edit-user-name" />
            </div>
            <div className="form-group">
              <label>Roll No</label>
              <input type="text" value={foundUser.roll_no} disabled className="form-input" style={{opacity:0.6}} />
            </div>
          </div>
          <div className="form-row">
            <div className="form-group">
              <label>Role</label>
              <select name="role" value={editData.role} onChange={handleChange} className="form-input" data-testid="edit-user-role">
                <option value="student">Student</option>
                <option value="teacher">Teacher</option>
              </select>
            </div>
            <div className="form-group">
              <label>Standard/Class</label>
              <select name="standard" value={editData.standard} onChange={handleChange} className="form-input" data-testid="edit-user-standard">
                <option value="">N/A</option>
                {[1,2,3,4,5,6,7,8,9,10,11,12].map(s => <option key={s} value={s}>Class {s}</option>)}
              </select>
            </div>
          </div>
          <div className="form-row">
            <div className="form-group">
              <label>School Name</label>
              <select name="school_name" value={editData.school_name} onChange={handleChange} className="form-input" data-testid="edit-user-school">
                <option value="">Select School</option>
                {availableSchools.map(s => <option key={s} value={s}>{s}</option>)}
                {editData.school_name && !availableSchools.includes(editData.school_name) && (
                  <option value={editData.school_name}>{editData.school_name}</option>
                )}
              </select>
            </div>
            <div className="form-group">
              <label>Gender</label>
              <select name="gender" value={editData.gender} onChange={handleChange} className="form-input" data-testid="edit-user-gender">
                <option value="male">Male</option>
                <option value="female">Female</option>
                <option value="other">Other</option>
              </select>
            </div>
          </div>
          <div className="form-row">
            <div className="form-group">
              <label>Phone</label>
              <input type="text" name="phone" value={editData.phone} onChange={handleChange} className="form-input" data-testid="edit-user-phone" />
            </div>
            <div className="form-group">
              <label>Parent Phone</label>
              <input type="text" name="parent_phone" value={editData.parent_phone} onChange={handleChange} className="form-input" data-testid="edit-user-parent-phone" />
            </div>
          </div>
          <div className="form-row">
            <div className="form-group">
              <label>Email</label>
              <input type="text" name="email" value={editData.email} onChange={handleChange} className="form-input" data-testid="edit-user-email" />
            </div>
            <div className="form-group" style={{display:'flex',alignItems:'center',gap:'10px',paddingTop:'24px'}}>
              <input type="checkbox" name="is_active" checked={editData.is_active} onChange={handleChange} data-testid="edit-user-active" />
              <label style={{margin:0}}>Active</label>
            </div>
          </div>
          <button onClick={handleSave} disabled={saving} className="btn-submit" data-testid="edit-user-save-btn" style={{marginTop:'16px',width:'100%'}}>
            {saving ? 'Saving...' : 'Save Changes'}
          </button>
        </div>
      )}
    </div>
  );
};

// Main Admin Dashboard Component
const AdminDashboard = ({ onLogout }) => {
  const [activeTab, setActiveTab] = useState('users');
  const [showSingleForm, setShowSingleForm] = useState(false);
  const [showBulkForm, setShowBulkForm] = useState(false);
  const [showEditForm, setShowEditForm] = useState(false);
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');

  useEffect(() => {
    fetchUsers();
  }, []);

  const fetchUsers = async () => {
    setLoading(true);
    try {
      const response = await axios.get(`${API}/admin/users`, { withCredentials: true });
      setUsers(response.data.users || []);
    } catch (err) {
      console.error('Failed to fetch users:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleToggleActive = async (userId, currentStatus) => {
    try {
      await axios.put(`${API}/admin/user/${userId}/toggle-active`, {}, { withCredentials: true });
      setMessage(`User ${currentStatus ? 'deactivated' : 'activated'} successfully`);
      fetchUsers();
      setTimeout(() => setMessage(''), 3000);
    } catch (err) {
      setMessage(extractErrorMessage(err, 'Action failed'));
    }
  };

  const handleDelete = async (userId) => {
    try {
      await axios.delete(`${API}/admin/user/${userId}`, { withCredentials: true });
      setMessage('User deleted successfully');
      fetchUsers();
      setTimeout(() => setMessage(''), 3000);
    } catch (err) {
      setMessage(extractErrorMessage(err, 'Delete failed'));
    }
  };

  const handleRegistrationSuccess = (data) => {
    setMessage(data.message || 'Registration successful');
    setShowSingleForm(false);
    setShowBulkForm(false);
    setShowEditForm(false);
    fetchUsers();
    setTimeout(() => setMessage(''), 3000);
  };

  // Reset Password Component
  const ResetPasswordTab = () => {
    const [searchRollNo, setSearchRollNo] = useState('');
    const [foundUser, setFoundUser] = useState(null);
    const [newPassword, setNewPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');
    const [searching, setSearching] = useState(false);
    const [resetting, setResetting] = useState(false);
    const [error, setError] = useState('');
    const [success, setSuccess] = useState('');

    const searchUser = async () => {
      if (!searchRollNo.trim()) {
        setError('Please enter a roll number');
        return;
      }
      setSearching(true);
      setError('');
      setSuccess('');
      setFoundUser(null);
      
      try {
        const response = await axios.get(`${API}/admin/search-user/${searchRollNo}`, { withCredentials: true });
        setFoundUser(response.data);
      } catch (err) {
        setError(extractErrorMessage(err, 'User not found'));
      } finally {
        setSearching(false);
      }
    };

    const handleResetPassword = async () => {
      if (!newPassword || !confirmPassword) {
        setError('Please enter new password');
        return;
      }
      if (newPassword !== confirmPassword) {
        setError('Passwords do not match');
        return;
      }
      if (newPassword.length < 6) {
        setError('Password must be at least 6 characters');
        return;
      }
      
      setResetting(true);
      setError('');
      setSuccess('');
      
      try {
        const response = await axios.post(`${API}/admin/reset-password`, {
          roll_no: searchRollNo,
          new_password: newPassword
        }, { withCredentials: true });
        setSuccess(response.data.message);
        setNewPassword('');
        setConfirmPassword('');
      } catch (err) {
        setError(extractErrorMessage(err, 'Failed to reset password'));
      } finally {
        setResetting(false);
      }
    };

    return (
      <div className="reset-password-container">
        <h3>Reset User Password</h3>
        <p className="tab-description">Search for a user by roll number and reset their password without OTP</p>
        
        <div className="search-user-section">
          <div className="search-row">
            <input
              type="text"
              placeholder="Enter Roll Number (e.g., S001, T001)"
              value={searchRollNo}
              onChange={(e) => setSearchRollNo(e.target.value)}
              className="search-input"
              data-testid="search-rollno-input"
            />
            <button 
              onClick={searchUser} 
              disabled={searching}
              className="btn-search"
              data-testid="search-user-btn"
            >
              {searching ? 'Searching...' : 'Search'}
            </button>
          </div>
        </div>

        {error && <div className="form-error">{error}</div>}
        {success && <div className="form-success">{success}</div>}

        {foundUser && (
          <div className="user-found-card">
            <div className="user-info">
              <h4>{foundUser.name}</h4>
              <div className="user-details">
                <span><strong>Roll No:</strong> {foundUser.roll_no}</span>
                <span><strong>Role:</strong> {foundUser.role}</span>
                <span><strong>Class:</strong> {foundUser.standard || 'N/A'}</span>
                <span><strong>School:</strong> {foundUser.school_name || 'N/A'}</span>
                <span><strong>Status:</strong> {foundUser.is_active ? 'Active' : 'Inactive'}</span>
              </div>
            </div>
            
            <div className="reset-form">
              <div className="form-row">
                <input
                  type="password"
                  placeholder="New Password (min 6 chars)"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  className="form-input"
                  data-testid="new-password-input"
                />
                <input
                  type="password"
                  placeholder="Confirm Password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className="form-input"
                  data-testid="confirm-password-input"
                />
              </div>
              <button 
                onClick={handleResetPassword}
                disabled={resetting}
                className="btn-reset"
                data-testid="reset-password-btn"
              >
                {resetting ? 'Resetting...' : 'Reset Password'}
              </button>
            </div>
          </div>
        )}
      </div>
    );
  };

  // Impersonate (Login As User) Component
  const ImpersonateTab = ({ onImpersonate }) => {
    const [searchRollNo, setSearchRollNo] = useState('');
    const [foundUser, setFoundUser] = useState(null);
    const [searching, setSearching] = useState(false);
    const [impersonating, setImpersonating] = useState(false);
    const [error, setError] = useState('');

    const searchUser = async () => {
      if (!searchRollNo.trim()) {
        setError('Please enter a roll number');
        return;
      }
      setSearching(true);
      setError('');
      setFoundUser(null);
      
      try {
        const response = await axios.get(`${API}/admin/search-user/${searchRollNo}`, { withCredentials: true });
        setFoundUser(response.data);
      } catch (err) {
        setError(extractErrorMessage(err, 'User not found'));
      } finally {
        setSearching(false);
      }
    };

    const handleImpersonate = async () => {
      setImpersonating(true);
      setError('');
      
      try {
        const response = await axios.post(`${API}/admin/impersonate`, {
          roll_no: searchRollNo
        }, { withCredentials: true });
        // Call parent handler to switch user context
        onImpersonate(response.data.user);
      } catch (err) {
        setError(extractErrorMessage(err, 'Failed to login as user'));
        setImpersonating(false);
      }
    };

    return (
      <div className="impersonate-container">
        <h3>Login As User</h3>
        <p className="tab-description">Search for a user by roll number and login as them to view their profile</p>
        
        <div className="search-user-section">
          <div className="search-row">
            <input
              type="text"
              placeholder="Enter Roll Number (e.g., S001, T001)"
              value={searchRollNo}
              onChange={(e) => setSearchRollNo(e.target.value)}
              className="search-input"
              data-testid="impersonate-rollno-input"
            />
            <button 
              onClick={searchUser} 
              disabled={searching}
              className="btn-search"
              data-testid="search-impersonate-btn"
            >
              {searching ? 'Searching...' : 'Search'}
            </button>
          </div>
        </div>

        {error && <div className="form-error">{error}</div>}

        {foundUser && (
          <div className="user-found-card">
            <div className="user-info">
              <h4>{foundUser.name}</h4>
              <div className="user-details">
                <span><strong>Roll No:</strong> {foundUser.roll_no}</span>
                <span><strong>Role:</strong> {foundUser.role}</span>
                <span><strong>Class:</strong> {foundUser.standard || 'N/A'}</span>
                <span><strong>School:</strong> {foundUser.school_name || 'N/A'}</span>
                <span><strong>Status:</strong> {foundUser.is_active ? 'Active' : 'Inactive'}</span>
              </div>
            </div>
            
            <button 
              onClick={handleImpersonate}
              disabled={impersonating || !foundUser.is_active}
              className="btn-impersonate"
              data-testid="impersonate-btn"
            >
              {impersonating ? 'Logging in...' : `Login as ${foundUser.name}`}
            </button>
            {!foundUser.is_active && (
              <p className="warning-text">This user is deactivated. Activate them first to login.</p>
            )}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="admin-dashboard" data-testid="admin-dashboard">
      <header className="admin-header">
        <div className="admin-title">
          <h1>Admin Dashboard</h1>
          <span className="admin-badge">Administrator</span>
        </div>
        <button className="btn-logout" onClick={onLogout}>Logout</button>
      </header>

      {message && (
        <div className={`admin-message ${message.includes('failed') || message.includes('error') ? 'error' : 'success'}`}>
          {message}
        </div>
      )}

      <div className="admin-content">
        <div className="admin-tabs">
          <button
            className={`tab-btn ${activeTab === 'users' ? 'active' : ''}`}
            onClick={() => setActiveTab('users')}
          >
            User Management
          </button>
          <button
            className={`tab-btn ${activeTab === 'register' ? 'active' : ''}`}
            onClick={() => setActiveTab('register')}
          >
            Register Students
          </button>
          <button
            className={`tab-btn ${activeTab === 'resetPassword' ? 'active' : ''}`}
            onClick={() => setActiveTab('resetPassword')}
          >
            Reset Password
          </button>
          <button
            className={`tab-btn ${activeTab === 'impersonate' ? 'active' : ''}`}
            onClick={() => setActiveTab('impersonate')}
          >
            Login As User
          </button>
        </div>

        {activeTab === 'users' && (
          <UserList
            users={users}
            onRefresh={fetchUsers}
            onToggleActive={handleToggleActive}
            onDelete={handleDelete}
          />
        )}

        {activeTab === 'register' && !showSingleForm && !showBulkForm && !showEditForm && (
          <div className="register-options">
            <div className="register-card" onClick={() => setShowSingleForm(true)}>
              <div className="card-icon">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
                  <circle cx="12" cy="7" r="4"/>
                </svg>
              </div>
              <h3>Single Registration</h3>
              <p>Register one student/teacher at a time with complete details</p>
            </div>
            <div className="register-card" onClick={() => setShowBulkForm(true)}>
              <div className="card-icon">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
                  <circle cx="9" cy="7" r="4"/>
                  <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
                  <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
                </svg>
              </div>
              <h3>Bulk Registration</h3>
              <p>Register multiple students at once using a table format</p>
            </div>
            <div className="register-card" onClick={() => setShowEditForm(true)} data-testid="edit-user-card">
              <div className="card-icon">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                  <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                </svg>
              </div>
              <h3>Edit User Profile</h3>
              <p>Search and update details of any registered user</p>
            </div>
          </div>
        )}

        {activeTab === 'register' && showSingleForm && (
          <StudentRegistrationForm
            onSuccess={handleRegistrationSuccess}
            onCancel={() => setShowSingleForm(false)}
          />
        )}

        {activeTab === 'register' && showBulkForm && (
          <BulkRegistration
            onSuccess={handleRegistrationSuccess}
            onCancel={() => setShowBulkForm(false)}
          />
        )}

        {activeTab === 'register' && showEditForm && (
          <EditUserProfile
            onCancel={() => setShowEditForm(false)}
          />
        )}

        {activeTab === 'resetPassword' && (
          <ResetPasswordTab />
        )}

        {activeTab === 'impersonate' && (
          <ImpersonateTab onImpersonate={(user) => {
            // When admin impersonates a user, we need to reload the app with the new user context
            window.location.reload();
          }} />
        )}
      </div>
    </div>
  );
};

export default AdminDashboard;
