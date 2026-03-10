import React, { useState, useEffect } from 'react';
import axios from 'axios';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import QuestionRenderer, { PassageDisplay, SectionHeader, FormattedContent } from './QuestionRenderer';
import './HomeworkAnswering.css';

const API = process.env.REACT_APP_BACKEND_URL ? `${process.env.REACT_APP_BACKEND_URL}/api` : '/api';

function HomeworkAnswering({ homework, onBack, onSubmit, isTeacherPreview = false }) {
  const [questions, setQuestions] = useState([]);
  const [solutions, setSolutions] = useState([]);
  const [answers, setAnswers] = useState({});
  const [evaluations, setEvaluations] = useState({});
  const [helpText, setHelpText] = useState({});
  const [loading, setLoading] = useState(true);
  const [evaluating, setEvaluating] = useState({});
  const [gettingHelp, setGettingHelp] = useState({});
  const [wordCounts, setWordCounts] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [allAnswered, setAllAnswered] = useState(false);

  useEffect(() => {
    loadHomeworkData();
  }, [homework.id]);

  useEffect(() => {
    const answered = questions.length > 0 && questions.every(q => {
      const ans = answers[q.question_number];
      if (!ans) return false;
      // Handle different answer formats
      if (typeof ans === 'string') return ans.trim().length > 0;
      if (typeof ans === 'object') return Object.keys(ans).length > 0;
      return true;
    });
    setAllAnswered(answered);
  }, [answers, questions]);

  const loadHomeworkData = async () => {
    try {
      const response = await axios.get(`${API}/homework/${homework.id}/questions-v2`, {
        withCredentials: true
      });
      
      if (!response.data.questions_extracted || !response.data.questions || response.data.questions.length === 0) {
        alert('Questions not extracted yet. Please try again later.');
        onBack();
        return;
      }
      
      setQuestions(response.data.questions);
      
      // Try to load solutions if available
      try {
        const solResponse = await axios.get(`${API}/homework/${homework.id}/solutions`, {
          withCredentials: true
        });
        if (solResponse.data.solutions) {
          setSolutions(solResponse.data.solutions);
        }
      } catch (e) {
        console.log('No solutions available');
      }
      
    } catch (error) {
      console.error('Error loading homework:', error);
      alert('Failed to load homework');
      onBack();
    } finally {
      setLoading(false);
    }
  };

  const handleAnswerChange = (questionNum, value) => {
    setAnswers(prev => ({ ...prev, [questionNum]: value }));
    
    // Calculate word count for text answers
    if (typeof value === 'string') {
      const words = value.trim().split(/\s+/).filter(w => w.length > 0);
      setWordCounts(prev => ({ ...prev, [questionNum]: words.length }));
    }
    
    // Clear previous evaluation if answer changes
    if (evaluations[questionNum]) {
      setEvaluations(prev => ({ ...prev, [questionNum]: null }));
    }
  };

  const checkAnswer = async (questionNum) => {
    const answer = answers[questionNum];
    if (!answer || (typeof answer === 'string' && answer.trim().length === 0)) {
      alert('Please write your answer first');
      return;
    }

    const question = questions.find(q => q.question_number === questionNum);
    const solution = solutions.find(s => s.question_number === questionNum);

    setEvaluating(prev => ({ ...prev, [questionNum]: true }));

    try {
      const response = await axios.post(
        `${API}/homework/${homework.id}/evaluate-answer`,
        {
          question_number: questionNum,
          question_text: question.question_text || question.question,
          student_answer: typeof answer === 'string' ? answer : JSON.stringify(answer),
          model_answer: solution ? (solution.answer || solution.solution) : null,
          question_type: question.question_type
        },
        { withCredentials: true }
      );

      setEvaluations(prev => ({
        ...prev,
        [questionNum]: response.data.evaluation
      }));
    } catch (error) {
      console.error('Error evaluating answer:', error);
      alert('Failed to check answer. Please try again.');
    } finally {
      setEvaluating(prev => ({ ...prev, [questionNum]: false }));
    }
  };

  const getHelp = async (questionNum) => {
    const question = questions.find(q => q.question_number === questionNum);
    
    setGettingHelp(prev => ({ ...prev, [questionNum]: true }));

    try {
      const response = await axios.post(
        `${API}/homework/${homework.id}/help`,
        {
          question_text: question.question_text || question.question,
          model_answer: solutions.find(s => s.question_number === questionNum)?.answer,
          question_type: question.question_type
        },
        { withCredentials: true }
      );

      setHelpText(prev => ({
        ...prev,
        [questionNum]: response.data.help_text
      }));
    } catch (error) {
      console.error('Error getting help:', error);
      alert('Failed to get help. Please try again.');
    } finally {
      setGettingHelp(prev => ({ ...prev, [questionNum]: false }));
    }
  };

  const handleSubmit = async () => {
    if (!allAnswered) {
      const unanswered = questions.filter(q => {
        const ans = answers[q.question_number];
        return !ans || (typeof ans === 'string' && ans.trim().length === 0);
      });
      if (!window.confirm(`You have ${unanswered.length} unanswered questions. Submit anyway?`)) {
        return;
      }
    }

    setSubmitting(true);
    try {
      await axios.post(`${API}/homework/${homework.id}/submit`, {}, { withCredentials: true });
      alert('✅ Homework submitted successfully!');
      onSubmit();
    } catch (error) {
      console.error('Error submitting homework:', error);
      alert('Failed to submit homework');
    } finally {
      setSubmitting(false);
    }
  };

  // Group questions by section
  const getGroupedQuestions = () => {
    const grouped = {};
    questions.forEach(q => {
      const sectionId = q.section_id || 'default';
      if (!grouped[sectionId]) {
        grouped[sectionId] = {
          section_id: sectionId,
          section_title: q.section_title,
          section_instruction: q.section_instruction,
          passage: q.passage,
          questions: []
        };
      }
      grouped[sectionId].questions.push(q);
    });
    return Object.values(grouped);
  };

  if (loading) {
    return <div className="homework-loading">Loading homework...</div>;
  }

  const sections = getGroupedQuestions();

  return (
    <div className="homework-answering">
      <div className="homework-header">
        <button onClick={onBack} className="back-btn">← Back</button>
        <h2>{homework.title}</h2>
      </div>

      {isTeacherPreview && (
        <div className="preview-notice" style={{
          background: '#fef3c7',
          color: '#92400e',
          padding: '12px 16px',
          borderRadius: '8px',
          marginBottom: '16px',
          fontWeight: 600,
          fontSize: '14px',
          textAlign: 'center'
        }}>
          👁️ Preview Mode: You can view homework questions but cannot submit answers.
        </div>
      )}

      <div className="questions-container">
        {sections.map((section, sectionIdx) => (
          <div key={section.section_id} className="section-container" style={{ marginBottom: '32px' }}>
            {/* Section Header */}
            {(section.section_instruction || section.section_title) && (
              <SectionHeader
                sectionId={section.section_id}
                sectionTitle={section.section_title}
                sectionInstruction={section.section_instruction}
              />
            )}
            
            {/* Passage/Poem for comprehension sections */}
            {section.passage && (
              <PassageDisplay
                passage={section.passage}
                title={section.section_title?.toLowerCase().includes('poem') ? 'Poem' : 'Reading Passage'}
              />
            )}
            
            {/* Questions in this section */}
            {section.questions.map((question, qIdx) => {
              const qNum = question.question_number;
              const wordCount = wordCounts[qNum] || 0;
              const evaluation = evaluations[qNum];
              const help = helpText[qNum];
              const questionType = (question.question_type || 'short_answer').toLowerCase();

              return (
                <div key={`${section.section_id}-${qNum}`} className="question-card" data-testid={`question-${qNum}`}>
                  {/* Question Renderer */}
                  <QuestionRenderer
                    question={question}
                    answer={answers[qNum]}
                    onChange={(value) => handleAnswerChange(qNum, value)}
                    disabled={isTeacherPreview}
                    showSection={false} // We're showing section at container level
                    isFirstInSection={qIdx === 0}
                  />
                  
                  {/* Word count for text answers */}
                  {['short_answer', 'long_answer', 'essay'].includes(questionType) && (
                    <div className="answer-meta" style={{ 
                      marginTop: '8px', 
                      fontSize: '12px', 
                      color: wordCount > 500 ? '#ef4444' : '#64748b' 
                    }}>
                      {wordCount} words
                    </div>
                  )}

                  {/* Action Buttons */}
                  <div className="question-actions" style={{ 
                    display: 'flex', 
                    gap: '12px', 
                    marginTop: '16px' 
                  }}>
                    <button
                      onClick={() => checkAnswer(qNum)}
                      disabled={isTeacherPreview || evaluating[qNum] || !answers[qNum]}
                      className="check-answer-btn"
                      data-testid={`check-answer-${qNum}`}
                      style={{
                        padding: '10px 20px',
                        borderRadius: '8px',
                        border: 'none',
                        background: isTeacherPreview ? '#e2e8f0' : '#10b981',
                        color: 'white',
                        fontWeight: '600',
                        cursor: isTeacherPreview ? 'not-allowed' : 'pointer',
                        opacity: isTeacherPreview || !answers[qNum] ? 0.5 : 1
                      }}
                    >
                      {evaluating[qNum] ? '⏳ Checking...' : (isTeacherPreview ? '🔒 Check' : '✓ Check Answer')}
                    </button>

                    <button
                      onClick={() => getHelp(qNum)}
                      disabled={isTeacherPreview || gettingHelp[qNum]}
                      className="help-btn"
                      data-testid={`get-help-${qNum}`}
                      style={{
                        padding: '10px 20px',
                        borderRadius: '8px',
                        border: 'none',
                        background: isTeacherPreview ? '#e2e8f0' : '#6366f1',
                        color: 'white',
                        fontWeight: '600',
                        cursor: isTeacherPreview ? 'not-allowed' : 'pointer',
                        opacity: isTeacherPreview ? 0.5 : 1
                      }}
                    >
                      {gettingHelp[qNum] ? '⏳ Getting help...' : (isTeacherPreview ? '🔒 Help' : '💡 Help Me')}
                    </button>
                  </div>

                  {/* Evaluation Result */}
                  {evaluation && (
                    <div className={`evaluation-result ${evaluation.is_correct ? 'correct' : 'needs-improvement'}`}
                      style={{
                        marginTop: '16px',
                        padding: '16px',
                        borderRadius: '10px',
                        background: evaluation.is_correct ? '#dcfce7' : '#fef3c7',
                        border: `1px solid ${evaluation.is_correct ? '#86efac' : '#fcd34d'}`
                      }}>
                      <h4 style={{ margin: '0 0 8px 0', color: evaluation.is_correct ? '#166534' : '#92400e' }}>
                        {evaluation.is_correct ? '✅ Correct!' : '📝 Needs Improvement'}
                      </h4>
                      <div className="feedback" style={{ color: '#374151' }}>
                        <FormattedContent content={evaluation.feedback} />
                      </div>
                      {evaluation.corrected_answer && !evaluation.is_correct && (
                        <div className="corrected-answer" style={{ marginTop: '12px' }}>
                          <strong>Suggested Answer:</strong>
                          <FormattedContent content={evaluation.corrected_answer} />
                        </div>
                      )}
                      {evaluation.score !== undefined && (
                        <div className="score" style={{ marginTop: '8px', fontWeight: '600' }}>
                          Score: {Math.round(evaluation.score * 100)}%
                        </div>
                      )}
                    </div>
                  )}

                  {/* Help Content */}
                  {help && (
                    <div className="help-content" style={{
                      marginTop: '16px',
                      padding: '16px',
                      borderRadius: '10px',
                      background: '#eff6ff',
                      border: '1px solid #bfdbfe'
                    }}>
                      <h4 style={{ margin: '0 0 8px 0', color: '#1e40af' }}>💡 Here's some help:</h4>
                      <FormattedContent content={help} />
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        ))}
      </div>

      {allAnswered && (
        <div className="completion-reward" style={{
          background: 'linear-gradient(135deg, #fef3c7 0%, #fde68a 100%)',
          padding: '24px',
          borderRadius: '12px',
          textAlign: 'center',
          marginBottom: '24px'
        }}>
          <h2 style={{ margin: '0 0 8px 0' }}>🌟 Amazing Work, Champ! 🌟</h2>
          <div style={{ fontSize: '32px', margin: '12px 0' }}>⭐⭐⭐⭐⭐</div>
          <div style={{ fontSize: '28px' }}>🏆 🏆 🏆</div>
          <p style={{ margin: '12px 0 0 0' }}>You've attempted all questions! Great job! 💪</p>
        </div>
      )}

      <div className="submit-section" style={{ textAlign: 'center', paddingBottom: '40px' }}>
        <button
          onClick={handleSubmit}
          disabled={submitting || isTeacherPreview}
          className="submit-homework-btn"
          data-testid="submit-homework-btn"
          style={{
            padding: '16px 48px',
            fontSize: '18px',
            fontWeight: '700',
            background: isTeacherPreview ? '#94a3b8' : 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
            color: 'white',
            border: 'none',
            borderRadius: '12px',
            cursor: isTeacherPreview ? 'not-allowed' : 'pointer',
            boxShadow: '0 4px 14px rgba(102, 126, 234, 0.4)'
          }}
        >
          {isTeacherPreview ? '🔒 Submit Disabled (Preview)' : (submitting ? '⏳ Submitting...' : '📤 Submit Homework')}
        </button>
      </div>
    </div>
  );
}

export default HomeworkAnswering;
