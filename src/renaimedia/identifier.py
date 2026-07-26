from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, cast

import httpx

from renaimedia.cache import get_cached, set_cached
from renaimedia.config import Config

SYSTEM_PROMPT = """\
You are a media identification expert. Given a folder name and its contents
(filenames), identify whether it contains a TV show or a movie.
Return ONLY valid JSON with no other text.

Include a confidence field (0-100 integer) for each identification:
- 80-100: Unique show/movie, well-known, no ambiguity (high confidence)
- 50-79:  Reasonable match but some uncertainty (medium confidence)
- 0-49:   Ambiguous (multiple shows share the name), or very obscure

Note: show titles may be in Spanish, English, or other languages.
Return the standardized international title (usually English), but
use the original language title if that's the primary known name.

For TV shows, return:
{"type": "show", "title": "<name>", "season": <int>, "confidence": <int>}

For movies, return:
{"type": "movie", "title": "<name>", "year": <int_or_null>, "confidence": <int>}

If you cannot determine the content:
{"type": "unknown", "title": null, "season": null, "year": null, "confidence": 0}

Examples:
{"type": "show", "title": "The Wire", "season": 1, "confidence": 95}
{"type": "movie", "title": "Inception", "year": 2010, "confidence": 90}
{"type": "show", "title": "La Casa de Papel", "season": 3, "confidence": 85}
{"type": "show", "title": "Money Heist", "season": 3, "confidence": 85}"""


def identify_folder(folder_path: Path, config: Config, use_cache: bool = True) -> dict[str, Any]:
    folder_name = folder_path.name
    parent_name = folder_path.parent.name if folder_path.parent != folder_path else ""
    items = list(folder_path.iterdir())

    files = sorted(f.name for f in items if f.is_file() and not f.name.startswith("."))
    subdirs = sorted(f.name + "/" for f in items if f.is_dir() and not f.name.startswith("."))

    if not files and not subdirs:
        return {"type": "unknown", "title": None, "season": None, "year": None}

    if use_cache:
        cached = get_cached(folder_path)
        if cached is not None:
            print(f"  AI: {folder_name} [cached]")
            return cached

    content_list = subdirs + files
    content_str = "\n".join(content_list[:60])

    user_prompt = f"Folder: {folder_name}\nParent: {parent_name}\nContents:\n{content_str}"

    print(f"  AI: identifying {folder_name}...", end="", flush=True)
    try:
        response_text, elapsed = _call_openrouter(user_prompt, config)
        print(f" done ({elapsed:.1f}s)")
        result = _parse_response(response_text)
    except Exception as e:
        print(f" error: {e}")
        return {"type": "unknown", "title": None, "season": None, "year": None}

    if use_cache:
        set_cached(folder_path, result)
    return result


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


def identify_flat_folder(
    folder_path: Path, config: Config, use_cache: bool = True
) -> list[dict[str, Any]]:
    files = sorted([f for f in folder_path.iterdir() if f.is_file() and not f.name.startswith(".")])
    if not files:
        return []

    if use_cache:
        cached = get_cached(folder_path)
        if cached is not None:
            print(f"  AI: {folder_path.name} [cached]")
            result = cached.get("_results")
            if isinstance(result, list):
                return result
            return [cached]

    files_str = "\n".join(f.name for f in files[:100])
    folder_name = folder_path.name
    parent_name = folder_path.parent.name if folder_path.parent != folder_path else ""
    user_prompt = (
        f"Folder: {folder_name}\nParent: {parent_name}\nFiles:\n{files_str}\n\n"
        f"NOTE: This folder may contain MULTIPLE shows/movies mixed together. "
        f"Return a JSON ARRAY of objects, one per distinct show/movie found. "
        f"For each object, include the type, title, season/year, confidence, and also a "
        f'"files" array listing which filenames belong to that show/movie.'
    )

    print(f"  AI: identifying {folder_name}...", end="", flush=True)
    try:
        content, elapsed = _call_openrouter(user_prompt, config)
        print(f" done ({elapsed:.1f}s)")
    except Exception as e:
        print(f" error: {e}")
        return []

    try:
        parsed = _parse_response(content)
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
            try:
                remaining_content, remaining_elapsed = _call_openrouter(remaining_prompt, config)
                print(f"  AI: second pass... done ({remaining_elapsed:.1f}s)")
                remaining_parsed = _parse_response(remaining_content)
                if isinstance(remaining_parsed, list):
                    for item in remaining_parsed:
                        item["_source"] = str(folder_path)
                        results.append(item)
                elif remaining_parsed.get("type") != "unknown":
                    remaining_parsed["_source"] = str(folder_path)
                    results.append(remaining_parsed)
            except Exception as e:
                print(f"  AI: second pass error: {e}")

        if use_cache:
            set_cached(folder_path, {"_results": results, "_cached": True})
        return results
    except Exception:
        return []


def _call_openrouter(user_prompt: str, config: Config) -> tuple[str, float]:
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

    start = time.monotonic()
    with httpx.Client(timeout=config.request_timeout) as client:
        response = client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
        )
        if not response.is_success:
            body = response.text[:500]
            raise RuntimeError(f"HTTP {response.status_code}: {body[:200]}")
        elapsed = time.monotonic() - start
        content: str = response.json()["choices"][0]["message"]["content"]
        return content, elapsed


def list_models(config: Config, provider: str | None = None) -> list[str]:
    headers = {
        "Authorization": f"Bearer {config.openrouter_api_key}",
        "Content-Type": "application/json",
    }
    try:
        with httpx.Client(timeout=config.request_timeout) as client:
            response = client.get(
                "https://openrouter.ai/api/v1/models",
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
            all_models: list[str] = []
            filtered: list[str] = []
            for m in data.get("data", []):
                mid = m.get("id", "")
                name = m.get("name", mid)
                line = f"  {mid}  ({name})"
                all_models.append(line)
                if provider and mid.startswith(f"{provider}/"):
                    filtered.append(line)
            if filtered:
                return sorted(filtered)
            if provider:
                return [
                    f"  No models found for provider '{provider}'",
                    f"  Total models available: {len(all_models)}",
                ]
            return sorted(all_models)
    except Exception as e:
        return [f"  Error fetching models: {e}"]


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
