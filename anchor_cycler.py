"""
Anchor Persona Cycling Module

This module implements the three-anchor rotation system where
each anchor provides a different perspective on the current story.
"""

import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta


class AnchorPersona:
    """Represents a single anchor with their unique perspective."""
    
    def __init__(self, name: str, focus: str, perspective: str, color: str):
        """
        Initialize an anchor persona.
        
        Args:
            name: Anchor identifier (e.g., "Anchor A")
            focus: What this anchor focuses on (e.g., "headline/facts")
            perspective: Description of their viewpoint
            color: Color code for visual representation
        """
        self.name = name
        self.focus = focus
        self.perspective = perspective
        self.color = color
    
    def get_lower_third_text(self, story_title: str) -> Dict[str, str]:
        """
        Generate lower third text for this anchor.
        
        Args:
            story_title: Current story title
            
        Returns:
            Dictionary with lower third display information
        """
        return {
            'anchor_name': self.name,
            'focus': self.focus,
            'story': story_title,
            'color': self.color
        }
    
    def __repr__(self):
        return f"AnchorPersona({self.name}, focus={self.focus})"


class AnchorCycler:
    """
    Manages cycling through anchor personas for each story.
    
    Implements continuous rotation through perspectives A, B, C
    until a new story arrives.
    """
    
    def __init__(self, anchors_config: List[Dict], rotation_interval: int = 30):
        """
        Initialize the anchor cycler.
        
        Args:
            anchors_config: List of anchor configuration dicts
            rotation_interval: Seconds each anchor speaks before cycling
        """
        self.rotation_interval = rotation_interval
        self.logger = logging.getLogger(__name__)
        
        # Create anchor personas
        self.anchors = [
            AnchorPersona(
                name=config['name'],
                focus=config['focus'],
                perspective=config['perspective'],
                color=config['color']
            )
            for config in anchors_config
        ]
        
        # State tracking
        self.current_anchor_index = 0
        self.last_rotation_time: Optional[datetime] = None
        self.current_story_guid: Optional[str] = None
        self.rotation_count = 0
    
    def start_story(self, story_guid: str):
        """
        Start covering a new story.
        
        Args:
            story_guid: Unique identifier for the story
        """
        self.current_story_guid = story_guid
        self.current_anchor_index = 0  # Start with Anchor A
        self.last_rotation_time = datetime.now()
        self.rotation_count = 0
        self.logger.info(
            f"Started new story coverage: {story_guid} with {self.anchors[0].name}"
        )
    
    def get_current_anchor(self) -> AnchorPersona:
        """
        Get the currently active anchor.
        
        Returns:
            Current AnchorPersona instance
        """
        return self.anchors[self.current_anchor_index]
    
    def should_rotate(self) -> bool:
        """
        Check if it's time to rotate to the next anchor.
        
        Returns:
            True if rotation interval has passed, False otherwise
        """
        if not self.last_rotation_time:
            return False
        
        elapsed = (datetime.now() - self.last_rotation_time).total_seconds()
        return elapsed >= self.rotation_interval
    
    def rotate(self) -> AnchorPersona:
        """
        Rotate to the next anchor in the cycle.
        
        Returns:
            The new current AnchorPersona
        """
        # Move to next anchor (cycle through A -> B -> C -> A -> ...)
        self.current_anchor_index = (self.current_anchor_index + 1) % len(self.anchors)
        self.last_rotation_time = datetime.now()
        self.rotation_count += 1
        
        current_anchor = self.anchors[self.current_anchor_index]
        self.logger.info(
            f"Rotated to {current_anchor.name} "
            f"(rotation #{self.rotation_count})"
        )
        
        return current_anchor
    
    def update(self) -> Optional[AnchorPersona]:
        """
        Update anchor state, rotating if necessary.
        
        Returns:
            New anchor if rotation occurred, None otherwise
        """
        if self.should_rotate():
            return self.rotate()
        return None
    
    def get_perspective_text(self, story: Dict) -> Dict[str, str]:
        """
        Generate perspective text for the current anchor.
        
        Args:
            story: Story dictionary with title, summary, etc.
            
        Returns:
            Dictionary with anchor-specific perspective text
        """
        anchor = self.get_current_anchor()
        
        # Generate perspective-specific content
        if "headline/facts" in anchor.focus:
            text = self._generate_headline_perspective(story)
        elif "implications" in anchor.focus:
            text = self._generate_implications_perspective(story)
        elif "context" in anchor.focus:
            text = self._generate_context_perspective(story)
        else:
            text = story.get('summary', '')
        
        return {
            'anchor': anchor.name,
            'focus': anchor.focus,
            'text': text,
            'perspective': anchor.perspective
        }
    
    def _generate_headline_perspective(self, story: Dict) -> str:
        """Generate headline/facts focused text."""
        return (
            f"Here's what happened: {story['title']}. "
            f"{story.get('summary', '')[:200]}"
        )
    
    def _generate_implications_perspective(self, story: Dict) -> str:
        """Generate implications focused text."""
        return (
            f"Why this matters: {story['title']} could have significant impacts. "
            f"Looking at what comes next..."
        )
    
    def _generate_context_perspective(self, story: Dict) -> str:
        """Generate context focused text."""
        return (
            f"For context on {story['title']}: "
            f"This story builds on recent developments..."
        )
    
    def get_stats(self) -> Dict:
        """Get statistics about the current coverage."""
        return {
            'current_anchor': self.get_current_anchor().name,
            'rotation_count': self.rotation_count,
            'story_guid': self.current_story_guid,
            'time_on_anchor': (
                (datetime.now() - self.last_rotation_time).total_seconds()
                if self.last_rotation_time else 0
            )
        }
