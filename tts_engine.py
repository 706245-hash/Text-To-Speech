"""
Piper TTS Engine
================

Core TTS synthesis engine for Piper neural voices.
Handles model downloading, voice synthesis, and audio processing.
"""

import os
import subprocess
import tempfile
import wave
from pathlib import Path

try:
    from piper.download_voices import download_voice
except ImportError:
    download_voice = None

try:
    from tts_config import MODELS_DIR, DEFAULT_VOICE
except ImportError:
    from .tts_config import MODELS_DIR, DEFAULT_VOICE


class PiperSynthesizer:
    """Manages Piper TTS voice synthesis and audio output."""
    
    def __init__(self):
        """Initialize the synthesizer."""
        self.models_dir = MODELS_DIR
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self._piper_cmd = None
    
    def _find_piper_command(self):
        """Find piper executable in venv or PATH."""
        if self._piper_cmd is not None:
            return self._piper_cmd
        
        # Try common venv locations
        possible_paths = [
            Path.home() / ".venv" / "bin" / "piper",
            Path.home() / "venv" / "bin" / "piper",
            Path.home().parent / "Documents" / "CODE" / "tts" / "venv" / "bin" / "piper",
            Path("/usr/local/bin/piper"),
            Path("/usr/bin/piper"),
        ]
        
        # Check explicit paths first
        for path in possible_paths:
            if path.exists():
                self._piper_cmd = str(path)
                return self._piper_cmd
        
        # Fall back to PATH search
        self._piper_cmd = "piper"
        return self._piper_cmd
    
    def ensure_model_downloaded(self, voice_id):
        """
        Ensure a voice model is downloaded and ready.
        
        Args:
            voice_id: Voice identifier (e.g. 'en_US-lessac-medium')
            
        Raises:
            RuntimeError: If model cannot be downloaded
        """
        model_file = self.models_dir / f"{voice_id}.onnx"
        config_file = self.models_dir / f"{voice_id}.onnx.json"
        
        if model_file.exists() and config_file.exists():
            return  # Already downloaded
        
        if download_voice is None:
            raise RuntimeError(
                f"Piper voice model '{voice_id}' not found and download not available. "
                f"Install piper-tts with: pip install piper-tts"
            )
        
        print(f"  Downloading voice model '{voice_id}'...")
        print(f"  (This may take a few minutes on first use)")
        
        try:
            download_voice(voice_id, self.models_dir)
            print(f"  Download complete!")
        except Exception as e:
            raise RuntimeError(
                f"Failed to download voice model '{voice_id}': {e}\n"
                f"Make sure you have internet connection and sufficient disk space."
            )
    
    def synthesize(self, text, voice_id, volume=1.0, output_path=None):
        """
        Synthesize text to speech.
        
        Args:
            text: Input text to synthesize
            voice_id: Voice identifier (e.g. 'en_US-lessac-medium')
            volume: Volume level (0.0-1.0, default 1.0)
            output_path: Output file path. If None, returns path to temp WAV file.
            
        Returns:
            Path to generated WAV file
            
        Raises:
            RuntimeError: If synthesis fails
        """
        # Ensure model is available
        self.ensure_model_downloaded(voice_id)
        
        # Use provided output or create temp file
        if output_path is None:
            fd, output_path = tempfile.mkstemp(suffix=".wav")
            os.close(fd)
        
        model_file = self.models_dir / f"{voice_id}.onnx"
        
        # Build piper command
        piper_cmd = self._find_piper_command()
        cmd = [piper_cmd, "--model", str(model_file), "--output-file", output_path]
        
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
            return output_path
            
        except subprocess.TimeoutExpired:
            raise RuntimeError("Synthesis timed out (exceeded 10 minutes)")
        except FileNotFoundError:
            raise RuntimeError("Piper command not found. Install with: pip install piper-tts")
        except Exception as e:
            if isinstance(e, RuntimeError):
                raise
            raise RuntimeError(f"Failed to synthesize audio: {e}")
    
    @staticmethod
    def apply_volume_to_wav(wav_path, volume):
        """
        Apply volume scaling to a WAV file.
        
        Args:
            wav_path: Path to WAV file to modify
            volume: Volume multiplier (0.0-1.0)
        """
        if volume == 1.0:
            return  # No change needed
        
        try:
            with wave.open(wav_path, "r+b") as wav_file:
                frames = wav_file.readframes(wav_file.getnframes())
                audio_data = bytearray(frames)
                
                # Process as 16-bit signed integers
                for i in range(0, len(audio_data) - 1, 2):
                    sample = int.from_bytes(audio_data[i:i+2], byteorder='little', signed=True)
                    sample = int(sample * volume)
                    sample = max(-32768, min(32767, sample))  # Clamp to valid range
                    audio_data[i:i+2] = sample.to_bytes(2, byteorder='little', signed=True)
                
                wav_file.rewind()
                wav_file.writeframes(bytes(audio_data))
        except Exception as e:
            print(f"  Warning: Could not apply volume: {e}", flush=True)
