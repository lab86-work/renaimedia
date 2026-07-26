# renaimedia

Rename and organize media files using local parsing (guessit + PTN) and AI identification via OpenRouter.

Scans a folder recursively, identifies TV shows and movies by analyzing folder and file names, then organizes them into `OUTPUT_FOLDER/TV Shows/Show Name/Season N/` and `OUTPUT_FOLDER/Movies/Movie Name (Year)/`.

## Installation

```bash
git clone https://github.com/lab86-work/renaimedia.git
cd renaimedia
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Run from source

```bash
source .venv/bin/activate
pip install -e .
renaimedia /path/to/media --dry-run
```

Or without installing:

```bash
source .venv/bin/activate
pip install httpx python-dotenv pyyaml guessit parse-torrent-name
PYTHONPATH=src python -m renaimedia /path/to/media --dry-run
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

Get an API key at [openrouter.ai/keys](https://openrouter.ai/keys). Skip this if using `--no-ai` (local parse only).

## Usage

```bash
renaimedia /path/to/media --dry-run
renaimedia /path/to/media
renaimedia /path/to/media -i --output /media/library
renaimedia /path/to/media --confidence 80
renaimedia /path/to/media --no-cache
renaimedia /path/to/media --no-local
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--output PATH` | `$OUTPUT_FOLDER` | Output directory |
| `--dry-run` | off | Show what would be done without changes |
| `-i`, `--interactive` | off | Prompt to approve every identification |
| `--confidence N` | `70` | Auto-accept threshold in % (0-100) |
| `--no-cache` | off | Skip AI call cache, always query OpenRouter |
| `--no-local` | off | Skip local parsing (guessit+PTN), always use AI |

### Environment variables (`.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENROUTER_API_KEY` | *(required)* | OpenRouter API key |
| `OPENROUTER_MODEL` | `openrouter/free` | Model to use for AI identification |
| `OUTPUT_FOLDER` | `./output` | Default output directory |
| `REQUEST_TIMEOUT` | `30` | API request timeout in seconds |

## Interactive mode

Single-result review (`-i` or low confidence):

```
  (45%)
  Type    : TV Show
  Title   : Prehistoric Planet
  Season  : 2
  Files   : 8
  mv  /media/Prehistoric.Planet.S02/* -> /output/TV Shows/Prehistoric Planet/Season 2/

  [y] accept  [e] edit  [s] skip  [q] quit
```

Multi-choice (local parse vs AI):

```
  [1] Local (70%)
      Type   : TV Show
      Title  : Breaking Bad
      Season : 1
      -> /output/TV Shows/Breaking Bad/Season 1/

  [2] AI (95%)
      Type   : TV Show
      Title  : Breaking Bad
      Season : 1
      -> /output/TV Shows/Breaking Bad/Season 1/

      mv  /media/Breaking.Bad.S01/* -> ...

  [1/2] pick  [e] edit  [s] skip  [q] quit
```

## How it works

1. **Local parse** — First tries guessit + PTN to extract title, type, season, year from the folder name (free, instant)
2. **Confidence scoring** — Both parsers agree → 90% confidence. Only one works → 70%. Disagree → 45%
3. **Auto-accept** — If confidence ≥ threshold (default 70%) and not in interactive mode, applies automatically
4. **AI fallback** — If local confidence is below threshold, queries OpenRouter for a second opinion
5. **Multi-choice** — When both local and AI results are available, user picks between them
6. **Cache** — AI results are cached in `~/.cache/renaimedia/identifications.json` and reused on subsequent runs

Files are **never deleted or renamed** — only moved into organized folders.

Folder names are sanitized to remove invalid filesystem characters (`/ \ : * ? " < > |`).
