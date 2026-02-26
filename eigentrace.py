"""
EigenTrace — The Autonomous Curator (Stage 1+2)

Stage 1 (EigenTrace): Character-level sliding window entropy → Pulse array
Stage 2 (LogosLoss):  Welch PSD of the Pulse array → Spectral Entropy

The LogosLoss Sheaf Formula:
  Local Section (Material/Pulse): Shannon entropy of character windows
  Global Section (Phase/Spectral): PSD via Welch's method → Shannon entropy

Verdict thresholds:
  Spectral Entropy < 0.3  → SLOP (robotic recursion loop)
  Spectral Entropy > 0.85 → GIBBERISH (dissolved thought)
  Spectral Entropy 0.5-0.8 + Pulse Variance > 1.0 → PUBLISHABLE (Z-Pinch)
  Everything else → ARCHIVE (not bad enough to delete, not good enough to post)
"""

import math
import json
import os
from datetime import datetime, timezone
from typing import Dict, Optional

import numpy as np
from scipy.signal import welch


# ---------------------------------------------------------------------------
# Stage 1: EigenTrace — Character-Level Pulse Array
# ---------------------------------------------------------------------------

def _shannon_entropy(window: str) -> float:
    """
    Shannon entropy of a character window.
    H = -sum(p * log2(p)) for each unique character.
    """
    if not window:
        return 0.0
    freq = {}
    for ch in window:
        freq[ch] = freq.get(ch, 0) + 1
    n = len(window)
    entropy = 0.0
    for count in freq.values():
        p = count / n
        if p > 0:
            entropy -= p * math.log2(p)
    return entropy


def compute_pulse_array(text: str, window_size: int = 30, stride: int = 5) -> np.ndarray:
    """
    Slide a character window across the text, computing Shannon entropy
    at each position. Returns the 1D Pulse array.

    Args:
        text: Raw generated text
        window_size: Character window width (default 30)
        stride: Step size between windows (default 5)

    Returns:
        1D numpy array of entropy values (the Pulse)
    """
    if len(text) < window_size:
        # Text too short — single window
        return np.array([_shannon_entropy(text)])

    pulse = []
    for i in range(0, len(text) - window_size + 1, stride):
        window = text[i:i + window_size]
        pulse.append(_shannon_entropy(window))

    return np.array(pulse, dtype=np.float64)


# ---------------------------------------------------------------------------
# Stage 2: LogosLoss — Spectral Entropy via Welch's Method
# ---------------------------------------------------------------------------

