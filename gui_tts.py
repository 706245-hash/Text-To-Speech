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
import os
import shutil
import subprocess
import tempfile
import threading
import tkinter as tk
from pathlib import Path
from tkinter import ttk, filedialog, messagebox

import pygame

from tts_config import PIPER_VOICES
from tts_engine import PiperSynthesizer


class AudioPlayer:
    """Wrapper for audio playback via pygame and synthesis via PiperSynthesizer."""
    
    def __init__(self):
        self.synthesizer = PiperSynthesizer()
        self.current_playback = None
        try:
            pygame.mixer.init()
        except Exception as e:
            print(f"Warning: Could not initialize audio: {e}")
    
    def synthesize(self, text, voice_id, volume, output_path=None):
        """Synthesize text to WAV file."""
        return self.synthesizer.synthesize(text, voice_id, volume, output_path)
    
    def play_wav(self, wav_path):
        """Play a WAV file using pygame."""
        try:
            pygame.mixer.stop()
            sound = pygame.mixer.Sound(wav_path)
            sound.play()
            self.current_playback = sound
        except Exception as e:
            raise RuntimeError(f"Failed to play audio: {e}")
    
    def stop_playback(self):
        """Stop playback."""
        try:
            pygame.mixer.stop()
        except:
            pass
        self.current_playback = None


# Global audio player instance
audio_player = AudioPlayer()






class TTSApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Text to Speech")
        self.geometry("780x620")
        self.minsize(640, 520)

        self.voices = []           # all voice objects from the engine
        self.filtered_voices = []  # currently filtered/displayed subset
        self.busy = False          # true while a background TTS job runs

        self._build_ui()
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
        self.char_count_var = tk.StringVar(value="0 characters")
        ttk.Label(toolbar, textvariable=self.char_count_var).pack(side="right")

        self.text_box = tk.Text(text_frame, wrap="word", undo=True, font=("Sans", 11))
        self.text_box.pack(fill="both", expand=True, padx=6, pady=6)
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

        # --- Customisation sliders ---
        controls_frame = ttk.LabelFrame(self, text="Customise")
        controls_frame.pack(fill="x", **pad)

        self.rate_var = tk.IntVar(value=175)
        self._add_slider(controls_frame, "Rate (words/min)", self.rate_var, 80, 300)

        self.volume_var = tk.DoubleVar(value=1.0)
        self._add_slider(controls_frame, "Volume", self.volume_var, 0.0, 1.0, is_float=True)

        # --- Actions ---
        action_frame = ttk.Frame(self)
        action_frame.pack(fill="x", **pad)
        ttk.Button(action_frame, text="Preview Text", command=self.preview_text).pack(side="left")
        ttk.Button(action_frame, text="Stop", command=self.stop_speaking).pack(side="left", padx=6)
        self.export_btn = ttk.Button(action_frame, text="Export Audio...", command=self.export_audio)
        self.export_btn.pack(side="right")

        # --- Status bar ---
        self.status_var = tk.StringVar(value="Loading voices...")
        status = ttk.Label(self, textvariable=self.status_var, anchor="w", relief="sunken")
        status.pack(fill="x", side="bottom")

        self.progress = ttk.Progressbar(self, mode="indeterminate")
        # packed/unpacked dynamically while busy

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
        self.status_var.set(f"Loaded: {os.path.basename(path)}")

    def clear_text(self):
        self.text_box.delete("1.0", "end")

    # ------------------------------------------------------------------
    # Busy state helpers
    # ------------------------------------------------------------------

    def _set_busy(self, busy, status=None):
        self.busy = busy
        state = "disabled" if busy else "normal"
        self.export_btn.config(state=state)
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
                audio_player.synthesize(text, voice_id, self.volume_var.get(), tmp_wav)
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

    def stop_speaking(self):
        """Stop playback."""
        audio_player.stop_playback()
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
        rate = self.rate_var.get()
        volume = self.volume_var.get()

        def worker():
            tmp_wav = None
            try:
                if fmt == "wav":
                    audio_player.synthesize(content, voice_id, volume, path)
                else:
                    fd, tmp_wav = tempfile.mkstemp(suffix=".wav")
                    os.close(fd)
                    audio_player.synthesize(content, voice_id, volume, tmp_wav)
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
