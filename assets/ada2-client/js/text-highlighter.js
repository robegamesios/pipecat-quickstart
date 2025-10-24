/**
 * Reusable Text Highlighter Module for ADA2
 * Provides synchronized text highlighting during TTS playback
 * Used by both document widget and chat widget
 */

class TextHighlighter {
    constructor(options = {}) {
        this.textSegments = [];
        this.currentHighlightIndex = -1;
        this.isInitialized = false;
        this.fullText = '';
        this.currentReadingPosition = 0;
        this.subtitleObserver = null;
        
        // Configurable options
        this.highlightDelay = options.highlightDelay || 1000;
        this.enableBookmarks = options.enableBookmarks || false;
        this.onBookmarkSet = options.onBookmarkSet || null;
        this.onProgressUpdate = options.onProgressUpdate || null;
        this.enableClickableSegments = options.enableClickableSegments || false;
    }

    /**
     * Initialize text structure for highlighting
     * @param {HTMLElement} textElement - The element containing the text
     * @param {string} fullText - The full text content
     */
    initializeTextStructure(textElement, fullText) {
        this.fullText = fullText;

        if (this.isInitialized) {
            this.clearAllHighlights();
            return;
        }

        // Split text into segments for highlighting
        const segments = this.splitTextIntoSegments(fullText);

        // Build HTML structure with spans
        const structuredHTML = segments.map((segment, index) => {
            const escapedText = this.escapeHtml(segment.text);
            const clickableClass = this.enableClickableSegments ? ' clickable-segment' : '';
            return `<span class="text-segment${clickableClass}" data-segment-index="${index}" data-start-pos="${segment.startPos}" data-end-pos="${segment.endPos}">${escapedText}</span>`;
        }).join('');

        textElement.innerHTML = structuredHTML;

        // Store references to all spans
        this.textSegments = Array.from(textElement.querySelectorAll('.text-segment'));
        this.isInitialized = true;
        this.currentReadingPosition = 0;
        this.currentHighlightIndex = -1;

        // Add click event listeners for bookmark setting if enabled
        if (this.enableClickableSegments) {
            this.addClickListeners();
        }
    }

    /**
     * Split text into segments for highlighting
     * @param {string} text - The text to split
     * @returns {Array} Array of text segments with positions
     */
    splitTextIntoSegments(text) {
        const segments = [];
        let currentPos = 0;

        // Split by words and punctuation
        const parts = text.split(/(\s+|[.!?;:,]+)/);

        for (const part of parts) {
            if (part.length > 0) {
                segments.push({
                    text: part,
                    startPos: currentPos,
                    endPos: currentPos + part.length
                });
                currentPos += part.length;
            }
        }

        return segments;
    }

    /**
     * Highlight text progressively based on the subtitle phrase.
     * First tries progressive phrase alignment (only highlight spoken portion
     * of the sentence so far). Falls back to word alignment if needed.
     * @param {string} searchText
     * @returns {boolean}
     */
    highlightText(searchText) {
        if (!searchText || !this.isInitialized) {
            return false;
        }
        // Progressive phrase highlight (partial sentence up to current fragment)
        if (this.highlightPhraseProgressive(searchText)) {
            return true;
        }
        // Fallback to word-based alignment
        const cleanSearchText = searchText.replace(/[^\w\s]/g, ' ').toLowerCase().trim();
        if (cleanSearchText.length < 2) return false;
        const matchIndex = this.findNextMatch(cleanSearchText);
        if (matchIndex === -1) return false;
        this.applySpanHighlightRange(matchIndex, matchIndex);
        return true;
    }

