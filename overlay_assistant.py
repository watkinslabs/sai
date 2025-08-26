#!/usr/bin/env python3
"""
AI Overlay Assistant - A floating overlay that provides real-time AI feedback
based on microphone input with timeline history and export capabilities.
"""

import sys
import json
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict
import os
from dotenv import load_dotenv

import speech_recognition as sr
import sounddevice as sd
import numpy as np
try:
    import whisper
    import webrtcvad
    FAST_AUDIO_AVAILABLE = True
except ImportError:
    FAST_AUDIO_AVAILABLE = False
    print("Fast audio dependencies not available, using fallback mode")

import asyncio
import queue
from concurrent.futures import ThreadPoolExecutor
import io
import wave
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, 
    QPushButton, QLabel, QScrollArea, QFrame, QSystemTrayIcon, QMenu,
    QComboBox, QGroupBox, QDialog, QDialogButtonBox, QSlider, QCheckBox,
    QTabWidget, QPlainTextEdit, QSpinBox, QSizeGrip
)
from PyQt6.QtCore import (
    Qt, QThread, pyqtSignal, QTimer, QPoint, QSize, QObject, QRunnable, QThreadPool
)
from PyQt6.QtGui import (
    QFont, QPalette, QColor, QPixmap, QIcon, QAction
)
import anthropic
import psutil

# Load environment variables
load_dotenv()

class FastAudioListener(QThread):
    """Optimized audio listener with local Whisper and VAD"""
    
    transcription_ready = pyqtSignal(str)
    
    def __init__(self, device_index=None):
        super().__init__()
        self.device_index = device_index
        self.running = False
        self.sample_rate = 16000
        self.chunk_size = int(0.5 * self.sample_rate)  # 0.5 second chunks
        self.buffer = queue.Queue()
        
        # Initialize Whisper model (tiny for speed)
        print("Loading Whisper model...")
        try:
            self.whisper_model = whisper.load_model("tiny")
            print("Whisper tiny model loaded successfully")
        except Exception as e:
            print(f"Failed to load Whisper: {e}, falling back to Google")
            self.whisper_model = None
        
        # Voice Activity Detection
        self.vad = webrtcvad.Vad(2)  # Aggressiveness level 0-3 (2 is balanced)
        
        # Audio processing
        self.audio_queue = queue.Queue()
        self.speech_frames = []
        self.is_speaking = False
        self.silence_count = 0
        self.max_silence = 10  # frames of silence before processing
        
    def update_microphone(self, device_index):
        """Update the microphone device"""
        self.device_index = device_index
    
    @staticmethod
    def get_microphone_list():
        """Get list of available microphones"""
        try:
            mic_list = []
            devices = sd.query_devices()
            for i, device in enumerate(devices):
                if device['max_input_channels'] > 0:  # Only input devices
                    mic_list.append((i, device['name']))
            return mic_list
        except Exception as e:
            print(f"Error getting microphone list: {e}")
            return [(None, "Default Microphone")]
    
    def is_speech(self, audio_chunk):
        """Check if audio chunk contains speech using WebRTC VAD"""
        try:
            # Convert to 16-bit PCM
            pcm_data = (audio_chunk * 32767).astype(np.int16).tobytes()
            
            # VAD works with specific frame sizes (10, 20, or 30ms)
            frame_duration = 30  # ms
            frame_size = int(self.sample_rate * frame_duration / 1000)
            
            if len(pcm_data) >= frame_size * 2:  # 2 bytes per sample
                return self.vad.is_speech(pcm_data[:frame_size * 2], self.sample_rate)
            return False
        except Exception:
            return True  # Assume speech if VAD fails
    
    def transcribe_audio(self, audio_data):
        """Transcribe audio using Whisper or fallback to Google"""
        try:
            if self.whisper_model:
                # Use local Whisper (much faster)
                result = self.whisper_model.transcribe(
                    audio_data,
                    language="en",
                    task="transcribe",
                    fp16=False,
                    verbose=False
                )
                text = result["text"].strip()
                return text
            else:
                # Fallback to Google STT
                recognizer = sr.Recognizer()
                audio_data_int16 = (audio_data * 32767).astype(np.int16)
                audio_bytes = audio_data_int16.tobytes()
                audio = sr.AudioData(audio_bytes, self.sample_rate, 2)
                
                text = recognizer.recognize_google(audio, language="en-US")
                return text.strip()
                
        except Exception as e:
            print(f"Transcription error: {e}")
            return ""
    
    def run(self):
        self.running = True
        
        def audio_callback(indata, frames, time, status):
            """Callback for continuous audio stream"""
            if status:
                print(f"Audio callback status: {status}")
            
            # Add audio chunk to queue
            audio_chunk = indata[:, 0]  # Get mono channel
            self.audio_queue.put(audio_chunk.copy())
        
        # Start audio stream
        with sd.InputStream(
            callback=audio_callback,
            channels=1,
            samplerate=self.sample_rate,
            blocksize=self.chunk_size,
            device=self.device_index,
            dtype=np.float32
        ):
            print(f"Audio streaming started on device {self.device_index}")
            
            while self.running:
                try:
                    # Get audio chunk with timeout
                    audio_chunk = self.audio_queue.get(timeout=1.0)
                    
                    # Check for speech activity
                    has_speech = self.is_speech(audio_chunk)
                    
                    if has_speech:
                        self.speech_frames.append(audio_chunk)
                        self.is_speaking = True
                        self.silence_count = 0
                    else:
                        if self.is_speaking:
                            self.silence_count += 1
                            
                            # Add a bit of trailing silence
                            if self.silence_count <= 3:
                                self.speech_frames.append(audio_chunk)
                    
                    # Process speech when silence detected after speech
                    if self.is_speaking and self.silence_count >= self.max_silence:
                        if len(self.speech_frames) > 5:  # Minimum frames for processing
                            # Combine speech frames
                            speech_audio = np.concatenate(self.speech_frames)
                            
                            # Transcribe in separate thread to avoid blocking
                            self.process_speech_async(speech_audio)
                        
                        # Reset for next speech segment
                        self.speech_frames = []
                        self.is_speaking = False
                        self.silence_count = 0
                    
                    # Clear buffer if too long without speech
                    if len(self.speech_frames) > 100:  # ~50 seconds at 0.5s chunks
                        self.speech_frames = self.speech_frames[-50:]  # Keep last 25 seconds
                        
                except queue.Empty:
                    continue
                except Exception as e:
                    print(f"Audio processing error: {e}")
                    time.sleep(0.1)
    
    def process_speech_async(self, audio_data):
        """Process speech transcription asynchronously"""
        def transcribe_worker():
            text = self.transcribe_audio(audio_data)
            if text and len(text.strip()) > 2:  # Minimum text length
                self.transcription_ready.emit(text)
        
        # Run transcription in thread pool to avoid blocking
        QThreadPool.globalInstance().start(
            lambda: transcribe_worker()
        )
    
    def stop(self):
        self.running = False

