import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './TeacherUpload.css';

const API = process.env.REACT_APP_BACKEND_URL ? `${process.env.REACT_APP_BACKEND_URL}/api` : '/api';

// Subject icon mapping - same as in App.js
const getSubjectIcon = (subjectName) => {
  const name = subjectName.toLowerCase();
  
  if (name.includes('english')) {
    return 'https://cdn3d.iconscout.com/3d/premium/thumb/book-3d-icon-download-in-png-blend-fbx-gltf-file-formats--education-reading-library-school-pack-icons-5187834.png';
  }
  if (name.includes('hindi')) {
    return 'https://cdn3d.iconscout.com/3d/premium/thumb/books-3d-icon-download-in-png-blend-fbx-gltf-file-formats--book-stack-education-library-study-learning-pack-school-icons-6887983.png';
  }
  if (name.includes('math')) {
    return 'https://cdn3d.iconscout.com/3d/premium/thumb/calculator-3d-icon-download-in-png-blend-fbx-gltf-file-formats--calculation-accounting-business-pack-icons-5187806.png';
  }
  if (name.includes('science') && !name.includes('social')) {
    return 'https://cdn3d.iconscout.com/3d/premium/thumb/flask-3d-icon-download-in-png-blend-fbx-gltf-file-formats--science-laboratory-chemistry-experiment-research-pack-icons-5187825.png';
  }
  if (name.includes('social') || name.includes('evs') || name.includes('environment')) {
    return 'https://cdn3d.iconscout.com/3d/premium/thumb/globe-3d-icon-download-in-png-blend-fbx-gltf-file-formats--earth-world-geography-planet-pack-education-icons-5187828.png';
  }
  if (name.includes('computer')) {
    return 'https://cdn3d.iconscout.com/3d/premium/thumb/computer-3d-icon-download-in-png-blend-fbx-gltf-file-formats--desktop-pc-technology-device-pack-icons-5187813.png';
  }
  return 'https://cdn3d.iconscout.com/3d/premium/thumb/graduation-cap-3d-icon-download-in-png-blend-fbx-gltf-file-formats--education-degree-achievement-school-pack-icons-5187830.png';
};

/**
 * TeacherUpload Component - Phase 4.1 Controlled AI Regeneration
 * 
 * CRITICAL RULES:
 * 1. Upload DOES NOT auto-regenerate AI content
 * 2. Teacher MUST explicitly confirm regeneration via modal
 * 3. Progress UI shown during regeneration
 */
