"""
TTS Configuration and Voice Definitions
========================================

Centralized configuration for Piper TTS voices and settings.
"""

import json
from pathlib import Path

# Available piper voices (language_code-voice_name-quality)
# Quality: low, medium, high (higher = larger download but better quality)
PIPER_VOICES = [
    ("en_US-lessac-medium", "Lessac (US, male, medium)"),
    ("en_US-lessac-high", "Lessac (US, male, high)"),
    ("en_US-libritts-high", "Libritts (US, female, high)"),
    ("en_US-glow-tts-medium", "Glow TTS (US, female, medium)"),
    ("en_GB-alan-medium", "Alan (UK, male, medium)"),
    ("en_GB-alan-high", "Alan (UK, male, high)"),
    ("en_GB-libby-medium", "Libby (UK, female, medium)"),
    ("en_GB-southern_english_female-low", "Southern English Female (UK, low)"),
    ("en_AU-kimberly-medium", "Kimberly (Australian, female, medium)"),
    ("fr_FR-siwis-medium", "Siwis (French, female, medium)"),
    ("de_DE-thorsten-medium", "Thorsten (German, male, medium)"),
    ("it_IT-riccardo_fasol-medium", "Riccardo (Italian, male, medium)"),
    ("es_ES-carla-medium", "Carla (Spanish, female, medium)"),
    ("es_MX-jasmijn-medium", "Jasmijn (Mexican Spanish, female, medium)"),
    ("nl_NL-mls-medium", "MLS (Dutch, medium)"),
    ("sv_SE-nils_f_knut-medium", "Nils Knut (Swedish, male, medium)"),
]

# Default voice
DEFAULT_VOICE = "en_US-lessac-medium"

# Model storage location
MODELS_DIR = Path.home() / ".local" / "share" / "piper" / "models"

# User-persisted default settings (voice/volume/speed/format)
CONFIG_DIR = Path.home() / ".config" / "tts"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULT_SETTINGS = {
    "voice": DEFAULT_VOICE,
    "volume": 1.0,
    "speed": 1.0,
    "format": "wav",
}


def load_config():
    """Load user config, filling in defaults for any missing/invalid keys."""
    settings = dict(DEFAULT_SETTINGS)
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                settings.update({k: v for k, v in data.items() if k in DEFAULT_SETTINGS})
        except (json.JSONDecodeError, OSError):
            pass  # Fall back to defaults on any config read error
    return settings


def save_config(settings):
    """Persist the given settings (only recognized keys) to the config file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    to_save = {k: settings[k] for k in DEFAULT_SETTINGS if k in settings}
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(to_save, f, indent=2)
        f.write("\n")


def get_voice_by_id(voice_id):
    """Get voice name by ID, or None if not found."""
    for vid, name in PIPER_VOICES:
        if vid == voice_id:
            return name
    return None


def filter_voices(query):
    """Filter voices by case-insensitive substring match on id/name."""
    if not query:
        return PIPER_VOICES
    
    q = query.lower()
    filtered = []
    for vid, name in PIPER_VOICES:
        haystack = f"{vid} {name}".lower()
        if q in haystack:
            filtered.append((vid, name))
    return filtered
