# SAI Migration to Modular Structure

The SAI project has been restructured from a single monolithic file (`overlay_assistant.py`) into a proper Python module with separate components.

## What Changed

### Old Structure
- Single file: `overlay_assistant.py` (1500+ lines)
- Direct execution: `python overlay_assistant.py`

### New Structure
- Modular package: `sai/` directory with multiple files:
  - `sai/__init__.py` - Module initialization
  - `sai/__main__.py` - Module entry point
  - `sai/main.py` - Application main function
  - `sai/cli.py` - Command line interface
  - `sai/ui.py` - User interface components
  - `sai/audio.py` - Audio processing and speech recognition
  - `sai/claude_client.py` - Claude API integration
  - `sai/config.py` - Configuration and settings

## How to Use

### Command Line Interface
```bash
# New CLI commands
sai check          # Check requirements
sai setup          # Setup environment
sai run            # Start the overlay
sai run --debug    # Debug mode

# Or as Python module
python -m sai check
python -m sai setup
python -m sai run
```

### Makefile Commands (Updated)
```bash
make check         # Uses new CLI check
make setup         # Uses new CLI setup
make run           # Uses new modular structure
make dev           # Debug mode
```

### Importing Components
```python
# Import specific components
from sai import OverlayWidget, ClaudeClient, FastAudioListener
from sai.config import Config

# Or import the main function
from sai import main
main()
```

## Benefits

1. **Better Organization**: Code is split into logical modules
2. **Easier Maintenance**: Each component has a single responsibility
3. **CLI Interface**: Professional command-line interface
4. **Improved Testing**: Components can be tested independently
5. **Better Imports**: Use only what you need
6. **Cleaner Architecture**: Separation of concerns

## Backward Compatibility

The old `overlay_assistant.py` file is preserved but the new structure is recommended for all new usage.

All functionality remains the same - just better organized!