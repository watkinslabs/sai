"""
Dedicated UI updater thread - handles ALL UI operations to avoid Qt threading issues
"""

import queue
import threading
from PyQt6.QtCore import QObject, pyqtSignal, QTimer
from datetime import datetime

class UIUpdateRequest:
    """Represents a UI update request"""
    def __init__(self, action, **kwargs):
        self.action = action
        self.kwargs = kwargs

class UIUpdater(QObject):
    """Thread-safe UI updater that handles all UI operations"""
    
    def __init__(self, overlay_widget):
        super().__init__()
        self.overlay_widget = overlay_widget
        self.update_queue = queue.Queue()
        
        # Timer to process UI updates
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.process_updates)
        self.update_timer.start(16)  # ~60fps updates
        
    def request_update(self, action, **kwargs):
        """Thread-safe method to request UI update"""
        self.update_queue.put(UIUpdateRequest(action, **kwargs))
    
    def process_updates(self):
        """Process all pending UI updates (runs in main thread)"""
        try:
            while True:
                try:
                    request = self.update_queue.get_nowait()
                    self._handle_update(request)
                except queue.Empty:
                    break
        except Exception as e:
            print(f"UI update error: {e}")
    
    def _handle_update(self, request):
        """Handle individual UI update request"""
        try:
            if request.action == "display_transcription":
                text = request.kwargs.get('text', '')
                if hasattr(self.overlay_widget, 'transcription_area'):
                    self.overlay_widget.transcription_area.setText(text)
                    
            elif request.action == "update_whisper_status":
                status = request.kwargs.get('status', 'idle')
                self._update_whisper_status(status)
                
            elif request.action == "update_ai_status":
                status = request.kwargs.get('status', 'idle')
                self._update_ai_status(status)
                
            elif request.action == "set_response":
                text = request.kwargs.get('text', '')
                if hasattr(self.overlay_widget, 'current_response'):
                    self.overlay_widget.current_response.setText(text)
                    
            elif request.action == "add_timeline_entry":
                entry = request.kwargs.get('entry')
                if entry:
                    self._add_timeline_entry(entry)
                    
            elif request.action == "claude_processing":
                text = request.kwargs.get('text', '')
                self._handle_claude_processing(text)
                
        except Exception as e:
            print(f"Error handling UI update {request.action}: {e}")
    
    def _update_whisper_status(self, status):
        """Update Whisper status indicator"""
        if not hasattr(self.overlay_widget, 'whisper_status'):
            return
            
        widget = self.overlay_widget.whisper_status
        
        if status == "listening":
            widget.setText("🎤")
            widget.setStyleSheet("color: #00ff00; font-size: 16px;")
            widget.setToolTip("Listening for speech...")
        elif status == "processing":
            widget.setText("🎵")
            widget.setStyleSheet("color: #ff8800; font-size: 16px;")
            widget.setToolTip("Processing speech...")
        elif status == "idle":
            widget.setText("🎤")
            widget.setStyleSheet("color: #666; font-size: 16px;")
            widget.setToolTip("Speech recognition idle")
        elif status == "disabled":
            widget.setText("🚫")
            widget.setStyleSheet("color: #ff0000; font-size: 16px;")
            widget.setToolTip("Microphone disabled")
    
    def _update_ai_status(self, status):
        """Update AI status indicator"""
        if not hasattr(self.overlay_widget, 'ai_status'):
            return
            
        widget = self.overlay_widget.ai_status
        
        if status == "thinking":
            widget.setText("🤔")
            widget.setStyleSheet("color: #0088ff; font-size: 16px;")
            widget.setToolTip("AI thinking...")
        elif status == "responding":
            widget.setText("💬")
            widget.setStyleSheet("color: #00ff88; font-size: 16px;")
            widget.setToolTip("AI responding...")
        elif status == "idle":
            widget.setText("🤖")
            widget.setStyleSheet("color: #666; font-size: 16px;")
            widget.setToolTip("AI idle")
        elif status == "error":
            widget.setText("⚠️")
            widget.setStyleSheet("color: #ff0000; font-size: 16px;")
            widget.setToolTip("AI error")
    
    def _add_timeline_entry(self, entry):
        """Add entry to timeline"""
        from PyQt6.QtWidgets import QFrame, QVBoxLayout, QLabel
        
        entry_widget = QFrame()
        entry_widget.setStyleSheet("""
            QFrame {
                background-color: rgba(10, 10, 10, 180);
                border: 1px solid rgba(0, 255, 0, 60);
                border-radius: 5px;
                margin: 2px;
                padding: 8px;
            }
        """)
        
        entry_layout = QVBoxLayout(entry_widget)
        
        # Timestamp
        timestamp_label = QLabel(entry.timestamp.strftime("[%H:%M:%S]"))
        timestamp_label.setStyleSheet("color: #00ff00; font-size: 10px; font-family: 'Courier New', monospace;")
        entry_layout.addWidget(timestamp_label)
        
        # Transcription
        transcription_label = QLabel(f">>> {entry.transcription}")
        transcription_label.setStyleSheet("color: #00ffff; font-weight: bold; font-family: 'Courier New', monospace;")
        transcription_label.setWordWrap(True)
        entry_layout.addWidget(transcription_label)
        
        # AI Response
        response_label = QLabel(f"<<< {entry.ai_response}")
        response_label.setStyleSheet("color: #00ff88; font-family: 'Courier New', monospace;")
        response_label.setWordWrap(True)
        entry_layout.addWidget(response_label)
        
        # Add to timeline
        if hasattr(self.overlay_widget, 'timeline_layout'):
            self.overlay_widget.timeline_layout.addWidget(entry_widget)
            
        # Auto-scroll to bottom
        if hasattr(self.overlay_widget, 'timeline_scroll'):
            QTimer.singleShot(100, lambda: self.overlay_widget.timeline_scroll.verticalScrollBar().setValue(
                self.overlay_widget.timeline_scroll.verticalScrollBar().maximum()
            ))
    
    def _handle_claude_processing(self, text):
        """Handle Claude API processing"""
        print(f"UI Updater: _handle_claude_processing called with text: '{text}'")
        if not self.overlay_widget.claude_client:
            print("UI Updater: No Claude client available")
            return
            
        # Show AI status
        self._update_ai_status("thinking")
        if hasattr(self.overlay_widget, 'current_response'):
            self.overlay_widget.current_response.setText("🤔 Processing...")
        
        # Get context from recent conversation
        context = ""
        if len(self.overlay_widget.conversation_history) > 0:
            recent_entries = self.overlay_widget.conversation_history[-2:]
            context = " ".join([f"{entry.transcription}" for entry in recent_entries])
            if len(context) > 200:
                context = context[-200:]
        
        # Async callback for AI response
        def on_ai_response(ai_response: str):
            from .config import ConversationEntry
            
            try:
                # Update AI status
                self.request_update("update_ai_status", status="responding")
                
                # Create conversation entry
                entry = ConversationEntry(datetime.now(), text, ai_response)
                self.overlay_widget.conversation_history.append(entry)
                
                # Update UI
                self.request_update("set_response", text=ai_response)
                self.request_update("add_timeline_entry", entry=entry)
                
                # Keep only last 100 entries
                if len(self.overlay_widget.conversation_history) > 100:
                    self.overlay_widget.conversation_history = self.overlay_widget.conversation_history[-100:]
                
                # Set AI back to idle after a brief delay
                def reset_ai_status():
                    self.request_update("update_ai_status", status="idle")
                QTimer.singleShot(2000, reset_ai_status)
                    
            except Exception as e:
                print(f"Error handling AI response: {e}")
                self.request_update("set_response", text=f"Error: {str(e)}")
                self.request_update("update_ai_status", status="error")
        
        # Get AI response asynchronously
        self.overlay_widget.claude_client.get_response_async(
            text, 
            context, 
            self.overlay_widget.settings.get('custom_prompt', ''),
            self.overlay_widget.settings.get('mode', 'default'),
            callback=on_ai_response,
            settings=self.overlay_widget.settings
        )