function TeacherUpload({ subjects = [], initialSubject = null, onBack }) {
  const [selectedSubject, setSelectedSubject] = useState(initialSubject);
  const [chapters, setChapters] = useState([]);
  const [selectedChapter, setSelectedChapter] = useState(null);
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState(null);
  
  // Regeneration modal state
  const [showRegenerateModal, setShowRegenerateModal] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [regenerationResult, setRegenerationResult] = useState(null);
  
  // AI content status
  const [aiContentStatus, setAiContentStatus] = useState(null);
  
  // Load chapters when subject is selected
  useEffect(() => {
    if (selectedSubject) {
      loadChapters(selectedSubject.id);
    }
  }, [selectedSubject]);
  
  // Check AI content status when chapter is selected
  useEffect(() => {
    if (selectedChapter) {
      checkAiContentStatus(selectedChapter.id);
    }
  }, [selectedChapter]);
  
  // Handler for subject dropdown change
  const handleSubjectChange = (e) => {
    const subjectId = e.target.value;
    const subject = subjects.find(s => s.id === parseInt(subjectId) || s.id === subjectId);
    setSelectedSubject(subject || null);
    setSelectedChapter(null);
    setChapters([]);
    setAiContentStatus(null);
  };
  
  // Handler for chapter dropdown change
  const handleChapterChange = (e) => {
    const chapterId = e.target.value;
    const chapter = chapters.find(c => c.id === parseInt(chapterId) || c.id === chapterId);
    setSelectedChapter(chapter || null);
  };
  
  const loadChapters = async (subjectId) => {
    try {
      const response = await axios.get(`${API}/subjects/${subjectId}/chapters`, {
        withCredentials: true
      });
      setChapters(response.data);
    } catch (error) {
      console.error('Error loading chapters:', error);
      setChapters([]);
    }
  };
  
  const checkAiContentStatus = async (chapterId) => {
    try {
      const response = await axios.get(`${API}/teacher/chapter/${chapterId}/ai-content-status`, {
        withCredentials: true
      });
      setAiContentStatus(response.data);
    } catch (error) {
      console.error('Error checking AI content status:', error);
      setAiContentStatus(null);
    }
  };
  
  const handleFileSelect = (e) => {
    const selectedFile = e.target.files[0];
    if (selectedFile && selectedFile.type === 'application/pdf') {
      setFile(selectedFile);
      setUploadResult(null);
    } else {
      alert('Please select a PDF file');
    }
  };
  
  const handleUpload = async () => {
    if (!file || !selectedChapter) return;
    
    setUploading(true);
    setUploadResult(null);
    
    try {
      const formData = new FormData();
      formData.append('chapter_id', selectedChapter.id);
      formData.append('content_type', 'textbook');
      formData.append('file', file);
      
      const response = await axios.post(`${API}/teacher/content/upload`, formData, {
        withCredentials: true,
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      
      setUploadResult(response.data);
      
      // If AI content already exists, show regeneration modal
      if (response.data.ai_content_exists || response.data.regeneration_required) {
        setShowRegenerateModal(true);
      }
      
      // Refresh AI content status
      checkAiContentStatus(selectedChapter.id);
      setFile(null);
      
    } catch (error) {
      console.error('Upload error:', error);
      setUploadResult({
        success: false,
        message: error.response?.data?.detail || 'Upload failed'
      });
    } finally {
      setUploading(false);
    }
  };
  
  const handleRegenerate = async () => {
    if (!selectedChapter) return;
    
    // Show modal immediately to give user feedback
    setShowRegenerateModal(true);
    setRegenerating(true);
    setRegenerationResult(null);
    
    try {
      // Call regeneration API - this starts background processing
      const response = await axios.post(
        `${API}/teacher/chapter/${selectedChapter.id}/regenerate-ai-content`,
        {},
        { withCredentials: true }
      );
      
      // Backend returns immediately with status "processing"
      setRegenerationResult({
        success: true,
        message: response.data.message || 'AI content generation has been started in the background.',
        background_process: true,
        details: response.data.details
      });
      
      // Refresh AI content status
      checkAiContentStatus(selectedChapter.id);
      
    } catch (error) {
      console.error('Regeneration error:', error);
      setRegenerationResult({
        success: false,
        message: error.response?.data?.detail || 'Failed to start AI content generation. Please try again.'
      });
    } finally {
      setRegenerating(false);
    }
  };
  
  const handleCancelRegeneration = () => {
    setShowRegenerateModal(false);
    setRegenerationResult(null);
  };
  
  return (
    <div className="teacher-upload" data-testid="teacher-upload">
      
      <div className="upload-container">
        {/* Step 1: Select Chapter Dropdown */}
        {selectedSubject && (
          <div className="upload-step">
            <label className="upload-label">Select a Chapter</label>
            <select 
              className="upload-dropdown"
              onChange={handleChapterChange}
              value={selectedChapter?.id || ""}
              data-testid="chapter-dropdown"
              disabled={chapters.length === 0}
            >
              <option value="" disabled>
                {chapters.length === 0 ? 'No chapters available' : 'Choose a chapter...'}
              </option>
              {chapters.map((chapter, idx) => (
                <option key={chapter.id} value={chapter.id}>
                  Ch {idx + 1}: {chapter.name}
                </option>
              ))}
            </select>
            {chapters.length === 0 && (
              <p className="helper-text">Please create chapters first in the Chapters tab</p>
            )}
          </div>
        )}
      </div>
      
      {/* Step 3: AI Content Status */}
      {selectedChapter && aiContentStatus && (
        <div className="upload-step ai-status-section">
          <h3>AI Content Status</h3>
          <div className="ai-status-card">
            <div className="status-row">
              <span className="status-label">Textbook Uploaded:</span>
              <span className={`status-value ${aiContentStatus.textbook_uploaded ? 'yes' : 'no'}`}>
                {aiContentStatus.textbook_uploaded ? '✅ Yes' : '❌ No'}
              </span>
            </div>
            {aiContentStatus.textbook_filename && (
              <div className="status-row">
                <span className="status-label">Current File:</span>
                <span className="status-value">{aiContentStatus.textbook_filename}</span>
              </div>
            )}
            <div className="status-row">
              <span className="status-label">AI Content Generated:</span>
              <span className={`status-value ${aiContentStatus.ai_content_exists ? 'yes' : 'no'}`}>
                {aiContentStatus.ai_content_exists ? '✅ Yes' : '❌ No'}
              </span>
            </div>
          </div>
        </div>
      )}
      
      {/* Step 4: Upload PDF */}
      {selectedChapter && (
        <div className="upload-step">
          <h3>Step 3: Upload PDF</h3>
          <div className="upload-zone">
            <input
              type="file"
              accept=".pdf"
              onChange={handleFileSelect}
              id="pdf-upload"
              className="file-input"
              data-testid="file-input"
            />
            <label htmlFor="pdf-upload" className="file-label">
              {file ? (
                <>📄 {file.name}</>
              ) : (
                <>📁 Click to select PDF</>
              )}
            </label>
          </div>
          
          {file && (
            <button
              onClick={handleUpload}
              disabled={uploading}
              className="upload-btn"
              data-testid="upload-btn"
            >
              {uploading ? '⏳ Uploading...' : '📤 Upload PDF'}
            </button>
          )}
          
          {uploadResult && (
            <div className={`upload-result ${uploadResult.success !== false ? 'success' : 'error'}`}>
              {uploadResult.message}
              {uploadResult.ai_content_exists && (
                <p className="warning-text">
                  ⚠️ This chapter already has AI content. You can regenerate it if needed.
                </p>
              )}
            </div>
          )}
        </div>
      )}
      
      {/* Manual Regeneration Button */}
      {selectedChapter && aiContentStatus?.textbook_uploaded && (
        <div className="upload-step">
          <h3>Generate AI Content</h3>
          <p className="regenerate-info">
            If you've already generated AI content (notes, flashcards, quizzes), clicking below will replace all existing AI content.
          </p>
          <button
            onClick={handleRegenerate}
            className="regenerate-btn"
            data-testid="regenerate-btn"
          >
            Generate AI Content
          </button>
        </div>
      )}
      
      {/* Regeneration Progress Modal */}
      {showRegenerateModal && (
        <div className="modal-overlay" data-testid="regenerate-modal">
          <div className="modal-content">
            
            {regenerating && (
              <div className="regeneration-progress">
                <h2 className="modal-title">Starting AI Content Generation...</h2>
                <p className="progress-note">Please wait while we initiate the process...</p>
              </div>
            )}
            
            {regenerationResult && (
              <div className="regeneration-result">
                {regenerationResult.success ? (
                  <>
                    <h2 className="modal-title success">🚀 AI Content Generation Started!</h2>
                    <p className="success-message">
                      {regenerationResult.message}
                    </p>
                    {regenerationResult.background_process && (
                      <>
                        <p className="info-message" style={{ marginTop: '15px', color: '#555' }}>
                          📝 The system is now generating:
                        </p>
                        <ul style={{ textAlign: 'left', margin: '10px 20px', color: '#666' }}>
                          <li>✓ Revision Notes</li>
                          <li>✓ 15 Flashcards</li>
                          <li>✓ 5 Practice Quizzes (75 questions total)</li>
                        </ul>
                        <p className="info-message" style={{ marginTop: '15px', color: '#555' }}>
                          ⏱️ This process may take 2-5 minutes.
                        </p>
                        <p className="info-message" style={{ marginTop: '10px', color: '#555' }}>
                          💡 You can continue working. The content will be available to students once generation is complete.
                        </p>
                        <p className="info-message" style={{ marginTop: '10px', color: '#555' }}>
                          🔄 Refresh this page later to check the status.
                        </p>
                      </>
                    )}
                  </>
                ) : (
                  <>
                    <h2 className="modal-title error">❌ Error</h2>
                    <p className="error-message">
                      {regenerationResult.message || 'Failed to start AI content generation. Please try again.'}
                    </p>
                  </>
                )}
                <div className="modal-actions">
                  <button
                    onClick={handleCancelRegeneration}
                    className="close-btn"
                    data-testid="close-modal-btn"
                  >
                    Close
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default TeacherUpload;