# Keep the old AudioListener as fallback
class AudioListener(QThread):
    """Fallback audio listener using Google STT"""
    
    transcription_ready = pyqtSignal(str)
    
    def __init__(self, device_index=None):
        super().__init__()
        self.recognizer = sr.Recognizer()
        self.device_index = device_index
        self.running = False
        self.sample_rate = 16000
        
        # Configure for faster recognition  
        self.recognizer.energy_threshold = 300
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.pause_threshold = 0.5  # Shorter pause
        self.recognizer.phrase_threshold = 0.2  # Faster phrase detection
        self.recognizer.non_speaking_duration = 0.5  # Less silence needed
        
        # Track if we should keep running (prevent infinite restart)
        self.should_run = True
    
    def update_microphone(self, device_index):
        self.device_index = device_index
    
    @staticmethod
    def get_microphone_list():
        try:
            mic_list = []
            devices = sd.query_devices()
            for i, device in enumerate(devices):
                if device['max_input_channels'] > 0:
                    mic_list.append((i, device['name']))
            return mic_list
        except Exception as e:
            print(f"Error getting microphone list: {e}")
            return [(None, "Default Microphone")]
    
    def run(self):
        self.running = True
        print("Starting audio listener...")
        
        # First, let's detect what devices actually work
        working_device = self.find_working_device()
        if working_device is None:
            print("No working audio device found!")
            return
            
        print(f"Using audio device: {working_device}")
        self.device_index = working_device
        
        while self.running and self.should_run:
            try:
                duration = 3.0
                
                # Use the device's native sample rate
                device_info = sd.query_devices(self.device_index)
                native_rate = int(device_info['default_samplerate'])
                print(f"Using native sample rate: {native_rate} Hz")
                
                # Record with native settings
                audio_data = sd.rec(
                    int(duration * native_rate),
                    samplerate=native_rate,
                    channels=1,
                    device=self.device_index,
                    dtype=np.float32
                )
                sd.wait()
                
                print(f"Recorded {len(audio_data)} samples")
                
                # Quick energy check
                energy = np.mean(np.abs(audio_data))
                print(f"Audio energy: {energy}")
                
                if energy < 0.001:  # Very quiet
                    print("Audio too quiet, skipping...")
                    continue
                
                # Simple resampling to 16kHz for speech recognition
                if native_rate == 48000:
                    # Simple 3:1 decimation
                    audio_data = audio_data[::3]
                    final_rate = 16000
                elif native_rate == 44100:
                    # Approximate decimation 44100->16000
                    step = int(44100 / 16000)
                    audio_data = audio_data[::step]  
                    final_rate = 16000
                else:
                    final_rate = native_rate
                
                # Convert to format expected by speech recognition
                audio_data_int16 = (audio_data * 32767).astype(np.int16)
                audio_bytes = audio_data_int16.tobytes()
                audio = sr.AudioData(audio_bytes, final_rate, 2)
                
                print("Sending to speech recognition...")
                try:
                    text = self.recognizer.recognize_google(audio, language="en-US")
                    if text.strip():
                        print(f"Recognized: {text}")
                        self.transcription_ready.emit(text)
                except sr.UnknownValueError:
                    print("No speech detected")
                except sr.RequestError as e:
                    print(f"Speech recognition error: {e}")
                    
            except Exception as e:
                print(f"Audio processing error: {e}")
                time.sleep(1.0)
    
    def find_working_device(self):
        """Find a microphone device that actually works"""
        print("Scanning for working audio devices...")
        
        devices = sd.query_devices()
        input_devices = [(i, d) for i, d in enumerate(devices) if d['max_input_channels'] > 0]
        
        for device_id, device_info in input_devices:
            print(f"Testing device {device_id}: {device_info['name']}")
            
            try:
                # Test record for 0.1 seconds
                test_duration = 0.1
                sample_rate = int(device_info['default_samplerate'])
                
                test_data = sd.rec(
                    int(test_duration * sample_rate),
                    samplerate=sample_rate,
                    channels=1,
                    device=device_id,
                    dtype=np.float32
                )
                sd.wait()
                
                print(f"✓ Device {device_id} works (rate: {sample_rate})")
                return device_id
                
            except Exception as e:
                print(f"✗ Device {device_id} failed: {e}")
                continue
        
        print("No working devices found")
        return None
    
    def stop(self):
        self.running = False

