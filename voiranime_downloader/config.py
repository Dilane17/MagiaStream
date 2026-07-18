"""Configuration centrale de MagiaStream."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class Config:
    """Contient les valeurs par défaut et les chemins de sortie."""

    BASE_URL: str = "https://voir-anime.to"
    output_dir: Path = field(default_factory=lambda: Path.cwd() / "downloads")
    temp_dir: Path = field(default_factory=lambda: Path.cwd() / ".tmp")
    user_agent: str = (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    )
    timeout_seconds: int = 30
