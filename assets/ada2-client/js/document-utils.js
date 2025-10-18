/**
 * Document handling utilities for ADA2 frontend
 * Handles natural language document queries and API interactions
 */

import { cleanTTSContent } from '/public/js/ui-utils.js';

/**
 * Check if a text query is document-related
 * @param {string} text - The user input text
 * @returns {boolean} - True if this is a document query
 */
export function checkDocumentQuery(text) {
  const query = text.toLowerCase();
  
  // Document command patterns
  const documentPatterns = [
    /show\s+(me\s+)?(section|chapter)\s+\d+/i,
    /list\s+(sections|chapters|documents|books)/i,
    /focus\s+(on\s+)?(book|document)\s+\d+/i,
    /(next|previous)\s+(section|chapter)/i,
    /show\s+(me\s+)?(chapter|section)\s+\d+\s+(of|from)\s+\w+/i,
    /open\s+(document|book)\s+widget/i,
    /close\s+(document|book)\s+widget/i
  ];
  
  // Check if query matches any document pattern
  for (const pattern of documentPatterns) {
    if (pattern.test(query)) {
      return true;
    }
  }
  
  return false;
}

/**
 * Handle document queries by calling the document API and processing responses
 * @param {string} text - The user query text
 * @param {Function} clearSubtitles - Clear subtitles function
 * @param {Function} addSubtitle - Add subtitle function
 * @param {Function} updateUIState - Update UI state function
 * @returns {Promise<void>}
 */
