"""
Broadcast Pipeline Module

Main orchestrator for the 24/7 morning show broadcast.
Coordinates RSS monitoring, anchor cycling, and visual rendering.
"""

import logging
import time
from typing import Optional, Dict
from datetime import datetime
import uuid
import subprocess
import shutil
import glob

from rss_monitor import RSSMonitor
from anchor_cycler import AnchorCycler
from visual_renderer import VisualStack
from image_gen import ImageGenerator
from tts_local import LocalTTS
from video_loop import make_loop
import os
import re
from eigentrace import compute_trace_metrics, log_telemetry


class BroadcastState:
    """Enumeration of broadcast states."""
    IDLE = "idle"
    RUNNING = "running"
    BREAKING_NEWS = "breaking_news"
    TRANSITIONING = "transitioning"


class BroadcastPipeline:
    """
    Main 24/7 broadcast pipeline orchestrator.
    
    Manages the complete broadcast lifecycle:
    - RSS monitoring and new story detection
    - Anchor persona cycling
    - Visual rendering and effects
    - Breaking news transitions
    """
    
    def __init__(self, config: Dict):
        """
        Initialize the broadcast pipeline.
        
        Args:
            config: Complete configuration dictionary
        """
        self.config = config
        self.logger = self._setup_logging(config.get('logging', {}))

        broadcast_config = config.get('broadcast', {})
        self.story_duration_seconds = broadcast_config.get('story_duration_seconds', 420)
        self.segment_durations_seconds = broadcast_config.get('segment_durations_seconds', {'anchor_a': 90, 'anchor_b': 60, 'anchor_c': 60, 'roundtable': 210})
        self.intermission_every_stories = broadcast_config.get('intermission_every_stories', 5)
        self.intermission_seconds = broadcast_config.get('intermission_seconds', 33)
        self.intermission_bed_path = broadcast_config.get('intermission_bed_path', '/home/remvelchio/agent/tmp/audio/news_bed.wav')
        self.intermission_announcement = broadcast_config.get('intermission_announcement', 'THIS IS AI NEWS, THE 24 HOUR BREAKING NEWS FEED - PLEASE STAY TUNED')
        self.queue_mode = broadcast_config.get('queue_mode', False)
        self.prebuffer_story_count = broadcast_config.get('prebuffer_story_count', 12)
        self.refresh_threshold = broadcast_config.get('refresh_threshold', 3)
        self.backlog_ready_flag = broadcast_config.get('backlog_ready_flag', '/home/remvelchio/agent/tmp/backlog/READY')
        self.backlog_building = False
        self.last_backlog_log_time = 0
        self.story_start_time = None
        self.story_index = 0
        self.current_phase = "lead"
        self.story_schedule_enabled = True
        self.story_schedule = [
            {"phase": "lead", "anchor": "Anchor A", "duration": self.segment_durations_seconds.get("anchor_a", 60)},
            {"phase": "analysis_b", "anchor": "Anchor B", "duration": self.segment_durations_seconds.get("anchor_b", 60)},
            {"phase": "analysis_c", "anchor": "Anchor C", "duration": self.segment_durations_seconds.get("anchor_c", 60)},
            {"phase": "analysis_d", "anchor": "Anchor D", "duration": self.segment_durations_seconds.get("anchor_d", 60)},
            {"phase": "roundtable", "anchor": "Anchor E", "duration": self.segment_durations_seconds.get("roundtable", 60)},
        ]
        
        # Generate unique episode ID
        self.episode_id = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.logger.info(f"Starting episode {self.episode_id}")
        
        # Initialize components
        rss_config = config.get('rss', {})
        if isinstance(rss_config, list):
            feed_urls = rss_config
            polling_interval = 60
            debounce_timeout = 5
        else:
            feed_urls = rss_config.get('urls') or rss_config.get('url')
            polling_interval = rss_config.get('polling_interval', 60)
            debounce_timeout = rss_config.get('debounce_timeout', 5)

        self.rss_monitor = RSSMonitor(
            feed_urls=feed_urls,
            polling_interval=polling_interval,
            debounce_timeout=debounce_timeout
        )

        anchors_config = config.get('anchors', {})
        self.anchor_cycler = AnchorCycler(
            anchors_config=anchors_config.get('cycle_order', []),
            rotation_interval=anchors_config.get('rotation_interval', 30)
        )
        
        visual_config = config.get('visuals', {})
        self.visual_stack = VisualStack(visual_config, self.episode_id)
        self.image_gen = ImageGenerator(out_dir="/home/remvelchio/agent/tmp/images", device="cuda")
        tts_config = config.get('tts', {})
        self.tts = LocalTTS(
            model_path=tts_config.get('model_path', '/home/remvelchio/agent/models/piper/en_US-lessac-medium.onnx'),
            config_path=tts_config.get('config_path', '/home/remvelchio/agent/models/piper/en_US-lessac-medium.onnx.json'),
            cache_dir=tts_config.get('cache_dir', '/home/remvelchio/agent/tmp/audio'),
            voice_map=tts_config.get('voice_map', {}),
        )
        video_config = config.get('video', {})
        self.video_output_dir = video_config.get('output_dir', '/home/remvelchio/agent/tmp/video')
        self.video_default_duration = video_config.get('default_duration', 6)
        os.makedirs(self.video_output_dir, exist_ok=True)
        self.backlog_audio_dir = str(self.tts.cache_dir)
        self.backlog_video_dir = self.video_output_dir
        os.makedirs(self.backlog_audio_dir, exist_ok=True)
        os.makedirs(self.backlog_video_dir, exist_ok=True)
        if self.backlog_ready_flag:
            os.makedirs(os.path.dirname(self.backlog_ready_flag), exist_ok=True)
        narration_config = config.get('narration', {})
        self.narration_log_path = narration_config.get('log_path', '/home/remvelchio/agent/tmp/scripts/narration.log')
        os.makedirs(os.path.dirname(self.narration_log_path), exist_ok=True)
        self.current_audio_path = None
        self.current_video_path = None
        
        # State tracking
        self.state = BroadcastState.IDLE
        self.current_story: Optional[Dict] = None
        self.last_poll_time = 0
        self.running = False
        self.frame_count = 0
        
        # Performance tracking
        self.stats = {
            'stories_covered': 0,
            'anchor_rotations': 0,
            'frames_rendered': 0,
            'start_time': datetime.now()
        }
    
    def _setup_logging(self, log_config: Dict) -> logging.Logger:
        """Setup logging configuration."""
        logger = logging.getLogger('agente')
        logger.setLevel(getattr(logging, log_config.get('level', 'INFO')))
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # File handler
        if 'file' in log_config:
            file_handler = logging.FileHandler(log_config['file'])
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        
        return logger
    
    def start(self):
        """Start the 24/7 broadcast."""
        self.logger.info("=" * 60)
        self.logger.info("STARTING 24/7 MORNING SHOW BROADCAST")
        self.logger.info(f"Episode ID: {self.episode_id}")
        self.logger.info("=" * 60)
        
        self.running = True
        self.state = BroadcastState.RUNNING
        
        # Initial RSS poll to get first story
        self._poll_rss()
        
        if not self.current_story:
            self.logger.warning("No initial story found, waiting for RSS update...")
    
    def stop(self):
        """Stop the broadcast."""
        self.logger.info("Stopping broadcast...")
        self.running = False
        self.state = BroadcastState.IDLE
        self._log_stats()
    
    def update(self, delta_time: float):
        """
        Main update loop - called each frame.
        
        Args:
            delta_time: Time elapsed since last update in seconds
        """
        if not self.running:
            return
        
        # Check for RSS updates
        current_time = time.time()
        if current_time - self.last_poll_time >= self.rss_monitor.polling_interval:
            self._poll_rss()
            self.last_poll_time = current_time

        # Apply story timing schedule
        self._apply_story_schedule()
        
        # Check for pending stories (debounce completed)
        if self.rss_monitor.has_pending_story():
            pending = self.rss_monitor.get_pending_story()
            if pending:
                self._transition_to_story(pending)

        # If schedule is disabled (waiting for new story), try polling more aggressively
        if not self.story_schedule_enabled and current_time - self.last_poll_time >= 10:
            new_story = self.rss_monitor.check_for_update(force=True)
            if new_story:
                self._transition_to_story(new_story)
            self.last_poll_time = current_time
        
        # Update anchor cycling only if schedule is disabled
        if self.current_story and not self.story_schedule_enabled:
            new_anchor = self.anchor_cycler.update()
            if new_anchor:
                self.stats['anchor_rotations'] += 1
                self.logger.info(f"Anchor rotated to: {new_anchor.name}")
                self._generate_anchor_narration(new_anchor)
        
        # Update visual effects
        self.visual_stack.update(delta_time)
        
        self.frame_count += 1
    
    def render_frame(self) -> Optional[Dict]:
        """
        Render the current broadcast frame.
        
        Returns:
            Frame data dictionary or None if no story active
        """
        if not self.current_story:
            return None
        
        # Get current anchor info
        current_anchor = self.anchor_cycler.get_current_anchor()
        anchor_info = current_anchor.get_lower_third_text(
            self.current_story['title']
        )
        
        # Render complete frame
        frame_data = self.visual_stack.render_frame(
            anchor_info=anchor_info,
            story_title=self.current_story['title']
        )
        
        # Add story and anchor perspective info
        frame_data['story'] = self.current_story
        frame_data['anchor_perspective'] = self.anchor_cycler.get_perspective_text(
            self.current_story
        )
        frame_data['state'] = self.state
        frame_data['frame_number'] = self.frame_count
        frame_data['episode_id'] = self.episode_id
        
        self.stats['frames_rendered'] += 1
        
        return frame_data
    
    def _poll_rss(self, force: bool = False):
        """Poll RSS feed for new stories."""
        new_story = self.rss_monitor.check_for_update(force=force)
        
        if new_story:
            if self.current_story and self.story_start_time:
                elapsed = time.time() - self.story_start_time
                if self.story_duration_seconds and elapsed < self.story_duration_seconds:
                    self.rss_monitor.pending_story = new_story
                    self.logger.info("Deferring new story until current segment completes")
                    return
            self._transition_to_story(new_story)
    
    def _transition_to_story(self, story: Dict):
        """
        Transition to a new story with breaking news effect.
        
        Args:
            story: Story dictionary
        """
        self.logger.info("=" * 60)
        self.logger.info("BREAKING NEWS TRANSITION")
        self.logger.info(f"New Story: {story['title']}")
        self.logger.info("=" * 60)
        
        # Set state to transitioning
        prev_state = self.state
        self.state = BroadcastState.BREAKING_NEWS
        
        # Intermission every N stories
        self.story_index += 1
        if self.intermission_every_stories and self.story_index % self.intermission_every_stories == 0:
            self._enqueue_intermission()

        # Update story
        self.current_story = story
        self.stats['stories_covered'] += 1
        
        self.story_start_time = time.time()
        self.current_phase = "lead"
        self.story_schedule_enabled = True
        self.story_schedule = [
            {"phase": "lead", "anchor": "Anchor A", "duration": self.segment_durations_seconds.get("anchor_a", 60)},
            {"phase": "analysis_b", "anchor": "Anchor B", "duration": self.segment_durations_seconds.get("anchor_b", 60)},
            {"phase": "analysis_c", "anchor": "Anchor C", "duration": self.segment_durations_seconds.get("anchor_c", 60)},
            {"phase": "analysis_d", "anchor": "Anchor D", "duration": self.segment_durations_seconds.get("anchor_d", 60)},
            {"phase": "roundtable", "anchor": "Anchor E", "duration": self.segment_durations_seconds.get("roundtable", 60)},
        ]
        self.anchor_cycler.set_phase("lead")

        self.story_start_time = time.time()
        self.current_phase = "lead"
        self.story_schedule_enabled = True
        self.story_schedule = [
            {"phase": "lead", "anchor": "Anchor A", "duration": self.segment_durations_seconds.get("anchor_a", 60)},
            {"phase": "analysis_b", "anchor": "Anchor B", "duration": self.segment_durations_seconds.get("anchor_b", 60)},
            {"phase": "analysis_c", "anchor": "Anchor C", "duration": self.segment_durations_seconds.get("anchor_c", 60)},
            {"phase": "analysis_d", "anchor": "Anchor D", "duration": self.segment_durations_seconds.get("anchor_d", 60)},
            {"phase": "roundtable", "anchor": "Anchor E", "duration": self.segment_durations_seconds.get("roundtable", 60)},
        ]
        self.anchor_cycler.set_phase("lead")
        self.logger.info("Story schedule started (7 minutes)")

        # Reset anchor cycling for new story
        self.anchor_cycler.start_story(story['guid'])
        
        # Generate image for this story
        try:
            prompt = (
                "split screen newsroom graphic. LEFT SIDE: long shot of five news anchors "
                "sitting at a desk, fully opaque, with distinct colors. RIGHT SIDE: "
                f"newsroom thumbnail graphic style image of: {story['title']}. "
                "high-end broadcast style."
            )
            story_image_path = self.image_gen.generate(prompt, width=1024, height=576, steps=4)
            story["image_url"] = story_image_path
        except Exception as e:
            self.logger.error(f"Image generation failed: {e}")

        # Update visuals
        self.visual_stack.set_story_image(story.get('image_url'))
        self.visual_stack.set_ticker_text(
            f"BREAKING: {story['title']} • Stay tuned for details"
        )

        # Generate initial narration for this story
        current_anchor = self.anchor_cycler.get_current_anchor()
        self._generate_anchor_narration(current_anchor, lead_in=True)
        
        # Simulate breaking news transition duration
        transition_duration = self.config.get('broadcast', {}).get(
            'breaking_news_transition_duration', 2
        )
        time.sleep(transition_duration)
        
        # Return to running state
        self.state = BroadcastState.RUNNING
        
        self.logger.info("Transition complete, resuming normal coverage")
    
    def _apply_story_schedule(self) -> None:
        """Apply the current story schedule for 5-anchor coverage."""
        if not self.current_story or not self.story_start_time:
            return
        if not self.story_schedule_enabled:
            return

        elapsed = time.time() - self.story_start_time
        total_duration = self.story_duration_seconds or sum(s["duration"] for s in self.story_schedule)

        cumulative = 0
        selected = self.story_schedule[-1]
        for segment in self.story_schedule:
            cumulative += segment["duration"]
            if elapsed < cumulative:
                selected = segment
                break

        if self.current_phase != selected["phase"]:
            self.current_phase = selected["phase"]
            self.anchor_cycler.set_phase(self.current_phase)
            anchor = self.anchor_cycler.force_anchor(selected["anchor"])
            self.stats['anchor_rotations'] += 1
            self._generate_anchor_narration(anchor, lead_in=(selected["phase"] == "lead"))

        if elapsed >= total_duration:
            # Story complete. All 5 anchors have spoken. NEVER repeat this story.
            completed_guid = self.current_story.get('guid') if self.current_story else None
            self.logger.info(f"Story complete: {completed_guid}. Finding next story...")

            # 1. Check if a pending story was already deferred
            pending = self.rss_monitor.get_pending_story()
            if pending:
                self._transition_to_story(pending)
                return

            # 2. Force a fresh RSS poll to find something new
            new_story = self.rss_monitor.check_for_update(force=True)
            if new_story:
                self._transition_to_story(new_story)
                return

            # 3. Truly nothing new — mark this story as done and wait
            self.story_schedule_enabled = False
            self.logger.info("No new stories available. Waiting for next RSS poll...")


    def _count_backlog_stories(self) -> int:
        pattern = os.path.join(self.video_output_dir, "story_*.mp4")
        files = [p for p in glob.glob(pattern) if os.path.getsize(p) > 0]
        segments = max(1, len(self.story_schedule))
        return len(files) // segments

    def _mark_backlog_ready(self) -> None:
        if not self.backlog_ready_flag:
            return
        os.makedirs(os.path.dirname(self.backlog_ready_flag), exist_ok=True)
        with open(self.backlog_ready_flag, "w") as f:
            f.write(datetime.now().isoformat())

    def _build_backlog(self, target_count: int) -> None:
        if self.backlog_building:
            return
        self.backlog_building = True
        try:
            while self._count_backlog_stories() < target_count:
                story = self.rss_monitor.check_for_update(force=True)
                if not story:
                    break
                self._queue_story(story)
        finally:
            self.backlog_building = False
        self.last_backlog_log_time = 0


    def _log_backlog_status(self, count: int) -> None:
        now = time.time()
        if now - self.last_backlog_log_time < 60:
            return
        ready = os.path.exists(self.backlog_ready_flag) if self.backlog_ready_flag else False
        audio_count = len(glob.glob(os.path.join(self.backlog_audio_dir, "*.wav")))
        video_count = len(glob.glob(os.path.join(self.backlog_video_dir, "*.mp4")))
        self.logger.info(f"Backlog status: stories={count}, audio={audio_count}, video={video_count}, ready={ready}")
        self.last_backlog_log_time = now

    def _ensure_backlog(self) -> None:
        count = self._count_backlog_stories()
        self._log_backlog_status(count)
        if count <= self.refresh_threshold:
            self.logger.info(f"Backlog low ({count} stories). Rebuilding...")
            self._build_backlog(self.prebuffer_story_count)

    def _queue_story(self, story: Dict) -> None:
        self.story_index += 1
        if self.intermission_every_stories and self.story_index % self.intermission_every_stories == 0:
            self._enqueue_intermission()

        self.current_story = story
        self.stats['stories_covered'] += 1

        self.anchor_cycler.start_story(story['guid'])
        for segment in self.story_schedule:
            self.current_phase = segment["phase"]
            self.anchor_cycler.set_phase(self.current_phase)
            anchor = self.anchor_cycler.force_anchor(segment["anchor"])
            self.stats['anchor_rotations'] += 1
            self._generate_anchor_narration(anchor, lead_in=(segment["phase"] == "lead"))

    def _enqueue_intermission(self) -> None:
        """Create a short intermission bumper video."""
        try:
            ts = datetime.now().strftime('%Y%m%d-%H%M%S')
            announcement = self.intermission_announcement
            audio_path = self.tts.synthesize(announcement, pitch=1.0)

            bed_path = self.intermission_bed_path if os.path.exists(self.intermission_bed_path) else None
            mix_path = audio_path
            if bed_path:
                mix_path = os.path.join(self.backlog_audio_dir, f"intermission_{ts}.wav")
                cmd = [
                    "ffmpeg", "-y",
                    "-stream_loop", "-1", "-i", bed_path,
                    "-i", audio_path,
                    "-filter_complex",
                    f"[0:a]volume=0.35[a0];[1:a]volume=1.0[a1];[a0][a1]amix=inputs=2:duration=shortest,atrim=0:{self.intermission_seconds}",
                    "-t", str(self.intermission_seconds),
                    mix_path
                ]
                subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            image_path = "/home/remvelchio/agent/assets/standby_background.png"
            if not os.path.exists(image_path):
                image_path = "/home/remvelchio/agent/tmp/images/anchors_fallback.svg"

            out_path = os.path.join(self.video_output_dir, f"intermission_{ts}.mp4")
            make_loop(
                image_path=image_path,
                out_path=out_path,
                seconds=self.intermission_seconds,
                fps=30,
                audio_path=mix_path,
                ticker_text="AINN • Stay tuned"
            )
        except Exception as e:
            self.logger.error(f"Intermission generation failed: {e}")

    def _log_narration(self, anchor_name: str, text: str) -> None:
        """Log narration and run EigenTrace quality filter."""
        if not self.narration_log_path:
            return
        ts = datetime.now().isoformat()
        line = f"[{ts}] {anchor_name}: {text}\n"
        try:
            with open(self.narration_log_path, "a") as f:
                f.write(line)
        except Exception as e:
            self.logger.error(f"Failed to write narration log: {e}")

        # EigenTrace Stage 1+2: Score the narration
        try:
            metrics = compute_trace_metrics(text)
            story_title = ""
            if self.current_story:
                story_title = self.current_story.get("title", "")

            entry = log_telemetry(
                anchor_name=anchor_name,
                story_title=story_title,
                text=text,
                metrics=metrics,
            )

            verdict = metrics["status"]
            se = metrics["spectral_entropy"]
            pv = metrics["pulse_variance"]
            pr = metrics["pulse_range"]

            if verdict == "PUBLISHABLE":
                self.logger.info(
                    f"EIGENTRACE Z-PINCH: {anchor_name} | "
                    f"SE={se:.4f} PV={pv:.4f} PR={pr:.4f} | "
                    f"Promoted to Mastodon outbox"
                )
            elif verdict in ("SLOP", "GIBBERISH"):
                self.logger.warning(
                    f"EIGENTRACE {verdict}: {anchor_name} | "
                    f"SE={se:.4f} PV={pv:.4f} PR={pr:.4f} | "
                    f"Reason: {metrics['reason']}"
                )
            else:
                self.logger.debug(
                    f"EIGENTRACE ARCHIVE: {anchor_name} | "
                    f"SE={se:.4f} PV={pv:.4f} PR={pr:.4f}"
                )
        except Exception as e:
            self.logger.error(f"EigenTrace scoring failed: {e}")

    def _generate_anchor_narration(self, anchor, lead_in: bool = False) -> None:
        if not self.current_story:
            return
        try:
            commentary = self.anchor_cycler.get_perspective_text(self.current_story, force_refresh=True)
            text = commentary.get('text') or self.current_story.get('summary') or self.current_story.get('title')
            text = re.sub(r"https?://\S+", "", text).strip()
            if lead_in:
                text = f"And now onto our next story. {text}"
            self._log_narration(anchor.name, text)
            audio_path = self.tts.synthesize(text, pitch=anchor.pitch, voice=anchor.name)
            self.current_audio_path = audio_path
            # Generate a fresh image for this anchor's segment
            try:
                img_prompt = (
                    f"TV news broadcast graphic for: {self.current_story.get('title', '')}. "
                    f"Visual angle: {anchor.focus}. "
                    f"Style: high-end cable news, cinematic, {anchor.perspective.split(';')[0]}. "
                    f"1024x576 broadcast resolution."
                )
                image_path = self.image_gen.generate(img_prompt, width=1024, height=576, steps=4)
                self.current_story['image_url'] = image_path
            except Exception as e:
                self.logger.warning(f"Per-anchor image gen failed: {e}")
                image_path = self.current_story.get('image_url') or "/home/remvelchio/agent/tmp/images/anchors_fallback.svg"
            ts = datetime.now().strftime('%Y%m%d-%H%M%S')
            safe_name = anchor.name.replace(' ', '_')
            out_path = os.path.join(self.video_output_dir, f"story_{ts}_{safe_name}.mp4")
            seconds = None if audio_path else self.video_default_duration
            video_path = make_loop(
                image_path=image_path,
                out_path=out_path,
                seconds=seconds,
                fps=30,
                audio_path=audio_path,
                ticker_text=None,
            )
            self.current_video_path = video_path
        except Exception as e:
            self.logger.error(f"Narration generation failed: {e}")

    def get_status(self) -> Dict:
        """
        Get current broadcast status.
        
        Returns:
            Status dictionary
        """
        status = {
            'episode_id': self.episode_id,
            'state': self.state,
            'running': self.running,
            'current_story': self.current_story['title'] if self.current_story else None,
            'current_anchor': self.anchor_cycler.get_current_anchor().name if self.current_story else None,
            'anchor_stats': self.anchor_cycler.get_stats() if self.current_story else {},
            'stats': self.stats,
            'frame_count': self.frame_count,
            'uptime': (datetime.now() - self.stats['start_time']).total_seconds()
        }
        
        return status
    
    def _log_stats(self):
        """Log broadcast statistics."""
        uptime = (datetime.now() - self.stats['start_time']).total_seconds()
        
        self.logger.info("=" * 60)
        self.logger.info("BROADCAST STATISTICS")
        self.logger.info(f"Episode ID: {self.episode_id}")
        self.logger.info(f"Uptime: {uptime:.1f} seconds")
        self.logger.info(f"Stories covered: {self.stats['stories_covered']}")
        self.logger.info(f"Anchor rotations: {self.stats['anchor_rotations']}")
        self.logger.info(f"Frames rendered: {self.stats['frames_rendered']}")
        if uptime > 0:
            self.logger.info(f"Avg FPS: {self.stats['frames_rendered'] / uptime:.2f}")
        self.logger.info("=" * 60)
