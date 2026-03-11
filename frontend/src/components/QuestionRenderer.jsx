import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';

/**
 * QuestionRenderer - Renders different question types with appropriate UI
 * 
 * Supported question types:
 * - mcq: Multiple choice with radio buttons
 * - fill_blanks: Fill in the blank with inline inputs
 * - match_following: Match columns with dropdowns
 * - short_answer: Text area for short responses
 * - long_answer: Larger text area for essays
 * - synonyms: Word meaning input
 * - grammar: Grammar exercise input
 * - true_false: True/False radio buttons
 */

const FormattedContent = ({ content }) => {
  if (!content) return null;
  return (
    <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
      {content}
    </ReactMarkdown>
  );
};

// Passage/Poem Display Component
const PassageDisplay = ({ passage, title }) => {
  if (!passage) return null;
  
  return (
    <div className="passage-container" style={{
      background: 'linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%)',
      border: '1px solid #cbd5e1',
      borderRadius: '12px',
      padding: '20px',
      marginBottom: '20px',
      boxShadow: '0 2px 4px rgba(0,0,0,0.05)'
    }}>
      {title && (
        <div style={{
          fontWeight: '700',
          color: '#475569',
          marginBottom: '12px',
          fontSize: '14px',
          textTransform: 'uppercase',
          letterSpacing: '0.5px'
        }}>
          📖 {title}
        </div>
      )}
      <div style={{
        fontStyle: 'italic',
        color: '#334155',
        lineHeight: '1.8',
        fontSize: '15px',
        whiteSpace: 'pre-wrap'
      }}>
        <FormattedContent content={passage} />
      </div>
    </div>
  );
};

// Section Header Component
const SectionHeader = ({ sectionId, sectionTitle, sectionInstruction }) => {
  if (!sectionInstruction && !sectionTitle) return null;
  
  return (
    <div className="section-header" style={{
      background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
      color: 'white',
      padding: '16px 20px',
      borderRadius: '10px',
      marginBottom: '16px'
    }}>
      {sectionId && (
        <span style={{
          background: 'rgba(255,255,255,0.2)',
          padding: '4px 10px',
          borderRadius: '4px',
          fontSize: '12px',
          fontWeight: '700',
          marginRight: '10px'
        }}>
          {sectionId}
        </span>
      )}
      {sectionTitle && (
        <span style={{ fontWeight: '600', fontSize: '16px' }}>{sectionTitle}</span>
      )}
      {sectionInstruction && (
        <div style={{
          marginTop: '8px',
          fontSize: '14px',
          opacity: '0.9'
        }}>
          📝 {sectionInstruction}
        </div>
      )}
    </div>
  );
};

// MCQ Question Component
const MCQQuestion = ({ question, answer, onChange, disabled }) => {
  const rawOptions = question.options;
  const options = Array.isArray(rawOptions) ? rawOptions : [];
  
  return (
    <div className="mcq-options" style={{
      marginTop: '12px',
      display: 'flex',
      flexDirection: 'column',
      gap: '8px'
    }}>
      {options.map((option, idx) => {
        const optionValue = String.fromCharCode(65 + idx); // A, B, C, D
        const isSelected = answer === optionValue || answer === option;
        
        // Clean option text (remove leading a), b), etc. if present)
        let optionText = option;
        if (typeof option === 'string') {
          optionText = option.replace(/^[a-d]\)\s*/i, '').replace(/^[a-d]\.\s*/i, '');
        }
        
        return (
          <label 
            key={idx} 
            style={{
              display: 'flex',
              alignItems: 'center',
              padding: '12px 16px',
              background: isSelected ? '#e0e7ff' : 'white',
              border: isSelected ? '2px solid #667eea' : '1px solid #e2e8f0',
              borderRadius: '10px',
              cursor: disabled ? 'not-allowed' : 'pointer',
              transition: 'all 0.2s ease',
              opacity: disabled ? 0.6 : 1
            }}
          >
            <input
              type="radio"
              name={`mcq-${question.question_number}`}
              value={optionValue}
              checked={isSelected}
              onChange={(e) => onChange(e.target.value)}
              disabled={disabled}
              style={{ 
                marginRight: '12px', 
                width: '18px', 
                height: '18px',
                accentColor: '#667eea'
              }}
            />
            <span style={{ 
              fontWeight: '600', 
              marginRight: '10px', 
              color: '#6366f1',
              minWidth: '24px'
            }}>
              {optionValue}.
            </span>
            <span style={{ color: '#1e293b' }}>{optionText}</span>
          </label>
        );
      })}
    </div>
  );
};

