/**
 * Document Widget for ADA2
 * A simplified version of the document widget adapted from the original ADA project
 * Features:
 * - Chapter/section navigation
 * - Text highlighting during TTS reading (uses shared TextHighlighter)
 * - Basic document viewer
 * - Integration with avatar voice commands
 */

class DocumentWidget {
    constructor() {
        this.isVisible = false;
        this.isDragging = false;
        this.dragOffset = { x: 0, y: 0 };
        this.currentDocument = null;
        this.currentSections = [];
        this.currentSection = null;
        this.highlightDelay = 1000; // 1 second delay for highlighting

        // Text highlighter with document-specific options
        this.textHighlighter = new TextHighlighter({
            highlightDelay: 1000,
            enableBookmarks: true,
            enableClickableSegments: true,
            onBookmarkSet: (position, segmentIndex) => {
                if (this.currentSection) {
                    this.setBookmark(position, this.currentSection.order);
                    this.readingStartPosition = position;
                }
            },
            onProgressUpdate: (progress) => {
                // Update reading position if we're currently reading
                if (this.isReading) {
                    this.readingStartPosition = progress.position;
                    
                    // Auto-save bookmark as highlighter moves
                    if (this.currentSection) {
                        this.setBookmark(progress.position, this.currentSection.order);
                    }
                }
                this.updateBookmarkDisplay();
            }
        });

        // Reading state management
        this.isReading = false;
        this.currentReadingText = '';
        this.readingStartPosition = 0;

        // Bookmark system
        this.bookmarks = this.loadBookmarks();

        this.init();
    }

    /**
     * Initialize the document widget
     */
    init() {
        this.createWidget();
        this.setupEventListeners();
        this.addStyles();
    }

    /**
     * Create the widget DOM structure
     */
    createWidget() {
        // Remove existing widget if any
        const existing = document.getElementById('document-widget');
        if (existing) {
            existing.remove();
        }

        // Create widget container
        this.widget = document.createElement('div');
        this.widget.id = 'document-widget';
        this.widget.className = 'document-widget';
        // Apply centralized widget container styles with flex-direction override
        if (window.WidgetStyles) {
            this.widget.style.cssText = window.WidgetStyles.container + '; flex-direction: column;';
        }

        // Create header (fixed at top)
        const header = document.createElement('div');
        header.className = 'document-header';
        // Apply centralized header styles 
        if (window.WidgetStyles) {
            header.style.cssText = window.WidgetStyles.header;
        }

        // Create content wrapper (below header)
        const contentWrapper = document.createElement('div');
        contentWrapper.style.cssText = `
            flex: 1;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        `;

        // Create title element
        const title = document.createElement('h3');
        if (window.WidgetStyles) {
            title.style.cssText = window.WidgetStyles.title;
        }
        title.textContent = '📚 Document Library';
        title.className = 'document-title-text';

        // Create close button  
        const closeButton = document.createElement('button');
        closeButton.className = 'document-close-btn';
        if (window.WidgetStyles) {
            closeButton.style.cssText = window.WidgetStyles.closeButton;
        }
        closeButton.innerHTML = '✕';
        closeButton.title = 'Close';

        // Add back button (hidden by default)
        const backButton = document.createElement('button');
        backButton.id = 'header-back-btn';
        backButton.innerHTML = '❮';
        backButton.title = 'Back';
        backButton.style.cssText = `
            background: none; 
            border: none; 
            color: #007bff; 
            cursor: pointer; 
            font-size: 16px; 
            display: none; 
            padding: 4px;
            margin-right: 10px;
        `;
        backButton.onclick = () => window.documentWidget.handleBackNavigation();

        // Create controls container for reading controls (hidden by default)
        const controlsContainer = document.createElement('div');
        controlsContainer.id = 'header-reading-controls';
        controlsContainer.style.cssText = 'display: none; align-items: center; gap: 6px; margin-right: 12px;';
        controlsContainer.innerHTML = `
            <div id="header-reading-status" style="font-size: 10px; color: #ccc;">Ready</div>
            <button id="header-read-btn" onclick="window.documentWidget.startReading()" 
                    style="background: #4CAF50; color: white; border: none; padding: 4px 8px; 
                           border-radius: 3px; cursor: pointer; font-size: 11px; font-weight: bold;">
                ▶ Read
            </button>
            <button id="header-stop-btn" onclick="window.documentWidget.stopReading()" 
                    style="background: #E53935; color: white; border: none; padding: 4px 8px; 
                           border-radius: 3px; cursor: pointer; font-size: 11px; font-weight: bold;">
                ⏹ Stop
            </button>
            <button id="header-reset-btn" onclick="window.documentWidget.resetReading()" 
                    style="background: #607D8B; color: white; border: none; padding: 4px 8px; 
                           border-radius: 3px; cursor: pointer; font-size: 11px;">
                🔄 Reset
            </button>
            <div id="header-bookmark-status" style="font-size: 9px; color: #999;">📍 0%</div>
        `;

        // Create section indicator (hidden by default)
        const sectionIndicator = document.createElement('span');
        sectionIndicator.id = 'header-section-indicator';
        sectionIndicator.style.cssText = 'color: #aaa; font-size: 13px; display: none; margin-left: 10px;';

        // Append elements to header
        header.appendChild(backButton);
        header.appendChild(title);
        header.appendChild(sectionIndicator);
        header.appendChild(controlsContainer);
        header.appendChild(closeButton);

        // Create content area
        const content = document.createElement('div');
        content.className = 'document-content';
        content.style.cssText = `
            flex: 1;
            display: flex;
            flex-direction: column;
            overflow: hidden;
            padding: 0 20px 20px 20px;
        `;

        // Create document library (shown when multiple documents available)
        const documentLibrary = document.createElement('div');
        documentLibrary.className = 'document-library';
        documentLibrary.style.cssText = `
            flex: 1;
            overflow-y: auto;
            padding: 0;
            display: none;
        `;

        // Create sections list
        const sectionsList = document.createElement('div');
        sectionsList.className = 'document-sections-list';
        sectionsList.style.cssText = `
            flex: 1;
            overflow-y: auto;
            padding: 16px;
        `;

        // Create content viewer
        const contentViewer = document.createElement('div');
        contentViewer.className = 'document-content-viewer';
        contentViewer.style.cssText = `
            flex: 1;
            overflow-y: auto;
            padding: 16px;
            display: none;
            background-color: #333;
            line-height: 1.6;
        `;

        content.appendChild(documentLibrary);
        content.appendChild(sectionsList);
        content.appendChild(contentViewer);

        // Append content to wrapper
        contentWrapper.appendChild(content);

        // Append header and wrapper to widget
        this.widget.appendChild(header);
        this.widget.appendChild(contentWrapper);
        document.body.appendChild(this.widget);

        // Store references
        this.titleElement = this.widget.querySelector('.document-title-text');
        this.documentLibraryElement = documentLibrary;
        this.sectionsListElement = sectionsList;
        this.contentViewerElement = contentViewer;
        this.headerElement = header;
    }

