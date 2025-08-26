# SAI - Smart AI Overlay Assistant

A powerful, fast overlay application that hovers above all windows, listens to your microphone, and provides real-time AI feedback using Claude API. Features local OpenAI Whisper for lightning-fast transcription and intelligent response caching.

🔗 **Repository**: https://github.com/watkinslabs/sai

![SAI Demo](https://img.shields.io/badge/Status-Active-brightgreen) ![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue) ![License MIT](https://img.shields.io/badge/License-MIT-green)

## ✨ Features

### 🚀 **Performance & Speed**
- **Local OpenAI Whisper** - Lightning-fast transcription (2-10x faster than cloud STT)
- **Voice Activity Detection** - Only processes when speech is detected
- **Async API calls** - Non-blocking Claude API requests with caching
- **Response caching** - Instant responses for repeated queries
- **Multi-threaded processing** - Smooth, responsive UI

### 🎯 **Core Functionality**
- **Always-on-top overlay** - Draggable, resizable window above all applications  
- **Multi-microphone support** - Easy microphone selection with live switching
- **Real-time transcription display** - See exactly what was heard
- **Claude AI integration** - Intelligent responses with multiple modes
- **Timeline history** - Searchable conversation history with timestamps

### 🛡️ **Smart Features**
- **Window exclusion** - Auto-hide during video calls (Zoom, Teams, Meet)
- **Configurable AI modes** - Default, Meeting, Learning, Summary, Custom prompts
- **Data export** - Export conversations to JSON with full metadata
- **Persistent storage** - All settings and history saved between sessions
- **Fully customizable** - Fonts, opacity, window size, response styles

## 🚀 Quick Start

### 1️⃣ **Clone the Repository**
```bash
git clone https://github.com/watkinslabs/sai.git
cd sai
```

### 2️⃣ **Complete Setup (Recommended)**
```bash
# Install everything including fast Whisper transcription
make setup
```

This will:
- ✅ Check system requirements  
- ✅ Install all dependencies with `uv`
- ✅ Install OpenAI Whisper for fast local transcription
- ✅ Download the Whisper tiny model (~39MB)
- ✅ Set up the development environment

### 3️⃣ **Configure API Key**
```bash
# Copy the environment template
cp .env.example .env

# Add your Claude API key to .env
echo "ANTHROPIC_API_KEY=your_key_here" >> .env
```

🔑 Get your API key from: https://console.anthropic.com/

### 4️⃣ **Launch SAI**
```bash
make run
```

## 📋 Alternative Installation Methods

### Basic Installation (without Whisper)
```bash
make install    # Basic dependencies only
make run        # Uses Google STT (slower)
```

### Manual Installation
```bash
# Install uv package manager
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies  
uv sync

# Add fast transcription (optional)
uv add openai-whisper torch webrtcvad

# Run
.venv/bin/python overlay_assistant.py
```

## 🛠️ Available Commands

```bash
make help           # Show all available commands
make check          # Check system requirements  
make install        # Install basic dependencies
make install-whisper # Add Whisper for fast transcription
make setup          # Complete setup with Whisper
make run            # Start the overlay
make dev            # Run in debug mode
make test           # Run functionality tests
make mic-test       # Test microphone access
make clean          # Clean cache files
```

## Usage

### Basic Operation

1. **Start the application** - The overlay window will appear in the top-right corner
2. **Select microphone** - Use the dropdown to choose your preferred microphone
3. **Start talking** - The application listens continuously and processes speech
4. **View AI responses** - Real-time responses appear in the "Current Response" area
5. **Check timeline** - See conversation history with timestamps in the timeline area

### Controls

- **Drag to move** - Click and drag the title bar to reposition the overlay
- **Hide button** - Click the "−" button to minimize the overlay
- **Export** - Save conversation history to a timestamped JSON file
- **Clear** - Reset the timeline and conversation history

### Smart Features

- **Auto-hide during video calls** - Overlay automatically hides when video conferencing apps are detected
- **Conversation context** - Claude receives context from recent conversation for better responses
- **Persistent history** - Conversation data is automatically saved and restored between sessions
- **Multi-format export** - Export data includes timestamps, transcriptions, and AI responses

## Troubleshooting

### Audio Issues

If you're having microphone issues:

1. **Check permissions** - Ensure the application has microphone access
2. **Test microphone** - Verify your microphone works in other applications
3. **Try different microphone** - Use the dropdown to select a different input device
4. **Check audio system** - Make sure PulseAudio/PipeWire is running properly

### API Issues

If Claude API isn't working:

1. **Verify API key** - Check that your `.env` file contains a valid API key
2. **Check network** - Ensure you have internet connectivity
3. **API quota** - Verify you haven't exceeded your API usage limits
4. **Check logs** - Look at terminal output for specific error messages

### Window Issues

If the overlay isn't behaving correctly:

1. **Wayland compatibility** - The app is designed for Wayland but should work on X11
2. **Window manager** - Some tiling window managers may behave differently
3. **Permissions** - Ensure the application can create overlay windows

## Architecture

- **PyQt6** - GUI framework for the overlay interface
- **SoundDevice** - Audio capture from microphones
- **SpeechRecognition** - Google Speech-to-Text for transcription
- **Anthropic API** - Claude AI for intelligent responses
- **Process monitoring** - Detects video conferencing applications

## File Structure

```
/home/nd/wl/sai/
├── overlay_assistant.py    # Main application
├── pyproject.toml         # Project configuration and dependencies
├── .env.example          # Environment template
├── .env                  # Your API configuration (not in git)
├── README.md            # This file
└── .overlay_assistant_data.json  # Persistent conversation data
```

## Data Privacy

- **Local processing** - Audio is processed locally, only transcriptions sent to APIs
- **Google Speech API** - Transcription data sent to Google's servers
- **Claude API** - Text and context sent to Anthropic's servers
- **Local storage** - Conversation history stored locally in your home directory
- **No permanent recordings** - Audio is not saved, only processed in real-time

## Contributing

This is a personal project, but feel free to fork and modify for your own use.

## License

MIT License - See project configuration for details.