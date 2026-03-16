import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import '@/App.css';
import '@/components/LearningTools.css';
import StudentProfileView from '@/components/StudentProfileView';
import '@/components/StudentProfileView.css';
import ProfileDropdown from '@/components/ProfileDropdown';
import '@/components/ProfileDropdown.css';
import HomeworkAnswering from '@/components/HomeworkAnswering';
import TestManagement from '@/components/TestManagement';
import StructuredTestCreator from '@/components/StructuredTestCreator';
import StudentAITest from '@/components/StudentAITest';
import StudentPerformanceDashboard from '@/components/StudentPerformanceDashboard';
import '@/components/StudentAITest.css';
import TestTaking from '@/components/TestTaking';
import TeacherUpload from '@/components/TeacherUpload';
import '@/components/TeacherUpload.css';
import StudentContentViewer from '@/components/StudentContentViewer';
import '@/components/StudentContentViewer.css';
import ParentDashboard from '@/components/ParentDashboard';
import '@/components/ParentDashboard.css';
import TeacherAnalytics from '@/components/TeacherAnalytics';
import '@/components/TeacherAnalytics.css';
import GalaxyBackground from '@/components/GalaxyBackground';
import AdminLogin from '@/components/AdminLogin';
import '@/components/AdminLogin.css';
import AdminDashboard from '@/components/AdminDashboard';
import '@/components/AdminDashboard.css';
import TeacherReviewMode from '@/components/TeacherReviewMode';
import '@/components/TeacherReviewMode.css';

const API = process.env.REACT_APP_BACKEND_URL 
  ? `${process.env.REACT_APP_BACKEND_URL}/api` 
  : '/api';

// CRITICAL: Enable credentials (cookies) for all axios requests
axios.defaults.withCredentials = true;

// Subject icon mapping - returns SVG icon component based on subject name
const getSubjectVectorIcon = (subjectName, color) => {
  const name = subjectName.toLowerCase();
  const iconColor = '#FFFFFF'; // Always white for dark mode
  
  // English - BookOpen
  if (name.includes('english')) {
    return (
      <svg viewBox="0 0 24 24" fill="none" stroke={iconColor} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="subject-card-vector-icon">
        <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"></path>
        <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"></path>
      </svg>
    );
  }
  
  // Hindi - Languages/PenTool
  if (name.includes('hindi')) {
    return (
      <svg viewBox="0 0 24 24" fill="none" stroke={iconColor} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="subject-card-vector-icon">
        <path d="M12 2v20"></path>
        <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"></path>
      </svg>
    );
  }
  
  // Mathematics - Calculator
  if (name.includes('math')) {
    return (
      <svg viewBox="0 0 24 24" fill="none" stroke={iconColor} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="subject-card-vector-icon">
        <rect x="4" y="2" width="16" height="20" rx="2"></rect>
        <line x1="8" y1="6" x2="16" y2="6"></line>
        <line x1="16" y1="14" x2="16" y2="18"></line>
        <line x1="8" y1="14" x2="8" y2="14.01"></line>
        <line x1="12" y1="14" x2="12" y2="14.01"></line>
        <line x1="8" y1="18" x2="8" y2="18.01"></line>
        <line x1="12" y1="18" x2="12" y2="18.01"></line>
      </svg>
    );
  }
  
  // Science - FlaskConical/Beaker
  if (name.includes('science') && !name.includes('social') && !name.includes('computer')) {
    return (
      <svg viewBox="0 0 24 24" fill="none" stroke={iconColor} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="subject-card-vector-icon">
        <path d="M10 2v7.527a2 2 0 0 1-.211.896L4.72 20.55a1 1 0 0 0 .9 1.45h12.76a1 1 0 0 0 .9-1.45l-5.069-10.127A2 2 0 0 1 14 9.527V2"></path>
        <path d="M8.5 2h7"></path>
        <path d="M7 16h10"></path>
      </svg>
    );
  }
  
  // EVS/Social Science - Globe
  if (name.includes('evs') || name.includes('environment') || name.includes('social')) {
    return (
      <svg viewBox="0 0 24 24" fill="none" stroke={iconColor} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="subject-card-vector-icon">
        <circle cx="12" cy="12" r="10"></circle>
        <line x1="2" y1="12" x2="22" y2="12"></line>
        <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path>
      </svg>
    );
  }
  
  // Computer Science - Monitor/Cpu
  if (name.includes('computer')) {
    return (
      <svg viewBox="0 0 24 24" fill="none" stroke={iconColor} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="subject-card-vector-icon">
        <rect x="2" y="3" width="20" height="14" rx="2"></rect>
        <line x1="8" y1="21" x2="16" y2="21"></line>
        <line x1="12" y1="17" x2="12" y2="21"></line>
      </svg>
    );
  }
  
  // Default - Book
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke={iconColor} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="subject-card-vector-icon">
      <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"></path>
      <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"></path>
    </svg>
  );
};

// Get color class for subject card
const getSubjectColorClass = (subjectName) => {
  const name = subjectName.toLowerCase();
  
  if (name.includes('english')) return 'color-english';
  if (name.includes('hindi')) return 'color-hindi';
  if (name.includes('math')) return 'color-math';
  if (name.includes('science') && !name.includes('social') && !name.includes('computer')) return 'color-science';
  if (name.includes('evs') || name.includes('environment') || name.includes('social')) return 'color-evs';
  if (name.includes('computer')) return 'color-computer';
  
  return 'color-english'; // Default
};