// Fill in Blanks Component
const FillBlanksQuestion = ({ question, answer, onChange, disabled }) => {
  const questionText = question.question_text || '';
  const blanksCount = question.blanks_count || 1;
  
  // Parse answers - could be a single string or array
  const answers = typeof answer === 'string' 
    ? answer.split('|||') 
    : (Array.isArray(answer) ? answer : ['']);
  
  // If question has ___ markers, render inline inputs
  if (questionText.includes('___')) {
    const parts = questionText.split('___');
    return (
      <div style={{ lineHeight: '2.2', fontSize: '15px' }}>
        {parts.map((part, idx) => (
          <React.Fragment key={idx}>
            <span>{part}</span>
            {idx < parts.length - 1 && (
              <input
                type="text"
                value={answers[idx] || ''}
                onChange={(e) => {
                  const newAnswers = [...answers];
                  newAnswers[idx] = e.target.value;
                  onChange(newAnswers.join('|||'));
                }}
                disabled={disabled}
                placeholder="..."
                style={{
                  width: '120px',
                  padding: '6px 12px',
                  margin: '0 4px',
                  border: '2px solid #667eea',
                  borderRadius: '6px',
                  fontSize: '14px',
                  background: disabled ? '#f1f5f9' : 'white',
                  textAlign: 'center'
                }}
              />
            )}
          </React.Fragment>
        ))}
      </div>
    );
  }
  
  // Otherwise, show question text + input field
  return (
    <div>
      <div style={{ marginBottom: '12px' }}>{questionText}</div>
      <input
        type="text"
        value={answer || ''}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        placeholder="Type your answer..."
        style={{
          width: '100%',
          padding: '12px 16px',
          border: '2px solid #e2e8f0',
          borderRadius: '8px',
          fontSize: '15px',
          background: disabled ? '#f1f5f9' : 'white'
        }}
      />
    </div>
  );
};

// Match the Following Component
const MatchFollowingQuestion = ({ question, answer, onChange, disabled }) => {
  const leftColumn = question.left_column || [];
  const rightColumn = question.right_column || [];
  
  // Parse answers - stored as JSON string of {left: right} pairs
  let matches = {};
  try {
    matches = typeof answer === 'string' && answer ? JSON.parse(answer) : (answer || {});
  } catch (e) {
    matches = {};
  }
  
  const handleMatchChange = (leftItem, rightItem) => {
    const newMatches = { ...matches, [leftItem]: rightItem };
    onChange(JSON.stringify(newMatches));
  };
  
  return (
    <div style={{ marginTop: '12px' }}>
      <div style={{
        display: 'grid',
        gridTemplateColumns: '1fr auto 1fr',
        gap: '12px',
        alignItems: 'center'
      }}>
        {/* Header Row */}
        <div style={{ fontWeight: '700', color: '#475569', textAlign: 'center', padding: '8px' }}>
          Column A
        </div>
        <div></div>
        <div style={{ fontWeight: '700', color: '#475569', textAlign: 'center', padding: '8px' }}>
          Column B
        </div>
        
        {/* Match Rows */}
        {leftColumn.map((leftItem, idx) => (
          <React.Fragment key={idx}>
            <div style={{
              padding: '12px 16px',
              background: '#f8fafc',
              borderRadius: '8px',
              border: '1px solid #e2e8f0',
              fontWeight: '500'
            }}>
              {idx + 1}. {leftItem}
            </div>
            
            <div style={{ textAlign: 'center', color: '#94a3b8' }}>→</div>
            
            <select
              value={matches[leftItem] || ''}
              onChange={(e) => handleMatchChange(leftItem, e.target.value)}
              disabled={disabled}
              style={{
                padding: '12px 16px',
                borderRadius: '8px',
                border: '2px solid #e2e8f0',
                fontSize: '14px',
                background: disabled ? '#f1f5f9' : 'white',
                cursor: disabled ? 'not-allowed' : 'pointer'
              }}
            >
              <option value="">Select match...</option>
              {rightColumn.map((rightItem, rIdx) => (
                <option key={rIdx} value={rightItem}>{rightItem}</option>
              ))}
            </select>
          </React.Fragment>
        ))}
      </div>
    </div>
  );
};

