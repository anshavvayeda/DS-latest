import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import {
  API, getSubjectVectorIcon, getSubjectColorClass, getSubjectIcon,
  cleanAIContent, FormattedContent,
  translateText, translateBatch, translateContent, extractErrorMessage
} from '@/utils/helpers';
import ToolContentDisplay from '@/components/ToolContentDisplay';
import HomeworkAnswering from '@/components/HomeworkAnswering';
import StudentAITest from '@/components/StudentAITest';
import StudentPerformanceDashboard from '@/components/StudentPerformanceDashboard';
import StudentContentViewer from '@/components/StudentContentViewer';

function StudentView({ user, language, isTeacherPreview = false }) {
  const [standard, setStandard] = useState(null); // Auto-fetched from user profile
  const [subjects, setSubjects] = useState([]);
  const [selectedSubject, setSelectedSubject] = useState(null);
  const [contentSource, setContentSource] = useState(null);
  const [learningMode, setLearningMode] = useState('chapter'); // Default to chapter mode
  const [chapters, setChapters] = useState([]);
  const [pyqs, setPyqs] = useState([]); // NEW: PYQs list
  const [loadingPYQs, setLoadingPYQs] = useState(false); // NEW: PYQs loading state
  const [selectedChapter, setSelectedChapter] = useState(null);
  const [selectedPYQ, setSelectedPYQ] = useState(null); // NEW: Selected PYQ
  const [pyqSolution, setPyqSolution] = useState(null); // NEW: PYQ solution
  const [pyqQuestions, setPyqQuestions] = useState(null); // NEW: PYQ questions from S3
  const [showFrequentPYQs, setShowFrequentPYQs] = useState(false); // NEW: Frequent PYQs modal
  const [frequentPYQsData, setFrequentPYQsData] = useState(null); // NEW: Frequent PYQs data
  const [loadingFrequentPYQs, setLoadingFrequentPYQs] = useState(false); // NEW: Loading state
  const [learningTool, setLearningTool] = useState(null);
  const [toolContent, setToolContent] = useState(null);
  const [loading, setLoading] = useState(false);
  
  // Translation states
  const [translatedUI, setTranslatedUI] = useState({});
  const [translatingPage, setTranslatingPage] = useState(false);
  
  // Homework and Study Materials states
  const [homeworkList, setHomeworkList] = useState([]);
  const [selectedHomework, setSelectedHomework] = useState(null);
  const [homeworkSolution, setHomeworkSolution] = useState(null);
  const [homeworkLoading, setHomeworkLoading] = useState(false);
  const [studyMaterials, setStudyMaterials] = useState([]);
  
  // AI-Evaluated (Structured) Test states
  const [aiTestList, setAiTestList] = useState([]);
  const [selectedAITest, setSelectedAITest] = useState(null);
  const [showPerformanceDashboard, setShowPerformanceDashboard] = useState(false);
  
  // Student classification for quiz filtering
  const [studentClassification, setStudentClassification] = useState('average');
  
  // Parent Dashboard state (collapsed view only - full page is handled in App)
  const [parentDashboardExpanded, setParentDashboardExpanded] = useState(false);

  // Auto-fetch student's standard from profile (or set default for teacher preview)
  useEffect(() => {
    const fetchStudentStandard = async () => {
      // If teacher in preview mode, set default standard to 5
      if (isTeacherPreview) {
        setStandard(5);
        console.log('✅ Teacher preview mode: Default standard set to 5');
        return;
      }
      
      // For actual students, fetch from profile
      try {
        const response = await axios.get(`${API}/student/profile`, { withCredentials: true });
        if (response.data && response.data.standard) {
          setStandard(response.data.standard);
          console.log('✅ Student standard auto-fetched:', response.data.standard);
        }
      } catch (error) {
        console.error('Error fetching student profile:', error);
        // Fallback to standard 5 if profile fetch fails
        setStandard(5);
      }
    };
    
    fetchStudentStandard();
  }, [isTeacherPreview]);

  const loadSubjects = React.useCallback(async () => {
    if (!standard) return; // Don't load until standard is fetched
    
    try {
      const response = await axios.get(`${API}/subjects?standard=${standard}`, { withCredentials: true });
      let subjectsData = response.data;
      
      // Translate subject names and descriptions if Gujarati
      if (language === 'gujarati') {
        console.log('[Translation] Translating subject names...');
        const subjectTexts = [];
        subjectsData.forEach(subject => {
          subjectTexts.push(subject.name);
          if (subject.description) {
            subjectTexts.push(subject.description);
          }
        });
        
        const translations = await translateBatch(subjectTexts, language, 'education');
        
        subjectsData = subjectsData.map(subject => ({
          ...subject,
          name: translations[subject.name] || subject.name,
          description: translations[subject.description] || subject.description
        }));
      }
      
      console.log('✅ Loaded subjects:', subjectsData.length);
      setSubjects(subjectsData);
    } catch (error) {
      console.error('Error loading subjects:', error);
      // Retry without credentials as fallback
      try {
        const response = await axios.get(`${API}/subjects?standard=${standard}`);
        console.log('✅ Loaded subjects (no auth):', response.data.length);
        setSubjects(response.data);
      } catch (fallbackError) {
        console.error('Fallback also failed:', fallbackError);
      }
    }
  }, [language, standard]);


  // Fetch student classification when subject is selected
  useEffect(() => {
    const fetchClassification = async () => {
      if (!selectedSubject || isTeacherPreview) {
        // Teachers in preview mode default to 'strong' to see all quizzes
        if (isTeacherPreview) {
          setStudentClassification('strong');
        }
        return;
      }
      
      try {
        const response = await axios.get(
          `${API}/student/classification/${selectedSubject.id}`,
          { withCredentials: true }
        );
        if (response.data && response.data.classification) {
          setStudentClassification(response.data.classification);
          console.log('Student classification:', response.data.classification);
        }
      } catch (error) {
        console.error('Error fetching classification:', error);
        // Default to average if error
        setStudentClassification('average');
      }
    };
    
    fetchClassification();
  }, [selectedSubject, isTeacherPreview]);

  useEffect(() => {
    loadSubjects();
  }, [loadSubjects]);

  // Translate UI elements when language changes
  useEffect(() => {
    const translateUI = async () => {
      if (language === 'gujarati') {
        setTranslatingPage(true);
        
        const uiTexts = [
          'Select a Subject', 'Choose Content Source', 'Select Learning Mode',
          'Choose a Chapter', 'Pick a Learning Tool',
          'NCERT Textbook', 'School Notes', 'Previous Year Papers',
          'Chapter-wise Learning', 'Topic-wise Learning', 'Concept-wise Learning',
          'Revision Notes', 'Flashcards', 'Practice Quiz',
          'Ask a Doubt',
          'Back', 'Try Again', 'Loading...', 'Generating content with AI...',
          'Unable to Generate Content', 'Please try again or select a different tool.'
        ];
        
        try {
          const translations = await translateBatch(uiTexts, language, 'ui');
          setTranslatedUI(translations);
        } catch (error) {
          console.error('UI translation failed:', error);
        } finally {
          setTranslatingPage(false);
        }
      } else {
        setTranslatedUI({});
      }
    };
    
    translateUI();
  }, [language]);

  // Effect to load PYQ solution when a PYQ is selected
  useEffect(() => {
    const loadPYQSolution = async () => {
      if (!selectedPYQ || pyqSolution) return; // Don't load if no PYQ selected or already loaded
      
      setLoading(true);
      try {
        console.log('[PYQ] Fetching solution for PYQ ID:', selectedPYQ.id);
        console.log('[PYQ] PYQ details:', selectedPYQ);
        
        // Use GET endpoint for read-only access to pre-generated solutions
        const response = await axios.get(`${API}/pyq/${selectedPYQ.id}/solution`, { withCredentials: true });
        
        console.log('[PYQ] Response:', response.data);
        
        if (response.data.success) {
          let solution = response.data.solution;
          
          // Translate if Gujarati
          if (language === 'gujarati') {
            console.log('[Translation] Translating PYQ solution...');
            setTranslatingPage(true);
            solution = await translateContent(solution, language);
            setTranslatingPage(false);
          }
          
          setPyqSolution(solution);
        } else {
          console.error('[PYQ] Solution not available:', response.data.message);
          alert(`❌ ${response.data.message || 'Solution not available yet'}`);
          setSelectedPYQ(null);
        }
      } catch (error) {
        console.error('[PYQ] Error loading PYQ solution:', error);
        console.error('[PYQ] Error response:', error.response?.data);
        alert(`❌ Failed to load PYQ solution: ${error.response?.data?.detail || error.message}`);
        setSelectedPYQ(null);
      } finally {
        setLoading(false);
      }
    };

    loadPYQSolution();
  }, [selectedPYQ, pyqSolution, language]);

  // Effect to load Frequently Asked PYQs when modal opened
  useEffect(() => {
    const loadFrequentPYQs = async () => {
      // Only load if modal is open and subject is selected
      if (!showFrequentPYQs || !selectedSubject) return;
      
      // If data already exists, don't reload (button handler clears it for reload)
      if (frequentPYQsData) return;
      
      setLoadingFrequentPYQs(true);
      console.log('🔥 Loading Frequently Asked PYQs for subject:', selectedSubject.name);
      
      try {
        const studentStandard = user?.student_profile?.standard || 5;
        const response = await axios.post(
          `${API}/subject/${selectedSubject.id}/frequently-asked-pyqs?standard=${studentStandard}`,
          {},
          { withCredentials: true }
        );
        
        console.log('📊 Frequent PYQs response:', response.data);
        
        if (response.data.success) {
          setFrequentPYQsData(response.data.analysis);
        } else {
          alert(response.data.message || 'Failed to load frequent PYQs');
          setShowFrequentPYQs(false);
        }
      } catch (error) {
        console.error('Error loading frequent PYQs:', error);
        alert('❌ Failed to load frequently asked PYQs');
        setShowFrequentPYQs(false);
      } finally {
        setLoadingFrequentPYQs(false);
      }
    };

    loadFrequentPYQs();
  }, [showFrequentPYQs, selectedSubject, user, frequentPYQsData]);  // Added back frequentPYQsData to dependencies

  const selectSubject = async (subject) => {
    setSelectedSubject(subject);
    setContentSource('ncert');
    setLoading(true);
    
    try {
      // Load ALL data in parallel for speed
      
      const [chaptersRes, pyqsRes, homeworkRes, aiTestsRes] = await Promise.allSettled([
        axios.get(`${API}/subjects/${subject.id}/chapters`),
        axios.get(`${API}/subjects/${subject.id}/pyqs?standard=${standard}`),
        axios.get(`${API}/homework?standard=${standard}&subject_id=${subject.id}`, { withCredentials: true }),
        axios.get(`${API}/structured-tests/list/${subject.id}/${standard}`, { withCredentials: true }),
      ]);
      
      // Process chapters
      let chaptersData = chaptersRes.status === 'fulfilled' ? chaptersRes.value.data : [];
      if (!Array.isArray(chaptersData)) chaptersData = [];
      if (language === 'gujarati' && chaptersData.length > 0) {
        const chapterNames = chaptersData.map(ch => ch.name);
        const translations = await translateBatch(chapterNames, language, 'education');
        chaptersData = chaptersData.map(chapter => ({
          ...chapter,
          name: translations[chapter.name] || chapter.name
        }));
      }
      setChapters(chaptersData);
      
      // Process PYQs
      setPyqs(pyqsRes.status === 'fulfilled' ? pyqsRes.value.data : []);
      
      // Process homework
      setHomeworkList(homeworkRes.status === 'fulfilled' ? homeworkRes.value.data : []);
      
      // Process AI tests
      const aiTestsData = aiTestsRes.status === 'fulfilled' ? aiTestsRes.value.data : [];
      setAiTestList(Array.isArray(aiTestsData) ? aiTestsData : []);
    } catch (error) {
      console.error('Error loading data:', error);
    } finally {
      setLoading(false);
    }
  };
  
  // Load study materials when chapter is selected
  const loadStudyMaterials = async (chapterId) => {
    try {
      const response = await axios.get(`${API}/chapters/${chapterId}/study-materials`, { withCredentials: true });
      setStudyMaterials(response.data);
    } catch (error) {
      console.error('Error loading study materials:', error);
      setStudyMaterials([]);
    }
  };
  
  // Open homework for answering
  const openHomework = (homework) => {
    setSelectedHomework(homework);
    setFrequentPYQsData(null);  // Clear frequent PYQs data
    setShowFrequentPYQs(false);
  };

  const selectContentSource = async (source) => {
    setContentSource(source);
    setLearningMode(null);
    setSelectedChapter(null);
  };

  const selectLearningMode = (mode) => {
    setLearningMode(mode);
  };

  const selectChapter = (chapter) => {
    setSelectedChapter(chapter);
    setLearningTool(null);
    setToolContent(null);
    loadStudyMaterials(chapter.id);
  };

  const selectPYQ = async (pyq) => {
    setSelectedPYQ(pyq);
    setPyqSolution(null); // Clear previous solution
    setPyqQuestions(null);

    // Load questions JSON from S3 via backend
    try {
      const response = await axios.get(`${API}/pyq/${pyq.id}/questions`, { withCredentials: true });
      const questions = response.data?.questions || response.data || [];
      setPyqQuestions(questions);
    } catch (error) {
      console.error('[PYQ] Error loading PYQ questions:', error);
      setPyqQuestions(null);
    }

    // useEffect will handle loading the solution
  };

  const selectLearningTool = async (tool) => {
    setLearningTool(tool);
    
    // For doubt chatbot, don't call API immediately - let the component handle it
    if (tool === 'doubt') {
      setToolContent({ isDoubtChat: true });
      return;
    }
    
    // For video, fetch video URL
    if (tool === 'video') {
      setLoading(true);
      try {
        const response = await axios.get(`${API}/chapters/${selectedChapter.id}/video`, { withCredentials: true });
        setToolContent({ 
          isVideo: true, 
          video_url: response.data.video_url,
          chapter_name: response.data.chapter_name
        });
      } catch (error) {
        console.error('Error loading video:', error);
        setToolContent({ 
          isVideo: true, 
          error: 'No video available for this chapter. Please ask your teacher to add one.' 
        });
      } finally {
        setLoading(false);
      }
      return;
    }
    
    // PHASE 4.1: Use READ-ONLY endpoint - NEVER triggers AI generation
    // Map tool names to content types
    const toolToContentType = {
      'revision_notes': 'revision_notes',
      'flashcards': 'flashcards',
      'quiz': 'quiz'
    };
    
    const contentType = toolToContentType[tool];
    if (!contentType) {
      console.error('Unknown tool type:', tool);
      setToolContent(null);
      return;
    }
    
    setLoading(true);
    try {
      // Use the READ-ONLY student endpoint that NEVER generates content
      const response = await axios.get(
        `${API}/student/chapter/${selectedChapter.id}/content/${contentType}`,
        { withCredentials: true }
      );
      
      if (response.data.available && response.data.content) {
        let content = response.data.content;
        
        // Translate AI-generated content if language is Gujarati
        if (language === 'gujarati') {
          console.log('[Translation] Starting AI content translation...');
          setTranslatingPage(true); // Show translation indicator
          
          try {
            content = await translateContent(content, language);
            console.log('[Translation] AI content translation complete!');
          } catch (error) {
            console.error('[Translation] Failed to translate AI content:', error);
          } finally {
            setTranslatingPage(false);
          }
        }
        
        setToolContent(content);
      } else {
        // Content not available - DO NOT trigger generation
        setToolContent({ 
          notAvailable: true, 
          message: response.data.message || 'Content not available yet. Please check back later.' 
        });
      }
    } catch (error) {
      console.error('Error fetching content:', error);
      setToolContent({ 
        notAvailable: true, 
        message: 'Content not available yet. Please check back later.' 
      });
    } finally {
      setLoading(false);
    }
  };

  const resetFlow = () => {
    // Don't reset standard for students (auto-fetched from profile)
    setSelectedSubject(null);
    setChapters([]);
    setPyqs([]);
    setSelectedChapter(null);
    setSelectedPYQ(null);
    setPyqSolution(null);
    setLearningTool(null);
    setToolContent(null);
    setHomeworkList([]);
    setSelectedHomework(null);
    setHomeworkSolution(null);
    setStudyMaterials([]);
    setTestList([]);
    setSelectedTest(null);
  };

  // Helper function to get translated text
  const t = (text) => {
    if (language === 'gujarati' && translatedUI[text]) {
      return translatedUI[text];
    }
    return text;
  };

  // Step 1: Standard Selection (NEW)
  // Step 1: Show loading while fetching student's standard
  if (!standard) {
    return (
      <div className="student-view">
        {isTeacherPreview && (
          <div className="teacher-preview-banner" data-testid="teacher-preview-banner">
            <span className="preview-icon">👁️</span>
            <span className="preview-text">Teacher Preview Mode - View Only (No Submissions Allowed)</span>
          </div>
        )}
        {translatingPage && (
          <div className="translation-banner">
            <span className="translation-spinner">🌐</span>
            Translating to Gujarati...
          </div>
        )}
        <div className="loading-content">
          <div className="loading-spinner"></div>
          <p>Loading your profile...</p>
        </div>
      </div>
    );
  }

  // Step 2: Subject Selection (standard auto-fetched from profile)
  if (!selectedSubject) {
    // Helper function to get progress color class
    const getProgressColorClass = (percentage) => {
      if (percentage < 25) return 'progress-low';
      if (percentage < 50) return 'progress-medium';
      if (percentage < 75) return 'progress-good';
      return 'progress-excellent';
    };

    return (
      <div className="student-view">
        {isTeacherPreview && (
          <div className="teacher-preview-banner" data-testid="teacher-preview-banner">
            <span className="preview-icon">👁️</span>
            <span className="preview-text">Teacher Preview Mode - View Only (No Submissions Allowed)</span>
          </div>
        )}
        {!isTeacherPreview && user?.student_profile?.name && (
          <div className="student-greeting" data-testid="student-greeting">
            <span className="greeting-text">
              Hi {user.student_profile.name}, Which subject do you want to study today?
            </span>
          </div>
        )}
        {isTeacherPreview && (
          <div className="standard-selector" style={{
            background: 'rgba(255, 255, 255, 0.05)',
            padding: '20px',
            borderRadius: '12px',
            marginBottom: '24px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '16px',
            flexWrap: 'wrap'
          }}>
            <span style={{ color: '#94A3B8', fontWeight: 600 }}>Preview Standard:</span>
            {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map(std => (
              <button
                key={std}
                onClick={() => {
                  setStandard(std);
                  setSelectedSubject(null);
                }}
                style={{
                  padding: '10px 20px',
                  borderRadius: '8px',
                  border: standard === std ? '2px solid #667eea' : '2px solid rgba(255,255,255,0.1)',
                  background: standard === std ? '#667eea' : 'rgba(255,255,255,0.05)',
                  color: 'white',
                  cursor: 'pointer',
                  fontWeight: standard === std ? 700 : 500,
                  transition: 'all 0.2s'
                }}
                onMouseEnter={(e) => {
                  if (standard !== std) {
                    e.target.style.background = 'rgba(255,255,255,0.1)';
                  }
                }}
                onMouseLeave={(e) => {
                  if (standard !== std) {
                    e.target.style.background = 'rgba(255,255,255,0.05)';
                  }
                }}
              >
                Class {std}
              </button>
            ))}
          </div>
        )}
        
        <div className="subjects-grid">
          {subjects.map((subject, index) => {
            const colorClass = getSubjectColorClass(subject.name);
            // Calculate progress based on actual chapter completion
            const progressPercent = subject.syllabus_complete_percent || 0;
            const progressColorClass = getProgressColorClass(progressPercent);
            return (
              <div
                key={subject.id}
                className={`subject-card ${colorClass}`}
                onClick={() => selectSubject(subject)}
                data-testid={`subject-${subject.name}`}
              >
                {getSubjectVectorIcon(subject.name)}
                <div className="subject-card-content">
                  <h3>{subject.name}</h3>
                </div>
                <div className="subject-progress-container">
                  <div className="subject-progress-label">
                    <span>Syllabus</span>
                    <span>{progressPercent}%</span>
                  </div>
                  <div className="subject-progress-bar">
                    <div 
                      className={`subject-progress-fill ${progressColorClass}`}
                      style={{ width: `${progressPercent}%` }}
                    />
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  // Step 3: Two Column Layout - Chapters and PYQs
  if (!selectedChapter && !selectedPYQ && !selectedHomework && !selectedAITest) {
    return (
      <div className="student-view">
        {isTeacherPreview && (
          <div className="teacher-preview-banner" data-testid="teacher-preview-banner">
            <span className="preview-icon">👁️</span>
            <span className="preview-text">Teacher Preview Mode - View Only (No Submissions Allowed)</span>
          </div>
        )}
        <button onClick={() => setSelectedSubject(null)} className="back-btn">← Back</button>
        <p className="section-subtitle">{t('Choose what you want to study')}</p>
        
        <div className="two-column-layout">
          {/* Left Column - Chapters */}
          <div className="column chapters-column">
            <h3 className="column-title">📚 {t('Chapters')}</h3>
            {loading ? (
              <div className="loading-small">Loading chapters...</div>
            ) : chapters.length > 0 ? (
              <div className="chapters-list">
                {chapters.map((chapter, idx) => (
                  <div
                    key={chapter.id}
                    className="chapter-item"
                    onClick={() => selectChapter(chapter)}
                    data-testid={`chapter-${chapter.name}`}
                  >
                    <span className="chapter-num">Chapter {idx + 1}</span>
                    <span className="chapter-name">{chapter.name}</span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="info-box">
                <p>No chapters available yet. Please ask your teacher to add chapters.</p>
              </div>
            )}
          </div>

          {/* Right Column - PYQs */}
          <div className="column pyqs-column">
            <h3 className="column-title">📝 {t('Previous Year Questions')}</h3>
            {pyqs.length > 0 ? (
              <>
                <div className="pyqs-list">
                  {pyqs.map((pyq) => (
                    <div
                      key={pyq.id}
                      className="pyq-item"
                      onClick={(e) => {
                        e.stopPropagation();
                        selectPYQ(pyq);
                      }}
                      data-testid={`pyq-${pyq.year}`}
                    >
                      <span className="pyq-year">{pyq.year}</span>
                      <span className="pyq-name">{pyq.exam_name}</span>
                    </div>
                  ))}
                </div>
                
                {/* Frequently Asked PYQs Button - only if 2+ PYQs */}
                {pyqs.length >= 2 && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      setSelectedPYQ(null);
                      setPyqSolution(null);
                      setSelectedHomework(null);
                      setFrequentPYQsData(null); // Clear cached data to force reload
                      setShowFrequentPYQs(true);
                    }}
                    style={{
                      width: '100%',
                      marginTop: '15px',
                      padding: '15px',
                      background: 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
                      color: 'white',
                      border: 'none',
                      borderRadius: '10px',
                      fontSize: '16px',
                      fontWeight: 'bold',
                      cursor: 'pointer',
                      boxShadow: '0 4px 15px rgba(240, 147, 251, 0.4)',
                      transition: 'transform 0.2s'
                    }}
                    onMouseEnter={(e) => e.target.style.transform = 'translateY(-2px)'}
                    onMouseLeave={(e) => e.target.style.transform = 'translateY(0)'}
                  >
                    🔥 Frequently Asked PYQs
                  </button>
                )}
              </>
            ) : (
              <div className="info-box">
                <p>No previous year questions available yet. Please ask your teacher to upload PYQs.</p>
              </div>
            )}
          </div>
        </div>
        
        {/* Homework Section */}
        <div className="homework-section" style={{ marginTop: '30px' }}>
          <h3 className="section-header">📝 {t('Homework')}</h3>
          {homeworkList.length > 0 ? (
            <div className="homework-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '15px' }}>
              {homeworkList.map((hw) => (
                <div 
                  key={hw.id} 
                  className="homework-card"
                  data-testid={`homework-${hw.id}`}
                  style={{ 
                    borderRadius: '12px',
                    padding: '20px',
                    color: 'white',
                    boxShadow: '0 4px 15px rgba(102, 126, 234, 0.3)'
                  }}
                >
                  <h4 style={{ margin: '0 0 10px 0', fontSize: '16px' }}>📄 {hw.title}</h4>
                  <p style={{ margin: '5px 0', fontSize: '13px', opacity: '0.9' }}>
                    📅 Due: {new Date(hw.expiry_date).toLocaleDateString()}
                  </p>
                  <p style={{ margin: '5px 0', fontSize: '12px', opacity: '0.8' }}>
                    {hw.file_name}
                  </p>
                  <div style={{ marginTop: '15px', display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
                    <a 
                      href={`${process.env.REACT_APP_BACKEND_URL}${hw.file_path}`}
                      target="_blank" 
                      rel="noopener noreferrer"
                      style={{
                        background: 'rgba(255,255,255,0.2)',
                        color: 'white',
                        padding: '8px 16px',
                        borderRadius: '20px',
                        textDecoration: 'none',
                        fontSize: '13px',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '5px'
                      }}
                    >
                      📥 View PDF
                    </a>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        openHomework(hw);
                      }}
                      data-testid={`homework-help-${hw.id}`}
                      style={{
                        background: '#48BB78',
                        color: 'white',
                        padding: '8px 16px',
                        borderRadius: '20px',
                        border: 'none',
                        cursor: 'pointer',
                        fontSize: '13px',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '5px'
                      }}
                    >
                      📝 Answer Homework
                    </button>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="info-box">
              <p style={{ margin: 0 }}>🎉 No homework assigned! Enjoy your free time.</p>
            </div>
          )}
        </div>
        
        {/* Tests Section */}
        <div className="tests-section" style={{ marginTop: '30px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
            <h3 className="section-header" style={{ margin: 0 }}>
              {showPerformanceDashboard ? '' : t('Tests')}
            </h3>
            <button
              onClick={() => setShowPerformanceDashboard(!showPerformanceDashboard)}
              data-testid="performance-dashboard-btn"
              style={{
                background: showPerformanceDashboard ? '#334155' : 'linear-gradient(135deg, #667eea, #764ba2)',
                color: 'white',
                border: 'none',
                padding: '8px 18px',
                borderRadius: '8px',
                cursor: 'pointer',
                fontSize: '13px',
                fontWeight: 700,
              }}
            >
              {showPerformanceDashboard ? 'Back to Tests' : 'My Performance'}
            </button>
          </div>
          
          {showPerformanceDashboard ? (
            <StudentPerformanceDashboard
              subjectId={selectedSubject.id}
              subjectName={selectedSubject.name}
              onClose={() => setShowPerformanceDashboard(false)}
            />
          ) : (
          <>
          {/* AI-Evaluated Tests */}
          {aiTestList.length > 0 && (
            <div style={{ marginBottom: '20px' }}>
              <h4 style={{ color: '#c4b5fd', fontSize: '14px', fontWeight: 600, marginBottom: '12px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                AI-Evaluated Tests
              </h4>
              <div className="tests-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '15px' }}>
                {aiTestList.map((aiTest) => (
                  <div 
                    key={aiTest.id} 
                    className="test-card"
                    data-testid={`ai-test-${aiTest.id}`}
                    style={{ 
                      borderRadius: '12px',
                      padding: '20px',
                      color: 'white',
                      boxShadow: '0 4px 15px rgba(102, 126, 234, 0.3)',
                      border: '2px solid rgba(102, 126, 234, 0.4)',
                      background: 'linear-gradient(135deg, rgba(102,126,234,0.15), rgba(118,75,162,0.15))'
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px' }}>
                      <span style={{ background: 'linear-gradient(135deg, #667eea, #764ba2)', padding: '2px 8px', borderRadius: '4px', fontSize: '10px', fontWeight: 700 }}>AI</span>
                      <h4 style={{ margin: 0, fontSize: '16px' }}>{aiTest.title}</h4>
                    </div>
                    <p style={{ margin: '5px 0', fontSize: '13px', opacity: '0.9' }}>
                      {aiTest.question_count} questions | {aiTest.total_marks} marks
                    </p>
                    <p style={{ margin: '5px 0', fontSize: '13px', opacity: '0.9' }}>
                      Duration: {aiTest.duration_minutes} min
                    </p>
                    <p style={{ margin: '5px 0', fontSize: '13px', opacity: '0.9' }}>
                      Deadline: {aiTest.submission_deadline ? new Date(aiTest.submission_deadline).toLocaleDateString() : 'N/A'}
                    </p>
                    {aiTest.submitted && aiTest.score !== null && (
                      <p style={{ margin: '10px 0 0', fontSize: '14px', background: 'rgba(255,255,255,0.15)', padding: '6px 12px', borderRadius: '6px', fontWeight: 600 }}>
                        Score: {aiTest.score}/{aiTest.total_marks} ({aiTest.percentage}%)
                      </p>
                    )}
                    <div style={{ marginTop: '15px' }}>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          console.log('AI Test button clicked! Setting selectedAITest to:', aiTest.title);
                          setSelectedAITest(aiTest);
                        }}
                        data-testid={`ai-test-action-${aiTest.id}`}
                        style={{
                          background: aiTest.submitted ? '#667eea' : '#10b981',
                          color: 'white',
                          padding: '10px 20px',
                          borderRadius: '20px',
                          border: 'none',
                          cursor: 'pointer',
                          fontSize: '14px',
                          fontWeight: 'bold',
                          width: '100%'
                        }}
                      >
                        {aiTest.submitted ? 'View Results' : 'Attempt Test'}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
          
          {/* Regular Tests */}
          {aiTestList.length === 0 && (
            <div className="info-box">
              <p style={{ margin: 0 }}>No tests scheduled yet.</p>
            </div>
          )}
          </>
          )}
        </div>
      </div>
    );
  }
  
  console.log('StudentView render - selectedHomework:', selectedHomework ? 'YES' : 'NO');
  console.log('StudentView render - selectedSubject:', selectedSubject ? selectedSubject.name : 'NO');
  console.log('StudentView render - selectedAITest:', selectedAITest ? selectedAITest.title : 'NO');
  
  // AI-Evaluated Test Taking/Results View
  if (selectedAITest) {
    console.log('Rendering StudentAITest for:', selectedAITest.title);
    return (
      <div className="student-view">
        <StudentAITest
          test={selectedAITest}
          userId={user?.id}
          onClose={() => {
            setSelectedAITest(null);
            // Reload AI tests to update status
            if (selectedSubject && standard) {
              axios.get(`${API}/structured-tests/list/${selectedSubject.id}/${standard}`, { withCredentials: true })
                .then(res => setAiTestList(res.data || []))
                .catch(err => console.error('Error reloading AI tests:', err));
            }
          }}
        />
      </div>
    );
  }

  // Homework Answering View
  if (selectedHomework) {
    return (
      <div className="student-view">
        {isTeacherPreview && (
          <div className="teacher-preview-banner" data-testid="teacher-preview-banner">
            <span className="preview-icon">👁️</span>
            <span className="preview-text">Teacher Preview Mode - View Only (No Submissions Allowed)</span>
          </div>
        )}
        <HomeworkAnswering
          homework={selectedHomework}
          isTeacherPreview={isTeacherPreview}
          onBack={() => {
            setSelectedHomework(null);
            setHomeworkSolution(null);
          }}
          onSubmit={() => {
            // After submission, go back to homework list
            setSelectedHomework(null);
            setHomeworkSolution(null);
            // Optionally reload homework list to update submission status
          }}
        />
      </div>
    );
  }

  // Frequently Asked PYQs Modal
  if (showFrequentPYQs) {
    return (
      <div className="student-view">
        <button onClick={() => { setShowFrequentPYQs(false); setFrequentPYQsData(null); }} className="back-btn">
          ← Back
        </button>
        
        <div className="frequent-pyqs-container" style={{ maxWidth: '900px', margin: '0 auto', padding: '20px' }}>
          <h2 style={{ 
            fontSize: '28px', 
            marginBottom: '10px',
            background: 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
            fontWeight: 'bold'
          }}>
            🔥 Frequently Asked Questions
          </h2>
          <p style={{ color: '#666', marginBottom: '30px' }}>
            Questions that appear multiple times across different exam papers
          </p>
          
          {loadingFrequentPYQs ? (
            <div style={{ textAlign: 'center', padding: '60px' }}>
              <div className="loading-spinner"></div>
              <p>Analyzing PYQs for patterns...</p>
            </div>
          ) : frequentPYQsData ? (
            <>
              {/* Exact Repeats Section */}
              {frequentPYQsData.exact_repeats && frequentPYQsData.exact_repeats.length > 0 && (
                <div style={{ marginBottom: '40px' }}>
                  <h3 style={{ 
                    fontSize: '22px', 
                    color: '#e74c3c', 
                    marginBottom: '20px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '10px'
                  }}>
                    🔴 Exact Repeats ({frequentPYQsData.exact_repeats.length})
                    <span style={{ fontSize: '14px', color: '#999', fontWeight: 'normal' }}>
                      Same question appearing multiple times
                    </span>
                  </h3>
                  
                  {frequentPYQsData.exact_repeats.map((item, idx) => (
                    <div key={idx} style={{
                      background: '#fff5f5',
                      border: '3px solid #e74c3c',
                      borderRadius: '12px',
                      padding: '20px',
                      marginBottom: '15px'
                    }}>
                      <div style={{ 
                        display: 'flex', 
                        justifyContent: 'space-between',
                        alignItems: 'flex-start',
                        marginBottom: '15px'
                      }}>
                        <div style={{ flex: 1 }}>
                          <div style={{ fontSize: '16px', fontWeight: '600', color: '#333', lineHeight: '1.6' }}>
                            {item.question}
                          </div>
                        </div>
                        <div style={{
                          background: '#e74c3c',
                          color: 'white',
                          padding: '8px 16px',
                          borderRadius: '20px',
                          fontSize: '14px',
                          fontWeight: 'bold',
                          marginLeft: '15px',
                          flexShrink: 0
                        }}>
                          {item.count}× Repeated
                        </div>
                      </div>
                      
                      <div style={{ 
                        display: 'flex', 
                        flexWrap: 'wrap', 
                        gap: '8px',
                        marginTop: '12px'
                      }}>
                        {item.appearances && item.appearances.map((app, i) => (
                          <span key={i} style={{
                            background: '#ffd7d7',
                            color: '#c92a2a',
                            padding: '5px 12px',
                            borderRadius: '15px',
                            fontSize: '13px',
                            fontWeight: '500'
                          }}>
                            📅 {app.exam} {app.year}
                          </span>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}
              
              {/* Similar Concepts Section */}
              {frequentPYQsData.similar_concepts && frequentPYQsData.similar_concepts.length > 0 && (
                <div style={{ marginBottom: '40px' }}>
                  <h3 style={{ 
                    fontSize: '22px', 
                    color: '#f5576c', 
                    marginBottom: '20px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '10px'
                  }}>
                    🟠 Similar Concepts ({frequentPYQsData.similar_concepts.length})
                    <span style={{ fontSize: '14px', color: '#999', fontWeight: 'normal' }}>
                      Different questions, same concept
                    </span>
                  </h3>
                  
                  {frequentPYQsData.similar_concepts.map((concept, idx) => (
                    <div key={idx} style={{
                      background: '#fff7ed',
                      border: '3px solid #f5576c',
                      borderRadius: '12px',
                      padding: '20px',
                      marginBottom: '15px'
                    }}>
                      <div style={{ 
                        display: 'flex', 
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        marginBottom: '15px'
                      }}>
                        <h4 style={{ 
                          fontSize: '18px', 
                          fontWeight: '700', 
                          color: '#333',
                          margin: 0
                        }}>
                          💡 {concept.concept}
                        </h4>
                        <div style={{
                          background: '#f5576c',
                          color: 'white',
                          padding: '8px 16px',
                          borderRadius: '20px',
                          fontSize: '14px',
                          fontWeight: 'bold'
                        }}>
                          {concept.count}× Asked
                        </div>
                      </div>
                      
                      <div style={{ marginTop: '15px' }}>
                        {concept.variations && concept.variations.map((variation, i) => (
                          <div key={i} style={{
                            background: 'white',
                            padding: '12px 15px',
                            borderRadius: '8px',
                            marginBottom: '8px',
                            border: '1px solid #ffd0d0'
                          }}>
                            <div style={{ fontSize: '15px', color: '#333', marginBottom: '5px' }}>
                              {variation.question}
                            </div>
                            <span style={{
                              fontSize: '12px',
                              color: '#f5576c',
                              fontWeight: '500'
                            }}>
                              📄 {variation.exam} {variation.year}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}
              
              {/* Summary Stats */}
              {(frequentPYQsData.total_questions || frequentPYQsData.exact_repeat_count) && (
                <div style={{
                  background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                  color: 'white',
                  padding: '20px',
                  borderRadius: '12px',
                  textAlign: 'center'
                }}>
                  <h4 style={{ margin: '0 0 15px 0', fontSize: '18px' }}>📊 Analysis Summary</h4>
                  <div style={{ 
                    display: 'grid', 
                    gridTemplateColumns: 'repeat(3, 1fr)', 
                    gap: '15px',
                    fontSize: '14px'
                  }}>
                    <div>
                      <div style={{ fontSize: '24px', fontWeight: 'bold' }}>
                        {frequentPYQsData.total_questions || 0}
                      </div>
                      <div style={{ opacity: 0.9 }}>Total Questions</div>
                    </div>
                    <div>
                      <div style={{ fontSize: '24px', fontWeight: 'bold' }}>
                        {frequentPYQsData.exact_repeat_count || 0}
                      </div>
                      <div style={{ opacity: 0.9 }}>Exact Repeats</div>
                    </div>
                    <div>
                      <div style={{ fontSize: '24px', fontWeight: 'bold' }}>
                        {frequentPYQsData.similar_concept_groups || 0}
                      </div>
                      <div style={{ opacity: 0.9 }}>Concept Groups</div>
                    </div>
                  </div>
                </div>
              )}
            </>
          ) : null}
        </div>
      </div>
    );
  }

  // PYQ Solution View
  if (selectedPYQ) {
    return (
      <div className="student-view">
        <button onClick={() => { setSelectedPYQ(null); setPyqSolution(null); }} className="back-btn">
          ← {t('Back')}
        </button>
        
        <h2 className="section-title">{selectedPYQ.exam_name} - {selectedPYQ.year}</h2>
        
        {loading || !pyqSolution ? (
          <div className="loading-content">
            <div className="loading-spinner"></div>
            <p>{t('Generating solutions with AI...')}</p>
            <p className="loading-subtitle">{t('This may take a moment')}</p>
          </div>
        ) : (
          <div className="pyq-solution-content">
            {/* Fun Header with Exam Info */}
            <div className="pyq-fun-header">
              <div className="pyq-info-badge">
                <span className="badge-icon">🎯</span>
                <div>
                  <div className="badge-label">{t('Total Marks')}</div>
                  <div className="badge-value">{pyqSolution.total_marks || 'N/A'}</div>
                </div>
              </div>
              <div className="pyq-info-badge">
                <span className="badge-icon">⏱️</span>
                <div>
                  <div className="badge-label">{t('Time Allowed')}</div>
                  <div className="badge-value">{pyqSolution.time_allowed || 'N/A'}</div>
                </div>
              </div>
            </div>
            
            {/* Questions and Answers */}
            <div className="qa-container">
              {pyqSolution.solutions && pyqSolution.solutions.map((sol, idx) => (
                <div key={idx} className="qa-pair" data-question-num={idx + 1}>
                  
                  {/* Question Box */}
                  <div className="question-box">
                    <div className="question-header">
                      <span className="question-number">❓ {t('Question')} {sol.question_number || (idx + 1)}</span>
                      <div className="question-badges">
                        {sol.marks && <span className="marks-badge">🌟 {sol.marks} {t('marks')}</span>}
                        {sol.difficulty && (
                          <span className={`difficulty-badge difficulty-${sol.difficulty?.toLowerCase()}`}>
                            {sol.difficulty === 'easy' ? '😊' : sol.difficulty === 'medium' ? '🤔' : '🔥'} {sol.difficulty}
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="question-text">
                      {(() => {
                        let text = sol.question || sol.question_text;

                        // If question text is missing, try to pull it from PYQ questions JSON
                        if (!text && pyqQuestions && Array.isArray(pyqQuestions)) {
                          const match = pyqQuestions.find((q) => {
                            const qNum = q.question_number || q.question_no || q.number;
                            const sNum = sol.question_number || sol.question_no || sol.number;
                            return qNum && sNum && String(qNum) == String(sNum);
                          }) || pyqQuestions[idx];

                          if (match) {
                            text = match.question || match.question_text || match.text || '';
                          }
                        }

                        return <FormattedContent content={text || ''} />;
                      })()}
                    </div>
                  </div>
                  
                  {/* Answer Box */}
                  <div className="answer-box">
                    <div className="answer-header">
                      <span className="answer-label">✅ {t('Solution')}</span>
                    </div>
                    <div className="answer-text">
                      {/* Handle both old (sol.answer) and new (sol.solution_steps + sol.final_answer) structures */}
                      {sol.solution_steps && sol.solution_steps.length > 0 ? (
                        <div className="solution-steps">
                          {sol.understanding && (
                            <div className="understanding-box">
                              <strong>📖 Understanding:</strong>
                              <FormattedContent content={sol.understanding} />
                            </div>
                          )}
                          <div className="steps-list">
                            {sol.solution_steps.map((step, stepIdx) => (
                              <div key={stepIdx} className="solution-step">
                                <span className="step-number">{stepIdx + 1}</span>
                                <FormattedContent content={step} />
                              </div>
                            ))}
                          </div>
                          {sol.final_answer && (
                            <div className="final-answer-box">
                              <strong>🎯 Final Answer:</strong>
                              <FormattedContent content={sol.final_answer} />
                            </div>
                          )}
                          {sol.exam_tip && (
                            <div className="exam-tip-box">
                              <strong>📝 Exam Tip:</strong> {cleanAIContent(sol.exam_tip)}
                            </div>
                          )}
                          {sol.common_mistake && (
                            <div className="common-mistake-box">
                              <strong>⚠️ Common Mistake:</strong> {cleanAIContent(sol.common_mistake)}
                            </div>
                          )}
                        </div>
                      ) : (
                        <FormattedContent content={sol.answer || sol.solution || 'Solution not available'} />
                      )}
                    </div>
                    {sol.topics && sol.topics.length > 0 && (
                      <div className="topics-section">
                        <span className="topics-label">📚 {t('Topics')}:</span>
                        <div className="topics-tags">
                          {sol.topics.map((topic, i) => (
                            <span key={i} className="topic-tag">{topic}</span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
            
            {/* Exam Tips Section */}
            {pyqSolution.tips && pyqSolution.tips.length > 0 && (
              <div className="exam-tips-section">
                <h3 className="tips-title">💡 {t('Exam Tips')} & {t('Tricks')}</h3>
                <div className="tips-grid">
                  {pyqSolution.tips.map((tip, i) => (
                    <div key={i} className="tip-card">
                      <span className="tip-number">{i + 1}</span>
                      <p className="tip-text">{tip}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    );
  }

  // Step 5: Learning Tools Selection
  if (!learningTool) {
    return (
      <div className="student-view">
        <button onClick={() => setSelectedChapter(null)} className="back-btn">← Back</button>
        <h2 className="section-title">{selectedChapter.name}</h2>
        <p className="section-subtitle">{t('Pick a Learning Tool')}</p>
        <div className="tools-grid">
          <div className="tool-card" onClick={() => selectLearningTool('revision_notes')} data-testid="tool-revision">
            <div className="tool-icon">🧠</div>
            <h3>{t('Revision Notes')}</h3>
          </div>
          <div className="tool-card" onClick={() => selectLearningTool('flashcards')} data-testid="tool-flashcards">
            <div className="tool-icon"><svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="2" y="4" width="20" height="16" rx="2"/><path d="M12 4v16"/><path d="M2 12h20"/></svg></div>
            <h3>{t('Flashcards')}</h3>
          </div>
          <div className="tool-card" onClick={() => selectLearningTool('quiz')} data-testid="tool-quiz">
            <div className="tool-icon">✍️</div>
            <h3>{t('Practice Quiz')}</h3>
          </div>
          <div className="tool-card" onClick={() => selectLearningTool('doubt')} data-testid="tool-doubt">
            <div className="tool-icon">❓</div>
            <h3>{t('Ask a Doubt')}</h3>
          </div>
          <div className="tool-card" onClick={() => selectLearningTool('video')} data-testid="tool-video">
            <div className="tool-icon">📺</div>
            <h3>{t('Watch Video')}</h3>
          </div>
        </div>
        
        {/* Study Materials Section */}
        {studyMaterials.length > 0 && (
          <div className="study-materials-section" style={{ marginTop: '30px' }}>
            <h3 className="column-title" style={{ marginBottom: '15px' }}>{t('Study Materials')}</h3>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))', gap: '15px' }}>
              {studyMaterials.map((material) => (
                <div 
                  key={material.id}
                  data-testid={`study-material-${material.id}`}
                  style={{
                    background: 'white',
                    borderRadius: '12px',
                    padding: '20px',
                    boxShadow: '0 2px 10px rgba(0,0,0,0.08)',
                    border: '1px solid #e0e0e0'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '10px' }}>
                    <span style={{ 
                      background: '#9b59b6',
                      color: 'white',
                      padding: '4px 10px',
                      borderRadius: '12px',
                      fontSize: '12px',
                      textTransform: 'capitalize'
                    }}>
                      {material.material_type}
                    </span>
                  </div>
                  <h4 style={{ margin: '0 0 10px 0', fontSize: '15px', color: '#333' }}>
                    {material.title}
                  </h4>
                  <p style={{ fontSize: '12px', color: '#666', margin: '0 0 15px 0' }}>
                    📄 {material.file_name}
                  </p>
                  <button
                    onClick={async () => {
                      try {
                        const response = await axios.get(`${API}/study-materials/${material.id}/download-url`, { withCredentials: true });
                        if (response.data.download_url) {
                          window.open(response.data.download_url, '_blank');
                        }
                      } catch (error) {
                        console.error('Failed to get download URL:', error);
                        alert('Failed to download file. Please try again.');
                      }
                    }}
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '5px',
                      background: '#9b59b6',
                      color: 'white',
                      padding: '8px 16px',
                      borderRadius: '20px',
                      border: 'none',
                      cursor: 'pointer',
                      fontSize: '13px'
                    }}
                  >
                    📥 Download
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  }

  // Step 6: Display Tool Content
  return (
    <div className="student-view">
      {isTeacherPreview && (
        <div className="teacher-preview-banner" data-testid="teacher-preview-banner">
          <span className="preview-icon">👁️</span>
          <span className="preview-text">Teacher Preview Mode - View Only (No Submissions Allowed)</span>
        </div>
      )}
      <button onClick={() => { setLearningTool(null); setToolContent(null); }} className="back-btn">← Back</button>
      
      {loading ? (
        <div className="loading-content">
          <div className="loading-spinner"></div>
          <p>{t('Loading...')}</p>
        </div>
      ) : learningTool === 'video' && toolContent?.isVideo ? (
        // Video Player with Strict Guardrails
        <div className="video-player-container">
          <h2 className="section-title">📺 {selectedChapter.name}</h2>
          {toolContent.error ? (
            <div className="error-content">
              <div className="error-icon">😕</div>
              <h3>{t('No Video Available')}</h3>
              <p>{toolContent.error}</p>
            </div>
          ) : (
            <div className="video-wrapper-strict">
              {(() => {
                const url = toolContent.video_url;
                // YouTube embed with MAXIMUM restrictions
                if (url.includes('youtube.com') || url.includes('youtu.be')) {
                  let videoId = '';
                  if (url.includes('youtu.be/')) {
                    videoId = url.split('youtu.be/')[1].split('?')[0];
                  } else if (url.includes('youtube.com/watch?v=')) {
                    videoId = url.split('v=')[1].split('&')[0];
                  } else if (url.includes('youtube.com/embed/')) {
                    videoId = url.split('embed/')[1].split('?')[0];
                  }
                  return (
                    <div className="video-embed-container">
                      <iframe
                        className="video-iframe-strict"
                        src={`https://www.youtube.com/embed/${videoId}?rel=0&modestbranding=1&controls=1&disablekb=1&fs=0&iv_load_policy=3&playsinline=1&showinfo=0&autohide=1&enablejsapi=0`}
                        title={selectedChapter.name}
                        frameBorder="0"
                        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                        allowFullScreen={false}
                        sandbox="allow-scripts allow-same-origin"
                      ></iframe>
                      {/* Overlay to prevent clicking through to YouTube */}
                      <div className="video-click-blocker"></div>
                    </div>
                  );
                }
                // Vimeo embed with restrictions
                else if (url.includes('vimeo.com')) {
                  const videoId = url.split('vimeo.com/')[1].split('?')[0];
                  return (
                    <div className="video-embed-container">
                      <iframe
                        className="video-iframe-strict"
                        src={`https://player.vimeo.com/video/${videoId}?byline=0&portrait=0&title=0&controls=1&dnt=1`}
                        title={selectedChapter.name}
                        frameBorder="0"
                        allow="autoplay; fullscreen; picture-in-picture"
                        allowFullScreen={false}
                      ></iframe>
                      <div className="video-click-blocker"></div>
                    </div>
                  );
                }
                // Direct video with minimal controls
                else {
                  return (
                    <div 
                      className="video-embed-container"
                      onContextMenu={(e) => e.preventDefault()}
                    >
                      <video
                        className="video-player-strict"
                        controls
                        controlsList="nodownload nofullscreen noremoteplayback"
                        disablePictureInPicture
                        onContextMenu={(e) => e.preventDefault()}
                      >
                        <source src={url} type="video/mp4" />
                        Your browser does not support the video tag.
                      </video>
                    </div>
                  );
                }
              })()}
              
              {/* Instruction message for parents/teachers */}
              <div className="video-safety-notice">
                <span className="safety-icon">🔒</span>
                <p>{t('Safe Mode Active: Student can only watch this video. External links disabled.')}</p>
              </div>
            </div>
          )}
        </div>
      ) : (learningTool === 'doubt' || toolContent) ? (
        <ToolContentDisplay 
          learningTool={learningTool}
          toolContent={toolContent}
          selectedSubject={selectedSubject}
          selectedChapter={selectedChapter}
          contentSource={contentSource}
          language={language}
          translatedUI={translatedUI}
          studentClassification={studentClassification}
        />
      ) : (
        <div className="error-content">
          <div className="error-icon">😕</div>
          <h3>{t('Unable to Generate Content')}</h3>
          <p>{t('Please try again or select a different tool.')}</p>
          <button className="retry-btn" onClick={() => selectLearningTool(learningTool)}>
            🔄 {t('Try Again')}
          </button>
        </div>
      )}
    </div>
  );
}

export default StudentView;
