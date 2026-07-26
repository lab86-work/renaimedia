from __future__ import annotations

from pathlib import Path
from typing import Any

from guessit import guessit
from PTN import parse as ptn_parse


def local_identify(folder_path: Path) -> dict[str, Any] | None:
    """Try to identify a folder using local parsers (guessit + PTN).

    Returns a dict like the AI response, or None if unidentifiable.
    """
    folder_name = folder_path.name
    guessit_result = _try_guessit(folder_name)
    if guessit_result is None:
        return None

    ptn_result = _try_ptn(folder_name)

    title = guessit_result["title"]
    media_type = guessit_result["type"]
    season = guessit_result.get("season")
    year = guessit_result.get("year")

    ptn_title = ptn_result.get("title") if ptn_result else None
    ptn_season = ptn_result.get("season") if ptn_result else None
    ptn_year = ptn_result.get("year") if ptn_result else None

    titles_match = ptn_title is not None and _normalize(ptn_title) == _normalize(title)

    if ptn_result and titles_match:
        if (media_type == "episode" and ptn_season == season) or (
            media_type == "movie" and ptn_year == year
        ):
            confidence = 90
        else:
            confidence = 75
    elif ptn_result and not titles_match:
        confidence = 45
    else:
        confidence = 70

    if media_type == "episode":
        return {
            "type": "show",
            "title": title,
            "season": season,
            "year": None,
            "confidence": confidence,
            "_source": "guessit+ptn",
        }
    if media_type == "movie":
        return {
            "type": "movie",
            "title": title,
            "season": None,
            "year": year,
            "confidence": confidence,
            "_source": "guessit+ptn",
        }
    return None


def _try_guessit(name: str) -> dict[str, Any] | None:
    try:
        result = guessit(name)
    except Exception:
        return None

    title = result.get("title")
    if not title:
        return None

    media_type = result.get("type") or "episode"
    season = result.get("season")
    year = result.get("year")

    if isinstance(season, list):
        season = season[0] if season else None

    return {
        "type": media_type,
        "title": title,
        "season": int(season) if season is not None else None,
        "year": int(year) if year is not None else None,
    }


def _try_ptn(name: str) -> dict[str, Any] | None:
    try:
        result = ptn_parse(name)
    except Exception:
        return None

    title = result.get("title")
    if not title:
        return None

    return {
        "title": title,
        "season": int(result["season"]) if result.get("season") else None,
        "year": int(result["year"]) if result.get("year") else None,
    }


def _normalize(s: str) -> str:
    return " ".join(s.lower().split())
