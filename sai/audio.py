"""
Audio processing and speech recognition for SAI
"""

import queue
import time
import speech_recognition as sr
import sounddevice as sd
import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal, QThreadPool, QRunnable

try:
    import whisper
    import webrtcvad
    FAST_AUDIO_AVAILABLE = True
except ImportError:
    FAST_AUDIO_AVAILABLE = False
    print("Fast audio dependencies not available, using fallback mode")

class FastAudioListener(QThread):
    """Optimized audio listener with local Whisper and VAD"""
    
    transcription_ready = pyqtSignal(str)
    whisper_status_changed = pyqtSignal(str)
    claude_ready = pyqtSignal(str)  # Separate signal for Claude processing
    
    def __init__(self, device_index=None):
        super().__init__()
        self.device_index = device_index
        self.running = False
        self.sample_rate = 16000  # Will be updated based on device
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
        
        # Voice Activity Detection - less sensitive to avoid false positives
        self.vad = webrtcvad.Vad(2)  # Aggressiveness level 0-3 (2 is more selective)
        
        # Audio processing
        self.audio_queue = queue.Queue()
        self.speech_frames = []
        self.is_speaking = False
        self.silence_count = 0
        self.max_silence = 3  # Much faster pause detection (1.5 seconds)
        self.min_speech_frames = 2  # Even faster minimum (1 second)
        self.max_speech_frames = 16  # Process after 8 seconds max
        
        # Thread-safe transcription results  
        self._transcription_result = None
        self._transcription_ready = False
        self._partial_transcription = ""
        self._partial_ready = False
        
        # Accumulate all transcribed text for complete Claude requests
        self._accumulated_text = ""
        self._text_segments = []
        
    def update_microphone(self, device_index):
        """Update the microphone device"""
        self.device_index = device_index
    
    @staticmethod
    def get_microphone_list():
        """Get list of available audio sources (mics + loopback), sorted by name"""
        try:
            audio_sources = []
            devices = sd.query_devices()
            
            for i, device in enumerate(devices):
                device_name = device['name']
                
                # Add input devices (microphones)
                if device['max_input_channels'] > 0:
                    if 'loopback' in device_name.lower() or 'stereo mix' in device_name.lower() or 'what u hear' in device_name.lower():
                        display_name = f"🔊 {device_name} (System Audio)"
                    else:
                        display_name = f"🎤 {device_name}"
                    audio_sources.append((i, display_name))
                
                # For Linux PulseAudio: Look for monitor devices (system audio capture)
                elif 'monitor' in device_name.lower() and device['max_input_channels'] > 0:
                    # This is a monitor device - can capture system audio
                    base_name = device_name.replace('.monitor', '').replace(' Monitor', '')
                    display_name = f"🔊 {base_name} (System Audio)"
                    audio_sources.append((i, display_name))
            
            # Sort by type (microphones first, then system audio)
            audio_sources.sort(key=lambda x: (not x[1].startswith('🎤'), x[1].lower()))
            return audio_sources
        except Exception as e:
            print(f"Error getting audio device list: {e}")
            return [(None, "🎤 Default Microphone")]
    
    @staticmethod
    def is_system_audio_device(device_name):
        """Check if a device is likely a system audio capture device"""
        system_keywords = [
            'loopback', 'stereo mix', 'what u hear', 'monitor', 
            'wave out mix', 'speakers', 'headphones'
        ]
        return any(keyword in device_name.lower() for keyword in system_keywords)
    
    @staticmethod 
    def get_system_audio_info():
        """Get information about available system audio capture methods"""
        try:
            devices = sd.query_devices()
            system_devices = []
            
            for i, device in enumerate(devices):
                if device['max_input_channels'] > 0:
                    device_name = device['name']
                    if FastAudioListener.is_system_audio_device(device_name):
                        system_devices.append({
                            'index': i,
                            'name': device_name,
                            'channels': device['max_input_channels'],
                            'sample_rate': device['default_samplerate']
                        })
            
            return system_devices
        except Exception as e:
            print(f"Error getting system audio info: {e}")
            return []
    
    def is_speech(self, audio_chunk):
        """Check if audio chunk contains speech using WebRTC VAD"""
        try:
            # Convert to 16-bit PCM
            pcm_data = (audio_chunk * 32767).astype(np.int16).tobytes()
            
            # VAD works with specific frame sizes (10, 20, or 30ms) at 8, 16, 32, or 48kHz
            # We need to resample to a supported rate for VAD
            vad_sample_rate = 16000  # VAD-supported rate
            if self.sample_rate not in [8000, 16000, 32000, 48000]:
                # Resample audio chunk to 16kHz for VAD with consistent float32
                audio_chunk = np.array(audio_chunk, dtype=np.float32)
                target_length = int(len(audio_chunk) * vad_sample_rate / self.sample_rate)
                old_indices = np.linspace(0.0, len(audio_chunk) - 1.0, len(audio_chunk), dtype=np.float32)
                new_indices = np.linspace(0.0, len(audio_chunk) - 1.0, target_length, dtype=np.float32)
                audio_chunk = np.interp(new_indices, old_indices, audio_chunk).astype(np.float32)
            else:
                vad_sample_rate = self.sample_rate
            
            # Convert to 16-bit PCM for resampled audio
            pcm_data = (audio_chunk * 32767).astype(np.int16).tobytes()
            
            # VAD works with specific frame sizes (10, 20, or 30ms)
            frame_duration = 30  # ms
            frame_size = int(vad_sample_rate * frame_duration / 1000)
            
            # Process in frames
            frames = len(pcm_data) // (frame_size * 2)  # 2 bytes per sample
            speech_frames = 0
            
            for i in range(frames):
                start = i * frame_size * 2
                end = start + frame_size * 2
                frame_data = pcm_data[start:end]
                
                if len(frame_data) == frame_size * 2:
                    if self.vad.is_speech(frame_data, vad_sample_rate):
                        speech_frames += 1
            
            # Consider it speech if more than 50% of frames contain speech (even less sensitive)
            return speech_frames > (frames * 0.5)
            
        except Exception:
            # Fallback: simple energy-based detection with higher threshold
            energy = np.sum(audio_chunk ** 2)
            return energy > 0.02  # Higher threshold to reduce false positives
    
    def transcribe_audio(self, audio_data):
        """Transcribe audio using Whisper"""
        if not self.whisper_model:
            return ""
        
        try:
            # Ensure audio is float32 consistently throughout
            audio = np.array(audio_data, dtype=np.float32)
            
            # Whisper expects audio to be in the range [-1, 1] and at 16kHz
            if audio.max() > 1.0:
                audio = audio / 32767.0  # Normalize if needed
            
            # Resample to 16kHz if needed (Whisper's expected rate)
            if self.sample_rate != 16000:
                # Use scipy-style resampling with consistent float32 types
                from scipy import signal
                try:
                    # Try scipy resampling first (more accurate)
                    target_samples = int(len(audio) * 16000 / self.sample_rate)
                    audio = signal.resample(audio, target_samples).astype(np.float32)
                except ImportError:
                    # Fallback to simple linear interpolation with explicit float32
                    target_length = int(len(audio) * 16000.0 / self.sample_rate)
                    old_indices = np.linspace(0.0, len(audio) - 1.0, len(audio), dtype=np.float32)
                    new_indices = np.linspace(0.0, len(audio) - 1.0, target_length, dtype=np.float32)
                    audio = np.interp(new_indices, old_indices, audio).astype(np.float32)
            
            # Final dtype check
            audio = audio.astype(np.float32)
            
            # Transcribe with Whisper
            result = self.whisper_model.transcribe(audio, fp16=False, language='en')
            return result.get('text', '').strip()
            
        except Exception as e:
            print(f"Whisper transcription error: {e}")
            return ""
    
    def run(self):
        """Main audio processing loop"""
        self.running = True
        
        # Try to find working device
        if self.device_index is None:
            self.device_index = self.find_working_device()
        
        if self.device_index is None:
            print("No working audio devices found")
            return
        
        # Get device sample rate
        try:
            devices = sd.query_devices()
            device_info = devices[self.device_index]
            self.sample_rate = int(device_info['default_samplerate'])
            self.chunk_size = int(0.5 * self.sample_rate)  # Update chunk size
            print(f"Using device sample rate: {self.sample_rate}Hz")
        except Exception as e:
            print(f"Error getting device info: {e}, using default 44100Hz")
            self.sample_rate = 44100
            self.chunk_size = int(0.5 * self.sample_rate)
        
        def audio_callback(indata, frames, time, status):
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
            self.whisper_status_changed.emit("listening")
            
            while self.running:
                try:
                    # Get audio chunk with timeout
                    audio_chunk = self.audio_queue.get(timeout=1.0)
                    
                    # Check for speech activity
                    has_speech = self.is_speech(audio_chunk)
                    
                    if has_speech:
                        # If we just started speaking after silence, reset accumulation
                        if not self.is_speaking:
                            self._accumulated_text = ""
                            self._text_segments = []
                            print("New speech started - reset text accumulation")
                        
                        self.speech_frames.append(audio_chunk)
                        self.is_speaking = True
                        self.silence_count = 0
                    else:
                        if self.is_speaking:
                            self.silence_count += 1
                            
                            # Add a bit of trailing silence
                            if self.silence_count <= 3:
                                self.speech_frames.append(audio_chunk)
                    
                    # Process speech in multiple scenarios for faster response
                    should_process = False
                    
                    # Process if we have enough silence after speech
                    if self.is_speaking and self.silence_count >= self.max_silence:
                        should_process = True
                    
                    # Process if we have enough speech frames (streaming behavior)
                    elif self.is_speaking and len(self.speech_frames) >= self.max_speech_frames:
                        should_process = True
                        # Don't reset completely - keep some context
                        
                    if should_process and len(self.speech_frames) >= self.min_speech_frames:
                        # Combine speech frames
                        speech_audio = np.concatenate(self.speech_frames)
                        
                        # Show partial transcription INSTANTLY while processing
                        self._partial_transcription = f"[Processing {len(self.speech_frames)} frames of speech...]"
                        self._partial_ready = True
                        
                        # Transcribe in separate thread to avoid blocking
                        is_final = self.silence_count >= self.max_silence
                        self.process_speech_async(speech_audio, is_final)
                        
                        # For streaming mode, keep some overlap for context
                        if len(self.speech_frames) >= self.max_speech_frames:
                            # Keep last 5 frames for context
                            self.speech_frames = self.speech_frames[-5:]
                        else:
                            # Complete reset for end of speech
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
    
    def process_speech_async(self, audio_data, is_final=False):
        """Process speech transcription asynchronously"""
        # Emit status change from main thread (this QThread)
        self.whisper_status_changed.emit("processing")
        
        # Use Python threading instead of Qt threading to avoid Qt object issues
        import threading
        
        def transcribe_worker():
            try:
                text = self.transcribe_audio(audio_data)
                # Store results for main thread to pick up
                self._transcription_result = text
                self._transcription_ready = True
                self._is_final = is_final  # Track if this should be sent to Claude
            except Exception as e:
                print(f"Transcription worker error: {e}")
                self._transcription_result = None
                self._transcription_ready = True
                self._is_final = is_final
        
        # Run in Python thread instead of Qt thread pool
        thread = threading.Thread(target=transcribe_worker, daemon=True)
        thread.start()
    
    def check_transcription_results(self):
        """Check for transcription results from worker thread (call from main thread)"""
        # Check for partial transcriptions (instant display)
        if self._partial_ready:
            self._partial_ready = False
            # Emit partial transcription for instant display
            self.transcription_ready.emit(self._partial_transcription)
            
        # Check for full transcriptions (accumulate and send to Claude if final)
        if self._transcription_ready:
            self._transcription_ready = False
            if self._transcription_result and len(self._transcription_result.strip()) > 2:
                transcribed_text = self._transcription_result.strip()
                
                # Filter out suspicious single-word false positives
                if len(transcribed_text.split()) == 1 and transcribed_text.upper() in ["YOU", "THE", "A", "I", "IT", "IS", "TO", "AND", "OR"]:
                    print(f"Filtering out suspicious single word: '{transcribed_text}'")
                    # Reset status back to listening
                    self.whisper_status_changed.emit("listening")
                    self._transcription_result = None
                    return
                
                # Emit the actual transcription for instant display
                self.transcription_ready.emit(transcribed_text)
                
                # Accumulate this text segment
                if transcribed_text not in self._text_segments:  # Avoid duplicates
                    self._text_segments.append(transcribed_text)
                    self._accumulated_text = " ".join(self._text_segments)
                    print(f"Accumulated text: '{self._accumulated_text}'")
                
                # If this is final (pause detected), send ALL accumulated text to Claude
                if getattr(self, '_is_final', False):
                    if self._accumulated_text and hasattr(self, 'claude_ready'):
                        # Filter: Only send to Claude if we have multiple words (at least 2)
                        word_count = len(self._accumulated_text.split())
                        if word_count >= 2:
                            print(f"Sending to Claude ({word_count} words): '{self._accumulated_text}'")
                            self.claude_ready.emit(self._accumulated_text)
                        else:
                            print(f"Skipping Claude - only {word_count} word(s): '{self._accumulated_text}'")
                    
                    # Reset accumulation after processing
                    self._accumulated_text = ""
                    self._text_segments = []
                    print("Reset accumulated text after processing")
            
            # Reset status back to listening
            self.whisper_status_changed.emit("listening")
            self._transcription_result = None
    
    def find_working_device(self):
        """Find first working audio input device"""
        try:
            devices = sd.query_devices()
            input_devices = [(i, d) for i, d in enumerate(devices) if d['max_input_channels'] > 0]
            
            if not input_devices:
                return None
                
            print(f"Testing {len(input_devices)} audio devices...")
        
        except Exception as e:
            print(f"Error querying devices: {e}")
            return None
        
        # Test each device to find one that works
        for device_id, device_info in input_devices:
            try:
                print(f"Testing device {device_id}: {device_info['name']}")
            except:
                print(f"Testing device {device_id}")
            
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
        self.error_count = 0
        self.max_errors = 10
    
    @staticmethod
    def get_microphone_list():
        """Get list of available microphones, sorted by name"""
        try:
            mic_list = []
            devices = sd.query_devices()
            for i, device in enumerate(devices):
                if device['max_input_channels'] > 0:  # Only input devices
                    mic_list.append((i, device['name']))
            # Sort by device name for better organization
            mic_list.sort(key=lambda x: x[1].lower())
            return mic_list
        except Exception as e:
            print(f"Error getting microphone list: {e}")
            return [(None, "Default Microphone")]
    
    def run(self):
        """Main listening loop"""
        if not self.should_run:
            return
            
        self.running = True
        
        # Set up microphone
        if self.device_index is not None:
            try:
                mic = sr.Microphone(device_index=self.device_index, sample_rate=self.sample_rate)
            except Exception as e:
                print(f"Failed to use device {self.device_index}: {e}")
                mic = sr.Microphone(sample_rate=self.sample_rate)
        else:
            mic = sr.Microphone(sample_rate=self.sample_rate)
        
        print(f"Listening with Google Speech Recognition on device: {self.device_index}")
        
        with mic as source:
            # Calibrate for ambient noise (but only briefly)
            print("Calibrating for ambient noise...")
            self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
        
        while self.running and self.should_run and self.error_count < self.max_errors:
            try:
                with mic as source:
                    # Listen with timeout
                    audio = self.recognizer.listen(source, timeout=1, phrase_time_limit=10)
                
                # Try to recognize the speech
                try:
                    text = self.recognizer.recognize_google(audio, language='en-US')
                    
                    if text and len(text.strip()) > 1:
                        self.transcription_ready.emit(text)
                        self.error_count = 0  # Reset error count on success
                        
                except sr.UnknownValueError:
                    # Google Speech Recognition could not understand audio
                    pass
                except sr.RequestError as e:
                    print(f"Google Speech Recognition error: {e}")
                    self.error_count += 1
                    time.sleep(1)
                    
            except sr.WaitTimeoutError:
                # No speech detected, continue
                continue
            except Exception as e:
                print(f"Audio listening error: {e}")
                self.error_count += 1
                time.sleep(0.5)
                
        if self.error_count >= self.max_errors:
            print("Too many audio errors, stopping listener")
            self.should_run = False
    
    def stop(self):
        """Stop the audio listener"""
        self.running = False
        self.should_run = False