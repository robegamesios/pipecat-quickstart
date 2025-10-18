/**
 * Web Worker for phonemization to prevent UI blocking
 * Handles eSpeak phoneme conversion in background thread
 */

// Cache for phoneme results
const phonemeCache = new Map();

// Phonemizer will be passed from main thread
let phonemizerModule = null;

self.onmessage = async function(e) {
  const { id, text, language, type, phonemizerCode } = e.data;
  
  try {
    if (type === 'init') {
      // Initialize phonemizer in worker from main thread code
      if (phonemizerCode) {
        eval(phonemizerCode);
        phonemizerModule = self.phonemize;
      }
      self.postMessage({
        id,
        type: 'initialized'
      });
      return;
    }
    
    if (type === 'phonemize') {
      // Check cache first
      const cacheKey = `${text}_${language}`;
      
      if (phonemeCache.has(cacheKey)) {
        self.postMessage({
          id,
          type: 'phonemes',
          phonemes: phonemeCache.get(cacheKey),
          fromCache: true
        });
        return;
      }
      
      if (!phonemizerModule) {
        self.postMessage({
          id,
          type: 'error',
          error: 'Phonemizer not initialized'
        });
        return;
      }
      
      // Process phonemes
      const phonemeArray = await phonemizerModule(text.trim(), language);
      const phonemes = phonemeArray.join(" ");
      
      // Post-process (same as original)
      const processedPhonemes = phonemes
        .replace(/ʲ/g, "j")
        .replace(/r/g, "ɹ") 
        .replace(/x/g, "k")
        .replace(/ɬ/g, "l")
        .trim();
      
      // Cache the result
      phonemeCache.set(cacheKey, processedPhonemes);
      
      self.postMessage({
        id,
        type: 'phonemes',
        phonemes: processedPhonemes,
        fromCache: false
      });
      
    } else if (type === 'clearCache') {
      phonemeCache.clear();
      self.postMessage({
        id,
        type: 'cacheCleared'
      });
    }
    
  } catch (error) {
    self.postMessage({
      id,
      type: 'error',
      error: error.message
    });
  }
};