    /**
     * Setup event listeners
     */
    setupEventListeners() {
        // Close button
        const closeBtn = this.widget.querySelector('.document-close-btn');
        closeBtn.addEventListener('click', () => {
            this.hide();
        });
        // Add hover effects to match ChatGPT widget
        closeBtn.addEventListener('mouseenter', () => {
            closeBtn.style.background = '#333';
            closeBtn.style.color = '#fff';
        });
        closeBtn.addEventListener('mouseleave', () => {
            closeBtn.style.background = 'none';
            closeBtn.style.color = '#888';
        });

        // Make draggable by header
        this.headerElement.addEventListener('mousedown', (e) => {
            this.startDrag(e);
        });

        document.addEventListener('mousemove', (e) => {
            if (this.isDragging) {
                this.drag(e);
            }
        });

        document.addEventListener('mouseup', () => {
            this.stopDrag();
        });
    }

    /**
     * Add CSS styles for the widget
     */
    addStyles() {
        if (document.getElementById('document-widget-styles')) {
            return;
        }

        const style = document.createElement('style');
        style.id = 'document-widget-styles';
        style.textContent = `
            .document-widget button {
                background: #444;
                color: white;
                border: none;
                padding: 8px 12px;
                border-radius: 4px;
                cursor: pointer;
                font-size: 14px;
            }
            
            .document-widget button:hover {
                background: #555;
            }
            
            
            .section-item {
                padding: 12px;
                border-bottom: 1px solid #444;
                cursor: pointer;
                transition: background-color 0.2s;
            }
            
            .section-item:hover {
                background-color: #3a3a3a;
            }
            
            .section-item.active {
                background-color: #0d47a1;
            }
            
            
            .document-content-viewer::-webkit-scrollbar,
            .document-sections-list::-webkit-scrollbar {
                width: 8px;
            }
            
            .document-content-viewer::-webkit-scrollbar-track,
            .document-sections-list::-webkit-scrollbar-track {
                background: #2a2a2a;
            }
            
            .document-content-viewer::-webkit-scrollbar-thumb,
            .document-sections-list::-webkit-scrollbar-thumb {
                background: #555;
                border-radius: 4px;
            }
            
            .document-content-viewer::-webkit-scrollbar-thumb:hover,
            .document-sections-list::-webkit-scrollbar-thumb:hover {
                background: #666;
            }
            
            /* Shift all elements left to be centered in the 60vw space */
            
            
            .delete-book-btn:hover {
                background-color: rgba(211, 47, 47, 0.1) !important;
                color: #d32f2f !important;
                transform: scale(1.1);
            }
            
            .delete-book-btn:active {
                transform: scale(0.95);
            }
        `;
        document.head.appendChild(style);
    }

    /**
     * Display document library or single document
     * @param {Object|Array} data - Single document data or array of documents
     */
    async displayDocuments(data) {
        if (Array.isArray(data)) {
            // Multiple documents - show library
            this.displayDocumentLibrary(data);
        } else {
            // Single document - show sections directly
            this.displayDocument(data);
        }
        this.show();
    }

    /**
     * Display document library (multiple documents)
     * @param {Array} documents - Array of document objects
     */
    displayDocumentLibrary(documents) {
        this.titleElement.textContent = 'Document Library';

        // Create upload button container
        const uploadContainer = document.createElement('div');
        uploadContainer.style.cssText = `
            padding: 8px 16px 16px 16px;
            border-bottom: 1px solid #444;
            text-align: center;
        `;

        uploadContainer.innerHTML = `
            <input type="file" id="epub-file-input" accept=".epub" style="display: none;">
            <button id="upload-epub-btn" style="
                background: #4CAF50;
                color: white;
                border: none;
                padding: 12px 24px;
                border-radius: 6px;
                cursor: pointer;
                font-size: 14px;
                font-weight: bold;
                display: flex;
                align-items: center;
                gap: 8px;
                margin: 0 auto;
            ">
                📤 Upload EPUB File
            </button>
        `;

        // Clear and rebuild library content
        this.documentLibraryElement.innerHTML = '';
        this.documentLibraryElement.appendChild(uploadContainer);

        if (!documents || documents.length === 0) {
            const emptyState = document.createElement('div');
            emptyState.style.cssText = `
                text-align: center;
                padding: 40px;
                color: #666;
            `;
            emptyState.innerHTML = `
                <div style="font-size: 48px; margin-bottom: 16px;">📚</div>
                <div>No documents in your library</div>
                <div style="font-size: 14px; margin-top: 8px; color: #888;">
                    Click the upload button above to add EPUB files
                </div>
            `;
            this.documentLibraryElement.appendChild(emptyState);
        } else {
            documents.forEach((doc, index) => {
                const docElement = this.createDocumentElement(doc, index + 1);
                this.documentLibraryElement.appendChild(docElement);
            });
        }

        // Add upload functionality
        this.setupUploadFunctionality();

        this.showDocumentLibrary();
    }

