# SAI - Smart AI Assistant

A powerful overlay application for Linux that provides real-time AI assistance through voice interaction. SAI features a draggable, always-on-top interface with local Whisper transcription, Claude AI integration, system audio capture, and comprehensive conversation management.

**Repository**: https://github.com/watkinslabs/sai

![Status](https://img.shields.io/badge/Status-Active-brightgreen) ![Python 3.9+](https://img.shields.io/badge/Python-3.9+-blue) ![License MIT](https://img.shields.io/badge/License-MIT-green)

## Features

### Core Functionality
- **Always-on-top overlay** - Draggable, resizable window that stays above all applications
- **Voice interaction** - Continuous microphone monitoring with speech-to-text transcription
- **Claude AI integration** - Real-time responses with configurable AI modes and custom prompts
- **System tray integration** - Hide/restore via system tray with quick microphone toggle
- **Question input** - Type questions directly for immediate AI processing
- **Timeline history** - Complete conversation history with timestamps and export capabilities

### Audio Processing
- **Local OpenAI Whisper** - Fast, accurate local transcription (primary mode)
- **Google Speech Recognition** - Cloud-based fallback transcription
- **Multi-microphone support** - Select from any available audio input device
- **System audio capture** - Monitor and transcribe audio from applications (loopback/stereo mix)
- **Voice Activity Detection** - Intelligent silence detection with false positive filtering
- **Real-time transcription** - Instant text display with accumulated Claude processing

### Interface & Controls
- **Compositor-aware dragging** - Native window dragging that works with all window managers
- **Position persistence** - Remembers window location between sessions  
- **Microphone toggle** - Button and spacebar shortcut to enable/disable audio input
- **Resize grip** - Visual resizing handle in bottom-right corner
- **System audio info** - Built-in help for configuring audio loopback on different platforms
- **Configurable templates** - Edit AI response templates for different use cases

### Smart Features
- **Minimum word filtering** - Prevents single-word false positives from being sent to Claude
- **Response caching** - Intelligent caching system for repeated queries
- **Async processing** - Non-blocking API calls maintain responsive interface
- **Thread-safe UI updates** - Dedicated UI updater prevents Qt threading issues
- **Settings persistence** - All preferences saved and restored automatically

## Installation

### Option 1: Install from PyPI (Recommended)

```bash
# Basic installation (Google Speech Recognition)
pip install sai-assistant

# With Whisper for fast local transcription (recommended)
pip install sai-assistant[whisper]

# Full installation with all features
pip install sai-assistant[full]
```

### Option 2: Install from Source

```bash
git clone https://github.com/watkinslabs/sai.git
cd sai
pip install -e .

# Or with Whisper support
pip install -e .[whisper]
```

### Setup

After installation, run the interactive setup:

```bash
sai-setup
```

This will:
- Install Whisper dependencies (if desired)
- Configure your Claude API key
- Check system audio dependencies

Or configure manually:
```bash
# Setup API key
sai-setup --api-key

# Install Whisper separately  
sai-setup --whisper

# Check installation status
sai-setup --check
```

## Quick Start

### 1. Get Claude API Key
1. Visit https://console.anthropic.com/
2. Create an account and generate an API key
3. Run `sai-setup --api-key` to configure

### 2. Run SAI
```bash
# Start the application
sai

# Or run with Python module
python -m sai
```

### 3. Basic Usage
1. **Select audio source** - Choose microphone or system audio from dropdown
2. **Toggle microphone** - Use microphone button or spacebar to enable/disable
3. **Speak or type** - Voice input or direct question typing
4. **View responses** - Real-time AI responses in the interface
5. **Manage history** - Export conversations or clear timeline

## Interface Guide

### Main Window Components

**Title Bar**:
- Drag handle for moving window
- Audio source selector (microphones and system audio)
- System audio info button
- Microphone toggle button
- Settings, minimize, and close buttons

**Content Areas**:
- **Transcription area** - Real-time speech-to-text display
- **Question input** - Type questions directly (Enter to send)
- **AI response area** - Current Claude response
- **Timeline** - Conversation history with timestamps
- **Control buttons** - Export and clear functions

### System Tray
- **Double-click** - Show/hide main window
- **Right-click menu**:
  - Show SAI
  - Toggle Microphone
  - Quit

### Audio Sources

**Microphone Input**:
- Any connected USB, built-in, or Bluetooth microphone
- Hot-swappable device selection
- Visual indicators for microphone status

**System Audio Capture**:
- Windows: Stereo Mix, What U Hear
- Linux: PulseAudio monitor devices, loopback
- macOS: Requires third-party tools (BlackHole, Loopback)

Use system audio to transcribe:
- Music and video content
- Audio from other applications
- Video calls and meetings
- Streaming content

## Configuration

### AI Response Modes

Configure different AI behavior modes:

- **Default** - General helpful responses (30 words max)
- **Meeting** - Focus on action items and decisions (20 words max)
- **Learning** - Explanations and educational insights (25 words max) 
- **Summary** - Concise bullet point summaries (25 words max)
- **Custom** - User-defined prompt templates

### Template Editing

Edit AI templates in Settings > AI Settings:
- Access template editor tabs for each mode
- Use `{text}` for user input and `{context}` for conversation history
- Templates are saved automatically and applied immediately

### Audio Settings

**Whisper Configuration**:
- Model: tiny (fastest, ~39MB)
- Voice Activity Detection level: configurable sensitivity
- Silence detection: 1.5 second pause threshold
- Processing: streaming with 8-second maximum chunks

**Speech Recognition Fallback**:
- Google Speech Recognition API
- Used when Whisper dependencies unavailable
- Requires internet connection

## System Requirements

### Operating System
- **Linux** (Primary support) - Fedora, Ubuntu, Arch, etc.
- **X11 or Wayland** - Compatible with both display servers
- **Audio system** - PulseAudio, PipeWire, or ALSA

### Python Requirements
- **Python 3.9+** (3.11 recommended for Whisper)
- **PyQt6** for GUI components
- **System audio libraries** (portaudio, pyaudio)

### Optional Dependencies

**For Whisper (local transcription)**:
- torch >= 2.0.0
- openai-whisper == 20231117  
- webrtcvad >= 2.0.10
- numba == 0.58.1
- scipy >= 1.13.1

**System packages (Linux)**:
```bash
# Ubuntu/Debian
sudo apt install portaudio19-dev python3-pyaudio

# Fedora
sudo dnf install portaudio-devel

# Arch
sudo pacman -S portaudio
```

## System Audio Setup

### Linux (PulseAudio)
```bash
# Enable loopback module
pactl load-module module-loopback

# Or use GUI
pavucontrol
# Recording tab > Select monitor device
```

### Windows
1. Right-click speaker icon > Sounds > Recording
2. Right-click > "Show Disabled Devices"
3. Enable "Stereo Mix" or "What U Hear"
4. Select as input device in SAI

### macOS
Requires third-party software:
- **BlackHole** (free virtual audio driver)
- **Loopback** (paid professional audio routing)

## CLI Reference

```bash
# Main commands
sai                    # Start SAI GUI
sai-setup              # Interactive setup
python -m sai          # Alternative launch method

# Setup options
sai-setup --api-key    # Configure Claude API key
sai-setup --whisper    # Install Whisper dependencies  
sai-setup --check      # Check installation status
sai-setup --all        # Complete setup

# Development
pip install -e .       # Install from source
pip install -e .[whisper]  # Install with Whisper
```

## Keyboard Shortcuts

- **Spacebar** - Toggle microphone on/off (global when focused)
- **Enter** - Send typed question (in question input field)
- **Esc** - Clear current transcription
- **Ctrl+Q** - Quit application

## Data & Privacy

### Local Processing
- Audio processed locally when using Whisper
- No audio recordings saved to disk
- Conversation history stored locally only

### External Services
- **Claude API** - Text transcriptions and context sent to Anthropic
- **Google Speech API** - Audio sent to Google when Whisper unavailable
- **No telemetry** - No usage analytics or tracking

### File Locations
```
~/.sai/
├── .env                    # API key configuration
├── settings.json          # Application preferences  
├── conversation_history.json  # Chat history
└── exports/               # Exported conversation files
```

## Troubleshooting

### Audio Issues

**No microphone detected**:
- Check system audio settings
- Verify microphone permissions
- Try different audio device
- Restart audio subsystem

**Poor transcription quality**:
- Check microphone positioning
- Reduce background noise
- Adjust microphone levels
- Try different audio device

**System audio not working**:
- Enable loopback/stereo mix
- Check monitor device availability
- Verify audio routing configuration
- See system audio setup section

### Application Issues

**Window not draggable**:
- Click and drag from title bar area
- Avoid clicking on buttons/controls
- Check window manager compatibility

**Claude API errors**:
- Verify API key configuration
- Check internet connectivity
- Monitor API usage limits
- Review error messages in console

**Performance issues**:
- Install Whisper for local processing
- Reduce timeline history size
- Check system resource usage
- Close other resource-intensive apps

### Installation Issues

**Package conflicts**:
- Use virtual environment
- Check Python version compatibility
- Update pip and setuptools
- Install system audio dependencies

**Whisper installation fails**:
- Install compatible Python version (3.9-3.11)
- Check available disk space (models ~2GB)
- Install system development packages
- Use CPU-only torch version if GPU issues

## Development

### Project Structure
```
sai/
├── __init__.py          # Package initialization
├── __main__.py          # Module entry point  
├── cli.py               # Command-line interface
├── main.py              # Application launcher
├── ui.py                # Main interface components
├── ui_updater.py        # Thread-safe UI updates
├── audio.py             # Audio processing & transcription
├── claude_client.py     # Claude API integration
├── config.py            # Settings and configuration
└── setup.py             # Post-install setup tool
```

### Building from Source
```bash
# Clone repository
git clone https://github.com/watkinslabs/sai.git
cd sai

# Install in development mode
pip install -e .[whisper]

# Run directly
python -m sai

# Build distribution
python build_package.py
```

## Contributing

This project welcomes contributions. Please:

1. Fork the repository
2. Create a feature branch
3. Make changes with tests
4. Submit a pull request

Areas for contribution:
- Additional audio backends
- Windows/macOS compatibility improvements
- New AI response modes
- Performance optimizations
- Documentation improvements

## License

MIT License. See LICENSE file for details.

## Support

- **Issues**: https://github.com/watkinslabs/sai/issues
- **Discussions**: https://github.com/watkinslabs/sai/discussions
- **Documentation**: README and inline help

---

**Note**: SAI is designed for Linux desktop environments. Windows and macOS support is experimental and may require additional configuration.