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
    Qt, pyqtSignal, QTimer, QPoint, QSize
)
from PyQt6.QtGui import (
    QFont, QPalette, QColor, QPixmap, QIcon, QAction
)

from .config import Config, ConversationEntry, WindowExcluder
from .claude_client import ClaudeClient
from .audio import FastAudioListener, AudioListener, FAST_AUDIO_AVAILABLE

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
        
        # Simple settings for now - can be expanded later
        settings_group = QGroupBox("Settings")
        settings_layout = QVBoxLayout(settings_group)
        
        # Font size
        self.font_slider = QSlider(Qt.Orientation.Horizontal)
        self.font_slider.setRange(8, 24)
        self.font_slider.setValue(self.settings.get('font_size', 12))
        self.font_label = QLabel(f"Font Size: {self.settings.get('font_size', 12)}px")
        settings_layout.addWidget(self.font_label)
        settings_layout.addWidget(self.font_slider)
        
        # Opacity
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(30, 100)
        self.opacity_slider.setValue(int(self.settings.get('opacity', 0.9) * 100))
        self.opacity_label = QLabel(f"Opacity: {int(self.settings.get('opacity', 0.9) * 100)}%")
        settings_layout.addWidget(self.opacity_label)
        settings_layout.addWidget(self.opacity_slider)
        
        layout.addWidget(settings_group)
        
        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        self.setLayout(layout)
    
    def get_dark_theme_style(self):
        """Get dark theme stylesheet"""
        return """
            QDialog {
                background-color: rgba(30, 30, 30, 240);
                color: white;
                border: 1px solid rgba(100, 100, 100, 150);
                border-radius: 8px;
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
        self.init_audio()
    
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
        # Set window properties
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Set size and position
        self.resize(self.settings['window_width'], self.settings['window_height'])
        
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
        content_layout.addWidget(self.current_response)
        
        # Timeline
        timeline_label = QLabel("Timeline:")
        content_layout.addWidget(timeline_label)
        
        self.timeline_scroll = QScrollArea()
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
        
        # Add resize grip
        size_grip = QSizeGrip(self)
        grip_layout = QHBoxLayout()
        grip_layout.addStretch()
        grip_layout.addWidget(size_grip)
        layout.addLayout(grip_layout)
        
        self.setLayout(layout)
        
        # Apply window opacity and styles
        self.setWindowOpacity(self.settings['opacity'])
        self.drag_position = QPoint()
        self.update_styles()
    
    def create_title_bar(self):
        """Create the title bar with controls"""
        title_frame = QFrame()
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
        
        # Title
        title_label = QLabel("SAI - Smart AI Assistant")
        title_label.setStyleSheet("color: white; font-weight: bold; font-size: 11px;")
        title_layout.addWidget(title_label)
        
        # Microphone selector
        self.mic_selector = QComboBox()
        self.mic_selector.setStyleSheet("""
            QComboBox {
                background-color: rgba(60, 60, 60, 180);
                color: white;
                border: 1px solid rgba(100, 100, 100, 150);
                border-radius: 3px;
                padding: 2px 5px;
                min-width: 120px;
            }
        """)
        self.mic_selector.currentIndexChanged.connect(self.on_microphone_changed)
        title_layout.addWidget(self.mic_selector)
        
        # Populate microphone list
        self.populate_microphone_list()
        
        title_layout.addStretch()
        
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
        hide_btn.clicked.connect(self.hide)
        title_layout.addWidget(hide_btn)
        
        return title_frame
    
    def populate_microphone_list(self):
        """Populate the microphone selector"""
        try:
            self.mic_selector.clear()
            microphones = AudioListener.get_microphone_list()
            
            for index, name in microphones:
                display_name = name[:50] + "..." if len(name) > 50 else name
                self.mic_selector.addItem(display_name, index)
            
            if len(microphones) > 0:
                self.mic_selector.setCurrentIndex(0)
        except Exception as e:
            print(f"Error populating microphone list: {e}")
            self.mic_selector.addItem("Default Microphone", None)
    
    def on_microphone_changed(self, index):
        """Handle microphone selection change"""
        try:
            device_index = self.mic_selector.itemData(index)
            
            if self.audio_listener:
                self.audio_listener.stop()
                self.audio_listener.wait()
                
                # Start new listener with selected microphone
                if FAST_AUDIO_AVAILABLE:
                    self.audio_listener = FastAudioListener(device_index)
                    if hasattr(self.audio_listener, 'whisper_status_changed'):
                        self.audio_listener.whisper_status_changed.connect(self.update_whisper_status)
                else:
                    self.audio_listener = AudioListener(device_index)
                    
                self.audio_listener.transcription_ready.connect(self.handle_transcription)
                self.audio_listener.start()
                
                mic_name = self.mic_selector.currentText()
                self.current_response.setText(f"Switched to microphone: {mic_name}")
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
        """Initialize audio listening"""
        try:
            if self.settings.get('use_fast_mode', True) and FAST_AUDIO_AVAILABLE:
                self.audio_listener = FastAudioListener()
                print("Using fast audio processing with Whisper + VAD")
                if hasattr(self.audio_listener, 'whisper_status_changed'):
                    self.audio_listener.whisper_status_changed.connect(self.update_whisper_status)
            else:
                self.audio_listener = AudioListener()
                print("Using optimized Google Speech Recognition")
                self.update_whisper_status("idle")
                
            self.audio_listener.transcription_ready.connect(self.handle_transcription)
            self.audio_listener.start()
        except Exception as e:
            print(f"Failed to initialize audio processing: {e}")
            self.current_response.setText(f"Audio Error: {e}")
    
    def handle_transcription(self, text: str):
        """Handle new transcription from audio listener"""
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
        
        # Get AI response asynchronously
        self.claude_client.get_response_async(
            text, 
            context, 
            self.settings.get('custom_prompt', ''),
            self.settings.get('mode', 'default'),
            callback=on_ai_response
        )
    
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
        """Update Whisper processing status indicator"""
        if not hasattr(self, 'whisper_status'):
            return
            
        if status == "listening":
            self.whisper_status.setText("🎤")
            self.whisper_status.setStyleSheet("color: #00ff00; font-size: 16px;")
            self.whisper_status.setToolTip("Listening for speech...")
        elif status == "processing":
            self.whisper_status.setText("🎵")
            self.whisper_status.setStyleSheet("color: #ff8800; font-size: 16px;")
            self.whisper_status.setToolTip("Processing speech...")
        elif status == "idle":
            self.whisper_status.setText("🎤")
            self.whisper_status.setStyleSheet("color: #666; font-size: 16px;")
            self.whisper_status.setToolTip("Speech recognition idle")
        elif status == "disabled":
            self.whisper_status.setText("🚫")
            self.whisper_status.setStyleSheet("color: #ff0000; font-size: 16px;")
            self.whisper_status.setToolTip("Microphone disabled")
    
    def update_ai_status(self, status):
        """Update AI processing status indicator"""
        if not hasattr(self, 'ai_status'):
            return
            
        if status == "thinking":
            self.ai_status.setText("🤔")
            self.ai_status.setStyleSheet("color: #0088ff; font-size: 16px;")
            self.ai_status.setToolTip("AI thinking...")
        elif status == "responding":
            self.ai_status.setText("💬")
            self.ai_status.setStyleSheet("color: #00ff88; font-size: 16px;")
            self.ai_status.setToolTip("AI responding...")
        elif status == "idle":
            self.ai_status.setText("🤖")
            self.ai_status.setStyleSheet("color: #666; font-size: 16px;")
            self.ai_status.setToolTip("AI idle")
        elif status == "error":
            self.ai_status.setText("⚠️")
            self.ai_status.setStyleSheet("color: #ff0000; font-size: 16px;")
            self.ai_status.setToolTip("AI error")
    
    def update_styles(self):
        """Update UI styles with current settings"""
        font_size = self.settings['font_size']
        self.setStyleSheet(f"""
            QWidget {{
                color: white;
                font-family: 'Arial', sans-serif;
                font-size: {font_size}px;
            }}
            QTextEdit {{
                background-color: rgba(40, 40, 40, 180);
                border: 1px solid rgba(100, 100, 100, 100);
                border-radius: 5px;
                padding: 8px;
                color: white;
                font-size: {font_size}px;
            }}
            QLabel {{
                color: white;
                font-size: {font_size}px;
            }}
        """)
    
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
    
    def mousePressEvent(self, event):
        """Handle mouse press for dragging"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
    
    def mouseMoveEvent(self, event):
        """Handle mouse move for dragging"""
        if event.buttons() == Qt.MouseButton.LeftButton:
            new_pos = event.globalPosition().toPoint() - self.drag_position
            
            # Keep window on screen
            screen = QApplication.primaryScreen().geometry()
            new_pos.setX(max(0, min(new_pos.x(), screen.width() - self.width())))
            new_pos.setY(max(0, min(new_pos.y(), screen.height() - self.height())))
            
            self.move(new_pos)
            event.accept()
    
    def closeEvent(self, event):
        """Handle close event"""
        if self.audio_listener:
            self.audio_listener.stop()
            self.audio_listener.wait()
        
        self.save_settings()
        self.save_conversation_history()
        event.accept()