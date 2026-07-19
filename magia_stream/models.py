"""Modèles de domaine pour MagiaStream."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass(slots=True)
class Episode:
    """Représente un épisode unique."""

    series: str
    season: int
    episode: int
    title: Optional[str] = None
    page_url: Optional[str] = None
    stream_url: Optional[str] = None
    raw_url: Optional[str] = None
    resolution: Optional[str] = None
    output_path: Optional[Path] = None
    headers: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class Season:
    """Représente une saison d'une série."""

    series: str
    season: int
    episodes: List[Episode]


@dataclass(slots=True)
class Series:
    """Représente une série complète."""

    name: str
    seasons: List[Season]
    page_url: Optional[str] = None
