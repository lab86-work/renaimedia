from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


@dataclass
class Config:
    openrouter_api_key: str
    openrouter_model: str = "openrouter/free"
    output_folder: Path = field(default_factory=lambda: Path("./output"))
    request_timeout: int = 30
    provider_order: list[str] | None = None
    allow_fallbacks: bool = True

    @classmethod
    def from_env(cls) -> Config:
        load_dotenv()
        api_key = os.getenv("OPENROUTER_API_KEY", "")
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY environment variable is required")
        order = os.getenv("PROVIDER_ORDER", "")
        return cls(
            openrouter_api_key=api_key,
            openrouter_model=os.getenv("OPENROUTER_MODEL", "openrouter/free"),
            output_folder=Path(os.getenv("OUTPUT_FOLDER", "./output")),
            request_timeout=int(os.getenv("REQUEST_TIMEOUT", "30")),
            provider_order=order.split(",") if order else None,
            allow_fallbacks=os.getenv("ALLOW_FALLBACKS", "true").lower() != "false",
        )