export async function handleDocumentQuery(text, clearSubtitles, addSubtitle, updateUIState) {
  try {
    const query = text.toLowerCase();
    
    // Check for widget control commands first
    if (/open\s+(document|book)\s+widget/i.test(query)) {
      // Fetch real documents from API and show widget
      if (window.documentWidget) {
        try {
          // First, get the list of available documents
          const docsResponse = await fetch('/api/documents/list');
          const docsData = await docsResponse.json();
          
          if (docsData.success && docsData.documents && Object.keys(docsData.documents).length > 0) {
            const documentKeys = Object.keys(docsData.documents);
            
            // Always show library first (even with just one document)
            const documentsArray = documentKeys.map((docId, index) => ({
              id: docId,
              title: docsData.documents[docId].title,
              author: docsData.documents[docId].author,
              chapters: docsData.documents[docId].chapters || 0
            }));
            
            window.documentWidget.displayDocuments(documentsArray);
            
            if (documentKeys.length === 1) {
              const responseText = `Showing your document library with ${documentKeys.length} book.`;
              speakResponse(responseText, clearSubtitles, addSubtitle);
            } else {
              const responseText = `Showing your document library with ${documentKeys.length} books.`;
              speakResponse(responseText, clearSubtitles, addSubtitle);
            }
          } else {
            // No documents available - show empty library with upload option
            window.documentWidget.displayDocuments([]);
            const responseText = "Your document library is empty. Use the upload button to add EPUB files.";
            speakResponse(responseText, clearSubtitles, addSubtitle);
          }
        } catch (error) {
          console.error('Error fetching documents:', error);
          const responseText = "I had trouble accessing the documents. Please make sure the backend is running and try again.";
          speakResponse(responseText, clearSubtitles, addSubtitle);
        }
      }
      return;
    }
    
    if (/close\s+(document|book)\s+widget/i.test(query)) {
      if (window.documentWidget) {
        window.documentWidget.hide();
        const responseText = "I've closed the document widget.";
        speakResponse(responseText, clearSubtitles, addSubtitle);
      }
      return;
    }
    
    // Check for chapter/section display commands
    const chapterMatch = query.match(/show\s+(me\s+)?(section|chapter)\s+(\d+)/i);
    if (chapterMatch) {
      const chapterNumber = parseInt(chapterMatch[3]);
      
      try {
        // First ensure we have a document focused
        const docsResponse = await fetch('/api/documents/list');
        const docsData = await docsResponse.json();
        
        if (!docsData.success || !docsData.documents || Object.keys(docsData.documents).length === 0) {
          const responseText = "I don't have any documents loaded. Please upload an EPUB file first.";
          speakResponse(responseText, clearSubtitles, addSubtitle);
          return;
        }
        
        // If widget is not visible, open it first
        if (window.documentWidget && !window.documentWidget.isVisible) {
          // Call the open widget function
          await handleDocumentQuery("open document widget", clearSubtitles, addSubtitle, updateUIState);
        }
        
        // Now load the specific chapter
        if (window.documentWidget && window.documentWidget.isVisible) {
          // Find the section in the current document
          if (window.documentWidget.currentSections && window.documentWidget.currentSections.length > 0) {
            const section = window.documentWidget.currentSections.find(s => s.order === chapterNumber);
            
            if (section) {
              // Load the section content in the widget
              await window.documentWidget.loadSectionContent(section, chapterNumber);
              
              // Get the actual content to speak
              const contentResponse = await fetch('/api/documents/query', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query: `show section ${chapterNumber}` })
              });
              const contentData = await contentResponse.json();
              
              if (contentData.success && contentData.content) {
                speakResponse(contentData.content, kokoroSpeak, clearSubtitles, addSubtitle);
              } else {
                const responseText = `I found chapter ${chapterNumber} but couldn't load its content.`;
                speakResponse(responseText, clearSubtitles, addSubtitle);
              }
              return;
            } else {
              const responseText = `I couldn't find chapter ${chapterNumber}. This document has ${window.documentWidget.currentSections.length} chapters.`;
              speakResponse(responseText, clearSubtitles, addSubtitle);
              return;
            }
          }
        }
      } catch (error) {
        console.error('Error showing chapter:', error);
        const responseText = `I had trouble loading chapter ${chapterNumber}. Please try again.`;
        speakResponse(responseText, clearSubtitles, addSubtitle);
        return;
      }
    }

    // Original API-based document handling for other commands
    const response = await fetch('/api/documents/query', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ query: text })
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    
    if (data.success) {
      let responseText = '';
      
      if (data.type === 'section_content') {
        // For section content, read the full content directly
        responseText = data.content;
        
        // Also update subtitles with the title
        clearSubtitles();
        addSubtitle(`📖 ${data.title}`, 10000);
        
      } else if (data.type === 'section_list') {
        // For section lists, create a spoken summary
        const sectionCount = data.sections.length;
        responseText = `I found ${sectionCount} sections. Here they are: `;
        
        data.sections.slice(0, 5).forEach((section, index) => {
          responseText += `Section ${section.number}: ${section.title}. `;
        });
        
        if (sectionCount > 5) {
          responseText += `And ${sectionCount - 5} more sections.`;
        }
        
      } else if (data.type === 'document_list') {
        // For document lists, create a spoken summary
        const docCount = Object.keys(data.documents).length;
        if (docCount === 0) {
          responseText = "No documents have been uploaded yet.";
        } else {
          responseText = `I found ${docCount} document${docCount > 1 ? 's' : ''}. `;
          Object.values(data.documents).forEach((doc, index) => {
            responseText += `${index + 1}: ${doc.title} by ${doc.author}. `;
          });
        }
        
      } else {
        // Generic success message
        responseText = data.message;
      }
      
      // Clean and speak the response
      speakResponse(responseText, clearSubtitles, addSubtitle);
      
    } else {
      // Handle error case
      const errorMessage = data.message || "I couldn't process that document request.";
      speakResponse(errorMessage, kokoroSpeak, clearSubtitles, addSubtitle);
    }
    
  } catch (error) {
    console.error('Document query error:', error);
    
    const errorMessage = "I encountered an error processing your document request.";
    speakResponse(errorMessage, kokoroSpeak, clearSubtitles, addSubtitle);
    
  } finally {
    // Reset UI state
    const nodeChat = document.getElementById('chat');
    if (nodeChat) {
      nodeChat.disabled = false;
    }
    
    // Note: isSpeaking and isProcessing states are managed by the calling function
    // since they need to be passed in or managed externally
  }
}

/**
 * Helper function to speak a response with unified TTS
 * @param {string} responseText - Text to speak
 * @param {Function} clearSubtitles - Clear subtitles function
 * @param {Function} addSubtitle - Add subtitle function
 */
function speakResponse(responseText, clearSubtitles, addSubtitle) {
  if (!window.unifiedTTS || !window.unifiedTTS.isReady()) {
    console.warn('TTS system not ready');
    return;
  }
  
  const ttsContent = cleanTTSContent(responseText);
  
  if (ttsContent.length > 0) {
    let sentenceId;
    window.unifiedTTS.speak(ttsContent, {
      onsubtitles: (sentence, id, word) => {
        if (id !== sentenceId) {
          sentenceId = id;
          clearSubtitles();
        }
        addSubtitle(word);
      }
    });
  }
}