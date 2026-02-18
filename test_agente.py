"""
Unit tests for the Agente 24/7 Morning Show Broadcast system.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import time

from rss_monitor import RSSMonitor
from anchor_cycler import AnchorCycler, AnchorPersona
from visual_renderer import VisualStack, LowerThird, Ticker, LiveTag
from broadcast_pipeline import BroadcastPipeline


class TestRSSMonitor(unittest.TestCase):
    """Test RSS monitoring and debouncing."""
    
    def setUp(self):
        self.monitor = RSSMonitor(
            feed_url="https://example.com/feed",
            polling_interval=60,
            debounce_timeout=5
        )
    
    def test_initialization(self):
        """Test RSS monitor initialization."""
        self.assertEqual(self.monitor.feed_url, "https://example.com/feed")
        self.assertEqual(self.monitor.polling_interval, 60)
        self.assertEqual(self.monitor.debounce_timeout, 5)
        self.assertIsNone(self.monitor.last_story_guid)
    
    def test_parse_entry(self):
        """Test RSS entry parsing."""
        mock_entry = {
            'id': 'story-123',
            'title': 'Test Story',
            'summary': 'This is a test',
            'link': 'https://example.com/story',
            'published': '2026-02-18T12:00:00Z'
        }
        
        story = self.monitor._parse_entry(mock_entry)
        
        self.assertEqual(story['guid'], 'story-123')
        self.assertEqual(story['title'], 'Test Story')
        self.assertEqual(story['summary'], 'This is a test')
        self.assertEqual(story['link'], 'https://example.com/story')
    
    @patch('rss_monitor.feedparser.parse')
    def test_poll_feed_new_story(self, mock_parse):
        """Test detecting new story from feed."""
        mock_parse.return_value = Mock(
            entries=[{
                'id': 'new-story',
                'title': 'New Story',
                'summary': 'Breaking news',
                'link': 'https://example.com/new'
            }]
        )
        
        story = self.monitor.poll_feed()
        
        self.assertIsNotNone(story)
        self.assertEqual(story['guid'], 'new-story')
        self.assertEqual(story['title'], 'New Story')
    
    @patch('rss_monitor.feedparser.parse')
    def test_poll_feed_no_new_story(self, mock_parse):
        """Test when no new story is available."""
        # Set existing story
        self.monitor.last_story_guid = 'existing-story'
        
        mock_parse.return_value = Mock(
            entries=[{
                'id': 'existing-story',
                'title': 'Old Story',
                'summary': 'Already seen',
                'link': 'https://example.com/old'
            }]
        )
        
        story = self.monitor.poll_feed()
        
        self.assertIsNone(story)
    
    def test_debouncing(self):
        """Test debounce prevents rapid story switching."""
        # Simulate first update
        self.monitor.last_update_time = datetime.now()
        self.monitor.last_story_guid = 'story-1'
        
        # Create a new story
        new_story = {
            'guid': 'story-2',
            'title': 'Story 2',
            'summary': 'New story',
            'link': 'https://example.com/2'
        }
        
        # Mock poll_feed to return new story
        with patch.object(self.monitor, 'poll_feed', return_value=new_story):
            # Should be blocked by debounce
            result = self.monitor.check_for_update()
            self.assertIsNone(result)
            self.assertIsNotNone(self.monitor.pending_story)


class TestAnchorCycler(unittest.TestCase):
    """Test anchor persona cycling."""
    
    def setUp(self):
        self.anchors_config = [
            {'name': 'Anchor A', 'focus': 'headline/facts', 
             'perspective': 'What happened', 'color': '#FF0000'},
            {'name': 'Anchor B', 'focus': 'implications', 
             'perspective': 'Why it matters', 'color': '#0000FF'},
            {'name': 'Anchor C', 'focus': 'context', 
             'perspective': 'Background', 'color': '#00FF00'}
        ]
        self.cycler = AnchorCycler(
            anchors_config=self.anchors_config,
            rotation_interval=30
        )
    
    def test_initialization(self):
        """Test anchor cycler initialization."""
        self.assertEqual(len(self.cycler.anchors), 3)
        self.assertEqual(self.cycler.rotation_interval, 30)
        self.assertEqual(self.cycler.current_anchor_index, 0)
    
    def test_start_story(self):
        """Test starting a new story."""
        self.cycler.start_story('story-123')
        
        self.assertEqual(self.cycler.current_story_guid, 'story-123')
        self.assertEqual(self.cycler.current_anchor_index, 0)
        self.assertEqual(self.cycler.rotation_count, 0)
    
    def test_anchor_rotation(self):
        """Test rotating through anchors."""
        self.cycler.start_story('story-123')
        
        # First anchor should be A
        anchor = self.cycler.get_current_anchor()
        self.assertEqual(anchor.name, 'Anchor A')
        
        # Rotate to B
        anchor = self.cycler.rotate()
        self.assertEqual(anchor.name, 'Anchor B')
        self.assertEqual(self.cycler.rotation_count, 1)
        
        # Rotate to C
        anchor = self.cycler.rotate()
        self.assertEqual(anchor.name, 'Anchor C')
        
        # Rotate back to A (cycle complete)
        anchor = self.cycler.rotate()
        self.assertEqual(anchor.name, 'Anchor A')
        self.assertEqual(self.cycler.rotation_count, 3)
    
    def test_should_rotate(self):
        """Test rotation timing."""
        self.cycler.start_story('story-123')
        
        # Immediately after start, should not rotate
        self.assertFalse(self.cycler.should_rotate())
        
        # Simulate time passing
        self.cycler.last_rotation_time = datetime.now() - timedelta(seconds=35)
        self.assertTrue(self.cycler.should_rotate())
    
    def test_perspective_generation(self):
        """Test perspective text generation."""
        story = {
            'title': 'Breaking: Major Event Happens',
            'summary': 'Details about the event...'
        }
        
        self.cycler.start_story('story-123')
        
        # Test headline perspective (Anchor A)
        perspective = self.cycler.get_perspective_text(story)
        self.assertIn('Here\'s what happened', perspective['text'])
        
        # Rotate and test implications (Anchor B)
        self.cycler.rotate()
        perspective = self.cycler.get_perspective_text(story)
        self.assertIn('Why this matters', perspective['text'])


class TestVisualStack(unittest.TestCase):
    """Test visual rendering components."""
    
    def setUp(self):
        self.config = {
            'lower_third': {'enabled': True, 'height': 120},
            'ticker': {'enabled': True, 'speed': 2},
            'live_tag': {'enabled': True, 'position': 'top-left'},
            'story_image': {'pan_zoom_enabled': True}
        }
        self.visual_stack = VisualStack(self.config, 'EP-12345')
    
    def test_lower_third_rendering(self):
        """Test lower third rendering."""
        anchor_info = {
            'anchor_name': 'Anchor A',
            'focus': 'headline/facts',
            'color': '#FF0000'
        }
        
        result = self.visual_stack.lower_third.render(anchor_info, 'Test Story')
        
        self.assertTrue(result['enabled'])
        self.assertEqual(result['anchor_name'], 'Anchor A')
        self.assertEqual(result['focus'], 'headline/facts')
    
    def test_ticker_update(self):
        """Test ticker position updates."""
        initial_pos = self.visual_stack.ticker.position
        
        self.visual_stack.ticker.update(1.0)  # 1 second
        
        self.assertGreater(self.visual_stack.ticker.position, initial_pos)
    
    def test_live_tag_rendering(self):
        """Test LIVE tag rendering."""
        result = self.visual_stack.live_tag.render()
        
        self.assertTrue(result['enabled'])
        self.assertEqual(result['text'], 'LIVE')
        self.assertIsNotNone(result['timestamp'])
        self.assertIn('EP-12345', result['display_text'])
    
    def test_story_image_pan_zoom(self):
        """Test story image pan/zoom effects."""
        self.visual_stack.story_image.start_image('https://example.com/image.jpg')
        
        initial_zoom = self.visual_stack.story_image.current_zoom
        
        # Simulate time passing
        self.visual_stack.story_image.update(10.0)
        
        # Zoom should have changed
        self.assertNotEqual(self.visual_stack.story_image.current_zoom, initial_zoom)


class TestBroadcastPipeline(unittest.TestCase):
    """Test the complete broadcast pipeline."""
    
    def setUp(self):
        self.config = {
            'rss': {
                'url': 'https://example.com/feed',
                'polling_interval': 60,
                'debounce_timeout': 5
            },
            'anchors': {
                'cycle_order': [
                    {'name': 'Anchor A', 'focus': 'headline/facts',
                     'perspective': 'What happened', 'color': '#FF0000'}
                ],
                'rotation_interval': 30
            },
            'visuals': {
                'lower_third': {'enabled': True},
                'ticker': {'enabled': True},
                'live_tag': {'enabled': True},
                'story_image': {'pan_zoom_enabled': True}
            },
            'broadcast': {
                'mode': '24/7',
                'breaking_news_transition_duration': 2
            },
            'logging': {
                'level': 'ERROR'  # Suppress logs during tests
            }
        }
    
    def test_pipeline_initialization(self):
        """Test pipeline initialization."""
        pipeline = BroadcastPipeline(self.config)
        
        self.assertIsNotNone(pipeline.episode_id)
        self.assertIsNotNone(pipeline.rss_monitor)
        self.assertIsNotNone(pipeline.anchor_cycler)
        self.assertIsNotNone(pipeline.visual_stack)
    
    def test_pipeline_start_stop(self):
        """Test starting and stopping the pipeline."""
        pipeline = BroadcastPipeline(self.config)
        
        pipeline.start()
        self.assertTrue(pipeline.running)
        
        pipeline.stop()
        self.assertFalse(pipeline.running)
    
    def test_status_reporting(self):
        """Test status reporting."""
        pipeline = BroadcastPipeline(self.config)
        pipeline.start()
        
        status = pipeline.get_status()
        
        self.assertIn('episode_id', status)
        self.assertIn('state', status)
        self.assertIn('stats', status)
        self.assertIn('uptime', status)
        
        pipeline.stop()


def run_tests():
    """Run all tests."""
    unittest.main(argv=[''], verbosity=2, exit=False)


if __name__ == '__main__':
    run_tests()