// True/False Component
const TrueFalseQuestion = ({ question, answer, onChange, disabled }) => {
  return (
    <div style={{ display: 'flex', gap: '16px', marginTop: '12px' }}>
      {['True', 'False'].map((option) => (
        <label
          key={option}
          style={{
            flex: 1,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '16px',
            background: answer === option ? (option === 'True' ? '#dcfce7' : '#fee2e2') : 'white',
            border: answer === option 
              ? `2px solid ${option === 'True' ? '#22c55e' : '#ef4444'}` 
              : '1px solid #e2e8f0',
            borderRadius: '10px',
            cursor: disabled ? 'not-allowed' : 'pointer',
            transition: 'all 0.2s'
          }}
        >
          <input
            type="radio"
            name={`tf-${question.question_number}`}
            value={option}
            checked={answer === option}
            onChange={(e) => onChange(e.target.value)}
            disabled={disabled}
            style={{ marginRight: '8px' }}
          />
          <span style={{ fontWeight: '600' }}>{option === 'True' ? '✓ True' : '✗ False'}</span>
        </label>
      ))}
    </div>
  );
};

// Short Answer Component
const ShortAnswerQuestion = ({ question, answer, onChange, disabled, rows = 3 }) => {
  return (
    <div style={{ marginTop: '12px' }}>
      <textarea
        value={answer || ''}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        placeholder={disabled ? "Answering disabled" : "Type your answer here..."}
        rows={rows}
        style={{
          width: '100%',
          padding: '14px 16px',
          border: '2px solid #e2e8f0',
          borderRadius: '10px',
          fontSize: '15px',
          lineHeight: '1.6',
          resize: 'vertical',
          background: disabled ? '#f1f5f9' : 'white',
          color: '#1e293b'
        }}
      />
    </div>
  );
};

// Synonyms/Meanings Component
const SynonymsQuestion = ({ question, answer, onChange, disabled }) => {
  const questionText = question.question_text || '';
  
  // Extract word from question (e.g., "hooked →" should show input after arrow)
  const parts = questionText.split('→');
  const word = parts[0]?.trim() || questionText;
  
  return (
    <div style={{ 
      display: 'flex', 
      alignItems: 'center', 
      gap: '12px',
      marginTop: '8px'
    }}>
      <span style={{ 
        fontWeight: '600', 
        color: '#475569',
        minWidth: '100px'
      }}>
        {word}
      </span>
      <span style={{ color: '#94a3b8' }}>→</span>
      <input
        type="text"
        value={answer || ''}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        placeholder="Write synonym/meaning..."
        style={{
          flex: 1,
          padding: '10px 14px',
          border: '2px solid #e2e8f0',
          borderRadius: '8px',
          fontSize: '14px',
          background: disabled ? '#f1f5f9' : 'white'
        }}
      />
    </div>
  );
};

// Grammar Question Component
const GrammarQuestion = ({ question, answer, onChange, disabled }) => {
  const questionText = question.question_text || '';
  const instruction = question.instruction || question.section_instruction || '';
  
  return (
    <div style={{ marginTop: '8px' }}>
      {instruction && (
        <div style={{ 
          fontSize: '13px', 
          color: '#64748b', 
          marginBottom: '8px',
          fontStyle: 'italic'
        }}>
          {instruction}
        </div>
      )}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        <span style={{ fontWeight: '500', color: '#334155' }}>{questionText}</span>
        <span style={{ color: '#94a3b8' }}>→</span>
        <input
          type="text"
          value={answer || ''}
          onChange={(e) => onChange(e.target.value)}
          disabled={disabled}
          placeholder="Your answer..."
          style={{
            flex: 1,
            maxWidth: '200px',
            padding: '10px 14px',
            border: '2px solid #e2e8f0',
            borderRadius: '8px',
            fontSize: '14px',
            background: disabled ? '#f1f5f9' : 'white'
          }}
        />
      </div>
    </div>
  );
};

