#!/usr/bin/env python3
"""
Basic test script to verify core functionality without UI
"""

import sys
import os
from dotenv import load_dotenv
import sounddevice as sd

# Load environment variables
load_dotenv()

def test_microphone():
    """Test microphone access"""
    print("Testing microphone access...")
    try:
        devices = sd.query_devices()
        input_devices = [d for d in devices if d['max_input_channels'] > 0]
        print(f"Found {len(input_devices)} input devices")
        
        # Test recording a short sample
        print("Testing audio recording...")
        duration = 1.0
        sample_rate = 16000
        audio_data = sd.rec(
            int(duration * sample_rate),
            samplerate=sample_rate,
            channels=1,
            dtype='float32'
        )
        sd.wait()
        print(f"Recorded {len(audio_data)} samples successfully")
        return True
    except Exception as e:
        print(f"Microphone test failed: {e}")
        return False

def test_claude_api():
    """Test Claude API connection"""
    print("Testing Claude API...")
    try:
        import anthropic
        
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            print("No ANTHROPIC_API_KEY found in environment")
            return False
        
        client = anthropic.Anthropic(api_key=api_key)
        
        # Test with a simple message
        message = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=50,
            messages=[
                {"role": "user", "content": "Say 'API test successful' if you can read this"}
            ]
        )
        
        response = message.content[0].text
        print(f"Claude response: {response}")
        return "test successful" in response.lower()
        
    except Exception as e:
        print(f"Claude API test failed: {e}")
        return False

def test_speech_recognition():
    """Test speech recognition import"""
    print("Testing speech recognition...")
    try:
        import speech_recognition as sr
        recognizer = sr.Recognizer()
        print("Speech recognition module loaded successfully")
        return True
    except Exception as e:
        print(f"Speech recognition test failed: {e}")
        return False

def test_gui_components():
    """Test PyQt6 import"""
    print("Testing GUI components...")
    try:
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import Qt
        print("PyQt6 components loaded successfully")
        return True
    except Exception as e:
        print(f"GUI test failed: {e}")
        return False

def main():
    print("AI Overlay Assistant - Basic Tests")
    print("=" * 40)
    
    tests = [
        ("Microphone", test_microphone),
        ("Speech Recognition", test_speech_recognition),
        ("GUI Components", test_gui_components),
        ("Claude API", test_claude_api),
    ]
    
    results = []
    for name, test_func in tests:
        print(f"\n{name}:")
        result = test_func()
        results.append((name, result))
        print(f"Status: {'✓ PASS' if result else '✗ FAIL'}")
    
    print("\n" + "=" * 40)
    print("Test Summary:")
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {name}: {status}")
    
    all_passed = all(result for _, result in results)
    print(f"\nOverall: {'✓ ALL TESTS PASSED' if all_passed else '✗ SOME TESTS FAILED'}")
    
    if not all_passed:
        print("\nNext steps:")
        print("- For microphone issues: check audio permissions and devices")
        print("- For API issues: verify your .env file has ANTHROPIC_API_KEY")
        print("- For GUI issues: ensure PyQt6 is properly installed")
    else:
        print("\nReady to run: uv run python overlay_assistant.py")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())