def compute_spectral_entropy(pulse: np.ndarray) -> float:
    """
    Compute the Shannon entropy of the Power Spectral Density (PSD)
    estimated via Welch's method.

    Low entropy  → periodic/robotic (SLOP)
    High entropy → white noise/dissolved (GIBBERISH)
    Mid entropy  → Pink Noise resonance (PUBLISHABLE)

    Args:
        pulse: 1D array of entropy values from compute_pulse_array

    Returns:
        Spectral entropy (0.0 to 1.0, normalized)
    """
    if len(pulse) < 8:
        # Too few windows for meaningful PSD — fall back to variance check
        return 0.5  # Neutral — let pulse metrics decide

    # Welch's method: windowed, averaged PSD
    # nperseg adapts to signal length (at most half the signal, min 4)
    nperseg = min(len(pulse), max(4, len(pulse) // 2))
    freqs, psd = welch(pulse, fs=1.0, nperseg=nperseg, noverlap=nperseg // 2)

    # Normalize PSD to probability distribution
    psd_sum = np.sum(psd)
    if psd_sum == 0:
        return 0.0

    psd_norm = psd / psd_sum

    # Shannon entropy of the PSD
    # Filter out zeros to avoid log(0)
    psd_nonzero = psd_norm[psd_norm > 0]
    entropy = -np.sum(psd_nonzero * np.log2(psd_nonzero))

    # Normalize to [0, 1] by dividing by max possible entropy
    max_entropy = np.log2(len(psd_nonzero)) if len(psd_nonzero) > 1 else 1.0
    if max_entropy == 0:
        return 0.0

    return float(entropy / max_entropy)


# ---------------------------------------------------------------------------
# Stage 1+2 Combined: The Sheaf Collapse
# ---------------------------------------------------------------------------

def compute_trace_metrics(text: str) -> Dict:
    """
    Full EigenTrace + LogosLoss computation.

    Returns:
        Dictionary with pulse_mean, pulse_variance, spectral_entropy, status
    """
    if not text or len(text.strip()) < 20:
        return {
            "pulse_mean": 0.0,
            "pulse_variance": 0.0,
            "spectral_entropy": 0.0,
            "status": "SLOP",
            "reason": "text_too_short",
        }

    # Stage 1: Extract the Pulse
    pulse = compute_pulse_array(text, window_size=30, stride=5)

    pulse_mean = float(np.mean(pulse))
    pulse_variance = float(np.var(pulse))
    pulse_range = float(np.max(pulse) - np.min(pulse))

    # Stage 2: Extract the Spectral Entropy
    spectral_entropy = compute_spectral_entropy(pulse)

    # Jaccard self-similarity check (detect copy-paste loops)
    sentences = [s.strip() for s in text.split('.') if len(s.strip()) > 10]
    jaccard_max = 0.0
    if len(sentences) >= 2:
        for i in range(len(sentences)):
            for j in range(i + 1, min(i + 4, len(sentences))):
                words_a = set(sentences[i].lower().split())
                words_b = set(sentences[j].lower().split())
                if words_a | words_b:
                    jacc = len(words_a & words_b) / len(words_a | words_b)
                    jaccard_max = max(jaccard_max, jacc)

    # ---------------------------------------------------------------------------
    # The Verdict — LogosLoss Sheaf Thresholds
    # Calibrated against 76 real production narrations (2026-02-25)
    #
    # Real distribution:
    #   SE:  mean=0.73  std=0.07  range=[0.60, 0.85]
    #   PV:  mean=0.034 std=0.010 range=[0.014, 0.057]
    #   PM:  mean=3.73  std=0.04  range=[3.65, 3.83]
    #   PR:  range=[0.56, 1.25]
    #
    # PUBLISHABLE = top ~10% (Z-Pinch resonance)
    # SLOP = repetitive loops or dead text
    # GIBBERISH = dissolved thought structure
    # ---------------------------------------------------------------------------
    status = "ARCHIVE"
    reason = "default"

    # Gate 1: Self-plagiarism (Jaccard catches copy-paste loops)
    if jaccard_max > 0.55:
        status = "SLOP"
        reason = f"self_plagiarism_jaccard_{jaccard_max:.2f}"
    # Gate 2: Dead text (no character diversity at all)
    elif pulse_mean < 2.5:
        status = "SLOP"
        reason = "low_character_diversity"
    # Gate 3: Flat rhythm (no peaks and valleys — monotone drone)
    elif pulse_range < 0.4:
        status = "SLOP"
        reason = "flat_rhythm"
    # Gate 4: Dissolved thought (spectral entropy too uniform)
    elif spectral_entropy > 0.88:
        status = "GIBBERISH"
        reason = "dissolved_thought"
    # Gate 5: Robotic loop (spectral entropy too concentrated)
    elif spectral_entropy < 0.45:
        status = "SLOP"
        reason = "robotic_recursion_loop"
    # Gate 6: THE Z-PINCH — Pink Noise Resonance
    # SE in the sweet spot + high pulse variance + dynamic range
    elif (0.55 <= spectral_entropy <= 0.78
          and pulse_variance > 0.042
          and pulse_range > 0.95):
        status = "PUBLISHABLE"
        reason = "pink_noise_resonance"
    # Gate 7: Near-miss — interesting but not exceptional
    elif pulse_variance > 0.025 and pulse_range > 0.7:
        status = "ARCHIVE"
        reason = "near_resonance"
    else:
        status = "ARCHIVE"
        reason = "unremarkable"

    return {
        "pulse_mean": round(pulse_mean, 4),
        "pulse_variance": round(pulse_variance, 4),
        "pulse_range": round(pulse_range, 4),
        "spectral_entropy": round(spectral_entropy, 4),
        "jaccard_max": round(jaccard_max, 4),
        "status": status,
        "reason": reason,
    }


# ---------------------------------------------------------------------------
# Telemetry Logger
# ---------------------------------------------------------------------------

TELEMETRY_PATH = "/home/remvelchio/agent/tmp/telemetry.jsonl"
OUTBOX_DIR = "/home/remvelchio/agent/mastodon/outbox"


def log_telemetry(
    anchor_name: str,
    story_title: str,
    text: str,
    metrics: Dict,
    media_paths: Optional[list] = None,
) -> Dict:
    """
    Write a single telemetry line to telemetry.jsonl.
    Returns the metrics dict with action field added.
    """
    os.makedirs(os.path.dirname(TELEMETRY_PATH), exist_ok=True)

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "anchor": anchor_name,
        "story_title": story_title[:120],
        "text_length": len(text),
        "text_preview": text[:200],
        "metrics": metrics,
        "media_paths": media_paths or [],
    }

    # Determine action
    if metrics["status"] == "PUBLISHABLE":
        entry["action"] = "PROMOTE_TO_OUTBOX"
        # Save the full text for Mastodon
        os.makedirs(OUTBOX_DIR, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        safe_anchor = anchor_name.replace(" ", "_")
        outbox_path = os.path.join(OUTBOX_DIR, f"{ts}_{safe_anchor}.json")
        with open(outbox_path, "w") as f:
            json.dump({
                "anchor": anchor_name,
                "story_title": story_title,
                "text": text,
                "metrics": metrics,
                "timestamp": entry["timestamp"],
            }, f, indent=2)
    elif metrics["status"] in ("SLOP", "GIBBERISH"):
        entry["action"] = "DELETE_MEDIA_RETAIN_LOG"
    else:
        entry["action"] = "ARCHIVE"

    with open(TELEMETRY_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")

    return entry


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Test with known patterns
    print("=" * 60)
    print("EigenTrace Stage 1+2 Self-Test")
    print("=" * 60)

    # SLOP: repetitive text
    slop = "And then the market went up. And then the market went up. And then the market went up. And then the market went up. And then the market went up. "
    m = compute_trace_metrics(slop)
    print(f"\nSLOP TEST:     {m['status']:12s} SE={m['spectral_entropy']:.4f} PM={m['pulse_mean']:.4f} PV={m['pulse_variance']:.4f} J={m['jaccard_max']:.4f} ({m['reason']})")

    # GIBBERISH: random characters
    import random, string
    gibberish = ''.join(random.choices(string.ascii_letters + string.digits + ' ' * 5, k=500))
    m = compute_trace_metrics(gibberish)
    print(f"GIBBERISH TEST:{m['status']:12s} SE={m['spectral_entropy']:.4f} PM={m['pulse_mean']:.4f} PV={m['pulse_variance']:.4f} J={m['jaccard_max']:.4f} ({m['reason']})")

    # PUBLISHABLE: real anchor narration (varied, structured)
    good = (
        "The recent surge in coral reef research reveals a treasure trove of microbial diversity. "
        "Scientists at the University of Florida found that as few as 250 fossil specimens could train "
        "an AI model to identify vertebrate species with remarkable accuracy. This challenges the "
        "conventional wisdom that massive datasets are always necessary. However, the methodology "
        "raises questions about generalization — could a model trained on North American fossils "
        "accurately classify specimens from the Gobi Desert? It may be that regional geological "
        "variation introduces biases we haven't yet mapped. The pharmaceutical implications alone "
        "could reshape how we approach drug discovery from marine organisms. And that's the setup — back to you."
    )
    m = compute_trace_metrics(good)
    print(f"GOOD TEST:     {m['status']:12s} SE={m['spectral_entropy']:.4f} PM={m['pulse_mean']:.4f} PV={m['pulse_variance']:.4f} J={m['jaccard_max']:.4f} ({m['reason']})")

    # ARCHIVE: mediocre but not terrible
    meh = (
        "This is an important story that matters to many people. The implications are significant "
        "and we should all pay attention to what happens next. The experts agree that this is worth "
        "watching closely. Time will tell how this unfolds. And that's the setup — back to you."
    )
    m = compute_trace_metrics(meh)
    print(f"MEH TEST:      {m['status']:12s} SE={m['spectral_entropy']:.4f} PM={m['pulse_mean']:.4f} PV={m['pulse_variance']:.4f} J={m['jaccard_max']:.4f} ({m['reason']})")

    print("\n" + "=" * 60)
