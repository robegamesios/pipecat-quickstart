/**
 * AI Chat Widget Utilities
 * Handles unified AI chat widget initialization and integration
 */

/**
 * Initialize AI chat widget functionality
 * @param {Object} dependencies - Required dependencies from main app
 */
export function initializeChatWidget(dependencies) {
  const { updateUIState, stopTalking } = dependencies;
  
  // Export functions to global scope for chat widget
  window.updateUIState = updateUIState;
  window.stopTalking = stopTalking;
  
  // Create AI chat widget instance immediately
  const aiChatWidget = new AIChatWidget();
  window.chatWidget = aiChatWidget; // Make it globally accessible
  
  // AI chat widget button
  const nodeChatGPTBtn = document.getElementById('chatgpt-widget-btn');
  
  if (nodeChatGPTBtn) {
    nodeChatGPTBtn.addEventListener('click', function () {
      // Use widget manager to handle widget switching
      if (aiChatWidget.isVisible) {
        aiChatWidget.hide();
      } else {
        window.widgetManager.showWidget('chat', () => {
          aiChatWidget.show();
        });
      }
    });
  }
}