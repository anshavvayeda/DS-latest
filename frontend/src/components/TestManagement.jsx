import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import './TestManagement.css';

const API = process.env.REACT_APP_BACKEND_URL ? `${process.env.REACT_APP_BACKEND_URL}/api` : '/api';

const TestManagement = ({ subjectId, standard, contentType = 'test' }) => {
  const [tests, setTests] = useState([]);
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [formData, setFormData] = useState({
    title: '',
    submissionDeadline: '',
    durationMinutes: contentType === 'test' ? 60 : 0,  // Duration only for tests
    testFile: null,
    modelAnswers: null,
    markingSchema: null  // NEW: Marking schema file
  });
  
  // EXTRACTION PROGRESS STATE
  const [showProgressModal, setShowProgressModal] = useState(false);
  const [extractionContentId, setExtractionContentId] = useState(null);
  const [extractionProgress, setExtractionProgress] = useState(0);
  const [extractionStage, setExtractionStage] = useState('');
  const [extractionMessage, setExtractionMessage] = useState('');
  const [extractionElapsed, setExtractionElapsed] = useState(0);
  const [extractionFailed, setExtractionFailed] = useState(false);
  const [extractionError, setExtractionError] = useState('');
  const [canRetry, setCanRetry] = useState(false);
  
  // REF for poll interval - prevents memory leaks
  const pollIntervalRef = useRef(null);

  useEffect(() => {
    console.log('TestManagement mounted/updated:', { subjectId, standard });
    if (subjectId && standard) {
      loadItems();
    }
  }, [subjectId, standard]);
  
  // CLEANUP: Clear polling interval on unmount
  useEffect(() => {
    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
        console.log('[CLEANUP] Polling interval cleared on unmount');
      }
    };
  }, []);

  const loadItems = async () => {
    try {
      console.log(`Loading ${contentType}s for:`, { subjectId, standard });
      const endpoint = contentType === 'test' 
        ? `${API}/tests/subject/${subjectId}/standard/${standard}`
        : `${API}/homework?subject_id=${subjectId}&standard=${standard}`;
      const response = await axios.get(endpoint, {
        withCredentials: true
      });
      console.log(`${contentType}s loaded:`, response.data);
      setTests(response.data.tests || response.data.homework || response.data || []);
    } catch (error) {
      console.error(`Error loading ${contentType}s:`, error);
      console.error('Error details:', error.response?.data);
      setTests([]);
    }
  };

  const handleFileChange = (e, field) => {
    const file = e.target.files[0];
    setFormData(prev => ({ ...prev, [field]: file }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    // Validate fields
    const itemName = contentType === 'test' ? 'test' : 'homework';
    if (!formData.title) {
      alert(`Please enter ${itemName} title`);
      return;
    }
    if (!formData.testFile) {
      alert(`Please upload ${itemName} PDF`);
      return;
    }
    
    // Tests require deadline and duration, homework needs deadline only
    if (contentType === 'test') {
      if (!formData.submissionDeadline) {
        alert('Please select submission deadline');
        return;
      }
      if (!formData.durationMinutes || formData.durationMinutes < 5) {
        alert('Please enter valid duration (at least 5 minutes)');
        return;
      }
    }
    
    setUploading(true);

    try {
      const formDataToSend = new FormData();
      formDataToSend.append('subject_id', subjectId);
      formDataToSend.append('standard', standard);
      formDataToSend.append('title', formData.title);
      formDataToSend.append('file', formData.testFile);
      
      if (contentType === 'test') {
        // Convert datetime-local format to ISO string with timezone
        const deadlineDate = new Date(formData.submissionDeadline);
        const isoDeadline = deadlineDate.toISOString();
        formDataToSend.append('submission_deadline', isoDeadline);
        formDataToSend.append('duration_minutes', formData.durationMinutes);
        if (formData.modelAnswers) {
          formDataToSend.append('model_answers', formData.modelAnswers);
        }
        // NEW: Add marking schema if provided
        if (formData.markingSchema) {
          formDataToSend.append('marking_schema', formData.markingSchema);
        }
      } else {
        // Homework: model answers as separate field
        if (formData.modelAnswers) {
          formDataToSend.append('model_answers_file', formData.modelAnswers);
        }
      }

      console.log(`Uploading ${itemName}...`);

      const endpoint = contentType === 'test' ? `${API}/tests` : `${API}/homework`;
      const response = await axios.post(endpoint, formDataToSend, {
        withCredentials: true,
        headers: { 'Content-Type': 'multipart/form-data' }
      });

      console.log('Upload response:', response.data);
      
      if (response.data.status === 'processing') {
        // Close upload modal
        setShowUploadModal(false);
        
        // Reset form
        setFormData({
          title: '',
          submissionDeadline: '',
          durationMinutes: contentType === 'test' ? 60 : 0,
          testFile: null,
          modelAnswers: null,
          markingSchema: null  // NEW: Reset marking schema
        });
        
        // STRICT: Parse content ID based on contentType
        let contentId;
        if (contentType === 'test') {
          contentId = response.data.test_id;
          if (!contentId) {
            throw new Error('Backend did not return test_id');
          }
        } else if (contentType === 'homework') {
          contentId = response.data.homework_id;
          if (!contentId) {
            throw new Error('Backend did not return homework_id');
          }
        } else {
          throw new Error(`Unknown content type: ${contentType}`);
        }
        
        // Show progress modal
        setExtractionContentId(contentId);
        setExtractionProgress(response.data.extraction_progress || 0);
        setExtractionStage(response.data.extraction_stage || 'UPLOADED');
        setExtractionMessage(response.data.message || 'Starting extraction...');
        setExtractionElapsed(0);
        setExtractionFailed(false);
        setExtractionError('');
        setCanRetry(false);
        setShowProgressModal(true);
        
        // Start polling for extraction status
        startExtractionPolling(contentId);
      } else {
        // Unexpected response
        alert('Upload successful but extraction status unknown. Please refresh.');
        loadItems();
      }
      
    } catch (error) {
      console.error(`Error creating ${itemName}:`, error);
      const errorMsg = error.response?.data?.detail || error.response?.data?.message || error.message || `Failed to create ${itemName}`;
      alert(`Failed to upload ${itemName}: ${errorMsg}`);
    } finally {
      setUploading(false);
    }
  };
  
  // Polling logic for extraction progress
  const startExtractionPolling = (contentId) => {
    // CRITICAL: Clear any existing interval before starting a new one
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
    
    // Guard against duplicate completion alerts
    let completionAlertShown = false;
    
    const pollInterval = setInterval(async () => {
      try {
        const endpoint = contentType === 'test' 
          ? `${API}/tests/${contentId}/extraction-status`
          : `${API}/homework/${contentId}/extraction-status`;
        const response = await axios.get(endpoint, {
          withCredentials: true
        });
        
        const data = response.data;
        
        // Update progress UI (ensure 100% for completed)
        const progress = data.extraction_stage === 'COMPLETED' ? 100 : (data.extraction_progress || 0);
        setExtractionProgress(progress);
        setExtractionStage(data.extraction_stage || '');
        setExtractionMessage(data.extraction_stage_message || '');
        setExtractionElapsed(data.elapsed_seconds || 0);
        setCanRetry(!!data.can_retry);
        
        // Terminal states - stop polling
        if (!data.should_poll) {
          clearInterval(pollInterval);
          pollIntervalRef.current = null;
          
          // SUCCESS: Completed
          if (data.extraction_stage === 'COMPLETED' && data.extraction_status === 'completed') {
            if (!completionAlertShown) {
              completionAlertShown = true;
              
              const itemName = contentType === 'test' ? 'Test' : 'Homework';
              
              // Check for extraction mismatch
              if (data.extraction_mismatch) {
                setExtractionFailed(true);
                setExtractionError("Extraction completed but questions.json missing. Contact teacher.");
                alert(`❌ ${itemName} extraction completed but questions.json missing. Contact teacher.`);
                return;
              }
              
              setShowProgressModal(false);
              
              // Only show number if it's a valid integer > 0
              const count = data.questions_extracted_count;
              let message;
              if (typeof count === 'number' && count > 0) {
                message = `✅ ${itemName} ready! ${count} questions extracted successfully.`;
              } else {
                message = `✅ ${itemName} ready! Questions extracted successfully.`;
              }
              alert(message);
              
              // Refresh the correct list
              loadItems();
            }
          } 
          // FAILURE: Failed/Timeout/Stuck
          else if (data.extraction_stage === 'FAILED' || data.extraction_stage === 'TIMEOUT' || data.is_stuck) {
            setExtractionFailed(true);
            setExtractionError(data.error || 'Extraction failed');
            setCanRetry(!!data.can_retry);
          }
        }
        
      } catch (error) {
        console.error('Error polling extraction status:', error);
        clearInterval(pollInterval);
        pollIntervalRef.current = null;
        setExtractionFailed(true);
        setExtractionError('Failed to check extraction status');
      }
    }, 3000);
    
    pollIntervalRef.current = pollInterval;
  };
  
  const handleRetryExtraction = async () => {
    try {
      setExtractionFailed(false);
      setExtractionError('');
      setExtractionProgress(0);
      setCanRetry(false);
      
      const endpoint = contentType === 'test'
        ? `${API}/tests/${extractionContentId}/retry-extraction`
        : `${API}/homework/${extractionContentId}/retry-extraction`;
      const response = await axios.post(endpoint, {}, {
        withCredentials: true
      });
      
      console.log('Retry extraction started:', response.data);
      
      // Restart polling (startExtractionPolling will clear any existing interval)
      startExtractionPolling(extractionContentId);
      
    } catch (error) {
      console.error('Error retrying extraction:', error);
      const errorMsg = error.response?.data?.detail || error.message;
      
      // Handle 409 (already processing) gracefully
      if (error.response?.status === 409) {
        alert('Extraction is already in progress. Please wait.');
        // Restart polling to catch up with current status
        startExtractionPolling(extractionContentId);
      } else {
        alert('Failed to retry extraction: ' + errorMsg);
        setExtractionFailed(true);
        setExtractionError(errorMsg);
      }
    }
  };
  
  const handleCloseProgressModal = () => {
    // CLEANUP: Stop polling using ref
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
      console.log('[CLEANUP] Polling interval cleared on modal close');
    }
    setShowProgressModal(false);
    loadItems();  // Refresh list
  };

  const handleDelete = async (testId) => {
    const itemName = contentType === 'test' ? 'test' : 'homework';
    if (!window.confirm(`Are you sure you want to delete this ${itemName}?`)) return;

    try {
      const endpoint = contentType === 'test' ? `${API}/tests/${testId}` : `${API}/homework/${testId}`;
      await axios.delete(endpoint, { withCredentials: true });
      alert(`${itemName.charAt(0).toUpperCase() + itemName.slice(1)} deleted successfully`);
      loadItems();
    } catch (error) {
      console.error(`Error deleting ${itemName}:`, error);
      alert(`Failed to delete ${itemName}`);
    }
  };

  const formatDeadline = (isoString) => {
    const date = new Date(isoString);
    return date.toLocaleString();
  };

  return (
    <div className="test-management">
      <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', marginBottom: '20px' }}>
        <button 
          onClick={() => setShowUploadModal(true)}
          className="add-btn"
        >
          + Upload {contentType === 'test' ? 'Test' : 'Homework'}
        </button>
      </div>

      {tests.length === 0 ? (
        <p style={{ color: '#999', textAlign: 'center' }}>
          No {contentType === 'test' ? 'tests' : 'homework'} uploaded yet.
        </p>
      ) : (
        <div className="tests-list">
          {tests.map(test => (
            <div key={test.id} className="test-card">
              <div className="test-header">
                <h4>{test.title}</h4>
                <button 
                  onClick={() => handleDelete(test.id)}
                  className="delete-btn"
                  title={contentType === 'test' ? 'Delete Test' : 'Delete Homework'}
                >
                  🗑️
                </button>
              </div>
              <div className="test-details">
                {contentType === 'test' && (
                  <>
                    <p><strong>Duration:</strong> {test.duration_minutes} minutes</p>
                    <p><strong>Deadline:</strong> {formatDeadline(test.submission_deadline)}</p>
                  </>
                )}
                
                {/* Extraction Status */}
                <p>
                  <strong>Extraction:</strong>{' '}
                  {test.extraction_stage === 'COMPLETED' ? (
                    test.questions_extracted_count > 0 ? (
                      <span style={{ color: '#4CAF50' }}>
                        ✅ {test.questions_extracted_count} questions
                        {test.solutions_extracted_count > 0 && ` | ${test.solutions_extracted_count} solutions`}
                      </span>
                    ) : (
                      <span style={{ color: '#f44336' }}>⚠️ No questions extracted</span>
                    )
                  ) : test.extraction_status === 'processing' ? (
                    <span style={{ color: '#ff9800' }}>⏳ {test.extraction_stage_message || 'Processing...'}</span>
                  ) : test.extraction_status === 'failed' ? (
                    <span style={{ color: '#f44336' }}>❌ {test.extraction_error || 'Failed'}</span>
                  ) : (
                    <span style={{ color: '#999' }}>⏳ Pending...</span>
                  )}
                </p>
                
                {/* Status - only for tests */}
                {contentType === 'test' && (
                  <p>
                    <strong>Status:</strong>{' '}
                    <span className={test.is_expired ? 'expired' : test.extraction_stage === 'COMPLETED' ? 'active' : 'draft'}>
                      {test.is_expired ? '🔒 Expired' : 
                       test.extraction_stage === 'COMPLETED' ? '✅ Active' :
                       '📝 Preparing...'}
                    </span>
                  </p>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {showUploadModal && (
        <div className="modal-overlay" onClick={() => !uploading && setShowUploadModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h2>{contentType === 'test' ? 'Create Test' : 'Create Homework'}</h2>
            <form onSubmit={handleSubmit} className="test-form">
              <div className="form-group">
                <label>{contentType === 'test' ? 'Test' : 'Homework'} Title *</label>
                <input
                  type="text"
                  value={formData.title}
                  onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                  required
                  placeholder={contentType === 'test' ? 'e.g., Mid-Term Exam 2025' : 'e.g., Chapter 1 Exercises'}
                />
              </div>

              <div className="form-group">
                <label>{contentType === 'test' ? 'Test Question Paper' : 'Homework'} (PDF) *</label>
                <input
                  type="file"
                  accept=".pdf"
                  onChange={(e) => handleFileChange(e, 'testFile')}
                  required
                />
              </div>

              <div className="form-group">
                <label>Model Answers (PDF) - Optional</label>
                <input
                  type="file"
                  accept=".pdf"
                  onChange={(e) => handleFileChange(e, 'modelAnswers')}
                />
              </div>

              {contentType === 'test' && (
                <div className="form-group">
                  <label>Marking Schema (PDF) - Optional</label>
                  <input
                    type="file"
                    accept=".pdf"
                    onChange={(e) => handleFileChange(e, 'markingSchema')}
                  />
                  <small style={{ color: '#666', fontSize: '12px', display: 'block', marginTop: '5px' }}>
                    Upload marking scheme for strict evaluation criteria
                  </small>
                </div>
              )}

              {contentType === 'test' && (
                <div className="form-row">
                  <div className="form-group">
                    <label>Duration (minutes) *</label>
                    <input
                      type="number"
                      min="5"
                      max="300"
                      value={formData.durationMinutes}
                      onChange={(e) => setFormData({ ...formData, durationMinutes: parseInt(e.target.value) })}
                      required
                    />
                  </div>

                  <div className="form-group">
                    <label>Submission Deadline *</label>
                    <input
                      type="datetime-local"
                      value={formData.submissionDeadline}
                      onChange={(e) => setFormData({ ...formData, submissionDeadline: e.target.value })}
                      min={new Date().toISOString().slice(0, 16)}
                      required
                    />
                  </div>
                </div>
              )}

              <div className="form-actions">
                <button type="submit" disabled={uploading} className="submit-btn">
                  {uploading ? '⏳ Uploading...' : `Upload ${contentType === 'test' ? 'Test' : 'Homework'}`}
                </button>
                <button 
                  type="button" 
                  onClick={() => setShowUploadModal(false)}
                  disabled={uploading}
                  className="cancel-btn"
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
      
      {/* EXTRACTION PROGRESS MODAL */}
      {showProgressModal && (
        <div className="modal-overlay">
          <div className="modal-content" style={{ maxWidth: '600px' }}>
            <h2>🤖 Preparing Your Test</h2>
            <p style={{ color: '#666', marginBottom: '20px' }}>
              AI is doing the magic, sit back and relax...
            </p>
            
            {/* Progress Bar */}
            <div style={{ marginBottom: '20px' }}>
              <div style={{ 
                width: '100%', 
                height: '30px', 
                backgroundColor: '#e0e0e0', 
                borderRadius: '15px',
                overflow: 'hidden'
              }}>
                <div style={{
                  width: `${extractionProgress}%`,
                  height: '100%',
                  backgroundColor: extractionFailed ? '#f44336' : '#4CAF50',
                  transition: 'width 0.5s ease',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: 'white',
                  fontWeight: 'bold'
                }}>
                  {extractionProgress}%
                </div>
              </div>
            </div>
            
            
            {/* Error Message - Show EXACT failure stage */}
            {extractionFailed && (
              <div style={{ 
                padding: '15px', 
                backgroundColor: '#ffebee',
                border: '1px solid #f44336',
                borderRadius: '8px',
                marginBottom: '15px'
              }}>
                <p style={{ color: '#f44336', fontWeight: 'bold', margin: '0 0 8px 0' }}>
                  ❌ Extraction failed
                </p>
                <p style={{ color: '#666', margin: '0 0 8px 0' }}>
                  <strong>Stage:</strong> {extractionStage}
                </p>
                <p style={{ color: '#666', margin: 0 }}>
                  <strong>Reason:</strong> {extractionError || 'Unknown error'}
                </p>
              </div>
            )}
            
            {/* Action Buttons */}
            <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end' }}>
              {canRetry && extractionFailed && (
                <button 
                  onClick={handleRetryExtraction}
                  style={{
                    padding: '10px 20px',
                    backgroundColor: '#ff9800',
                    color: 'white',
                    border: 'none',
                    borderRadius: '5px',
                    cursor: 'pointer'
                  }}
                >
                  🔄 Retry Extraction
                </button>
              )}
              <button 
                onClick={handleCloseProgressModal}
                style={{
                  padding: '10px 20px',
                  backgroundColor: '#666',
                  color: 'white',
                  border: 'none',
                  borderRadius: '5px',
                  cursor: 'pointer'
                }}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default TestManagement;
