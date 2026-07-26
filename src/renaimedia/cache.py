from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, cast

CACHE_DIR = Path.home() / ".cache" / "renaimedia"
CACHE_FILE = CACHE_DIR / "identifications.json"


def _load_cache() -> dict[str, dict[str, Any]]:
    if not CACHE_FILE.exists():
        return {}
    try:
        with open(CACHE_FILE) as f:
            return cast(dict[str, dict[str, Any]], json.load(f))
    except json.JSONDecodeError, OSError:
        return {}


def _save_cache(cache: dict[str, dict[str, Any]]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2, sort_keys=True)


def _make_key(folder_path: Path) -> str:
    folder_name = folder_path.name
    files = sorted(
        f.name for f in folder_path.iterdir() if f.is_file() and not f.name.startswith(".")
    )
    data = folder_name + "|" + "|".join(files)
    return hashlib.sha256(data.encode()).hexdigest()[:16]


def get_cached(folder_path: Path) -> dict[str, Any] | None:
    key = _make_key(folder_path)
    cache = _load_cache()
    return cache.get(key)


def set_cached(folder_path: Path, result: dict[str, Any]) -> None:
    key = _make_key(folder_path)
    cache = _load_cache()
    cache[key] = result
    _save_cache(cache)
