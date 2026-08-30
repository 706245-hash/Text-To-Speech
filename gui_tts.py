#!/usr/bin/env python3
"""
GUI Text-to-Speech App
------------------------
A Tkinter desktop app to type or load text, browse/customise a voice
(voice, rate, volume, pitch where supported), preview it out loud,
and export the narration as a WAV or MP3 file.

Requires: piper-tts (pip install piper-tts), pygame (pip install pygame),
tkinter (usually bundled with Python; on Linux: apt install python3-tk),
and ffmpeg on PATH if exporting to MP3.
"""

import io
import json
import os
import shutil
import subprocess
import tempfile
import threading
import tkinter as tk
from pathlib import Path
from tkinter import ttk, filedialog, messagebox, simpledialog

import pygame

from tts_config import PIPER_VOICES
from tts_engine import PiperSynthesizer


class AudioPlayer:
    """Wrapper for audio playback via pygame and synthesis via PiperSynthesizer."""
    
    def __init__(self):
        self.synthesizer = PiperSynthesizer()
        self.current_playback = None
        self.current_channel = None
        self.paused = False
        try:
            pygame.mixer.init()
        except Exception as e:
            print(f"Warning: Could not initialize audio: {e}")
    
    def synthesize(self, text, voice_id, volume, output_path=None, speed=1.0):
        """Synthesize text to WAV file."""
        return self.synthesizer.synthesize(text, voice_id, volume, output_path, speed=speed)
    
    def play_wav(self, wav_path):
        """Play a WAV file using pygame."""
        try:
            pygame.mixer.stop()
            sound = pygame.mixer.Sound(wav_path)
            channel = pygame.mixer.find_channel(True)
            if channel is None:
                raise RuntimeError("No available audio channel found")
            channel.play(sound)
            self.current_playback = sound
            self.current_channel = channel
            self.paused = False
        except Exception as e:
            raise RuntimeError(f"Failed to play audio: {e}")

    def pause_playback(self):
        """Pause the active playback if possible."""
        if self.current_channel is not None and self.current_playback is not None:
            self.current_channel.pause()
            self.paused = True

    def resume_playback(self):
        """Resume playback after pausing."""
        if self.current_channel is not None and self.current_playback is not None:
            self.current_channel.unpause()
            self.paused = False
    
    def stop_playback(self):
        """Stop playback."""
        try:
            pygame.mixer.stop()
        except Exception:
            pass
        self.current_playback = None
        self.current_channel = None
        self.paused = False


# Global audio player instance
audio_player = AudioPlayer()






class TTSApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Text to Speech")
        self.geometry("860x620")
        self.minsize(760, 520)

        self.voices = []           # all voice objects from the engine
        self.filtered_voices = []  # currently filtered/displayed subset
        self.busy = False          # true while a background TTS job runs
        self.recent_files = self._load_recent_files()
        self.presets = self._load_presets()

        self._build_ui()
        self.after(50, self._adjust_window_to_fit)
        self._load_voices_async()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        pad = {"padx": 10, "pady": 6}

        # --- Text input area ---
        text_frame = ttk.LabelFrame(self, text="Text")
        text_frame.pack(fill="both", expand=True, **pad)

        toolbar = ttk.Frame(text_frame)
        toolbar.pack(fill="x", padx=6, pady=(6, 0))
        ttk.Button(toolbar, text="Load Text File...", command=self.load_text_file).pack(side="left")
        ttk.Button(toolbar, text="Clear", command=self.clear_text).pack(side="left", padx=(6, 0))

        self.recent_var = tk.StringVar()
        self.recent_combo = ttk.Combobox(toolbar, textvariable=self.recent_var, width=35, state="readonly")
        self.recent_combo.pack(side="left", padx=(12, 0))
        self.recent_combo.bind("<Return>", lambda _evt: self.open_recent_file())
        ttk.Button(toolbar, text="Open Recent", command=self.open_recent_file).pack(side="left", padx=(6, 0))
        self.recent_combo["values"] = self.recent_files
        if self.recent_files:
            self.recent_combo.current(0)

        self.char_count_var = tk.StringVar(value="0 characters")
        ttk.Label(toolbar, textvariable=self.char_count_var).pack(side="right")

        text_container = ttk.Frame(text_frame)
        text_container.pack(fill="both", expand=True, padx=6, pady=6)

        self.text_box = tk.Text(text_container, wrap="word", undo=True, height=12, font=("Sans", 11))
        self.text_box.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(text_container, orient="vertical", command=self.text_box.yview)
        scrollbar.pack(side="right", fill="y")
        self.text_box.configure(yscrollcommand=scrollbar.set)
        self.text_box.bind("<<Modified>>", self._on_text_modified)

        # --- Voice selection ---
        voice_frame = ttk.LabelFrame(self, text="Voice")
        voice_frame.pack(fill="x", **pad)

        filter_row = ttk.Frame(voice_frame)
        filter_row.pack(fill="x", padx=6, pady=(6, 0))
        ttk.Label(filter_row, text="Filter:").pack(side="left")
        self.filter_var = tk.StringVar()
        self.filter_var.trace_add("write", lambda *_: self._apply_filter())
        ttk.Entry(filter_row, textvariable=self.filter_var).pack(side="left", fill="x", expand=True, padx=6)

        combo_row = ttk.Frame(voice_frame)
        combo_row.pack(fill="x", padx=6, pady=6)
        ttk.Label(combo_row, text="Voice:").pack(side="left")
        self.voice_combo = ttk.Combobox(combo_row, state="readonly", width=55)
        self.voice_combo.pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(combo_row, text="Preview Voice", command=self.preview_voice).pack(side="left")

        preset_row = ttk.Frame(voice_frame)
        preset_row.pack(fill="x", padx=6, pady=(0, 6))
        self.preset_var = tk.StringVar()
        self.preset_combo = ttk.Combobox(preset_row, textvariable=self.preset_var, state="readonly", width=28)
        self.preset_combo.pack(side="left")
        ttk.Button(preset_row, text="Save Preset", command=self.save_current_preset).pack(side="left", padx=(6, 0))
        ttk.Button(preset_row, text="Load Preset", command=self.load_selected_preset).pack(side="left", padx=(6, 0))
        self._refresh_presets()

        # --- Customisation sliders ---
        controls_frame = ttk.LabelFrame(self, text="Customise")
        controls_frame.pack(fill="x", **pad)

        self.rate_var = tk.DoubleVar(value=1.0)
        self._add_slider(controls_frame, "Speed", self.rate_var, 0.5, 2.0, is_float=True)

        self.volume_var = tk.DoubleVar(value=1.0)
        self._add_slider(controls_frame, "Volume", self.volume_var, 0.0, 1.0, is_float=True)

        # --- Actions ---
        action_frame = ttk.Frame(self)
        action_frame.pack(fill="x", **pad)
        ttk.Button(action_frame, text="Preview Text", command=self.preview_text).pack(side="left")
        self.pause_btn = ttk.Button(action_frame, text="Pause", command=self.toggle_pause)
        self.pause_btn.pack(side="left", padx=6)
        ttk.Button(action_frame, text="Stop", command=self.stop_speaking).pack(side="left")
        self.export_btn = ttk.Button(action_frame, text="Export Audio...", command=self.export_audio)
        self.export_btn.pack(side="right")

        # --- Status bar ---
        self.status_var = tk.StringVar(value="Loading voices...")
        status = ttk.Label(self, textvariable=self.status_var, anchor="w", relief="sunken")
        status.pack(fill="x", side="bottom")

        self.progress = ttk.Progressbar(self, mode="indeterminate")
        # packed/unpacked dynamically while busy

    def _adjust_window_to_fit(self):
        self.update_idletasks()
        width = max(self.winfo_reqwidth() + 20, 760)
        height = min(max(self.winfo_reqheight() + 20, 540), 720)
        self.minsize(760, 520)
        self.geometry(f"{width}x{height}")

    def _add_slider(self, parent, label, var, frm, to, is_float=False):
        row = ttk.Frame(parent)
        row.pack(fill="x", padx=6, pady=4)
        ttk.Label(row, text=label, width=18).pack(side="left")
        value_lbl = ttk.Label(row, width=6)
        value_lbl.pack(side="right")

        def on_change(_evt=None):
            v = var.get()
            value_lbl.config(text=f"{v:.2f}" if is_float else f"{int(v)}")

        scale = ttk.Scale(row, from_=frm, to=to, variable=var, orient="horizontal", command=on_change)
        scale.pack(side="left", fill="x", expand=True, padx=8)
        on_change()

    # ------------------------------------------------------------------
    # Voice loading / filtering
    # ------------------------------------------------------------------

    def _load_voices_async(self):
        def worker():
            try:
                # With piper, voices are loaded on-demand, so just return the available list
                voices = [(vid, name) for vid, name in PIPER_VOICES]
            except Exception as e:
                self.after(0, lambda: self._voice_load_failed(e))
                return
            self.after(0, lambda: self._voices_loaded(voices))

        threading.Thread(target=worker, daemon=True).start()

    def _voices_loaded(self, voices):
        self.voices = voices
        self._apply_filter()
        self.status_var.set(f"{len(voices)} voices available. Ready.")

    def _voice_load_failed(self, error):
        messagebox.showerror("Error", f"Could not load voices:\n{error}")
        self.status_var.set("Failed to load voices.")

    def _apply_filter(self):
        query = self.filter_var.get().strip().lower()
        if not query:
            self.filtered_voices = list(self.voices)
        else:
            self.filtered_voices = [
                (vid, name) for vid, name in self.voices
                if query in f"{vid} {name}".lower()
            ]
        labels = [f"{name}  ({vid})" for vid, name in self.filtered_voices]
        self.voice_combo["values"] = labels
        if labels:
            self.voice_combo.current(0)
        else:
            self.voice_combo.set("")

    def _selected_voice_id(self):
        idx = self.voice_combo.current()
        if idx < 0 or idx >= len(self.filtered_voices):
            return None
        return self.filtered_voices[idx][0]

    # ------------------------------------------------------------------
    # Text helpers
    # ------------------------------------------------------------------

    def _on_text_modified(self, _evt):
        self.text_box.edit_modified(False)
        content = self.text_box.get("1.0", "end-1c")
        self.char_count_var.set(f"{len(content)} characters")

    def _load_recent_files(self):
        config_dir = Path.home() / ".config" / "tts"
        path = config_dir / "recent_files.json"
        if not path.exists():
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return [str(p) for p in data if str(p)]
        except (OSError, json.JSONDecodeError):
            pass
        return []

    def _save_recent_files(self):
        config_dir = Path.home() / ".config" / "tts"
        config_dir.mkdir(parents=True, exist_ok=True)
        path = config_dir / "recent_files.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.recent_files[:10], f, indent=2)

    def _remember_recent_file(self, path):
        if not path:
            return
        canonical = os.path.abspath(path)
        self.recent_files = [item for item in self.recent_files if os.path.abspath(item) != canonical]
        self.recent_files.insert(0, canonical)
        self.recent_files = self.recent_files[:10]
        self._save_recent_files()
        self.recent_combo["values"] = self.recent_files
        if self.recent_files:
            self.recent_combo.current(0)

    def load_text_file(self):
        path = filedialog.askopenfilename(
            title="Choose a text file",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except Exception as e:
            messagebox.showerror("Error", f"Could not read file:\n{e}")
            return
        self.text_box.delete("1.0", "end")
        self.text_box.insert("1.0", content)
        self._remember_recent_file(path)
        self.status_var.set(f"Loaded: {os.path.basename(path)}")

    def open_recent_file(self):
        path = self.recent_var.get()
        if not path:
            return
        if not os.path.exists(path):
            messagebox.showwarning("Missing file", f"Recent file no longer exists:\n{path}")
            self.recent_files = [item for item in self.recent_files if item != path]
            self._save_recent_files()
            self._refresh_recent_files()
            return
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except Exception as e:
            messagebox.showerror("Error", f"Could not read file:\n{e}")
            return
        self.text_box.delete("1.0", "end")
        self.text_box.insert("1.0", content)
        self.status_var.set(f"Loaded recent: {os.path.basename(path)}")

    def clear_text(self):
        self.text_box.delete("1.0", "end")

    def _load_presets(self):
        config_dir = Path.home() / ".config" / "tts"
        path = config_dir / "presets.json"
        if not path.exists():
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except (OSError, json.JSONDecodeError):
            pass
        return {}

    def _save_presets(self):
        config_dir = Path.home() / ".config" / "tts"
        config_dir.mkdir(parents=True, exist_ok=True)
        path = config_dir / "presets.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.presets, f, indent=2)

    def _refresh_recent_files(self):
        self.recent_combo["values"] = self.recent_files
        if self.recent_files:
            self.recent_combo.current(0)

    def _refresh_presets(self):
        names = list(self.presets.keys())
        self.preset_combo["values"] = names
        if names:
            self.preset_combo.current(0)
        else:
            self.preset_combo.set("")

    def save_current_preset(self):
        name = simpledialog.askstring("Save preset", "Preset name:", parent=self)
        if not name:
            return
        self.presets[name.strip()] = {
            "voice_id": self._selected_voice_id(),
            "volume": self.volume_var.get(),
            "speed": self.rate_var.get(),
        }
        self._save_presets()
        self._refresh_presets()
        self.status_var.set(f"Saved preset: {name.strip()}")

    def load_selected_preset(self):
        preset_name = self.preset_var.get()
        if not preset_name or preset_name not in self.presets:
            return
        preset = self.presets[preset_name]
        voice_id = preset.get("voice_id")
        if voice_id:
            values = [vid for vid, _ in self.filtered_voices]
            for idx, vid in enumerate(values):
                if vid == voice_id:
                    self.voice_combo.current(idx)
                    break
        volume = preset.get("volume")
        speed = preset.get("speed")
        if volume is not None:
            self.volume_var.set(float(volume))
        if speed is not None:
            self.rate_var.set(float(speed))
        self.status_var.set(f"Loaded preset: {preset_name}")

    # ------------------------------------------------------------------
    # Busy state helpers
    # ------------------------------------------------------------------

    def _set_busy(self, busy, status=None):
        self.busy = busy
        state = "disabled" if busy else "normal"
        self.export_btn.config(state=state)
        self.pause_btn.config(state=state)
        if busy:
            self.progress.pack(fill="x", side="bottom")
            self.progress.start(12)
        else:
            self.progress.stop()
            self.progress.pack_forget()
        if status:
            self.status_var.set(status)

    # ------------------------------------------------------------------
    # Preview
    # ------------------------------------------------------------------

    def preview_voice(self):
        voice_id = self._selected_voice_id()
        if not voice_id:
            messagebox.showwarning("No voice", "Please select a voice first.")
            return
        self._speak_async("This is a preview of the selected voice.", voice_id)

    def preview_text(self):
        content = self.text_box.get("1.0", "end-1c").strip()
        if not content:
            messagebox.showwarning("No text", "Type or load some text first.")
            return
        voice_id = self._selected_voice_id()
        sample = content[:400]  # keep previews short
        self._speak_async(sample, voice_id)

    def _speak_async(self, text, voice_id):
        if self.busy:
            return
        self._set_busy(True, "Speaking...")

        def worker():
            tmp_wav = None
            try:
                fd, tmp_wav = tempfile.mkstemp(suffix=".wav")
                os.close(fd)
                audio_player.synthesize(text, voice_id, self.volume_var.get(), tmp_wav, speed=self.rate_var.get())
                audio_player.play_wav(tmp_wav)
                self.after(0, lambda: self._set_busy(False, "Ready."))
            except Exception as e:
                self.after(0, lambda: self._speak_failed(e))
            finally:
                # Keep the file around for playback; it will be cleaned up when app closes
                pass

        threading.Thread(target=worker, daemon=True).start()

    def _speak_failed(self, error):
        self._set_busy(False, "Ready.")
        messagebox.showerror(
            "Playback error",
            f"Could not play audio out loud on this system:\n{error}\n\n"
            "You can still use Export Audio to save it to a file.",
        )

    def toggle_pause(self):
        if audio_player.paused:
            audio_player.resume_playback()
            self.pause_btn.config(text="Pause")
            self.status_var.set("Playback resumed.")
        else:
            audio_player.pause_playback()
            self.pause_btn.config(text="Resume")
            self.status_var.set("Playback paused.")

    def stop_speaking(self):
        """Stop playback."""
        audio_player.stop_playback()
        self.pause_btn.config(text="Pause")
        self._set_busy(False, "Stopped.")

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def export_audio(self):
        content = self.text_box.get("1.0", "end-1c").strip()
        if not content:
            messagebox.showwarning("No text", "Type or load some text first.")
            return
        voice_id = self._selected_voice_id()
        if not voice_id:
            messagebox.showwarning("No voice", "Please select a voice first.")
            return

        path = filedialog.asksaveasfilename(
            title="Export audio as...",
            defaultextension=".wav",
            filetypes=[("WAV audio", "*.wav"), ("MP3 audio", "*.mp3")],
        )
        if not path:
            return

        fmt = "mp3" if path.lower().endswith(".mp3") else "wav"
        if fmt == "mp3" and not shutil.which("ffmpeg"):
            messagebox.showerror(
                "ffmpeg not found",
                "Exporting to MP3 requires ffmpeg to be installed and on your PATH.\n"
                "Install ffmpeg, or export as .wav instead.",
            )
            return

        self._set_busy(True, f"Exporting to {os.path.basename(path)}...")
        speed = self.rate_var.get()
        volume = self.volume_var.get()

        def worker():
            tmp_wav = None
            try:
                if fmt == "wav":
                    audio_player.synthesize(content, voice_id, volume, path, speed=speed)
                else:
                    fd, tmp_wav = tempfile.mkstemp(suffix=".wav")
                    os.close(fd)
                    audio_player.synthesize(content, voice_id, volume, tmp_wav, speed=speed)
                    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", tmp_wav, path]
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    if result.returncode != 0:
                        raise RuntimeError(result.stderr)
                self.after(0, lambda: self._export_done(path))
            except Exception as e:
                self.after(0, lambda: self._export_failed(e))
            finally:
                if tmp_wav and os.path.exists(tmp_wav):
                    os.remove(tmp_wav)

        threading.Thread(target=worker, daemon=True).start()

    def _export_done(self, path):
        self._set_busy(False, "Ready.")
        size_kb = os.path.getsize(path) / 1024
        self.status_var.set(f"Saved: {path} ({size_kb:.1f} KB)")
        messagebox.showinfo("Export complete", f"Audio saved to:\n{path}")

    def _export_failed(self, error):
        self._set_busy(False, "Ready.")
        messagebox.showerror("Export failed", str(error))


def main():
    app = TTSApp()
    app.mainloop()


if __name__ == "__main__":
    main()
