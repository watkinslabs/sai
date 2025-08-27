"""
UI components for SAI overlay
"""

import json
import os
from datetime import datetime
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, 
    QPushButton, QLabel, QScrollArea, QFrame, QSystemTrayIcon, QMenu,
    QComboBox, QGroupBox, QDialog, QDialogButtonBox, QSlider, QCheckBox,
    QTabWidget, QPlainTextEdit, QSpinBox, QSizeGrip
)
from PyQt6.QtCore import (
    Qt, pyqtSignal, QTimer, QPoint, QSize, QMetaObject, Q_ARG
)
from PyQt6.QtGui import (
    QFont, QPalette, QColor, QPixmap, QIcon, QAction
)

from .config import Config, ConversationEntry, WindowExcluder
from .claude_client import ClaudeClient
from .audio import FastAudioListener, AudioListener, FAST_AUDIO_AVAILABLE
from .ui_updater import UIUpdater

class DraggableFrame(QFrame):
    """A frame that uses compositor-aware dragging"""
    
    def __init__(self, parent_window):
        super().__init__()
        self.parent_window = parent_window
        self.setCursor(Qt.CursorShape.SizeAllCursor)
    
    def mousePressEvent(self, event):
        """Start compositor-aware drag"""
        if event.button() == Qt.MouseButton.LeftButton:
            # Use Qt's native window dragging through compositor
            window_handle = self.parent_window.windowHandle()
            if window_handle:
                print("Starting compositor drag")
                window_handle.startSystemMove()
            event.accept()
    
    def mouseMoveEvent(self, event):
        """Compositor handles the movement"""
        pass
    
    def mouseReleaseEvent(self, event):
        """Compositor handles the release"""
        if event.button() == Qt.MouseButton.LeftButton:
            # Save position when drag ends
            self.parent_window.save_window_position()
            event.accept()

