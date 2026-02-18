"""
TTS Local Module

Provides text-to-speech synthesis using Piper TTS.
Supports caching to avoid regenerating audio for identical text.
"""

import logging
import hashlib
import os
import subprocess
from pathlib import Path
from typing import Optional


class LocalTTS:
    """
    Local text-to-speech using Piper.
    
    Generates audio files from text and caches them to avoid
    regeneration when text is unchanged.
    """
    
    def __init__(self, cache_dir: str = "/tmp/tts_cache", model: str = "en_US-lessac-medium"):
        """
        Initialize LocalTTS.
        
        Args:
            cache_dir: Directory to store cached audio files
            model: Piper model to use for synthesis
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.model = model
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"LocalTTS initialized with cache_dir={cache_dir}, model={model}")
    
    def _get_cache_key(self, text: str, voice: str = "default") -> str:
        """
        Generate cache key from text and voice.
        
        Args:
            text: Text to synthesize
            voice: Voice identifier
            
        Returns:
            MD5 hash of text + voice
        """
        content = f"{text}|{voice}|{self.model}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def _get_cache_path(self, cache_key: str) -> Path:
        """Get path to cached audio file."""
        return self.cache_dir / f"{cache_key}.wav"
    
    def synthesize(self, text: str, output_path: Optional[str] = None, voice: str = "default") -> str:
        """
        Synthesize text to speech.
        
        Args:
            text: Text to synthesize
            output_path: Optional custom output path. If None, uses cache.
            voice: Voice identifier for cache differentiation
            
        Returns:
            Path to generated audio file
        """
        if not text or not text.strip():
            self.logger.warning("Empty text provided for TTS synthesis")
            return None
        
        # Check cache first
        cache_key = self._get_cache_key(text, voice)
        cache_path = self._get_cache_path(cache_key)
        
        if cache_path.exists():
            self.logger.info(f"Using cached audio for text: {text[:50]}...")
            if output_path and output_path != str(cache_path):
                # Copy cached file to requested output path
                import shutil
                shutil.copy(cache_path, output_path)
                return output_path
            return str(cache_path)
        
        # Determine output path
        final_output = output_path if output_path else str(cache_path)
        
        # Synthesize with Piper
        self.logger.info(f"Synthesizing audio for text: {text[:50]}...")
        
        try:
            # Run Piper TTS
            # Command: echo "text" | piper --model <model> --output_file <output>
            cmd = [
                "piper",
                "--model", self.model,
                "--output_file", final_output
            ]
            
            result = subprocess.run(
                cmd,
                input=text.encode(),
                capture_output=True,
                timeout=30
            )
            
            if result.returncode != 0:
                self.logger.error(f"Piper TTS failed: {result.stderr.decode()}")
                # Fall back to creating silent audio or raise error
                raise RuntimeError(f"Piper TTS synthesis failed: {result.stderr.decode()}")
            
            self.logger.info(f"Successfully synthesized audio to {final_output}")
            
            # If we used a custom output path, also cache it
            if output_path and output_path != str(cache_path):
                import shutil
                shutil.copy(output_path, cache_path)
            
            return final_output
            
        except FileNotFoundError:
            self.logger.error("Piper TTS not found. Please install piper-tts.")
            # Create a placeholder silent audio file for testing
            return self._create_silent_audio(final_output)
        except subprocess.TimeoutExpired:
            self.logger.error("Piper TTS synthesis timed out")
            return self._create_silent_audio(final_output)
        except Exception as e:
            self.logger.error(f"Error during TTS synthesis: {e}")
            return self._create_silent_audio(final_output)
    
    def _create_silent_audio(self, output_path: str, duration: float = 5.0) -> str:
        """
        Create a silent audio file as fallback.
        
        Args:
            output_path: Path to output file
            duration: Duration in seconds
            
        Returns:
            Path to created audio file
        """
        try:
            # Use ffmpeg to create silent audio
            cmd = [
                "ffmpeg", "-y",
                "-f", "lavfi",
                "-i", f"anullsrc=duration={duration}:sample_rate=22050",
                "-acodec", "pcm_s16le",
                output_path
            ]
            subprocess.run(cmd, capture_output=True, timeout=10)
            self.logger.warning(f"Created silent audio fallback at {output_path}")
            return output_path
        except Exception as e:
            self.logger.error(f"Failed to create silent audio: {e}")
            return None
    
    def clear_cache(self):
        """Clear all cached audio files."""
        import shutil
        if self.cache_dir.exists():
            shutil.rmtree(self.cache_dir)
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self.logger.info("TTS cache cleared")
