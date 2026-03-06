path = "/home/remvelchio/agent/eigentrace.py"
with open(path, "r") as f:
    content = f.read()

old = """def compute_trace_metrics(text: str) -> dict:
    """Score a narration text using spectral entropy and z-pinch logic.
    Returns dict with keys: status, spectral_entropy, pulse_variance, pulse_range, reason.
    """
    import math
    try:
        words = text.split()
        if len(words) < 5:
            return {"status": "GIBBERISH", "spectral_entropy": 0.0,
                    "pulse_variance": 0.0, "pulse_range": 0.0,
                    "reason": "too short"}
        # Compute surprisal proxy: normalised word-length entropy
        lengths = [len(w) for w in words]
        mean_l = sum(lengths) / len(lengths)
        surprisal = [abs(l - mean_l) / (mean_l + 1e-9) for l in lengths]
        se = _spectral_entropy(surprisal)
        pinched = _z_pinch(surprisal)
        pv = sum((x - (sum(pinched)/(len(pinched)+1e-9)))**2
                 for x in pinched) / (len(pinched) + 1e-9)
        pr = max(pinched) - min(pinched) if pinched else 0.0
        # Verdict thresholds
        if se < 0.1 or pr < 0.01:
            status, reason = "GIBBERISH", "flat signal"
        elif se > 3.5 or pv > 1.2:
            status, reason = "SLOP", "high entropy / incoherent"
        else:
            status, reason = "PUBLISHABLE", "within normal range"
        return {"status": status, "spectral_entropy": round(se, 6),
                "pulse_variance": round(pv, 6), "pulse_range": round(pr, 6),
                "reason": reason}
    except Exception as exc:
        return {"status": "ARCHIVE", "spectral_entropy": 0.0,
                "pulse_variance": 0.0, "pulse_range": 0.0,
                "reason": str(exc)}"""

new = """def compute_trace_metrics(text: str) -> dict:
    """Score a narration text using spectral entropy and z-pinch logic.
    Returns dict with keys: status, spectral_entropy, pulse_variance, pulse_range, reason.
    """
    try:
        words = text.split()
        if len(words) < 5:
            return {"status": "GIBBERISH", "spectral_entropy": 0.0,
                    "pulse_variance": 0.0, "pulse_range": 0.0,
                    "reason": "too short"}
        # Surprisal proxy: normalised word-length deviation
        lengths = [len(w) for w in words]
        mean_l = sum(lengths) / len(lengths)
        surprisal = [abs(l - mean_l) / (mean_l + 1e-9) for l in lengths]
        se = _spectral_entropy(surprisal)
        # _z_pinch returns bool (spike detector) - compute pulse stats directly
        has_spike = _z_pinch(surprisal)  # bool
        mean_s = sum(surprisal) / len(surprisal)
        pv = sum((x - mean_s) ** 2 for x in surprisal) / len(surprisal)
        pr = max(surprisal) - min(surprisal)
        # Verdict thresholds
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
                "reason": str(exc)}"""

if old in content:
    content = content.replace(old, new, 1)
    with open(path, "w") as f:
        f.write(content)
    print("OK: compute_trace_metrics patched")
else:
    print("FAIL: old block not found, trying line-level patch...")
    # Fallback: replace just the broken _z_pinch usage lines
    old2 = "        pinched = _z_pinch(surprisal)\n        pv = sum((x - (sum(pinched)/(len(pinched)+1e-9)))**2\n                 for x in pinched) / (len(pinched) + 1e-9)\n        pr = max(pinched) - min(pinched) if pinched else 0.0"
    new2 = "        has_spike = _z_pinch(surprisal)  # bool\n        mean_s = sum(surprisal) / len(surprisal)\n        pv = sum((x - mean_s) ** 2 for x in surprisal) / len(surprisal)\n        pr = max(surprisal) - min(surprisal)"
    if old2 in content:
        content = content.replace(old2, new2, 1)
        with open(path, "w") as f:
            f.write(content)
        print("OK: fallback line patch applied")
    else:
        print("FAIL: fallback also not found - manual fix needed")

# Quick smoke test
import subprocess as sp
r = sp.run(["/home/remvelchio/agent/.venv/bin/python3", "-c",
    "import sys; sys.path.insert(0, '/home/remvelchio/agent'); from eigentrace import compute_trace_metrics; print(compute_trace_metrics('The quick brown fox jumps over the lazy dog and reports breaking news tonight'))"],
    capture_output=True, text=True)
print("smoke test:", r.stdout.strip())
print(r.stderr.strip() or "no stderr")