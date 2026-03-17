import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { API, getSubjectVectorIcon, getSubjectColorClass, extractErrorMessage } from '@/utils/helpers';
import StructuredTestCreator from '@/components/StructuredTestCreator';
import StructuredHomeworkCreator from '@/components/StructuredHomeworkCreator';
import TeacherUpload from '@/components/TeacherUpload';
import TeacherReviewMode from '@/components/TeacherReviewMode';

function TeacherAITestsList({ subjectId, standard }) {
  const [tests, setTests] = React.useState([]);
  const [loading, setLoading] = React.useState(true);
  const [reviewTestId, setReviewTestId] = React.useState(null);
  const [reviewTestTitle, setReviewTestTitle] = React.useState('');
  
  React.useEffect(() => {
    if (!subjectId || !standard) return;
    setLoading(true);
    axios.get(`${API}/structured-tests/list/${subjectId}/${standard}`, { withCredentials: true })
      .then(res => setTests(res.data || []))
      .catch(() => setTests([]))
      .finally(() => setLoading(false));
  }, [subjectId, standard]);
  
  if (loading) return <div style={{ color: '#94a3b8', padding: '12px 0', fontSize: 14 }}>Loading AI tests...</div>;
  if (tests.length === 0) return null;

  if (reviewTestId) {
    return (
      <TeacherReviewMode
        testId={reviewTestId}
        testTitle={reviewTestTitle}
        onClose={() => { setReviewTestId(null); setReviewTestTitle(''); }}
      />
    );
  }
  
  return (
    <div style={{ marginBottom: 24 }} data-testid="teacher-ai-tests-list">
      <h4 style={{ color: '#c4b5fd', fontSize: 14, fontWeight: 600, marginBottom: 12, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
        Published AI-Evaluated Tests
      </h4>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {tests.map(t => (
          <div key={t.id} data-testid={`teacher-ai-test-${t.id}`} style={{
            background: 'rgba(102,126,234,0.1)',
            border: '1px solid rgba(102,126,234,0.3)',
            borderRadius: 10,
            padding: '14px 18px',
            display: 'flex',
            flexDirection: 'column',
            gap: 10,
          }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4, flexWrap: 'wrap' }}>
                <span style={{ background: 'linear-gradient(135deg,#667eea,#764ba2)', padding: '2px 8px', borderRadius: 4, fontSize: 10, fontWeight: 700, color: '#fff' }}>AI</span>
                <span style={{ fontSize: 15, fontWeight: 600, color: '#F8FAFC' }}>{t.title}</span>
                <span style={{
                  fontSize: 11, fontWeight: 600, padding: '2px 8px', borderRadius: 10,
                  background: 'rgba(34,197,94,0.2)', color: '#22c55e',
                }}>Published</span>
              </div>
              <div style={{ fontSize: 13, color: '#94a3b8', display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                <span>{t.question_count} questions</span>
                <span>{t.total_marks} marks</span>
                <span>{t.duration_minutes} min</span>
                {t.submission_deadline && <span>Deadline: {new Date(t.submission_deadline).toLocaleDateString()}</span>}
              </div>
            </div>
            <button
              onClick={() => { setReviewTestId(t.id); setReviewTestTitle(t.title); }}
              data-testid={`review-test-btn-${t.id}`}
              style={{
                background: 'linear-gradient(135deg, #667eea, #764ba2)',
                color: '#fff',
                border: 'none',
                padding: '8px 18px',
                borderRadius: 8,
                fontSize: 13,
                fontWeight: 600,
                cursor: 'pointer',
                alignSelf: 'flex-start',
              }}
            >
              Review Submissions
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

function TeacherAIHomeworkList({ subjectId, standard }) {
  const [homeworks, setHomeworks] = React.useState([]);
  const [loading, setLoading] = React.useState(true);
  const [viewSubmissions, setViewSubmissions] = React.useState(null);
  const [submissions, setSubmissions] = React.useState([]);

  const loadHomeworks = React.useCallback(() => {
    if (!subjectId || !standard) return;
    setLoading(true);
    axios.get(`${API}/structured-homework/list/${subjectId}/${standard}`, { withCredentials: true })
      .then(res => setHomeworks(res.data?.homework || []))
      .catch(() => setHomeworks([]))
      .finally(() => setLoading(false));
  }, [subjectId, standard]);

  React.useEffect(() => { loadHomeworks(); }, [loadHomeworks]);

  const loadSubmissions = async (hwId) => {
    try {
      const res = await axios.get(`${API}/structured-homework/${hwId}/submissions`, { withCredentials: true });
      setSubmissions(res.data || []);
      setViewSubmissions(hwId);
    } catch { setSubmissions([]); }
  };

  const deleteHomework = async (hwId, title) => {
    if (!window.confirm(`Delete homework: ${title}?`)) return;
    try {
      await axios.delete(`${API}/structured-homework/${hwId}`, { withCredentials: true });
      loadHomeworks();
    } catch (err) {
      alert('Failed to delete: ' + (err.response?.data?.detail || err.message));
    }
  };

  if (loading) return <div style={{ color: '#94a3b8', padding: '12px 0', fontSize: 14 }}>Loading AI homework...</div>;
  if (homeworks.length === 0) return null;

  if (viewSubmissions) {
    const hw = homeworks.find(h => h.id === viewSubmissions);
    return (
      <div data-testid="hw-submissions-view">
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
          <button onClick={() => setViewSubmissions(null)} style={{ background: '#334155', color: '#F8FAFC', border: 'none', padding: '6px 14px', borderRadius: 8, cursor: 'pointer', fontSize: 13 }}>Back</button>
          <h4 style={{ color: '#F8FAFC', margin: 0 }}>{hw?.title} — Submissions</h4>
        </div>
        {submissions.length === 0 ? (
          <p style={{ color: '#94a3b8', fontSize: 14 }}>No submissions yet.</p>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {submissions.map(s => (
              <div key={s.id} style={{ background: 'rgba(72,187,120,0.08)', border: '1px solid rgba(72,187,120,0.2)', borderRadius: 8, padding: '12px 16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <span style={{ color: '#F8FAFC', fontWeight: 600, fontSize: 14 }}>{s.roll_no}</span>
                  <span style={{ color: '#94a3b8', fontSize: 13, marginLeft: 12 }}>{s.questions_attempted || 0} answered</span>
                  <span style={{ color: '#94a3b8', fontSize: 13, marginLeft: 12 }}>{s.hints_used || 0} hints used</span>
                </div>
                <span style={{
                  fontSize: 12, fontWeight: 600, padding: '3px 10px', borderRadius: 10,
                  background: s.completed ? 'rgba(34,197,94,0.2)' : 'rgba(251,191,36,0.2)',
                  color: s.completed ? '#22c55e' : '#fbbf24',
                }}>{s.completed ? 'Completed' : 'In Progress'}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }

  return (
    <div style={{ marginBottom: 24 }} data-testid="teacher-ai-homework-list">
      <h4 style={{ color: '#86efac', fontSize: 14, fontWeight: 600, marginBottom: 12, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
        Published AI Homework
      </h4>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {homeworks.map(h => (
          <div key={h.id} data-testid={`teacher-ai-hw-${h.id}`} style={{
            background: 'rgba(72,187,120,0.1)',
            border: '1px solid rgba(72,187,120,0.3)',
            borderRadius: 10,
            padding: '14px 18px',
            display: 'flex',
            flexDirection: 'column',
            gap: 10,
          }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4, flexWrap: 'wrap' }}>
                <span style={{ background: 'linear-gradient(135deg,#48bb78,#38a169)', padding: '2px 8px', borderRadius: 4, fontSize: 10, fontWeight: 700, color: '#fff' }}>AI</span>
                <span style={{ fontSize: 15, fontWeight: 600, color: '#F8FAFC' }}>{h.title}</span>
                <span style={{
                  fontSize: 11, fontWeight: 600, padding: '2px 8px', borderRadius: 10,
                  background: h.status === 'active' ? 'rgba(34,197,94,0.2)' : 'rgba(148,163,184,0.2)',
                  color: h.status === 'active' ? '#22c55e' : '#94a3b8',
                }}>{h.status === 'active' ? 'Active' : 'Expired'}</span>
              </div>
              <div style={{ fontSize: 13, color: '#94a3b8', display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                <span>{h.question_count} questions</span>
                {h.deadline && <span>Deadline: {new Date(h.deadline).toLocaleDateString()}</span>}
              </div>
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button
                onClick={() => loadSubmissions(h.id)}
                data-testid={`hw-submissions-btn-${h.id}`}
                style={{ background: 'linear-gradient(135deg,#48bb78,#38a169)', color: '#fff', border: 'none', padding: '8px 16px', borderRadius: 8, fontSize: 13, fontWeight: 600, cursor: 'pointer', whiteSpace: 'nowrap' }}
              >View Submissions</button>
              <button
                onClick={() => deleteHomework(h.id, h.title)}
                data-testid={`hw-delete-btn-${h.id}`}
                style={{ background: 'transparent', color: '#94a3b8', border: '1px solid #475569', padding: '8px 12px', borderRadius: 8, fontSize: 13, cursor: 'pointer' }}
              >Delete</button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function TeacherView({ user, language }) {
  const [standard, setStandard] = useState(null); // NEW: Standard selection
  const [subjects, setSubjects] = useState([]);
  const [selectedSubject, setSelectedSubject] = useState(null);
  const [chapters, setChapters] = useState([]);
  const [chaptersStatus, setChaptersStatus] = useState({});
  const [showAddSubject, setShowAddSubject] = useState(false);
  const [showAddChapter, setShowAddChapter] = useState(false);
  const [showPYQModal, setShowPYQModal] = useState(false);
  const [showAddPYQ, setShowAddPYQ] = useState(false);
  const [pyqYear, setPyqYear] = useState('');
  const [pyqExamName, setPyqExamName] = useState('');
  const [pyqFile, setPyqFile] = useState(null);
  const [newSubjectName, setNewSubjectName] = useState('');
  const [newChapterName, setNewChapterName] = useState('');
  const [editingSubject, setEditingSubject] = useState(null);
  const [editingChapter, setEditingChapter] = useState(null);
  const [editName, setEditName] = useState('');
  const [uploading, setUploading] = useState(false);
  
  // NEW: Homework & Study Materials state
  const [activeTab, setActiveTab] = useState('chapters');
  const [homeworkList, setHomeworkList] = useState([]);
  const [showAddHomework, setShowAddHomework] = useState(false);
  const [homeworkTitle, setHomeworkTitle] = useState('');
  const [homeworkFile, setHomeworkFile] = useState(null);
  const [modelAnswersFile, setModelAnswersFile] = useState(null); // NEW: Model answers
  const [studentCount, setStudentCount] = useState(0); // NEW: Student count
  const [selectedHomeworkSubmissions, setSelectedHomeworkSubmissions] = useState(null); // NEW: Track submissions
  const [pyqList, setPyqList] = useState([]); // NEW: PYQ list for teacher
  
  // UNIFIED EXTRACTION PROGRESS STATE (for homework, pyq, textbook)
  const [showProgressModal, setShowProgressModal] = useState(false);
  const [showAITestCreator, setShowAITestCreator] = useState(false);
  const [showAIHomeworkCreator, setShowAIHomeworkCreator] = useState(false);
  const [extractionContentId, setExtractionContentId] = useState(null);
  const [extractionContentType, setExtractionContentType] = useState(''); // 'homework', 'pyq', 'test'
  const [extractionProgress, setExtractionProgress] = useState(0);
  const [extractionStage, setExtractionStage] = useState('');
  const [extractionMessage, setExtractionMessage] = useState('');
  const [extractionElapsed, setExtractionElapsed] = useState(0);
  const [extractionFailed, setExtractionFailed] = useState(false);
  const [extractionError, setExtractionError] = useState('');
  const [canRetry, setCanRetry] = useState(false);
  const pollIntervalRef = useRef(null);
  
  // Study materials per chapter
  const [chapterStudyMaterials, setChapterStudyMaterials] = useState({});

  const loadSubjects = React.useCallback(async () => {
    if (!standard) return;
    const response = await axios.get(`${API}/subjects?standard=${standard}`, { withCredentials: true });
    setSubjects(response.data);
    
    // Load student count for this standard
    try {
      const countResponse = await axios.get(`${API}/teacher/students/count?standard=${standard}`, {
        withCredentials: true
      });
      setStudentCount(countResponse.data.total_students);
    } catch (error) {
      console.error('Error loading student count:', error);
      setStudentCount(0);
    }
  }, [standard]);

  useEffect(() => {
    loadSubjects();
  }, [loadSubjects]);

  const loadChapters = async (subject) => {
    const response = await axios.get(`${API}/subjects/${subject.id}/chapters`, { withCredentials: true });
    setChapters(response.data);
    setSelectedSubject(subject);
    
    const statusMap = {};
    const materialsMap = {};
    
    for (const chapter of response.data) {
      try {
        const statusResponse = await axios.get(`${API}/chapters/${chapter.id}/content-status`);
        statusMap[chapter.id] = statusResponse.data;
      } catch (error) {
        statusMap[chapter.id] = { textbook: null };
      }
      
      // Load study materials for each chapter
      try {
        const materialsResponse = await axios.get(`${API}/chapters/${chapter.id}/study-materials`, { withCredentials: true });
        materialsMap[chapter.id] = materialsResponse.data;
      } catch (error) {
        materialsMap[chapter.id] = [];
      }
    }
    setChaptersStatus(statusMap);
    setChapterStudyMaterials(materialsMap);
  };

  const addSubject = async (e) => {
    e.preventDefault();
    try {
      await axios.post(`${API}/subjects`, { 
        name: newSubjectName, 
        standard: standard  // Include standard
      }, { withCredentials: true });
      setNewSubjectName('');
      setShowAddSubject(false);
      loadSubjects();
      alert('✅ Subject added successfully!');
    } catch (error) {
      console.error('Add subject error:', error);
      const errorMessage = error.response?.data?.detail || error.message || 'Unknown error';
      alert(`❌ Failed to add subject: ${errorMessage}`);
    }
  };

  const addChapter = async (e) => {
    e.preventDefault();
    try {
      await axios.post(
        `${API}/chapters`,
        { subject_id: selectedSubject.id, name: newChapterName },
        { withCredentials: true }
      );
      setNewChapterName('');
      setShowAddChapter(false);
      loadChapters(selectedSubject);
      alert('✅ Chapter added successfully!');
    } catch (error) {
      console.error('Add chapter error:', error);
      const errorMessage = error.response?.data?.detail || error.message || 'Unknown error';
      alert(`❌ Failed to add chapter: ${errorMessage}`);
    }
  };

  const updateVideoUrl = async (chapterId, videoUrl) => {
    try {
      const formData = new FormData();
      formData.append('video_url', videoUrl);
      
      await axios.put(`${API}/chapters/${chapterId}/video`, formData, { withCredentials: true });
      
      // Reload chapters to update the UI
      loadChapters(selectedSubject);
      alert(videoUrl ? '✅ Video URL updated successfully!' : '✅ Video URL removed');
    } catch (error) {
      console.error('Error updating video URL:', error);
      alert('❌ Failed to update video URL');
    }
  };

  const updateSubject = async (subjectId) => {
    try {
      const formData = new FormData();
      formData.append('name', editName);
      await axios.put(`${API}/subjects/${subjectId}`, formData, { withCredentials: true });
      setEditingSubject(null);
      loadSubjects();
      if (selectedSubject && selectedSubject.id === subjectId) {
        setSelectedSubject({ ...selectedSubject, name: editName });
      }
      alert('✅ Subject updated successfully!');
    } catch (error) {
      alert('❌ Failed to update subject');
    }
  };

  const deleteSubject = async (subjectId, subjectName) => {
    if (window.confirm(`⚠️ Are you sure you want to delete "${subjectName}"?\n\nThis will also delete all chapters and content for this subject. This action cannot be undone!`)) {
      try {
        await axios.delete(`${API}/subjects/${subjectId}`, { withCredentials: true });
        alert(`✅ Subject "${subjectName}" deleted successfully`);
        loadSubjects();
        setSelectedSubject(null);
      } catch (error) {
        alert('❌ Failed to delete subject');
        console.error(error);
      }
    }
  };

  const deleteChapter = async (chapterId, chapterName) => {
    if (window.confirm(`⚠️ Are you sure you want to delete "${chapterName}"?\n\nThis will also delete all uploaded content for this chapter. This action cannot be undone!`)) {
      try {
        await axios.delete(`${API}/chapters/${chapterId}`, { withCredentials: true });
        alert(`✅ Chapter "${chapterName}" deleted successfully`);
        loadChapters(selectedSubject);
      } catch (error) {
        alert('❌ Failed to delete chapter');
        console.error(error);
      }
    }
  };

  const updateChapter = async (chapterId) => {
    try {
      const formData = new FormData();
      formData.append('name', editName);
      await axios.put(`${API}/chapters/${chapterId}`, formData, { withCredentials: true });
      setEditingChapter(null);
      loadChapters(selectedSubject);
      alert('✅ Chapter updated successfully!');
    } catch (error) {
      alert('❌ Failed to update chapter');
    }
  };

  const handleFileUpload = async (e, chapterId) => {
    const file = e.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('chapter_id', chapterId);
    formData.append('content_type', 'textbook'); // Single type instead of ncert/school
    formData.append('file', file);

    setUploading(true);
    try {
      await axios.post(`${API}/content/upload`, formData, {
        withCredentials: true,
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      loadChapters(selectedSubject);
      alert('✅ Textbook uploaded successfully!');
    } catch (error) {
      alert('❌ Failed to upload. Please try again.');
    } finally {
      setUploading(false);
    }
  };

  const uploadPYQ = async (e) => {
    e.preventDefault();
    
    if (!pyqYear || !pyqExamName || !pyqFile) {
      alert('Please fill all fields');
      return;
    }

    const formData = new FormData();
    formData.append('file', pyqFile);
    formData.append('year', pyqYear);
    formData.append('exam_name', pyqExamName);
    formData.append('standard', standard);

    setUploading(true);
    try {
      const response = await axios.post(`${API}/subjects/${selectedSubject.id}/upload-pyq`, formData, {
        withCredentials: true,
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      
      setShowPYQModal(false);
      setPyqYear('');
      setPyqExamName('');
      setPyqFile(null);
      
      if (response.data.pyq_id) {
        // Always show unified extraction progress for PYQs when we get a valid id
        setExtractionContentId(response.data.pyq_id);
        setExtractionContentType('pyq');
        setExtractionProgress(0);
        setExtractionStage('UPLOADED');
        setExtractionMessage('Starting extraction...');
        setExtractionFailed(false);
        setExtractionError('');
        setShowProgressModal(true);
        startExtractionPolling(response.data.pyq_id, 'pyq');
      } else {
        // Fallback: no id returned, just refresh list
        alert('PYQ uploaded successfully!');
        loadPYQs();
      }
    } catch (error) {
      alert('❌ Failed to upload PYQ. Please try again.');
      console.error(error);
    } finally {
      setUploading(false);
    }
  };

  // Generate PYQ Solutions
  const generatePYQSolutions = async (pyqId) => {
    if (!window.confirm('Generate AI solutions for this PYQ?\n\nRelax, AI is preparing solutions for you. This may take 1-2 minutes.')) {
      return;
    }
    
    setUploading(true);
    try {
      const response = await axios.post(
        `${API}/pyq/${pyqId}/generate-solutions`,
        {},
        { withCredentials: true }
      );
      
      if (response.data.solution_generated) {
        alert(`✅ Solutions generated successfully! (${response.data.solutions_count} solutions)`);
        loadPYQs();
      }
    } catch (error) {
      alert('❌ Failed to generate solutions. Please try again.');
      console.error(error);
    } finally {
      setUploading(false);
    }
  };

  // Delete PYQ (handler defined later in file)


  // Load homework for selected subject
  const loadHomework = React.useCallback(async () => {
    if (!selectedSubject || !standard) return;
    try {
      const response = await axios.get(`${API}/homework?standard=${standard}&subject_id=${selectedSubject.id}`, {
        withCredentials: true
      });
      setHomeworkList(response.data);
    } catch (error) {
      console.error('Error loading homework:', error);
    }
  }, [selectedSubject, standard]);

  const loadPYQs = React.useCallback(async () => {
    if (!selectedSubject || !standard) return;
    try {
      const response = await axios.get(`${API}/subjects/${selectedSubject.id}/pyqs?standard=${standard}`, {
        withCredentials: true
      });
      setPyqList(response.data);
    } catch (error) {
      console.error('Error loading PYQs:', error);
    }
  }, [selectedSubject, standard]);

  // UNIFIED EXTRACTION POLLING (for homework, pyq, textbook)
  const startExtractionPolling = (contentId, contentType) => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
    
    let completionAlertShown = false;
    
    const pollInterval = setInterval(async () => {
      try {
        let endpoint = '';
        if (contentType === 'homework') {
          endpoint = `${API}/homework/${contentId}/extraction-status`;
        } else if (contentType === 'pyq') {
          endpoint = `${API}/pyq/${contentId}/extraction-status`;
        } else if (contentType === 'test') {
          endpoint = `${API}/tests/${contentId}/extraction-status`;
        }
        
        const response = await axios.get(endpoint, { withCredentials: true });
        const data = response.data;
        
        const progress = data.extraction_stage === 'COMPLETED' ? 100 : (data.extraction_progress || 0);
        setExtractionProgress(progress);
        setExtractionStage(data.extraction_stage || '');
        setExtractionMessage(data.extraction_stage_message || '');
        setExtractionElapsed(data.elapsed_seconds || 0);
        setCanRetry(!!data.can_retry);
        
        if (!data.should_poll) {
          clearInterval(pollInterval);
          pollIntervalRef.current = null;
          
          if (data.extraction_stage === 'COMPLETED' && data.extraction_status === 'completed') {
            if (!completionAlertShown) {
              completionAlertShown = true;
              setShowProgressModal(false);
              alert(`✅ ${contentType.charAt(0).toUpperCase() + contentType.slice(1)} ready! ${data.questions_extracted_count || 0} questions extracted successfully.`);
              if (contentType === 'homework') loadHomework();
              else if (contentType === 'pyq') loadPYQs();
            }
          } else if (data.extraction_stage === 'FAILED' || data.extraction_stage === 'TIMEOUT' || data.is_stuck) {
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
  
  const handleCloseProgressModal = () => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
    setShowProgressModal(false);
    if (extractionContentType === 'homework') loadHomework();
    else if (extractionContentType === 'pyq') loadPYQs();
  };
  
  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
      }
    };
  }, []);

  // Effect to load homework/PYQs when subject or tab changes
  useEffect(() => {
    if (selectedSubject && standard && activeTab === 'homework') {
      loadHomework();
    }
    if (selectedSubject && standard && activeTab === 'pyqs') {
      loadPYQs();
    }
  }, [selectedSubject, standard, activeTab, loadHomework, loadPYQs]);

  // Upload homework
  const uploadHomework = async (e) => {
    e.preventDefault();
    if (!homeworkTitle || !homeworkFile) {
      alert('Please fill all fields');
      return;
    }

    const formData = new FormData();
    formData.append('subject_id', selectedSubject.id);
    formData.append('standard', standard);
    formData.append('title', homeworkTitle);
    formData.append('file', homeworkFile);
    
    if (modelAnswersFile) {
      formData.append('model_answers_file', modelAnswersFile);
    }

    setUploading(true);
    try {
      const response = await axios.post(`${API}/homework`, formData, {
        withCredentials: true,
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      
      setHomeworkTitle('');
      setHomeworkFile(null);
      setModelAnswersFile(null);
      setShowAddHomework(false);
      
      // Start extraction progress tracking
      if (response.data.status === 'processing' && response.data.homework_id) {
        setExtractionContentId(response.data.homework_id);
        setExtractionContentType('homework');
        setExtractionProgress(0);
        setExtractionStage('UPLOADED');
        setExtractionMessage('Starting extraction...');
        setExtractionFailed(false);
        setExtractionError('');
        setShowProgressModal(true);
        startExtractionPolling(response.data.homework_id, 'homework');
      } else {
        alert('Homework uploaded successfully!');
        loadHomework();
      }
    } catch (error) {
      console.error('Upload error:', error);
      alert('❌ Failed to upload homework: ' + (error.response?.data?.detail || error.message));
    } finally {
      setUploading(false);
    }
  };

  // Delete homework
  const deleteHomework = async (homeworkId, title) => {
    if (window.confirm(`Delete homework: ${title}?`)) {
      try {
        await axios.delete(`${API}/homework/${homeworkId}`, { withCredentials: true });
        loadHomework();
        alert('✅ Homework deleted');
      } catch (error) {
        alert('❌ Failed to delete homework');
      }
    }
  };

  const deletePYQ = async (pyqId, examName, year) => {
    if (window.confirm(`Delete PYQ: ${examName} ${year}?`)) {
      try {
        await axios.delete(`${API}/pyq/${pyqId}`, { withCredentials: true });
        loadPYQs();
        alert('✅ PYQ deleted successfully');
      } catch (error) {
        console.error('Error deleting PYQ:', error);
        alert('❌ Failed to delete PYQ');
      }
    }
  };

  const viewHomeworkSubmissions = async (homeworkId) => {
    try {
      const response = await axios.get(`${API}/homework/${homeworkId}/submissions`, { 
        withCredentials: true 
      });
      setSelectedHomeworkSubmissions(response.data);
    } catch (error) {
      console.error('Error loading submissions:', error);
      alert('❌ Failed to load submissions');
    }
  };

  // Simple study material upload
  const handleStudyMaterialUpload = async (e, chapterId) => {
    const file = e.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('material_type', 'notes');
    formData.append('title', file.name.replace('.pdf', ''));
    formData.append('file', file);

    setUploading(true);
    try {
      await axios.post(`${API}/chapters/${chapterId}/study-materials`, formData, {
        withCredentials: true,
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      alert('✅ Study material uploaded!');
      loadChapters(selectedSubject);
    } catch (error) {
      alert('❌ Failed to upload material');
    } finally {
      setUploading(false);
    }
  };
  
  // Delete study material
  const deleteStudyMaterial = async (materialId, materialTitle) => {
    if (window.confirm(`Delete study material: ${materialTitle}?`)) {
      try {
        await axios.delete(`${API}/study-materials/${materialId}`, { withCredentials: true });
        loadChapters(selectedSubject);
        alert('✅ Study material deleted');
      } catch (error) {
        alert('❌ Failed to delete study material');
      }
    }
  };

  // Load homework when subject is selected
  useEffect(() => {
    if (selectedSubject) {
      loadHomework();
    }
  }, [selectedSubject, standard, loadHomework]);

  // Step 1: Standard selection with subject dropdown appearing on same page
  if (!selectedSubject) {
    return (
      <div className="teacher-view">
        <div className="standard-selection-container">
          {/* Banner Logo */}
          <div className="banner-logo-container">
            <img 
              src="/studybuddy-banner.png" 
              alt="StudyBuddy Banner" 
              className="banner-logo"
            />
            <p className="banner-tagline">Your Personal AI Teaching Assistant 24*7</p>
          </div>
          
          <h2 className="standard-selection-title">Select Standard to Manage 🎓</h2>
          <select 
            className="standard-dropdown"
            onChange={(e) => setStandard(parseInt(e.target.value))}
            value={standard || ""}
            data-testid="teacher-standard-dropdown"
          >
            <option value="" disabled>Choose a class...</option>
            <option value="1">Class 1</option>
            <option value="2">Class 2</option>
            <option value="3">Class 3</option>
            <option value="4">Class 4</option>
            <option value="5">Class 5</option>
            <option value="6">Class 6</option>
            <option value="7">Class 7</option>
            <option value="8">Class 8</option>
            <option value="9">Class 9</option>
            <option value="10">Class 10</option>
          </select>
          
          {/* Subject dropdown appears when standard is selected */}
          {standard && (
            <div style={{ marginTop: '48px' }}>
              <div style={{ display: 'flex', gap: '12px', alignItems: 'center', justifyContent: 'center', flexWrap: 'wrap' }}>
                <select 
                  className="standard-dropdown"
                  onChange={(e) => {
                    const subject = subjects.find(s => s.id === e.target.value);
                    if (subject) loadChapters(subject);
                  }}
                  defaultValue=""
                  data-testid="teacher-subject-dropdown"
                  style={{ flex: '1', maxWidth: '400px' }}
                >
                  <option value="" disabled>Choose a subject...</option>
                  {subjects.map(subject => (
                    <option key={subject.id} value={subject.id}>
                      {subject.name}
                    </option>
                  ))}
                </select>
                <button
                  onClick={() => setShowAddSubject(true)}
                  data-testid="add-subject-btn"
                  style={{
                    padding: '14px 24px',
                    background: 'rgba(255, 255, 255, 0.08)',
                    color: '#F8FAFC',
                    border: '1px solid rgba(255, 255, 255, 0.15)',
                    borderRadius: '16px',
                    fontFamily: "'Outfit', sans-serif",
                    fontSize: '18px',
                    fontWeight: '600',
                    cursor: 'pointer',
                    transition: 'all 0.3s ease',
                    whiteSpace: 'nowrap'
                  }}
                  onMouseEnter={(e) => {
                    e.target.style.background = 'rgba(255, 255, 255, 0.12)';
                    e.target.style.transform = 'translateY(-2px)';
                  }}
                  onMouseLeave={(e) => {
                    e.target.style.background = 'rgba(255, 255, 255, 0.08)';
                    e.target.style.transform = 'translateY(0)';
                  }}
                >
                  + Add Subject
                </button>
              </div>

              {/* Subject list with delete buttons */}
              {subjects.length > 0 && (
                <div style={{ marginTop: '20px', display: 'flex', flexWrap: 'wrap', gap: '10px', justifyContent: 'center' }}>
                  {subjects.map(subject => (
                    <div
                      key={subject.id}
                      data-testid={`subject-chip-${subject.id}`}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px',
                        padding: '8px 12px 8px 16px',
                        background: 'rgba(255, 255, 255, 0.08)',
                        border: '1px solid rgba(255, 255, 255, 0.15)',
                        borderRadius: '24px',
                        cursor: 'pointer',
                        transition: 'all 0.2s ease',
                      }}
                    >
                      <span
                        onClick={() => loadChapters(subject)}
                        style={{
                          color: '#F8FAFC',
                          fontFamily: "'Outfit', sans-serif",
                          fontSize: '14px',
                          fontWeight: '600',
                        }}
                      >
                        {subject.name}
                      </span>
                      <button
                        onClick={(e) => { e.stopPropagation(); deleteSubject(subject.id, subject.name); }}
                        data-testid={`delete-subject-${subject.id}`}
                        title={`Remove ${subject.name}`}
                        style={{
                          background: 'transparent',
                          border: 'none',
                          color: '#94a3b8',
                          cursor: 'pointer',
                          fontSize: '16px',
                          lineHeight: '1',
                          padding: '2px 4px',
                          borderRadius: '50%',
                          transition: 'all 0.2s ease',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                        }}
                        onMouseEnter={(e) => { e.target.style.color = '#ef4444'; e.target.style.background = 'rgba(239,68,68,0.15)'; }}
                        onMouseLeave={(e) => { e.target.style.color = '#94a3b8'; e.target.style.background = 'transparent'; }}
                      >
                        ✕
                      </button>
                    </div>
                  ))}
                </div>
              )}
              
              {/* Add Subject Modal */}
              {showAddSubject && (
                <div style={{
                  marginTop: '24px',
                  padding: '24px',
                  background: 'rgba(255, 255, 255, 0.08)',
                  border: '1px solid rgba(255, 255, 255, 0.15)',
                  borderRadius: '16px'
                }}>
                  <h4 style={{ 
                    color: '#F8FAFC', 
                    fontFamily: "'Outfit', sans-serif", 
                    fontSize: '18px', 
                    fontWeight: '600',
                    marginBottom: '16px',
                    marginTop: 0
                  }}>
                    Add New Subject for Class {standard}
                  </h4>
                  <form onSubmit={addSubject} style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
                    <input
                      type="text"
                      placeholder="Subject Name (e.g., Mathematics)"
                      value={newSubjectName}
                      onChange={(e) => setNewSubjectName(e.target.value)}
                      required
                      style={{
                        flex: '1',
                        minWidth: '200px',
                        padding: '14px 18px',
                        background: 'rgba(255, 255, 255, 0.08)',
                        color: '#F8FAFC',
                        border: '1px solid rgba(255, 255, 255, 0.15)',
                        borderRadius: '16px',
                        fontFamily: "'Outfit', sans-serif",
                        fontSize: '18px',
                        fontWeight: '600'
                      }}
                    />
                    <button
                      type="submit"
                      style={{
                        padding: '14px 24px',
                        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                        color: '#F8FAFC',
                        border: 'none',
                        borderRadius: '16px',
                        fontFamily: "'Outfit', sans-serif",
                        fontSize: '18px',
                        fontWeight: '600',
                        cursor: 'pointer'
                      }}
                    >
                      Add
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setShowAddSubject(false);
                        setNewSubjectName('');
                      }}
                      style={{
                        padding: '14px 24px',
                        background: 'rgba(255, 255, 255, 0.08)',
                        color: '#F8FAFC',
                        border: '1px solid rgba(255, 255, 255, 0.15)',
                        borderRadius: '16px',
                        fontFamily: "'Outfit', sans-serif",
                        fontSize: '18px',
                        fontWeight: '600',
                        cursor: 'pointer'
                      }}
                    >
                      Cancel
                    </button>
                  </form>
                </div>
              )}
              
              {/* Info message when no subjects */}
              {subjects.length === 0 && !showAddSubject && (
                <p style={{
                  marginTop: '16px',
                  color: 'rgba(248, 250, 252, 0.6)',
                  fontFamily: "'Outfit', sans-serif",
                  fontSize: '16px',
                  textAlign: 'center'
                }}>
                  No subjects found for Class {standard}. Click "Add Subject" to create one.
                </p>
              )}
            </div>
          )}
        </div>
      </div>
    );
  }

  // Step 2: Subject Management
  if (selectedSubject) {
    return (
      <>
      <div className="teacher-view">
        <button className="back-btn" onClick={() => setSelectedSubject(null)}>← Back</button>
        
        <div className="teacher-header">
          <div>
            <span style={{ fontSize: '14px', color: '#666', display: 'block', marginBottom: '5px' }}>
              Class {standard}
            </span>
            {editingSubject === selectedSubject.id ? (
              <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
                <input
                  type="text"
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  className="form-input"
                  style={{ width: '300px' }}
                />
                <button onClick={() => updateSubject(selectedSubject.id)} className="form-submit">Save</button>
                <button onClick={() => setEditingSubject(null)} className="form-cancel">Cancel</button>
              </div>
            ) : (
              <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
                <h2 className="section-title">{selectedSubject.name}</h2>
              </div>
            )}
          </div>
        </div>

        {/* Tabs for Chapters, Homework, Tests, and PYQs */}
        <div className="teacher-tabs" data-testid="teacher-tabs">
          <button className={`teacher-tab ${activeTab === 'chapters' ? 'active' : ''}`} onClick={() => setActiveTab('chapters')}>
            Chapters
          </button>
          <button className={`teacher-tab ${activeTab === 'homework' ? 'active' : ''}`} onClick={() => setActiveTab('homework')}>
            Homework
          </button>
          <button className={`teacher-tab ${activeTab === 'tests' ? 'active' : ''}`} onClick={() => setActiveTab('tests')}>
            Create Test
          </button>
          <button className={`teacher-tab ${activeTab === 'pyqs' ? 'active' : ''}`} onClick={() => setActiveTab('pyqs')}>
            PYQ Papers
          </button>
          <button className={`teacher-tab ${activeTab === 'upload' ? 'active' : ''}`} onClick={() => setActiveTab('upload')} data-testid="upload-content-tab">
            AI Content
          </button>
        </div>

        {uploading && activeTab !== 'pyqs' && (
          <div className="uploading-msg">⏳ Uploading file... Please wait.</div>
        )}

        {/* Upload & AI Content Tab - CONTROLLED REGENERATION */}
        {activeTab === 'upload' && (
          <TeacherUpload 
            subjects={subjects}
            initialSubject={selectedSubject}
            onBack={() => setActiveTab('chapters')}
          />
        )}

        {/* Chapters Tab Content */}
        {activeTab === 'chapters' && (
          <>
            <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', marginBottom: '20px' }}>
              <button className="add-btn" onClick={() => setShowAddChapter(true)} data-testid="add-chapter-button">
                + Add Chapter
              </button>
            </div>

            {showAddChapter && (
          <div className="add-form">
            <input
              type="text"
              placeholder="Chapter name"
              value={newChapterName}
              onChange={(e) => setNewChapterName(e.target.value)}
              className="form-input"
              data-testid="chapter-name-input"
            />
            <button onClick={addChapter} className="form-submit">Add</button>
            <button onClick={() => setShowAddChapter(false)} className="form-cancel">Cancel</button>
          </div>
        )}

        <div className="chapters-list">
          {chapters.map((chapter, idx) => (
            <div key={chapter.id} className="chapter-item-teacher" data-testid={`chapter-${chapter.name}`}>
              <div className="chapter-info">
                <span className="chapter-num">Chapter {idx + 1}</span>
                {editingChapter === chapter.id ? (
                  <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                    <input
                      type="text"
                      value={editName}
                      onChange={(e) => setEditName(e.target.value)}
                      className="form-input"
                      style={{ width: '250px', padding: '8px' }}
                    />
                    <button onClick={() => updateChapter(chapter.id)} className="form-submit" style={{ padding: '8px 16px' }}>Save</button>
                    <button onClick={() => setEditingChapter(null)} className="form-cancel" style={{ padding: '8px 16px' }}>Cancel</button>
                  </div>
                ) : (
                  <>
                    <span className="chapter-name">{chapter.name}</span>
                    <button
                      onClick={() => {
                        setEditingChapter(chapter.id);
                        setEditName(chapter.name);
                      }}
                      className="edit-btn-small"
                    >
                      ✏️
                    </button>
                    <button
                      onClick={() => deleteChapter(chapter.id, chapter.name)}
                      className="delete-btn-small"
                      style={{ backgroundColor: '#dc3545', color: 'white', border: 'none', padding: '4px 8px', borderRadius: '4px', cursor: 'pointer', marginLeft: '5px' }}
                    >
                      🗑️
                    </button>
                  </>
                )}
              </div>
              <div className="chapter-actions">
                <button 
                  className={chapter.video_url ? "video-btn uploaded" : "video-btn"}
                  onClick={() => {
                    const url = prompt(chapter.video_url ? `Current video URL:\n${chapter.video_url}\n\nEnter new URL or leave blank to remove:` : 'Enter YouTube/Vimeo/Video URL:', chapter.video_url || '');
                    if (url !== null) {
                      updateVideoUrl(chapter.id, url);
                    }
                  }}
                  title={chapter.video_url ? `Video: ${chapter.video_url}` : 'Add Video Link'}
                >
                  {chapter.video_url ? '✓ 📺 Video Added' : '📺 Add Video'}
                </button>
                
                <label className="upload-btn">
                  + Add Study Material
                  <input
                    type="file"
                    accept=".pdf"
                    onChange={(e) => handleStudyMaterialUpload(e, chapter.id)}
                    disabled={uploading}
                    style={{ display: 'none' }}
                  />
                </label>
              </div>
              
              {/* Study Materials List */}
              {chapterStudyMaterials[chapter.id] && chapterStudyMaterials[chapter.id].length > 0 && (
                <div style={{ marginTop: '10px', paddingTop: '10px', borderTop: '1px dashed #ddd' }}>
                  <span style={{ fontSize: '12px', color: '#666', fontWeight: '600' }}>Study Materials:</span>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginTop: '8px' }}>
                    {chapterStudyMaterials[chapter.id].map((material) => (
                      <div 
                        key={material.id}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '8px',
                          background: '#f8f4ff',
                          padding: '6px 12px',
                          borderRadius: '16px',
                          fontSize: '13px',
                          border: '1px solid #e0d4f7'
                        }}
                      >
                        <a 
                          href={`${process.env.REACT_APP_BACKEND_URL}${material.file_path}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          style={{ color: '#9b59b6', textDecoration: 'none' }}
                          title={material.file_name}
                        >
                          📄 {material.title.length > 20 ? material.title.substring(0, 20) + '...' : material.title}
                        </a>
                        <button
                          onClick={() => deleteStudyMaterial(material.id, material.title)}
                          style={{
                            background: 'none',
                            border: 'none',
                            color: '#dc3545',
                            cursor: 'pointer',
                            padding: '2px',
                            fontSize: '14px'
                          }}
                          title="Delete"
                        >
                          ✕
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
        </>
       )}

       {/* Homework Tab Content */}
       {activeTab === 'homework' && selectedSubject && (
         showAIHomeworkCreator ? (
           <StructuredHomeworkCreator
             subjectId={selectedSubject.id}
             subjectName={selectedSubject.name}
             standard={standard}
             schoolName={user.school_name}
             onBack={() => setShowAIHomeworkCreator(false)}
           />
         ) : (
           <div>
             <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 12 }}>
               <button
                 data-testid="create-ai-homework-btn"
                 onClick={() => setShowAIHomeworkCreator(true)}
                 style={{
                   background: 'linear-gradient(135deg, #48bb78, #38a169)',
                   color: 'white',
                   border: 'none',
                   padding: '10px 20px',
                   borderRadius: 8,
                   fontWeight: 600,
                   cursor: 'pointer',
                   fontSize: 14,
                 }}
               >
                 + Create AI Homework
               </button>
             </div>
             <TeacherAIHomeworkList subjectId={selectedSubject.id} standard={standard} />
           </div>
         )
       )}
       {/* Tests Tab Content */}
       {activeTab === 'tests' && (
         showAITestCreator ? (
           <StructuredTestCreator 
             subjectId={selectedSubject.id}
             subjectName={selectedSubject.name}
             standard={standard} 
             schoolName={user.school_name}
             onBack={() => setShowAITestCreator(false)}
           />
         ) : (
           <div>
             <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 12 }}>
               <button
                 data-testid="create-ai-test-btn"
                 onClick={() => setShowAITestCreator(true)}
                 style={{
                   background: 'linear-gradient(135deg, #667eea, #764ba2)',
                   color: 'white',
                   border: 'none',
                   padding: '10px 20px',
                   borderRadius: 8,
                   fontWeight: 600,
                   cursor: 'pointer',
                   fontSize: 14,
                 }}
               >
                 + Create AI-Evaluated Test
               </button>
             </div>
             <TeacherAITestsList subjectId={selectedSubject.id} standard={standard} />
           </div>
         )
       )}

       {/* UNIFIED EXTRACTION PROGRESS MODAL (within subject view) */}
       {showProgressModal && (
         <div style={{
           position: 'fixed',
           top: 0,
           left: 0,
           right: 0,
           bottom: 0,
           background: 'rgba(0,0,0,0.5)',
           display: 'flex',
           alignItems: 'center',
           justifyContent: 'center',
           zIndex: 1000
         }}>
           <div style={{
             background: 'white',
             borderRadius: '12px',
             padding: '30px',
             maxWidth: '600px',
             width: '90%'
           }}>
             <h2 style={{ color: '#333', marginBottom: '10px' }}>🤖 AI is Doing the Magic for You</h2>
             <p style={{ color: '#666', marginBottom: '25px', fontSize: '16px' }}>
               Sit back and relax meanwhile AI does all the heavy lifting for you ✨
             </p>
             
             <div style={{ marginBottom: '20px' }}>
               <div style={{ 
                 width: '100%', 
                 height: '40px', 
                 backgroundColor: '#e0e0e0', 
                 borderRadius: '20px',
                 overflow: 'hidden',
                 boxShadow: 'inset 0 2px 4px rgba(0,0,0,0.1)'
               }}>
                 <div style={{
                   width: `${extractionProgress}%`,
                   height: '100%',
                   background: extractionFailed ? 
                     'linear-gradient(90deg, #f44336, #d32f2f)' : 
                     'linear-gradient(90deg, #667eea, #764ba2)',
                   transition: 'width 0.5s ease',
                   display: 'flex',
                   alignItems: 'center',
                   justifyContent: 'center',
                   color: 'white',
                   fontWeight: 'bold',
                   fontSize: '18px'
                 }}>
                   {extractionProgress}%
                 </div>
               </div>
             </div>
             
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
                   <strong>Error:</strong> {extractionError || 'Something went wrong while extracting questions.'}
                 </p>
                 {canRetry && (
                   <p style={{ color: '#666', margin: 0 }}>
                     You can close this and try uploading again.
                   </p>
                 )}
               </div>
             )}

             <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
               <button
                 onClick={handleCloseProgressModal}
                 style={{
                   padding: '8px 16px',
                   borderRadius: '6px',
                   border: 'none',
                   backgroundColor: '#e0e0e0',
                   cursor: 'pointer',
                   color: '#000',
                   fontWeight: '500'
                 }}
               >
                 Close
               </button>
             </div>
           </div>
         </div>
       )}
      </div>

       {/* PYQs Tab Content */}
       {activeTab === 'pyqs' && selectedSubject && (
         <div>
           {/* PYQ Upload Modal */}
           <div className="add-form pyq-upload-form">
             <h4 style={{ marginTop: 0, marginBottom: '15px', color: '#F8FAFC', fontFamily: 'Outfit, sans-serif', fontSize: '18px', fontWeight: 600 }}>Upload Previous Year Paper</h4>
             
             <input
               type="number"
               placeholder="Year (e.g., 2022)"
               value={pyqYear}
               onChange={(e) => setPyqYear(e.target.value)}
               className="form-input"
               min="2000"
               max="2030"
               style={{ marginBottom: '10px' }}
             />
             
             <input
               type="text"
               placeholder="Exam Name (e.g., Annual Exam, Midterm)"
               value={pyqExamName}
               onChange={(e) => setPyqExamName(e.target.value)}
               className="form-input"
               style={{ marginBottom: '10px' }}
             />
             
             <input
               type="file"
               accept=".pdf"
               onChange={(e) => setPyqFile(e.target.files[0])}
               className="form-input"
               style={{ marginBottom: '10px' }}
             />
             
             <div style={{ display: 'flex', gap: '10px' }}>
               <button 
                 onClick={uploadPYQ}
                 className="form-submit"
                 disabled={uploading || !pyqYear || !pyqExamName || !pyqFile}
                 style={{ flex: 1 }}
               >
                 {uploading ? '⏳ Uploading...' : '📤 Upload'}
               </button>
               <button 
                 onClick={() => {
                   setPyqYear('');
                   setPyqExamName('');
                   setPyqFile(null);
                 }}
                 className="form-cancel"
                 style={{ flex: 1 }}
               >
                 Cancel
               </button>
             </div>
           </div>

           {/* PYQs List */}
           {pyqList.length === 0 ? (
             <div style={{ textAlign: 'center', padding: '40px', color: '#999' }}>
             </div>
           ) : (
             <div className="content-list" style={{ 
               display: 'grid', 
               gridTemplateColumns: 'repeat(2, 1fr)', 
               gap: '15px',
               marginTop: '20px'
             }}>
               {pyqList.map((pyq) => (
                 <div key={pyq.id} className="content-item" style={{ 
                   padding: '15px', 
                   background: 'rgba(255, 255, 255, 0.08)', 
                   borderRadius: '16px', 
                   border: '1px solid rgba(255, 255, 255, 0.15)',
                   fontFamily: "'Outfit', sans-serif"
                 }}>
                   <div>
                     <div>
                       <h4 style={{ margin: '0 0 8px 0', color: '#F8FAFC', fontSize: '15px', fontWeight: '600', fontFamily: "'Outfit', sans-serif" }}>
                         📄 {pyq.exam_name} - {pyq.year}
                       </h4>
                       <p style={{ margin: '5px 0', fontSize: '13px', color: '#F8FAFC', fontWeight: '500', fontFamily: "'Outfit', sans-serif" }}>
                         <strong>File:</strong> {pyq.file_name}
                       </p>
                       <p style={{ margin: '5px 0', fontSize: '13px', color: '#F8FAFC', fontWeight: '500', fontFamily: "'Outfit', sans-serif" }}>
                         <strong>Uploaded:</strong>{' '}
                         {pyq.upload_date ? new Date(pyq.upload_date).toLocaleDateString() : 'Not available'}
                       </p>
                       <p style={{ margin: '5px 0', fontSize: '13px', fontFamily: "'Outfit', sans-serif" }}>
                         <strong style={{ color: '#F8FAFC' }}>Extraction:</strong>{' '}
                         {pyq.extraction_stage === 'COMPLETED' ? (
                           <span style={{ color: '#4CAF50' }}>
                             ✅ {pyq.questions_extracted_count || 0} questions
                             {pyq.solution_generated && ' | ✅ Solutions generated'}
                           </span>
                         ) : pyq.extraction_status === 'processing' ? (
                           <span style={{ color: '#ff9800' }}>⏳ Processing...</span>
                         ) : pyq.extraction_status === 'failed' ? (
                           <span style={{ color: '#f44336' }}>❌ Failed</span>
                         ) : (
                           <span style={{ color: '#999' }}>⏳ Pending...</span>
                         )}
                       </p>
                     </div>
                     <div style={{ display: 'flex', gap: '8px', marginTop: '10px', flexWrap: 'wrap' }}>
                       {pyq.extraction_stage === 'COMPLETED' && !pyq.solution_generated && (
                         <button
                           onClick={() => generatePYQSolutions(pyq.id)}
                           style={{
                             padding: '6px 12px',
                             background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                             color: 'white',
                             border: 'none',
                             borderRadius: '6px',
                             cursor: 'pointer',
                             fontSize: '12px',
                             fontWeight: '600'
                           }}
                         >
                           🤖 Generate Solutions
                         </button>
                       )}
                       <button
                         onClick={() => deletePYQ(pyq.id, pyq.exam_name)}
                         style={{
                           padding: '6px 12px',
                           background: '#dc3545',
                           color: 'white',
                           border: 'none',
                           borderRadius: '6px',
                           cursor: 'pointer',
                           fontSize: '12px'
                         }}
                       >
                         🗑️ Delete
                       </button>
                     </div>
                   </div>
                 </div>
               ))}
             </div>
           )}
         </div>
       )}

      </>
    );
  }

  return (
    <div className="teacher-view">
      <button onClick={() => { setStandard(null); setSubjects([]); }} className="back-btn">
        ← Back
      </button>
      
      {/* Student Count Banner */}
      <div style={{
        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
        padding: '15px 25px',
        borderRadius: '10px',
        marginBottom: '20px',
        color: 'white',
        display: 'flex',
        alignItems: 'center',
        gap: '10px',
        boxShadow: '0 4px 15px rgba(102, 126, 234, 0.3)'
      }}>
        <span style={{ fontSize: '24px' }}>👥</span>
        <div>
          <div style={{ fontSize: '14px', opacity: 0.9 }}>Total Students Enrolled (Class {standard})</div>
          <div style={{ fontSize: '28px', fontWeight: 'bold' }}>{studentCount}</div>
        </div>
      </div>
      
      <div className="teacher-header">
        <h2 className="section-title">Manage Subjects for Class {standard} 📚</h2>
        <button className="add-btn" onClick={() => setShowAddSubject(true)} data-testid="add-subject-button">
          + Add Subject
        </button>
      </div>

      {showAddSubject && (
        <div className="add-form">
          <input
            type="text"
            placeholder="Subject name"
            value={newSubjectName}
            onChange={(e) => setNewSubjectName(e.target.value)}
            className="form-input"
            data-testid="subject-name-input"
          />
          <button onClick={addSubject} className="form-submit">Add</button>
          <button onClick={() => setShowAddSubject(false)} className="form-cancel">Cancel</button>
        </div>
      )}

      <div className="subjects-list">
        {subjects.map((subject) => (
          <div
            key={subject.id}
            className="subject-item"
            data-testid={`subject-${subject.name}`}
          >
            <div onClick={() => loadChapters(subject)} style={{ flex: 1, cursor: 'pointer' }}>
              <h3>{subject.name}</h3>
              <p>{subject.description}</p>
            </div>
            <div className="subject-actions" style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setEditingSubject(subject.id);
                  setEditName(subject.name);
                  setSelectedSubject(subject);
                }}
                className="edit-btn-small"
                style={{ padding: '4px 8px', borderRadius: '4px', border: '1px solid #ccc', backgroundColor: '#f8f9fa', cursor: 'pointer' }}
              >
                ✏️
              </button>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  deleteSubject(subject.id, subject.name);
                }}
                className="delete-btn-small"
                style={{ backgroundColor: '#dc3545', color: 'white', border: 'none', padding: '4px 8px', borderRadius: '4px', cursor: 'pointer' }}
              >
                🗑️
              </button>
            </div>
          </div>
        ))}
      </div>

      
      {/* UNIFIED EXTRACTION PROGRESS MODAL moved inside selectedSubject view */}

    </div>
  );
}

export default TeacherView;