// Subject icon mapping - returns icon URL based on subject name
const getSubjectIcon = (subjectName) => {
  const name = subjectName.toLowerCase();
  
  // English - Book/Pencil
  if (name.includes('english')) {
    return 'https://cdn3d.iconscout.com/3d/premium/thumb/book-3d-icon-download-in-png-blend-fbx-gltf-file-formats--education-reading-library-school-pack-icons-5187834.png';
  }
  
  // Hindi - Book
  if (name.includes('hindi')) {
    return 'https://cdn3d.iconscout.com/3d/premium/thumb/books-3d-icon-download-in-png-blend-fbx-gltf-file-formats--book-stack-education-library-study-learning-pack-school-icons-6887983.png';
  }
  
  // Mathematics - Calculator
  if (name.includes('math')) {
    return 'https://cdn3d.iconscout.com/3d/premium/thumb/calculator-3d-icon-download-in-png-blend-fbx-gltf-file-formats--calculation-accounting-business-pack-icons-5187806.png';
  }
  
  // Science - Flask
  if (name.includes('science') && !name.includes('social')) {
    return 'https://cdn3d.iconscout.com/3d/premium/thumb/flask-3d-icon-download-in-png-blend-fbx-gltf-file-formats--science-laboratory-chemistry-experiment-research-pack-icons-5187825.png';
  }
  
  // Social Science / EVS - Globe
  if (name.includes('social') || name.includes('evs') || name.includes('environment')) {
    return 'https://cdn3d.iconscout.com/3d/premium/thumb/globe-3d-icon-download-in-png-blend-fbx-gltf-file-formats--earth-world-geography-planet-pack-education-icons-5187828.png';
  }
  
  // Computer Science - Computer
  if (name.includes('computer')) {
    return 'https://cdn3d.iconscout.com/3d/premium/thumb/computer-3d-icon-download-in-png-blend-fbx-gltf-file-formats--desktop-pc-technology-device-pack-icons-5187813.png';
  }
  
  // Default - General education icon
  return 'https://cdn3d.iconscout.com/3d/premium/thumb/graduation-cap-3d-icon-download-in-png-blend-fbx-gltf-file-formats--education-degree-achievement-school-pack-icons-5187830.png';
};

