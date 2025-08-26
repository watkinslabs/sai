"""
Audio processing and speech recognition for SAI
"""

import queue
import time
import speech_recognition as sr
import sounddevice as sd
import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal, QThreadPool

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
            
            # Process in frames
            frames = len(pcm_data) // (frame_size * 2)  # 2 bytes per sample
            speech_frames = 0
            
            for i in range(frames):
                start = i * frame_size * 2
                end = start + frame_size * 2
                frame_data = pcm_data[start:end]
                
                if len(frame_data) == frame_size * 2:
                    if self.vad.is_speech(frame_data, self.sample_rate):
                        speech_frames += 1
            
            # Consider it speech if more than 30% of frames contain speech
            return speech_frames > (frames * 0.3)
            
        except Exception:
            # Fallback: simple energy-based detection
            energy = np.sum(audio_chunk ** 2)
            return energy > 0.01  # Threshold for basic energy detection
    
    def transcribe_audio(self, audio_data):
        """Transcribe audio using Whisper"""
        if not self.whisper_model:
            return ""
        
        try:
            # Ensure audio is float32 and normalized
            audio = audio_data.astype(np.float32)
            
            # Whisper expects audio to be in the range [-1, 1] and at 16kHz
            if audio.max() > 1.0:
                audio = audio / 32767.0  # Normalize if needed
            
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
            self.whisper_status_changed.emit("processing")
            text = self.transcribe_audio(audio_data)
            if text and len(text.strip()) > 2:  # Minimum text length
                self.transcription_ready.emit(text)
            self.whisper_status_changed.emit("listening")
        
        # Run transcription in thread pool to avoid blocking
        QThreadPool.globalInstance().start(
            lambda: transcribe_worker()
        )
    
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