class AsyncClaudeWorker(QRunnable):
    """Worker for async Claude API calls"""
    
    def __init__(self, client, text, context, custom_prompt, mode, callback):
        super().__init__()
        self.client = client
        self.text = text
        self.context = context
        self.custom_prompt = custom_prompt
        self.mode = mode
        self.callback = callback
    
    def run(self):
        """Execute the API call in background"""
        try:
            response = self.client.get_response_sync(
                self.text, self.context, self.custom_prompt, self.mode
            )
            self.callback(response)
        except Exception as e:
            self.callback(f"Error: {str(e)}")

class ClaudeClient:
    """Optimized Claude API client with caching and async calls"""
    
    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.response_cache = {}  # Simple LRU cache
        self.max_cache_size = 100
        self.thread_pool = QThreadPool.globalInstance()
        self.thread_pool.setMaxThreadCount(3)  # Limit concurrent API calls
    
    def _get_cache_key(self, text: str, context: str, mode: str) -> str:
        """Generate cache key for request"""
        return f"{mode}:{hash(text + context)}"
    
    def get_response_sync(self, text: str, context: str = "", custom_prompt: str = "", mode: str = "default") -> str:
        """Synchronous API call (for worker threads)"""
        try:
            # Check cache first
            cache_key = self._get_cache_key(text, context, mode)
            if cache_key in self.response_cache:
                return self.response_cache[cache_key]
            
            # Prompt templates for different modes (shortened for speed)
            prompts = {
                "default": f"Context: {context}\nInput: \"{text}\"\nBrief response (max 30 words):",
                
                "meeting": f"Meeting context: {context}\nCurrent: \"{text}\"\nKey point (max 20 words):",
                
                "learning": f"Context: {context}\nTopic: \"{text}\"\nQuick insight (max 25 words):",
                
                "summary": f"Context: {context}\nText: \"{text}\"\nSummary (max 25 words):",
                
                "custom": custom_prompt.format(text=text, context=context) if custom_prompt else f"Respond to: {text}"
            }
            
            prompt = prompts.get(mode, prompts["default"])

            message = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=100,  # Reduced for faster response
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3  # Lower temperature for consistency
            )
            
            response = message.content[0].text if message.content else "No response"
            
            # Cache the response
            if len(self.response_cache) >= self.max_cache_size:
                # Remove oldest entry
                oldest_key = next(iter(self.response_cache))
                del self.response_cache[oldest_key]
            
            self.response_cache[cache_key] = response
            return response
            
        except Exception as e:
            return f"API Error: {str(e)}"
    
    def get_response_async(self, text: str, context: str = "", custom_prompt: str = "", mode: str = "default", callback=None):
        """Async API call using thread pool"""
        if not callback:
            return self.get_response_sync(text, context, custom_prompt, mode)
        
        # Check cache first (synchronously)
        cache_key = self._get_cache_key(text, context, mode)
        if cache_key in self.response_cache:
            callback(self.response_cache[cache_key])
            return
        
        # Queue worker for API call
        worker = AsyncClaudeWorker(self, text, context, custom_prompt, mode, callback)
        self.thread_pool.start(worker)

class ConversationEntry:
    """Represents a single conversation entry"""
    
    def __init__(self, timestamp: datetime, transcription: str, ai_response: str):
        self.timestamp = timestamp
        self.transcription = transcription
        self.ai_response = ai_response
    
    def to_dict(self) -> Dict:
        return {
            'timestamp': self.timestamp.isoformat(),
            'transcription': self.transcription,
            'ai_response': self.ai_response
        }

class WindowExcluder:
    """Handles window exclusion for video conferencing apps"""
    
    # More specific exclusions - only actual video conferencing apps
    EXCLUDED_PROCESSES = [
        'zoom', 'skype', 'microsoft teams', 'teams.exe', 'webex'
    ]
    
    @staticmethod
    def should_hide_overlay() -> bool:
        """Check if overlay should be hidden based on active processes"""
        try:
            # For now, disable auto-hiding as it's too aggressive
            # You can enable this by returning the logic below instead of False
            return False
            
            # Original logic (commented out):
            # for proc in psutil.process_iter(['pid', 'name']):
            #     proc_name = proc.info['name'].lower()
            #     if any(excluded in proc_name for excluded in WindowExcluder.EXCLUDED_PROCESSES):
            #         return True
            # return False
        except Exception:
            return False