    /**
     * Attempt to highlight only the already-spoken portion of a sentence.
     * Maps the current subtitle fragment to full text, expands start to
     * sentence boundary but clamps end to the end of the fragment.
     * @param {string} phrase
     * @returns {boolean}
     */
    highlightPhraseProgressive(phrase) {
        try {
            const text = String(phrase || '').replace(/\s+/g, ' ').trim();
            if (!text) return false;
            const full = String(this.fullText || '');
            if (!full) return false;

            const fullLower = full.toLowerCase();
            // Build a robust fragment from the phrase
            let fragment = text.toLowerCase();
            // Keep a middle-sized fragment ~30-80 chars to locate
            if (fragment.length > 120) fragment = fragment.slice(0, 120);
            if (fragment.length < 20) {
                // Augment with nearby words: take last 4 words
                const words = fragment.split(' ').filter(Boolean);
                fragment = words.slice(-6).join(' ');
            }
            if (!fragment || fragment.length < 4) return false;

            // Search near current position first, with small backoff window
            const startSearch = Math.max(0, this.currentReadingPosition - 100);
            let idx = fullLower.indexOf(fragment, startSearch);
            if (idx === -1) {
                // Fallback: global search
                idx = fullLower.indexOf(fragment);
                if (idx === -1) return false;
            }

            let startIdx = idx;
            let endIdx = idx + fragment.length; // clamp to fragment

            // Expand to sentence boundaries
            const punct = /[.!?]/;
            // backtrack to previous boundary
            for (let i = startIdx - 1; i >= 0; i--) {
                const ch = full[i];
                if (punct.test(ch)) { startIdx = i + 1; break; }
                if (i < startIdx - 200) break;
            }
            // We deliberately do NOT advance endIdx to the full sentence end;
            // we keep it at the end of the current subtitle fragment to avoid
            // highlighting unreached words.

            // Map character range -> span index range
            let firstSpan = -1; let lastSpan = -1;
            for (let i = 0; i < this.textSegments.length; i++) {
                const span = this.textSegments[i];
                const s = parseInt(span.dataset.startPos);
                const e = parseInt(span.dataset.endPos);
                if (firstSpan === -1 && e > startIdx) firstSpan = i;
                if (s < endIdx) lastSpan = i; else break;
            }
            if (firstSpan === -1 || lastSpan === -1) return false;
            this.applySpanHighlightRange(firstSpan, lastSpan);
            // Update reading position to end of phrase
            this.currentReadingPosition = endIdx;
            return true;
        } catch (e) {
            return false;
        }
    }

    /**
     * Apply highlight styling across a span index range and scroll into view.
     * @param {number} firstIdx
     * @param {number} lastIdx
     */
    applySpanHighlightRange(firstIdx, lastIdx) {
        // Clear previous highlights
        for (let i = 0; i < this.textSegments.length; i++) {
            const span = this.textSegments[i];
            if (i < firstIdx) {
                span.className = span.className.replace(/\b(current-reading-text|unread-text|current-position-text)\b/g, '').trim() + ' read-text';
            } else if (i >= firstIdx && i <= lastIdx) {
                span.className = span.className.replace(/\b(read-text|unread-text|current-position-text)\b/g, '').trim() + ' current-reading-text';
            } else {
                span.className = span.className.replace(/\b(read-text|current-reading-text|current-position-text)\b/g, '').trim() + ' unread-text';
            }
        }
        this.currentHighlightIndex = firstIdx;
        this.scrollToHighlight();
        if (this.onProgressUpdate) this.onProgressUpdate(this.getProgress());
    }

    /**
     * Find next matching segment
     * @param {string} searchText - Text to search for
     * @returns {number} Index of matching segment or -1
     */
    findNextMatch(searchText) {
        const searchWords = searchText.split(/\s+/).filter(word => word.length > 1);

        // Start searching from current position
        const startIndex = Math.max(0, this.currentHighlightIndex - 1);

        for (let i = startIndex; i < this.textSegments.length; i++) {
            const span = this.textSegments[i];
            const spanText = span.textContent.toLowerCase();

            // Check if any search words match this span
            for (const word of searchWords) {
                if (spanText.includes(word) && word.length > 2) {
                    const spanStart = parseInt(span.dataset.startPos);

                    // Only accept matches at or after current reading position
                    if (spanStart >= this.currentReadingPosition - 50) {
                        return i;
                    }
                }
            }
        }

        return -1;
    }

    /**
     * Scroll to highlighted text
     */
    scrollToHighlight() {
        if (this.currentHighlightIndex >= 0 && this.textSegments[this.currentHighlightIndex]) {
            const highlightElement = this.textSegments[this.currentHighlightIndex];
            highlightElement.scrollIntoView({
                behavior: 'smooth',
                block: 'center',
                inline: 'nearest'
            });
        }
    }

    /**
     * Clear all highlights
     */
    clearAllHighlights() {
        for (const span of this.textSegments) {
            span.className = span.className.replace(/\b(read-text|current-reading-text|current-position-text)\b/g, '').trim() + ' unread-text';
        }
        this.currentHighlightIndex = -1;
    }

    /**
     * Add click event listeners to text segments for bookmark setting
     */
    addClickListeners() {
        this.textSegments.forEach((segment, index) => {
            segment.addEventListener('click', (event) => {
                event.preventDefault();
                this.setBookmarkAtSegment(index);
            });
        });
    }

    /**
     * Set bookmark at a specific text segment
     * @param {number} segmentIndex - Index of the clicked segment
     */
    setBookmarkAtSegment(segmentIndex) {
        if (segmentIndex < 0 || segmentIndex >= this.textSegments.length) {
            return;
        }

        const segment = this.textSegments[segmentIndex];
        const position = parseInt(segment.dataset.startPos);

        // Update reading position
        this.currentReadingPosition = position;

        // Notify bookmark set callback if provided
        if (this.onBookmarkSet) {
            this.onBookmarkSet(position, segmentIndex);
        }

        // Apply visual feedback
        this.showBookmarkSetFeedback(segment);

        // Update visual progress
        this.applyReadingProgress();
    }

