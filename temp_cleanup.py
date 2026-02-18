import time
from pathlib import Path
from typing import Iterable

def cleanup_paths(paths: Iterable[str], max_age_seconds: int = 7200, keep_last: int = 50) -> None:
    now = time.time()
    files = []
    for path in paths:
        p = Path(path)
        if not p.exists():
            continue
        for f in p.glob("*"):
            if f.is_file():
                files.append(f)

    files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    keep_set = set(files[:keep_last])

    for f in files:
        if f in keep_set:
            continue
        age = now - f.stat().st_mtime
        if age > max_age_seconds:
            try:
                f.unlink()
            except Exception:
                pass
