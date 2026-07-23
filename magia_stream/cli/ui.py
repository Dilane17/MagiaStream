"""Module d'interface utilisateur pour la CLI (Rich Console & Formateurs)."""

from __future__ import annotations

import logging
from typing import Any

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text
    HAS_RICH = True
except Exception:
    class FallbackConsole:
        def print(self, *args: Any, **kwargs: Any) -> None:
            print(*args)

    Console = FallbackConsole  # type: ignore
    Panel = None  # type: ignore
    Text = None  # type: ignore
    HAS_RICH = False

console = Console()
logger = logging.getLogger(__name__)


def print_header(title: str = "MagiaStream CLI") -> None:
    """Affiche une bannière d'en-tête élégante."""
    if HAS_RICH and Panel:
        console.print(Panel(f"[bold cyan]{title}[/bold cyan]", expand=False))
    else:
        console.print(f"=== {title} ===")


def print_success(message: str) -> None:
    """Affiche un message de succès."""
    if HAS_RICH:
        console.print(f"[bold green]✔[/bold green] {message}")
    else:
        console.print(f"[OK] {message}")


def print_error(message: str) -> None:
    """Affiche un message d'erreur."""
    if HAS_RICH:
        console.print(f"[bold red]✘[/bold red] {message}")
    else:
        console.print(f"[ERROR] {message}")
