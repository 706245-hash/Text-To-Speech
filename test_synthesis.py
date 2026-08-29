#!/usr/bin/env python3
"""Quick test of piper synthesis"""
import os
import sys
from pathlib import Path

# Add venv to path
sys.path.insert(0, str(Path(__file__).parent / "venv" / "lib" / "python3.12" / "site-packages"))

from piper import PiperVoice

models_dir = Path.home() / ".local" / "share" / "piper" / "models"
models_dir.mkdir(parents=True, exist_ok=True)

voice_id = "en_US-lessac-medium"
text = "Hello! This is a test of Piper TTS synthesis."
output_path = Path(__file__).parent / "test_output.wav"

print(f"Voice ID: {voice_id}")
print(f"Models dir: {models_dir}")
print(f"Output: {output_path}")

try:
    print("Loading voice...")
    voice = PiperVoice.load(voice_id)
    
    print("Synthesizing...")
    with open(output_path, "wb") as wav_file:
        voice.synthesize(text, wav_file)
    
    if output_path.exists():
        size = output_path.stat().st_size
        print(f"SUCCESS! Generated {size} bytes")
    else:
        print("ERROR: File not created")
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
