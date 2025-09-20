/**
 * English lipsync module - Stub implementation
 */

export const lipsyncEn = {
  // Simple phoneme mapping for basic lip sync
  phonemeToViseme: {
    'sil': 0,   // silence
    'aa': 1,    // open
    'ae': 1,    // open
    'ah': 1,    // open
    'ao': 2,    // rounded
    'aw': 2,    // rounded
    'ay': 1,    // open
    'b': 3,     // closed
    'm': 3,     // closed
    'p': 3,     // closed
    'f': 4,     // narrow
    'v': 4,     // narrow
    'th': 4,    // narrow
    // Add more mappings as needed
  },
  
  // Convert text to basic phonemes (simplified)
  textToPhonemes: function(text) {
    // Very basic implementation - just return vowel/consonant pattern
    const words = text.toLowerCase().split(' ');
    return words.map(word => {
      return word.split('').map(char => {
        if ('aeiou'.includes(char)) return 'aa';
        if ('bmp'.includes(char)) return 'b';
        if ('fv'.includes(char)) return 'f';
        return 'sil';
      });
    }).flat();
  }
};

export default lipsyncEn;