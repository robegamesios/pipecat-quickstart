/**
 * ADA2 AI Chat Widget - Unified chat interface with model selection
 * Supports Local AI, ChatGPT, and Gemini with conversation history
 */
class AIChatWidget {
  constructor() {
    this.isVisible = false;
    this.container = null;
    this.conversationHistory = [];
    this.browserStatus = 'disconnected';
    this.isInitializing = false;
    this.selectedModel = 'local'; // Default to local
    this.localChatActive = false;
    this.displayMode = 'text'; // 'text' or 'iframe'
    
    // Active text highlighter instance (created per response)
    this.currentTextHighlighter = null;

    // Voice coordination (mute status only)
    this.micAvailable = false;
    this.micMuted = false;
    this.handleVoiceConnected = (event) => this.onVoiceConnected(event);
    this.handleVoiceDisconnected = (event) => this.onVoiceDisconnected(event);
    this.handleMicMuted = (event) => this.onMicMuted(event);
    this.defaultPlaceholder = 'Type your question...';
    this.lastAssistantText = '';
    this.awaitingAssistant = false;
    this.turnPairs = 0;
    this.turnLimit = 60;
    
    this.createWidget();
  }

  createWidget() {
    // Check if already exists
    if (document.getElementById('chatgpt-widget')) {
      this.container = document.getElementById('chatgpt-widget');
      return;
    }

    this.container = document.createElement('div');
    this.container.id = 'chatgpt-widget';
    this.container.className = 'chatgpt-widget';
    
    // Apply centralized widget container styles with flexbox fix
    if (window.WidgetStyles) {
      this.container.style.cssText = window.WidgetStyles.container;
    }
    // Override with proper flexbox structure
    this.container.style.display = 'flex';
    this.container.style.flexDirection = 'column';
    this.container.style.height = '85vh';
    this.container.style.minHeight = '750px';

    this.container.innerHTML = `
      <div style="height: 100%; display: flex; flex-direction: column; padding: 20px 20px 15px 20px; box-sizing: border-box;">
        <!-- Header with model selection and display mode -->
        <div id="chatgpt-header" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; border-bottom: 1px solid #333; padding-bottom: 15px; flex-shrink: 0;">
          <div style="display: flex; align-items: center; gap: 15px;">
            <h3 id="chat-title" style="margin: 0; color: #00d4aa; font-size: 18px; font-weight: 600;">AI Chat</h3>
            <select id="model-selector" style="
              background: #333;
              color: #fff;
              border: 1px solid #555;
              padding: 6px 10px;
              border-radius: 4px;
              font-size: 13px;
              cursor: pointer;
            ">
              <option value="local">Local AI</option>
              <option value="chatgpt">ChatGPT</option>
              <option value="gemini">Gemini</option>
            </select>
            
            <!-- Display Mode buttons inline -->
            <div id="display-mode-buttons" style="display: flex; gap: 5px; margin-left: 10px;">
              <button id="text-mode-btn" class="display-mode-btn active" data-mode="text" style="
                background: #00d4aa;
                color: #000;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                cursor: pointer;
                font-size: 12px;
                font-weight: 500;
              ">Text Chat</button>
              <button id="iframe-mode-btn" class="display-mode-btn" data-mode="iframe" style="
                background: #333;
                color: #fff;
                border: 1px solid #555;
                padding: 6px 12px;
                border-radius: 4px;
                cursor: pointer;
                font-size: 12px;
                font-weight: 500;
              ">Web View</button>
            </div>
          </div>
          <div style="display:flex; align-items:center; gap:8px; margin-left:auto;">
            <button id="new-session-btn" title="Start a new session" style="
              background: #444; color: #fff; border: none; padding: 6px 10px; border-radius: 4px; cursor: pointer; font-size: 12px;">
              New Session
            </button>
            <button id="chatgpt-close-btn" style="background: none; border: none; color: #888; font-size: 18px; cursor: pointer; padding: 5px; width: 30px; height: 30px; display: flex; align-items: center; justify-content: center; border-radius: 4px; transition: all 0.2s ease;">✕</button>
          </div>
        </div>

        <!-- Conversation History - This should expand to fill space -->
        <div style="flex: 1; overflow: hidden; display: flex; flex-direction: column; min-height: 0;">
          <h4 id="conversation-title" style="margin: 0 0 15px 0; color: #ccc; font-size: 14px; flex-shrink: 0;">Conversation History</h4>
          
          <!-- Text Mode Container -->
          <div id="text-mode-container" style="flex: 1; display: flex; flex-direction: column; min-height: 0;">
            <div id="chatgpt-conversation" style="
              flex: 1;
              overflow-y: auto; 
              background: #2d2d2d; 
              border-radius: 8px; 
              padding: 15px;
              margin-bottom: 15px;
            ">
              <div id="text-chat-placeholder" style="
                display: flex;
                align-items: center;
                justify-content: center;
                height: 100%;
                color: #ddd;
                text-align: center;
                font-size: 14px;
                flex-direction: column;
                gap: 15px;
              ">
                <div style="font-size: 24px;">💬</div>
                <div>Ready to chat with AI</div>
                <div style="font-size: 12px; color: #aaa;">For ChatGPT/Gemini: Initialize browser session first</div>
                <button id="text-init-browser-btn" style="
                  background: #00d4aa;
                  color: #000;
                  border: none;
                  padding: 10px 20px;
                  border-radius: 6px;
                  cursor: pointer;
                  font-weight: 500;
                  font-size: 13px;
                  display: none;
                ">Initialize Browser Session</button>
              </div>
            </div>
          </div>

          <!-- Iframe Mode Container -->
          <div id="iframe-mode-container" style="flex: 1; display: none; flex-direction: column; min-height: 0;">
            <div id="iframe-container" style="
              flex: 1;
              background: #2d2d2d;
              border-radius: 8px;
              padding: 10px;
              margin-bottom: 15px;
              min-height: 400px;
            ">
              <iframe id="web-iframe" 
                      src="" 
                      style="
                        width: 100%; 
                        height: 100%; 
                        border: none; 
                        border-radius: 6px;
                        background: white;
                        overflow: auto;
                      ">
              </iframe>
            </div>
          </div>
        </div>

        <!-- Send Query at Bottom - Fixed -->
        <div style="flex-shrink: 0; margin-top: 10px; margin-bottom: 0;">
          <div id="turn-counter" style="color:#999; font-size: 11px; margin: 0 0 6px 2px;">0/60</div>
          <div style="display: flex; gap: 10px; align-items: center;">
            <input id="chatgpt-query-input" type="text" placeholder="Type your question..." style="
              flex: 1;
              background: #333;
              color: #fff;
              border: 1px solid #555;
              padding: 10px 15px;
              border-radius: 6px;
              font-size: 14px;
            ">
            <button id="chatgpt-mic-btn" title="Toggle microphone mode" style="
              background: #333;
              color: #fff;
              border: 1px solid #555;
              padding: 10px 14px;
              border-radius: 6px;
              cursor: pointer;
              font-size: 16px;
              display: flex;
              align-items: center;
              justify-content: center;
              transition: all 0.2s ease;
            ">🎤</button>
            <button id="chatgpt-send-btn" style="
              background: #00d4aa;
              color: #000;
              border: none;
              padding: 10px 20px;
              border-radius: 6px;
              cursor: pointer;
              font-weight: 500;
              font-size: 14px;
            ">Send</button>
          </div>
        </div>
      </div>
    `;

    document.body.appendChild(this.container);
    // Make widget globally accessible for error buttons
    window.chatWidget = this;
    this.setupEventListeners();
    
    // Initialize the UI state based on default model
    this.onModelChanged();
  }

