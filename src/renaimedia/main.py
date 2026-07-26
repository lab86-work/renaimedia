from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from renaimedia.cache import set_cached
from renaimedia.config import Config
from renaimedia.identifier import identify_flat_folder, identify_folder, list_models
from renaimedia.local_parse import local_identify
from renaimedia.organizer import is_media_file, organize, safe_name


def _target_path(
    config: Config, media_type: str, title: str, season: int | None, year: int | None
) -> Path:
    name = safe_name(title)
    if media_type == "show" and season is not None:
        return config.output_folder / "TV Shows" / name / f"Season {season}"
    if media_type == "movie":
        year_suffix = f" ({year})" if isinstance(year, int) else ""
        return config.output_folder / "Movies" / f"{name}{year_suffix}"
    return config.output_folder / name


def _result_to_dict(
    media_type: str, title: str, season: int | None, year: int | None
) -> dict[str, str | int | None]:
    return {"type": media_type, "title": title, "season": season, "year": year}


def _prompt_multi(
    source: Path,
    local: dict[str, Any] | None,
    ai: dict[str, Any] | None,
    target_local: Path | None,
    target_ai: Path | None,
    file_count: int,
    config: Config,
) -> dict[str, str | int | None] | None:
    """Prompt user to choose between local parse and AI result."""
    while True:
        print()
        if local:
            _print_option(1, "Local", local, target_local)
        if ai:
            _print_option(2, "AI", ai, target_ai)
        print(f"      mv  {source}/* -> ...")
        print()
        print("  [1/2] pick  [e] edit  [s] skip  [q] quit")
        choice = input("  > ").strip().lower()

        if choice == "q":
            print("Quitting.")
            sys.exit(0)
        if choice == "s":
            return None
        if choice == "e":
            ref = local or ai or {}
            mt = str(ref.get("type", "show"))
            t = str(ref.get("title", ""))
            s = ref.get("season")
            y = ref.get("year")
            new_type = input(f"  Type (show/movie) [{mt}]: ").strip() or mt
            new_title = input(f"  Title [{t}]: ").strip() or t
            if new_type == "show":
                raw_season = input(f"  Season [{s}]: ").strip()
                if raw_season:
                    try:
                        s = int(raw_season)
                    except ValueError:
                        print(f"  Invalid season: {raw_season}")
                y = None
            elif new_type == "movie":
                raw_year = input(f"  Year [{y}]: ").strip()
                if raw_year:
                    try:
                        y = int(raw_year)
                    except ValueError:
                        print(f"  Invalid year: {raw_year}")
                s = None
            return _result_to_dict(new_type, new_title, s, y)
        if choice in ("1", "2"):
            selected = local if choice == "1" else ai
            if selected:
                stype = str(selected.get("type", "show"))
                stitle = str(selected.get("title", ""))
                sseason = selected.get("season")
                syear = selected.get("year")
                return _result_to_dict(
                    stype,
                    stitle,
                    int(sseason) if sseason is not None else None,
                    int(syear) if syear is not None else None,
                )


def _print_option(num: int, label: str, result: dict[str, Any], target: Path | None) -> None:
    c = _get_confidence(result)
    mt = str(result.get("type", "show"))
    tt = str(result.get("title", "?"))
    sn = result.get("season")
    yr = result.get("year")

    if label:
        print(f"  [{num}] {label} ({c}%)")
    else:
        print(f"  ({c}%)")
    print(f"      Type   : {'TV Show' if mt == 'show' else 'Movie'}")
    print(f"      Title  : {tt}")
    if mt == "show" and sn is not None:
        print(f"      Season : {int(sn)}")
    if mt == "movie" and yr is not None:
        print(f"      Year   : {int(yr)}")
    if target:
        print(f"      -> {target}/")


