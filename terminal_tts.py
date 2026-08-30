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
    python3 terminal_tts.py chapter1.txt chapter2.txt chapter3.txt -o audio/  (batch mode)
    python3 terminal_tts.py my_book_folder/ --voice "en_US-lessac-medium" -o audio/  (batch mode)
    python3 terminal_tts.py --list-voices
    python3 terminal_tts.py --list-voices --lang en
    python3 terminal_tts.py --list-downloaded
    python3 terminal_tts.py --clear-cache en_US-lessac-medium
    python3 terminal_tts.py --clear-cache
    python3 terminal_tts.py input.txt --save-config  (remember voice/volume/speed/format as defaults)
    python3 terminal_tts.py --show-config

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

from tts_config import (
    PIPER_VOICES,
    filter_voices as config_filter_voices,
    load_config,
    save_config,
    CONFIG_FILE,
)
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


def format_size(size_bytes):
    """Format a byte count as a human-readable string."""
    size = float(size_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}"
        size /= 1024


def print_downloaded_voices():
    """Print the list of locally downloaded voice models with sizes."""
    downloaded = synthesizer.list_downloaded_voices()
    if not downloaded:
        print("No voice models downloaded yet.")
        return
    total = 0
    print(f"{'Voice ID':<35}{'Size':>10}")
    print("-" * 45)
    for voice_id, size in downloaded:
        print(f"{voice_id:<35}{format_size(size):>10}")
        total += size
    print("-" * 45)
    print(f"{'Total':<35}{format_size(total):>10}")
    print(f"\nStored in: {synthesizer.models_dir}")


def clear_cache(voice_id):
    """Remove a single downloaded voice model, or all of them if voice_id is None."""
    if voice_id:
        if synthesizer.remove_model(voice_id):
            print(f"Removed voice model: {voice_id}")
        else:
            print(f"No downloaded model found for: {voice_id}")
        return

    downloaded = synthesizer.list_downloaded_voices()
    if not downloaded:
        print("No voice models downloaded yet.")
        return

    print(f"This will remove {len(downloaded)} downloaded voice model(s):")
    for vid, size in downloaded:
        print(f"  - {vid} ({format_size(size)})")
    confirm = input("Continue? [y/N] ").strip().lower()
    if confirm not in ("y", "yes"):
        print("Cancelled.")
        return
    for vid, _ in downloaded:
        synthesizer.remove_model(vid)
    print(f"Removed {len(downloaded)} voice model(s).")


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


def resolve_input_files(input_paths):
    """Expand a mix of file paths and directories into a sorted list of .txt files."""
    files = []
    for path in input_paths:
        if os.path.isdir(path):
            files.extend(
                str(p) for p in sorted(Path(path).glob("*.txt"))
            )
        else:
            files.append(path)
    return files


