"""
Main entry point for SAI - Smart AI Overlay Assistant
"""

import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from .ui import OverlayWidget

def main():
    """Main application entry point"""
    # Enable high DPI scaling
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
    
    # Create application
    app = QApplication(sys.argv)
    app.setApplicationName("SAI - Smart AI Assistant")
    app.setApplicationVersion("0.1.0")
    
    # Create and show overlay
    overlay = OverlayWidget()
    overlay.show()
    
    # Position in top-right corner
    screen = app.primaryScreen().geometry()
    overlay.move(screen.width() - overlay.width() - 50, 50)
    
    print("SAI - Smart AI Overlay Assistant started")
    print("Press Ctrl+C in terminal or close the overlay window to exit")
    
    # Run application
    return app.exec()

if __name__ == "__main__":
    main()