def _prompt_review(
    source: Path,
    media_type: str,
    title: str,
    season: int | None,
    year: int | None,
    confidence: int,
    target: Path,
    file_count: int,
    config: Config,
) -> dict[str, str | int | None] | None:
    while True:
        print()
        print(f"  [{confidence}%]")
        print(f"  Type    : {'TV Show' if media_type == 'show' else 'Movie'}")
        print(f"  Title   : {title}")
        if media_type == "show":
            print(f"  Season  : {season if season is not None else '?'}")
        else:
            print(f"  Year    : {year if year is not None else '?'}")
        print(f"  Files   : {file_count}")
        print(f"  mv  {source}/* -> {target}/")
        print()
        print("  [y] accept  [e] edit  [s] skip  [q] quit")
        choice = input("  > ").strip().lower()

        if choice == "y":
            return _result_to_dict(media_type, title, season, year)
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
            confidence = 100
            target = _target_path(
                config=config,
                media_type=media_type,
                title=title,
                season=season,
                year=year,
            )
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
        help="Prompt to approve every identification regardless of confidence",
    )
    parser.add_argument(
        "--confidence",
        type=int,
        default=70,
        metavar="N",
        help="Auto-accept threshold in %% (0-100, default: 70). "
        "Lower-confidence matches will prompt for review.",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Skip AI call cache, always query OpenRouter",
    )
    parser.add_argument(
        "--no-local",
        action="store_true",
        help="Skip local parsing (guessit+PTN), always use AI",
    )
    parser.add_argument(
        "--provider",
        type=str,
        default=None,
        metavar="PROVIDER",
        help="OpenRouter provider (openai, anthropic, google, etc.)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        metavar="MODEL",
        help="Model name (combines with --provider as provider/model)",
    )
    parser.add_argument(
        "--list-models",
        nargs="?",
        const="",
        default=None,
        metavar="PROVIDER",
        help="List available OpenRouter models (optionally filter by provider)",
    )
    args = parser.parse_args()

    if args.list_models is not None:
        try:
            config = Config.from_env()
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        provider_filter = args.list_models or None
        print("Available OpenRouter models:")
        for m in list_models(config, provider_filter):
            print(m)
        sys.exit(0)

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
    if args.model:
        if args.provider and "/" not in args.model:
            config.openrouter_model = f"{args.provider}/{args.model}"
        else:
            config.openrouter_model = args.model
    elif args.provider:
        config.openrouter_model = f"{args.provider}/"
    config.output_folder.mkdir(parents=True, exist_ok=True)

    subs = [f for f in source.iterdir() if f.is_dir() and not f.name.startswith(".")]
    files_at_root = [f for f in source.iterdir() if f.is_file() and not f.name.startswith(".")]

    print(f"Source: {source}")
    print(f"Output: {config.output_folder}")
    print(f"Model: {config.openrouter_model}")
    print(f"Subfolders: {len(subs)}, Files at root: {len(files_at_root)}")
    if args.dry_run:
        print("[DRY RUN - no changes will be made]")
    print(f"Confidence threshold: {args.confidence}%")
    if args.no_cache:
        print("[CACHE DISABLED]")
    if args.no_local:
        print("[LOCAL PARSING DISABLED]")
    print()

    use_cache = not args.no_cache
    use_local = not args.no_local
    if subs:
        _process_subfolders(
            subs,
            config,
            args.dry_run,
            args.interactive,
            args.confidence,
            use_cache,
            use_local,
        )

    if files_at_root:
        _process_flat(
            source,
            config,
            args.dry_run,
            args.interactive,
            args.confidence,
            use_cache,
        )


def _process_subfolders(
    subfolders: list[Path],
    config: Config,
    dry_run: bool,
    interactive: bool,
    confidence_threshold: int,
    use_cache: bool,
    use_local: bool,
) -> None:
    for folder in subfolders:
        items = list(folder.iterdir())
        subfiles = [f for f in items if f.is_file() and not f.name.startswith(".")]
        if not subfiles:
            grandkids = [f for f in items if f.is_dir() and not f.name.startswith(".")]
            if grandkids:
                _process_subfolders(
                    grandkids,
                    config,
                    dry_run,
                    interactive,
                    confidence_threshold,
                    use_cache,
                    use_local,
                )
            continue

        media_files = [f for f in subfiles if is_media_file(f)]
        if not media_files:
            continue

        local_result = None
        if use_local:
            local_result = local_identify(folder)
            if local_result:
                lc = _get_confidence(local_result)
                lt = local_result.get("title")
                ls = local_result.get("season")
                ly = local_result.get("year")
                parts = [f"[local] {folder.name} -> {lt} ({lc}%)"]
                if ls is not None:
                    parts.append(f"S{int(ls)}")
                if ly is not None:
                    parts.append(f"({int(ly)})")
                print("  " + " ".join(parts))

        if (
            local_result
            and not interactive
            and _get_confidence(local_result) >= confidence_threshold
        ):
            _apply_result(folder, local_result, media_files, config, dry_run)
            continue

        ai_result = identify_folder(folder, config, use_cache)
        ai_result["_source"] = str(folder)
        ai_ok = ai_result.get("type") != "unknown" and ai_result.get("title")

        if local_result and (interactive or _get_confidence(local_result) < confidence_threshold):
            if ai_ok:
                tl = _target_path(
                    config,
                    str(local_result.get("type", "show")),
                    str(local_result.get("title", "")),
                    int(local_result["season"]) if local_result.get("season") is not None else None,
                    int(local_result["year"]) if local_result.get("year") is not None else None,
                )
                ta = _target_path(
                    config,
                    str(ai_result.get("type", "unknown")),
                    str(ai_result.get("title", "")),
                    int(ai_result["season"]) if ai_result.get("season") is not None else None,
                    int(ai_result["year"]) if ai_result.get("year") is not None else None,
                )
                override = _prompt_multi(
                    folder, local_result, ai_result, tl, ta, len(media_files), config
                )
                if override is None:
                    print(f"  [SKIP] User skipped: {folder}")
                    continue
                _apply_from_override(folder, override, media_files, config, dry_run)
                continue

            _apply_result(folder, local_result, media_files, config, dry_run)
            continue

        if ai_ok:
            _handle_folder_result(
                folder,
                ai_result,
                media_files,
                config,
                dry_run,
                interactive,
                confidence_threshold,
            )
        else:
            print(f"  [SKIP] AI could not identify: {folder}")


