from __future__ import annotations

from pathlib import Path

from renaimedia.config import Config

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


def organize(
    source: Path,
    title: str,
    season: int | None,
    year: int | None,
    files: list[Path],
    config: Config,
    media_type: str = "show",
) -> Path:
    safe_title = safe_name(title)

    if media_type == "show" and season is not None:
        target_dir = config.output_folder / "TV Shows" / safe_title / f"Season {season}"
    elif media_type == "movie":
        year_suffix = f" ({year})" if year else ""
        target_dir = config.output_folder / "Movies" / f"{safe_title}{year_suffix}"
    else:
        target_dir = config.output_folder / safe_title

    target_dir.mkdir(parents=True, exist_ok=True)

    moved = 0
    skipped = 0
    for src_file in files:
        dest = target_dir / src_file.name
        if dest.exists():
            skipped += 1
            continue
        print(f"    {src_file}")
        print(f"    -> {dest}")
        src_file.rename(dest)
        moved += 1

    if skipped:
        print(f"    ({skipped} already existed, skipped)")

    if moved == 0 and skipped > 0:
        return target_dir

    return target_dir


def safe_name(name: str) -> str:
    name = name.strip()
    result: list[str] = []
    for ch in name:
        if ch.isalnum() or ch in " .-_":
            result.append(ch)
        elif ch in "/\\":
            result.append(" - ")
        elif ch in ",!?'\"":
            pass
        else:
            result.append(" ")
    name = "".join(result)
    while "  " in name:
        name = name.replace("  ", " ")
    while " - - " in name:
        name = name.replace(" - - ", " - ")
    name = name.rstrip(" .-")
    return name
