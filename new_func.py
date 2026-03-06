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
        se, _dom_freq = _spectral_entropy(surprisal)  # returns (se, dominant_freq)
        has_spike = _z_pinch(surprisal)               # returns bool
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