def _process_flat(
    folder: Path,
    config: Config,
    dry_run: bool,
    interactive: bool,
    confidence_threshold: int,
    use_cache: bool,
) -> None:
    results = identify_flat_folder(folder, config, use_cache)
    if not results:
        print(f"  [SKIP] Could not identify content in: {folder}")
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
        media_files = [f for f in files if is_media_file(f)]
        _handle_folder_result(
            source,
            result,
            media_files,
            config,
            dry_run,
            interactive,
            confidence_threshold,
        )


def _handle_folder_result(
    source: Path,
    result: dict[str, str | int | list[str] | None],
    media_files: list[Path],
    config: Config,
    dry_run: bool,
    interactive: bool,
    confidence_threshold: int,
) -> None:
    media_type = str(result.get("type", "unknown"))
    title = str(result.get("title", ""))
    season = result.get("season")
    year = result.get("year")
    confidence = _get_confidence(result)

    if media_type == "unknown" or not title:
        print(f"  [SKIP] Could not identify: {source}")
        return

    if not media_files:
        return

    target = _target_path(
        config,
        media_type,
        title,
        int(season) if isinstance(season, int) else None,
        int(year) if isinstance(year, int) else None,
    )

    all_there = all((target / f.name).exists() for f in media_files)
    if target.exists() and all_there:
        print(f"  [SKIP] Already organized: {source}")
        return

    needs_review = interactive or confidence < confidence_threshold
    if needs_review:
        result_override = _prompt_review(
            source,
            media_type,
            title,
            int(season) if isinstance(season, int) else None,
            int(year) if isinstance(year, int) else None,
            confidence,
            target,
            len(media_files),
            config,
        )
        if result_override is None:
            print(f"  [SKIP] User skipped: {source}")
            return
        media_type = str(result_override["type"])
        title = str(result_override["title"])
        season = result_override["season"]
        year = result_override["year"]
        target = _target_path(
            config,
            media_type,
            title,
            int(season) if isinstance(season, int) else None,
            int(year) if isinstance(year, int) else None,
        )
        set_cached(
            source,
            {
                "type": media_type,
                "title": title,
                "season": season,
                "year": year,
                "confidence": confidence,
            },
        )

    _apply_result(
        source,
        _result_to_dict(
            media_type,
            title,
            int(season) if isinstance(season, int) else None,
            int(year) if isinstance(year, int) else None,
        ),
        media_files,
        config,
        dry_run,
    )


def _apply_result(
    source: Path,
    result: dict[str, str | int | None],
    media_files: list[Path],
    config: Config,
    dry_run: bool,
) -> None:
    media_type = str(result.get("type", "show"))
    title = str(result.get("title", ""))
    season = result.get("season")
    year = result.get("year")
    confidence = _get_confidence(result)

    target = _target_path(
        config,
        media_type,
        title,
        int(season) if isinstance(season, int) else None,
        int(year) if isinstance(year, int) else None,
    )

    all_there = all((target / f.name).exists() for f in media_files)
    if target.exists() and all_there:
        print(f"  [SKIP] Already organized: {source}")
        return

    print(f"  [{confidence}%] [{'DRY' if dry_run else 'MOVE'}] {len(media_files)} files")
    print(f"  mv  {source}/*")
    print(f"  ->  {target}/")

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


def _apply_from_override(
    source: Path,
    override: dict[str, str | int | None],
    media_files: list[Path],
    config: Config,
    dry_run: bool,
) -> None:
    _apply_result(source, override, media_files, config, dry_run)


def _get_confidence(result: dict[str, Any] | dict[str, str | int | list[str] | None]) -> int:
    raw = result.get("confidence")
    if isinstance(raw, (int, float)):
        return int(raw)
    return 0