def compute_output_path(input_file, output_arg, fmt, batch_mode):
    """Determine the output audio path for a given input file."""
    base = os.path.splitext(os.path.basename(input_file))[0]
    if batch_mode:
        out_dir = output_arg or os.path.dirname(input_file) or "."
        os.makedirs(out_dir, exist_ok=True)
        return os.path.join(out_dir, f"{base}.{fmt}")
    if output_arg:
        return output_arg
    return f"{os.path.splitext(input_file)[0]}.{fmt}"


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
        description="Convert text file(s) to speech, with interactive voice selection."
    )
    parser.add_argument(
        "input_paths",
        nargs="*",
        help="Path(s) to text file(s) and/or directories to narrate (batch mode if more than one file resolves)",
    )
    parser.add_argument(
        "-o", "--output",
        help="Output file path (single input) or output directory (batch mode)",
    )
    parser.add_argument(
        "--format",
        choices=["wav", "mp3"],
        default=None,
        help="Output audio format (inferred from --output extension if omitted; default wav)",
    )
    parser.add_argument("--voice", help="Voice ID to use directly (skips interactive picker)")
    parser.add_argument(
        "--pick-voice", action="store_true",
        help="Force the interactive voice picker, even if a default voice is saved in config",
    )
    parser.add_argument("--volume", type=float, default=None, help="Volume, 0.0 to 1.0 (default from config, else 1.0)")
    parser.add_argument("--speed", type=float, default=None, help="Speech speed multiplier, e.g. 0.5=half speed, 2.0=2x faster (default from config, else 1.0)")
    parser.add_argument("--list-voices", action="store_true", help="List available voices and exit")
    parser.add_argument("--lang", help="Filter --list-voices by language/name substring")
    parser.add_argument(
        "--list-downloaded", action="store_true",
        help="List voice models already downloaded to disk, with sizes, and exit",
    )
    parser.add_argument(
        "--clear-cache", nargs="?", const="__ALL__", metavar="VOICE_ID",
        help="Remove a downloaded voice model (or all of them if no VOICE_ID given) and exit",
    )
    parser.add_argument(
        "--save-config", action="store_true",
        help="Save the voice/volume/speed/format used in this run as the new defaults",
    )
    parser.add_argument(
        "--show-config", action="store_true",
        help="Print the current saved default settings and exit",
    )

    args = parser.parse_args()

    config = load_config()

    if args.show_config:
        print(f"Config file: {CONFIG_FILE}")
        if CONFIG_FILE.exists():
            for key, value in config.items():
                print(f"  {key}: {value}")
        else:
            print("  (no config file saved yet; showing built-in defaults)")
            for key, value in config.items():
                print(f"  {key}: {value}")
        return

    if args.list_downloaded:
        print_downloaded_voices()
        return

    if args.clear_cache is not None:
        clear_cache(None if args.clear_cache == "__ALL__" else args.clear_cache)
        return

    if args.list_voices:
        voices = filter_voices(get_voices(), args.lang)
        if not voices:
            print("No voices matched.")
        else:
            print_voice_table(voices)
        return

    if not args.input_paths:
        parser.error("input_paths is required (or use --list-voices)")

    input_files = resolve_input_files(args.input_paths)
    if not input_files:
        print("Error: no .txt files found in the given path(s).")
        sys.exit(1)

    missing = [f for f in input_files if not os.path.isfile(f)]
    if missing:
        print(f"Error: file(s) not found: {', '.join(missing)}")
        sys.exit(1)

    batch_mode = len(input_files) > 1
    if batch_mode:
        print(f"Batch mode: {len(input_files)} files to process.")

    # --- Voice selection (once, applied to every file) ---
    if args.voice:
        voice_id = args.voice
        print(f"Using voice: {voice_id}")
    elif not args.pick_voice and CONFIG_FILE.exists() and config.get("voice"):
        voice_id = config["voice"]
        print(f"Using saved default voice: {voice_id} (use --pick-voice to choose a different one)")
    else:
        volume_for_preview = args.volume if args.volume is not None else config["volume"]
        speed_for_preview = args.speed if args.speed is not None else config["speed"]
        voice_id = choose_voice_interactively(volume_for_preview, speed_for_preview)

    volume = args.volume if args.volume is not None else config["volume"]
    speed = args.speed if args.speed is not None else config["speed"]

    fmt = args.format
    if not fmt and args.output and not batch_mode:
        ext = os.path.splitext(args.output)[1].lstrip(".").lower()
        fmt = ext if ext in ("wav", "mp3") else "wav"
    if not fmt:
        fmt = config["format"]

    if args.save_config:
        save_config({"voice": voice_id, "volume": volume, "speed": speed, "format": fmt})
        print(f"Saved defaults to {CONFIG_FILE}")

    print(f"\nGenerating audio with volume={volume}, speed={speed} ...")

    succeeded, failed = [], []
    for i, input_file in enumerate(input_files, start=1):
        prefix = f"[{i}/{len(input_files)}] " if batch_mode else ""
        try:
            text = read_text_file(input_file)
            if not text:
                raise ValueError("input file is empty")

            print(f"{prefix}{input_file} ({len(text)} characters)")
            output_path = compute_output_path(input_file, args.output, fmt, batch_mode)

            if fmt == "wav":
                synthesizer.synthesize(text, voice_id, volume, output_path, speed=speed)
            else:
                fd, tmp_wav = tempfile.mkstemp(suffix=".wav")
                os.close(fd)
                try:
                    synthesizer.synthesize(text, voice_id, volume, tmp_wav, speed=speed)
                    convert_wav_to(tmp_wav, output_path, fmt)
                finally:
                    if os.path.exists(tmp_wav):
                        os.remove(tmp_wav)

            size_kb = os.path.getsize(output_path) / 1024
            print(f"  -> Saved to: {output_path} ({size_kb:.1f} KB)")
            succeeded.append(input_file)
        except Exception as e:
            print(f"  Error processing '{input_file}': {e}")
            failed.append(input_file)
            if not batch_mode:
                sys.exit(1)

    if batch_mode:
        print(f"\nDone! {len(succeeded)} succeeded, {len(failed)} failed.")
        if failed:
            sys.exit(1)
    else:
        print("\nDone!")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCancelled.")
        sys.exit(1)