    /**
     * Show visual feedback when bookmark is set
     * @param {HTMLElement} segment - The clicked segment
     */
    showBookmarkSetFeedback(segment) {
        // Add temporary feedback class
        segment.classList.add('bookmark-set-feedback');

        // Remove feedback after animation
        setTimeout(() => {
            segment.classList.remove('bookmark-set-feedback');
        }, 1000);
    }

    /**
     * Apply visual progress based on current reading position
     * Dims text that has already been read
     */
    applyReadingProgress() {
        if (!this.isInitialized || this.textSegments.length === 0) {
            return;
        }

        // Find the segment that corresponds to the current reading position
        let progressIndex = -1;

        for (let i = 0; i < this.textSegments.length; i++) {
            const span = this.textSegments[i];
            const segmentStart = parseInt(span.dataset.startPos);

            if (segmentStart <= this.currentReadingPosition) {
                progressIndex = i;
            } else {
                break;
            }
        }

        // Apply styling based on reading progress
        for (let i = 0; i < this.textSegments.length; i++) {
            const span = this.textSegments[i];

            if (i < progressIndex) {
                // Already read - dim it
                span.className = span.className.replace(/\b(current-reading-text|unread-text|current-position-text)\b/g, '').trim() + ' read-text';
            } else if (i === progressIndex) {
                // Current position - mark as ready to read
                span.className = span.className.replace(/\b(current-reading-text|read-text|unread-text)\b/g, '').trim() + ' current-position-text';
            } else {
                // Not yet read - normal styling
                span.className = span.className.replace(/\b(current-reading-text|read-text|current-position-text)\b/g, '').trim() + ' unread-text';
            }
        }

        // Scroll to current reading position
        if (progressIndex >= 0 && this.textSegments[progressIndex]) {
            this.textSegments[progressIndex].scrollIntoView({
                behavior: 'smooth',
                block: 'center',
                inline: 'nearest'
            });
        }
    }

    /**
     * Start monitoring subtitles for highlighting
     * @param {HTMLElement} subtitlesElement - The subtitles element to monitor
     */
    startSubtitleMonitoring(subtitlesElement) {
        // Disconnect existing observer
        if (this.subtitleObserver) {
            this.subtitleObserver.disconnect();
        }

        if (!subtitlesElement) {
            console.warn('⚠️ Subtitles element not found');
            return;
        }

        // Create mutation observer to watch for subtitle changes
        this.subtitleObserver = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                if (mutation.type === 'childList' || mutation.type === 'characterData') {
                    const subtitleText = subtitlesElement.textContent.trim();

                    if (subtitleText && this.isInitialized) {
                        // Queue highlighting with delay
                        setTimeout(() => {
                            this.highlightText(subtitleText);
                        }, this.highlightDelay);
                    }
                }
            });
        });

        // Start observing
        this.subtitleObserver.observe(subtitlesElement, {
            childList: true,
            subtree: true,
            characterData: true
        });
    }

    /**
     * Stop monitoring subtitles
     */
    stopSubtitleMonitoring() {
        if (this.subtitleObserver) {
            this.subtitleObserver.disconnect();
            this.subtitleObserver = null;
        }
    }

    /**
     * Reset highlighter state
     */
    reset() {
        try {
            // Visually clear any applied classes before dropping references
            if (this.isInitialized) {
                this.clearAllHighlights();
            }
        } catch(_) {}
        this.stopSubtitleMonitoring();
        this.isInitialized = false;
        this.textSegments = [];
        this.fullText = '';
        this.currentReadingPosition = 0;
        this.currentHighlightIndex = -1;
    }

    /**
     * Get reading progress
     * @returns {Object} Progress information
     */
    getProgress() {
        const totalLength = this.fullText.length;
        const progressPercent = totalLength > 0 ? (this.currentReadingPosition / totalLength * 100).toFixed(1) : 0;

        return {
            position: this.currentReadingPosition,
            totalLength: totalLength,
            progressPercent: progressPercent,
            currentIndex: this.currentHighlightIndex,
            totalSegments: this.textSegments.length
        };
    }

    /**
     * Update reading position (for external bookmark loading)
     * @param {number} position - New reading position
     */
    setReadingPosition(position) {
        this.currentReadingPosition = position;
        this.applyReadingProgress();
    }

    /**
     * Escape HTML
     * @param {string} text - Text to escape
     * @returns {string} Escaped text
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Export for global use
window.TextHighlighter = TextHighlighter;