// Main QuestionRenderer Component
const QuestionRenderer = ({ 
  question, 
  answer, 
  onChange, 
  disabled = false,
  showSection = false,
  isFirstInSection = false 
}) => {
  const questionType = (question.question_type || 'short_answer').toLowerCase();
  
  // Render answer input based on question type
  const renderAnswerInput = () => {
    switch (questionType) {
      case 'mcq':
      case 'multiple_choice':
        return <MCQQuestion question={question} answer={answer} onChange={onChange} disabled={disabled} />;
      
      case 'fill_blanks':
      case 'fill_in_the_blanks':
        return <FillBlanksQuestion question={question} answer={answer} onChange={onChange} disabled={disabled} />;
      
      case 'match_following':
      case 'matching':
        return <MatchFollowingQuestion question={question} answer={answer} onChange={onChange} disabled={disabled} />;
      
      case 'true_false':
        return <TrueFalseQuestion question={question} answer={answer} onChange={onChange} disabled={disabled} />;
      
      case 'synonyms':
      case 'meanings':
        return <SynonymsQuestion question={question} answer={answer} onChange={onChange} disabled={disabled} />;
      
      case 'grammar':
        return <GrammarQuestion question={question} answer={answer} onChange={onChange} disabled={disabled} />;
      
      case 'long_answer':
      case 'essay':
        return <ShortAnswerQuestion question={question} answer={answer} onChange={onChange} disabled={disabled} rows={6} />;
      
      case 'short_answer':
      case 'comprehension':
      default:
        return <ShortAnswerQuestion question={question} answer={answer} onChange={onChange} disabled={disabled} rows={3} />;
    }
  };
  
  // Get question type badge color
  const getTypeColor = () => {
    switch (questionType) {
      case 'mcq': return { bg: '#dbeafe', text: '#1d4ed8' };
      case 'fill_blanks': return { bg: '#fef3c7', text: '#b45309' };
      case 'match_following': return { bg: '#d1fae5', text: '#047857' };
      case 'true_false': return { bg: '#e0e7ff', text: '#4338ca' };
      case 'synonyms': return { bg: '#fce7f3', text: '#be185d' };
      case 'grammar': return { bg: '#ede9fe', text: '#6d28d9' };
      case 'long_answer': return { bg: '#fee2e2', text: '#b91c1c' };
      default: return { bg: '#f1f5f9', text: '#475569' };
    }
  };
  
  const typeColor = getTypeColor();
  
  return (
    <div className="question-renderer" style={{ marginBottom: '24px' }}>
      {/* Section Header - only show for first question in section */}
      {showSection && isFirstInSection && (
        <>
          <SectionHeader 
            sectionId={question.section_id}
            sectionTitle={question.section_title}
            sectionInstruction={question.section_instruction}
          />
          <PassageDisplay 
            passage={question.passage} 
            title={questionType === 'comprehension' ? 'Reading Passage' : 'Reference Text'}
          />
        </>
      )}
      
      {/* Question Card */}
      <div style={{
        background: 'white',
        border: '1px solid #e2e8f0',
        borderRadius: '12px',
        padding: '20px',
        boxShadow: '0 1px 3px rgba(0,0,0,0.05)'
      }}>
        {/* Question Header */}
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          marginBottom: '12px'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span style={{
              fontWeight: '700',
              color: '#1e293b',
              fontSize: '16px'
            }}>
              Q{question.question_number}
            </span>
            <span style={{
              background: typeColor.bg,
              color: typeColor.text,
              padding: '4px 10px',
              borderRadius: '20px',
              fontSize: '11px',
              fontWeight: '600',
              textTransform: 'uppercase'
            }}>
              {questionType.replace('_', ' ')}
            </span>
          </div>
          {question.marks && (
            <span style={{
              background: '#f1f5f9',
              color: '#64748b',
              padding: '4px 10px',
              borderRadius: '6px',
              fontSize: '12px',
              fontWeight: '600'
            }}>
              {question.marks} marks
            </span>
          )}
        </div>
        
        {/* Question Instruction (if different from section) */}
        {question.instruction && question.instruction !== question.section_instruction && (
          <div style={{
            fontSize: '13px',
            color: '#64748b',
            marginBottom: '10px',
            fontStyle: 'italic',
            background: '#f8fafc',
            padding: '8px 12px',
            borderRadius: '6px'
          }}>
            💡 {question.instruction}
          </div>
        )}
        
        {/* Question Text - hide for synonyms/grammar as it's shown inline */}
        {!['synonyms', 'grammar'].includes(questionType) && question.question_text && (
          <div style={{
            fontSize: '15px',
            color: '#334155',
            lineHeight: '1.7',
            marginBottom: '16px'
          }}>
            <FormattedContent content={question.question_text} />
          </div>
        )}
        
        {/* Answer Input based on type */}
        {renderAnswerInput()}
      </div>
    </div>
  );
};

export default QuestionRenderer;
export { 
  PassageDisplay, 
  SectionHeader, 
  MCQQuestion, 
  FillBlanksQuestion, 
  MatchFollowingQuestion,
  TrueFalseQuestion,
  ShortAnswerQuestion,
  SynonymsQuestion,
  GrammarQuestion,
  FormattedContent
};