    /**
     * Create a document element for the library
     * @param {Object} doc - Document data
     * @param {number} index - Document index (1-based)
     * @returns {HTMLElement} Document element
     */
    createDocumentElement(doc, index) {
        const docDiv = document.createElement('div');
        docDiv.className = 'document-item';
        docDiv.style.cssText = `
            padding: 16px;
            border-bottom: 1px solid #444;
            cursor: pointer;
            transition: background-color 0.2s;
        `;

        docDiv.innerHTML = `
            <div style="display: flex; align-items: center; gap: 16px;">
                <div style="font-size: 32px;">📖</div>
                <div style="flex: 1;">
                    <div style="font-weight: bold; margin-bottom: 4px; font-size: 16px;">
                        ${this.escapeHtml(doc.title || 'Untitled')}
                    </div>
                    <div style="font-size: 14px; color: #aaa; margin-bottom: 4px;">
                        by ${this.escapeHtml(doc.author || 'Unknown Author')}
                    </div>
                    <div style="font-size: 12px; color: #666;">
                        ${doc.chapters || 0} chapters
                    </div>
                </div>
                <div style="display: flex; align-items: center; gap: 12px;">
                    <button class="delete-book-btn" data-book-id="${doc.id}" 
                            style="background: none; color: #999; border: none; 
                                   padding: 4px; cursor: pointer; font-size: 18px; 
                                   display: flex; align-items: center; justify-content: center; 
                                   width: 32px; height: 32px; border-radius: 4px; 
                                   transition: all 0.2s ease;"
                            title="Delete this book">
                        🗑️
                    </button>
                    <div style="color: #666; font-size: 18px;">▶</div>
                </div>
            </div>
        `;

        // Add hover effect
        docDiv.addEventListener('mouseenter', () => {
            docDiv.style.backgroundColor = '#3a3a3a';
        });
        docDiv.addEventListener('mouseleave', () => {
            docDiv.style.backgroundColor = 'transparent';
        });

        // Add click handler to focus on this document
        docDiv.addEventListener('click', async (event) => {
            // Don't trigger focus if delete button was clicked
            if (event.target.closest('.delete-book-btn')) {
                return;
            }
            await this.focusOnDocument(doc, index);
        });

        // Add delete button handler
        const deleteBtn = docDiv.querySelector('.delete-book-btn');
        if (deleteBtn) {
            deleteBtn.addEventListener('click', async (event) => {
                event.stopPropagation(); // Prevent document click
                await this.deleteDocument(doc.id, doc.title);
            });
        }

        return docDiv;
    }

