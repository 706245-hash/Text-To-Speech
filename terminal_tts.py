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
from pathlib import Path

from tts_config import PIPER_VOICES, filter_voices as config_filter_voices
from tts_engine import PiperSynthesizer


# Initialize synthesizer
synthesizer = PiperSynthesizer()


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


def preview_voice(voice_id, sample_text, volume, speed=1.0):
    """Speak a short sample through the system's audio output."""
    try:
        fd, tmp_wav = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        
        # Synthesize the sample using the shared synthesizer
        synthesizer.synthesize(sample_text, voice_id, volume, tmp_wav, speed=speed)
        
        # Try to play the audio
        try:
            os.system(f"aplay {tmp_wav} 2>/dev/null || ffplay -nodisp -autoexit {tmp_wav} 2>/dev/null || echo 'Audio saved to {tmp_wav}'")
        except Exception as e:
            print(f"  (Could not play audio out loud here: {e})")
            print(f"  Sample saved to: {tmp_wav}")
    except Exception as e:
        print(f"  Error previewing voice: {e}")


# --------------------------------------------------------------------------
# Interactive voice picker
# --------------------------------------------------------------------------

def choose_voice_interactively(volume, speed=1.0):
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
                preview_voice(vid, sample_text, volume, speed)
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
    parser.add_argument("--speed", type=float, default=1.0, help="Speech speed multiplier, e.g. 0.5=half speed, 2.0=2x faster (default 1.0)")
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
        voice_id = choose_voice_interactively(args.volume, args.speed)

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
    print(f"\nGenerating audio with volume={args.volume}, speed={args.speed} ...")

    if fmt == "wav":
        synthesizer.synthesize(text, voice_id, args.volume, output_path, speed=args.speed)
    else:
        fd, tmp_wav = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        try:
            synthesizer.synthesize(text, voice_id, args.volume, tmp_wav, speed=args.speed)
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
