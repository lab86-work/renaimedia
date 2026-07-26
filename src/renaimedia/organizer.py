from __future__ import annotations

import re
from pathlib import Path

from renaimedia.config import Config

KNOWN_PATTERN = re.compile(
    r"^(?P<title>.+?)\s*[-._]\s*[Ss](?P<season>\d+)",
    re.IGNORECASE,
)

MEDIA_EXTENSIONS = {
    ".mkv",
    ".mp4",
    ".avi",
    ".mov",
    ".wmv",
    ".flv",
    ".m4v",
    ".mpg",
    ".mpeg",
    ".webm",
    ".ts",
    ".m2ts",
    ".vob",
    ".divx",
    ".ogm",
    ".rm",
    ".rmvb",
    ".asf",
    ".iso",
}


def is_media_file(filepath: Path) -> bool:
    return filepath.suffix.lower() in MEDIA_EXTENSIONS


def is_already_organized(folder: Path) -> bool:
    match = KNOWN_PATTERN.search(folder.name)
    if not match:
        return False
    has_media = any(
        is_media_file(f) for f in folder.iterdir() if f.is_file() and not f.name.startswith(".")
    )
    return has_media


def organize(
    source: Path,
    title: str,
    season: int | None,
    year: int | None,
    files: list[Path],
    config: Config,
    media_type: str = "show",
) -> Path:
    safe_title = _safe_name(title)

    if media_type == "show" and season is not None:
        target_dir = config.output_folder / safe_title / f"Season {season}"
    elif media_type == "movie":
        year_suffix = f" ({year})" if year else ""
        target_dir = config.output_folder / f"{safe_title}{year_suffix}"
    else:
        target_dir = config.output_folder / safe_title

    target_dir.mkdir(parents=True, exist_ok=True)

    moved = 0
    for src_file in files:
        dest = target_dir / src_file.name
        if dest.exists():
            continue
        src_file.rename(dest)
        moved += 1

    return target_dir


def _safe_name(name: str) -> str:
    name = name.strip()
    name = name.replace("/", " - ").replace("\\", " - ")
    name = name.replace(":", " -").replace("*", "").replace("?", "")
    name = name.replace('"', "'").replace("<", "").replace(">", "").replace("|", "")
    while "  " in name:
        name = name.replace("  ", " ")
    name = name.rstrip(" .")
    return name
