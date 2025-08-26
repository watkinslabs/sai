"""
Command Line Interface for SAI
"""

import argparse
import sys
from pathlib import Path
from .main import main as run_overlay
from .config import Config

def check_requirements():
    """Check if all requirements are met"""
    print("Checking SAI requirements...")
    
    # Check Python version
    if sys.version_info < (3, 9):
        print(f"❌ Python 3.9+ required (found {sys.version_info.major}.{sys.version_info.minor})")
        return False
    else:
        print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    
    # Check API key
    try:
        Config.get_api_key()
        print("✅ ANTHROPIC_API_KEY found")
    except ValueError as e:
        print(f"❌ {e}")
        return False
    
    # Check audio dependencies
    try:
        import sounddevice
        print("✅ Audio system available")
    except ImportError:
        print("❌ Audio system not available")
        return False
    
    # Check Whisper (optional)
    try:
        import whisper
        print("✅ Whisper available for fast transcription")
    except ImportError:
        print("⚠️  Whisper not available, using Google STT fallback")
    
    print("✅ All requirements satisfied")
    return True

def setup_env():
    """Set up environment file"""
    env_example = Path(".env.example")
    env_file = Path(".env")
    
    if env_file.exists():
        print("✅ .env file already exists")
        return
    
    if env_example.exists():
        print("Creating .env file from template...")
        env_file.write_text(env_example.read_text())
        print("✅ .env file created")
        print("⚠️  Please edit .env file and add your ANTHROPIC_API_KEY")
    else:
        print("Creating .env file...")
        env_file.write_text("ANTHROPIC_API_KEY=your_api_key_here\\n")
        print("✅ .env file created")
        print("⚠️  Please edit .env file and add your ANTHROPIC_API_KEY")

def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="SAI - Smart AI Overlay Assistant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  sai run              # Start the overlay
  sai check            # Check requirements
  sai setup            # Set up environment file

For more information, visit: https://github.com/watkinslabs/sai
        """
    )
    
    parser.add_argument(
        "command",
        nargs="?",
        choices=["run", "check", "setup"],
        default="run",
        help="Command to execute (default: run)"
    )
    
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug output"
    )
    
    parser.add_argument(
        "--version",
        action="version",
        version="SAI v0.1.0"
    )
    
    args = parser.parse_args()
    
    if args.debug:
        import os
        os.environ["DEBUG"] = "1"
    
    if args.command == "check":
        success = check_requirements()
        sys.exit(0 if success else 1)
    elif args.command == "setup":
        setup_env()
        sys.exit(0)
    elif args.command == "run":
        if not check_requirements():
            print("\\n❌ Requirements not satisfied. Run 'sai setup' first.")
            sys.exit(1)
        
        print("Starting SAI overlay...")
        return run_overlay()
    
if __name__ == "__main__":
    main()