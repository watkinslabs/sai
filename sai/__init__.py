"""
SAI - Smart AI Overlay Assistant
A powerful overlay application with real-time microphone transcription and Claude API integration
"""

__version__ = "0.1.0"
__author__ = "Chris Watkins"

from .main import main
from .ui import OverlayWidget
from .audio import FastAudioListener, AudioListener
from .claude_client import ClaudeClient

__all__ = ["main", "OverlayWidget", "FastAudioListener", "AudioListener", "ClaudeClient"]