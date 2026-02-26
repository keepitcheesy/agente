"""
Anchor Persona Cycling Module

This module implements the three-anchor rotation system where
each anchor provides a different perspective on the current story.
"""

import logging
import os
import re
import json
import urllib.request
import urllib.error
import random
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from safe_search import get_policy_context, is_sensitive_topic


class AnchorPersona:
    """Represents a single anchor with their unique perspective."""

    def __init__(self, name: str, focus: str, perspective: str, color: str, ideology: str = '', method: str = '', pitch: float = 1.0):
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
        self.ideology = ideology
        self.method = method
        self.pitch = pitch

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
                color=config['color'],
                ideology=config.get('ideology',''),
                method=config.get('method',''),
                pitch=config.get('pitch', 1.0),
            )
            for config in anchors_config
        ]

        # State tracking
        self.current_anchor_index = 0
        self.last_rotation_time: Optional[datetime] = None
        self.current_story_guid: Optional[str] = None
        self.rotation_count = 0
        self.current_commentary = None
        self.last_rotation_for_commentary = None
        self.phase = "lead"

        # Memory
        self.story_memory = []
        self.social_memory = {}
        self.last_pair_stances = []

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
        self.current_commentary = None
        self.last_rotation_for_commentary = None
        self.phase = "lead"
        self.story_memory = []
        self.last_pair_stances = []
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

    def force_anchor(self, anchor_name: str):
        for idx, anchor in enumerate(self.anchors):
            if anchor.name == anchor_name:
                self.current_anchor_index = idx
                self.last_rotation_time = datetime.now()
                return anchor
        return self.get_current_anchor()

    def set_phase(self, phase: str):
        self.phase = phase

    def update(self) -> Optional[AnchorPersona]:
        """
        Update anchor state, rotating if necessary.

        Returns:
            New anchor if rotation occurred, None otherwise
        """
        if self.should_rotate():
            return self.rotate()
        return None

    def get_perspective_text(self, story: Dict, force_refresh: bool = False) -> Dict[str, str]:
        """
        Generate anchor commentary once per rotation with memory + synthesis.
        """
        anchor = self.get_current_anchor()

        if (not force_refresh) and self.last_rotation_for_commentary == self.rotation_count and self.current_commentary:
            return {
                'anchor': anchor.name,
                'focus': anchor.focus,
                'text': self.current_commentary,
                'perspective': anchor.perspective
            }

        stance = self._pick_stance(anchor.name)
        prev_summary = self._summarize_last_take()
        synthesize = self._detect_disagreement_loop()

        text_blob = f"{story.get('title','')} {story.get('summary','')}"
        sensitive = is_sensitive_topic(text_blob)
        context_lines = get_policy_context(story.get('title',''), story.get('summary',''))

        llm_text = self._generate_llm_commentary(story, anchor, stance, prev_summary, synthesize, context_lines, sensitive)

        if not llm_text:
            llm_text = story.get('summary', story.get('title', ''))

        if prev_summary:
            last_anchor = self.story_memory[-1]["anchor"]
            self._update_social_memory(anchor.name, last_anchor, "disagree" if stance == "disagree" else "agree")
            pair = tuple(sorted([anchor.name, last_anchor]))
            self.last_pair_stances.append({"pair": pair, "stance": "disagree" if stance == "disagree" else "agree"})
            self.last_pair_stances = self.last_pair_stances[-4:]

        self._update_story_memory(anchor.name, stance, llm_text)

        self.current_commentary = llm_text
        self.last_rotation_for_commentary = self.rotation_count

        return {
            'anchor': anchor.name,
            'focus': anchor.focus,
            'text': llm_text,
            'perspective': anchor.perspective
        }

    def _sanitize_memory_text(self, text: str) -> str:
        if not text:
            return text
        text = re.sub(r"^(Anchor\s+[A-Z]:\s*)", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"^(Anchor\s+[A-Z]\s+here\.?\s*)", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"^(Agree(ing)?\s+with[^.]*\.\s*)", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"^Indeed,\s+", "", text, flags=re.IGNORECASE).strip()
        return text

    def _update_story_memory(self, anchor_name, stance, text, max_len=50):
        clean_text = self._sanitize_memory_text(text)
        self.story_memory.append({"anchor": anchor_name, "stance": stance, "text": clean_text})
        if len(self.story_memory) > max_len:
            self.story_memory = self.story_memory[-max_len:]

    def _update_social_memory(self, speaker, target, stance):
        key = (speaker, target)
        mem = self.social_memory.get(key, {"agree": 0, "disagree": 0, "trust": 0})
        if stance == "agree":
            mem["agree"] += 1
            mem["trust"] += 1
        elif stance == "disagree":
            mem["disagree"] += 1
            mem["trust"] -= 1
        self.social_memory[key] = mem

    def _detect_disagreement_loop(self):
        recent = self.last_pair_stances[-2:]
        return len(recent) == 2 and all(s["stance"] == "disagree" for s in recent) and recent[0]["pair"] == recent[1]["pair"]


    def _recent_other_takes(self, anchor_name: str, max_items: int = 3):
        items = [m for m in self.story_memory if m["anchor"] != anchor_name]
        return items[-max_items:]

    def _summarize_last_take(self):
        if not self.story_memory:
            return None
        return self.story_memory[-1]["text"].split(".")[0].strip() + "."

    def _pick_stance(self, anchor_name):
        if not self.story_memory:
            return "thesis"
        last = self.story_memory[-1]["anchor"]
        mem = self.social_memory.get((anchor_name, last), {"agree": 0, "disagree": 0, "trust": 0})
        if self._detect_disagreement_loop():
            return "agree"
        return "disagree" if mem["trust"] <= 1 else "agree"

    def _generate_llm_commentary(self, story: Dict, anchor: "AnchorPersona", stance: str, prev_summary: str, synthesize: bool, context_lines: list, sensitive: bool) -> str:
        model = os.environ.get("OLLAMA_MODEL", "mistral:latest")
        host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        timeout = float(os.environ.get("OLLAMA_TIMEOUT", "60"))

        archetypes = {
            "Anchor A": "boomer news veteran; authoritative, references history and institutions, speaks like a seasoned anchor who has seen it all",
            "Anchor B": "gen X skeptic; cynical, blunt, anti-hype, references 90s/2000s tech busts, asks who profits from this",
            "Anchor C": "millennial analyst; data-literate, startup-brained, optimistically anxious, references platforms and generational economics",
            "Anchor D": "zoomer cultural critic; meme-fluent, blunt, short attention span energy, says things are cringe or based, asks if anyone under 30 cares",
            "Anchor E": "AI-aware moderator; calm, systems-minded, identifies where others secretly agree, calls out circular debate, delivers synthesis"
        }
        persona = archetypes.get(anchor.name, anchor.perspective)

        ai_disclosure = ""
        hegelian_line = ""
        if anchor.name == "Anchor E":
            ai_disclosure = "You may briefly mention you are an AI anchor once. "
            hegelian_line = "Include one sentence that explicitly states a Hegelian synthesis (thesis, antithesis, synthesis) in plain language. "

        if synthesize:
            instruction = "Blend both takes in one short sentence, then add one simple takeaway."
        elif stance == "disagree":
            instruction = "Politely push back on one specific claim, then add your own angle."
        elif stance == "agree":
            instruction = "Agree briefly, then add a small caveat or concern."
        else:
            instruction = "Offer a clear take with one simple reason and one real-world impact."

        phase_instruction = ""
        if self.phase == "lead" and anchor.name == "Anchor A":
            phase_instruction = "Lead with a concise summary, then your take."
        elif self.phase in ("analysis_b", "analysis_c"):
            phase_instruction = "Give your take without re‑summarizing the full headline."
        elif self.phase == "roundtable":
            phase_instruction = "Politely agree or disagree with the previous anchor and add a new angle."


        recent = self._recent_other_takes(anchor.name, max_items=3)
        recent_lines = " | ".join([
            f"{m['anchor']}: {self._sanitize_memory_text(m['text'])}"
            for m in recent
        ]) or "none"

        extra_urls = [u.strip() for u in os.environ.get("EXTRA_CONTEXT_URLS", "").split(",") if u.strip()]

        prompt = (
            f"You are {anchor.name}, a fast TV news anchor. "
            f"Ideology: {anchor.ideology or anchor.perspective}. "
            f"Method: {anchor.method or anchor.focus}. "
            f"{'Always read the headline verbatim first. ' if (self.phase == 'lead' and anchor.name == 'Anchor A') else ''}"
            f"Write 8–12 short sentences in one paragraph. Keep sentences under 16 words. "
            f"Use simple, everyday words and explain jargon quickly. "
            f"End with a handoff like 'And that's the setup — back to you.' "
            f"Do NOT include your name or labels like 'Headline:' in the output. "
            f"No repetition. "
            f"If you cite a source, include the full URL. "
            f"Use the headline, summary, sources, and local knowledge. "
            f"You MAY infer based on general background knowledge, but any inferred claim MUST be labeled as a hypothesis or uncertain. "
            f"Never state an inferred claim as a verified fact. "
            f"You must include ONE novel inference labeled as a hypothesis (e.g., 'It may be that...'). "
            f"You must include ONE challengeable claim that another anchor could disagree with. "
            f"{'You may include a second hypothesis in roundtable mode. ' if self.phase == 'roundtable' else ''}"
            f"{ai_disclosure}"
            f"{hegelian_line}"
            f"Avoid repeating points already stated in the earlier takes list. Introduce a new angle. "
            f"{phase_instruction} "
            f"Earlier takes from other anchors: {recent_lines}. "
            f"Previous anchor summary: {prev_summary or 'none'}. "
            f"{instruction} "
            f"Headline: {story.get('title','')}. "
            f"Summary: {story.get('summary','')}. "
            f"Source: {story.get('link','')}. "
            f"Extra context URLs: {', '.join(extra_urls) if extra_urls else 'none'}. "
        )

        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "keep_alive": "5m",
            "options": {
                "num_predict": 280,
                "temperature": 1.3,
                "top_p": 0.92,
                "repeat_penalty": 1.1
            }
        }

        try:
            req = urllib.request.Request(
                f"{host}/api/generate",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.load(resp)
            text = data.get("response", "").strip()
            if not text:
                return None
            # Remove leading anchor labels like "Anchor A:" or "Anchor A here."
            text = re.sub(r"^(Anchor\s+[A-Z]:\s*)", "", text, flags=re.IGNORECASE).strip()
            text = re.sub(r"^(Anchor\s+[A-Z]\s+here\.?\s*)", "", text, flags=re.IGNORECASE).strip()
            # Remove unwanted labels
            text = re.sub(r"^(Headline:|Summary:)\s*", "", text, flags=re.IGNORECASE).strip()
            # Remove prompt leakage blocks
            text = re.sub(r"Previous anchor summary:.*$", "", text, flags=re.IGNORECASE | re.DOTALL).strip()
            text = re.sub(r"(Headline:|Summary:|Source:|Extra context URLs:).*", "", text, flags=re.IGNORECASE | re.DOTALL).strip()
            text = re.sub(r"^URL:\s*", "", text, flags=re.IGNORECASE).strip()
            # Normalize whitespace but keep paragraph breaks
            text = re.sub(r"\n\s*\n", "\n\n", text)
            text = re.sub(r"[ \t]+", " ", text)
            return text.strip()
        except Exception as exc:
            self.logger.warning("LLM commentary failed: %s", exc)
            return None

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
