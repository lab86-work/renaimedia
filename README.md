# renaimedia

Rename and organize media files using AI identification via OpenRouter.

Scans a folder recursively, identifies TV shows and movies by analyzing folder and file names, then organizes them into `OUTPUT_FOLDER/TV Shows/Show Name/Season N/` and `OUTPUT_FOLDER/Movies/Movie Name (Year)/`.

## Installation

```bash
git clone https://github.com/lab86-work/renaimedia.git
cd renaimedia
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Run from source

If you don't want to install, you can run directly after installing dependencies:

```bash
python -m venv .venv && source .venv/bin/activate
pip install httpx python-dotenv pyyaml
PYTHONPATH=src python -m renaimedia /path/to/media --dry-run
```

Or with pip installed in dev mode (recommended):

```bash
pip install -e .
renaimedia /path/to/media --dry-run
```

## Setup

```bash
cp .env.sample .env
```

Edit `.env` and set your OpenRouter API key:

```
OPENROUTER_API_KEY=sk-or-v1-your-key-here
OPENROUTER_MODEL=openrouter/free
OUTPUT_FOLDER=./output
```

Get an API key at [openrouter.ai/keys](https://openrouter.ai/keys).

## Usage

```bash
renaimedia /path/to/media --dry-run
renaimedia /path/to/media
renaimedia /path/to/media -i --output /media/library
```

### Options

| Option | Description |
|--------|-------------|
| `--output PATH` | Output directory (overrides `OUTPUT_FOLDER` env var) |
| `--dry-run` | Show what would be done without changes |
| `-i`, `--interactive` | Approve or edit each identified title before moving |

### Interactive mode

```
Source: Breaking.Bad.S01
Identified as: [show] Breaking Bad - Season 1
[y] accept  [e] edit  [s] skip  [q] quit
>
```

- **y** — accept and move files
- **e** — edit type, title, season, or year
- **s** — skip
- **q** — quit

## How it works

1. Scans the source folder recursively
2. Groups files by their containing folder for context
3. Sends folder name + file list to OpenRouter AI for identification
4. Parses the structured JSON response (show/movie, title, season, year)
5. Creates `OUTPUT_FOLDER/Show Name/Season N/` and moves files
6. Skips already-organized folders (checks if target output path already exists)

Files are **never deleted or renamed** — only moved into organized folders.
