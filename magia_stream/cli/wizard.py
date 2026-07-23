"""Assistant interactif (Wizard) pour MagiaStream CLI."""

from __future__ import annotations

import logging
from typing import Any, Optional
from magia_stream.cli.ui import console

logger = logging.getLogger(__name__)


def run_interactive_wizard(cfg: Any, download_fn: Any) -> None:
    """Execute le wizard interactif avec questionary."""
    try:
        import questionary
    except ImportError:
        console.print("[red]Le module 'questionary' est requis pour le mode interactif.[/red]")
        return

    from magia_stream.scrapers.voiranime import VoirAnimeScraper

    console.print("[bold magenta]Bienvenue dans l'assistant interactif MagiaStream ![/bold magenta]\n")

    serie = questionary.text("Quel animé cherchez-vous ?").ask()
    if not serie:
        return

    with console.status(f"Recherche de '{serie}'...", spinner="dots"):
        scraper = VoirAnimeScraper(config=cfg)
        try:
            if scraper.browser_manager is not None:
                scraper.browser_manager.start()
            results = scraper.search_series_all_results(serie, trace=False)
        finally:
            if scraper.browser_manager is not None:
                scraper.browser_manager.stop()

    if not results:
        console.print("[red]Aucune série trouvée pour cette recherche.[/red]")
        return

    choices = [f"{r['title']} (Slug: {r['slug']})" for r in results]
    selected_text = questionary.select(
        "Plusieurs résultats trouvés. Sélectionnez la série :", choices=choices
    ).ask()

    if not selected_text:
        return

    selected_index = choices.index(selected_text)
    selected_result = results[selected_index]
    slug = selected_result["slug"]

    action_choices = [
        "1. Télécharger toute la saison (--all)",
        "2. Télécharger un épisode spécifique",
        "3. Télécharger une plage d'épisodes (ex: 1-5)",
        "4. Rien, donne-moi juste les infos",
    ]

    action = questionary.select(
        f"Que voulez-vous faire pour '{selected_result['title']}' ?", choices=action_choices
    ).ask()

    if not action or action.startswith("4"):
        console.print(f"\n[green]URL officielle :[/green] {selected_result['url']}")
        console.print(f"[green]Slug à utiliser :[/green] {slug}")
        return

    saison = questionary.text("Numéro de la saison ?", default="1").ask()
    resolution = questionary.select("Quelle résolution ?", choices=["1080p", "720p", "480p"], default="1080p").ask()

    saison_int = int(saison) if saison.isdigit() else 1

    all_eps = False
    ep_range = None
    ep_single: Optional[int] = None

    if action.startswith("1"):
        all_eps = True
    elif action.startswith("2"):
        ep_input = questionary.text("Quel numéro d'épisode ?").ask()
        if ep_input and ep_input.isdigit():
            ep_single = int(ep_input)
    elif action.startswith("3"):
        ep_range = questionary.text("Quelle plage (ex: 1-12) ?").ask()

    class DummyCtx:
        obj = cfg

    cache_key = scraper._series_cache_key(slug)
    scraper.cache.set(cache_key, selected_result["url"], ttl_seconds=7 * 24 * 60 * 60)

    console.print("\n[bold green]Lancement de l'orchestrateur de téléchargement...[/bold green]")

    download_fn(
        ctx=DummyCtx(),
        serie=slug,
        saison=saison_int,
        episode=ep_single,
        all_episodes=all_eps,
        range_episodes=ep_range,
        resolution=resolution,
        dry_run=False,
        trace=False,
    )
