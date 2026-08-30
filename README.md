# Piper TTS Studio

A Python-based text-to-speech app built on Piper TTS with both a terminal interface and a desktop GUI. It focuses on a clean shared engine, local voice caching, batch generation, and quick export workflows.

## Interfaces

- `terminal_tts.py` — command-line synthesis, batch processing, cache management, and quick voice selection
- `gui_tts.py` — Tkinter desktop app for typing/loading text, voice selection, preview, export, presets, and recent files

## Features

- High-quality Piper neural voices with offline synthesis
- 16 bundled voice models across multiple languages and accents
- Adjustable speed and volume
- WAV and MP3 export
- Batch processing for folders or multiple input files
- Local model support via a direct `.onnx` path
- Persistent user defaults for voice, volume, speed, and format
- Recent-file tracking and saved presets in the GUI
- Cached downloaded models with list/remove support
- Shared synthesis engine so CLI and GUI stay consistent

## Quick start

### 1. Install dependencies

Linux/macOS:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

If you need GUI support and MP3 export:

```bash
sudo apt install python3-tk ffmpeg
```

### 2. Run the GUI

```bash
python3 gui_tts.py
```

### 3. Run the CLI

```bash
# Basic conversion
python3 terminal_tts.py input.txt -o output.wav

# Use a specific bundled voice
python3 terminal_tts.py input.txt -o output.wav --voice en_US-lessac-medium

# Use a local .onnx model
python3 terminal_tts.py input.txt -o output.wav --voice /path/to/custom_voice.onnx

# Batch mode from a folder
python3 terminal_tts.py texts/ -o output_dir --voice en_US-lessac-medium

# List available voices
python3 terminal_tts.py --list-voices

# Show saved defaults
python3 terminal_tts.py --show-config
```

## Voice Model Behavior

The app uses Piper models stored in:

```bash
~/.local/share/piper/models/
```

Models are downloaded automatically on first use when a bundled voice is selected. You can also point `--voice` directly at a local `.onnx` file, which skips the download step for custom or manually installed models.

## CLI capabilities

- `--voice` accepts either a known voice ID or a local `.onnx` file path
- `--speed` supports multipliers such as `0.5`, `1.0`, `1.5`, `2.0`
- `--volume` accepts values from `0.0` to `1.0`
- `--format wav` or `--format mp3`
- `--list-downloaded` shows cached model sizes
- `--clear-cache` removes one or all downloaded models
- `--save-config` stores default TTS settings for later use

## GUI capabilities

- Text input with scrollable editing area
- Voice filter and selection
- Speed and volume controls
- Preview text or selected voice
- Pause/resume playback while sound is active
- Stop playback at any time
- Export to WAV or MP3
- Save and load preset combinations
- Track and reopen recent text files

## Architecture

```text
tts/
├── terminal_tts.py     # CLI entry point
├── gui_tts.py          # Desktop application
├── tts_engine.py       # Shared Piper synthesis engine
├── tts_config.py       # Shared voice catalog and config helpers
├── requirements.txt    # Python dependencies
├── input.txt           # Example input file
└── texts/              # Example output/test text area
```

## Requirements

- Python 3.11+
- Piper TTS
- pygame
- tkinter
- ffmpeg for MP3 export

## Troubleshooting

### Piper command not found

```bash
source venv/bin/activate
pip install -r requirements.txt
```

If needed, make sure the Piper CLI is available on your PATH.

### Voice model download issues

- Check your internet connection
- Confirm the environment has write access to `~/.local/share/piper/models/`
- For custom local voices, pass the `.onnx` path directly with `--voice`

### Audio playback is missing

- Install `pygame`
- Ensure your system audio is available
- If playback is not possible in the current environment, use export to save audio to disk

### MP3 export fails

Install ffmpeg:

```bash
sudo apt install ffmpeg
```

or on macOS:

```bash
brew install ffmpeg
```

## License

MIT
