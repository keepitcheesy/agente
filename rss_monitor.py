"""
RSS Feed Monitor Module

This module handles polling RSS feeds, detecting new items,
and implementing debouncing logic to prevent rapid story switching.
"""

import feedparser
import time
import logging
from typing import Optional, Dict, List, Union
from datetime import datetime


class RSSMonitor:
    """
    Monitors one or more RSS feeds for new items with debouncing.

    Implements event-driven behavior where new RSS items trigger
    story updates, with debouncing to prevent rapid switching.
    """

    def __init__(self, feed_urls: Union[str, List[str]], polling_interval: int = 60,
                 debounce_timeout: int = 5):
        """
        Initialize the RSS monitor.

        Args:
            feed_urls: URL or list of URLs of RSS feeds to monitor
            polling_interval: Seconds between feed checks
            debounce_timeout: Minimum seconds between story transitions
        """
        self.feed_urls = self._normalize_urls(feed_urls)
        self.polling_interval = polling_interval
        self.debounce_timeout = debounce_timeout
        self.logger = logging.getLogger(__name__)

        # State tracking
        self.last_story_guid: Optional[str] = None
        self.last_update_time: Optional[datetime] = None
        self.current_story: Optional[Dict] = None
        self.pending_story: Optional[Dict] = None

    def _normalize_urls(self, feed_urls: Union[str, List[str]]) -> List[str]:
        if isinstance(feed_urls, str):
            return [feed_urls]
        if isinstance(feed_urls, list):
            return [u for u in feed_urls if u]
        return []

    def _entry_timestamp(self, entry: Dict) -> float:
        if entry.get('published_parsed'):
            return time.mktime(entry.published_parsed)
        if entry.get('updated_parsed'):
            return time.mktime(entry.updated_parsed)
        return time.time()

    def poll_feed(self) -> Optional[Dict]:
        """
        Poll all RSS feeds for updates.

        Returns:
            Latest story dict if new item found, None otherwise
        """
        try:
            if not self.feed_urls:
                self.logger.warning("No RSS feed URLs configured")
                return None

            latest_entry = None
            latest_time = 0.0

            for url in self.feed_urls:
                self.logger.info(f"Polling RSS feed: {url}")
                feed = feedparser.parse(url)
                if not feed.entries:
                    self.logger.warning(f"No entries found in feed: {url}")
                    continue

                entry = feed.entries[0]
                entry_time = self._entry_timestamp(entry)
                if entry_time > latest_time:
                    latest_time = entry_time
                    latest_entry = entry

            if not latest_entry:
                return None

            latest_guid = latest_entry.get('id') or latest_entry.get('link')

            if latest_guid != self.last_story_guid:
                story = self._parse_entry(latest_entry)
                self.logger.info(f"New story detected: {story['title']}")
                return story

            return None

        except Exception as e:
            self.logger.error(f"Error polling RSS feeds: {e}")
            return None

    def check_for_update(self) -> Optional[Dict]:
        new_story = self.poll_feed()

        if new_story is None:
            return None

        now = datetime.now()
        if self.last_update_time:
            time_since_last = (now - self.last_update_time).total_seconds()
            if time_since_last < self.debounce_timeout:
                self.logger.info(
                    f"Debouncing: {time_since_last:.1f}s since last update "
                    f"(minimum: {self.debounce_timeout}s)"
                )
                self.pending_story = new_story
                return None

        self.last_story_guid = new_story['guid']
        self.last_update_time = now
        self.current_story = new_story
        self.pending_story = None

        return new_story

    def has_pending_story(self) -> bool:
        return self.pending_story is not None

    def get_pending_story(self) -> Optional[Dict]:
        if not self.pending_story:
            return None

        now = datetime.now()
        if self.last_update_time:
            time_since_last = (now - self.last_update_time).total_seconds()
            if time_since_last >= self.debounce_timeout:
                story = self.pending_story
                self.pending_story = None
                self.last_story_guid = story['guid']
                self.last_update_time = now
                self.current_story = story
                return story

        return None

    def _parse_entry(self, entry: Dict) -> Dict:
        return {
            'guid': entry.get('id') or entry.get('link'),
            'title': entry.get('title', 'Untitled'),
            'summary': entry.get('summary', ''),
            'link': entry.get('link', ''),
            'published': entry.get('published', ''),
            'source': entry.get('source', {}).get('title', 'Unknown')
        }
