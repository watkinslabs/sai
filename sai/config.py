"""
Configuration and settings management for SAI
"""

import os
from typing import Dict, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    """Configuration class for SAI settings"""
    
    DEFAULT_SETTINGS = {
        'font_size': 12,
        'opacity': 0.9,
        'mode': 'default',
        'custom_prompt': '',
        'show_transcription': True,
        'window_width': 600,
        'window_height': 400,
        'use_fast_mode': True,
        'microphone_device': None,
    }
    
    @staticmethod
    def get_api_key() -> str:
        """Get Claude API key from environment"""
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required")
        return api_key
    
    @staticmethod
    def get_default_settings() -> Dict[str, Any]:
        """Get default application settings"""
        return Config.DEFAULT_SETTINGS.copy()

class ConversationEntry:
    """Represents a single conversation entry"""
    
    def __init__(self, timestamp, transcription: str, ai_response: str):
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
            # import psutil
            # for proc in psutil.process_iter(['pid', 'name']):
            #     proc_name = proc.info['name'].lower()
            #     if any(excluded in proc_name for excluded in WindowExcluder.EXCLUDED_PROCESSES):
            #         return True
            # return False
        except Exception:
            return False