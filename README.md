# Text-to-Speech App

Professional neural text-to-speech with natural-sounding voices. Two interfaces:

- **`terminal_tts.py`** — CLI: convert text files to audio with interactive voice selection and filtering
- **`gui_tts.py`** — Desktop app: type or load text, customize voice/volume, preview, and export

Built on **Piper TTS** — free, fast, offline neural synthesis with 16 voices across 8 languages.

## Features

**High-quality neural voices** — Natural pronunciation, proper intonation  
**Multilingual** — 8 languages (English, French, German, Italian, Spanish, Dutch, Swedish, plus AU/UK accents)  
**Fast and offline** — No API calls needed, processes text in seconds  
**Volume control** — Adjust output level  
**Multiple formats** — Export as WAV or MP3  
**Two interfaces** — CLI for scripting, GUI for interactive use  

## Quick Start

### 1. Install Dependencies

**Linux/Ubuntu:**
```bash
sudo apt install python3-tk ffmpeg
pip install -r requirements.txt
```

**macOS:**
```bash
brew install ffmpeg
pip install -r requirements.txt
```

**Windows:**
- Download [ffmpeg](https://ffmpeg.org/download.html) or install via Scoop: `scoop install ffmpeg`
- Install Python packages: `pip install -r requirements.txt`

### 2. Terminal CLI

```bash
# Interactive mode
python3 terminal_tts.py my_story.txt

# Specify voice and options
python3 terminal_tts.py input.txt -o narration.wav --voice en_US-lessac-medium --volume 0.9

# List available voices
python3 terminal_tts.py --list-voices
```

## Available Voices

| Language | Code | Voice |
|----------|------|-------|
| **English (US)** | en_US-lessac-medium | Lessac (male, default) |
| | en_US-lessac-high | Lessac (male, high quality) |
| | en_US-libritts-high | Libritts (female, high) |
| | en_US-glow-tts-medium | Glow TTS (female) |
| **English (UK)** | en_GB-alan-medium | Alan (male) |
| | en_GB-alan-high | Alan (male, high) |
| | en_GB-libby-medium | Libby (female) |
| | en_GB-southern_english_female-low | Southern English (female) |
| **English (AU)** | en_AU-kimberly-medium | Kimberly (female) |
| **French** | fr_FR-siwis-medium | Siwis (female) |
| **German** | de_DE-thorsten-medium | Thorsten (male) |
| **Italian** | it_IT-riccardo_fasol-medium | Riccardo (male) |
| **Spanish** | es_ES-carla-medium | Carla (female) |
| **Spanish (MX)** | es_MX-jasmijn-medium | Jasmijn (female) |
| **Dutch** | nl_NL-mls-medium | MLS (medium) |
| **Swedish** | sv_SE-nils_f_knut-medium | Nils Knut (male) |

**Note:** Voice models are auto-downloaded on first use (~20-50 MB each) and cached in `~/.local/share/piper/models/`.

## Architecture

```
tts/
├── terminal_tts.py     # CLI interface
├── gui_tts.py          # Desktop GUI
├── tts_config.py       # Shared voice definitions
├── tts_engine.py       # Shared TTS synthesis core
└── requirements.txt    # Dependencies
```

Both `terminal_tts.py` and `gui_tts.py` share the same `PiperSynthesizer` engine (`tts_engine.py`) and voice list (`tts_config.py`), so there's no duplicated synthesis logic between the CLI and GUI.

## Requirements

- Python 3.8+
- piper-tts (neural TTS engine)
- pygame (audio playback)
- tkinter (GUI only)
- ffmpeg (MP3 export)

## Troubleshooting

**"Piper command not found"**
- Ensure `piper-tts` is installed: `pip install piper-tts`
- If using venv, activate it: `source venv/bin/activate`

**"Unable to find voice"**
- Check internet connection (models auto-download on first use)
- Models stored in: `~/.local/share/piper/models/`
- Try deleting the model and re-running to re-download

**Audio playback fails**
- Install pygame: `pip install pygame`
- Check volume isn't muted
- On headless servers, use `-o filename.wav` to save instead of playing

**MP3 export not working**
- Install ffmpeg: `sudo apt install ffmpeg` (Linux) or `brew install ffmpeg` (macOS)

## License

MIT
