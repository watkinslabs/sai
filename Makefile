# SAI - Smart AI Overlay Assistant
# Makefile for project management

.PHONY: help install install-whisper dev run test clean lint format check setup

# Default target
help:
	@echo "SAI - Smart AI Overlay Assistant"
	@echo "================================"
	@echo ""
	@echo "Available commands:"
	@echo "  make install        - Install basic dependencies"
	@echo "  make install-whisper - Install with OpenAI Whisper for fast transcription"
	@echo "  make setup          - Complete setup with Whisper + dependencies"
	@echo "  make run            - Run the overlay assistant"
	@echo "  make dev            - Run in development mode with debug output"
	@echo "  make test           - Run basic functionality tests"
	@echo "  make clean          - Clean cache and temporary files"
	@echo "  make lint           - Run code linting"
	@echo "  make format         - Format code"
	@echo "  make check          - Check system requirements"
	@echo ""
	@echo "Quick start:"
	@echo "  make setup     # Install everything including Whisper"
	@echo "  make run       # Start the application"

# Check system requirements
check:
	@echo "Checking system requirements..."
	@python3 --version || (echo "Python 3.9+ required" && exit 1)
	@which uv > /dev/null || (echo "uv package manager required: https://docs.astral.sh/uv/" && exit 1)
	@echo "✓ Python and uv found"
	@echo ""
	@echo "Running SAI requirements check..."
	.venv/bin/python -m sai check

# Install basic dependencies
install:
	@echo "Installing basic dependencies..."
	uv sync
	@echo "✓ Basic installation complete"
	@echo ""
	@echo "To add fast local transcription, run: make install-whisper"

# Install with OpenAI Whisper for fast transcription  
install-whisper:
	@echo "Installing OpenAI Whisper and performance dependencies..."
	@echo "Note: Installing compatible versions for your Python environment..."
	uv add --resolution=lowest-direct "openai-whisper>=20231117" || echo "Whisper install failed, will use fallback mode"
	uv add "webrtcvad>=2.0.10" || echo "WebRTC VAD install failed, continuing..."
	@echo "✓ Performance dependencies installed"
	@echo ""
	@echo "Testing Whisper installation..."
	@if .venv/bin/python -c "import whisper" 2>/dev/null; then \
		echo "Downloading Whisper tiny model..."; \
		.venv/bin/python -c "import whisper; whisper.load_model('tiny')" && echo "✓ Whisper ready"; \
	else \
		echo "⚠ Whisper not available, will use Google STT fallback"; \
	fi

# Complete setup with everything
setup: check install install-whisper
	@echo ""
	@echo "Setting up environment..."
	.venv/bin/python -m sai setup
	@echo ""
	@echo "🎉 Setup complete!"
	@echo ""
	@echo "Next steps:"
	@echo "1. Edit .env and add your ANTHROPIC_API_KEY"
	@echo "2. Run: make run"

# Run the application
run:
	@echo "Starting SAI Overlay Assistant..."
	@if [ ! -f .env ]; then \
		echo "⚠ .env file not found!"; \
		echo "Copy .env.example to .env and add your ANTHROPIC_API_KEY"; \
		exit 1; \
	fi
	.venv/bin/python -m sai run

# Development mode with debug output
dev:
	@echo "Starting SAI in development mode..."
	@if [ ! -f .env ]; then \
		echo "⚠ .env file not found!"; \
		echo "Copy .env.example to .env and add your ANTHROPIC_API_KEY"; \
		exit 1; \
	fi
	DEBUG=1 .venv/bin/python -m sai run --debug

# Run basic tests
test:
	@echo "Running basic functionality tests..."
	.venv/bin/python test_basic.py

# Clean up
clean:
	@echo "Cleaning cache and temporary files..."
	rm -rf __pycache__/
	rm -rf .pytest_cache/
	rm -rf *.egg-info/
	rm -f .overlay_assistant_data.json
	rm -f .overlay_assistant_settings.json
	find . -name "*.pyc" -delete
	find . -name "*.pyo" -delete
	@echo "✓ Cleanup complete"

# Code linting (if available)
lint:
	@if .venv/bin/python -c "import ruff" 2>/dev/null; then \
		echo "Running ruff linter..."; \
		.venv/bin/ruff check .; \
	else \
		echo "Ruff not installed, skipping lint"; \
	fi

# Code formatting (if available)
format:
	@if .venv/bin/python -c "import black" 2>/dev/null; then \
		echo "Running black formatter..."; \
		.venv/bin/black .; \
	else \
		echo "Black not installed, skipping format"; \
	fi

# Quick microphone test
mic-test:
	@echo "Testing microphone access..."
	@echo "Available input devices:"
	.venv/bin/python -c "import sounddevice as sd; devices = sd.query_devices(); [print(f'{i}: {d[\"name\"]} (rate: {d[\"default_samplerate\"]}Hz, channels: {d[\"max_input_channels\"]})') for i, d in enumerate(devices) if d['max_input_channels'] > 0]"
	@echo ""
	@echo "Testing device access..."
	.venv/bin/python -c "import sounddevice as sd; import numpy as np; print('Testing first working device...'); devices = sd.query_devices(); input_devs = [(i, d) for i, d in enumerate(devices) if d['max_input_channels'] > 0]; device_id, device = input_devs[0] if input_devs else (None, None); print(f'Testing device {device_id}: {device[\"name\"]}') if device else print('No input devices'); sd.rec(int(0.1 * device['default_samplerate']), samplerate=int(device['default_samplerate']), channels=1, device=device_id) if device else None; sd.wait() if device else None; print('✓ Microphone access works!') if device else print('✗ No microphones available')"

# Install development dependencies
dev-deps:
	uv add --dev ruff black pytest
	@echo "✓ Development dependencies installed"