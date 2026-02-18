"""
Video Loop Module

Generates looping video clips for broadcast output.
Supports muxing audio into video for Owncast streaming.
"""

import logging
import os
import subprocess
from pathlib import Path
from typing import Optional


class VideoLoopGenerator:
    """
    Generates video loops with optional audio for broadcast.
    
    Creates MP4 video loops that can be streamed to Owncast.
    Supports embedding audio (e.g., TTS narration) into the video.
    """
    
    def __init__(self, output_dir: str = "/tmp/video_loops", default_duration: int = 30):
        """
        Initialize VideoLoopGenerator.
        
        Args:
            output_dir: Directory to store generated video loops
            default_duration: Default duration for loops without audio (seconds)
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.default_duration = default_duration
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"VideoLoopGenerator initialized with output_dir={output_dir}")
    
    def make_loop(
        self,
        image_path: Optional[str] = None,
        audio_path: Optional[str] = None,
        output_path: Optional[str] = None,
        duration: Optional[int] = None
    ) -> str:
        """
        Generate a video loop from an image with optional audio.
        
        Args:
            image_path: Path to image file. If None, creates color bar test pattern.
            audio_path: Path to audio file to mux into video. If None, video has no audio.
            output_path: Custom output path. If None, auto-generates in output_dir.
            duration: Duration in seconds. If None and audio_path provided, uses audio duration.
                     Otherwise uses default_duration.
        
        Returns:
            Path to generated video file
        """
        # Determine duration
        if duration is None:
            if audio_path:
                duration = self._get_audio_duration(audio_path)
            else:
                duration = self.default_duration
        
        # Generate output path if not provided
        if output_path is None:
            import hashlib
            import time
            key = f"{image_path}|{audio_path}|{duration}|{time.time()}"
            filename = hashlib.md5(key.encode()).hexdigest() + ".mp4"
            output_path = str(self.output_dir / filename)
        
        self.logger.info(f"Generating video loop: duration={duration}s, audio={audio_path is not None}")
        
        try:
            # Build ffmpeg command
            cmd = ["ffmpeg", "-y"]
            
            # Input: image or test pattern
            if image_path and os.path.exists(image_path):
                # Loop image for duration
                cmd.extend([
                    "-loop", "1",
                    "-i", image_path,
                    "-t", str(duration)
                ])
            else:
                # Generate test pattern (color bars)
                cmd.extend([
                    "-f", "lavfi",
                    "-i", f"testsrc=duration={duration}:size=1920x1080:rate=30",
                ])
            
            # Input: audio (if provided)
            if audio_path and os.path.exists(audio_path):
                cmd.extend(["-i", audio_path])
            
            # Video encoding settings
            cmd.extend([
                "-c:v", "libx264",
                "-preset", "medium",
                "-crf", "23",
                "-pix_fmt", "yuv420p",
                "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2",
                "-r", "30"
            ])
            
            # Audio encoding settings
            if audio_path and os.path.exists(audio_path):
                cmd.extend([
                    "-c:a", "aac",
                    "-b:a", "128k",
                    "-ar", "44100"
                ])
                # Adjust video duration to match audio if needed
                if duration is None:
                    cmd.extend(["-shortest"])
            else:
                # No audio
                cmd.extend(["-an"])
            
            # Output
            cmd.append(output_path)
            
            # Run ffmpeg
            self.logger.debug(f"Running ffmpeg: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=120
            )
            
            if result.returncode != 0:
                self.logger.error(f"ffmpeg failed: {result.stderr.decode()}")
                raise RuntimeError(f"Video generation failed: {result.stderr.decode()}")
            
            self.logger.info(f"Successfully generated video loop: {output_path}")
            return output_path
            
        except FileNotFoundError:
            self.logger.error("ffmpeg not found. Please install ffmpeg.")
            raise
        except subprocess.TimeoutExpired:
            self.logger.error("Video generation timed out")
            raise
        except Exception as e:
            self.logger.error(f"Error during video generation: {e}")
            raise
    
    def _get_audio_duration(self, audio_path: str) -> int:
        """
        Get duration of audio file in seconds.
        
        Args:
            audio_path: Path to audio file
            
        Returns:
            Duration in seconds (rounded up)
        """
        try:
            cmd = [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                audio_path
            ]
            result = subprocess.run(cmd, capture_output=True, timeout=10)
            duration = float(result.stdout.decode().strip())
            return int(duration) + 1  # Round up
        except Exception as e:
            self.logger.warning(f"Failed to get audio duration: {e}, using default")
            return self.default_duration
    
    def create_loop_with_effects(
        self,
        image_path: str,
        audio_path: Optional[str] = None,
        lower_third_text: Optional[str] = None,
        ticker_text: Optional[str] = None,
        output_path: Optional[str] = None
    ) -> str:
        """
        Create video loop with visual effects overlays.
        
        Args:
            image_path: Path to background image
            audio_path: Path to audio file
            lower_third_text: Text for lower third overlay
            ticker_text: Text for ticker overlay
            output_path: Custom output path
            
        Returns:
            Path to generated video
        """
        # This is a simplified version - full implementation would use
        # ffmpeg complex filters to add text overlays, ticker animation, etc.
        # For now, just use basic make_loop
        self.logger.info("Creating loop with effects (simplified)")
        return self.make_loop(image_path, audio_path, output_path)
