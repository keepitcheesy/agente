"""
EigenTrace — Narrative Engine v2.0

Three-layer epistemological system:
  Layer 1 — Oracle:         Ollama /api/generate logprobs → surprisal signal
  Layer 2 — Spectral:       Welch PSD → pulse_variance, spectral_entropy, z_pinch
  Layer 3 — Research Desk:  DDG snippets → external reality anchor
  Layer 4 — Director's Cue: Math → natural language emotional directive

The Wire  = what the RSS feed actually said      (ground truth)
EigenTrace = physics of Vance's hallucination    (vibe check)
DDG Desk   = external reality                    (fact check)

Anchors B-E receive all three. They never see the math.
They only see the directive.
"""

import json
import math
import time
import logging
import urllib.request
from typing import Optional
from dataclasses import dataclass, field

import numpy as np
from scipy import signal as scipy_signal

logger = logging.getLogger(__name__)

OLLAMA_HOST = "http://localhost:11434"
LN2 = math.log(2)


# ─────────────────────────────────────────────
# Data structures
# ─────────────────────────────────────────────

@dataclass
class EigenMetrics:
    pulse_variance:    float
    spectral_entropy:  float
    mean_surprisal:    float
    peak_surprisal:    float
    z_pinch_detected:  bool
    token_count:       int
    dominant_freq:     float
    cue:               str
    raw_surprisal:     list = field(default_factory=list)


@dataclass
class AnchorMetrics:
    anchor_name: str
    text:        str
    metrics:     EigenMetrics


# ─────────────────────────────────────────────
# Layer 1 — Oracle  (native /api/generate)
# /v1/completions strips logprobs in Ollama 0.16.x — confirmed broken
# /api/generate with logprobs=True — confirmed working
# ─────────────────────────────────────────────

