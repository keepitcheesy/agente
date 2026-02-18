"""
Example/Demo Script for Agente 24/7 Broadcast

This script demonstrates the broadcast pipeline with a mock RSS feed
for testing and demonstration purposes.
"""

import yaml
import time
import json
from datetime import datetime
from unittest.mock import Mock, patch
from broadcast_pipeline import BroadcastPipeline


class MockRSSFeed:
    """Mock RSS feed for demonstration."""
    
    def __init__(self):
        self.stories = [
            {
                'id': 'story-1',
                'title': 'Breaking: Major Technology Breakthrough Announced',
                'summary': 'Scientists reveal revolutionary new discovery in quantum computing...',
                'link': 'https://example.com/tech-breakthrough',
                'published': '2026-02-18T10:00:00Z'
            },
            {
                'id': 'story-2',
                'title': 'Global Markets React to Policy Changes',
                'summary': 'Stock markets worldwide show mixed reactions to new regulations...',
                'link': 'https://example.com/markets',
                'published': '2026-02-18T10:15:00Z'
            },
            {
                'id': 'story-3',
                'title': 'Climate Summit Reaches Landmark Agreement',
                'summary': 'World leaders agree on ambitious new climate targets...',
                'link': 'https://example.com/climate',
                'published': '2026-02-18T10:30:00Z'
            }
        ]
        self.current_index = 0
    
    def get_next_story(self):
        """Get the next story in sequence."""
        if self.current_index >= len(self.stories):
            return None
        
        story = self.stories[self.current_index]
        self.current_index += 1
        return story


def create_demo_config():
    """Create configuration for demo."""
    return {
        'rss': {
            'url': 'https://example.com/demo-feed',
            'polling_interval': 15,  # Faster for demo
            'debounce_timeout': 3    # Shorter for demo
        },
        'anchors': {
            'cycle_order': [
                {
                    'name': 'Anchor A',
                    'focus': 'headline/facts',
                    'perspective': 'What happened and when',
                    'color': '#FF0000'
                },
                {
                    'name': 'Anchor B',
                    'focus': 'implications',
                    'perspective': 'Why it matters and what comes next',
                    'color': '#0000FF'
                },
                {
                    'name': 'Anchor C',
                    'focus': 'context',
                    'perspective': 'Background and historical perspective',
                    'color': '#00FF00'
                }
            ],
            'rotation_interval': 10  # Faster rotation for demo
        },
        'visuals': {
            'lower_third': {
                'enabled': True,
                'update_per_anchor': True,
                'height': 120,
                'font_size': 18
            },
            'ticker': {
                'enabled': True,
                'speed': 2,
                'height': 40,
                'font_size': 14
            },
            'live_tag': {
                'enabled': True,
                'position': 'top-left',
                'show_timestamp': True,
                'show_episode_id': True
            },
            'story_image': {
                'pan_zoom_enabled': True,
                'pan_speed': 0.5,
                'zoom_factor': 1.1,
                'duration': 120
            }
        },
        'broadcast': {
            'mode': '24/7',
            'breaking_news_transition_duration': 1
        },
        'logging': {
            'level': 'INFO',
            'file': 'demo.log'
        }
    }


