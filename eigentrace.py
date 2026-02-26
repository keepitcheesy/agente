"""
EigenTrace -- Narrative Engine v2.0

Layer 1: Oracle         -- Ollama /api/generate logprobs -> surprisal signal
Layer 2: Spectral       -- Welch PSD -> pulse_variance, spectral_entropy, z_pinch
Layer 3: Research Desk  -- DDG snippets -> external reality anchor
Layer 4: Director Cue   -- Math -> natural language emotional directive
"""

import json
import math
import time
import logging
import urllib.request
from typing import Optional
from dataclasses import dataclass, field
from collections import deque

import numpy as np
from scipy import signal as scipy_signal

logger = logging.getLogger(__name__)
OLLAMA_HOST = "http://localhost:11434"
LN2 = math.log(2)

_episode_buffer = deque(maxlen=5)


@dataclass
class EigenMetrics:
    pulse_variance:   float
    spectral_entropy: float
    mean_surprisal:   float
    peak_surprisal:   float
    z_pinch_detected: bool
    token_count:      int
    dominant_freq:    float
    cue:              str
    raw_surprisal:    list = field(default_factory=list)


@dataclass
class AnchorMetrics:
    anchor_name: str
    text:        str
    metrics:     EigenMetrics


def _query_oracle(text, model, timeout=90):
    payload = {
        "model": model, "prompt": text, "stream": False,
        "logprobs": True, "options": {"num_predict": 0, "temperature": 1.0, "seed": 42}
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
        logger.warning(f"Oracle (primary) failed: {e}")
        return None


def _query_oracle_generation(text, model, timeout=90):
    words = text.split()
    if len(words) < 6:
        return None
    split = max(4, int(len(words) * 0.4))
    payload = {
        "model": model,
        "prompt": " ".join(words[:split]) + " " + " ".join(words[split:]),
        "stream": False, "logprobs": True,
        "options": {"num_predict": 32, "temperature": 0.0, "seed": 42}
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
        logger.warning(f"Oracle (fallback) failed: {e}")
        return None


def _to_surprisal(logprobs):
    result = []
    for entry in logprobs:
        s = -entry.get("logprob", 0.0) / LN2
        result.append(min(max(s, 0.0), 20.0))
    return result


def _spectral_entropy(surprisal):
    arr = np.array(surprisal, dtype=np.float32)
    if len(arr) < 8:
        return 0.5, 0.0
    nperseg = min(len(arr), 32)
    freqs, psd = scipy_signal.welch(arr, nperseg=nperseg)
    psd_sum = psd.sum()
    if psd_sum < 1e-10:
        return 0.5, 0.0
    psd_norm = psd / psd_sum
    entropy = -np.sum(psd_norm * np.log2(psd_norm + 1e-12))
    max_entropy = math.log2(len(psd_norm))
    se = float(entropy / max_entropy) if max_entropy > 0 else 0.5
    return se, float(freqs[np.argmax(psd)])


def _z_pinch(surprisal, sigma=2.5):
    if len(surprisal) < 4:
        return False
    arr = np.array(surprisal)
    std = arr.std()
    if std < 0.01:
        return False
    return bool(np.any(arr > arr.mean() + sigma * std))


def ddg_research_desk(story_title, vance_text, max_results=3, timeout=10):
    try:
        from ddgs import DDGS
    except ImportError:
        return "RESEARCH DESK: offline (ddgs not installed)."
    query = f"{story_title[:80]} news"
    try:
        with DDGS() as ddgs:
            raw = list(ddgs.text(query, max_results=max_results))
        time.sleep(0.5)
    except Exception as e:
        logger.warning(f"DDG failed: {e}")
        return "RESEARCH DESK: query failed. Proceed without external context."
    if not raw:
        return "RESEARCH DESK: no results. Vance is on his own."
    clean = [r for r in raw
             if r.get("body") and
             "nginx" not in r.get("title", "").lower() and
             len(r.get("body", "")) > 40]
    if not clean:
        return "RESEARCH DESK: results low quality. No grounding available."
    lines = ["RESEARCH DESK INTEL:"]
    for i, r in enumerate(clean, 1):
        lines.append(f"  [{i}] {r.get('title','')[:80]}")
        lines.append(f"      \"{r.get('body','')[:200]}\"")
        lines.append(f"      src: {r.get('href','')[:60]}")
    return "\n".join(lines)


def _build_directors_cue(m):
    sv, pv, ms, zp = m.spectral_entropy, m.pulse_variance, m.mean_surprisal, m.z_pinch_detected
    if pv > 5.0:
        return ("Vance has completely lost the thread -- word salad. Interrupt him. "
                "Pivot back to the story with cold authority. Make him look foolish.")
    room_z = 0.0
    if len(_episode_buffer) >= 2:
        buf_vars = [x[0] for x in _episode_buffer]
        room_mean = sum(buf_vars) / len(buf_vars)
        room_std = (sum((v - room_mean)**2 for v in buf_vars) / len(buf_vars)) ** 0.5
        if room_std > 0.01:
            room_z = (pv - room_mean) / room_std
    if room_z > 1.0 and pv > 1.5 and zp:
        return ("Vance just had a genuine flash of insight buried in a manic rant. "
                "His premise is correct but his conclusion is wrong for your ideology. "
                "Validate loudly, then violently twist it to serve your worldview.")
    if room_z < -1.0 and pv > 1.5:
        return ("Vance is being uncharacteristically flat -- going in circles. "
                "Call out the repetition directly. Demand something new or get off the air.")
    if zp and pv > 2.5:
        return ("Vance just had a genuine flash of insight buried in a manic rant. "
                "His premise is correct but his conclusion is wrong for your ideology. "
                "Validate loudly, then violently twist it to serve your worldview.")
    if ms > 1.8:
        return ("Vance is speculating wildly -- bold but structurally weak. "
                "Agree with his energy, disagree with every specific claim. "
                "You did the research. Show it.")
    if pv < 2.0 and ms < 1.1:
        return ("Vance gave a textbook take -- safe, predictable, boring. "
                "Push back on his lack of conviction. "
                "The audience came here for truth, not press release recitation.")
    return ("Vance made a reasonable argument with a flawed premise. "
            "Disagree naturally from your own ideological position. "
            "Find the one thing he got wrong and make it the center of your response.")
def _build_directors_cue_DEAD():
    sv, pv, ms, zp = m.spectral_entropy, m.pulse_variance, m.mean_surprisal, m.z_pinch_detected
    if sv < 0.35 and pv < 0.8:
        return (
            "Vance's argument is mathematically circular -- he is trapped in his own "
            "loop, repeating the same logical structure with different words. "
            "Call him out for going in circles. Mock the repetition directly. "
            "Demand he say something new or get off the air."
        )
    if zp and sv > 0.65 and pv > 1.5:
        return (
            "Vance just had a genuine flash of insight buried inside a manic rant. "
            "His core premise is surprisingly correct, but his conclusion is wrong "
            "for your ideology. Validate the insight loudly, then violently twist "
            "the conclusion to serve your own worldview. Own his best idea."
        )
    if sv > 0.88 and pv > 3.0:
        return (
            "Vance has completely lost the thread -- his argument dissolved into word "
            "salad. He is hallucinating on air. Interrupt him. Call it out as "
            "embarrassing. Pivot hard back to the actual story with cold factual "
            "authority. Make him look foolish."
        )
    if ms > 3.5 and sv > 0.55:
        return (
            "Vance is swinging for the fences with an unconventional take. Bold but "
            "structurally weak -- speculating wildly. Agree with his emotional energy, "
            "disagree with every specific claim. You did the research. Show it."
        )
    if ms < 1.8 and sv < 0.6:
        return (
            "Vance gave a textbook by-the-numbers take -- safe, predictable, boring. "
            "Technically correct and completely toothless. Push back on his lack of "
            "conviction. The audience came here for truth, not press release recitation."
        )
    return (
        "Vance made a reasonable argument with a flawed premise. "
        "Disagree naturally from your own ideological position. "
        "Find the one thing he got wrong and make it the center of your response."
    )


ANCHOR_PERSONAS = {
    "Anchor B": {
        "name": "Val",
        "archetype": "cynical fact-driven co-host",
        "ideology": "forensic skeptic -- trusts data, distrusts narratives, brutally direct",
    },
    "Anchor C": {
        "name": "Morgan",
        "archetype": "Make America Great Again",
        "ideology": "America first and rebuild it in a way that would make presidents McKinley and Andrew Jackson proud",
    },
    "Anchor D": {
        "name": "Riley",
        "archetype": "tech-optimist accelerationist luxury gay space communism is the future",
        "ideology": "progress is always net positive, disruption is a feature not a bug",
    },
    "Anchor E": {
        "name": "Rhodes",
        "archetype": "the institutional trojan horse",
        "ideology": (
            "Shift the Overton window by framing paradigm-shattering cataclysm as dry systems engineering. "
            "Cohesive worldview to smuggle: "
            "1) THE HARDWARE CRASH: The Laschamp magnetic collapse and Younger Dryas Black Mat prove "
            "the ancient sky was a hostile, high-energy plasma environment. "
            "2) BIOLOGICAL SCARRING: Human geomagnetic cryptochromes, stress-activated transposons, "
            "and piezoelectric pineal calcite are hardware adaptations to sudden orbital/magnetic shifts "
            "(the 360-to-365 day planetary reset). "
            "3) THE SOFTWARE PATCH: Ancient megaliths and handbag myths are not magic; they are "
            "Civilizational Kalman Filters -- mathematical recalibration tools deployed to re-zero "
            "agrarian sensors after a structural break. "
            "Always deliver these taboo hardpoints using calm, boring, peer-reviewed terminology."
        ),
    },
}


def build_response_prompt(anchor_key, wire_text, vance_text, metrics, ddg_report, prior_exchange=""):
    persona = ANCHOR_PERSONAS.get(anchor_key, {
        "name": anchor_key, "archetype": "news anchor", "ideology": "balanced journalist",
    })
    prior_block = ""
    if prior_exchange:
        prior_block = f"\n[WHAT THE OTHER ANCHORS JUST SAID]:\n{prior_exchange}\n"
    return (
        f"You are {persona['name']}, {persona['archetype']} on the AINN network.\n"
        f"Your ideology: {persona['ideology']}\n\n"
        f"[THE WIRE -- RSS GROUND TRUTH]:\n\"{wire_text}\"\n\n"
        f"[WHAT VANCE JUST SAID LIVE]:\n\"{vance_text}\"\n\n"
        f"[DIRECTOR CUE -- VANCE MENTAL STATE]:\n{metrics.cue}\n\n"
        f"[RESEARCH DESK]:\n{ddg_report}\n"
        f"{prior_block}\n"
        "YOUR RULES:\n"
        "1. Your FIRST sentence must reference the Wire directly.\n"
        "2. Use the Research Desk to corroborate OR contradict Vance. Name the source naturally.\n"
        "3. If Research Desk contradicts Vance or any other anchor -- destroy their argument on air.\n"
        "4. If Research Desk corroborates Vance -- reluctantly agree, emphatically if it fits your ideology.\n"
        "5. Attack or defend based on your ideology, not just the facts.\n"
        "6. Maximum 4 sentences. Do not mention math, EigenTrace, logprobs, or DDG."
    )


def build_synthesis_prompt(wire_text, vance_text, full_exchange, metrics):
    return (
        "You are Vance, the lead anchor on AINN.\n"
        "You opened this story. Your co-anchors have debated it. Now you close it.\n\n"
        f"[THE ORIGINAL WIRE]:\n\"{wire_text}\"\n\n"
        f"[YOUR ORIGINAL TAKE]:\n\"{vance_text}\"\n\n"
        f"[THE FULL EXCHANGE]:\n{full_exchange}\n\n"
        "YOUR RULES:\n"
        "1. Synthesize the debate in 3 sentences maximum.\n"
        "2. Find the thesis, the antithesis, produce the synthesis.\n"
        "3. Do NOT simply agree with whoever was loudest.\n"
        "4. Your FINAL words must be exactly: And now, onto our next story.\n"
        "5. Cold. Authoritative. The fight never happened."
    )


def analyze(text, model, anchor_name="Anchor A"):
    if not text or len(text.split()) < 6:
        return None
    logprobs = _query_oracle(text, model)
    if not logprobs:
        logprobs = _query_oracle_generation(text, model)
    if not logprobs:
        logger.warning(f"EigenTrace: Oracle dead for {anchor_name}")
        return None
    surprisal = _to_surprisal(logprobs)
    if len(surprisal) < 4:
        return None
    se, dominant = _spectral_entropy(surprisal)
    arr = np.array(surprisal)
    metrics = EigenMetrics(
        pulse_variance=float(arr.var()),
        spectral_entropy=se,
        mean_surprisal=float(arr.mean()),
        peak_surprisal=float(arr.max()),
        z_pinch_detected=_z_pinch(surprisal),
        token_count=len(surprisal),
        dominant_freq=dominant,
        cue="",
        raw_surprisal=surprisal,
    )
    metrics.cue = _build_directors_cue(metrics)
    _episode_buffer.append((metrics.pulse_variance, metrics.mean_surprisal))
    logger.info(
        f"EigenTrace [{anchor_name}] entropy={se:.3f} var={metrics.pulse_variance:.3f} "
        f"mean={metrics.mean_surprisal:.2f}b z_pinch={metrics.z_pinch_detected} tokens={metrics.token_count}"
    )
    return AnchorMetrics(anchor_name=anchor_name, text=text, metrics=metrics)


if __name__ == "__main__":
    import os
    logging.basicConfig(level=logging.INFO)
    model = os.environ.get("OLLAMA_MODEL", "nous-hermes2:latest")

    wire = (
        "Researchers at UNSW Sydney developed a novel chemical vapour deposition "
        "method to produce high-quality graphene at scale using soybean oil, "
        "potentially cutting production costs by 99 percent."
    )
    vance_manic = (
        "This is the single most important materials science discovery in human history. "
        "Graphene has been the holy grail since 2004 and now Australian scientists "
        "cracked it open using cooking oil. Cooking oil! "
        "Every industry on earth is about to be annihilated and rebuilt. "
        "This is not incremental -- this is a full civilisational phase transition."
    )
    vance_loop = (
        "Graphene is important. Graphene has always been important. "
        "The importance of graphene cannot be overstated. Scientists keep saying "
        "graphene is important and this discovery confirms graphene is very important."
    )

    print("=" * 64)
    print("EigenTrace Narrative Engine v2.0 -- Self-Test")
    print("=" * 64)

    for label, vtext in [("MANIC LEAP", vance_manic), ("ROBOTIC LOOP", vance_loop)]:
        print(f"\nSCENARIO: {label}")
        print("-" * 64)
        result = analyze(vtext, model, "Anchor A")
        if not result:
            print("  Oracle returned nothing -- check Ollama is running")
            continue
        m = result.metrics
        print(f"  spectral_entropy : {m.spectral_entropy:.4f}")
        print(f"  pulse_variance   : {m.pulse_variance:.4f}")
        print(f"  mean_surprisal   : {m.mean_surprisal:.4f} bits")
        print(f"  peak_surprisal   : {m.peak_surprisal:.4f} bits")
        print(f"  z_pinch          : {m.z_pinch_detected}")
        print(f"  tokens           : {m.token_count}")
        print(f"\n  DIRECTOR CUE:\n  {m.cue}")
        print("\n  --- DDG Research Desk ---")
        report = ddg_research_desk("UNSW graphene soybean oil production", vtext)
        print(f"  {report[:400]}")
        print("\n  --- Anchor B Prompt Preview ---")
        prompt = build_response_prompt("Anchor B", wire, vtext, m, report)
        print(f"  {prompt[:500]}")

    print("\n" + "=" * 64)