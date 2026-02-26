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


import hashlib
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

_TRACKING_KEYS = {
    "utm_source","utm_medium","utm_campaign","utm_term","utm_content",
    "utm_id","gclid","fbclid","mc_cid","mc_eid","ref","ref_src"
}

def canonicalize_url(url: str) -> str:
    if not url:
        return ""
    u = url.strip()
    try:
        p = urlparse(u)
        scheme = (p.scheme or "https").lower()
        netloc = (p.netloc or "").lower()
        path = p.path or ""
        q = [(k, v) for (k, v) in parse_qsl(p.query, keep_blank_values=True) if k.lower() not in _TRACKING_KEYS]
        query = urlencode(q, doseq=True)
        return urlunparse((scheme, netloc, path, "", query, ""))  # drop fragment
    except Exception:
        return u

def compute_guid(entry: dict) -> str:
    guid = (entry.get("guid") or entry.get("id") or "").strip()
    if guid:
        return guid

    link = canonicalize_url((entry.get("link") or "").strip())
    if link:
        return link

    title = (entry.get("title") or "").strip()
    published = (entry.get("published") or entry.get("updated") or "").strip()
    blob = (title + "|" + published).encode("utf-8", errors="ignore")
    return "hash:" + hashlib.sha1(blob).hexdigest()


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
        self.seen_guids: set = set()
        self.last_update_time: Optional[datetime] = None
        self.current_story: Optional[Dict] = None
        self.pending_story: Optional[Dict] = None
        self.last_accepted_timestamp: Optional[float] = None

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

    def poll_feed(self, force: bool = False) -> Optional[Dict]:
        """
        Poll all RSS feeds for updates.

        Returns:
            Latest story dict if new item found, None otherwise
        """
        try:
            if not self.feed_urls:
                self.logger.warning("No RSS feed URLs configured")
                return None

            entries = []

            for url in self.feed_urls:
                self.logger.info(f"Polling RSS feed: {url}")
                feed = feedparser.parse(url)
                if not feed.entries:
                    self.logger.warning(f"No entries found in feed: {url}")
                    continue

                for entry in feed.entries[:10]:
                    entry_time = self._entry_timestamp(entry)
                    entries.append((entry_time, entry))

            if not entries:
                return None

            entries.sort(key=lambda x: x[0], reverse=True)

            def guid(e):
                return e.get('id') or e.get('link')

            selected = None
            if force:
                for _, entry in entries:
                    entry_time = self._entry_timestamp(entry)
                    if self.last_accepted_timestamp is not None and entry_time < self.last_accepted_timestamp:
                        continue
                    if guid(entry) not in self.seen_guids:
                        selected = entry
                        break
                if not selected:
                    selected = entries[0][1]
            else:
                for _, entry in entries:
                    entry_time = self._entry_timestamp(entry)
                    if self.last_accepted_timestamp is not None and entry_time < self.last_accepted_timestamp:
                        continue
                    if guid(entry) not in self.seen_guids:
                        selected = entry
                        break

            if selected:
                story = self._parse_entry(selected)
                self.logger.info(f"New story detected: {story['title']}")
                return story

            return None

        except Exception as e:
            self.logger.error(f"Error polling RSS feeds: {e}")
            return None

    def check_for_update(self, force: bool = False) -> Optional[Dict]:
        new_story = self.poll_feed(force=force)

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
        self.seen_guids.add(new_story['guid'])
        self.last_update_time = now
        self.current_story = new_story
        self.pending_story = None
        self.last_accepted_timestamp = new_story.get('timestamp')

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
                self.last_accepted_timestamp = story.get('timestamp')
                return story

        return None

    def _parse_entry(self, entry: Dict) -> Dict:
        return {
            'guid': compute_guid(entry),
            'title': entry.get('title', 'Untitled'),
            'summary': entry.get('summary', ''),
            'link': entry.get('link', ''),
            'published': entry.get('published', ''),
            'source': entry.get('source', {}).get('title', 'Unknown'),
            'timestamp': self._entry_timestamp(entry)
        }
