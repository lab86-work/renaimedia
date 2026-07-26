from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import httpx

from renaimedia.config import Config

SYSTEM_PROMPT = """\
You are a media identification expert. Given a folder name and its contents
(filenames), identify whether it contains a TV show or a movie.
Return ONLY valid JSON with no other text.

For TV shows, provide:
- type: "show"
- title: The show name (standardized, e.g. "The Wire", "Breaking Bad")
- season: The season number as an integer

For movies, provide:
- type: "movie"
- title: The movie name (standardized)
- year: The release year as an integer (if discernible, otherwise null)

If you cannot determine the content, return:
{"type": "unknown", "title": null, "season": null, "year": null}

Examples of expected output:
{"type": "show", "title": "The Wire", "season": 1}
{"type": "movie", "title": "Inception", "year": 2010}
{"type": "show", "title": "Game of Thrones", "season": 3}"""


def identify_folder(folder_path: Path, config: Config) -> dict[str, Any]:
    folder_name = folder_path.name
    files = sorted(
        [f.name for f in folder_path.iterdir() if f.is_file() and not f.name.startswith(".")]
    )
    if not files:
        return {"type": "unknown", "title": None, "season": None, "year": None}

    files_str = "\n".join(files[:50])
    user_prompt = f"Folder: {folder_name}\nFiles:\n{files_str}"

    response = _call_openrouter(user_prompt, config)
    return _parse_response(response)


def identify_root_folder(folder_path: Path, config: Config) -> list[dict[str, Any]]:
    subfolders = sorted(
        [f for f in folder_path.iterdir() if f.is_dir() and not f.name.startswith(".")]
    )
    results = []
    for sf in subfolders:
        result = identify_folder(sf, config)
        result["_source"] = str(sf)
        results.append(result)
    return results


def identify_flat_folder(folder_path: Path, config: Config) -> list[dict[str, Any]]:
    files = sorted([f for f in folder_path.iterdir() if f.is_file() and not f.name.startswith(".")])
    if not files:
        return []

    files_str = "\n".join(f.name for f in files[:100])
    folder_name = folder_path.name
    user_prompt = (
        f"Folder: {folder_name}\n"
        f"Files:\n{files_str}\n\n"
        f"NOTE: This folder may contain MULTIPLE shows/movies mixed together. "
        f"Return a JSON ARRAY of objects, one per distinct show/movie found. "
        f"For each object, include the type, title, season/year, and also a "
        f'"files" array listing which filenames belong to that show/movie.'
    )

    response = _call_openrouter(user_prompt, config)

    try:
        parsed = _parse_response(response)
        if isinstance(parsed, list):
            for item in parsed:
                if "_source" not in item:
                    item["_source"] = str(folder_path)
            return parsed
        if parsed.get("type") == "unknown":
            return []
        parsed["_source"] = str(folder_path)
        matched = parsed.get("files", [])
        if not matched:
            return [parsed]
        result_files = []
        remaining = [f for f in files if f.name not in matched]
        for f in files:
            if f.name in matched:
                result_files.append(f.name)
        parsed["files"] = result_files
        results = [parsed]

        if remaining:
            remaining_prompt = (
                f"Folder: {folder_name}\n"
                f"Remaining files (may be another show/movie):\n"
                + "\n".join(f.name for f in remaining[:50])
            )
            remaining_response = _call_openrouter(remaining_prompt, config)
            remaining_parsed = _parse_response(remaining_response)
            if isinstance(remaining_parsed, list):
                for item in remaining_parsed:
                    item["_source"] = str(folder_path)
                    results.append(item)
            elif remaining_parsed.get("type") != "unknown":
                remaining_parsed["_source"] = str(folder_path)
                results.append(remaining_parsed)

        return results
    except ValueError, json.JSONDecodeError:
        return []


def _call_openrouter(user_prompt: str, config: Config) -> str:
    headers = {
        "Authorization": f"Bearer {config.openrouter_api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/lsk242/renaimedia",
        "X-Title": "renaimedia",
    }
    payload = {
        "model": config.openrouter_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.1,
        "max_tokens": 1000,
    }

    with httpx.Client(timeout=config.request_timeout) as client:
        response = client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        content: str = response.json()["choices"][0]["message"]["content"]
        return content


def _parse_response(content: str) -> dict[str, Any]:
    content = content.strip()
    start = content.find("{")
    if start == -1:
        start = content.find("[")
        if start == -1:
            raise ValueError(f"No JSON found in response: {content[:200]}")
        end = content.rfind("]") + 1
    else:
        end = content.rfind("}") + 1
    if end <= 0:
        raise ValueError(f"Could not find JSON end: {content[:200]}")
    json_str = content[start:end]
    return cast(dict[str, Any], json.loads(json_str))
