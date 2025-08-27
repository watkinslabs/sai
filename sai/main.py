"""
Main entry point for SAI - Smart AI Overlay Assistant
"""

import sys
import signal
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QTimer

from .ui import OverlayWidget

def main():
    """Main application entry point"""
    # Enable high DPI scaling (for PyQt6 compatibility)
    try:
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
    except AttributeError:
        # These attributes were removed in newer PyQt6 versions
        # High DPI scaling is enabled by default
        pass
    
    # Create application
    app = QApplication(sys.argv)
    app.setApplicationName("SAI - Smart AI Assistant")
    app.setApplicationVersion("0.1.0")
    
    # Set up signal handling for Ctrl+C
    def signal_handler(sig, frame):
        print("\nShutting down SAI...")
        app.quit()
    
    signal.signal(signal.SIGINT, signal_handler)
    
    # Enable processing of signals during Qt event loop
    timer = QTimer()
    timer.start(500)  # Check for signals every 500ms
    timer.timeout.connect(lambda: None)  # Do nothing, just allow signal processing
    
    # Create and show overlay
    overlay = OverlayWidget()
    overlay.show()
    
    # Position in top-right corner
    screen = app.primaryScreen().geometry()
    overlay.move(screen.width() - overlay.width() - 50, 50)
    
    print("SAI - Smart AI Overlay Assistant started")
    print("Press Ctrl+C in terminal or close the overlay window to exit")
    
    # Run application
    try:
        return app.exec()
    except KeyboardInterrupt:
        print("\nShutting down SAI...")
        return 0

if __name__ == "__main__":
    main()