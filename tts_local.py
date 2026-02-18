"""
TTS Local Module

Provides text-to-speech synthesis using Piper TTS.
Supports caching to avoid regenerating audio for identical text.
"""

import hashlib
import logging
import subprocess
from pathlib import Path
from typing import Optional


class LocalTTS:
    def __init__(
        self,
        model_path: str = "/home/remvelchio/agent/models/piper/en_US-lessac-medium.onnx",
        config_path: str = "/home/remvelchio/agent/models/piper/en_US-lessac-medium.onnx.json",
        cache_dir: str = "/home/remvelchio/agent/tmp/audio",
    ):
        self.model_path = model_path
        self.config_path = config_path
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger(__name__)

    def _cache_key(self, text: str) -> str:
        return hashlib.md5(text.encode("utf-8")).hexdigest()

    def synthesize(self, text: str) -> Optional[str]:
        if not text or not text.strip():
            return None

        key = self._cache_key(text)
        out_path = self.cache_dir / f"tts_{key}.wav"

        if out_path.exists():
            return str(out_path)

        cmd = [
            "piper",
            "--model", self.model_path,
            "--config", self.config_path,
            "--output_file", str(out_path),
        ]
        proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        proc.communicate(input=text)

        if out_path.exists():
            return str(out_path)

        self.logger.error("Piper failed to create audio output.")
        return None