class ConfigDialog(QDialog):
    """Configuration dialog for settings"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Overlay Assistant Settings")
        self.setModal(True)
        self.resize(500, 600)
        
        # Load current settings
        self.settings = getattr(parent, 'settings', {
            'font_size': 12,
            'opacity': 0.9,
            'mode': 'default',
            'custom_prompt': '',
            'show_transcription': True,
            'window_width': 600,
            'window_height': 400
        })
        
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Match main overlay dark theme
        self.setStyleSheet("""
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
        """)
        
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
        self.font_slider.valueChanged.connect(self.update_font_preview)
        
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
        self.opacity_slider.valueChanged.connect(self.update_opacity_preview)
        
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
        
        # Custom prompt
        prompt_group = QGroupBox("Custom Prompt Template")
        prompt_layout = QVBoxLayout(prompt_group)
        
        prompt_layout.addWidget(QLabel("Use {text} for input and {context} for conversation context:"))
        
        self.custom_prompt_edit = QPlainTextEdit()
        self.custom_prompt_edit.setPlainText(self.settings.get('custom_prompt', ''))
        self.custom_prompt_edit.setMaximumHeight(100)
        self.custom_prompt_edit.setEnabled(self.settings.get('mode') == 'custom')
        prompt_layout.addWidget(self.custom_prompt_edit)
        
        ai_layout.addWidget(prompt_group)
        
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
        fallback_label.setStyleSheet("font-style: italic; color: palette(mid);")
        audio_layout.addWidget(fallback_label)
        
        perf_layout.addWidget(audio_group)
        
        # API settings
        api_group = QGroupBox("API Performance")
        api_layout = QVBoxLayout(api_group)
        
        cache_label = QLabel("Response caching: Enabled (improves speed for repeated queries)")
        cache_label.setStyleSheet("color: palette(mid);")
        api_layout.addWidget(cache_label)
        
        async_label = QLabel("Async processing: Enabled (non-blocking API calls)")
        async_label.setStyleSheet("color: palette(mid);")
        api_layout.addWidget(async_label)
        
        perf_layout.addWidget(api_group)
        
        perf_layout.addStretch()
        
        tabs.addTab(perf_tab, "Performance")
        
        layout.addWidget(tabs)
        
        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        self.setLayout(layout)
    
    def update_font_preview(self, value):
        self.font_label.setText(f"Font Size: {value}px")
    
    def update_opacity_preview(self, value):
        self.opacity_label.setText(f"Opacity: {value}%")
    
    def on_mode_changed(self, mode):
        self.custom_prompt_edit.setEnabled(mode == 'custom')
        mode_desc = {
            "default": "General helpful responses (50 words max)",
            "meeting": "Focus on action items and decisions (30 words max)", 
            "learning": "Explanations and insights (40 words max)",
            "summary": "Bullet point summaries (35 words max)",
            "custom": "Use your own prompt template"
        }
        self.mode_desc_label.setText(mode_desc.get(mode, ''))
    
    def get_settings(self):
        return {
            'font_size': self.font_slider.value(),
            'opacity': self.opacity_slider.value() / 100.0,
            'mode': self.mode_combo.currentText(),
            'custom_prompt': self.custom_prompt_edit.toPlainText(),
            'show_transcription': self.show_transcription_cb.isChecked(),
            'window_width': self.width_spin.value(),
            'window_height': self.height_spin.value(),
            'use_fast_mode': self.fast_mode_cb.isChecked()
        }

class OverlayWidget(QWidget):
    """Main overlay window"""
    
    def __init__(self):
        super().__init__()
        self.claude_client = None
        self.audio_listener = None
        self.conversation_history: List[ConversationEntry] = []
        self.data_file = Path.home() / '.overlay_assistant_data.json'
        self.settings_file = Path.home() / '.overlay_assistant_settings.json'
        self.mic_enabled = True
        
        # Default settings
        self.settings = {
            'font_size': 14,
            'opacity': 0.9,
            'mode': 'default',
            'custom_prompt': '',
            'show_transcription': True,
            'window_width': 600,
            'window_height': 500,
            'use_fast_mode': True,  # Use Whisper + VAD for speed
            'whisper_model': 'tiny'  # tiny, base, small models
        }
        
        self.load_settings()
        self.init_claude()
        self.init_ui()
        self.init_audio()
        self.load_history()
        
        # Timer for checking window exclusions
        self.exclusion_timer = QTimer()
        self.exclusion_timer.timeout.connect(self.check_exclusions)
        self.exclusion_timer.start(2000)  # Check every 2 seconds
        
        # Auto-save timer
        self.save_timer = QTimer()
        self.save_timer.timeout.connect(self.save_history)
        self.save_timer.start(30000)  # Save every 30 seconds
    
    def init_claude(self):
        """Initialize Claude API client"""
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            print("Warning: ANTHROPIC_API_KEY not found in environment variables")
            return
        
        try:
            self.claude_client = ClaudeClient(api_key)
        except Exception as e:
            print(f"Error initializing Claude client: {e}")
    
    def init_ui(self):
        """Initialize the user interface"""
        # Window setup
        self.setWindowTitle("AI Overlay Assistant")
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(self.settings['window_width'], self.settings['window_height'])
        self.setMinimumSize(400, 350)
        
        # Main layout
        layout = QVBoxLayout()
        layout.setSpacing(5)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Title bar with drag handle
        title_bar = QFrame()
        title_bar.setStyleSheet("background-color: rgba(40, 40, 40, 200); border-radius: 5px;")
        title_bar.setFixedHeight(30)
        title_layout = QHBoxLayout(title_bar)
        
        title_label = QLabel("🤖 AI Assistant [Drag Here]")
        title_label.setStyleSheet("color: white; font-weight: bold;")
        title_label.setToolTip("Drag this area to move the window")
        title_layout.addWidget(title_label)
        
        title_layout.addStretch()
        
        # Microphone toggle
        self.mic_btn = QPushButton("🎤")
        self.mic_btn.setFixedSize(30, 25)
        self.mic_btn.setStyleSheet("background-color: rgba(0, 150, 0, 150); color: white; border-radius: 12px; font-size: 14px;")
        self.mic_btn.setToolTip("Toggle microphone on/off")
        self.mic_btn.clicked.connect(self.toggle_microphone)
        title_layout.addWidget(self.mic_btn)
        
        # Settings button
        settings_btn = QPushButton("⚙")
        settings_btn.setFixedSize(30, 25)
        settings_btn.setStyleSheet("background-color: rgba(100, 100, 100, 150); color: white; border-radius: 12px; font-size: 14px;")
        settings_btn.setToolTip("Open settings")
        settings_btn.clicked.connect(self.open_settings)
        title_layout.addWidget(settings_btn)
        
        # Close button
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(30, 25)
        close_btn.setStyleSheet("background-color: rgba(255, 0, 0, 150); color: white; border-radius: 12px; font-size: 12px;")
        close_btn.setToolTip("Close application")
        close_btn.clicked.connect(self.close)
        title_layout.addWidget(close_btn)
        
        layout.addWidget(title_bar)
        
        # Main content area
        content_frame = QFrame()
        content_frame.setStyleSheet("background-color: rgba(30, 30, 30, 220); border-radius: 8px;")
        content_layout = QVBoxLayout(content_frame)
        
        # Transcription area (if enabled)
        if self.settings.get('show_transcription', True):
            transcription_label = QLabel("Last Heard:")
            transcription_label.setStyleSheet("color: #cccccc; font-weight: bold;")
            content_layout.addWidget(transcription_label)
            
            self.transcription_area = QTextEdit()
            self.transcription_area.setMaximumHeight(60)
            self.transcription_area.setStyleSheet(f"""
                background-color: rgba(70, 70, 70, 150);
                color: #ffffff;
                border: 1px solid rgba(255, 255, 255, 100);
                border-radius: 5px;
                font-family: 'Arial', sans-serif;
                font-size: {self.settings['font_size']}px;
            """)
            self.transcription_area.setPlaceholderText("Transcribed speech will appear here...")
            self.transcription_area.setReadOnly(True)
            content_layout.addWidget(self.transcription_area)
        else:
            self.transcription_area = None

        # Current response area with status indicators
        response_header = QHBoxLayout()
        response_label = QLabel("AI Response:")
        response_label.setStyleSheet("color: #cccccc; font-weight: bold;")
        response_header.addWidget(response_label)
        
        # Status indicators
        response_header.addStretch()
        
        # Whisper status indicator
        self.whisper_status = QLabel("🎤")
        self.whisper_status.setStyleSheet("color: #666; font-size: 16px;")
        self.whisper_status.setToolTip("Speech recognition status")
        response_header.addWidget(self.whisper_status)
        
        # AI processing indicator  
        self.ai_status = QLabel("🤖")
        self.ai_status.setStyleSheet("color: #666; font-size: 16px;")
        self.ai_status.setToolTip("AI processing status")
        response_header.addWidget(self.ai_status)
        
        content_layout.addLayout(response_header)
        
        self.current_response = QTextEdit()
        self.current_response.setMinimumHeight(100)
        self.current_response.setStyleSheet(f"""
            background-color: rgba(50, 50, 50, 150);
            color: #00ff88;
            border: 1px solid rgba(0, 255, 136, 100);
            border-radius: 5px;
            font-family: 'Arial', sans-serif;
            font-size: {self.settings['font_size']}px;
            padding: 8px;
        """)
        self.current_response.setPlaceholderText("AI responses will appear here...")
        self.current_response.setReadOnly(True)
        content_layout.addWidget(self.current_response)
        
        # Timeline area
        timeline_label = QLabel("Timeline:")
        timeline_label.setStyleSheet("color: white; font-weight: bold;")
        content_layout.addWidget(timeline_label)
        
        self.timeline_area = QScrollArea()
        self.timeline_widget = QWidget()
        self.timeline_layout = QVBoxLayout(self.timeline_widget)
        self.timeline_layout.setSpacing(2)
        
        self.timeline_area.setWidget(self.timeline_widget)
        self.timeline_area.setWidgetResizable(True)
        self.timeline_area.setMinimumHeight(80)
        self.timeline_area.setStyleSheet(f"""
            background-color: rgba(20, 20, 20, 150);
            border: 1px solid rgba(100, 100, 100, 100);
            border-radius: 5px;
        """)
        content_layout.addWidget(self.timeline_area)
        
        # Microphone selection
        mic_group = QGroupBox("Microphone")
        mic_layout = QVBoxLayout(mic_group)
        
        self.mic_selector = QComboBox()
        self.mic_selector.setStyleSheet("""
            QComboBox {
                background-color: rgba(60, 60, 60, 150);
                color: white;
                border: 1px solid rgba(100, 100, 100, 100);
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
            }
        """)
        self.populate_microphone_list()
        self.mic_selector.currentIndexChanged.connect(self.on_microphone_changed)
        mic_layout.addWidget(self.mic_selector)
        
        content_layout.addWidget(mic_group)

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
        
        # Apply window opacity
        self.setWindowOpacity(self.settings['opacity'])
        
        # Enable dragging
        self.drag_position = QPoint()
        
        # Apply dark theme with dynamic font size
        self.update_styles()
    
    def init_audio(self):
        """Initialize audio listening with fast or fallback mode"""
        try:
            if self.settings.get('use_fast_mode', True) and FAST_AUDIO_AVAILABLE:
                # Use fast Whisper + VAD system
                self.audio_listener = FastAudioListener()
                print("Using fast audio processing with Whisper + VAD")
            else:
                # Use optimized fallback Google STT
                self.audio_listener = AudioListener()
                print("Using optimized Google Speech Recognition")
                
            self.audio_listener.transcription_ready.connect(self.handle_transcription)
            self.audio_listener.start()
        except Exception as e:
            print(f"Failed to initialize audio processing, falling back: {e}")
            # Final fallback to basic Google STT
            self.audio_listener = AudioListener()
            self.audio_listener.transcription_ready.connect(self.handle_transcription)
            self.audio_listener.start()
    
    def populate_microphone_list(self):
        """Populate the microphone selector with available microphones"""
        try:
            self.mic_selector.clear()
            microphones = AudioListener.get_microphone_list()
            
            for index, name in microphones:
                # Truncate long microphone names for display
                display_name = name[:50] + "..." if len(name) > 50 else name
                self.mic_selector.addItem(display_name, index)
            
            # Set default selection
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
                # Stop current listener
                self.audio_listener.stop()
                self.audio_listener.wait()
                
                # Start new listener with selected microphone
                self.audio_listener = AudioListener(device_index)
                self.audio_listener.transcription_ready.connect(self.handle_transcription)
                self.audio_listener.start()
                
                mic_name = self.mic_selector.currentText()
                self.current_response.setText(f"Switched to microphone: {mic_name}")
                
        except Exception as e:
            self.current_response.setText(f"Error switching microphone: {str(e)}")
            print(f"Error in microphone change: {e}")
    
    def update_whisper_status(self, status):
        """Update Whisper processing status indicator"""
        if not hasattr(self, 'whisper_status'):
            return
            
        if status == "listening":
            self.whisper_status.setText("🎤")
            self.whisper_status.setStyleSheet("color: #00ff00; font-size: 16px;")  # Green
            self.whisper_status.setToolTip("Listening for speech...")
        elif status == "processing":
            self.whisper_status.setText("🎵")
            self.whisper_status.setStyleSheet("color: #ff8800; font-size: 16px;")  # Orange
            self.whisper_status.setToolTip("Processing speech...")
        elif status == "idle":
            self.whisper_status.setText("🎤")
            self.whisper_status.setStyleSheet("color: #666; font-size: 16px;")     # Gray
            self.whisper_status.setToolTip("Speech recognition idle")
        elif status == "disabled":
            self.whisper_status.setText("🚫")
            self.whisper_status.setStyleSheet("color: #ff0000; font-size: 16px;")  # Red
            self.whisper_status.setToolTip("Microphone disabled")
    
    def update_ai_status(self, status):
        """Update AI processing status indicator"""
        if not hasattr(self, 'ai_status'):
            return
            
        if status == "thinking":
            self.ai_status.setText("🤔")
            self.ai_status.setStyleSheet("color: #0088ff; font-size: 16px;")       # Blue
            self.ai_status.setToolTip("AI thinking...")
        elif status == "responding":
            self.ai_status.setText("💬")
            self.ai_status.setStyleSheet("color: #00ff88; font-size: 16px;")       # Green
            self.ai_status.setToolTip("AI responding...")
        elif status == "idle":
            self.ai_status.setText("🤖")
            self.ai_status.setStyleSheet("color: #666; font-size: 16px;")          # Gray
            self.ai_status.setToolTip("AI idle")
        elif status == "error"):
            self.ai_status.setText("⚠️")
            self.ai_status.setStyleSheet("color: #ff0000; font-size: 16px;")       # Red
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
            QLabel {{
                color: #cccccc;
                font-size: {font_size}px;
            }}
        """)
    
    def toggle_microphone(self):
        """Toggle microphone on/off"""
        self.mic_enabled = not self.mic_enabled
        
        if self.mic_enabled:
            self.mic_btn.setStyleSheet("background-color: rgba(0, 150, 0, 150); color: white; border-radius: 12px; font-size: 14px;")
            self.mic_btn.setToolTip("Microphone ON - Click to turn off")
            if hasattr(self, 'transcription_area') and self.transcription_area:
                self.transcription_area.setPlaceholderText("Transcribed speech will appear here...")
        else:
            self.mic_btn.setStyleSheet("background-color: rgba(150, 0, 0, 150); color: white; border-radius: 12px; font-size: 14px;")
            self.mic_btn.setToolTip("Microphone OFF - Click to turn on")
            if hasattr(self, 'transcription_area') and self.transcription_area:
                self.transcription_area.setPlaceholderText("Microphone is disabled")
    
    def open_settings(self):
        """Open settings dialog"""
        dialog = ConfigDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_settings = dialog.get_settings()
            self.settings.update(new_settings)
            self.apply_settings()
            self.save_settings()
    
    def apply_settings(self):
        """Apply current settings to the UI"""
        # Update window size
        self.resize(self.settings['window_width'], self.settings['window_height'])
        
        # Update opacity
        self.setWindowOpacity(self.settings['opacity'])
        
        # Update styles
        self.update_styles()
        
        # Update font sizes for existing elements
        font_size = self.settings['font_size']
        if hasattr(self, 'current_response'):
            self.current_response.setStyleSheet(f"""
                background-color: rgba(50, 50, 50, 150);
                color: #00ff88;
                border: 1px solid rgba(0, 255, 136, 100);
                border-radius: 5px;
                font-family: 'Arial', sans-serif;
                font-size: {font_size}px;
                padding: 8px;
            """)
        
        if hasattr(self, 'transcription_area') and self.transcription_area:
            self.transcription_area.setStyleSheet(f"""
                background-color: rgba(70, 70, 70, 150);
                color: #ffffff;
                border: 1px solid rgba(255, 255, 255, 100);
                border-radius: 5px;
                font-family: 'Arial', sans-serif;
                font-size: {font_size}px;
            """)
    
    def load_settings(self):
        """Load settings from file"""
        try:
            if self.settings_file.exists():
                with open(self.settings_file, 'r') as f:
                    saved_settings = json.load(f)
                    self.settings.update(saved_settings)
        except Exception as e:
            print(f"Error loading settings: {e}")
    
    def save_settings(self):
        """Save settings to file"""
        try:
            with open(self.settings_file, 'w') as f:
                json.dump(self.settings, f, indent=2)
        except Exception as e:
            print(f"Error saving settings: {e}")
    
    def mousePressEvent(self, event):
        """Handle mouse press for dragging"""
        if event.button() == Qt.MouseButton.LeftButton:
            # Allow dragging from the title bar area (first 40 pixels)
            if event.position().y() <= 40:
                self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
                event.accept()
            else:
                super().mousePressEvent(event)
        else:
            super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """Handle mouse move for dragging"""
        if (event.buttons() == Qt.MouseButton.LeftButton and 
            hasattr(self, 'drag_position')):
            new_pos = event.globalPosition().toPoint() - self.drag_position
            
            # Keep window on screen
            screen = QApplication.primaryScreen().geometry()
            min_x = -self.width() + 50  # Allow partial off-screen but keep 50px visible
            max_x = screen.width() - 50
            min_y = 0
            max_y = screen.height() - 50
            
            new_pos.setX(max(min_x, min(max_x, new_pos.x())))
            new_pos.setY(max(min_y, min(max_y, new_pos.y())))
            
            self.move(new_pos)
            event.accept()
        else:
            super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        """Handle mouse release after dragging"""
        if event.button() == Qt.MouseButton.LeftButton:
            if hasattr(self, 'drag_position'):
                self.setCursor(Qt.CursorShape.ArrowCursor)
                delattr(self, 'drag_position')
                event.accept()
            else:
                super().mouseReleaseEvent(event)
        else:
            super().mouseReleaseEvent(event)
    
    def handle_transcription(self, text: str):
        """Handle new transcription from audio listener"""
        # Check if microphone is enabled
        if not self.mic_enabled:
            return
            
        if not self.claude_client:
            return
        
        # Show transcribed text immediately
        if hasattr(self, 'transcription_area') and self.transcription_area:
            self.transcription_area.setText(text)
        
        # Show "thinking" indicator
        self.current_response.setText("🤔 Processing...")
        
        # Get context from recent conversation (limit for speed)
        context = ""
        if len(self.conversation_history) > 0:
            recent_entries = self.conversation_history[-2:]  # Reduced from 3 to 2 for speed
            context = " ".join([f"{entry.transcription}" for entry in recent_entries])
            # Limit context length
            if len(context) > 200:
                context = context[-200:]  # Keep last 200 chars
        
        # Async callback for AI response
        def on_ai_response(ai_response: str):
            """Called when AI response is ready"""
            try:
                # Create conversation entry
                entry = ConversationEntry(datetime.now(), text, ai_response)
                self.conversation_history.append(entry)
                
                # Update UI
                self.current_response.setText(ai_response)
                self.add_timeline_entry(entry)
                
                # Keep only last 100 entries
                if len(self.conversation_history) > 100:
                    self.conversation_history = self.conversation_history[-100:]
                    
            except Exception as e:
                print(f"Error handling AI response: {e}")
                self.current_response.setText(f"Error: {str(e)}")
        
        # Get AI response asynchronously (non-blocking)
        self.claude_client.get_response_async(
            text, 
            context, 
            self.settings.get('custom_prompt', ''),
            self.settings.get('mode', 'default'),
            callback=on_ai_response
        )
    
    def add_timeline_entry(self, entry: ConversationEntry):
        """Add entry to timeline display"""
        entry_frame = QFrame()
        entry_frame.setStyleSheet("""
            background-color: rgba(40, 40, 40, 150);
            border-left: 3px solid #00ff88;
            border-radius: 3px;
            margin: 1px;
            padding: 3px;
        """)
        
        entry_layout = QVBoxLayout(entry_frame)
        entry_layout.setContentsMargins(5, 3, 5, 3)
        entry_layout.setSpacing(1)
        
        # Timestamp
        time_label = QLabel(entry.timestamp.strftime("%H:%M:%S"))
        time_label.setStyleSheet(f"color: #888888; font-size: {max(8, self.settings['font_size']-2)}px;")
        entry_layout.addWidget(time_label)
        
        # Transcription (truncated)
        trans_text = entry.transcription[:80] + "..." if len(entry.transcription) > 80 else entry.transcription
        trans_label = QLabel(f"🎤 {trans_text}")
        trans_label.setStyleSheet(f"color: #cccccc; font-size: {max(10, self.settings['font_size']-1)}px;")
        trans_label.setWordWrap(True)
        entry_layout.addWidget(trans_label)
        
        # AI Response (truncated)
        resp_text = entry.ai_response[:80] + "..." if len(entry.ai_response) > 80 else entry.ai_response
        resp_label = QLabel(f"🤖 {resp_text}")
        resp_label.setStyleSheet(f"color: #00ff88; font-size: {max(10, self.settings['font_size']-1)}px;")
        resp_label.setWordWrap(True)
        entry_layout.addWidget(resp_label)
        
        self.timeline_layout.insertWidget(0, entry_frame)  # Insert at top
        
        # Limit timeline entries shown
        if self.timeline_layout.count() > 20:
            item = self.timeline_layout.takeAt(20)
            if item.widget():
                item.widget().deleteLater()
    
    def check_exclusions(self):
        """Check if overlay should be hidden due to video conferencing apps"""
        should_hide = WindowExcluder.should_hide_overlay()
        
        if should_hide and self.isVisible():
            self.hide()
        elif not should_hide and not self.isVisible():
            self.show()
    
    def export_data(self):
        """Export conversation history to JSON file"""
        try:
            export_file = Path.home() / f"overlay_assistant_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            
            export_data = {
                'export_timestamp': datetime.now().isoformat(),
                'total_entries': len(self.conversation_history),
                'conversations': [entry.to_dict() for entry in self.conversation_history]
            }
            
            with open(export_file, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            
            self.current_response.setText(f"Exported {len(self.conversation_history)} entries to:\n{export_file}")
            
        except Exception as e:
            self.current_response.setText(f"Export failed: {str(e)}")
    
    def clear_timeline(self):
        """Clear the timeline and conversation history"""
        self.conversation_history.clear()
        
        # Clear timeline UI
        for i in reversed(range(self.timeline_layout.count())):
            item = self.timeline_layout.itemAt(i)
            if item.widget():
                item.widget().deleteLater()
        
        self.current_response.setText("Timeline cleared.")
    
    def save_history(self):
        """Save conversation history to file"""
        try:
            data = {
                'conversations': [entry.to_dict() for entry in self.conversation_history]
            }
            
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            print(f"Error saving history: {e}")
    
    def load_history(self):
        """Load conversation history from file"""
        try:
            if self.data_file.exists():
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                for conv_data in data.get('conversations', []):
                    entry = ConversationEntry(
                        datetime.fromisoformat(conv_data['timestamp']),
                        conv_data['transcription'],
                        conv_data['ai_response']
                    )
                    self.conversation_history.append(entry)
                    self.add_timeline_entry(entry)
                    
        except Exception as e:
            print(f"Error loading history: {e}")
    
    def closeEvent(self, event):
        """Handle application close"""
        self.save_history()
        self.save_settings()
        
        if self.audio_listener:
            self.audio_listener.stop()
            self.audio_listener.wait()
        
        event.accept()

def main():
    app = QApplication(sys.argv)
    
    # Set application properties
    app.setApplicationName("AI Overlay Assistant")
    app.setQuitOnLastWindowClosed(True)
    
    # Create and show overlay
    overlay = OverlayWidget()
    
    # Position overlay in top-right corner
    screen = app.primaryScreen().geometry()
    overlay.move(screen.width() - overlay.width() - 20, 20)
    
    overlay.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()