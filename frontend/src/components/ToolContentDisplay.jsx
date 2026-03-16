import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import { API, cleanAIContent, FormattedContent, translateText, translateBatch, translateContent, SimpleList } from '@/utils/helpers';

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

export default ToolContentDisplay;
