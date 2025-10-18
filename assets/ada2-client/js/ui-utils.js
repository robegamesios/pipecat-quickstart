// UI Utilities - Pure functions without global variables
// All state management remains in main.js

/**
 * Create stop button element
 * @param {Function} onClickHandler - Function to call when button is clicked
 * @returns {HTMLElement} The created stop button element
 */
export function createStopButton(onClickHandler) {
  const avatarContainer = document.getElementById('avatar');
  if (!avatarContainer) return null;

  const stopButton = document.createElement('button');
  stopButton.id = 'stop-speech-button';
  stopButton.innerHTML = '⏹️';
  stopButton.title = 'Stop Speech (ESC)';
  stopButton.setAttribute('aria-label', 'Stop current speech');

  stopButton.addEventListener('click', onClickHandler);

  avatarContainer.appendChild(stopButton);
  return stopButton;
}

/**
 * Create thinking icon element
 * @param {Function} onClickHandler - Function to call when thinking icon is clicked
 * @returns {HTMLElement} The created thinking icon element
 */
export function createThinkingIcon(onClickHandler = null) {
  const avatarContainer = document.getElementById('avatar');
  if (!avatarContainer) return null;

  const thinkingIcon = document.createElement('div');
  thinkingIcon.id = 'thinking-icon';
  thinkingIcon.style.cursor = 'pointer';
  thinkingIcon.title = 'Click to cancel request';
  thinkingIcon.innerHTML = `
    <div class="thinking-spinner">
      <div class="spinner-line"></div>
      <div class="spinner-line"></div>
      <div class="spinner-line"></div>
      <div class="spinner-line"></div>
      <div class="spinner-line"></div>
      <div class="spinner-line"></div>
      <div class="spinner-line"></div>
      <div class="spinner-line"></div>
    </div>
  `;

  if (onClickHandler) {
    thinkingIcon.addEventListener('click', onClickHandler);
  }

  avatarContainer.appendChild(thinkingIcon);
  return thinkingIcon;
}

/**
 * Update UI element visibility based on state
 * @param {string} elementId - ID of the element to update
 * @param {boolean} shouldShow - Whether the element should be visible
 * @param {Function} createElement - Function to create element if it doesn't exist
 * @returns {HTMLElement|null} The element or null if not found/created
 */
export function updateElementVisibility(elementId, shouldShow, createElement = null) {
  let element = document.getElementById(elementId);

  if (!element && shouldShow && createElement) {
    element = createElement();
  }

  if (element) {
    if (shouldShow) {
      element.classList.add('visible');
    } else {
      element.classList.remove('visible');
    }
  }

  return element;
}

/**
 * Update both thinking icon and stop button visibility
 * @param {boolean} isProcessing - Whether AI is processing
 * @param {boolean} isSpeaking - Whether avatar is speaking
 * @param {Function} stopClickHandler - Handler for stop button clicks
 * @param {Function} cancelClickHandler - Handler for cancel button clicks
 */
export function updateUIState(isProcessing, isSpeaking, stopClickHandler, cancelClickHandler = null) {
  // Handle thinking icon - pass cancel handler
  const thinkingCancelHandler = cancelClickHandler || (async () => {
    // Set global stop flag to cancel stream reading
    window.globalStopRequested = true;
    
    // Use the same mechanism as voice interruption - trigger stop button if it exists
    const stopButton = document.getElementById('stop-speech-button');
    if (stopButton && stopButton.classList.contains('visible')) {
      stopButton.click(); // Use existing stop mechanism
    }
    
    try {
      // Call the stop server endpoint to stop the AutoGen team
      await signalServerStop();
      // Add a small delay to allow backend cleanup
      await new Promise(resolve => setTimeout(resolve, 500));
    } catch (err) {
      console.error('Error stopping AutoGen team:', err);
    }
  });
  
  updateElementVisibility('thinking-icon', isProcessing, () => createThinkingIcon(thinkingCancelHandler));
  
  // Handle stop button
  updateElementVisibility('stop-speech-button', isSpeaking, () => createStopButton(stopClickHandler));
}

/**
 * Clear all TTS queues and reset audio state
 * @param {Object} kokoro - Kokoro TTS instance
 * @param {Array} kokoroQueue - Local kokoro queue
 * @param {Object} head - TalkingHead instance
 */
export function clearTTSState(kokoro, kokoroQueue, head) {
  // Clear Kokoro TTS queue
  if (kokoro) {
    if (kokoro.queue) kokoro.queue.length = 0;
    if (kokoro.audioQueue) kokoro.audioQueue.length = 0;
    if (kokoro.textQueue) kokoro.textQueue.length = 0;
    kokoro.processing = false;
    kokoro.isProcessing = false;
  }

  // Clear local queues
  kokoroQueue.length = 0;

  // Stop TalkingHead if it has stopSpeaking method
  if (head && typeof head.stopSpeaking === 'function') {
    head.stopSpeaking();
  }
}

/**
 * Monitor when TalkingHead finishes speaking
 * @param {Object} head - TalkingHead instance
 * @param {Array} kokoroQueue - Local kokoro queue
 * @param {Function} onSpeechEnd - Callback when speech ends
 * @param {Function} shouldContinue - Function to check if monitoring should continue
 */
export function monitorSpeechEnd(head, kokoroQueue, onSpeechEnd, shouldContinue) {
  if (!head || !shouldContinue()) return;
  
  const checkSpeechEnd = () => {
    if (head.isSpeaking === false && kokoroQueue.length === 0) {
      onSpeechEnd();
      return;
    }
    
    if (shouldContinue()) {
      requestAnimationFrame(checkSpeechEnd);
    }
  };
  
  requestAnimationFrame(checkSpeechEnd);
}

/**
 * Clean text content for TTS by removing termination strings
 * @param {string} content - Raw content from agent
 * @returns {string} Cleaned content ready for TTS
 */
export function cleanTTSContent(content) {
  return content
    .replace(/TERMINATE/g, '')
    .trim();
}

/**
 * Make fetch request to stop server streaming
 * @returns {Promise} Promise that resolves when request completes
 */
export function signalServerStop() {
  return fetch('/api/stop', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' }
  }).catch(() => {}); // Silent error handling
}