  setupEventListeners() {
    this.queryInput = this.container.querySelector('#chatgpt-query-input');
    this.sendBtn = this.container.querySelector('#chatgpt-send-btn');
    this.micBtn = this.container.querySelector('#chatgpt-mic-btn');
    this.quickButtons = Array.from(this.container.querySelectorAll('.chatgpt-quick-btn') || []);
    if (this.queryInput) {
      this.defaultPlaceholder =
        this.queryInput.getAttribute('placeholder') || this.defaultPlaceholder;
    }

    // Close button with hover effects
    const closeBtn = this.container.querySelector('#chatgpt-close-btn');
    closeBtn.addEventListener('click', () => this.hide());
    closeBtn.addEventListener('mouseenter', () => {
      closeBtn.style.background = '#333';
      closeBtn.style.color = '#fff';
    });
    closeBtn.addEventListener('mouseleave', () => {
      closeBtn.style.background = 'none';
      closeBtn.style.color = '#888';
    });

    // New Session button
    const newSessionBtn = this.container.querySelector('#new-session-btn');
    if (newSessionBtn) {
      newSessionBtn.addEventListener('click', () => this.startNewSession());
    }

    // Model selector
    const modelSelector = this.container.querySelector('#model-selector');
    modelSelector.addEventListener('change', (e) => {
      this.selectedModel = e.target.value;
      this.onModelChanged();
    });

    // Text mode initialize browser button
    const textInitBtn = this.container.querySelector('#text-init-browser-btn');
    textInitBtn.addEventListener('click', () => this.initializeBrowserSession());

    if (this.sendBtn) {
      this.sendBtn.addEventListener('click', () => {
        if (!this.queryInput) return;
        const query = this.queryInput.value.trim();
        if (query) {
          this.sendQuery(query);
          this.queryInput.value = '';
        }
      });
    }

    if (this.micBtn) {
      this.micBtn.addEventListener('click', () => this.handleMicButtonClick());
    }

    if (this.queryInput) {
      this.queryInput.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' && !event.shiftKey) {
          event.preventDefault();
          const query = this.queryInput.value.trim();
          if (query) {
            this.sendQuery(query);
            this.queryInput.value = '';
          }
        }
      });
    }

    this.quickButtons.forEach((btn) => {
      btn.addEventListener('click', async () => {
        const query = btn.dataset.query;
        if (query === 'Clear conversation') {
          await this.clearChatInBrowser();
        } else {
          this.sendQuery(query);
        }
      });
    });

    const textModeBtn = this.container.querySelector('#text-mode-btn');
    const iframeModeBtn = this.container.querySelector('#iframe-mode-btn');

    textModeBtn.addEventListener('click', () => this.switchDisplayMode('text'));
    iframeModeBtn.addEventListener('click', () => this.switchDisplayMode('iframe'));

    window.addEventListener('ada2:voice-connected', this.handleVoiceConnected);
    window.addEventListener('ada2:voice-disconnected', this.handleVoiceDisconnected);
    window.addEventListener('ada2:mic-muted', this.handleMicMuted);

    if (window.avatarVoiceChat && window.avatarVoiceChat.isConnected) {
      const muted = Boolean(window.avatarVoiceChat.isMicMuted);
      this.onVoiceConnected({ detail: { muted } });
    } else {
      this.micAvailable = false;
      this.micMuted = false;
      this.updateMicButtonState();
    }
  }

  show() {
    this.container.style.display = 'block';
    this.isVisible = true;
    document.body.classList.add('widget-visible');
    
    // Load global conversation history if widget hasn't been synced yet
    if (window.globalConversationHistory && window.globalConversationHistory.length > this.conversationHistory.length) {
      this.conversationHistory = [...window.globalConversationHistory];
      this.updateConversationDisplay();
    }
    
    // Trigger reflow and animation
    setTimeout(() => {
      this.container.style.transform = 'translateX(0)';
    }, 10);
  }

  hide() {
    document.body.classList.remove('widget-visible');
    this.container.style.transform = 'translateX(100%)';
    
    // Clean up text highlighter
    if (this.currentTextHighlighter) {
      this.currentTextHighlighter.reset();
      this.currentTextHighlighter = null;
    }
    
    setTimeout(() => {
      this.container.style.display = 'none';
      this.isVisible = false;
    }, 300);

    // Notify widget manager
    if (window.widgetManager) {
      window.widgetManager.widgetClosed('chat');
    }
  }

  toggle() {
    if (this.isVisible) {
      this.hide();
    } else {
      this.show();
    }
  }

  handleMicButtonClick() {
    if (!this.micBtn) return;
    // If voice chat is not connected yet, clicking the mic should connect.
    const av = window.avatarVoiceChat;
    if (!av || !av.isConnected) {
      try { if (av && typeof av.connect === 'function') { av.connect(); } } catch(_) {}
      return;
    }
    // Sync local state with avatar, then toggle
    try { this.micMuted = !!av.isMicMuted; } catch(_) {}
    if (typeof av.toggleMicMuted === 'function') {
      av.toggleMicMuted();
    }
    try { this.micMuted = !!av.isMicMuted; } catch(_) {}
    this.updateMicButtonState();
  }

  onVoiceConnected(event) {
    this.micAvailable = true;
    const muted = event && event.detail && typeof event.detail.muted === 'boolean'
      ? event.detail.muted
      : false;
    this.micMuted = muted;
    this.updateMicButtonState();
  }

  onVoiceDisconnected() {
    this.micAvailable = false;
    this.micMuted = false;
    this.updateMicButtonState();
    // Reset counter when a session fully disconnects
    this.turnPairs = 0;
    this.updateTurnCounter();
  }

  onMicMuted(event) {
    if (event && event.detail && typeof event.detail.muted === 'boolean') {
      this.micMuted = event.detail.muted;
    }
    const connected = window.avatarVoiceChat && window.avatarVoiceChat.isConnected;
    this.micAvailable = Boolean(connected);
    this.updateMicButtonState();
  }

  updateMicButtonState() {
    if (!this.micBtn) return;
    const av = window.avatarVoiceChat;
    const connected = !!(av && av.isConnected);
    if (!connected) {
      // Not connected: button acts as Connect
      this.micBtn.disabled = false;
      this.micBtn.style.opacity = '1';
      this.micBtn.style.background = '#333';
      this.micBtn.style.color = '#fff';
      this.micBtn.textContent = '🎤';
      this.micBtn.title = 'Click to connect voice chat';
      return;
    }
    // Connected: color reflects mute state
    try { this.micMuted = !!av.isMicMuted; } catch(_) {}
    this.micBtn.disabled = false;
    this.micBtn.style.opacity = '1';
    if (this.micMuted) {
      // Muted: amber and mute icon
      this.micBtn.style.background = '#ffbc42';
      this.micBtn.style.color = '#000';
      this.micBtn.textContent = '🔇';
      this.micBtn.title = 'Microphone muted – click to unmute';
    } else {
      // Unmuted: green and mic icon
      this.micBtn.style.background = '#00d4aa';
      this.micBtn.style.color = '#000';
      this.micBtn.textContent = '🎤';
      this.micBtn.title = 'Microphone active – click to mute';
    }
  }

  showLocalWebViewMessage() {
    const iframeContainer = this.container.querySelector('#iframe-container');
    
    iframeContainer.innerHTML = `
      <div style="
        display: flex;
        align-items: center;
        justify-content: center;
        height: 100%;
        color: #ddd;
        text-align: center;
        font-size: 14px;
        flex-direction: column;
        gap: 15px;
      ">
        <div style="font-size: 24px;">💬</div>
        <div>Local AI Web View</div>
        <div style="font-size: 12px; color: #aaa;">Web view is not available for Local AI. Use text chat mode instead.</div>
      </div>
    `;
  }

  showWebViewInitializeOption(model) {
    const iframeContainer = this.container.querySelector('#iframe-container');
    
    const modelInfo = {
      'chatgpt': { name: 'ChatGPT', icon: '🤖' },
      'gemini': { name: 'Gemini', icon: '✨' }
    };

    const info = modelInfo[model];
    
    // Always show initialize option - initialization will automatically start live browser view
    iframeContainer.innerHTML = `
      <div style="
        display: flex;
        align-items: center;
        justify-content: center;
        height: 100%;
        color: #ddd;
        text-align: center;
        font-size: 14px;
        flex-direction: column;
        gap: 15px;
      ">
        <div style="font-size: 24px;">${info.icon}</div>
        <div>Ready to chat with ${info.name}</div>
        <div style="font-size: 12px; color: #aaa;">Initialize browser session first</div>
        <button id="web-init-browser-btn" style="
          background: #00d4aa;
          color: #000;
          border: none;
          padding: 10px 20px;
          border-radius: 6px;
          cursor: pointer;
          font-weight: 500;
          font-size: 13px;
        ">Initialize Browser Session</button>
      </div>
    `;
    
    // Add event listener for the initialize browser button
    const initBtn = iframeContainer.querySelector('#web-init-browser-btn');
    initBtn.addEventListener('click', () => {
      this.initializeBrowserSession();
    });
  }

  switchDisplayMode(mode) {
    this.displayMode = mode;
    
    const textModeBtn = this.container.querySelector('#text-mode-btn');
    const iframeModeBtn = this.container.querySelector('#iframe-mode-btn');
    const textContainer = this.container.querySelector('#text-mode-container');
    const iframeContainer = this.container.querySelector('#iframe-mode-container');
    const conversationTitle = this.container.querySelector('#conversation-title');
    const textInitBtn = this.container.querySelector('#text-init-browser-btn');

    if (mode === 'text') {
      // Update button styles
      textModeBtn.style.background = '#00d4aa';
      textModeBtn.style.color = '#000';
      textModeBtn.classList.add('active');
      
      iframeModeBtn.style.background = '#333';
      iframeModeBtn.style.color = '#fff';
      iframeModeBtn.classList.remove('active');

      // Show/hide containers
      textContainer.style.display = 'flex';
      iframeContainer.style.display = 'none';
      conversationTitle.textContent = 'Conversation History';
      
      
    } else if (mode === 'iframe') {
      // Update button styles
      iframeModeBtn.style.background = '#00d4aa';
      iframeModeBtn.style.color = '#000';
      iframeModeBtn.classList.add('active');
      
      textModeBtn.style.background = '#333';
      textModeBtn.style.color = '#fff';
      textModeBtn.classList.remove('active');

      // Show/hide containers
      textContainer.style.display = 'none';
      iframeContainer.style.display = 'flex';
      conversationTitle.textContent = 'Web View';
      
      
      // For ChatGPT/Gemini, use live browser view; for local, show appropriate message
      if (this.selectedModel === 'local') {
        this.showLocalWebViewMessage();
      } else {
        // Show ready state with initialize option
        this.showWebViewInitializeOption(this.selectedModel);
      }
    }
  }

  loadIframeForModel() {
    const iframe = this.container.querySelector('#web-iframe');
    const iframeContainer = this.container.querySelector('#iframe-container');
    
    // Reset iframe container to show iframe
    iframeContainer.innerHTML = `
      <iframe id="web-iframe" 
              src="" 
              style="
                width: 100%; 
                height: 100%; 
                border: none; 
                border-radius: 6px;
                background: white;
                overflow: auto;
              ">
      </iframe>
      <div id="iframe-fallback" style="display: none;">
        <div style="
          display: flex;
          align-items: center;
          justify-content: center;
          height: 100%;
          color: #666;
          text-align: center;
          font-size: 14px;
          flex-direction: column;
          gap: 15px;
        ">
          <div style="font-size: 18px;">🚫</div>
          <div>
            <div style="margin-bottom: 10px; font-weight: 500;">Site blocked iframe access</div>
            <div id="fallback-message"></div>
          </div>
          <button id="open-external-btn" style="
            background: #00d4aa;
            color: #000;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            cursor: pointer;
            font-weight: 500;
          ">Open in New Tab</button>
        </div>
      </div>
    `;
    
    const newIframe = iframeContainer.querySelector('#web-iframe');
    const fallback = iframeContainer.querySelector('#iframe-fallback');
    const fallbackMessage = iframeContainer.querySelector('#fallback-message');
    const openExternalBtn = iframeContainer.querySelector('#open-external-btn');
    
    let targetUrl = '';
    let fallbackText = '';
    
    switch(this.selectedModel) {
      case 'chatgpt':
        // Most AI sites block iframe embedding for security
        this.showEmbeddingAlternatives('chatgpt');
        return;
      case 'gemini':
        // Google services typically block iframe embedding
        this.showEmbeddingAlternatives('gemini');
        return;
      case 'local':
        // For local AI, show a message that iframe mode isn't available
        fallback.style.display = 'flex';
        newIframe.style.display = 'none';
        fallbackMessage.textContent = 'Web view is not available for Local AI. Use text chat mode instead.';
        openExternalBtn.style.display = 'none';
        return;
    }
    
    // Set up iframe error handling
    const timeoutId = setTimeout(() => {
      // If iframe doesn't load within 5 seconds, show fallback
      this.showIframeFallback(targetUrl, fallbackText);
    }, 5000);
    
    newIframe.onload = () => {
      clearTimeout(timeoutId);
      try {
        // Try to access iframe content to see if it loaded properly
        newIframe.contentDocument;
        // If we get here, iframe loaded successfully
      } catch (e) {
        // Cross-origin error means the site loaded but blocks iframe access
        this.showIframeFallback(targetUrl, fallbackText);
      }
    };
    
    newIframe.onerror = () => {
      clearTimeout(timeoutId);
      this.showIframeFallback(targetUrl, fallbackText);
    };
    
    // Set up external link button
    openExternalBtn.onclick = () => {
      window.open(targetUrl, '_blank');
    };
    
    // Load the URL
    newIframe.src = targetUrl;
  }
  
  showEmbeddingAlternatives(model) {
    const iframeContainer = this.container.querySelector('#iframe-container');
    
    const modelInfo = {
      'chatgpt': { name: 'ChatGPT', icon: '🤖' },
      'gemini': { name: 'Gemini', icon: '✨' }
    };

    const info = modelInfo[model];
    
    // Show initialization message
    iframeContainer.innerHTML = `
      <div style="
        display: flex;
        align-items: center;
        justify-content: center;
        height: 100%;
        color: #ddd;
        text-align: center;
        font-size: 14px;
        flex-direction: column;
        gap: 15px;
      ">
        <div style="font-size: 24px;">⚡</div>
        <div>Auto-initializing ${info.name} browser session...</div>
        <div style="font-size: 12px; color: #aaa;">This may take a moment</div>
      </div>
    `;
    
    // Automatically start the browser session
    setTimeout(() => {
      this.startLiveBrowserView(model);
    }, 500);
  }

  async startLiveBrowserView(model) {
    const iframeContainer = this.container.querySelector('#iframe-container');
    
    // Show initializing state
    iframeContainer.innerHTML = `
      <div style="
        display: flex;
        align-items: center;
        justify-content: center;
        height: 100%;
        color: #ddd;
        text-align: center;
        font-size: 14px;
        flex-direction: column;
        gap: 15px;
      ">
        <div style="font-size: 24px;">⚡</div>
        <div>Initializing ${model === 'chatgpt' ? 'ChatGPT' : 'Gemini'} browser session...</div>
        <div style="font-size: 12px; color: #aaa;">This may take a moment</div>
      </div>
    `;
    
    try {
      // Initialize browser session first
      const initEndpoint = model === 'chatgpt' ? '/api/chatgpt/initialize' : '/api/gemini/initialize';
      const initResponse = await fetch(initEndpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      const initData = await initResponse.json();
      
      if (!initData.success) {
        throw new Error(initData.error || 'Failed to initialize browser session');
      }
      
      // Start live browser view
      this.setupLiveBrowserView(model);
      
    } catch (error) {
      console.error('Error starting browser view:', error);
      iframeContainer.innerHTML = `
        <div style="
          display: flex;
          align-items: center;
          justify-content: center;
          height: 100%;
          color: #ff6b6b;
          text-align: center;
          font-size: 14px;
          flex-direction: column;
          gap: 15px;
        ">
          <div style="font-size: 24px;">❌</div>
          <div>Failed to start browser session</div>
          <div style="font-size: 12px; color: #aaa;">${error.message}</div>
          <button onclick="window.chatWidget.switchDisplayMode('text')" style="
            background: #555;
            color: #fff;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
          ">← Back to Text Chat</button>
        </div>
      `;
    }
  }

  setupLiveBrowserView(model) {
    const iframeContainer = this.container.querySelector('#iframe-container');
    this.browserModel = model;
    
    iframeContainer.innerHTML = `
      <div style="height: 100%; display: flex; flex-direction: column; position: relative;">
        <!-- Browser Screenshot Display -->
        <div id="browser-screenshot-container" style="
          flex: 1;
          background: #1a1a1a;
          border-radius: 6px 6px 0 0;
          position: relative;
          overflow: hidden;
          cursor: grab;
          user-select: none;
        ">
          <img id="browser-screenshot" 
               style="
                 position: absolute;
                 top: 0;
                 left: 0;
                 transform-origin: 0 0;
                 transition: transform 0.1s ease;
                 border-radius: 6px;
               "
               alt="Browser view"
               draggable="false">
          
          <!-- Loading overlay -->
          <div id="screenshot-loading" style="
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            color: #aaa;
            font-size: 14px;
            text-align: center;
          ">
            <div style="margin-bottom: 10px;">📸</div>
            <div>Loading browser view...</div>
          </div>
        </div>
        
      </div>
    `;

    // Set up event listeners
    const screenshotContainer = iframeContainer.querySelector('#browser-screenshot-container');

    // Initialize transform properties
    this.scale = 1;
    this.translateX = 0;
    this.translateY = 0;
    this.isDragging = false;
    this.startX = 0;
    this.startY = 0;
    this.dragThreshold = 10;
    
    // Touch properties for pinch zoom
    this.touches = [];
    this.lastTouchDistance = 0;
    this.pinchStartScale = 1;

    // Click handler
    screenshotContainer.addEventListener('click', async (e) => {
      if (!this.isDragging) {
        await this.handleBrowserClick(e);
      }
    });

    // Mouse drag for pan
    screenshotContainer.addEventListener('mousedown', (e) => {
      if (e.button === 0) {
        this.isDragging = false;
        this.startX = e.clientX - this.translateX;
        this.startY = e.clientY - this.translateY;
        screenshotContainer.style.cursor = 'grabbing';
      }
    });

    screenshotContainer.addEventListener('mousemove', (e) => {
      if (e.buttons === 1) { // Left button held
        const deltaX = Math.abs(e.clientX - this.startX - this.translateX);
        const deltaY = Math.abs(e.clientY - this.startY - this.translateY);
        
        if (deltaX > this.dragThreshold || deltaY > this.dragThreshold) {
          this.isDragging = true;
        }
        
        if (this.isDragging) {
          this.translateX = e.clientX - this.startX;
          this.translateY = e.clientY - this.startY;
          this.updateTransform();
        }
      }
    });

    screenshotContainer.addEventListener('mouseup', () => {
      screenshotContainer.style.cursor = 'default';
      // Don't reset isDragging immediately to prevent click after drag
      setTimeout(() => { this.isDragging = false; }, 50);
    });

    screenshotContainer.addEventListener('mouseleave', () => {
      screenshotContainer.style.cursor = 'default';
    });

    // Mouse wheel for zoom and scroll
    screenshotContainer.addEventListener('wheel', (e) => {
      e.preventDefault();
      
      if (e.ctrlKey || e.metaKey) {
        // Zoom mode with Ctrl/Cmd
        const rect = screenshotContainer.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;
        
        // Much slower zoom speed (25x slower total)
        const zoomFactor = e.deltaY > 0 ? 0.996 : 1.004;
        const newScale = Math.max(0.5, Math.min(3, this.scale * zoomFactor));
        
        // Zoom toward mouse cursor
        const scaleChange = newScale / this.scale;
        this.translateX = mouseX - (mouseX - this.translateX) * scaleChange;
        this.translateY = mouseY - (mouseY - this.translateY) * scaleChange;
        this.scale = newScale;
        
        this.updateTransform();
      } else {
        // Scroll mode
        const rect = screenshotContainer.getBoundingClientRect();
        const mouseX = (e.clientX - rect.left - this.translateX) / this.scale;
        const mouseY = (e.clientY - rect.top - this.translateY) / this.scale;
        
        const img = screenshotContainer.querySelector('#browser-screenshot');
        if (img && img.naturalWidth && img.naturalHeight) {
          const actualX = Math.round(mouseX * (img.naturalWidth / img.offsetWidth));
          const actualY = Math.round(mouseY * (img.naturalHeight / img.offsetHeight));
          
          // Send scroll with smoother scrolling (amplify scroll delta)
          const smoothScrollX = e.deltaX * 2;
          const smoothScrollY = e.deltaY * 2;
        this.scrollBrowserAt(actualX, actualY, smoothScrollX, smoothScrollY);
        }
      }
    });

    // Touch events for pinch zoom and pan
    screenshotContainer.addEventListener('touchstart', (e) => {
      this.touches = Array.from(e.touches);
      
      if (e.touches.length === 1) {
        // Single touch - potential pan
        const touch = e.touches[0];
        this.startX = touch.clientX - this.translateX;
        this.startY = touch.clientY - this.translateY;
        this.isDragging = false;
      } else if (e.touches.length === 2) {
        // Two touches - pinch zoom
        const touch1 = e.touches[0];
        const touch2 = e.touches[1];
        this.lastTouchDistance = Math.sqrt(
          Math.pow(touch2.clientX - touch1.clientX, 2) +
          Math.pow(touch2.clientY - touch1.clientY, 2)
        );
        this.pinchStartScale = this.scale;
      }
      e.preventDefault();
    });

    screenshotContainer.addEventListener('touchmove', (e) => {
      if (e.touches.length === 1 && this.touches.length === 1) {
        // Single touch pan
        const touch = e.touches[0];
        const deltaX = Math.abs(touch.clientX - this.startX - this.translateX);
        const deltaY = Math.abs(touch.clientY - this.startY - this.translateY);
        
        if (deltaX > this.dragThreshold || deltaY > this.dragThreshold) {
          this.isDragging = true;
        }
        
        if (this.isDragging) {
          this.translateX = touch.clientX - this.startX;
          this.translateY = touch.clientY - this.startY;
          this.updateTransform();
        }
      } else if (e.touches.length === 2) {
        // Two touch pinch zoom
        const touch1 = e.touches[0];
        const touch2 = e.touches[1];
        const currentDistance = Math.sqrt(
          Math.pow(touch2.clientX - touch1.clientX, 2) +
          Math.pow(touch2.clientY - touch1.clientY, 2)
        );
        
        if (this.lastTouchDistance > 0) {
          // Make pinch zoom 25x slower total (5x slower than before)
          const rawScale = currentDistance / this.lastTouchDistance;
          const dampedScale = 1 + (rawScale - 1) * 0.04; // 25x slower total
          const newScale = Math.max(0.5, Math.min(3, this.scale * dampedScale));
          
          // Get pinch center
          const rect = screenshotContainer.getBoundingClientRect();
          const centerX = (touch1.clientX + touch2.clientX) / 2 - rect.left;
          const centerY = (touch1.clientY + touch2.clientY) / 2 - rect.top;
          
          // Zoom toward pinch center
          const scaleChange = newScale / this.scale;
          this.translateX = centerX - (centerX - this.translateX) * scaleChange;
          this.translateY = centerY - (centerY - this.translateY) * scaleChange;
          this.scale = newScale;
          
          this.updateTransform();
        }
      }
      e.preventDefault();
    });

    screenshotContainer.addEventListener('touchend', async (e) => {
      if (e.touches.length === 0) {
        // All touches ended
        if (e.changedTouches.length === 1 && !this.isDragging) {
          // Single tap - interact with browser
          await this.handleBrowserClick(e.changedTouches[0]);
        }
        // Reset state
        this.isDragging = false;
        this.lastTouchDistance = 0;
        this.pinchStartScale = this.scale;
      }
      this.touches = Array.from(e.touches);
    });

    // Auto-refresh functionality (no manual button needed)

    // Start refreshing
    this.startBrowserRefresh();
  }

  async refreshBrowserView() {
    if (!this.browserModel) return;
    
    try {
      const response = await fetch(`/api/browser/screenshot/${this.browserModel}`);
      const data = await response.json();
      
      if (data.success) {
        const img = document.querySelector('#browser-screenshot');
        const loading = document.querySelector('#screenshot-loading');
        
        if (img) {
          img.src = data.screenshot;
          img.onload = () => {
            if (loading) loading.style.display = 'none';
            // Apply current transform
            this.updateTransform();
          };
        }
      }
    } catch (error) {
      console.error('Error refreshing browser view:', error);
    }
  }

  async clickBrowserCoordinates(x, y) {
    if (!this.browserModel) return;
    
    try {
      await fetch(`/api/browser/click/${this.browserModel}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ x, y })
      });
    } catch (error) {
      console.error('Error clicking browser coordinates:', error);
    }
  }

  async typeBrowserText(text) {
    if (!this.browserModel) return;
    
    try {
      await fetch(`/api/browser/type/${this.browserModel}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text })
      });
    } catch (error) {
      console.error('Error typing browser text:', error);
    }
  }

  async scrollBrowserAt(x, y, deltaX, deltaY) {
    if (!this.browserModel) return;
    
    try {
      await fetch(`/api/browser/scroll/${this.browserModel}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ x, y, deltaX, deltaY })
      });
    } catch (error) {
      console.error('Error scrolling browser:', error);
    }
  }

  updateTransform() {
    const img = document.querySelector('#browser-screenshot');
    if (img) {
      img.style.transform = `translate(${this.translateX}px, ${this.translateY}px) scale(${this.scale})`;
      img.style.transformOrigin = '0 0';
    }
  }

  async handleBrowserClick(e) {
    const rect = e.currentTarget.getBoundingClientRect();
    // Apply inverse transform to get actual click position
    const x = (e.clientX - rect.left - this.translateX) / this.scale;
    const y = (e.clientY - rect.top - this.translateY) / this.scale;
    
    // Convert to browser coordinates
    const img = document.querySelector('#browser-screenshot');
    if (img && img.naturalWidth && img.naturalHeight) {
      const actualX = Math.round(x * (img.naturalWidth / img.offsetWidth));
      const actualY = Math.round(y * (img.naturalHeight / img.offsetHeight));
      
      await this.clickBrowserCoordinates(actualX, actualY);
      setTimeout(() => this.refreshBrowserView(), 500);
    }
  }

  startBrowserRefresh() {
    if (this.browserRefreshInterval) {
      clearInterval(this.browserRefreshInterval);
    }
    
    // Initial load
    this.refreshBrowserView();
    
    // Auto-refresh every 100ms for smooth scrolling
    this.browserRefreshInterval = setInterval(() => {
      this.refreshBrowserView();
    }, 150);
  }

  stopLiveBrowserView() {
    if (this.browserRefreshInterval) {
      clearInterval(this.browserRefreshInterval);
      this.browserRefreshInterval = null;
    }
    this.browserModel = null;
  }

  attemptDirectEmbedding(url) {
    // This method is no longer used but kept for compatibility
    console.log('Direct embedding deprecated, use live browser view instead');
  }

  showIframeFallback(url, message) {
    const iframeContainer = this.container.querySelector('#iframe-container');
    const iframe = iframeContainer.querySelector('#web-iframe');
    const fallback = iframeContainer.querySelector('#iframe-fallback');
    const fallbackMessage = iframeContainer.querySelector('#fallback-message');
    const openExternalBtn = iframeContainer.querySelector('#open-external-btn');
    
    if (iframe) iframe.style.display = 'none';
    if (fallback) {
      fallback.style.display = 'flex';
      fallbackMessage.textContent = message;
      
      openExternalBtn.onclick = () => {
        window.open(url, '_blank');
      };
    }
  }

  onModelChanged() {
    // Update title based on selected model
    const title = this.container.querySelector('#chat-title');
    const textInitBtn = this.container.querySelector('#text-init-browser-btn');
    const textPlaceholder = this.container.querySelector('#text-chat-placeholder');
    const iframeModeBtn = this.container.querySelector('#iframe-mode-btn');
    
    switch(this.selectedModel) {
      case 'local':
        title.textContent = 'Local AI Chat';
        // Hide init button and Web View button for local AI
        if (textInitBtn) textInitBtn.style.display = 'none';
        if (iframeModeBtn) iframeModeBtn.style.display = 'none';
        if (textPlaceholder) {
          textPlaceholder.querySelector('div:nth-child(2)').textContent = 'Ready to chat with Local AI';
          textPlaceholder.querySelector('div:nth-child(3)').textContent = 'Start typing your question below';
        }
        // Switch back to text mode if currently in iframe mode
        if (this.displayMode === 'iframe') {
          this.switchDisplayMode('text');
        }
        break;
      case 'chatgpt':
        title.textContent = 'ChatGPT Chat';
        // Show init button and Web View button for ChatGPT
        if (textInitBtn) textInitBtn.style.display = 'inline-block';
        if (iframeModeBtn) iframeModeBtn.style.display = 'inline-block';
        if (textPlaceholder) {
          textPlaceholder.querySelector('div:nth-child(2)').textContent = 'Ready to chat with ChatGPT';
          textPlaceholder.querySelector('div:nth-child(3)').textContent = 'Initialize browser session first';
        }
        break;
      case 'gemini':
        title.textContent = 'Gemini Chat';
        // Show init button and Web View button for Gemini
        if (textInitBtn) textInitBtn.style.display = 'inline-block';
        if (iframeModeBtn) iframeModeBtn.style.display = 'inline-block';
        if (textPlaceholder) {
          textPlaceholder.querySelector('div:nth-child(2)').textContent = 'Ready to chat with Gemini';
          textPlaceholder.querySelector('div:nth-child(3)').textContent = 'Initialize browser session first';
        }
        break;
    }
    
    // Update iframe if in iframe mode
    if (this.displayMode === 'iframe') {
      this.loadIframeForModel();
    }
    
    // Clear conversation when switching models
    this.clearConversation();
  }

  updateStatus(status, text) {
    this.browserStatus = status;
    const textInitBtn = this.container.querySelector('#text-init-browser-btn');
    const textPlaceholder = this.container.querySelector('#text-chat-placeholder');
    const webInitBtn = this.container.querySelector('#web-init-browser-btn');

    // Update the text initialization button state
    if (this.selectedModel !== 'local') {
      switch(status) {
        case 'connected':
          if (textInitBtn) textInitBtn.style.display = 'none';
          if (textPlaceholder && textPlaceholder.querySelector('div:nth-child(3)')) {
            textPlaceholder.querySelector('div:nth-child(3)').textContent = 'Browser session ready - start chatting!';
          }
          break;
        case 'connecting':
          if (textInitBtn) {
            textInitBtn.textContent = 'Connecting...';
            textInitBtn.disabled = true;
          }
          if (webInitBtn) {
            webInitBtn.textContent = 'Connecting...';
            webInitBtn.disabled = true;
          }
          break;
        case 'error':
          if (textInitBtn) {
            textInitBtn.textContent = 'Initialize Browser Session';
            textInitBtn.disabled = false;
            textInitBtn.style.display = 'inline-block';
          }
          if (webInitBtn) {
            webInitBtn.textContent = 'Initialize Browser Session';
            webInitBtn.disabled = false;
          }
          if (textPlaceholder && textPlaceholder.querySelector('div:nth-child(3)')) {
            textPlaceholder.querySelector('div:nth-child(3)').textContent = 'Connection failed - try initializing again';
          }
          break;
        default:
          if (textInitBtn) {
            textInitBtn.textContent = 'Initialize Browser Session';
            textInitBtn.disabled = false;
            textInitBtn.style.display = 'inline-block';
          }
          if (webInitBtn) {
            webInitBtn.textContent = 'Initialize Browser Session';
            webInitBtn.disabled = false;
          }
          if (textPlaceholder && textPlaceholder.querySelector('div:nth-child(3)')) {
            textPlaceholder.querySelector('div:nth-child(3)').textContent = 'Initialize browser session first';
          }
      }
    }
  }

  async initializeBrowserSession() {
    if (this.isInitializing || this.selectedModel === 'local') return;
    
    this.isInitializing = true;
    this.updateStatus('connecting', 'Initializing browser...');

    try {
      const endpoint = this.selectedModel === 'chatgpt' ? '/api/chatgpt/initialize' : '/api/gemini/initialize';
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });

      const data = await response.json();
      
      if (data.success) {
        this.updateStatus('connected', 'Browser Ready');
        this.addToConversation('system', `${this.selectedModel} browser session initialized successfully`);
        
        // If we're in Web View mode, automatically start the live browser view
        if (this.displayMode === 'iframe') {
          setTimeout(() => {
            this.startLiveBrowserView(this.selectedModel);
          }, 500);
        }
      } else {
        throw new Error(data.error || 'Failed to initialize');
      }
    } catch (error) {
      this.updateStatus('error', 'Initialization failed');
      this.addToConversation('system', `Error: ${error.message}`);
    } finally {
      this.isInitializing = false;
    }
  }

  async sendQuery(query) {
    // Add user query to conversation
    this.addToConversation('user', query);

    try {
      // Show thinking icon using the global UI state system
      this.showThinkingState();

      if (this.selectedModel === 'local') {
        await this.sendLocalQuery(query);
      } else if (this.selectedModel === 'chatgpt') {
        await this.sendChatGPTQuery(query);
      } else if (this.selectedModel === 'gemini') {
        await this.sendGeminiQuery(query);
      }
      
    } catch (error) {
      this.addToConversation('system', `Error: ${error.message}`);
      this.hideThinkingState();
    }
  }

  async sendLocalQuery(query) {
    try {
      // Route to local pipeline (same path used by voice), no streaming here
      const payload = { text: query };
      try {
        if (window.avatarVoiceChat && window.avatarVoiceChat.isConnected && window.avatarVoiceChat.pc_id) {
          payload.pc_id = window.avatarVoiceChat.pc_id;
        } else if (window.readerRTC && window.readerRTC.pc_id) {
          payload.pc_id = window.readerRTC.pc_id;
        }
      } catch(_){}
      const response = await fetch('/api/chat/send', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      // Assistant text will arrive via datachannel (assistant_full_text)
      this.hideThinkingState();
      this.updateStatus('ok', 'Sent to Local AI');
      return;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop();

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const jsonStr = line.substring(6);
              if (jsonStr.trim() === '') continue;
              
              const data = JSON.parse(jsonStr);
              
              if (data.type === 'message' || data.type === 'chunk' || data.type === 'response') {
                if (data.source !== 'user' && data.content?.trim()) {
                  lastAgentResponse = { content: data.content, source: data.source };
                }
              } else if (data.type === 'end') {
                if (lastAgentResponse && lastAgentResponse.content) {
                  this.addToConversation('assistant', lastAgentResponse.content);
                  this.speakResponse(lastAgentResponse.content);
                }
                break;
              }
            } catch (e) {
              // Skip invalid JSON
            }
          }
        }
      }
      
      this.hideThinkingState();
    } catch (error) {
      throw error;
    }
  }

  async sendChatGPTQuery(query) {
    if (this.browserStatus !== 'connected') {
      this.addToConversation('system', 'ChatGPT browser not connected. Please initialize first.');
      return;
    }

    try {
      this.updateStatus('connecting', 'Sending query...');
      
      const response = await fetch('/api/chatgpt/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query })
      });

      const data = await response.json();
      
      if (data.success) {
        this.addToConversation('assistant', data.response);
        this.updateStatus('connected', 'Ready');
        this.hideThinkingState();
        this.speakResponse(data.response);
      } else {
        throw new Error(data.error || 'ChatGPT query failed');
      }
    } catch (error) {
      this.updateStatus('error', 'Query failed');
      throw error;
    }
  }

  async sendGeminiQuery(query) {
    if (this.browserStatus !== 'connected') {
      this.addToConversation('system', 'Gemini browser not connected. Please initialize first.');
      return;
    }

    try {
      this.updateStatus('connecting', 'Sending query...');
      
      const response = await fetch('/api/gemini/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query })
      });

      const data = await response.json();
      
      if (data.success) {
        this.addToConversation('assistant', data.response);
        this.updateStatus('connected', 'Ready');
        this.hideThinkingState();
        this.speakResponse(data.response);
      } else {
        throw new Error(data.error || 'Gemini query failed');
      }
    } catch (error) {
      this.updateStatus('error', 'Query failed');
      throw error;
    }
  }

  addToConversation(role, content) {
    const text = content != null ? String(content) : '';
    if (role === 'assistant') {
      const normalized = text.trim();
      if (!normalized) {
        return;
      }
      if (normalized === this.lastAssistantText) {
        return;
      }
      const lastEntry = this.conversationHistory[this.conversationHistory.length - 1];
      if (lastEntry && lastEntry.role === 'assistant') {
        this.conversationHistory.pop();
      }
      this.conversationHistory.push({
        role: 'assistant',
        content: normalized,
        timestamp: Date.now(),
      });
      this.lastAssistantText = normalized;
      this.awaitingAssistant = false;
      this.updateConversationDisplay();
      // Count one turn (user+assistant) per assistant reply
      this.turnPairs = Math.max(0, (this.turnPairs || 0)) + 1;
      this.updateTurnCounter();
      this.syncSessionIfNeeded();
      return;
    }
    if (role === 'user') {
      this.awaitingAssistant = true;
      this.lastAssistantText = '';
      this.conversationHistory.push({
        role,
        content: text,
        timestamp: Date.now(),
      });
      this.updateConversationDisplay();
      this.updateTurnCounter();
      return;
    }
    this.conversationHistory.push({
      role,
      content: text,
      timestamp: Date.now(),
    });
    this.updateConversationDisplay();
    this.updateTurnCounter();
  }

  // Auto-compact via server when the counter reaches the limit
  async syncSessionIfNeeded() {
    try {
      const cap = Math.max(1, this.turnLimit || 60);
      const val = Math.max(0, this.turnPairs || 0);
      if (val < cap) return;
      // Build sanitized user/assistant turns list
      const turns = (this.conversationHistory || [])
        .filter(m => m && (m.role === 'user' || m.role === 'assistant'))
        .map(m => ({ role: m.role, content: String(m.content || '') }));
      const clientId = (() => { try { return localStorage.getItem('ada2_client_id'); } catch(_) { return null; } })();
      await fetch('/api/session/sync', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ client_id: clientId, turns })
      }).catch(()=>{});
      // Reset counter after compaction
      this.turnPairs = 0;
      this.updateTurnCounter();
    } catch(_) {}
  }

  updateConversationDisplay() {
    const conversationDiv = this.container.querySelector('#chatgpt-conversation');
    const textPlaceholder = this.container.querySelector('#text-chat-placeholder');
    
    if (this.conversationHistory.length === 0) {
      // Show placeholder with appropriate content
      if (textPlaceholder) {
        textPlaceholder.style.display = 'flex';
      }
      if (typeof window !== 'undefined') {
        window.globalConversationHistory = [];
      }
      return;
    } else {
      // Hide placeholder when there are conversations
      if (textPlaceholder) {
        textPlaceholder.style.display = 'none';
      }
    }

    conversationDiv.innerHTML = this.conversationHistory.map((msg, index) => {
      const roleColor = {
        user: '#00d4aa',
        assistant: '#4a9eff', 
        system: '#ffa500'
      }[msg.role] || '#ccc';

      let roleName = 'Unknown';
      if (msg.role === 'user') {
        roleName = 'You';
      } else if (msg.role === 'assistant') {
        switch(this.selectedModel) {
          case 'local': roleName = 'Local AI'; break;
          case 'chatgpt': roleName = 'ChatGPT'; break;
          case 'gemini': roleName = 'Gemini'; break;
          default: roleName = 'AI'; break;
        }
      } else if (msg.role === 'system') {
        roleName = 'System';
      }

      // For assistant messages, create a structure that can be highlighted
      const contentDiv = msg.role === 'assistant' 
        ? `<div class="chat-response-text" data-message-index="${index}" style="color: #ddd; font-size: 14px; line-height: 1.4;">${msg.content || ''}</div>`
        : `<div style="color: #ddd; font-size: 14px; line-height: 1.4;">${msg.content || ''}</div>`;

      return `
        <div style="margin-bottom: 15px; padding-bottom: 15px; border-bottom: 1px solid #3a3a3a;">
          <div style="color: ${roleColor}; font-weight: 500; font-size: 12px; margin-bottom: 5px;">
            ${roleName}
          </div>
          ${contentDiv}
        </div>
      `;
    }).join('');

    // Scroll to bottom
    conversationDiv.scrollTop = conversationDiv.scrollHeight;
    if (typeof window !== 'undefined') {
      window.globalConversationHistory = [...this.conversationHistory];
    }
    const tail = this.conversationHistory[this.conversationHistory.length - 1];
    if (tail && tail.role === 'assistant') {
      this.lastAssistantText = (tail.content || '').trim();
    } else if (!tail) {
      this.lastAssistantText = '';
    }
  }

  clearConversation() {
    this.conversationHistory = [];
    this.lastAssistantText = '';
    this.updateConversationDisplay();
    this.turnPairs = 0;
    this.updateTurnCounter();
  }

  async startNewSession() {
    try {
      const clientId = (() => {
        try { return localStorage.getItem('ada2_client_id'); } catch(_) { return null; } })();
      await fetch('/api/session/clear', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ client_id: clientId })
      });
    } catch(_) {}
    this.clearConversation();
    this.addToConversation('system', '🆕 Started a new session');
  }

  updateTurnCounter() {
    try {
      const el = this.container.querySelector('#turn-counter');
      if (!el) return;
      const val = Math.max(0, this.turnPairs || 0);
      const cap = Math.max(1, this.turnLimit || 60);
      el.textContent = `${val}/${cap}`;
    } catch (_) {}
  }

  speakResponse(text) {
    // Ensure audio context is initialized
    this.initializeAudio();
    
    // Initialize highlighting for the latest assistant response
    this.initializeResponseHighlighting(text);
    
    // Use the unified TTS system to make the avatar speak
    if (window.unifiedTTS && window.unifiedTTS.isReady()) {
      // Clean the text for TTS (remove any unwanted characters)
      const cleanText = this.cleanTTSContent(text);
      
      if (cleanText.length > 0) {
        let sentenceId;
        window.unifiedTTS.speak(cleanText, {
          onsubtitles: (sentence, id, word) => {
            if (id !== sentenceId) {
              sentenceId = id;
              // Clear subtitles when starting new sentence
              const subtitlesElement = document.getElementById('subtitles');
              if (subtitlesElement) {
                subtitlesElement.textContent = '';
              }
            }
            
            // Add word to subtitles (only if word is defined and not empty)
            const subtitlesElement = document.getElementById('subtitles');
            if (subtitlesElement && word && typeof word === 'string' && word.trim() !== '') {
              subtitlesElement.textContent += word;
              subtitlesElement.scrollTop = subtitlesElement.scrollHeight;
            }
          }
        });
      }
    } else {
      console.warn('Unified TTS system not ready');
    }
  }

  /**
   * Initialize highlighting for the most recent assistant response
   * @param {string} responseText - The text that will be spoken
   */
  initializeResponseHighlighting(responseText) {
    // Stop any existing highlighter
    if (this.currentTextHighlighter) {
      this.currentTextHighlighter.reset();
    }
    
    // Find the most recent assistant response element
    const responseElements = this.container.querySelectorAll('.chat-response-text');
    const latestResponse = responseElements[responseElements.length - 1];
    
    if (latestResponse) {
      // Create a new highlighter instance for this response
      this.currentTextHighlighter = new TextHighlighter({
        highlightDelay: 1000,
        enableBookmarks: false,
        enableClickableSegments: false
      });
      
      // Initialize text highlighting for this response
      this.currentTextHighlighter.initializeTextStructure(latestResponse, responseText);
      
      // Start monitoring subtitles for highlighting
      const subtitlesElement = document.getElementById('subtitles');
      if (subtitlesElement) {
        this.currentTextHighlighter.startSubtitleMonitoring(subtitlesElement);
      }
    }
  }

  initializeAudio() {
    // Use the same audio initialization function from main.js
    if (typeof window.head !== 'undefined' && window.head && window.head.audioCtx) {
      if (window.head.audioCtx.state === 'suspended') {
        window.head.audioCtx.resume().then(() => {
        });
      }
    }
  }

  showThinkingState() {
    // Use the global UI state system to show thinking icon
    if (typeof window.updateUIState === 'function' && typeof window.stopTalking === 'function') {
      window.updateUIState(true, false, window.stopTalking);
    }
  }

  hideThinkingState() {
    // Use the global UI state system to hide thinking icon
    if (typeof window.updateUIState === 'function' && typeof window.stopTalking === 'function') {
      window.updateUIState(false, false, window.stopTalking);
    }
  }

  async clearChatInBrowser() {
    try {
      // Only works for ChatGPT and Gemini models, not local
      if (this.selectedModel === 'local') {
        // For local model, just clear the conversation display
        this.clearConversation();
        return;
      }

      const response = await fetch(`/api/browser/new-chat/${this.selectedModel}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      
      const data = await response.json();
      
      if (data.success) {
        // Clear our conversation display too
        this.clearConversation();
        this.addToConversation('system', `✅ Successfully started new chat in ${this.selectedModel === 'chatgpt' ? 'ChatGPT' : 'Gemini'}`);
        
        // Refresh the browser view if we're in web view mode
        if (this.displayMode === 'iframe') {
          setTimeout(() => this.refreshBrowserView(), 1000);
        }
      } else {
        this.addToConversation('system', `❌ Failed to clear chat: ${data.error}`);
        console.error('Failed to clear chat in browser:', data.error);
      }
    } catch (error) {
      this.addToConversation('system', `❌ Error clearing chat: ${error.message}`);
      console.error('Error clearing chat in browser:', error);
    }
  }

  cleanTTSContent(content) {
    if (!content) return '';
    
    // Remove common termination strings that shouldn't be spoken
    const terminationStrings = [
      'TERMINATE',
      '\\[TERMINATE\\]', 
      '\\*\\*TERMINATE\\*\\*',
      'END_OF_RESPONSE',
      '\\[END_OF_RESPONSE\\]',
      '\\*\\*END_OF_RESPONSE\\*\\*'
    ];
    
    let cleanContent = content;
    
    // Remove termination strings
    terminationStrings.forEach(term => {
      cleanContent = cleanContent.replace(new RegExp(term, 'gi'), '');
    });
    
    // Clean up extra whitespace and newlines
    cleanContent = cleanContent.replace(/\s+/g, ' ').trim();
    
    return cleanContent;
  }
}

// Export for use in other modules
window.AIChatWidget = AIChatWidget;
