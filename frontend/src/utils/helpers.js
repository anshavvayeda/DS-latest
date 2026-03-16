import React from 'react';
import axios from 'axios';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';

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

export {
  API,
  getSubjectVectorIcon,
  getSubjectColorClass,
  getSubjectIcon,
  cleanAIContent,
  FormattedContent,
  translateText,
  translateBatch,
  translateContent,
  SimpleList,
  extractErrorMessage
};
