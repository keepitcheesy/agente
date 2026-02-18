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

from rss_monitor import RSSMonitor
from anchor_cycler import AnchorCycler
from visual_renderer import VisualStack


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
        
        # Generate unique episode ID
        self.episode_id = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.logger.info(f"Starting episode {self.episode_id}")
        
        # Initialize components
        rss_config = config.get('rss', {})
        self.rss_monitor = RSSMonitor(
            feed_url=rss_config.get('url'),
            polling_interval=rss_config.get('polling_interval', 60),
            debounce_timeout=rss_config.get('debounce_timeout', 5)
        )
        
        anchors_config = config.get('anchors', {})
        self.anchor_cycler = AnchorCycler(
            anchors_config=anchors_config.get('cycle_order', []),
            rotation_interval=anchors_config.get('rotation_interval', 30)
        )
        
        visual_config = config.get('visuals', {})
        self.visual_stack = VisualStack(visual_config, self.episode_id)
        
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
        
        # Check for pending stories (debounce completed)
        if self.rss_monitor.has_pending_story():
            pending = self.rss_monitor.get_pending_story()
            if pending:
                self._transition_to_story(pending)
        
        # Update anchor cycling
        if self.current_story:
            new_anchor = self.anchor_cycler.update()
            if new_anchor:
                self.stats['anchor_rotations'] += 1
                self.logger.info(f"Anchor rotated to: {new_anchor.name}")
        
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
    
    def _poll_rss(self):
        """Poll RSS feed for new stories."""
        new_story = self.rss_monitor.check_for_update()
        
        if new_story:
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
        
        # Update story
        self.current_story = story
        self.stats['stories_covered'] += 1
        
        # Reset anchor cycling for new story
        self.anchor_cycler.start_story(story['guid'])
        
        # Update visuals
        self.visual_stack.set_story_image(story.get('image_url'))
        self.visual_stack.set_ticker_text(
            f"BREAKING: {story['title']} • Stay tuned for details"
        )
        
        # Simulate breaking news transition duration
        transition_duration = self.config.get('broadcast', {}).get(
            'breaking_news_transition_duration', 2
        )
        time.sleep(transition_duration)
        
        # Return to running state
        self.state = BroadcastState.RUNNING
        
        self.logger.info("Transition complete, resuming normal coverage")
    
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
