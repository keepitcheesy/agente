"""
RSS Feed Monitor Module

This module handles polling RSS feeds, detecting new items,
and implementing debouncing logic to prevent rapid story switching.
"""

import feedparser
import time
import logging
from typing import Optional, Dict, List
from datetime import datetime, timedelta


class RSSMonitor:
    """
    Monitors an RSS feed for new items with debouncing.
    
    Implements event-driven behavior where new RSS items trigger
    story updates, with debouncing to prevent rapid switching.
    """
    
    def __init__(self, feed_url: str, polling_interval: int = 60, 
                 debounce_timeout: int = 5):
        """
        Initialize the RSS monitor.
        
        Args:
            feed_url: URL of the RSS feed to monitor
            polling_interval: Seconds between feed checks
            debounce_timeout: Minimum seconds between story transitions
        """
        self.feed_url = feed_url
        self.polling_interval = polling_interval
        self.debounce_timeout = debounce_timeout
        self.logger = logging.getLogger(__name__)
        
        # State tracking
        self.last_story_guid: Optional[str] = None
        self.last_update_time: Optional[datetime] = None
        self.current_story: Optional[Dict] = None
        self.pending_story: Optional[Dict] = None
        
    def poll_feed(self) -> Optional[Dict]:
        """
        Poll the RSS feed for updates.
        
        Returns:
            Latest story dict if new item found, None otherwise
        """
        try:
            self.logger.info(f"Polling RSS feed: {self.feed_url}")
            feed = feedparser.parse(self.feed_url)
            
            if not feed.entries:
                self.logger.warning("No entries found in feed")
                return None
            
            latest_entry = feed.entries[0]
            latest_guid = latest_entry.get('id') or latest_entry.get('link')
            
            # Check if this is a new story
            if latest_guid != self.last_story_guid:
                story = self._parse_entry(latest_entry)
                self.logger.info(f"New story detected: {story['title']}")
                return story
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error polling RSS feed: {e}")
            return None
    
    def check_for_update(self) -> Optional[Dict]:
        """
        Check for new story update with debouncing.
        
        Returns:
            New story if available and debounce period has passed,
            None otherwise
        """
        new_story = self.poll_feed()
        
        if new_story is None:
            return None
        
        # Check debounce timeout
        now = datetime.now()
        if self.last_update_time:
            time_since_last = (now - self.last_update_time).total_seconds()
            if time_since_last < self.debounce_timeout:
                self.logger.info(
                    f"Debouncing: {time_since_last:.1f}s since last update "
                    f"(minimum: {self.debounce_timeout}s)"
                )
                # Store as pending
                self.pending_story = new_story
                return None
        
        # Update is ready
        self.last_story_guid = new_story['guid']
        self.last_update_time = now
        self.current_story = new_story
        self.pending_story = None
        
        return new_story
    
    def has_pending_story(self) -> bool:
        """Check if there's a pending story waiting for debounce."""
        return self.pending_story is not None
    
    def get_pending_story(self) -> Optional[Dict]:
        """
        Get pending story if debounce period has passed.
        
        Returns:
            Pending story if ready, None otherwise
        """
        if not self.pending_story:
            return None
        
        now = datetime.now()
        if self.last_update_time:
            time_since_last = (now - self.last_update_time).total_seconds()
            if time_since_last >= self.debounce_timeout:
                story = self.pending_story
                self.last_story_guid = story['guid']
                self.last_update_time = now
                self.current_story = story
                self.pending_story = None
                return story
        
        return None
    
    def _parse_entry(self, entry) -> Dict:
        """
        Parse an RSS entry into a standardized story format.
        
        Args:
            entry: feedparser entry object
            
        Returns:
            Dictionary with story information
        """
        return {
            'guid': entry.get('id') or entry.get('link'),
            'title': entry.get('title', 'Untitled'),
            'summary': entry.get('summary', ''),
            'link': entry.get('link', ''),
            'published': entry.get('published', ''),
            'published_parsed': entry.get('published_parsed'),
            'image_url': self._extract_image_url(entry),
            'timestamp': datetime.now().isoformat()
        }
    
    def _extract_image_url(self, entry) -> Optional[str]:
        """Extract image URL from RSS entry."""
        # Try media:content
        if hasattr(entry, 'media_content'):
            for media in entry.media_content:
                if media.get('type', '').startswith('image/'):
                    return media.get('url')
        
        # Try enclosures
        if hasattr(entry, 'enclosures'):
            for enclosure in entry.enclosures:
                if enclosure.get('type', '').startswith('image/'):
                    return enclosure.get('href')
        
        # Try media:thumbnail
        if hasattr(entry, 'media_thumbnail'):
            if entry.media_thumbnail:
                return entry.media_thumbnail[0].get('url')
        
        return None