class ConfigDialog(QDialog):
    """Configuration dialog for settings"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Overlay Assistant Settings")
        self.setModal(True)
        self.resize(500, 600)
        
        # Load current settings
        self.settings = getattr(parent, 'settings', Config.get_default_settings())
        self.init_ui()
    
    def init_ui(self):
        """Initialize the UI"""
        layout = QVBoxLayout()
        
        # Apply dark theme styling
        self.setStyleSheet(self.get_dark_theme_style())
        
        # Create tabs
        tabs = QTabWidget()
        
        # Appearance tab
        appearance_tab = QWidget()
        appearance_layout = QVBoxLayout(appearance_tab)
        
        # Font size
        font_group = QGroupBox("Font Size")
        font_layout = QVBoxLayout(font_group)
        
        self.font_slider = QSlider(Qt.Orientation.Horizontal)
        self.font_slider.setRange(8, 24)
        self.font_slider.setValue(self.settings.get('font_size', 12))
        self.font_slider.valueChanged.connect(self.update_font_label)
        
        self.font_label = QLabel(f"Font Size: {self.settings.get('font_size', 12)}px")
        font_layout.addWidget(self.font_label)
        font_layout.addWidget(self.font_slider)
        appearance_layout.addWidget(font_group)
        
        # Window opacity
        opacity_group = QGroupBox("Window Transparency")
        opacity_layout = QVBoxLayout(opacity_group)
        
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(30, 100)
        self.opacity_slider.setValue(int(self.settings.get('opacity', 0.9) * 100))
        self.opacity_slider.valueChanged.connect(self.update_opacity_label)
        
        self.opacity_label = QLabel(f"Opacity: {int(self.settings.get('opacity', 0.9) * 100)}%")
        opacity_layout.addWidget(self.opacity_label)
        opacity_layout.addWidget(self.opacity_slider)
        appearance_layout.addWidget(opacity_group)
        
        # Window size
        size_group = QGroupBox("Window Size")
        size_layout = QVBoxLayout(size_group)
        
        width_layout = QHBoxLayout()
        width_layout.addWidget(QLabel("Width:"))
        self.width_spin = QSpinBox()
        self.width_spin.setRange(400, 1200)
        self.width_spin.setValue(self.settings.get('window_width', 600))
        width_layout.addWidget(self.width_spin)
        size_layout.addLayout(width_layout)
        
        height_layout = QHBoxLayout()
        height_layout.addWidget(QLabel("Height:"))
        self.height_spin = QSpinBox()
        self.height_spin.setRange(300, 800)
        self.height_spin.setValue(self.settings.get('window_height', 400))
        height_layout.addWidget(self.height_spin)
        size_layout.addLayout(height_layout)
        
        appearance_layout.addWidget(size_group)
        
        # Show transcription toggle
        self.show_transcription_cb = QCheckBox("Show transcribed text")
        self.show_transcription_cb.setChecked(self.settings.get('show_transcription', True))
        appearance_layout.addWidget(self.show_transcription_cb)
        
        tabs.addTab(appearance_tab, "Appearance")
        
        # AI Mode tab
        ai_tab = QWidget()
        ai_layout = QVBoxLayout(ai_tab)
        
        # Mode selection
        mode_group = QGroupBox("AI Response Mode")
        mode_layout = QVBoxLayout(mode_group)
        
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["default", "meeting", "learning", "summary", "custom"])
        self.mode_combo.setCurrentText(self.settings.get('mode', 'default'))
        self.mode_combo.currentTextChanged.connect(self.on_mode_changed)
        mode_layout.addWidget(self.mode_combo)
        
        # Mode descriptions
        mode_desc = {
            "default": "General helpful responses (50 words max)",
            "meeting": "Focus on action items and decisions (30 words max)", 
            "learning": "Explanations and insights (40 words max)",
            "summary": "Bullet point summaries (35 words max)",
            "custom": "Use your own prompt template"
        }
        
        self.mode_desc_label = QLabel(mode_desc.get(self.settings.get('mode', 'default'), ''))
        self.mode_desc_label.setWordWrap(True)
        self.mode_desc_label.setStyleSheet("color: #666; font-style: italic;")
        mode_layout.addWidget(self.mode_desc_label)
        
        ai_layout.addWidget(mode_group)
        
        # Template editing
        template_group = QGroupBox("Edit AI Templates")
        template_layout = QVBoxLayout(template_group)
        
        template_layout.addWidget(QLabel("Use {text} for input and {context} for conversation context:"))
        
        # Create tabs for each template
        template_tabs = QTabWidget()
        
        # Dictionary to store template editors
        self.template_editors = {}
        
        # Template types
        template_types = [
            ("default", "Default"),
            ("meeting", "Meeting"), 
            ("learning", "Learning"),
            ("summary", "Summary")
        ]
        
        for template_key, template_name in template_types:
            tab_widget = QWidget()
            tab_layout = QVBoxLayout(tab_widget)
            
            editor = QPlainTextEdit()
            editor.setPlainText(self.settings.get(f'template_{template_key}', ''))
            editor.setMaximumHeight(80)
            editor.setStyleSheet("font-family: 'Courier New', monospace; font-size: 11px;")
            
            tab_layout.addWidget(editor)
            template_tabs.addTab(tab_widget, template_name)
            
            # Store reference for saving
            self.template_editors[template_key] = editor
        
        template_layout.addWidget(template_tabs)
        ai_layout.addWidget(template_group)
        
        # Custom prompt
        custom_group = QGroupBox("Custom Mode Prompt")
        custom_layout = QVBoxLayout(custom_group)
        
        self.custom_prompt_edit = QPlainTextEdit()
        self.custom_prompt_edit.setPlainText(self.settings.get('custom_prompt', ''))
        self.custom_prompt_edit.setMaximumHeight(80)
        self.custom_prompt_edit.setStyleSheet("font-family: 'Courier New', monospace; font-size: 11px;")
        self.custom_prompt_edit.setEnabled(self.settings.get('mode') == 'custom')
        custom_layout.addWidget(self.custom_prompt_edit)
        
        ai_layout.addWidget(custom_group)
        
        tabs.addTab(ai_tab, "AI Settings")
        
        # Performance tab
        perf_tab = QWidget()
        perf_layout = QVBoxLayout(perf_tab)
        
        # Audio processing mode
        audio_group = QGroupBox("Audio Processing")
        audio_layout = QVBoxLayout(audio_group)
        
        self.fast_mode_cb = QCheckBox("Use fast local processing (Whisper + VAD)")
        self.fast_mode_cb.setChecked(self.settings.get('use_fast_mode', True))
        self.fast_mode_cb.setToolTip("Uses local Whisper model with voice activity detection for faster, more responsive transcription")
        audio_layout.addWidget(self.fast_mode_cb)
        
        fallback_label = QLabel("When unchecked, uses Google Speech Recognition (slower but more accurate)")
        fallback_label.setStyleSheet("font-style: italic; color: #666;")
        audio_layout.addWidget(fallback_label)
        
        perf_layout.addWidget(audio_group)
        
        # API settings
        api_group = QGroupBox("API Performance")
        api_layout = QVBoxLayout(api_group)
        
        cache_label = QLabel("Response caching: Enabled (improves speed for repeated queries)")
        cache_label.setStyleSheet("color: #666;")
        api_layout.addWidget(cache_label)
        
        async_label = QLabel("Async processing: Enabled (non-blocking API calls)")
        async_label.setStyleSheet("color: #666;")
        api_layout.addWidget(async_label)
        
        perf_layout.addWidget(api_group)
        
        perf_layout.addStretch()
        
        tabs.addTab(perf_tab, "Performance")
        
        layout.addWidget(tabs)
        
        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        self.setLayout(layout)
    
    def accept(self):
        """Override accept to save template settings"""
        # Save template settings
        if hasattr(self, 'template_editors'):
            for template_key, editor in self.template_editors.items():
                self.settings[f'template_{template_key}'] = editor.toPlainText()
        
        # Update parent settings
        if hasattr(self, 'parent') and self.parent():
            self.parent().settings.update(self.settings)
        
        super().accept()
    
    def update_font_label(self, value):
        """Update font size label"""
        self.font_label.setText(f"Font Size: {value}px")
    
    def update_opacity_label(self, value):
        """Update opacity label"""
        self.opacity_label.setText(f"Opacity: {value}%")
    
    def on_mode_changed(self, mode):
        """Handle AI mode change"""
        mode_desc = {
            "default": "General helpful responses (50 words max)",
            "meeting": "Focus on action items and decisions (30 words max)", 
            "learning": "Explanations and insights (40 words max)",
            "summary": "Bullet point summaries (35 words max)",
            "custom": "Use your own prompt template"
        }
        
        self.mode_desc_label.setText(mode_desc.get(mode, ''))
        self.custom_prompt_edit.setEnabled(mode == 'custom')
    
    def get_dark_theme_style(self):
        """Get dark theme stylesheet"""
        return """
            QDialog {
                background-color: rgba(30, 30, 30, 240);
                color: white;
                border: 1px solid rgba(100, 100, 100, 150);
                border-radius: 8px;
            }
            QTabWidget::pane {
                border: 1px solid rgba(100, 100, 100, 150);
                background-color: rgba(40, 40, 40, 200);
                border-radius: 5px;
            }
            QTabWidget::tab-bar {
                alignment: center;
            }
            QTabBar::tab {
                background-color: rgba(60, 60, 60, 180);
                color: white;
                padding: 8px 16px;
                margin-right: 2px;
                border: 1px solid rgba(100, 100, 100, 150);
                border-bottom: none;
                border-radius: 5px 5px 0 0;
            }
            QTabBar::tab:selected {
                background-color: rgba(40, 40, 40, 200);
                border-bottom: 1px solid rgba(40, 40, 40, 200);
            }
            QTabBar::tab:hover {
                background-color: rgba(80, 80, 80, 200);
            }
            QGroupBox {
                font-weight: bold;
                color: #cccccc;
                border: 1px solid rgba(100, 100, 100, 150);
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 5px;
                background-color: rgba(50, 50, 50, 100);
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: white;
            }
            QLabel {
                color: #cccccc;
            }
            QSlider::groove:horizontal {
                border: 1px solid rgba(100, 100, 100, 150);
                height: 6px;
                background: rgba(20, 20, 20, 200);
                margin: 2px 0;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: rgba(0, 150, 255, 200);
                border: 1px solid rgba(100, 100, 100, 150);
                width: 14px;
                margin: -5px 0;
                border-radius: 7px;
            }
            QSlider::handle:horizontal:hover {
                background: rgba(0, 180, 255, 255);
            }
            QComboBox {
                background-color: rgba(60, 60, 60, 180);
                color: white;
                border: 1px solid rgba(100, 100, 100, 150);
                border-radius: 3px;
                padding: 5px;
                min-height: 20px;
            }
            QComboBox::drop-down {
                background-color: rgba(80, 80, 80, 200);
                border: none;
                border-radius: 3px;
            }
            QComboBox::down-arrow {
                image: none;
                border: none;
            }
            QComboBox QAbstractItemView {
                background-color: rgba(60, 60, 60, 240);
                color: white;
                selection-background-color: rgba(0, 150, 255, 150);
                border: 1px solid rgba(100, 100, 100, 150);
            }
            QTextEdit, QPlainTextEdit {
                background-color: rgba(50, 50, 50, 180);
                color: white;
                border: 1px solid rgba(100, 100, 100, 150);
                border-radius: 3px;
                padding: 5px;
            }
            QSpinBox {
                background-color: rgba(60, 60, 60, 180);
                color: white;
                border: 1px solid rgba(100, 100, 100, 150);
                border-radius: 3px;
                padding: 2px;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                background-color: rgba(80, 80, 80, 200);
                border: 1px solid rgba(100, 100, 100, 150);
            }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                background-color: rgba(100, 100, 100, 200);
            }
            QCheckBox {
                spacing: 8px;
                color: white;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 1px solid rgba(100, 100, 100, 150);
                border-radius: 3px;
                background-color: rgba(60, 60, 60, 180);
            }
            QCheckBox::indicator:checked {
                background-color: rgba(0, 150, 255, 200);
            }
            QCheckBox::indicator:hover {
                background-color: rgba(80, 80, 80, 200);
            }
            QPushButton {
                background-color: rgba(60, 60, 60, 180);
                color: white;
                border: 1px solid rgba(100, 100, 100, 150);
                border-radius: 3px;
                padding: 5px 15px;
            }
            QPushButton:hover {
                background-color: rgba(80, 80, 80, 200);
            }
            QPushButton:pressed {
                background-color: rgba(40, 40, 40, 200);
            }
        """

class OverlayWidget(QWidget):
    """Main overlay widget"""
    
    def __init__(self):
        super().__init__()
        self.settings_file = Path.home() / ".overlay_assistant_settings.json"
        self.data_file = Path.home() / ".overlay_assistant_data.json"
        
        # Load settings and data
        self.settings = self.load_settings()
        self.conversation_history = self.load_conversation_history()
        
        # Initialize components
        self.claude_client = None
        self.audio_listener = None
        self.mic_enabled = True
        
        self.init_ui()
        self.init_claude_client()
        
        # Initialize UI updater BEFORE audio to avoid threading issues
        self.ui_updater = UIUpdater(self)
        
        # Initialize system tray
        self.init_system_tray()
        
        self.init_audio()
    
    def init_system_tray(self):
        """Initialize system tray icon"""
        # Check if system tray is available
        if not QSystemTrayIcon.isSystemTrayAvailable():
            print("System tray not available")
            return
            
        # Create tray icon
        self.tray_icon = QSystemTrayIcon(self)
        
        # Create a simple icon (you could use a proper icon file instead)
        pixmap = QPixmap(16, 16)
        pixmap.fill(QColor(0, 255, 0))  # Green square
        self.tray_icon.setIcon(QIcon(pixmap))
        
        # Create tray menu
        tray_menu = QMenu()
        
        # Show/Hide action
        self.show_action = QAction("Show SAI", self)
        self.show_action.triggered.connect(self.show_from_tray)
        tray_menu.addAction(self.show_action)
        
        # Toggle microphone action
        self.mic_action = QAction("Toggle Microphone", self)
        self.mic_action.triggered.connect(self.toggle_microphone)
        tray_menu.addAction(self.mic_action)
        
        tray_menu.addSeparator()
        
        # Quit action
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.quit_application)
        tray_menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        
        # Handle tray icon activation (double-click)
        self.tray_icon.activated.connect(self.on_tray_activated)
        
        # Show tray icon
        self.tray_icon.show()
        
        # Update tooltip
        self.tray_icon.setToolTip("SAI - Smart AI Assistant")
        
    def show_from_tray(self):
        """Show window from system tray"""
        self.show()
        self.raise_()
        self.activateWindow()
        
    def on_tray_activated(self, reason):
        """Handle tray icon activation"""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            if self.isVisible():
                self.hide()
            else:
                self.show_from_tray()
                
    def quit_application(self):
        """Properly quit the application"""
        if hasattr(self, 'tray_icon'):
            self.tray_icon.hide()
        self.close()
        QApplication.quit()
    
    def hide_to_tray(self):
        """Hide window to system tray"""
        if hasattr(self, 'tray_icon') and self.tray_icon.isVisible():
            self.hide()
            # Show tray notification
            if hasattr(self.tray_icon, 'showMessage'):
                self.tray_icon.showMessage(
                    "SAI Hidden",
                    "SAI is still running in the system tray. Double-click to restore.",
                    QSystemTrayIcon.MessageIcon.Information,
                    3000
                )
        else:
            # Fallback to regular hide if tray not available
            self.hide()
    
    def load_settings(self):
        """Load settings from file"""
        try:
            if self.settings_file.exists():
                with open(self.settings_file, 'r') as f:
                    loaded_settings = json.load(f)
                    # Merge with defaults
                    settings = Config.get_default_settings()
                    settings.update(loaded_settings)
                    return settings
        except Exception as e:
            print(f"Error loading settings: {e}")
        
        return Config.get_default_settings()
    
    def save_settings(self):
        """Save settings to file"""
        try:
            with open(self.settings_file, 'w') as f:
                json.dump(self.settings, f, indent=2)
        except Exception as e:
            print(f"Error saving settings: {e}")
    
    def load_conversation_history(self):
        """Load conversation history from file"""
        try:
            if self.data_file.exists():
                with open(self.data_file, 'r') as f:
                    data = json.load(f)
                    history = []
                    for entry_data in data.get('conversation_history', []):
                        timestamp = datetime.fromisoformat(entry_data['timestamp'])
                        entry = ConversationEntry(
                            timestamp, 
                            entry_data['transcription'], 
                            entry_data['ai_response']
                        )
                        history.append(entry)
                    return history
        except Exception as e:
            print(f"Error loading conversation history: {e}")
        
        return []
    
    def save_conversation_history(self):
        """Save conversation history to file"""
        try:
            data = {
                'conversation_history': [entry.to_dict() for entry in self.conversation_history]
            }
            with open(self.data_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving conversation history: {e}")
    
    def init_ui(self):
        """Initialize the user interface"""
        # Set window properties - hide from taskbar
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Set size and restore position if saved
        self.resize(self.settings['window_width'], self.settings['window_height'])
        self.restore_window_position()
        
        # Create layout
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Title bar with controls
        title_bar = self.create_title_bar()
        layout.addWidget(title_bar)
        
        # Main content
        content_frame = QFrame()
        content_frame.setStyleSheet("""
            QFrame {
                background-color: rgba(20, 20, 20, 200);
                border-radius: 8px;
                border: 1px solid rgba(100, 100, 100, 100);
            }
        """)
        
        content_layout = QVBoxLayout(content_frame)
        
        # Current transcription area
        self.transcription_area = QTextEdit()
        self.transcription_area.setPlaceholderText("Listening for speech...")
        self.transcription_area.setMaximumHeight(60)
        self.transcription_area.setStyleSheet("""
            QTextEdit {
                background-color: rgba(10, 10, 10, 200);
                color: #00ff00;
                border: 1px solid rgba(0, 255, 0, 100);
                border-radius: 5px;
                padding: 8px;
                font-family: 'Courier New', monospace;
                font-size: 12px;
            }
        """)
        content_layout.addWidget(self.transcription_area)
        
        # Response area with status indicators
        response_header = QHBoxLayout()
        response_header.addWidget(QLabel("AI Response:"))
        
        # Status indicators
        self.whisper_status = QLabel("🎤")
        self.whisper_status.setStyleSheet("color: #666; font-size: 16px;")
        self.whisper_status.setToolTip("Speech recognition status")
        
        self.ai_status = QLabel("🤖")
        self.ai_status.setStyleSheet("color: #666; font-size: 16px;")
        self.ai_status.setToolTip("AI processing status")
        
        response_header.addStretch()
        response_header.addWidget(self.whisper_status)
        response_header.addWidget(self.ai_status)
        
        content_layout.addLayout(response_header)
        
        # Current response
        self.current_response = QTextEdit()
        self.current_response.setPlaceholderText("AI responses will appear here...")
        self.current_response.setMaximumHeight(80)
        self.current_response.setStyleSheet("""
            QTextEdit {
                background-color: rgba(5, 5, 15, 220);
                color: #00ccff;
                border: 1px solid rgba(0, 200, 255, 120);
                border-radius: 5px;
                padding: 8px;
                font-family: 'Courier New', monospace;
                font-size: 12px;
            }
            QTextEdit::placeholder {
                color: rgba(0, 200, 255, 100);
            }
        """)
        content_layout.addWidget(self.current_response)
        
        # Question input area
        question_label = QLabel("Ask a Question:")
        question_label.setStyleSheet("color: #00ff88; font-weight: bold; margin-top: 10px;")
        content_layout.addWidget(question_label)
        
        question_layout = QHBoxLayout()
        self.question_input = QTextEdit()
        self.question_input.setPlaceholderText("Type your question here...")
        self.question_input.setMaximumHeight(60)
        self.question_input.setStyleSheet("""
            QTextEdit {
                background-color: rgba(10, 10, 20, 200);
                color: #00ffff;
                border: 1px solid rgba(0, 255, 255, 100);
                border-radius: 5px;
                padding: 8px;
                font-family: 'Courier New', monospace;
                font-size: 12px;
            }
            QTextEdit::placeholder {
                color: rgba(0, 255, 255, 100);
            }
        """)
        
        # Handle Enter key for question input
        def handle_question_key_press(event):
            if event.key() == Qt.Key.Key_Return and not event.modifiers():
                self.ask_question()
                event.accept()
            else:
                QTextEdit.keyPressEvent(self.question_input, event)
        
        self.question_input.keyPressEvent = handle_question_key_press
        question_layout.addWidget(self.question_input)
        
        self.ask_btn = QPushButton("Ask")
        self.ask_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(0, 255, 128, 150);
                color: white;
                border-radius: 5px;
                font-weight: bold;
                font-size: 12px;
                padding: 5px 15px;
            }
            QPushButton:hover {
                background-color: rgba(0, 255, 128, 200);
            }
        """)
        self.ask_btn.setFixedHeight(60)
        self.ask_btn.clicked.connect(self.ask_question)
        question_layout.addWidget(self.ask_btn)
        
        content_layout.addLayout(question_layout)
        
        # Timeline
        timeline_label = QLabel("Timeline:")
        content_layout.addWidget(timeline_label)
        
        self.timeline_scroll = QScrollArea()
        self.timeline_scroll.setStyleSheet("""
            QScrollArea {
                background-color: rgba(5, 5, 5, 180);
                border: 1px solid rgba(0, 255, 0, 80);
                border-radius: 5px;
            }
            QScrollBar:vertical {
                background: rgba(20, 20, 20, 200);
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background: rgba(0, 255, 0, 150);
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(0, 255, 0, 200);
            }
        """)
        self.timeline_widget = QWidget()
        self.timeline_layout = QVBoxLayout(self.timeline_widget)
        self.timeline_scroll.setWidget(self.timeline_widget)
        self.timeline_scroll.setWidgetResizable(True)
        content_layout.addWidget(self.timeline_scroll)
        
        # Control buttons
        button_layout = QHBoxLayout()
        
        self.export_btn = QPushButton("Export")
        self.export_btn.setStyleSheet("background-color: rgba(0, 150, 255, 150); color: white; border-radius: 3px; padding: 5px;")
        self.export_btn.clicked.connect(self.export_data)
        
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setStyleSheet("background-color: rgba(255, 150, 0, 150); color: white; border-radius: 3px; padding: 5px;")
        self.clear_btn.clicked.connect(self.clear_timeline)
        
        button_layout.addWidget(self.export_btn)
        button_layout.addWidget(self.clear_btn)
        content_layout.addLayout(button_layout)
        
        layout.addWidget(content_frame)
        
        # Add visible resize grip
        size_grip = QSizeGrip(self)
        size_grip.setStyleSheet("""
            QSizeGrip {
                background-color: rgba(0, 255, 0, 100);
                border: 1px solid rgba(0, 255, 0, 150);
                border-radius: 3px;
                width: 16px;
                height: 16px;
            }
            QSizeGrip:hover {
                background-color: rgba(0, 255, 0, 150);
            }
        """)
        grip_layout = QHBoxLayout()
        grip_layout.addStretch()
        grip_layout.addWidget(size_grip)
        layout.addLayout(grip_layout)
        
        self.setLayout(layout)
        
        # Apply window opacity and styles
        self.setWindowOpacity(self.settings['opacity'])
        self.drag_position = QPoint()
        self.dragging = False
        self.update_styles()
        
        # Set global dark theme for context menus
        self.setStyleSheet(self.get_global_dark_theme())
    
    
    def restore_window_position(self):
        """Restore saved window position"""
        if self.settings.get('window_x') is not None and self.settings.get('window_y') is not None:
            x = self.settings['window_x']
            y = self.settings['window_y']
            print(f"Restoring window position to ({x}, {y})")
            
            # Try to restore position after window is shown
            QTimer.singleShot(100, lambda: self.move(x, y))
        else:
            print("No saved position to restore")
    
    def save_window_position(self):
        """Save current window position"""
        pos = self.pos()
        self.settings['window_x'] = pos.x()
        self.settings['window_y'] = pos.y()
        print(f"Saving window position: ({pos.x()}, {pos.y()})")
        self.save_settings()
    
    def moveEvent(self, event):
        """Called when window is moved - save position"""
        super().moveEvent(event)
        # Save position when window moves (with small delay to avoid spam)
        if hasattr(self, '_move_timer'):
            self._move_timer.stop()
        
        self._move_timer = QTimer()
        self._move_timer.setSingleShot(True)
        self._move_timer.timeout.connect(self.save_window_position)
        self._move_timer.start(1000)  # Save after 1 second of no movement
    
    def keyPressEvent(self, event):
        """Handle keyboard shortcuts"""
        if event.key() == Qt.Key.Key_Space:
            self.toggle_microphone()
            event.accept()
        else:
            super().keyPressEvent(event)
    
    def toggle_microphone(self):
        """Toggle microphone on/off"""
        try:
            # Check if currently enabled by looking at audio listener state
            currently_enabled = self.audio_listener is not None and hasattr(self, 'mic_enabled') and self.mic_enabled
            
            if currently_enabled:
                # Turn off microphone
                self.mic_enabled = False
                if self.audio_listener:
                    self.audio_listener.stop()
                    self.audio_listener.wait()
                    self.audio_listener = None
                
                # Update button appearance
                self.mic_toggle_btn.setText("🔇")
                self.mic_toggle_btn.setStyleSheet("""
                    QPushButton {
                        background-color: rgba(255, 0, 0, 150);
                        color: white;
                        border-radius: 10px;
                        font-weight: bold;
                        font-size: 12px;
                    }
                    QPushButton:hover {
                        background-color: rgba(255, 0, 0, 200);
                    }
                """)
                self.mic_toggle_btn.setToolTip("Turn On Microphone (Space)")
                
                # Update UI
                if hasattr(self, 'ui_updater'):
                    self.ui_updater.request_update("update_whisper_status", status="disabled")
                    self.ui_updater.request_update("display_transcription", text="Microphone disabled")
                
                print("Microphone turned OFF")
            else:
                # Turn on microphone
                self.mic_enabled = True
                self.init_audio()
                
                # Update button appearance
                self.mic_toggle_btn.setText("🎤")
                self.mic_toggle_btn.setStyleSheet("""
                    QPushButton {
                        background-color: rgba(0, 255, 0, 150);
                        color: white;
                        border-radius: 10px;
                        font-weight: bold;
                        font-size: 12px;
                    }
                    QPushButton:hover {
                        background-color: rgba(0, 255, 0, 200);
                    }
                """)
                self.mic_toggle_btn.setToolTip("Turn Off Microphone (Space)")
                
                print("Microphone turned ON")
                
        except Exception as e:
            print(f"Error toggling microphone: {e}")
    
    def ask_question(self):
        """Process question from input area"""
        question_text = self.question_input.toPlainText().strip()
        if not question_text:
            return
            
        print(f"Processing question: {question_text}")
        
        # Clear the input
        self.question_input.clear()
        
        # Send to Claude processing
        if hasattr(self, 'ui_updater') and self.ui_updater:
            self.ui_updater.request_update("claude_processing", text=question_text)
    
    def show_system_audio_info(self):
        """Show information about available system audio capture options"""
        try:
            from PyQt6.QtWidgets import QMessageBox
            from .audio import FastAudioListener
            
            system_devices = FastAudioListener.get_system_audio_info()
            
            if not system_devices:
                info_text = """No system audio capture devices found.

To capture system audio, you may need to:

• Linux: Install and configure PulseAudio
  - Run: pactl load-module module-loopback
  - Or enable monitor devices in pavucontrol

• Windows: Enable "Stereo Mix" in Sound settings
  - Right-click speaker icon → Sounds → Recording
  - Right-click → Show Disabled Devices
  - Enable "Stereo Mix" or "What U Hear"

• macOS: Requires third-party tools like:
  - BlackHole (free virtual audio driver)
  - Loopback (paid audio routing tool)"""
            else:
                info_text = f"Found {len(system_devices)} system audio device(s):\n\n"
                for device in system_devices:
                    info_text += f"• {device['name']}\n"
                    info_text += f"  Channels: {device['channels']}, Rate: {int(device['sample_rate'])}Hz\n\n"
                info_text += "Select one from the audio source dropdown to capture system audio."
            
            msg = QMessageBox(self)
            msg.setWindowTitle("System Audio Capture Info")
            msg.setText(info_text)
            msg.setIcon(QMessageBox.Icon.Information)
            msg.exec()
            
        except Exception as e:
            print(f"Error showing system audio info: {e}")
            if hasattr(self, 'current_response'):
                self.current_response.setText(f"Error: {str(e)}")
    
    def create_title_bar(self):
        """Create the title bar with controls"""
        title_frame = DraggableFrame(self)
        title_frame.setStyleSheet("""
            QFrame {
                background-color: rgba(40, 40, 40, 180);
                border-radius: 6px;
                border: 1px solid rgba(120, 120, 120, 100);
            }
        """)
        title_frame.setFixedHeight(35)
        
        title_layout = QHBoxLayout(title_frame)
        title_layout.setContentsMargins(10, 5, 10, 5)
        
        # Title (drag area)
        title_label = QLabel("SAI - Smart AI Assistant")
        title_label.setStyleSheet("color: white; font-weight: bold; font-size: 11px;")
        title_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        title_layout.addWidget(title_label)
        
        # Audio source selector (includes system audio)
        self.mic_selector = QComboBox()
        self.mic_selector.setStyleSheet("""
            QComboBox {
                background-color: rgba(60, 60, 60, 180);
                color: white;
                border: 1px solid rgba(100, 100, 100, 150);
                border-radius: 3px;
                padding: 2px 5px;
                min-width: 150px;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                color: white;
            }
        """)
        self.mic_selector.currentIndexChanged.connect(self.on_microphone_changed)
        title_layout.addWidget(self.mic_selector)
        
        # Populate audio source list
        self.populate_microphone_list()
        
        # System audio info button
        audio_info_btn = QPushButton("🔊")
        audio_info_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(0, 200, 255, 150);
                color: white;
                border-radius: 8px;
                font-weight: bold;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: rgba(0, 220, 255, 200);
            }
        """)
        audio_info_btn.setFixedSize(16, 20)
        audio_info_btn.setToolTip("Show System Audio Info")
        audio_info_btn.clicked.connect(self.show_system_audio_info)
        title_layout.addWidget(audio_info_btn)
        
        title_layout.addStretch()
        
        # Mic toggle button
        self.mic_toggle_btn = QPushButton("🎤")
        self.mic_toggle_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(0, 255, 0, 150);
                color: white;
                border-radius: 10px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: rgba(0, 255, 0, 200);
            }
        """)
        self.mic_toggle_btn.setFixedSize(25, 20)
        self.mic_toggle_btn.setToolTip("Toggle Microphone (Space)")
        self.mic_toggle_btn.clicked.connect(self.toggle_microphone)
        title_layout.addWidget(self.mic_toggle_btn)
        
        # Config button
        config_btn = QPushButton("⚙")
        config_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(100, 150, 255, 150);
                color: white;
                border-radius: 10px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: rgba(120, 170, 255, 200);
            }
        """)
        config_btn.setFixedSize(20, 20)
        config_btn.setToolTip("Settings")
        config_btn.clicked.connect(self.show_config_dialog)
        title_layout.addWidget(config_btn)
        
        # Hide button
        hide_btn = QPushButton("−")
        hide_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 200, 0, 150);
                color: black;
                border-radius: 10px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: rgba(255, 220, 0, 200);
            }
        """)
        hide_btn.setFixedSize(20, 20)
        hide_btn.setToolTip("Hide to Tray")
        hide_btn.clicked.connect(self.hide_to_tray)
        title_layout.addWidget(hide_btn)
        
        # Close button
        close_btn = QPushButton("×")
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 100, 100, 150);
                color: white;
                border-radius: 10px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: rgba(255, 120, 120, 200);
            }
        """)
        close_btn.setFixedSize(20, 20)
        close_btn.setToolTip("Close")
        close_btn.clicked.connect(self.quit_application)
        title_layout.addWidget(close_btn)
        
        return title_frame
    
    def populate_microphone_list(self):
        """Populate the microphone selector with saved device restoration"""
        try:
            self.mic_selector.clear()
            microphones = AudioListener.get_microphone_list()
            
            saved_device_index = self.settings.get('microphone_device_index')
            saved_device_name = self.settings.get('microphone_device_name', '')
            selected_index = 0  # Default to first item
            
            for i, (index, name) in enumerate(microphones):
                display_name = name[:50] + "..." if len(name) > 50 else name
                self.mic_selector.addItem(display_name, index)
                
                # Try to restore saved device by index first, then by name
                if saved_device_index is not None and index == saved_device_index:
                    selected_index = i
                elif saved_device_name and saved_device_name in name:
                    selected_index = i
            
            if len(microphones) > 0:
                self.mic_selector.setCurrentIndex(selected_index)
                print(f"Restored microphone: {microphones[selected_index][1]}")
            
        except Exception as e:
            print(f"Error populating microphone list: {e}")
            self.mic_selector.addItem("Default Microphone", None)
    
    def on_microphone_changed(self, index):
        """Handle microphone selection change and save selection"""
        try:
            device_index = self.mic_selector.itemData(index)
            mic_name = self.mic_selector.currentText()
            
            # Save the selected device to settings
            self.settings['microphone_device_index'] = device_index
            self.settings['microphone_device_name'] = mic_name
            self.save_settings()
            
            if self.audio_listener:
                self.audio_listener.stop()
                self.audio_listener.wait()
                
                # Stop transcription check timer if it exists
                if hasattr(self, 'transcription_check_timer'):
                    self.transcription_check_timer.stop()
                
                # Start new listener with selected microphone
                if FAST_AUDIO_AVAILABLE and self.settings.get('use_fast_mode', True):
                    self.audio_listener = FastAudioListener(device_index)
                    print(f"Device changed: Using FastAudioListener with device {device_index}")
                    
                    # Reconnect ALL signals for FastAudioListener
                    if hasattr(self.audio_listener, 'whisper_status_changed'):
                        self.audio_listener.whisper_status_changed.connect(self.update_whisper_status)
                        print("Connected whisper_status_changed signal")
                    
                    if hasattr(self.audio_listener, 'claude_ready'):
                        self.audio_listener.claude_ready.connect(self.handle_claude_request)
                        print("Connected claude_ready signal")
                    
                    # Restart transcription check timer for instant display
                    self.transcription_check_timer = QTimer()
                    self.transcription_check_timer.timeout.connect(self._check_transcription_results)
                    self.transcription_check_timer.start(50)
                    print("Restarted transcription check timer")
                    
                else:
                    self.audio_listener = AudioListener(device_index)
                    print(f"Device changed: Using AudioListener with device {device_index}")
                    
                # Connect transcription signal for both types
                self.audio_listener.transcription_ready.connect(self.display_transcription)
                print("Connected transcription_ready signal")
                
                self.audio_listener.start()
                print("Audio listener restarted successfully")
                
                self.current_response.setText(f"Switched to: {mic_name}")
                print(f"Microphone saved: {mic_name} (index: {device_index})")
        except Exception as e:
            self.current_response.setText(f"Error switching microphone: {str(e)}")
            print(f"Error in microphone change: {e}")
    
    def init_claude_client(self):
        """Initialize Claude API client"""
        try:
            api_key = Config.get_api_key()
            self.claude_client = ClaudeClient(api_key)
            print("Claude client initialized")
        except Exception as e:
            print(f"Failed to initialize Claude client: {e}")
            self.current_response.setText(f"Claude API Error: {e}")
    
    def init_audio(self):
        """Initialize audio listening with saved device"""
        try:
            # Get saved microphone device
            saved_device_index = self.settings.get('microphone_device_index')
            saved_device_name = self.settings.get('microphone_device_name', '')
            
            if self.settings.get('use_fast_mode', True) and FAST_AUDIO_AVAILABLE:
                self.audio_listener = FastAudioListener(saved_device_index)
                print(f"Using fast audio processing with Whisper + VAD")
                if saved_device_name:
                    print(f"Using saved microphone: {saved_device_name}")
                if hasattr(self.audio_listener, 'whisper_status_changed'):
                    self.audio_listener.whisper_status_changed.connect(self.update_whisper_status)
                if hasattr(self.audio_listener, 'claude_ready'):
                    self.audio_listener.claude_ready.connect(self.handle_claude_request)
                
                # Set up timer to check for transcription results from worker threads
                self.transcription_check_timer = QTimer()
                self.transcription_check_timer.timeout.connect(self._check_transcription_results)
                self.transcription_check_timer.start(50)  # Check every 50ms for instant display
                
            else:
                self.audio_listener = AudioListener(saved_device_index)
                print(f"Using optimized Google Speech Recognition")
                if saved_device_name:
                    print(f"Using saved microphone: {saved_device_name}")
                self.update_whisper_status("idle")
                
            self.audio_listener.transcription_ready.connect(self.display_transcription)
            self.audio_listener.start()
        except Exception as e:
            print(f"Failed to initialize audio processing: {e}")
            self.current_response.setText(f"Audio Error: {e}")
    
    def _check_transcription_results(self):
        """Check for transcription results from worker threads (runs in main thread)"""
        if hasattr(self.audio_listener, 'check_transcription_results'):
            self.audio_listener.check_transcription_results()
    
    def handle_transcription(self, text: str):
        """Handle new transcription from audio listener (thread-safe)"""
        # Use QTimer to ensure this runs in main thread
        def _handle_in_main_thread():
            if not self.mic_enabled or not self.claude_client:
                return
            
            # Show transcribed text
            if hasattr(self, 'transcription_area') and self.transcription_area:
                self.transcription_area.setText(text)
            
            # Show AI status
            self.update_ai_status("thinking")
            self.current_response.setText("🤔 Processing...")
            
            # Get context from recent conversation
            context = ""
            if len(self.conversation_history) > 0:
                recent_entries = self.conversation_history[-2:]
                context = " ".join([f"{entry.transcription}" for entry in recent_entries])
                if len(context) > 200:
                    context = context[-200:]
            
            # Async callback for AI response
            def on_ai_response(ai_response: str):
                def _handle_ai_response():
                    try:
                        self.update_ai_status("responding")
                        
                        # Create conversation entry
                        entry = ConversationEntry(datetime.now(), text, ai_response)
                        self.conversation_history.append(entry)
                        
                        # Update UI
                        self.current_response.setText(ai_response)
                        self.add_timeline_entry(entry)
                        
                        # Keep only last 100 entries
                        if len(self.conversation_history) > 100:
                            self.conversation_history = self.conversation_history[-100:]
                        
                        # Set AI back to idle after a brief delay
                        QTimer.singleShot(2000, lambda: self.update_ai_status("idle"))
                            
                    except Exception as e:
                        print(f"Error handling AI response: {e}")
                        self.current_response.setText(f"Error: {str(e)}")
                        self.update_ai_status("error")
                
                # Ensure AI response handling is also in main thread
                QTimer.singleShot(0, _handle_ai_response)
            
            # Get AI response asynchronously
            self.claude_client.get_response_async(
                text, 
                context, 
                self.settings.get('custom_prompt', ''),
                self.settings.get('mode', 'default'),
                callback=on_ai_response
            )
        
        # Ensure this entire method runs in the main thread
        QTimer.singleShot(0, _handle_in_main_thread)
    
    def display_transcription(self, text: str):
        """Display transcription instantly (thread-safe)"""
        self.ui_updater.request_update("display_transcription", text=text)
    
    def handle_claude_request(self, text: str):
        """Handle Claude processing request (thread-safe)"""
        print(f"handle_claude_request called with text: '{text}'")
        self.ui_updater.request_update("claude_processing", text=text)
    
    def add_timeline_entry(self, entry: ConversationEntry):
        """Add an entry to the timeline"""
        entry_widget = QFrame()
        entry_widget.setStyleSheet("""
            QFrame {
                background-color: rgba(60, 60, 60, 100);
                border: 1px solid rgba(100, 100, 100, 80);
                border-radius: 5px;
                margin: 2px;
                padding: 5px;
            }
        """)
        
        entry_layout = QVBoxLayout(entry_widget)
        
        # Timestamp
        timestamp_label = QLabel(entry.timestamp.strftime("%H:%M:%S"))
        timestamp_label.setStyleSheet("color: #aaa; font-size: 10px;")
        entry_layout.addWidget(timestamp_label)
        
        # Transcription
        transcription_label = QLabel(f"You: {entry.transcription}")
        transcription_label.setStyleSheet("color: white; font-weight: bold;")
        transcription_label.setWordWrap(True)
        entry_layout.addWidget(transcription_label)
        
        # AI Response
        response_label = QLabel(f"AI: {entry.ai_response}")
        response_label.setStyleSheet("color: #88ff88;")
        response_label.setWordWrap(True)
        entry_layout.addWidget(response_label)
        
        # Add to timeline
        self.timeline_layout.addWidget(entry_widget)
        
        # Auto-scroll to bottom
        QTimer.singleShot(100, lambda: self.timeline_scroll.verticalScrollBar().setValue(
            self.timeline_scroll.verticalScrollBar().maximum()
        ))
    
    def update_whisper_status(self, status):
        """Update Whisper processing status indicator (thread-safe)"""
        self.ui_updater.request_update("update_whisper_status", status=status)
    
    def update_ai_status(self, status):
        """Update AI processing status indicator (thread-safe)"""
        self.ui_updater.request_update("update_ai_status", status=status)
    
    def get_global_dark_theme(self):
        """Get global dark theme including context menus"""
        font_size = self.settings['font_size']
        return f"""
            QWidget {{
                color: white;
                font-family: 'Arial', sans-serif;
                font-size: {font_size}px;
                background-color: transparent;
            }}
            QLabel {{
                color: white;
                font-size: {font_size}px;
            }}
            /* Context menu styling */
            QMenu {{
                background-color: rgba(20, 20, 20, 240);
                color: #00ff00;
                border: 1px solid rgba(0, 255, 0, 150);
                border-radius: 5px;
                padding: 5px;
                font-family: 'Courier New', monospace;
            }}
            QMenu::item {{
                background-color: transparent;
                padding: 5px 10px;
                border-radius: 3px;
            }}
            QMenu::item:selected {{
                background-color: rgba(0, 255, 0, 50);
                color: #00ff00;
            }}
            QMenu::item:pressed {{
                background-color: rgba(0, 255, 0, 100);
            }}
            QMenu::separator {{
                height: 1px;
                background-color: rgba(0, 255, 0, 100);
                margin: 5px;
            }}
        """
    
    def update_styles(self):
        """Update UI styles with current settings"""
        self.setStyleSheet(self.get_global_dark_theme())
    
    def export_data(self):
        """Export conversation data to JSON file"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            export_file = Path.home() / f"sai_export_{timestamp}.json"
            
            export_data = {
                'export_timestamp': datetime.now().isoformat(),
                'conversation_history': [entry.to_dict() for entry in self.conversation_history],
                'settings': self.settings
            }
            
            with open(export_file, 'w') as f:
                json.dump(export_data, f, indent=2)
            
            self.current_response.setText(f"Data exported to: {export_file}")
        except Exception as e:
            self.current_response.setText(f"Export error: {str(e)}")
    
    def clear_timeline(self):
        """Clear the timeline and conversation history"""
        self.conversation_history = []
        
        # Clear timeline UI
        for i in reversed(range(self.timeline_layout.count())):
            child = self.timeline_layout.itemAt(i).widget()
            if child:
                child.deleteLater()
        
        self.current_response.setText("Timeline cleared")
        self.save_conversation_history()
    
    def show_config_dialog(self):
        """Show configuration dialog"""
        dialog = ConfigDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Update all settings from dialog
            self.settings['font_size'] = dialog.font_slider.value()
            self.settings['opacity'] = dialog.opacity_slider.value() / 100.0
            self.settings['window_width'] = dialog.width_spin.value()
            self.settings['window_height'] = dialog.height_spin.value()
            self.settings['show_transcription'] = dialog.show_transcription_cb.isChecked()
            self.settings['mode'] = dialog.mode_combo.currentText()
            self.settings['custom_prompt'] = dialog.custom_prompt_edit.toPlainText()
            self.settings['use_fast_mode'] = dialog.fast_mode_cb.isChecked()
            
            # Apply changes immediately
            self.setWindowOpacity(self.settings['opacity'])
            self.resize(self.settings['window_width'], self.settings['window_height'])
            self.update_styles()
            
            # Update transcription area visibility
            if hasattr(self, 'transcription_area'):
                self.transcription_area.setVisible(self.settings['show_transcription'])
            
            # Restart audio if mode changed
            if hasattr(self, 'audio_listener') and self.audio_listener:
                old_mode = getattr(self, '_current_audio_mode', True)
                new_mode = self.settings['use_fast_mode']
                if old_mode != new_mode:
                    self.restart_audio_listener()
                self._current_audio_mode = new_mode
            
            self.save_settings()
            self.current_response.setText("Settings updated and applied")
    
    def restart_audio_listener(self):
        """Restart audio listener with new settings"""
        try:
            if self.audio_listener:
                self.audio_listener.stop()
                self.audio_listener.wait()
            
            # Reinitialize audio with new settings
            self.init_audio()
        except Exception as e:
            print(f"Error restarting audio listener: {e}")
            self.current_response.setText(f"Audio restart error: {str(e)}")
    
    
    def closeEvent(self, event):
        """Handle close event"""
        if self.audio_listener:
            self.audio_listener.stop()
            self.audio_listener.wait()
        
        self.save_settings()
        self.save_conversation_history()
        event.accept()