    /**
     * Focus on a specific document (equivalent to /focus book <number>)
     * @param {Object} doc - Document data
     * @param {number} index - Document index (1-based)
     */
    async focusOnDocument(doc, index) {
        try {
            // Call the backend focus API
            await fetch('/api/documents/query', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query: `focus on book ${index}` })
            });

            // Get sections for this document
            const sectionsResponse = await fetch('/api/documents/query', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query: 'list sections' })
            });
            const sectionsData = await sectionsResponse.json();

            if (sectionsData.success && sectionsData.sections) {
                // Update current document data
                this.currentDocument = {
                    ...doc,
                    sections: sectionsData.sections.map(section => ({
                        order: section.number,
                        title: section.title,
                        id: section.number
                    }))
                };
                this.currentSections = this.currentDocument.sections;

                // Update title and show sections
                this.titleElement.textContent = doc.title || 'Document';
                this.displaySections(this.currentSections);
                this.showSectionsList();
            } else {
                throw new Error('Failed to load sections');
            }
        } catch (error) {
            console.error('Error focusing on document:', error);
        }
    }

    /**
     * Display a document with its sections (original method, now for single document)
     * @param {Object} documentData - The document data
     */
    displayDocument(documentData) {
        this.currentDocument = documentData;
        this.currentSections = documentData.sections || [];

        // Update title
        this.titleElement.textContent = documentData.title || 'Document';

        // Display sections
        this.displaySections(this.currentSections);
        this.showSectionsList();
    }

    /**
     * Display sections list
     * @param {Array} sections - Array of sections
     */
    displaySections(sections) {
        if (!sections || sections.length === 0) {
            this.sectionsListElement.innerHTML = `
                <div style="text-align: center; padding: 40px; color: #666;">
                    <div style="font-size: 48px; margin-bottom: 16px;">📚</div>
                    <div>No sections found</div>
                </div>
            `;
            return;
        }

        this.sectionsListElement.innerHTML = '';
        sections.forEach((section, index) => {
            const sectionElement = this.createSectionElement(section, index);
            this.sectionsListElement.appendChild(sectionElement);
        });
    }

    /**
     * Create a section element
     * @param {Object} section - Section data
     * @param {number} index - Section index
     * @returns {HTMLElement} Section element
     */
    createSectionElement(section, index) {
        const sectionDiv = document.createElement('div');
        sectionDiv.className = 'section-item';

        const sectionNumber = section.order || (index + 1);
        const sectionTitle = section.title || `Section ${sectionNumber}`;

        sectionDiv.innerHTML = `
            <div style="display: flex; align-items: center; gap: 12px;">
                <div style="font-size: 20px;">📖</div>
                <div style="flex: 1;">
                    <div style="font-weight: bold; margin-bottom: 4px;">
                        ${this.escapeHtml(sectionTitle)}
                    </div>
                    <div style="font-size: 12px; color: #aaa;">
                        Section ${sectionNumber}
                    </div>
                </div>
                <div style="color: #666;">▶</div>
            </div>
        `;

        // Add click handler
        sectionDiv.addEventListener('click', (event) => {
            // Store reference to the clicked element for active state management
            sectionDiv.clickedElement = event.target.closest('.section-item');
            this.loadSectionContent(section, sectionNumber, sectionDiv);
        });

        return sectionDiv;
    }

    /**
     * Load section content
     * @param {Object} section - Section data
     * @param {number} sectionNumber - Section number
     * @param {HTMLElement} [clickedElement] - The clicked section element for UI updates
     */
    async loadSectionContent(section, sectionNumber, clickedElement) {

        // Mark section as active
        this.sectionsListElement.querySelectorAll('.section-item').forEach(item => {
            item.classList.remove('active');
        });

        // If called from UI click, use the clicked element, otherwise find by section number
        if (clickedElement) {
            clickedElement.classList.add('active');
        } else {
            // Find the section element by section number for programmatic calls
            const allSections = this.sectionsListElement.querySelectorAll('.section-item');
            allSections.forEach((item, index) => {
                if (index + 1 === sectionNumber) {
                    item.classList.add('active');
                }
            });
        }

        // Show loading state
        this.contentViewerElement.innerHTML = `
            <div style="display: flex; align-items: center; justify-content: center; height: 200px;">
                <div>Loading section content...</div>
            </div>
        `;

        // Switch to content view
        this.showContentView();

        try {
            // Fetch the actual section content from the API
            const response = await fetch('/api/documents/query', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query: `show section ${sectionNumber}` })
            });

            const data = await response.json();

            if (data.success && data.content) {
                // Use the real content from the API
                const sectionText = data.content;

                // Update section object with real content
                const sectionWithContent = {
                    ...section,
                    text: sectionText,
                    title: data.title || section.title
                };

                // Display the content
                this.displaySectionContent(sectionWithContent, sectionNumber, sectionText);

                // Monitor global stop state
                this.initializeStopMonitoring();
            } else {
                throw new Error(data.message || 'Failed to fetch section content');
            }

        } catch (error) {
            console.error('Error loading section:', error);
            this.contentViewerElement.innerHTML = `
                <div style="text-align: center; padding: 40px; color: #d32f2f;">
                    <div style="margin-bottom: 16px;">⚠️ Error loading content</div>
                    <div style="font-size: 14px;">${error.message}</div>
                    <button onclick="window.documentWidget.showSectionsList()" style="margin-top: 16px;">
                        Back to Sections
                    </button>
                </div>
            `;
        }
    }

    /**
     * Display section content
     * @param {Object} section - Section data
     * @param {number} sectionNumber - Section number
     * @param {string} sectionText - Section text content
     */
    displaySectionContent(section, sectionNumber, sectionText) {
        this.currentSection = section;

        // Reset highlighter
        this.textHighlighter.reset();

        const sectionTitle = section.title || `Section ${sectionNumber}`;

        this.contentViewerElement.innerHTML = `
            <!-- Chapter Title -->
            <div style="margin-bottom: 16px;">
                <h2 style="margin: 0; color: #fff; font-size: 20px;">
                    ${this.escapeHtml(sectionTitle)}
                </h2>
                <div style="font-size: 14px; color: #aaa; margin-top: 4px;">
                    Section ${sectionNumber} of "${this.currentDocument.title}"
                </div>
            </div>
            
            <div style="background: #3a3a3a; padding: 20px; border-radius: 8px; line-height: 1.8;">
                <div class="reading-text" style="font-size: 16px; white-space: pre-wrap; word-wrap: break-word;">
                    <!-- Text will be structured by highlighter -->
                </div>
            </div>
        `;

        // Initialize text highlighting
        const textElement = this.contentViewerElement.querySelector('.reading-text');
        this.textHighlighter.initializeTextStructure(textElement, sectionText);

        // Load bookmark for this section
        this.loadFromBookmark();

        // Start subtitle monitoring for highlighting (should be after text initialization)
        this.initializeSubtitleMonitoring();

        // Show header controls, back button, and section indicator now that content is loaded
        const headerControls = this.widget?.querySelector('#header-reading-controls');
        const headerBackBtn = this.widget?.querySelector('#header-back-btn');
        const headerSectionIndicator = this.widget?.querySelector('#header-section-indicator');

        if (headerControls) {
            headerControls.style.display = 'flex';
        }
        if (headerBackBtn) {
            headerBackBtn.style.display = 'block';
            headerBackBtn.title = 'Back to Sections';
        }
        if (headerSectionIndicator) {
            headerSectionIndicator.textContent = `: S${sectionNumber}`;
            headerSectionIndicator.style.display = 'inline';
        }

        // Reset scroll position
        this.contentViewerElement.scrollTop = 0;

        // Initialize reading button states
        this.updateReadingButtons();

    }

    /**
     * Initialize stop button monitoring
     */
    initializeStopMonitoring() {
        // Monitor when the global stop button is pressed
        const stopBtn = document.getElementById('stop-speech-button');
        if (stopBtn) {
            const observer = new MutationObserver((mutations) => {
                mutations.forEach((mutation) => {
                    if (mutation.type === 'attributes' && mutation.attributeName === 'class') {
                        const isVisible = stopBtn.classList.contains('visible');
                        if (!isVisible && this.isReading) {
                            // Stop button was hidden, meaning speech stopped
                            this.handleExternalStop();
                        }
                    }
                });
            });

            observer.observe(stopBtn, {
                attributes: true,
                attributeFilter: ['class']
            });

        }

        // Also monitor global stop events
        document.addEventListener('keydown', (event) => {
            if (event.key === 'Escape' && this.isReading) {
                this.handleExternalStop();
            }
        });
    }

    /**
     * Initialize subtitle monitoring for text highlighting
     */
    initializeSubtitleMonitoring() {
        // Find subtitles element
        const subtitlesElement = document.getElementById('subtitles');
        if (!subtitlesElement) {
            console.warn('⚠️ Subtitles element not found');
            return;
        }

        // Use shared highlighter's subtitle monitoring
        this.textHighlighter.startSubtitleMonitoring(subtitlesElement);
    }

    /**
     * Handle back navigation (content → sections → library)
     */
    async handleBackNavigation() {
        // If currently showing content, go back to sections
        if (this.contentViewerElement.style.display === 'block') {
            this.showSectionsList();
        }
        // If currently showing sections, go back to library
        else if (this.sectionsListElement.style.display === 'block') {
            await this.returnToLibrary();
        }
    }

    /**
     * Return to document library from sections view
     */
    async returnToLibrary() {
        try {
            // Fetch current documents list
            const docsResponse = await fetch('/api/documents/list');
            const docsData = await docsResponse.json();

            if (docsData.success && docsData.documents) {
                const documentKeys = Object.keys(docsData.documents);
                const documentsArray = documentKeys.map((docId) => ({
                    id: docId,
                    title: docsData.documents[docId].title,
                    author: docsData.documents[docId].author,
                    chapters: docsData.documents[docId].chapters || 0
                }));

                // Clear current document state
                this.currentDocument = null;
                this.currentSections = [];
                this.currentSection = null;

                // Show library
                this.displayDocumentLibrary(documentsArray);
            } else {
                // No documents available - show empty library
                this.displayDocumentLibrary([]);
            }
        } catch (error) {
            console.error('Error returning to library:', error);
            // Fallback to empty library
            this.displayDocumentLibrary([]);
        }
    }

    /**
     * Show content view
     */
    showContentView() {
        this.documentLibraryElement.style.display = 'none';
        this.sectionsListElement.style.display = 'none';
        this.contentViewerElement.style.display = 'block';
    }

    /**
     * Show document library view
     */
    showDocumentLibrary() {
        this.documentLibraryElement.style.display = 'block';
        this.sectionsListElement.style.display = 'none';
        this.contentViewerElement.style.display = 'none';

        // Hide header controls, back button, and section indicator when showing library
        const headerControls = this.widget?.querySelector('#header-reading-controls');
        const headerBackBtn = this.widget?.querySelector('#header-back-btn');
        const headerSectionIndicator = this.widget?.querySelector('#header-section-indicator');

        if (headerControls) {
            headerControls.style.display = 'none';
        }
        if (headerBackBtn) {
            headerBackBtn.style.display = 'none';
        }
        if (headerSectionIndicator) {
            headerSectionIndicator.style.display = 'none';
        }
    }

    /**
     * Show sections list
     */
    showSectionsList() {
        this.documentLibraryElement.style.display = 'none';
        this.contentViewerElement.style.display = 'none';
        this.sectionsListElement.style.display = 'block';

        // Show back button for sections view, hide reading controls and section indicator
        const headerControls = this.widget?.querySelector('#header-reading-controls');
        const headerBackBtn = this.widget?.querySelector('#header-back-btn');
        const headerSectionIndicator = this.widget?.querySelector('#header-section-indicator');

        if (headerControls) {
            headerControls.style.display = 'none';
        }
        if (headerBackBtn) {
            headerBackBtn.style.display = 'block';
            headerBackBtn.title = 'Back to Library';
        }
        if (headerSectionIndicator) {
            headerSectionIndicator.style.display = 'none';
        }

        // Clear active section
        this.sectionsListElement.querySelectorAll('.section-item').forEach(item => {
            item.classList.remove('active');
        });
    }

    /**
     * Show the widget
     */
    show() {
        if (!this.isVisible) {
            this.widget.style.display = 'flex';
            this.isVisible = true;
            document.body.classList.add('widget-visible');
            try { const sub = document.getElementById('subtitles'); if(sub){ sub.style.left = 'calc(50% - 22vw)'; } } catch(_){ }

            // Trigger animation
            setTimeout(() => {
                this.widget.style.transform = 'translateX(0)';
            }, 10);

        }
    }

    /**
     * Hide the widget
     */
    hide() {
        if (this.isVisible) {
            document.body.classList.remove('widget-visible');
            this.widget.style.transform = 'translateX(100%)';

            setTimeout(() => {
                this.widget.style.display = 'none';
            }, 300);

            this.isVisible = false;
            this.currentDocument = null;
            this.currentSections = [];
            this.currentSection = null;

            // Clean up text highlighting
            this.textHighlighter.reset();

            // Notify widget manager
            if (window.widgetManager) {
                window.widgetManager.widgetClosed('document');
            }
            try { const sub = document.getElementById('subtitles'); if(sub){ sub.style.left = '50%'; } } catch(_){ }
        }
    }

    // Dragging functionality
    startDrag(e) {
        if (e.target.closest('.document-controls')) {
            return;
        }
        this.isDragging = true;
        const rect = this.widget.getBoundingClientRect();
        this.dragOffset = {
            x: e.clientX - rect.left,
            y: e.clientY - rect.top
        };
        e.preventDefault();
    }

    drag(e) {
        if (!this.isDragging) return;
        const newLeft = e.clientX - this.dragOffset.x;
        const newTop = e.clientY - this.dragOffset.y;
        const maxLeft = window.innerWidth - this.widget.offsetWidth;
        const constrainedLeft = Math.max(0, Math.min(newLeft, maxLeft));
        const constrainedTop = Math.max(0, Math.min(newTop, window.innerHeight - this.widget.offsetHeight));
        this.widget.style.left = constrainedLeft + 'px';
        this.widget.style.top = constrainedTop + 'px';
        this.widget.style.right = 'auto';
    }

    stopDrag() {
        this.isDragging = false;
    }

    /**
     * Load bookmarks from localStorage
     */
    loadBookmarks() {
        try {
            const stored = localStorage.getItem('documentBookmarks');
            return stored ? JSON.parse(stored) : {};
        } catch (error) {
            console.warn('Error loading bookmarks:', error);
            return {};
        }
    }

    /**
     * Save bookmarks to localStorage
     */
    saveBookmarks() {
        try {
            localStorage.setItem('documentBookmarks', JSON.stringify(this.bookmarks));
        } catch (error) {
            console.warn('Error saving bookmarks:', error);
        }
    }

    /**
     * Get bookmark for current document and section
     */
    getCurrentBookmark() {
        if (!this.currentDocument || !this.currentSection) return null;
        const bookmarkKey = `${this.currentDocument.id}_section_${this.currentSection.order}`;
        return this.bookmarks[bookmarkKey] || null;
    }

    /**
     * Set bookmark for current document and section
     */
    setBookmark(position, sectionNumber) {
        if (!this.currentDocument || !sectionNumber) return;

        const bookmarkKey = `${this.currentDocument.id}_section_${sectionNumber}`;
        this.bookmarks[bookmarkKey] = {
            position: position,
            sectionNumber: sectionNumber,
            timestamp: Date.now()
        };
        this.saveBookmarks();
        this.updateBookmarkDisplay();

    }

    /**
     * Update bookmark display in header
     */
    updateBookmarkDisplay() {
        const headerBookmarkElement = this.widget?.querySelector('#header-bookmark-status');

        const bookmark = this.getCurrentBookmark();
        if (bookmark && this.textHighlighter.isInitialized) {
            const progressPercent = (bookmark.position / this.textHighlighter.fullText.length * 100).toFixed(1);
            if (headerBookmarkElement) {
                headerBookmarkElement.textContent = `📍 ${progressPercent}%`;
            }
        } else {
            if (headerBookmarkElement) {
                headerBookmarkElement.textContent = '📍 0%';
            }
        }
    }

    /**
     * Load reading position from bookmark for current section
     */
    loadFromBookmark() {
        const bookmark = this.getCurrentBookmark();
        if (bookmark && this.currentSection) {
            this.readingStartPosition = bookmark.position;
            // Use shared highlighter's method
            setTimeout(() => {
                this.textHighlighter.setReadingPosition(bookmark.position);
            }, 100); // Small delay to ensure text structure is ready
        } else {
            // No bookmark for this section, start from beginning
            this.readingStartPosition = 0;
            this.textHighlighter.setReadingPosition(0);
        }
        this.updateBookmarkDisplay();
    }

    /**
     * Start reading the current chapter
     */
    async startReading() {
        if (!this.currentSection) {
            console.warn('No section loaded');
            return;
        }

        // Get the text to read
        this.currentReadingText = this.currentSection.text || '';

        if (!this.currentReadingText.trim()) {
            console.warn('No text to read');
            return;
        }

        // Start from current bookmark position
        const textToRead = this.currentReadingText.substring(this.readingStartPosition);
        this.updateReadingStatus('Reading...');

        this.isReading = true;
        this.updateReadingButtons();

        // Use Kokoro TTS via global window.kokoroSpeak (server injects kokoro-bootstrap)
        try {
            // Ensure receive-only reader session for server-side TTS
            if (!(window.readerRTC && window.readerRTC.isConnected && window.readerRTC.isConnected())) {
              try { if (window.readerRTC && window.readerRTC.connect) { await window.readerRTC.connect(); } } catch(_){}
            }
            // Prefer server-side TTS via /api/tts/read (zero-latency lipsync like LLM path)
            let usedServer = false;
            try {
              const resp = await fetch('/api/tts/read', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: textToRead, pc_id: (window.readerRTC && window.readerRTC.pc_id) || undefined })
              });
              const data = await resp.json().catch(() => ({}));
              usedServer = !!(data && data.success);
            } catch(_) { usedServer = false; }

            if (!usedServer) {
              // No active voice session; advise user to Connect Voice Chat instead of freezing the UI
              this.updateReadingStatus('Connect Voice Chat to hear reading');
              this.isReading = false;
              this.updateReadingButtons();
              return;
            }
            // Server path: subtitles will stream over datachannel; clear first
            const sub = document.getElementById('subtitles');
            if (sub) { sub.textContent = ''; }

        } catch (error) {
            console.warn('TTS system not available:', error.message);
            this.updateReadingStatus('TTS not available');
            this.stopReading();

            // Alternative: Try to trigger TTS through the main chat system
            this.fallbackToMainTTS(textToRead);
        }

    }

    /**
     * Stop reading utility to match ADA2 API expectations
     */
    stopReading() {
        // Server interrupt to stop the active TTS/lipsync stream
        try {
            const pc_id = (window.readerRTC && window.readerRTC.pc_id) || undefined;
            fetch('/api/stop', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ pc_id })
            }).catch(() => {});
        } catch (_) {}
        // Update local UI only; the client will receive tts_interrupt and halt avatar speech
        this.isReading = false;
        this.updateReadingStatus('Stopped');
        this.updateReadingButtons();
        if (this.currentSection) {
            this.setBookmark(this.readingStartPosition || 0, this.currentSection.order);
        }
    }

    /**
     * Stop reading completely (called when existing stop button is pressed)
     */
    handleExternalStop() {
        this.isReading = false;
        this.updateReadingStatus('Stopped');
        this.updateReadingButtons();

        // Save current position as bookmark
        if (this.currentSection) {
            this.setBookmark(this.readingStartPosition, this.currentSection.order);
        }

    }

    /**
     * Reset reading position to beginning
     */
    resetReading() {
        // Stop current reading using the global stop function
        if (window.stopTalking) {
            window.stopTalking();
        }

        // Stop local TTS as well
        this.stopTTSPlayback();

        this.isReading = false;

        // Reset position
        this.readingStartPosition = 0;
        this.textHighlighter.reset();

        // Clear bookmark for this section
        if (this.currentDocument && this.currentSection) {
            this.setBookmark(0, this.currentSection.order);
        }

        // Re-initialize highlighting if we have content
        if (this.currentSection && this.currentSection.text) {
            const textElement = this.contentViewerElement.querySelector('.reading-text');
            if (textElement) {
                this.textHighlighter.initializeTextStructure(textElement, this.currentSection.text);
            }
        }

        this.updateReadingStatus('Reset to beginning');
        this.updateReadingButtons();

    }

    /**
     * Fallback TTS method using the main textbox system
     */
    fallbackToMainTTS(text) {
        try {
            // Try to use the main UI TTS system
            const textbox = document.getElementById('textbox');
            const speakBtn = document.getElementById('speak');

            if (textbox && speakBtn) {
                // Set the text and trigger speak
                textbox.value = text.substring(0, 500); // Limit length
                speakBtn.click();
                this.updateReadingStatus('Reading via main TTS...');
            } else {
                this.updateReadingStatus('No TTS system available');
            }
        } catch (error) {
            console.warn('Fallback TTS failed:', error);
            this.updateReadingStatus('TTS failed');
        }
    }

    /**
     * Stop TTS playback
     */
    stopTTSPlayback() {
        // Stop the global TTS system
        if (window.kokoro) {
            try {
                // Clear TTS queue
                if (window.kokoroQueue) {
                    window.kokoroQueue.length = 0;
                }

                // Stop any current audio playback
                if (window.head && window.head.stopSpeaking) {
                    window.head.stopSpeaking();
                }

                // Clear subtitles
                const subtitlesElement = document.getElementById('subtitles');
                if (subtitlesElement) {
                    subtitlesElement.textContent = '';
                }

            } catch (error) {
                console.warn('Error stopping TTS:', error);
            }
        }
    }

    /**
     * Update reading status display
     */
    updateReadingStatus(status) {
        const statusElement = this.widget?.querySelector('#header-reading-status');
        if (statusElement) {
            statusElement.textContent = status;
        }
    }

    /**
     * Update reading button states in header
     */
    updateReadingButtons() {
        const readBtn = this.widget?.querySelector('#header-read-btn');
        const stopBtn = this.widget?.querySelector('#header-stop-btn');
        const resetBtn = this.widget?.querySelector('#header-reset-btn');
        const statusElement = this.widget?.querySelector('#header-reading-status');

        if (!readBtn || !resetBtn || !stopBtn) {
            return;
        }

        if (this.isReading) {
            // Reading: enable stop, disable read/reset
            readBtn.innerHTML = '🔊 Reading...';
            readBtn.disabled = true;
            readBtn.style.opacity = '0.6';
            readBtn.style.background = '#9E9E9E';
            stopBtn.disabled = false;
            stopBtn.style.opacity = '1';
            resetBtn.disabled = true;
            resetBtn.style.opacity = '0.5';
            if (statusElement) {
                statusElement.textContent = 'Reading...';
                statusElement.style.color = '#4CAF50';
            }
        } else {
            // Idle: enable read/reset, disable stop
            readBtn.innerHTML = '▶ Read';
            readBtn.disabled = false;
            readBtn.style.opacity = '1';
            readBtn.style.background = '#4CAF50';
            stopBtn.disabled = true;
            stopBtn.style.opacity = '0.5';
            resetBtn.disabled = false;
            resetBtn.style.opacity = '1';
            if (statusElement) {
                statusElement.textContent = 'Ready';
                statusElement.style.color = '#ccc';
            }
        }
    }

    /**
     * Setup upload functionality for EPUB files
     */
    setupUploadFunctionality() {
        const uploadBtn = document.getElementById('upload-epub-btn');
        const fileInput = document.getElementById('epub-file-input');

        if (uploadBtn && fileInput) {
            // Click upload button triggers file input
            uploadBtn.addEventListener('click', () => {
                fileInput.click();
            });

            // Handle file selection
            fileInput.addEventListener('change', async (event) => {
                const file = event.target.files[0];
                if (file && file.name.toLowerCase().endsWith('.epub')) {
                    await this.uploadEpubFile(file);
                }
                // Reset file input for next upload
                fileInput.value = '';
            });
        }
    }

    /**
     * Upload EPUB file to backend
     * @param {File} file - The EPUB file to upload
     */
    async uploadEpubFile(file) {
        const uploadBtn = document.getElementById('upload-epub-btn');

        try {
            // Show processing state with rotating messages
            if (uploadBtn) {
                uploadBtn.innerHTML = '⚙️ Processing...';
                uploadBtn.disabled = true;

                // Show rotating progress messages
                this.showUploadProgress(uploadBtn, file.name);
            }

            // Create FormData for file upload
            const formData = new FormData();
            formData.append('file', file);

            // Upload file
            const response = await fetch('/api/documents/upload', {
                method: 'POST',
                body: formData
            });

            const result = await response.json();

            if (result.success) {
                // Upload successful - refresh the library
                const responseText = `Successfully uploaded "${file.name}". Refreshing your library.`;

                // Speak the response
                if (window.kokoroSpeak) {
                    window.kokoroSpeak(responseText, {}, (sentence, id, word) => {
                        const subtitlesElement = document.getElementById('subtitles');
                        if (subtitlesElement) {
                            if (id !== this.lastSentenceId) {
                                this.lastSentenceId = id;
                                subtitlesElement.textContent = '';
                            }
                            subtitlesElement.textContent += word;
                        }
                    });
                }

                // Refresh the document library
                setTimeout(async () => {
                    try {
                        const docsResponse = await fetch('/api/documents/list');
                        const docsData = await docsResponse.json();

                        if (docsData.success && docsData.documents) {
                            const documentKeys = Object.keys(docsData.documents);
                            const documentsArray = documentKeys.map((docId) => ({
                                id: docId,
                                title: docsData.documents[docId].title,
                                author: docsData.documents[docId].author,
                                chapters: docsData.documents[docId].chapters || 0
                            }));

                            this.displayDocumentLibrary(documentsArray);
                        }
                    } catch (error) {
                        console.error('Error refreshing library:', error);
                    }
                }, 1000);

            } else {
                throw new Error(result.message || 'Upload failed');
            }

        } catch (error) {
            console.error('Upload error:', error);

            const errorText = `Failed to upload "${file.name}": ${error.message}`;

            // Speak error message
            if (window.kokoroSpeak) {
                window.kokoroSpeak(errorText, {}, (sentence, id, word) => {
                    const subtitlesElement = document.getElementById('subtitles');
                    if (subtitlesElement) {
                        if (id !== this.lastSentenceId) {
                            this.lastSentenceId = id;
                            subtitlesElement.textContent = '';
                        }
                        subtitlesElement.textContent += word;
                    }
                });
            }

        } finally {
            // Reset upload button
            if (uploadBtn) {
                uploadBtn.innerHTML = '📤 Upload EPUB File';
                uploadBtn.disabled = false;
            }
        }
    }

    /**
     * Show upload progress messages to indicate processing
     * @param {HTMLElement} uploadBtn - Upload button element
     * @param {string} filename - Name of file being uploaded
     */
    showUploadProgress(uploadBtn, filename) {
        const messages = [
            '⚙️ Processing EPUB file...',
            '⚙️ Extracting chapters...',
            '⚙️ Creating chunks...',
            '⚙️ Storing in memory...',
            '⚙️ Building search index...'
        ];

        let messageIndex = 0;
        const interval = setInterval(() => {
            if (uploadBtn && uploadBtn.disabled) {
                uploadBtn.innerHTML = messages[messageIndex % messages.length];
                messageIndex++;
            } else {
                clearInterval(interval);
            }
        }, 2000); // Change message every 2 seconds

        // Store interval ID to clear it later
        this.uploadProgressInterval = interval;
    }

    /**
     * Delete a document
     * @param {string} docId - Document ID to delete
     * @param {string} docTitle - Document title for confirmation
     */
    async deleteDocument(docId, docTitle) {
        // Show confirmation dialog
        if (!confirm(`Are you sure you want to delete "${docTitle}"?\n\nThis action cannot be undone.`)) {
            return;
        }

        try {
            // Call backend delete API
            const response = await fetch('/api/documents/delete', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ document_id: docId })
            });

            const result = await response.json();

            if (result.success) {
                // Success - refresh the library
                const responseText = `Deleted "${docTitle}" successfully.`;

                // Speak the response
                if (window.kokoroSpeak) {
                    window.kokoroSpeak(responseText, {}, (sentence, id, word) => {
                        const subtitlesElement = document.getElementById('subtitles');
                        if (subtitlesElement) {
                            if (id !== this.lastSentenceId) {
                                this.lastSentenceId = id;
                                subtitlesElement.textContent = '';
                            }
                            subtitlesElement.textContent += word;
                        }
                    });
                }

                // Refresh the document library
                setTimeout(async () => {
                    try {
                        const docsResponse = await fetch('/api/documents/list');
                        const docsData = await docsResponse.json();

                        if (docsData.success && docsData.documents) {
                            const documentKeys = Object.keys(docsData.documents);
                            const documentsArray = documentKeys.map((docId) => ({
                                id: docId,
                                title: docsData.documents[docId].title,
                                author: docsData.documents[docId].author,
                                chapters: docsData.documents[docId].chapters || 0
                            }));

                            this.displayDocumentLibrary(documentsArray);
                        } else {
                            // No documents left - show empty library
                            this.displayDocumentLibrary([]);
                        }
                    } catch (error) {
                        console.error('Error refreshing library after deletion:', error);
                    }
                }, 1000);

            } else {
                throw new Error(result.message || 'Delete failed');
            }

        } catch (error) {
            console.error('Delete error:', error);

            const errorText = `Failed to delete "${docTitle}": ${error.message}`;

            // Speak error message
            if (window.kokoroSpeak) {
                window.kokoroSpeak(errorText, {}, (sentence, id, word) => {
                    const subtitlesElement = document.getElementById('subtitles');
                    if (subtitlesElement) {
                        if (id !== this.lastSentenceId) {
                            this.lastSentenceId = id;
                            subtitlesElement.textContent = '';
                        }
                        subtitlesElement.textContent += word;
                    }
                });
            }
        }
    }

    /**
     * Escape HTML
     * @param {string} text - Text to escape
     * @returns {string} Escaped text
     */
    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Export for global use
window.DocumentWidget = DocumentWidget;

// Initialize document widget when page loads
document.addEventListener('DOMContentLoaded', function () {
    window.documentWidget = new DocumentWidget();
});
