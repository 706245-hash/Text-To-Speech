#!/usr/bin/env python3
"""
Terminal Text-to-Speech App
----------------------------
Reads a text file, lets you browse and preview available voices,
then saves the narration to an audio file (WAV or MP3).

Uses Piper TTS for high-quality neural voices.

Usage:
    python3 terminal_tts.py input.txt
    python3 terminal_tts.py input.txt -o narration.mp3
    python3 terminal_tts.py input.txt --voice "en_US-lessac-medium"
    python3 terminal_tts.py --list-voices
    python3 terminal_tts.py --list-voices --lang en

Requires: piper-tts (pip install piper-tts), pygame (pip install pygame),
and ffmpeg on PATH if exporting to a format other than WAV.
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

from piper import PiperVoice
from piper.download_voices import download_voice


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

# Cache for loaded voices
voice_cache = {}


# --------------------------------------------------------------------------
# Voice helpers
# --------------------------------------------------------------------------

def get_voices():
    """Return the list of available piper voices."""
    return PIPER_VOICES


def filter_voices(voices, query):
    """Filter voices by a case-insensitive substring match on id/name."""
    if not query:
        return voices
    q = query.lower()
    out = []
    for vid, name in voices:
        haystack = f"{vid} {name}".lower()
        if q in haystack:
            out.append((vid, name))
    return out


def print_voice_table(voices, start_index=0):
    print(f"{'#':<5}{'Name':<40}{'Voice ID':<30}")
    print("-" * 80)
    for i, (vid, name) in enumerate(voices, start=start_index):
        print(f"{i:<5}{name[:39]:<40}{vid:<30}")


def get_piper_model_path(voice_id):
    """Get the Piper model path, downloading if necessary."""
    data_dir = Path.home() / ".local" / "share" / "piper"
    model_file = data_dir / "models" / f"{voice_id}.onnx"
    config_file = data_dir / "models" / f"{voice_id}.json"
    
    if model_file.exists() and config_file.exists():
        return str(model_file)
    
    # Need to download the model
    print(f"  Downloading voice model '{voice_id}'...")
    print(f"  (This may take a minute on first use)")
    
    # Use piper's download system
    try:
        subprocess.run(
            ["piper", "--model", voice_id, "--input-file", "/dev/null"],
            capture_output=True,
            timeout=300,
        )
    except Exception as e:
        print(f"  Note: Could not verify download via piper CLI: {e}")
    
    # Models are stored in a standard piper location
    if model_file.exists():
        return str(model_file)
    else:
        raise RuntimeError(
            f"Could not find or download voice model '{voice_id}'. "
            f"Expected at: {model_file}\n"
            f"Make sure you have internet connection and sufficient disk space."
        )


def synthesize_to_wav(text, voice_id, volume, wav_path):
    """Synthesize text to WAV using piper CLI."""
    models_dir = Path.home() / ".local" / "share" / "piper" / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    
    model_file = models_dir / f"{voice_id}.onnx"
    config_file = models_dir / f"{voice_id}.onnx.json"
    
    # Download model if not present
    if not (model_file.exists() and config_file.exists()):
        print(f"  Downloading voice model '{voice_id}'...", flush=True)
        print(f"  (This may take a few minutes on first use)", flush=True)
        try:
            download_voice(voice_id, models_dir)
            print(f"  Download complete!", flush=True)
        except Exception as e:
            raise RuntimeError(
                f"Failed to download voice model '{voice_id}': {e}\n"
                f"Make sure you have internet connection."
            )
    
    # Find piper - try in venv first, then in PATH
    piper_cmd = "piper"
    venv_piper = Path.home().parent / "Documents" / "CODE" / "tts" / "venv" / "bin" / "piper"
    if venv_piper.exists():
        piper_cmd = str(venv_piper)
    
    # Use piper CLI for synthesis with full path to model
    cmd = [piper_cmd, "--model", str(model_file), "--output-file", wav_path]
    
    if volume != 1.0:
        cmd.extend(["--volume", str(volume)])
    
    try:
        print(f"  Synthesizing audio...", flush=True)
        result = subprocess.run(
            cmd,
            input=text,
            capture_output=True,
            text=True,
            timeout=600
        )
        
        if result.returncode != 0:
            stderr_msg = result.stderr if result.stderr else result.stdout
            raise RuntimeError(f"Piper synthesis failed:\n{stderr_msg}")
        
        print(f"  Done!", flush=True)
        
    except subprocess.TimeoutExpired:
        raise RuntimeError("Piper synthesis timed out (exceeded 10 minutes)")
    except FileNotFoundError:
        raise RuntimeError("Piper command not found. Install with: pip install piper-tts")
    except Exception as e:
        if "RuntimeError" in str(type(e)):
            raise
        raise RuntimeError(f"Failed to synthesize audio: {e}")


def apply_volume_to_wav_file(wav_path, volume):
    """Apply volume scaling to a WAV file."""
    try:
        with wave.open(wav_path, "r+b") as wav_file:
            frames = wav_file.readframes(wav_file.getnframes())
            audio_data = bytearray(frames)
            
            # Process as 16-bit signed integers
            for i in range(0, len(audio_data) - 1, 2):
                sample = int.from_bytes(audio_data[i:i+2], byteorder='little', signed=True)
                sample = int(sample * volume)
                sample = max(-32768, min(32767, sample))  # Clamp
                audio_data[i:i+2] = sample.to_bytes(2, byteorder='little', signed=True)
            
            wav_file.rewind()
            wav_file.writeframes(bytes(audio_data))
    except Exception as e:
        print(f"  Warning: Could not apply volume: {e}", flush=True)


def preview_voice(voice_id, sample_text, volume):
    """Speak a short sample through the system's audio output."""
    try:
        fd, tmp_wav = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        
        # Synthesize the sample
        synthesize_to_wav(sample_text, voice_id, volume, tmp_wav)
        
        # Try to play the audio
        try:
            import os
            os.system(f"aplay {tmp_wav} 2>/dev/null || ffplay -nodisp -autoexit {tmp_wav} 2>/dev/null || echo 'Audio saved to {tmp_wav}'")
        except Exception as e:
            print(f"  (Could not play audio out loud here: {e})")
            print(f"  Sample saved to: {tmp_wav}")
    except Exception as e:
        print(f"  Error previewing voice: {e}")


