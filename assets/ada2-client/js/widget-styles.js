/**
 * Centralized Widget Styles
 * Shared styling system for all widgets (ChatGPT, Document Library, Map)
 */

window.WidgetStyles = {
  // Main container styles for all widgets
  container: `
    position: fixed;
    top: 0;
    right: 0;
    width: 50vw;
    height: 100vh;
    background: #1e1e1e;
    color: #fff;
    box-shadow: -4px 0 20px rgba(0,0,0,0.15);
    transform: translateX(100%);
    transition: transform 0.3s ease;
    z-index: 1000;
    display: none;
    overflow: hidden;
    font-family: -apple-system, BlinkMacSystemFont, sans-serif;
  `,

  // Header styles for all widgets
  header: `
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
    border-bottom: 1px solid #333;
    padding: 20px 20px 15px 20px;
  `,

  // Title styles for all widgets
  title: `
    margin: 0;
    color: #00d4aa;
    font-size: 18px;
    font-weight: 600;
  `,

  // Close button styles for all widgets
  closeButton: `
    background: none;
    border: none;
    color: #888;
    font-size: 18px;
    cursor: pointer;
    padding: 5px;
    margin-left: auto;
    width: 30px;
    height: 30px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 4px;
    transition: all 0.2s ease;
  `,

  // Content wrapper styles
  contentWrapper: `
    padding: 20px;
    height: 100%;
    display: flex;
    flex-direction: column;
  `,

  // Content area styles
  contentArea: `
    flex: 1;
    overflow-y: auto;
    background: #2d2d2d;
    border-radius: 8px;
    padding: 15px;
    margin-bottom: 15px;
  `
};

/**
 * Apply widget styles to an element
 * @param {HTMLElement} element - The element to style
 * @param {string} styleKey - The style key from WidgetStyles
 */
window.applyWidgetStyle = function(element, styleKey) {
  if (window.WidgetStyles[styleKey]) {
    element.style.cssText = window.WidgetStyles[styleKey];
  }
};

/**
 * Create a standardized widget container
 * @param {string} id - Widget ID
 * @param {string} className - Widget class name
 * @returns {HTMLElement} Configured widget container
 */
window.createWidgetContainer = function(id, className) {
  const container = document.createElement('div');
  container.id = id;
  container.className = className;
  window.applyWidgetStyle(container, 'container');
  return container;
};

/**
 * Create a standardized widget header
 * @param {string} titleText - Header title text
 * @param {Function} onClose - Close button click handler
 * @returns {HTMLElement} Configured header element
 */
window.createWidgetHeader = function(titleText, onClose) {
  const header = document.createElement('div');
  window.applyWidgetStyle(header, 'header');

  const title = document.createElement('h3');
  window.applyWidgetStyle(title, 'title');
  title.textContent = titleText;

  const closeButton = document.createElement('button');
  window.applyWidgetStyle(closeButton, 'closeButton');
  closeButton.innerHTML = '✕';
  closeButton.title = 'Close';
  closeButton.addEventListener('click', onClose);

  // Add hover effect for close button
  closeButton.addEventListener('mouseenter', () => {
    closeButton.style.background = '#333';
    closeButton.style.color = '#fff';
  });
  closeButton.addEventListener('mouseleave', () => {
    closeButton.style.background = 'none';
    closeButton.style.color = '#888';
  });

  header.appendChild(title);
  header.appendChild(closeButton);
  
  return header;
};

/**
 * Create a standardized content wrapper
 * @returns {HTMLElement} Configured content wrapper
 */
window.createContentWrapper = function() {
  const wrapper = document.createElement('div');
  window.applyWidgetStyle(wrapper, 'contentWrapper');
  return wrapper;
};