def run_demo(duration_seconds=60):
    """
    Run a demonstration of the broadcast pipeline.
    
    Args:
        duration_seconds: How long to run the demo
    """
    print("=" * 70)
    print("AGENTE 24/7 MORNING SHOW BROADCAST - DEMO MODE")
    print("=" * 70)
    print()
    
    # Create mock RSS feed
    mock_feed = MockRSSFeed()
    
    # Create configuration
    config = create_demo_config()
    
    # Create pipeline
    pipeline = BroadcastPipeline(config)
    
    # Mock the RSS monitor's poll_feed method
    story_release_times = [0, 20, 40]  # Release stories at these times
    start_time = time.time()
    
    def mock_poll_feed():
        """Mock RSS polling that releases stories over time."""
        elapsed = time.time() - start_time
        
        for release_time in story_release_times:
            if (elapsed >= release_time and 
                mock_feed.current_index < len(mock_feed.stories) and
                mock_feed.current_index == story_release_times.index(release_time)):
                
                story_entry = mock_feed.get_next_story()
                if story_entry and story_entry['id'] != pipeline.rss_monitor.last_story_guid:
                    return pipeline.rss_monitor._parse_entry(story_entry)
        
        return None
    
    # Replace poll_feed with our mock
    pipeline.rss_monitor.poll_feed = mock_poll_feed
    
    # Start the pipeline
    pipeline.start()
    
    print(f"Demo will run for {duration_seconds} seconds")
    print("Watch as stories arrive and anchors rotate through perspectives!")
    print()
    print("Legend:")
    print("  [NEW STORY] = Breaking news transition")
    print("  [ANCHOR ROTATION] = Perspective change")
    print("  [FRAME] = Regular update")
    print()
    
    # Main demo loop
    end_time = time.time() + duration_seconds
    frame_count = 0
    last_anchor = None
    last_story = None
    
    try:
        while time.time() < end_time and pipeline.running:
            # Update pipeline
            pipeline.update(0.033)  # ~30 FPS
            
            # Render frame
            frame = pipeline.render_frame()
            
            if frame:
                # Check for story change
                current_story = frame['story']['title']
                if current_story != last_story:
                    print()
                    print("🔴 " + "=" * 65)
                    print(f"🔴 [BREAKING NEWS] {current_story}")
                    print("🔴 " + "=" * 65)
                    last_story = current_story
                
                # Check for anchor rotation
                current_anchor = frame['anchor_perspective']['anchor']
                if current_anchor != last_anchor:
                    print()
                    print(f"📺 [ANCHOR ROTATION] → {current_anchor}")
                    print(f"   Focus: {frame['anchor_perspective']['focus']}")
                    print(f"   Perspective: {frame['anchor_perspective']['perspective']}")
                    last_anchor = current_anchor
                
                # Show frame data periodically
                if frame_count % 150 == 0:  # Every ~5 seconds
                    print(f"\n   [FRAME {frame_count}]")
                    print(f"   Episode: {frame['episode_id']}")
                    print(f"   State: {frame['state']}")
                    print(f"   Visual Stack:")
                    print(f"     - Lower Third: {frame['lower_third']['text']}")
                    print(f"     - LIVE Tag: {frame['live_tag']['display_text']}")
                    print(f"     - Ticker: {frame['ticker']['text'][:50]}...")
                    if frame['story_image']['image_url']:
                        print(f"     - Image: Pan({frame['story_image']['pan_x']:.1f}, "
                              f"{frame['story_image']['pan_y']:.1f}) "
                              f"Zoom({frame['story_image']['zoom']:.2f}x)")
            
            frame_count += 1
            time.sleep(0.033)  # ~30 FPS
    
    except KeyboardInterrupt:
        print("\n\nDemo interrupted by user")
    
    # Stop pipeline
    pipeline.stop()
    
    # Show final statistics
    print()
    print("=" * 70)
    print("DEMO COMPLETE")
    print("=" * 70)
    
    status = pipeline.get_status()
    print(f"\nFinal Statistics:")
    print(f"  Episode ID: {status['episode_id']}")
    print(f"  Stories Covered: {status['stats']['stories_covered']}")
    print(f"  Anchor Rotations: {status['stats']['anchor_rotations']}")
    print(f"  Frames Rendered: {status['stats']['frames_rendered']}")
    print(f"  Uptime: {status['uptime']:.1f} seconds")
    print(f"  Average FPS: {status['stats']['frames_rendered'] / status['uptime']:.1f}")
    print()
    print("Check demo.log for detailed logs!")
    print()


if __name__ == '__main__':
    import sys
    
    duration = 60  # Default 60 seconds
    if len(sys.argv) > 1:
        try:
            duration = int(sys.argv[1])
        except ValueError:
            print(f"Invalid duration: {sys.argv[1]}, using default {duration}s")
    
    run_demo(duration)