// Utility function to clean and format AI content
const cleanAIContent = (text) => {
  if (!text) return '';
  
  // Convert string to string if not already
  let cleaned = String(text);
  
  // Remove excessive asterisks used for bold (keep single *)
  cleaned = cleaned.replace(/\*\*\*/g, '');
  cleaned = cleaned.replace(/\*\*/g, '');
  
  // Remove markdown headers that don't render well
  cleaned = cleaned.replace(/^#{1,6}\s*/gm, '');
  
  // Clean up arrow characters
  cleaned = cleaned.replace(/→/g, '→');
  cleaned = cleaned.replace(/->/g, '→');
  cleaned = cleaned.replace(/=>/g, '⇒');
  
  // Clean up bullet points
  cleaned = cleaned.replace(/^[-•]\s*/gm, '• ');
  
  // Remove excessive newlines
  cleaned = cleaned.replace(/\n{3,}/g, '\n\n');
  
  // Trim whitespace
  cleaned = cleaned.trim();
  
  return cleaned;
};

// Component to render formatted content with math support
const FormattedContent = ({ content, className = '' }) => {
  if (!content) return null;
  
  const cleaned = cleanAIContent(content);
  
  return (
    <div className={`formatted-content ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkMath]}
        rehypePlugins={[rehypeKatex]}
        components={{
          // Custom paragraph to avoid nested p tags
          p: ({ children }) => <p className="content-paragraph">{children}</p>,
          // Custom list items
          li: ({ children }) => <li className="content-list-item">{children}</li>,
          // Custom code blocks
          code: ({ inline, children }) => 
            inline ? <code className="inline-code">{children}</code> : <pre className="code-block"><code>{children}</code></pre>
        }}
      >
        {cleaned}
      </ReactMarkdown>
    </div>
  );
};

// Translation Helper Functions
const translateText = async (text, language, context = 'ui') => {
  if (!text || language === 'english') return text;
  
  console.log(`[Translation] Translating "${text}" to ${language}`);
  
  try {
    const formData = new FormData();
    formData.append('text', text);
    formData.append('to_language', 'gujarati');
    formData.append('context', context);
    
    const response = await axios.post(`${API}/translate`, formData, { 
      withCredentials: true 
    });
    
    console.log(`[Translation] Response:`, response.data);
    
    return response.data.success ? response.data.translated_text : text;
  } catch (error) {
    console.error('[Translation] Failed:', error);
    return text;
  }
};

const translateBatch = async (texts, language, context = 'ui') => {
  if (!texts || texts.length === 0 || language === 'english') {
    return texts.reduce((acc, text) => ({ ...acc, [text]: text }), {});
  }
  
  console.log(`[Translation] Batch translating ${texts.length} texts to ${language}`);
  
  try {
    const formData = new FormData();
    formData.append('texts', JSON.stringify(texts));
    formData.append('to_language', 'gujarati');
    formData.append('context', context);
    
    const response = await axios.post(`${API}/translate/batch`, formData, {
      withCredentials: true
    });
    
    console.log(`[Translation] Batch response:`, response.data);
    
    return response.data.success ? response.data.translations : {};
  } catch (error) {
    console.error('[Translation] Batch translation failed:', error);
    return {};
  }
};

const translateContent = async (content, language) => {
  if (!content || language === 'english') return content;
  
  console.log('[Translation] Translating AI content to Gujarati...');
  console.log('[Translation] Content structure:', Object.keys(content));
  
  try {
    const formData = new FormData();
    formData.append('content', JSON.stringify(content));
    formData.append('to_language', 'gujarati');
    
    console.log('[Translation] Sending content translation request...');
    
    const response = await axios.post(`${API}/translate/content`, formData, {
      withCredentials: true
    });
    
    console.log('[Translation] Content translation response:', response.data);
    
    if (response.data.success && response.data.translated_content) {
      console.log('[Translation] ✅ Content successfully translated!');
      return response.data.translated_content;
    } else {
      console.error('[Translation] ❌ Translation failed:', response.data);
      return content;
    }
  } catch (error) {
    console.error('[Translation] ❌ Content translation error:', error);
    return content;
  }
};

// Simple list renderer to avoid deep recursion in babel plugin
const SimpleList = ({ items, renderItem }) => {
  if (!items || items.length === 0) return null;
  return items.map((item, i) => <React.Fragment key={i}>{renderItem(item, i)}</React.Fragment>);
};

// Tool Content Display Component
function ToolContentDisplay({ learningTool, toolContent, selectedSubject, selectedChapter, contentSource, studentClassification = 'average', language, translatedUI }) {
  const [fcIndex, setFcIndex] = useState(0);
  const [fcFlipped, setFcFlipped] = useState(false);
  const [fcRatings, setFcRatings] = useState({});
  const [fcHint, setFcHint] = useState(false);
  const [qzSelected, setQzSelected] = useState(null);
  const [qzQuestion, setQzQuestion] = useState(0);
  const [qzAnswer, setQzAnswer] = useState(null);
  const [qzShowResult, setQzShowResult] = useState(false);
  const [qzScore, setQzScore] = useState(0);
  const [qzAnswers, setQzAnswers] = useState({});
  const [qzExplanation, setQzExplanation] = useState('');
  const [qzLoading, setQzLoading] = useState(false);
  const [qzCompleted, setQzCompleted] = useState(false);
  const [impExpanded, setImpExpanded] = useState('must_know');
  const [dMessages, setDMessages] = useState(() => {
    // Initialize with welcome message for doubt tool
    return [];
  });
  const [dInput, setDInput] = useState('');
  const [dLoading, setDLoading] = useState(false);
  const dEndRef = useRef(null);
  
  useEffect(() => {
    if (learningTool === 'flashcards' && selectedChapter?.id) {
      axios.get(`${API}/student/flashcard-ratings/${selectedChapter.id}`, { withCredentials: true })
        .then(res => setFcRatings(res.data.ratings || {})).catch(() => {});
    }
  }, [learningTool, selectedChapter?.id]);
  
  useEffect(() => { dEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [dMessages]);

  // PHASE 4.1: Handle "Content Not Available" state - Students NEVER trigger generation
  if (toolContent?.notAvailable) {
    return (
      <div className="content-not-available-display" data-testid="content-not-available">
        <div className="not-available-icon">📚</div>
        <h3>Content Not Available Yet</h3>
        <p>{toolContent.message || 'Please check back later.'}</p>
        <p className="hint-text">Your teacher needs to upload and generate AI content for this chapter.</p>
      </div>
    );
  }

  // Revision Notes - Updated with new structure and formatted content
  if (learningTool === 'revision_notes' && toolContent) {
    return (
      <div className="revision-notes-container" data-testid="revision-notes">
        <div className="revision-header"><div className="revision-icon">📚</div><h2>Revision Notes</h2><p className="chapter-badge">{selectedChapter?.name}</p></div>
        
        {/* Chapter Summary */}
        {(toolContent.summary || toolContent.chapter_summary) && (
          <div className="summary-card">
            <div className="summary-icon">💡</div>
            <FormattedContent content={toolContent.summary || toolContent.chapter_summary} />
          </div>
        )}
        
        {/* Key Concepts - New Structure */}
        {toolContent.key_concepts && (
          <div className="notes-section">
            <h3>🎯 Key Concepts</h3>
            <div className="concepts-grid">
              <SimpleList items={toolContent.key_concepts} renderItem={(c) => (
                <div className="concept-card">
                  <h4>{cleanAIContent(c.title)}</h4>
                  <FormattedContent content={c.explanation || c.description} />
                  {c.why_important && <p className="why-important"><strong>Why it matters:</strong> {cleanAIContent(c.why_important)}</p>}
                  {c.exam_tip && <p className="exam-tip">📝 <strong>Exam tip:</strong> {cleanAIContent(c.exam_tip)}</p>}
                  {c.example && <p className="example">💡 <strong>Example:</strong> {cleanAIContent(c.example)}</p>}
                </div>
              )} />
            </div>
          </div>
        )}
        
        {/* Exam Important Points - New */}
        {toolContent.exam_important_points && (
          <div className="notes-section exam-points-section">
            <h3>🎯 Exam Important Points</h3>
            <div className="exam-points-list">
              <SimpleList items={toolContent.exam_important_points} renderItem={(p) => (
                <div className="exam-point-item">
                  <span className={`point-type ${p.type || 'fact'}`}>{p.type || 'Fact'}</span>
                  <FormattedContent content={p.point} />
                  {p.memory_trick && <p className="memory-trick">🧠 <strong>Remember:</strong> {cleanAIContent(p.memory_trick)}</p>}
                </div>
              )} />
            </div>
          </div>
        )}
        
        {/* Definitions */}
        {(toolContent.definitions || toolContent.definitions_to_memorize) && (
          <div className="notes-section">
            <h3>📖 Definitions to Memorize</h3>
            <div className="definitions-list">
              <SimpleList items={toolContent.definitions || toolContent.definitions_to_memorize} renderItem={(d) => (
                <div className="definition-item">
                  <span className="term">{cleanAIContent(d.term)}:</span>
                  <span className="meaning"><FormattedContent content={d.meaning || d.definition} /></span>
                  {d.example && <span className="def-example">Example: {cleanAIContent(d.example)}</span>}
                </div>
              )} />
            </div>
          </div>
        )}
        
        {/* Formulas and Rules */}
        {(toolContent.formulas || toolContent.formulas_and_rules) && (
          <div className="notes-section formulas-section">
            <h3>📐 Formulas & Rules</h3>
            <div className="formulas-list">
              <SimpleList items={toolContent.formulas || toolContent.formulas_and_rules} renderItem={(f) => (
                <div className="formula-item">
                  <div className="formula-box"><FormattedContent content={f.formula} /></div>
                  <p className="formula-usage"><strong>When to use:</strong> {cleanAIContent(f.when_to_use || f.usage)}</p>
                  {f.common_mistakes && <p className="formula-mistakes">⚠️ <strong>Common mistake:</strong> {cleanAIContent(f.common_mistakes)}</p>}
                </div>
              )} />
            </div>
          </div>
        )}
        
        {/* Important Facts (old structure) */}
        {toolContent.important_facts && (
          <div className="notes-section">
            <h3>⭐ Important Facts</h3>
            <div className="facts-list">
              <SimpleList items={toolContent.important_facts} renderItem={(f) => (
                <div className="fact-item">
                  <span className="fact-bullet">•</span>
                  <FormattedContent content={f.fact || f} />
                  {f.remember_tip && <span className="remember-tip">💡 {cleanAIContent(f.remember_tip)}</span>}
                </div>
              )} />
            </div>
          </div>
        )}
        
        {/* Quick Revision Points */}
        {(toolContent.quick_tips || toolContent.quick_revision_points) && (
          <div className="notes-section tips-section">
            <h3>🚀 Quick Revision Points</h3>
            <div className="tips-container">
              <SimpleList items={toolContent.quick_tips || toolContent.quick_revision_points} renderItem={(t, i) => (
                <div className="tip-badge">
                  <span className="tip-number">{i+1}</span>
                  <FormattedContent content={typeof t === 'string' ? t : t.point || t.tip} />
                </div>
              )} />
            </div>
          </div>
        )}
        
        {/* Exam Prediction */}
        {toolContent.exam_prediction && (
          <div className="notes-section exam-prediction">
            <h3>🔮 What to Expect in Exam</h3>
            <FormattedContent content={toolContent.exam_prediction} />
          </div>
        )}
      </div>
    );
  }

  // Flashcards - Updated with formatted content
  if (learningTool === 'flashcards' && toolContent && toolContent.length > 0) {
    const card = toolContent[fcIndex];
    const cardId = card?.id || fcIndex + 1;
    const saveRating = (r) => {
      const fd = new FormData(); fd.append('chapter_id', selectedChapter.id); fd.append('flashcard_id', cardId); fd.append('rating', r);
      axios.post(`${API}/student/flashcard-rating`, fd, { withCredentials: true }).catch(() => {});
      setFcRatings(p => ({ ...p, [cardId]: r })); setFcFlipped(false); setFcIndex((fcIndex + 1) % toolContent.length);
    };
    return (
      <div className="flashcards-container" data-testid="flashcards">
        <div className="flashcards-header"><h2>🃏 Flashcards</h2><p className="chapter-badge">{selectedChapter?.name}</p></div>
        <div className="flashcards-stats">
          <div className="stat-item easy"><span className="stat-emoji">😊</span><span className="stat-count">{Object.values(fcRatings).filter(r => r === 'easy').length}</span></div>
          <div className="stat-item medium"><span className="stat-emoji">🤔</span><span className="stat-count">{Object.values(fcRatings).filter(r => r === 'medium').length}</span></div>
          <div className="stat-item hard"><span className="stat-emoji">😅</span><span className="stat-count">{Object.values(fcRatings).filter(r => r === 'hard').length}</span></div>
        </div>
        <div className="progress-container"><div className="progress-bar"><div className="progress-fill" style={{ width: `${((fcIndex+1)/toolContent.length)*100}%` }}/></div><span className="progress-text">{fcIndex+1}/{toolContent.length}</span></div>
        <div className={`flashcard ${fcFlipped ? 'flipped' : ''}`} onClick={() => setFcFlipped(!fcFlipped)} data-testid="flashcard">
          <div className="flashcard-inner">
            <div className="flashcard-front">
              <div className="card-category">{cleanAIContent(card?.category) || 'Question'}</div>
              {card?.exam_likelihood && <span className={`exam-badge ${card.exam_likelihood}`}>{card.exam_likelihood} priority</span>}
              <div className="card-content"><FormattedContent content={card?.front} /></div>
              <div className="flip-hint">Click to reveal</div>
            </div>
            <div className="flashcard-back">
              <div className="card-label">Answer</div>
              <div className="card-content"><FormattedContent content={card?.back} /></div>
              {card?.hint && <div className="card-hint">💡 Hint: {cleanAIContent(card.hint)}</div>}
            </div>
          </div>
        </div>
        {fcFlipped && <div className="rating-section"><p className="rating-prompt">How well did you know?</p><div className="rating-buttons">
          <button className={`rating-btn easy ${fcRatings[cardId] === 'easy' ? 'selected' : ''}`} onClick={() => saveRating('easy')}>😊 Easy</button>
          <button className={`rating-btn medium ${fcRatings[cardId] === 'medium' ? 'selected' : ''}`} onClick={() => saveRating('medium')}>🤔 Medium</button>
          <button className={`rating-btn hard ${fcRatings[cardId] === 'hard' ? 'selected' : ''}`} onClick={() => saveRating('hard')}>😅 Hard</button>
        </div></div>}
        <div className="flashcard-nav"><button className="nav-btn" onClick={() => { setFcFlipped(false); setFcIndex(fcIndex === 0 ? toolContent.length-1 : fcIndex-1); }}>← Prev</button><button className="nav-btn primary" onClick={() => { setFcFlipped(false); setFcIndex((fcIndex+1) % toolContent.length); }}>Next →</button></div>
      </div>
    );
  }

  // Quiz
  if (learningTool === 'quiz' && toolContent?.quizzes) {
    const startQuiz = (q) => { setQzSelected(q); setQzQuestion(0); setQzAnswer(null); setQzShowResult(false); setQzScore(0); setQzAnswers({}); setQzExplanation(''); setQzCompleted(false); };
    const submit = async () => { 
      if (!qzAnswer) return; 
      const q = qzSelected.questions[qzQuestion]; 
      const correctIdx = typeof q.correct_answer === 'number' ? q.correct_answer : parseInt(q.correct_answer);
      const isCorrect = qzAnswer === q.options[correctIdx];
      setQzShowResult(true); 
      setQzAnswers(p => ({ ...p, [qzQuestion]: { correct: isCorrect } })); 
      if (isCorrect) { 
        setQzScore(p => p + 1); 
        setQzExplanation(''); // No explanation needed for correct answer
      } else { 
        // Use the explanation from the quiz JSON - NO LLM call needed
        setQzExplanation(q.explanation || 'Review this topic in your textbook.');
      } 
    };
    const next = () => { if (qzQuestion < qzSelected.questions.length - 1) { setQzQuestion(p => p + 1); setQzAnswer(null); setQzShowResult(false); setQzExplanation(''); } else { setQzCompleted(true); } };
    
    // Submit practice progress to backend (idempotent - marks completion once)
    const submitPracticeProgress = async () => {
      try {
        const quizIndex = toolContent.quizzes.findIndex(q => q.title === qzSelected.title);
        const practiceTestNumber = quizIndex >= 0 ? quizIndex + 1 : 1;
        const pct = qzSelected.questions.length > 0 ? Math.round((qzScore / qzSelected.questions.length) * 100) : 0;
        
        await axios.post(`${API}/student/practice-progress`, {
          subject: selectedSubject.name,
          chapter: selectedChapter.name,
          practice_test_number: practiceTestNumber,
          score: pct
        }, { withCredentials: true });
        
        alert('Progress saved! Great job completing this quiz.');
      } catch (error) {
        console.error('Error saving progress:', error);
      }
    };
    
    if (!qzSelected) {
      // Filter quizzes based on student classification
      let filteredQuizzes = toolContent.quizzes || [];
      
      // Show only Easy, Medium, Hard for average/weak students
      // Show all 5 (including Advanced 1 & 2) for strong students
      if (studentClassification !== 'strong') {
        filteredQuizzes = filteredQuizzes.filter(q => 
          q.difficulty !== 'Advanced'
        );
      }
      
      return (
        <div className="quiz-container" data-testid="practice-quiz">
          <div className="quiz-header"><h2>Practice Quizzes</h2><p className="chapter-badge">{selectedChapter?.name}</p></div>
          <div className="quiz-cards"><SimpleList items={filteredQuizzes} renderItem={(q) => <div className={`quiz-card difficulty-${q.difficulty.toLowerCase()}`} onClick={() => startQuiz(q)}><div className="quiz-card-icon">{q.difficulty === 'Easy' ? '🌟' : q.difficulty === 'Medium' ? '⭐' : q.difficulty === 'Hard' ? '🏆' : '💎'}</div><h3>{q.title}</h3><span className={`difficulty-badge ${q.difficulty.toLowerCase()}`}>{q.difficulty}</span><button className="start-quiz-btn">Start</button></div>} /></div>
        </div>
      );
    }
    if (qzCompleted) {
      const pct = Math.round((qzScore / qzSelected.questions.length) * 100);
      return (
        <div className="quiz-container">
          <div className="quiz-results">
            <div className="results-header" style={{ backgroundColor: pct >= 70 ? '#48BB78' : '#ED8936' }}>
              <h2>{pct >= 70 ? 'Great Job!' : 'Good Try!'}</h2>
            </div>
            <div className="results-score">
              <div className="score-circle">
                <span className="score-number">{qzScore}</span>
                <span className="score-total">/{qzSelected.questions.length}</span>
              </div>
              <p className="score-percentage">{pct}%</p>
            </div>
            <div className="results-actions">
              <button className="action-btn submit-progress" onClick={submitPracticeProgress} data-testid="submit-quiz-progress">
                Save Progress
              </button>
              <button className="action-btn retry" onClick={() => startQuiz(qzSelected)}>Retry</button>
              <button className="action-btn back" onClick={() => setQzSelected(null)}>Back</button>
            </div>
          </div>
        </div>
      );
    }
    const q = qzSelected.questions[qzQuestion];
    return (
      <div className="quiz-container"><div className="quiz-progress-header"><button className="quit-btn" onClick={() => setQzSelected(null)}>✕</button><span className="score-display">Score: {qzScore}</span></div>
        <div className="quiz-progress"><div className="progress-bar"><div className="progress-fill" style={{ width: `${((qzQuestion+1)/qzSelected.questions.length)*100}%` }}/></div></div>
        <div className="question-card"><div className="question-number">Q{qzQuestion+1}</div><h3 className="question-text"><FormattedContent content={q.question} /></h3>
          <div className="options-list"><SimpleList items={q.options} renderItem={(o, i) => {
            const isCorrect = o === q.options[q.correct_answer] || (typeof q.correct_answer === 'number' ? i === q.correct_answer : o === q.correct_answer);
            const isSelected = o === qzAnswer;
            let optionClass = 'option-btn';
            if (qzShowResult) {
              if (isCorrect) optionClass += ' correct';
              else if (isSelected) optionClass += ' incorrect';
            } else if (isSelected) {
              optionClass += ' selected';
            }
            return <button className={optionClass} onClick={() => !qzShowResult && setQzAnswer(o)} disabled={qzShowResult} style={qzShowResult ? (isCorrect ? {borderColor: '#22c55e', background: '#dcfce7', borderWidth: '3px'} : isSelected ? {borderColor: '#ef4444', background: '#fee2e2', borderWidth: '3px'} : {}) : {}}><span className="option-letter" style={qzShowResult ? (isCorrect ? {background: '#22c55e', color: 'white'} : isSelected ? {background: '#ef4444', color: 'white'} : {}) : {}}>{String.fromCharCode(65+i)}</span><FormattedContent content={o} />{qzShowResult && isCorrect && <span style={{marginLeft: 'auto', color: '#22c55e', fontWeight: 'bold'}}>✓</span>}{qzShowResult && isSelected && !isCorrect && <span style={{marginLeft: 'auto', color: '#ef4444', fontWeight: 'bold'}}>✗</span>}</button>
          }} /></div>
          {qzShowResult && qzAnswers[qzQuestion]?.correct && <div style={{marginTop: '16px', padding: '16px', background: '#dcfce7', borderRadius: '12px', border: '2px solid #22c55e', textAlign: 'center'}}><span style={{fontSize: '24px'}}>🎉</span> <span style={{fontWeight: 'bold', color: '#166534', fontSize: '18px'}}>Correct! Well done!</span></div>}
          {qzShowResult && !qzAnswers[qzQuestion]?.correct && qzExplanation && <div className="explanation-box" style={{marginTop: '16px', padding: '16px', background: '#fef9c3', borderRadius: '12px', border: '2px solid #eab308'}}><span className="explanation-icon" style={{fontSize: '20px'}}>💡</span><div className="explanation-text" style={{marginTop: '8px', color: '#713f12', fontSize: '14px', lineHeight: '1.5'}}>{qzExplanation}</div></div>}
        </div>
        <div className="quiz-actions">{!qzShowResult ? <button className="submit-btn" onClick={submit} disabled={!qzAnswer}>Check</button> : <button className="next-btn" onClick={next}>{qzQuestion < qzSelected.questions.length-1 ? 'Next' : 'Results'}</button>}</div>
      </div>
    );
  }

  // Doubt (Ask a Question)
  if (learningTool === 'doubt' && toolContent) {
    // Ensure welcome message is present
    const messagesWithWelcome = dMessages.length === 0 && selectedChapter?.name ? 
      [{ role: 'assistant', content: `Hi! 👋 Ask me about ${selectedChapter.name}!`, suggestions: ["Explain the concept", "What's important?"] }] : 
      dMessages;

    const sendMsg = async (msg) => {
      if (!msg.trim() || dLoading) return; 
      setDMessages(p => [...p, { role: 'user', content: msg }]); 
      setDInput(''); 
      setDLoading(true);
      try {
        const res = await axios.post(`${API}/student/generate-content`, { 
          subject_id: selectedSubject.id, 
          chapter_id: selectedChapter.id, 
          feature_type: 'doubt', 
          language: 'english', 
          content_source: contentSource, 
          additional_params: { 
            question: msg, 
            conversation_history: dMessages.map(m => ({ role: m.role, content: m.content })) 
          } 
        }, { withCredentials: true });
        
        console.log('Doubt API Response:', res.data);
        
        if (res.data.success && res.data.content) { 
          const ai = res.data.content; 
          setDMessages(p => [...p, { 
            role: 'assistant', 
            content: ai.answer || ai, 
            suggestions: ai.follow_up_suggestions || [] 
          }]); 
        } else { 
          console.error('Doubt API failed:', res.data);
          const errorMsg = res.data.error || "Sorry, I couldn't process your question. Please try again!";
          setDMessages(p => [...p, { 
            role: 'assistant', 
            content: errorMsg, 
            suggestions: [] 
          }]); 
        }
      } catch (err) { 
        console.error('Doubt API error:', err);
        const errorMsg = err.response?.data?.detail || "Connection error! Please check your internet.";
        setDMessages(p => [...p, { 
          role: 'assistant', 
          content: errorMsg, 
          suggestions: [] 
        }]); 
      }
      setDLoading(false);
    };
    return (
      <div className="doubt-container" data-testid="ask-doubt">
        <div className="doubt-header"><div className="doubt-icon">💬</div><h2>Ask a Doubt</h2><p className="chapter-badge">{selectedChapter?.name}</p></div>
        <div className="chat-container">
          <div className="messages-area">
            <SimpleList items={messagesWithWelcome} renderItem={(m) => <div className={`message ${m.role}`}>{m.role === 'assistant' && <div className="assistant-avatar">🤖</div>}<div className="message-bubble"><FormattedContent content={m.content} />{m.suggestions?.length > 0 && <div className="suggestion-chips"><SimpleList items={m.suggestions} renderItem={(s) => <button className="suggestion-chip" onClick={() => sendMsg(s)}>{s}</button>} /></div>}</div>{m.role === 'user' && <div className="user-avatar">👤</div>}</div>} />
            {dLoading && <div className="message assistant"><div className="assistant-avatar">🤖</div><div className="message-bubble typing"><div className="typing-indicator"><span></span><span></span><span></span></div></div></div>}
            <div ref={dEndRef} />
          </div>
          <form className="chat-input-area" onSubmit={(e) => { e.preventDefault(); sendMsg(dInput); }}><input type="text" className="chat-input" placeholder="Ask..." value={dInput} onChange={(e) => setDInput(e.target.value)} disabled={dLoading} /><button type="submit" className="send-btn" disabled={!dInput.trim() || dLoading}>➤</button></form>
          <div className="guardrail-notice">📚 I only answer about {selectedChapter?.name}</div>
        </div>
      </div>
    );
  }

  return <div>Select a tool</div>;
}

function App() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [view, setView] = useState('student');
  const [showProfileForm, setShowProfileForm] = useState(false);
  const [showParentDashboard, setShowParentDashboard] = useState(false);
  const [showTeacherAnalytics, setShowTeacherAnalytics] = useState(false);
  const [showAdminLogin, setShowAdminLogin] = useState(false);
  const [language, setLanguage] = useState(() => {
    // Get language from localStorage or default to english
    return localStorage.getItem('preferred_language') || 'english';
  });

  // Click sound effect
  useEffect(() => {
    const clickSound = new Audio('/click-sound.mp3');
    clickSound.volume = 0.3; // Set volume to 30%
    
    const playClickSound = (e) => {
      // Only play for actual clicks, not for keyboard events
      if (e.isTrusted) {
        clickSound.currentTime = 0; // Reset to start for rapid clicks
        clickSound.play().catch(err => {
          // Ignore errors (e.g., if user hasn't interacted with page yet)
          console.debug('Click sound play prevented:', err);
        });
      }
    };
    
    // Add click listener to entire document
    document.addEventListener('click', playClickSound);
    
    // Cleanup
    return () => {
      document.removeEventListener('click', playClickSound);
    };
  }, []);

  useEffect(() => {
    checkAuth();
  }, []);

  const checkAuth = async () => {
    try {
      const response = await axios.get(`${API}/auth/me`, { withCredentials: true });
      setUser(response.data);
      
      // Store token in localStorage as fallback (if provided)
      if (response.data.token) {
        localStorage.setItem('auth_token', response.data.token);
      }
      
      // Handle admin, teacher, and student views
      if (response.data.role === 'admin') {
        setView('admin');
      } else if (response.data.role === 'teacher') {
        setView('teacher');
      } else {
        setView('student');
      }
      
      // Students no longer auto-show registration form - admin will set up profiles
    } catch (error) {
      console.log('Not authenticated');
      localStorage.removeItem('auth_token'); // Clear token on auth failure
    } finally {
      setLoading(false);
    }
  };

  // Add axios interceptor to include token in headers as fallback
  useEffect(() => {
    const requestInterceptor = axios.interceptors.request.use(
      (config) => {
        // Always try cookies first (withCredentials)
        // But also add Bearer token as fallback for CORS/HTTP issues
        // IMPORTANT: Get token from localStorage at request time (not at mount time)
        const token = localStorage.getItem('auth_token');
        if (token) {
          // Always set the Authorization header with latest token
          config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
      },
      (error) => {
        return Promise.reject(error);
      }
    );

    return () => {
      axios.interceptors.request.eject(requestInterceptor);
    };
  }, []); // Empty dependency array - interceptor stays consistent

  const handleProfileComplete = (profile) => {
    setUser(prev => ({
      ...prev,
      profile_completed: true,
      student_profile: profile
    }));
    setShowProfileForm(false);
  };

  const handleLogout = async () => {
    // CRITICAL: Clear localStorage token FIRST to prevent interceptor sending stale token
    localStorage.removeItem('auth_token');

    try {
      await axios.post(`${API}/auth/logout`, {}, { withCredentials: true });
    } catch (err) {
      console.error('Logout error:', err);
    }

    // Clear all state
    setUser(null);
    setShowProfileForm(false);
    setShowAdminLogin(false);
    setView('student');
    setShowParentDashboard(false);
    setShowTeacherAnalytics(false);
  };

  const handleLanguageToggle = () => {
    const newLanguage = language === 'english' ? 'gujarati' : 'english';
    setLanguage(newLanguage);
    localStorage.setItem('preferred_language', newLanguage);
  };

  const handleParentDashboard = () => {
    setShowParentDashboard(true);
  };
  
  const handleTeacherAnalytics = () => {
    setShowTeacherAnalytics(true);
  };

  const handleAdminLoginSuccess = (adminUser) => {
    setUser({ ...adminUser, role: 'admin' });
    setView('admin');
    setShowAdminLogin(false);
  };

  if (loading) {
    return (
      <div className="loading">
        <GalaxyBackground />
        Loading...
      </div>
    );
  }

  // Show Admin Login page
  if (showAdminLogin && !user) {
    return (
      <AdminLogin 
        onLoginSuccess={handleAdminLoginSuccess}
      />
    );
  }

  // Show Admin Dashboard for admin users
  if (user && user.role === 'admin') {
    return (
      <AdminDashboard onLogout={handleLogout} />
    );
  }

  if (!user) {
    return (
      <>
        <GalaxyBackground />
        <AuthScreen onSuccess={() => checkAuth()} onAdminLogin={() => setShowAdminLogin(true)} />
      </>
    );
  }

  // Show read-only profile view for students when requested
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
    // Only students can view/edit profile
    if (user.role === 'student') {
      setShowProfileForm(true);
    }
    // For teachers, this could open a settings modal in the future
  };

  // Show Teacher Analytics (full-page)
  if (showTeacherAnalytics && user.role === 'teacher') {
    return (
      <div className="app-container">
        <GalaxyBackground />
        <TeacherAnalytics onClose={() => setShowTeacherAnalytics(false)} />
      </div>
    );
  }

  // Show Parent Dashboard (full-page)
  if (showParentDashboard && user.role === 'student') {
    return (
      <div className="app-container">
        <GalaxyBackground />
        <Header 
          user={user} 
          view={view} 
          setView={setView} 
          onLogout={handleLogout}
          language={language}
          onLanguageToggle={handleLanguageToggle}
          studentProfile={user?.student_profile}
          onViewProfile={handleViewProfile}
          onParentDashboard={handleParentDashboard}
          onAnalytics={handleTeacherAnalytics}
        />
        <ParentDashboard 
          isFullPage={true}
          onClose={() => setShowParentDashboard(false)}
        />
      </div>
    );
  }

  return (
    <div className="app-container">
      <GalaxyBackground />
      <Header 
        user={user} 
        view={view} 
        setView={setView} 
        onLogout={handleLogout}
        language={language}
        onLanguageToggle={handleLanguageToggle}
        studentProfile={user?.student_profile}
        onViewProfile={handleViewProfile}
        onParentDashboard={handleParentDashboard}
        onAnalytics={handleTeacherAnalytics}
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

// Helper function to extract error message from FastAPI responses
const extractErrorMessage = (err, fallbackMessage = 'An error occurred') => {
  const errorData = err?.response?.data?.detail;
  if (Array.isArray(errorData)) {
    return errorData.map(e => e.msg || e.message || JSON.stringify(e)).join(', ');
  } else if (typeof errorData === 'object' && errorData !== null) {
    return errorData.msg || errorData.message || JSON.stringify(errorData);
  } else if (typeof errorData === 'string') {
    return errorData;
  }
  return err?.message || fallbackMessage;
};

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
        {/* Language Toggle Button */}
        <button 
          onClick={onLanguageToggle} 
          className="language-toggle-btn" 
          data-testid="language-toggle"
          title={language === 'english' ? 'Switch to Gujarati' : 'Switch to English'}
        >
          {language === 'english' ? '🇮🇳 ગુજરાતી' : '🇬🇧 English'}
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
  
  // Test states
  const [testList, setTestList] = useState([]);
  const [selectedTest, setSelectedTest] = useState(null);
  
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
      
      const [chaptersRes, pyqsRes, homeworkRes, testsRes, aiTestsRes] = await Promise.allSettled([
        axios.get(`${API}/subjects/${subject.id}/chapters`),
        axios.get(`${API}/subjects/${subject.id}/pyqs?standard=${standard}`),
        axios.get(`${API}/homework?standard=${standard}&subject_id=${subject.id}`, { withCredentials: true }),
        axios.get(`${API}/tests/subject/${subject.id}/standard/${standard}`, { withCredentials: true }),
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
      
      // Process old tests
      const testsData = testsRes.status === 'fulfilled' ? testsRes.value.data : { tests: [] };
      setTestList(testsData.tests || []);
      
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
  if (!selectedChapter && !selectedPYQ && !selectedHomework && !selectedTest && !selectedAITest) {
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
          {testList.length > 0 ? (
            <div className="tests-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '15px' }}>
              {testList.map((test) => (
                <div 
                  key={test.id} 
                  className="test-card"
                  data-testid={`test-${test.id}`}
                  style={{ 
                    borderRadius: '12px',
                    padding: '20px',
                    color: 'white',
                    boxShadow: '0 4px 15px rgba(245, 87, 108, 0.3)',
                    border: '2px solid rgba(255,255,255,0.3)'
                  }}
                >
                  <h4 style={{ margin: '0 0 10px 0', fontSize: '16px' }}>🧪 {test.title}</h4>
                  <p style={{ margin: '5px 0', fontSize: '13px', opacity: '0.9' }}>
                    ⏱️ Duration: {test.duration_minutes} minutes
                  </p>
                  <p style={{ margin: '5px 0', fontSize: '13px', opacity: '0.9' }}>
                    📅 Deadline: {new Date(test.submission_deadline).toLocaleDateString()}
                  </p>
                  {test.submitted && (
                    <p style={{ margin: '10px 0', fontSize: '13px', background: 'rgba(255,255,255,0.2)', padding: '5px 10px', borderRadius: '5px' }}>
                      ✅ Submitted
                    </p>
                  )}
                  <div style={{ marginTop: '15px' }}>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        console.log('Attempt Test clicked for:', test);
                        setSelectedTest(test);
                        setFrequentPYQsData(null);  // Clear frequent PYQs data
                        setShowFrequentPYQs(false);
                      }}
                      disabled={test.submitted}
                      data-testid={`attempt-test-${test.id}`}
                      style={{
                        background: test.submitted ? '#ccc' : '#10b981',
                        color: 'white',
                        padding: '10px 20px',
                        borderRadius: '20px',
                        border: 'none',
                        cursor: test.submitted ? 'not-allowed' : 'pointer',
                        fontSize: '14px',
                        fontWeight: 'bold',
                        width: '100%'
                      }}
                    >
                      {test.submitted ? '✅ Completed' : test.started ? '⏱️ Continue Test' : '🚀 Attempt Test'}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          ) : aiTestList.length === 0 && (
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
  
  console.log('StudentView render - selectedTest:', selectedTest ? 'YES' : 'NO');
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

  // Test Taking View
  if (selectedTest) {
    console.log('Rendering TestTaking component for test:', selectedTest);
    return (
      <div className="student-view">
        {isTeacherPreview && (
          <div className="teacher-preview-banner" data-testid="teacher-preview-banner">
            <span className="preview-icon">👁️</span>
            <span className="preview-text">Teacher Preview Mode - View Only (No Submissions Allowed)</span>
          </div>
        )}
        <TestTaking
          test={selectedTest}
          isTeacherPreview={isTeacherPreview}
          onClose={() => {
            setSelectedTest(null);
            // Reload tests to update status
            if (selectedSubject && standard) {
              axios.get(`${API}/tests/subject/${selectedSubject.id}/standard/${standard}`, { withCredentials: true })
                .then(response => setTestList(response.data.tests || []))
                .catch(err => console.error('Error reloading tests:', err));
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
            <div className="tool-icon">🃏</div>
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

// Teacher's published AI tests list
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
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 12,
          }}>
            <div style={{ flex: 1 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                <span style={{ background: 'linear-gradient(135deg,#667eea,#764ba2)', padding: '2px 8px', borderRadius: 4, fontSize: 10, fontWeight: 700, color: '#fff' }}>AI</span>
                <span style={{ fontSize: 15, fontWeight: 600, color: '#F8FAFC' }}>{t.title}</span>
                <span style={{
                  fontSize: 11, fontWeight: 600, padding: '2px 8px', borderRadius: 10,
                  background: 'rgba(34,197,94,0.2)', color: '#22c55e',
                }}>Published</span>
              </div>
              <div style={{ fontSize: 13, color: '#94a3b8', display: 'flex', gap: 16 }}>
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
                whiteSpace: 'nowrap',
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

        {/* NEW: Tabs for Chapters, Homework, Tests, and PYQs */}
        <div style={{ display: 'flex', marginTop: '20px', marginBottom: '20px', borderBottom: '2px solid rgba(255, 255, 255, 0.1)', width: '100%' }}>
          <button 
            onClick={() => setActiveTab('chapters')}
            style={{
              flex: 1,
              padding: '12px 10px',
              border: 'none',
              background: activeTab === 'chapters' ? 'rgba(79, 70, 229, 0.9)' : 'transparent',
              color: '#F8FAFC',
              cursor: 'pointer',
              borderRadius: '8px 8px 0 0',
              fontWeight: '700',
              fontFamily: 'Outfit, sans-serif',
              fontSize: '22px',
              textAlign: 'center'
            }}
          >
            Chapters
          </button>
          <button 
            onClick={() => setActiveTab('homework')}
            style={{
              flex: 1,
              padding: '12px 10px',
              border: 'none',
              background: activeTab === 'homework' ? 'rgba(79, 70, 229, 0.9)' : 'transparent',
              color: '#F8FAFC',
              cursor: 'pointer',
              borderRadius: '8px 8px 0 0',
              fontWeight: '700',
              fontFamily: 'Outfit, sans-serif',
              fontSize: '22px',
              textAlign: 'center'
            }}
          >
            Homework
          </button>
          <button 
            onClick={() => setActiveTab('tests')}
            style={{
              flex: 1,
              padding: '12px 10px',
              border: 'none',
              background: activeTab === 'tests' ? 'rgba(79, 70, 229, 0.9)' : 'transparent',
              color: '#F8FAFC',
              cursor: 'pointer',
              borderRadius: '8px 8px 0 0',
              fontWeight: '700',
              fontFamily: 'Outfit, sans-serif',
              fontSize: '22px',
              textAlign: 'center'
            }}
          >
            Create Test
          </button>
          <button 
            onClick={() => setActiveTab('pyqs')}
            style={{
              flex: 1,
              padding: '12px 10px',
              border: 'none',
              background: activeTab === 'pyqs' ? 'rgba(79, 70, 229, 0.9)' : 'transparent',
              color: '#F8FAFC',
              cursor: 'pointer',
              borderRadius: '8px 8px 0 0',
              fontWeight: '700',
              fontFamily: 'Outfit, sans-serif',
              fontSize: '22px',
              textAlign: 'center'
            }}
          >
            Previous Year Papers
          </button>
          <button 
            onClick={() => setActiveTab('upload')}
            data-testid="upload-content-tab"
            style={{
              flex: 1,
              padding: '12px 10px',
              border: 'none',
              background: activeTab === 'upload' ? 'rgba(79, 70, 229, 0.9)' : 'transparent',
              color: '#F8FAFC',
              cursor: 'pointer',
              borderRadius: '8px 8px 0 0',
              fontWeight: '700',
              fontFamily: 'Outfit, sans-serif',
              fontSize: '22px',
              textAlign: 'center'
            }}
          >
            Generate AI Content
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
         <TestManagement 
           subjectId={selectedSubject.id} 
           standard={standard}
           contentType="homework"
         />
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
             <TestManagement subjectId={selectedSubject.id} standard={standard} />
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

export default App;
