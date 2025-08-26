#!/bin/bash
# SAI - Smart AI Overlay Assistant launcher

cd "$(dirname "$0")"

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "Virtual environment not found. Run 'uv sync' first."
    exit 1
fi

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "Environment file not found. Please create .env with your ANTHROPIC_API_KEY"
    echo "You can copy .env.example to .env and add your API key."
    exit 1
fi

# Run the application
.venv/bin/python overlay_assistant.py