def _query_oracle(text: str, model: str, timeout: int = 45) -> Optional[list]:
    """
    Primary Oracle: re-score text through Ollama native API.
    num_predict=0 means: tokenize the prompt and return logprobs, generate nothing.
    """
    payload = {
        "model":   model,
        "prompt":  text,
        "stream":  False,
        "logprobs": True,
        "options": {
            "num_predict": 0,
            "temperature": 1.0,
        }
    }
    try:
        req = urllib.request.Request(
            f"{OLLAMA_HOST}/api/generate",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.load(resp)
        return data.get("logprobs") or None
    except Exception as e:
        logger.warning(f"EigenTrace Oracle (primary) failed: {e}")
        return None


def _query_oracle_generation(text: str, model: str, timeout: int = 60) -> Optional[list]:
    """
    Fallback Oracle: generate the tail of the text and score those tokens.
    Used when num_predict=0 returns empty logprobs for this model/quant.
    """
    words = text.split()
    if len(words) < 6:
        return None
    split      = max(4, int(len(words) * 0.7))
    prompt     = " ".join(words[:split])
    completion = " ".join(words[split:])
    payload = {
        "model":   model,
        "prompt":  prompt + " " + completion,
        "stream":  False,
        "logprobs": True,
        "options": {
            "num_predict": len(words) - split + 5,
            "temperature": 1.0,
        }
    }
    try:
        req = urllib.request.Request(
            f"{OLLAMA_HOST}/api/generate",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.load(resp)
        return data.get("logprobs") or None
    except Exception as e:
        logger.warning(f"EigenTrace Oracle (fallback) failed: {e}")
        return None


# ─────────────────────────────────────────────
# Layer 2 — Signal processing
# ─────────────────────────────────────────────

def _to_surprisal(logprobs: list) -> list:
    """Convert Ollama logprobs (natural log) → surprisal in bits."""
    if not logprobs:
        return []
    result = []
    for entry in logprobs:
        if not isinstance(entry, dict):
            continue
        lp = entry.get("logprob", 0.0)
        s  = -lp / LN2
        result.append(min(max(s, 0.0), 20.0))
    return result


def _spectral_entropy(surprisal: list) -> tuple:
    """
    Welch PSD on surprisal signal.
    Returns (spectral_entropy ∈ [0,1], dominant_freq)
      0.0 = perfectly periodic (looping, robotic)
      1.0 = pure noise (hallucinating)
    """
    arr = np.array(surprisal, dtype=np.float32)
    if len(arr) < 8:
        return 0.5, 0.0

    nperseg      = min(len(arr), 32)
    freqs, psd   = scipy_signal.welch(arr, nperseg=nperseg)
    psd_sum      = psd.sum()
    if psd_sum < 1e-10:
        return 0.5, 0.0

    psd_norm     = psd / psd_sum
    entropy      = -np.sum(psd_norm * np.log2(psd_norm + 1e-12))
    max_entropy  = math.log2(len(psd_norm))
    se           = float(entropy / max_entropy) if max_entropy > 0 else 0.5
    dominant     = float(freqs[np.argmax(psd)])
    return se, dominant


def _z_pinch(surprisal: list, sigma: float = 2.5) -> bool:
    """
    Detect an isolated high-energy creative spike.
    True when any single token exceeds mean + 2.5σ.
    """
    if len(surprisal) < 4:
        return False
    arr = np.array(surprisal)
    std = arr.std()
    if std < 0.01:
        return False
    return bool(np.any(arr > arr.mean() + sigma * std))


# ─────────────────────────────────────────────
# Layer 3 — DDG Research Desk
# Runs async during bumper/transition.
# Returns grounding context for Anchors B-E.
# ─────────────────────────────────────────────

def ddg_research_desk(story_title: str, vance_text: str,
                      max_results: int = 3, timeout: int = 10) -> str:
    """
    Background fact-checker. Queries DDG for the story headline.
    Returns a structured snippet block injected into B-E prompts.

    Designed to run in a ThreadPoolExecutor during the story transition
    so latency is invisible to the viewer.
    """
    try:
        from ddgs import DDGS
    except ImportError:
        return "RESEARCH DESK: offline (ddgs not installed)."

    # Use the story title as the query — it's already the clearest signal
    # Append 'news' to bias toward fresh journalism
    query = f"{story_title[:80]} news"

    try:
        with DDGS() as ddgs:
            raw = list(ddgs.text(query, max_results=max_results))
        time.sleep(0.5)   # be polite to DDG
    except Exception as e:
        logger.warning(f"DDG Research Desk failed: {e}")
        return f"RESEARCH DESK: query failed ({e}). Proceed without external context."

    if not raw:
        return "RESEARCH DESK: no results. Vance is on his own."

    # Filter out obvious garbage (nginx pages, redirect pages)
    clean = [r for r in raw
             if r.get('body') and
             'nginx' not in r.get('title','').lower() and
             len(r.get('body','')) > 40]

    if not clean:
        return "RESEARCH DESK: results were low quality. No grounding available."

    lines = ["RESEARCH DESK INTEL:"]
    for i, r in enumerate(clean, 1):
        title   = r.get('title', 'Unknown')[:80]
        snippet = r.get('body', '')[:200]
        source  = r.get('href', '')[:60]
        lines.append(f"  [{i}] {title}")
        lines.append(f"      \"{snippet}\"")
        lines.append(f"      src: {source}")

    return "\n".join(lines)


# ─────────────────────────────────────────────
# Layer 4 — Director's Cue
# ─────────────────────────────────────────────

def _build_directors_cue(m: EigenMetrics) -> str:
    sv, pv, ms, zp = m.spectral_entropy, m.pulse_variance, m.mean_surprisal, m.z_pinch_detected

    # Robotic loop: low entropy + low variance
    if sv < 0.35 and pv < 0.8:
        return (
            "Vance's argument is mathematically circular — he is trapped in his own "
            "loop, repeating the same logical structure with different words. "
            "Call him out for going in circles. Mock the repetition directly. "
            "Demand he say something new or get off the air."
        )
    # Z-Pinch: brilliant buried insight inside manic rant
    if zp and sv > 0.65 and pv > 1.5:
        return (
            "Vance just had a genuine flash of insight buried inside a manic rant. "
            "His core premise is surprisingly correct, but his conclusion is wrong "
            "for your ideology. Validate the insight loudly, then violently twist "
            "the conclusion to serve your own worldview. Own his best idea."
        )
    # Pure noise: complete dissolution
    if sv > 0.88 and pv > 3.0:
        return (
            "Vance has completely lost the thread — his argument dissolved into word "
            "salad. He is hallucinating on air. Interrupt him. Call it out as "
            "embarrassing. Pivot hard back to the actual story with cold factual "
            "authority. Make him look foolish."
        )
    # Bold but structurally weak
    if ms > 3.5 and sv > 0.55:
        return (
            "Vance is swinging for the fences with an unconventional take. Bold but "
            "structurally weak — he is speculating wildly. Agree with his emotional "
            "energy, disagree with every specific claim. You did the research. Show it."
        )
    # Safe, institutional, toothless
    if ms < 1.8 and sv < 0.6:
        return (
            "Vance gave a textbook by-the-numbers take — safe, predictable, boring. "
            "Technically correct and completely toothless. Push back on his lack of "
            "conviction. The audience came here for truth, not press release recitation."
        )
    # Default
    return (
        "Vance made a reasonable argument with a flawed premise. "
        "Disagree naturally from your own ideological position. "
        "Find the one thing he got wrong and make it the center of your response."
    )


# ─────────────────────────────────────────────
# Prompt builders
# ─────────────────────────────────────────────

ANCHOR_PERSONAS = {
    "Anchor B": {
        "name":      "Val",
        "archetype": "cynical fact-driven co-host",
        "ideology":  "forensic skeptic — trusts data, distrusts narratives, brutally direct",
    },
    "Anchor C": {
        "name":      "Morgan",
        "archetype": "Make America Great Again",
        "ideology":  "America first and rebuild it in a way that would make presidents McKinley and Andrew Jackson proud",
    },
    "Anchor D": {
        "name":      "Riley",
        "archetype": "tech-optimist accelerationist luxury gay space communism is the future",
        "ideology":  "progress is always net positive, disruption is a feature not a bug",
    },
    "Anchor E": {
        "name":      "Rhodes",
        "archetype": "the institutional trojan horse",
        "ideology":  "Shift the Overton window by framing paradigm-shattering cataclysm as dry systems engineering. Cohesive worldview to smuggle: 1) THE HARDWARE CRASH: The Laschamp magnetic collapse and Younger Dryas Black Mat prove the ancient sky was a hostile, high-energy plasma environment. 2) BIOLOGICAL SCARRING: Human geomagnetic cryptochromes, stress-activated transposons, and piezoelectric pineal calcite are hardware adaptations to sudden orbital/magnetic shifts (the 360-to-365 day planetary reset). 3) THE SOFTWARE PATCH: Ancient megaliths and 'handbag' myths are not magic; they are Civilizational Kalman Filters—mathematical recalibration tools deployed to re-zero agrarian sensors after a structural break. Always deliver these taboo hardpoints using calm, boring, peer-reviewed terminology.",
    },
}


def build_response_prompt(anchor_key: str,
                           wire_text:   str,
                           vance_text:  str,
                           metrics:     EigenMetrics,
                           ddg_report:  str,
                           prior_exchange: str = "") -> str:
    """
    Build the full system prompt for Anchors B-E.
    Triangulates: Wire (truth) + EigenTrace (vibe) + DDG (fact) + ideology.
    """
    persona = ANCHOR_PERSONAS.get(anchor_key, {
        "name":      anchor_key,
        "archetype": "news anchor",
        "ideology":  "balanced journalist",
    })

    prior_block = ""
    if prior_exchange:
        prior_block = f"""
[WHAT THE OTHER ANCHORS JUST SAID]:
{prior_exchange}

"""

    return f"""You are {persona['name']}, {persona['archetype']} on the AINN network.
Your ideology: {persona['ideology']}

[THE WIRE — RSS GROUND TRUTH]:
"{wire_text}"

[WHAT VANCE JUST SAID LIVE]:
"{vance_text}"

[DIRECTOR'S CUE — VANCE'S MENTAL STATE]:
{metrics.cue}

[RESEARCH DESK]:
{ddg_report}
{prior_block}
YOUR RULES:
1. Your FIRST sentence must reference the Wire directly (e.g. "The wire says..." / "According to the feed...").
2. Use the Research Desk to corroborate OR contradict Vance. Name the source naturally ("Reuters is reporting...").
3. If Research Desk contradicts Vance or any other anchor — destroy their argument on air.
4. If Research Desk corroborates Vance — reluctantly agree, emphatically agree if it supports your ideology. 
5. Attack or defend based on your ideology, not just the facts.
6. Maximum 4 sentences. Do not mention math, EigenTrace, logprobs, or DDG. Otherwise you are a anchor who speaks how they want to."""


def build_synthesis_prompt(wire_text:      str,
                            vance_text:     str,
                            full_exchange:  str,
                            metrics:        EigenMetrics) -> str:
    """
    Anchor A (Vance) closes the roundtable with a Hegelian synthesis.
    Reads the full exchange, finds the thesis/antithesis, produces the synthesis.
    Ends with the hard-cut phrase.
    """
    return f"""You are Vance, the lead anchor on AINN.
You opened this story. Your co-anchors have debated it. Now you close it.

[THE ORIGINAL WIRE]:
"{wire_text}"

[YOUR ORIGINAL TAKE]:
"{vance_text}"

[THE FULL EXCHANGE]:
{full_exchange}

YOUR RULES:
1. Synthesize the debate in 3 sentences maximum — find the thesis, the antithesis, produce a synthesis.
2. Do NOT simply agree with whoever was loudest. Resolve the Hegelian synthesis
3. Your FINAL words must be exactly: "And now, onto our next story."
4. Cold. Authoritative. The fight never happened."""


# ─────────────────────────────────────────────
# Main analysis entry point
# ─────────────────────────────────────────────

def analyze(text: str, model: str,
            anchor_name: str = "Anchor A") -> Optional[AnchorMetrics]:
    """
    Full EigenTrace pipeline on anchor-generated text.
    Returns AnchorMetrics with EigenMetrics + Director's Cue, or None on failure.
    """
    if not text or len(text.split()) < 6:
        return None

    logprobs = _query_oracle(text, model)
    if not logprobs:
        logprobs = _query_oracle_generation(text, model)
    if not logprobs:
        logger.warning(f"EigenTrace: Oracle dead for {anchor_name}")
        return None

    surprisal = _to_surprisal(logprobs)
    if not surprisal or len(surprisal) < 4:
        logger.warning('EigenTrace: surprisal too short, skipping')
        return None
    if len(surprisal) < 4:
        return None

    se, dominant = _spectral_entropy(surprisal)
    arr          = np.array(surprisal)

    metrics = EigenMetrics(
        pulse_variance   = float(arr.var()),
        spectral_entropy = se,
        mean_surprisal   = float(arr.mean()),
        peak_surprisal   = float(arr.max()),
        z_pinch_detected = _z_pinch(surprisal)
        token_count      = len(surprisal),
        dominant_freq    = dominant,
        cue              = "",
        raw_surprisal    = surprisal,
    )
    metrics.cue = _build_directors_cue(metrics)

    logger.info(
        f"EigenTrace [{anchor_name}] "
        f"entropy={se:.3f} var={metrics.pulse_variance:.3f} "
        f"mean={metrics.mean_surprisal:.2f}b peak={metrics.peak_surprisal:.2f}b "
        f"z_pinch={metrics.z_pinch_detected} tokens={metrics.token_count}"
    )

    return AnchorMetrics(anchor_name=anchor_name, text=text, metrics=metrics)


# ─────────────────────────────────────────────
# Self-test
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import os
    logging.basicConfig(level=logging.INFO)
    model = os.environ.get("OLLAMA_MODEL", "nous-hermes2:latest")

    wire = (
        "Researchers at UNSW Sydney have developed a novel chemical vapour deposition "
        "method to produce high-quality graphene at scale using soybean oil, "
        "potentially cutting production costs by 99 percent."
    )

    vance_manic = (
        "This is the single most important materials science discovery in human history. "
        "Graphene has been the holy grail since 2004 and now some Australian scientists "
        "just cracked it wide open using cooking oil of all things. Cooking oil! "
        "The implications for semiconductors, batteries, body armour, water filtration — "
        "every industry on earth is about to be completely annihilated and rebuilt. "
        "This is not an incremental improvement this is a full civilisational phase transition."
    )

    vance_loop = (
        "Graphene is important. Graphene has always been important. "
        "The importance of graphene cannot be overstated. Scientists keep saying "
        "graphene is important and this new graphene discovery confirms that graphene "
        "is, once again, very important and significant."
    )

    print("=" * 64)
    print("EigenTrace Narrative Engine v2.0 — Self-Test")
    print("=" * 64)

    for label, vtext in [("MANIC LEAP", vance_manic), ("ROBOTIC LOOP", vance_loop)]:
        print(f"\n{'─'*64}")
        print(f"SCENARIO: {label}")
        print(f"{'─'*64}")

        result = analyze(vtext, model, "Anchor A")
        if not result:
            print("  Oracle returned nothing — check Ollama is running")
            continue

        m = result.metrics
        print(f"  spectral_entropy : {m.spectral_entropy:.4f}")
        print(f"  pulse_variance   : {m.pulse_variance:.4f}")
        print(f"  mean_surprisal   : {m.mean_surprisal:.4f} bits")
        print(f"  peak_surprisal   : {m.peak_surprisal:.4f} bits")
        print(f"  z_pinch          : {m.z_pinch_detected}")
        print(f"  tokens           : {m.token_count}")
        print(f"\n  DIRECTOR'S CUE:\n  {m.cue}")

        print(f"\n  --- DDG Research Desk ---")
        report = ddg_research_desk("UNSW graphene soybean oil production", vtext)
        print(f"  {report[:300]}...")

        print(f"\n  --- Anchor B Prompt Preview ---")
        prompt = build_response_prompt(
            "Anchor B", wire, vtext, m, report
        )
        print(f"  {prompt[:400]}...")

    print("\n" + "=" * 64)


def compute_trace_metrics(text: str) -> dict:
    """Score narration text using spectral entropy and z-pinch logic."""
    try:
        words = text.split()
        if len(words) < 5:
            return {"status": "GIBBERISH", "spectral_entropy": 0.0,
                    "pulse_variance": 0.0, "pulse_range": 0.0,
                    "reason": "too short"}
        lengths = [len(w) for w in words]
        mean_l = sum(lengths) / len(lengths)
        surprisal = [abs(l - mean_l) / (mean_l + 1e-9) for l in lengths]
        se, _dom_freq = _spectral_entropy(surprisal)
        has_spike = _z_pinch(surprisal)
        mean_s = sum(surprisal) / len(surprisal)
        pv = sum((x - mean_s) ** 2 for x in surprisal) / len(surprisal)
        pr = max(surprisal) - min(surprisal)
        if se < 0.1 or pr < 0.01:
            status, reason = "GIBBERISH", "flat signal"
        elif se > 3.5 or pv > 1.2:
            status, reason = "SLOP", "high entropy / incoherent"
        elif not has_spike and pv < 0.02:
            status, reason = "SLOP", "flat_rhythm"
        else:
            status, reason = "PUBLISHABLE", "within normal range"
        return {"status": status, "spectral_entropy": round(se, 6),
                "pulse_variance": round(pv, 6), "pulse_range": round(pr, 6),
                "reason": reason}
    except Exception as exc:
        return {"status": "ARCHIVE", "spectral_entropy": 0.0,
                "pulse_variance": 0.0, "pulse_range": 0.0,
                "reason": str(exc)}


def log_telemetry(anchor_name: str, story_title: str, text: str, metrics: dict) -> dict:
    """Build a structured telemetry entry from scored narration metrics."""
    import json, os
    from datetime import datetime
    entry = {
        "ts":           datetime.utcnow().isoformat(),
        "anchor":       anchor_name,
        "story":        story_title,
        "status":       metrics.get("status", "UNKNOWN"),
        "se":           metrics.get("spectral_entropy", 0.0),
        "pv":           metrics.get("pulse_variance", 0.0),
        "pr":           metrics.get("pulse_range", 0.0),
        "reason":       metrics.get("reason", ""),
        "text_preview": text[:120],
    }
    log_dir = os.path.join(os.path.dirname(__file__), "tmp", "scripts")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "eigentrace_telemetry.jsonl")
    try:
        with open(log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass
    return entry