# --------------------------------------------------------------------------
# Interactive voice picker
# --------------------------------------------------------------------------

def choose_voice_interactively(volume):
    all_voices = get_voices()
    current = all_voices
    sample_text = "Hello! This is a preview of the currently selected voice."

    print(f"\n{len(all_voices)} voices available.\n")

    while True:
        print_voice_table(current)
        print(
            "\nCommands: "
            "[number]=select voice, "
            "p[number]=preview voice, "
            "f <text>=filter (e.g. 'f en' for English), "
            "f=clear filter, "
            "q=quit"
        )
        choice = input("> ").strip()

        if choice.lower() == "q":
            print("Cancelled.")
            sys.exit(0)

        if choice.lower().startswith("f"):
            query = choice[1:].strip()
            current = filter_voices(all_voices, query)
            if not current:
                print("No voices matched that filter. Showing all voices again.\n")
                current = all_voices
            continue

        if choice.lower().startswith("p") and choice[1:].strip().isdigit():
            idx = int(choice[1:].strip())
            if 0 <= idx < len(current):
                vid, name = current[idx]
                print(f"Previewing: {name} ...")
                preview_voice(vid, sample_text, volume)
            else:
                print("Invalid index.")
            continue

        if choice.isdigit():
            idx = int(choice)
            if 0 <= idx < len(current):
                vid, name = current[idx]
                confirm = input(
                    f"Use voice '{name}' ({vid})? [Y/n] "
                ).strip().lower()
                if confirm in ("", "y", "yes"):
                    return vid
                continue
            else:
                print("Invalid index.")
            continue

        print("Didn't understand that. Try again.")


# --------------------------------------------------------------------------
# Audio export
# --------------------------------------------------------------------------

def read_text_file(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read().strip()


def convert_wav_to(wav_path, output_path, fmt):
    """Convert WAV to another format using ffmpeg."""
    if not shutil.which("ffmpeg"):
        raise RuntimeError(
            f"ffmpeg is required to export .{fmt} files but was not found on PATH. "
            "Install ffmpeg, or export as .wav instead."
        )
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", wav_path, output_path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg conversion failed:\n{result.stderr}")


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Convert a text file to speech, with interactive voice selection."
    )
    parser.add_argument("input_file", nargs="?", help="Path to the text file to narrate")
    parser.add_argument("-o", "--output", help="Output audio file path (default: <input>.wav)")
    parser.add_argument(
        "--format",
        choices=["wav", "mp3"],
        default=None,
        help="Output audio format (inferred from --output extension if omitted; default wav)",
    )
    parser.add_argument("--voice", help="Voice ID to use directly (skips interactive picker)")
    parser.add_argument("--volume", type=float, default=1.0, help="Volume, 0.0 to 1.0 (default 1.0)")
    parser.add_argument("--list-voices", action="store_true", help="List available voices and exit")
    parser.add_argument("--lang", help="Filter --list-voices by language/name substring")

    args = parser.parse_args()

    if args.list_voices:
        voices = filter_voices(get_voices(), args.lang)
        if not voices:
            print("No voices matched.")
        else:
            print_voice_table(voices)
        return

    if not args.input_file:
        parser.error("input_file is required (or use --list-voices)")

    if not os.path.isfile(args.input_file):
        print(f"Error: file not found: {args.input_file}")
        sys.exit(1)

    text = read_text_file(args.input_file)
    if not text:
        print("Error: input file is empty.")
        sys.exit(1)

    print(f"Loaded '{args.input_file}' ({len(text)} characters).")

    # --- Voice selection ---
    if args.voice:
        voice_id = args.voice
        print(f"Using voice: {voice_id}")
    else:
        voice_id = choose_voice_interactively(args.volume)

    # --- Determine output path/format ---
    base, _ = os.path.splitext(args.input_file)
    fmt = args.format
    output_path = args.output

    if output_path and not fmt:
        ext = os.path.splitext(output_path)[1].lstrip(".").lower()
        fmt = ext if ext in ("wav", "mp3") else "wav"
    if not fmt:
        fmt = "wav"
    if not output_path:
        output_path = f"{base}.{fmt}"

    # --- Synthesize ---
    print(f"\nGenerating audio with volume={args.volume} ...")

    if fmt == "wav":
        synthesize_to_wav(text, voice_id, args.volume, output_path)
    else:
        fd, tmp_wav = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        try:
            synthesize_to_wav(text, voice_id, args.volume, tmp_wav)
            convert_wav_to(tmp_wav, output_path, fmt)
        finally:
            if os.path.exists(tmp_wav):
                os.remove(tmp_wav)

    size_kb = os.path.getsize(output_path) / 1024
    print(f"\nDone! Saved to: {output_path} ({size_kb:.1f} KB)")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCancelled.")
        sys.exit(1)
