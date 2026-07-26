from __future__ import annotations

import argparse
import sys
from pathlib import Path

from renaimedia.config import Config
from renaimedia.identifier import (
    identify_flat_folder,
    identify_folder,
)
from renaimedia.organizer import is_media_file, organize


def _prompt_review(
    source_name: str,
    media_type: str,
    title: str,
    season: int | None,
    year: int | None,
) -> dict[str, str | int | None] | None:
    while True:
        print()
        print(f"  Source folder: {source_name}")
        if media_type == "show":
            print("  Type   : TV Show")
            print(f"  Title  : {title}")
            print(f"  Season : {season if season is not None else '?'}")
        else:
            print("  Type   : Movie")
            print(f"  Title  : {title}")
            print(f"  Year   : {year if year is not None else '?'}")
        print("  [y] accept  [e] edit  [s] skip  [q] quit")
        choice = input("  > ").strip().lower()

        if choice == "y":
            return {"type": media_type, "title": title, "season": season, "year": year}
        if choice == "s":
            return None
        if choice == "q":
            print("Quitting.")
            sys.exit(0)
        if choice == "e":
            new_type = input(f"  Type (show/movie) [{media_type}]: ").strip() or media_type
            new_title = input(f"  Title [{title}]: ").strip() or title
            if new_type == "show":
                raw_season = input(f"  Season [{season}]: ").strip()
                if raw_season:
                    try:
                        season = int(raw_season)
                    except ValueError:
                        print(f"  Invalid season: {raw_season}")
                year = None
            elif new_type == "movie":
                raw_year = input(f"  Year [{year}]: ").strip()
                if raw_year:
                    try:
                        year = int(raw_year)
                    except ValueError:
                        print(f"  Invalid year: {raw_year}")
                season = None
            else:
                print(f"  Unknown type: {new_type}")
            media_type = new_type
            title = new_title
        else:
            print("  Invalid choice. Use y/e/s/q")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Organize media files into Show/Season folders using AI identification."
    )
    parser.add_argument(
        "source",
        type=Path,
        help="Source directory containing media files",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output directory (overrides OUTPUT_FOLDER env var)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    parser.add_argument(
        "-i",
        "--interactive",
        action="store_true",
        help="Prompt to approve or edit each identified title before moving",
    )
    args = parser.parse_args()

    source: Path = args.source.resolve()
    if not source.exists():
        print(f"Error: Source directory '{source}' does not exist.", file=sys.stderr)
        sys.exit(1)
    if not source.is_dir():
        print(f"Error: Source '{source}' is not a directory.", file=sys.stderr)
        sys.exit(1)

    try:
        config = Config.from_env()
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if args.output:
        config.output_folder = args.output.resolve()
    config.output_folder.mkdir(parents=True, exist_ok=True)

    subs = [f for f in source.iterdir() if f.is_dir() and not f.name.startswith(".")]
    files_at_root = [f for f in source.iterdir() if f.is_file() and not f.name.startswith(".")]

    print(f"Source: {source}")
    print(f"Output: {config.output_folder}")
    print(f"Subfolders: {len(subs)}, Files at root: {len(files_at_root)}")
    if args.dry_run:
        print("[DRY RUN - no changes will be made]")
    if args.interactive:
        print("[INTERACTIVE - approve each identification]")
    print()

    if subs:
        _process_subfolders(subs, config, args.dry_run, args.interactive)

    if files_at_root:
        _process_flat(source, config, args.dry_run, args.interactive)


def _process_subfolders(
    subfolders: list[Path], config: Config, dry_run: bool, interactive: bool
) -> None:
    for folder in subfolders:
        subfiles = [f for f in folder.iterdir() if f.is_file() and not f.name.startswith(".")]
        if not subfiles:
            grandkids = [f for f in folder.iterdir() if f.is_dir() and not f.name.startswith(".")]
            if grandkids:
                print(f"  [DRILL] Recursing into: {folder.name}")
                _process_subfolders(grandkids, config, dry_run, interactive)
            continue

        result = identify_folder(folder, config)
        _handle_result(folder, result, subfiles, config, dry_run, interactive)


def _process_flat(folder: Path, config: Config, dry_run: bool, interactive: bool) -> None:
    results = identify_flat_folder(folder, config)
    if not results:
        print(f"  [SKIP] Could not identify content in: {folder.name}")
        return

    for result in results:
        matched_files = result.get("files", [])
        files = [
            f
            for f in folder.iterdir()
            if f.is_file()
            and not f.name.startswith(".")
            and (not matched_files or f.name in matched_files)
        ]
        source = Path(result.get("_source", str(folder)))
        _handle_result(source, result, files, config, dry_run, interactive)


def _handle_result(
    source: Path,
    result: dict[str, str | int | list[str] | None],
    files: list[Path],
    config: Config,
    dry_run: bool,
    interactive: bool,
) -> None:
    media_type = str(result.get("type", "unknown"))
    title = str(result.get("title", ""))
    season = result.get("season")
    year = result.get("year")

    if media_type == "unknown" or not title:
        print(f"  [SKIP] Could not identify: {source.name}")
        return

    media_files = [f for f in files if is_media_file(f)]
    if not media_files:
        print(f"  [SKIP] No media files in: {source.name}")
        return

    if interactive:
        result_override = _prompt_review(
            source.name,
            media_type,
            title,
            int(season) if isinstance(season, int) else None,
            int(year) if isinstance(year, int) else None,
        )
        if result_override is None:
            print(f"  [SKIP] User skipped: {source.name}")
            return
        media_type = str(result_override["type"])
        title = str(result_override["title"])
        season = result_override["season"]
        year = result_override["year"]

    if media_type == "show" and isinstance(season, int):
        target = config.output_folder / "TV Shows" / title / f"Season {season}"
        desc = f"{title} - Season {season}"
    elif media_type == "movie":
        year_info = f" ({year})" if isinstance(year, int) else ""
        target = config.output_folder / "Movies" / f"{title}{year_info}"
        desc = f"{title}{year_info}"
    else:
        target = config.output_folder / title
        desc = title

    all_there = all((target / f.name).exists() for f in media_files)
    if target.exists() and all_there:
        print(f"  [SKIP] Already organized: {desc}")
        return

    print(
        f"  [{'DRY' if dry_run else 'MOVE'}] {desc} <- {len(media_files)} files from {source.name}"
    )
    print(f"  -> {target}/")

    if not dry_run:
        organize(
            source,
            title,
            int(season) if isinstance(season, int) else None,
            int(year) if isinstance(year, int) else None,
            media_files,
            config,
            media_type,
        )
