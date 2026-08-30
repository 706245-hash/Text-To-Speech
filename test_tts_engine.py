import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tts_engine import PiperSynthesizer


class PiperSynthesizerLoggingTests(unittest.TestCase):
    def test_ensure_model_downloaded_uses_logger_and_not_print(self):
        temp_dir = Path(tempfile.mkdtemp(prefix="tts_engine_test_"))
        synth = PiperSynthesizer()
        synth.models_dir = temp_dir
        voice_id = "test_voice"

        with patch("tts_engine.download_voice") as mock_download, \
             patch("logging.getLogger") as mock_get_logger, \
             patch("sys.stdout", new_callable=io.StringIO) as stdout:
            logger = mock_get_logger.return_value
            mock_download.return_value = None

            synth.ensure_model_downloaded(voice_id)

            self.assertTrue(mock_get_logger.called)
            self.assertTrue(logger.info.called)
            self.assertEqual(stdout.getvalue(), "")

    def test_resolve_model_path_accepts_local_onnx_file(self):
        temp_dir = Path(tempfile.mkdtemp(prefix="tts_engine_local_"))
        local_model = temp_dir / "custom_voice.onnx"
        local_model.write_bytes(b"not real model")

        synth = PiperSynthesizer()
        synth.models_dir = temp_dir

        self.assertEqual(synth.resolve_model_path(str(local_model)), local_model)

    def test_ensure_model_downloaded_allows_local_onnx_inputs(self):
        temp_dir = Path(tempfile.mkdtemp(prefix="tts_engine_local_"))
        local_model = temp_dir / "custom_voice.onnx"
        local_model.write_bytes(b"not real model")

        synth = PiperSynthesizer()
        synth.models_dir = temp_dir

        with patch("tts_engine.download_voice") as mock_download:
            synth.ensure_model_downloaded(str(local_model))
            mock_download.assert_not_called()


if __name__ == "__main__":
    unittest.main()
