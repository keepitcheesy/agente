#!/usr/bin/env python
"""
Demo script showing the new TTS and video integration features.

This demo simulates a short broadcast session with:
- Multiple anchor rotations
- Narration logging
- TTS audio generation (if available)
- Video loop generation (if available)
- Dynamic ticker updates
"""

import yaml
import time
import os
from datetime import datetime
from broadcast_pipeline import BroadcastPipeline


def create_demo_config():
    """Create a demo configuration with TTS/video enabled."""
    return {
        'rss': {
            'url': 'https://rss.example.com/feed.xml',
            'polling_interval': 30,
            'debounce_timeout': 3
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
            'rotation_interval': 10  # Quick rotations for demo
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
        'tts': {
            'cache_dir': '/tmp/demo_tts_cache',
            'model': 'en_US-lessac-medium'
        },
        'video': {
            'output_dir': '/tmp/demo_video_loops',
            'default_duration': 30
        },
        'narration': {
            'log_path': '/tmp/demo_narration.log'
        },
        'logging': {
            'level': 'INFO',
            'file': 'demo_tts_video.log'
        }
    }


def mock_story():
    """Create a mock story for demonstration."""
    return {
        'guid': 'demo-story-001',
        'title': 'Major Technology Breakthrough Announced',
        'summary': 'Scientists reveal revolutionary new discovery in quantum computing that could transform the industry.',
        'link': 'https://example.com/tech-breakthrough',
        'published': datetime.now().isoformat(),
        'image_url': None
    }


def print_separator(title=""):
    """Print a formatted separator."""
    if title:
        print(f"\n{'=' * 60}")
        print(f"  {title}")
        print('=' * 60)
    else:
        print('-' * 60)


def main():
    """Run the demo."""
    print("\n" + "=" * 60)
    print("AGENTE TTS & VIDEO INTEGRATION DEMO")
    print("=" * 60)
    print("\nThis demo shows the new features:")
    print("  ✓ Narration logging with timestamp")
    print("  ✓ Piper TTS audio generation")
    print("  ✓ Video loop creation with audio")
    print("  ✓ Dynamic ticker updates per anchor")
    print("\nNote: TTS/video will fall back gracefully if dependencies are missing.")
    
    # Create configuration
    config = create_demo_config()
    
    print_separator("INITIALIZING PIPELINE")
    pipeline = BroadcastPipeline(config)
    
    print(f"\nConfiguration:")
    print(f"  Narration log: {pipeline.narration_log_path}")
    print(f"  TTS cache: {pipeline.tts.cache_dir}")
    print(f"  Video output: {pipeline.video_loop_generator.output_dir}")
    
    # Start pipeline
    print_separator("STARTING BROADCAST")
    pipeline.start()
    
    # Simulate a story
    print("\nSimulating story arrival...")
    story = mock_story()
    pipeline.current_story = story
    pipeline.stats['stories_covered'] += 1
    
    # Initialize anchor cycling
    pipeline.anchor_cycler.start_story(story['guid'])
    pipeline.visual_stack.set_story_image(None)
    pipeline.visual_stack.set_ticker_text(f"BREAKING: {story['title']}")
    
    # Generate initial narration
    print(f"\n📰 Story: {story['title']}")
    current_anchor = pipeline.anchor_cycler.get_current_anchor()
    print(f"📺 Initial Anchor: {current_anchor.name} ({current_anchor.focus})")
    
    pipeline._generate_anchor_narration(current_anchor)
    
    # Show ticker
    ticker_data = pipeline.visual_stack.ticker.render(pipeline.visual_stack.ticker_text)
    print(f"📊 Ticker: {ticker_data['text'][:80]}...")
    
    # Simulate 2 anchor rotations
    for i in range(2):
        print_separator(f"ANCHOR ROTATION #{i+1}")
        time.sleep(1)  # Brief pause
        
        # Force rotation
        new_anchor = pipeline.anchor_cycler.rotate()
        pipeline.stats['anchor_rotations'] += 1
        
        print(f"\n📺 Rotated to: {new_anchor.name}")
        print(f"   Focus: {new_anchor.focus}")
        print(f"   Perspective: {new_anchor.perspective}")
        
        # Generate narration
        pipeline._generate_anchor_narration(new_anchor)
        
        # Show updated ticker
        ticker_data = pipeline.visual_stack.ticker.render(pipeline.visual_stack.ticker_text)
        print(f"📊 Updated Ticker: {ticker_data['text'][:80]}...")
        
        # Show audio/video paths if generated
        if pipeline.current_audio_path:
            print(f"🔊 Audio: {pipeline.current_audio_path}")
        if pipeline.current_video_path:
            print(f"🎬 Video: {pipeline.current_video_path}")
    
    # Stop pipeline
    print_separator("STOPPING BROADCAST")
    pipeline.stop()
    
    # Show statistics
    print_separator("RESULTS")
    print("\nBroadcast Statistics:")
    print(f"  Stories covered: {pipeline.stats['stories_covered']}")
    print(f"  Anchor rotations: {pipeline.stats['anchor_rotations']}")
    
    # Show narration log
    print("\nNarration Log Contents:")
    print_separator()
    if os.path.exists(pipeline.narration_log_path):
        with open(pipeline.narration_log_path, 'r') as f:
            print(f.read())
    else:
        print("  (No narration log file created)")
    
    print_separator()
    print("\n✓ Demo completed successfully!")
    print("\nGenerated files:")
    print(f"  - Narration log: {pipeline.narration_log_path}")
    print(f"  - Broadcast log: demo_tts_video.log")
    print(f"  - TTS cache: {pipeline.tts.cache_dir}")
    print(f"  - Video loops: {pipeline.video_loop_generator.output_dir}")
    print("\nCheck these locations to see the outputs.\n")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nDemo interrupted by user")
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()
