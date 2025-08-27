#!/usr/bin/env python3
"""
SAI Setup - Handle optional Whisper installation and configuration
"""

import sys
import subprocess
import os
from pathlib import Path
import argparse

def check_whisper_available():
    """Check if Whisper dependencies are available"""
    try:
        import whisper
        import webrtcvad
        import torch
        return True
    except ImportError as e:
        print(f"Whisper dependencies not available: {e}")
        return False

def install_whisper():
    """Install Whisper dependencies"""
    print("Installing Whisper dependencies...")
    
    # Use current Python executable to install packages
    python_exe = sys.executable
    
    try:
        # Install with pip
        subprocess.check_call([
            python_exe, "-m", "pip", "install",
            "torch>=2.0.0",
            "webrtcvad>=2.0.10", 
            "openai-whisper==20231117",
            "numba==0.58.1",
            "scipy>=1.13.1"
        ])
        print("✅ Whisper dependencies installed successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install Whisper dependencies: {e}")
        return False

def install_with_uv():
    """Install Whisper dependencies using uv if available"""
    try:
        # Check if uv is available
        subprocess.check_call(["uv", "--version"], stdout=subprocess.DEVNULL)
        
        print("Installing Whisper dependencies with uv...")
        subprocess.check_call([
            "uv", "add", 
            "torch>=2.0.0",
            "webrtcvad>=2.0.10",
            "openai-whisper==20231117", 
            "numba==0.58.1",
            "scipy>=1.13.1"
        ])
        print("✅ Whisper dependencies installed with uv!")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def setup_api_key():
    """Setup Claude API key"""
    print("\\n🔧 Setting up Claude API key...")
    
    # Check if already set
    current_key = os.getenv('ANTHROPIC_API_KEY')
    if current_key:
        print(f"✅ API key already set: {current_key[:8]}...")
        change = input("Change API key? (y/N): ").lower().strip()
        if change != 'y':
            return
    
    # Get API key from user
    print("\\nGet your Claude API key from: https://console.anthropic.com/")
    api_key = input("Enter your Claude API key: ").strip()
    
    if not api_key:
        print("❌ No API key provided")
        return
    
    # Save to .env file
    env_file = Path.home() / '.sai' / '.env'
    env_file.parent.mkdir(exist_ok=True)
    
    # Read existing .env content
    env_content = []
    if env_file.exists():
        with open(env_file, 'r') as f:
            env_content = f.readlines()
    
    # Remove existing ANTHROPIC_API_KEY lines
    env_content = [line for line in env_content if not line.startswith('ANTHROPIC_API_KEY=')]
    
    # Add new API key
    env_content.append(f'ANTHROPIC_API_KEY={api_key}\\n')
    
    # Write back to file
    with open(env_file, 'w') as f:
        f.writelines(env_content)
    
    print(f"✅ API key saved to {env_file}")
    
    # Also set for current session
    os.environ['ANTHROPIC_API_KEY'] = api_key

def check_system_dependencies():
    """Check for system-level audio dependencies"""
    print("\\n🔧 Checking system dependencies...")
    
    # Check for audio libraries
    try:
        import sounddevice
        import pyaudio
        print("✅ Audio libraries available")
    except ImportError:
        print("⚠️  Audio libraries may need system packages:")
        print("   Ubuntu/Debian: sudo apt install portaudio19-dev python3-pyaudio")
        print("   Fedora: sudo dnf install portaudio-devel")
        print("   macOS: brew install portaudio")

def show_installation_summary():
    """Show post-installation instructions"""
    whisper_available = check_whisper_available()
    
    print("\\n" + "="*60)
    print("🎉 SAI Setup Complete!")
    print("="*60)
    
    print("\\n📦 Installation Status:")
    print(f"   Core SAI: ✅ Installed") 
    print(f"   Whisper:  {'✅ Available' if whisper_available else '❌ Not installed'}")
    
    print("\\n🚀 How to run SAI:")
    print("   sai                    # Start SAI with GUI")
    print("   sai --help             # Show all options")
    
    if not whisper_available:
        print("\\n⚡ For fast local speech recognition:")
        print("   sai-setup --whisper   # Install Whisper dependencies")
        print("   pip install sai-assistant[whisper]  # Or install with whisper")
    
    print("\\n🔧 Configuration:")
    print("   • Set ANTHROPIC_API_KEY in ~/.sai/.env")
    print("   • Run sai-setup --api-key to configure")
    
    print("\\n📚 More info: https://github.com/watkinslabs/sai")

def main():
    """Main setup function"""
    parser = argparse.ArgumentParser(description='SAI Setup - Install and configure SAI components')
    parser.add_argument('--whisper', action='store_true', help='Install Whisper dependencies')
    parser.add_argument('--api-key', action='store_true', help='Setup Claude API key')
    parser.add_argument('--check', action='store_true', help='Check installation status')
    parser.add_argument('--all', action='store_true', help='Install everything')
    
    args = parser.parse_args()
    
    if not any(vars(args).values()):
        # No arguments provided - run interactive setup
        print("🎯 SAI Interactive Setup")
        print("=" * 30)
        
        # Check current status
        check_system_dependencies()
        whisper_available = check_whisper_available()
        
        if not whisper_available:
            install_whisper_choice = input("\\nInstall Whisper for local speech recognition? (Y/n): ").lower().strip()
            if install_whisper_choice != 'n':
                if not install_with_uv():
                    install_whisper()
        
        setup_api_key()
        show_installation_summary()
        return
    
    if args.check:
        check_system_dependencies()
        whisper_available = check_whisper_available()
        print(f"Whisper available: {whisper_available}")
        return
    
    if args.whisper or args.all:
        if not install_with_uv():
            install_whisper()
    
    if args.api_key or args.all:
        setup_api_key()
    
    if args.all:
        show_installation_summary()

if __name__ == '__main__':
    main()