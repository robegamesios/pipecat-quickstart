/**
 * Simple Widget Manager - ensures only one widget is open at a time
 */
class WidgetManager {
  constructor() {
    this.currentWidget = null;
  }

  /**
   * Show a widget, closing any currently open widget
   * @param {string} widgetName - Name of the widget being opened
   * @param {Function} showFunction - Function to show the widget
   */
  showWidget(widgetName, showFunction) {
    // Close current widget if there is one and it's different
    if (this.currentWidget && this.currentWidget !== widgetName) {
      this.closeCurrentWidget();
    }
    
    // Show the new widget
    showFunction();
    this.currentWidget = widgetName;
  }

  /**
   * Close the currently open widget
   */
  closeCurrentWidget() {
    if (!this.currentWidget) return;

    // Close the appropriate widget
    switch (this.currentWidget) {
      case 'document':
        if (window.documentWidget && window.documentWidget.isVisible) {
          window.documentWidget.hide();
        }
        break;
      case 'chat':
        if (window.chatWidget && window.chatWidget.isVisible) {
          window.chatWidget.hide();
        }
        break;
      case 'directions':
        if (window.directionsWidget && window.directionsWidget.isVisible) {
          window.directionsWidget.hide();
        }
        break;
    }
    
    this.currentWidget = null;
  }

  /**
   * Mark a widget as closed
   * @param {string} widgetName - Name of widget that was closed
   */
  widgetClosed(widgetName) {
    if (this.currentWidget === widgetName) {
      this.currentWidget = null;
    }
  }
}

// Create global instance
window.widgetManager = new WidgetManager();