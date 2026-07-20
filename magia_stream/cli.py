"""Point d'entrée CLI de MagiaStream."""

from __future__ import annotations

import logging
import sys
from typing import List, Optional

try:
    import typer  # type: ignore

    HAS_TYPER = True
except Exception:
    typer = None  # type: ignore
    HAS_TYPER = False

try:
    from rich.console import Console
except Exception:

    class FallbackConsole:  # pragma: no cover - fallback
        def print(self, *args, **kwargs):
            print(*args)

    Console = FallbackConsole  # type: ignore


import os
from pathlib import Path

from magia_stream.config import Config
from magia_stream.downloader import Downloader
from magia_stream.scraper import Scraper
from magia_stream.utils import setup_logging

app = typer.Typer(help="CLI MagiaStream pour orchestrer le téléchargement d'épisodes.") if HAS_TYPER else None
config_app = typer.Typer() if HAS_TYPER else None
if HAS_TYPER:
    app.add_typer(config_app, name="config")  # type: ignore
console = Console()
logger = logging.getLogger(__name__)


def _load_config(config_file: Optional[str]) -> Config:
    if config_file:
        # support for passing a custom .env file path
        from dotenv import load_dotenv

        load_dotenv(config_file)
    return Config.from_env()


def _configure_global(verbose: bool, config_file: Optional[str]) -> Config:
    """Charge la configuration et configure le logging global.

    Utilisé par Typer et par le fallback minimal.
    """

    cfg = _load_config(config_file)
    level = logging.DEBUG if verbose else getattr(logging, cfg.LOG_LEVEL.upper(), logging.INFO)
    setup_logging(level=level, log_file=cfg.TEMP_DIR / "magia.log", json_format=cfg.LOG_JSON)
    return cfg


if HAS_TYPER:

    @app.callback(invoke_without_command=True)  # type: ignore
    def main(
        ctx: typer.Context,
        verbose: bool = typer.Option(False, "--verbose", help="Augmente le niveau de log."),
        config_file: Optional[str] = typer.Option(None, "--config-file", help="Chemin vers un .env personnalisé."),
    ) -> None:
        """Contexte global de l'application. Configure logging et charge la config."""

        cfg = _configure_global(verbose, config_file)
        ctx.obj = cfg


if HAS_TYPER:

    @app.command()  # type: ignore
    def download(
        ctx: typer.Context,
        serie: str = typer.Option(..., "--serie", help="Nom de la série à télécharger."),
        saison: int = typer.Option(1, "--saison", min=1, help="Numéro de saison."),
        episode: Optional[int] = typer.Option(None, "--episode", min=1, help="Numéro d'épisode."),
        all_episodes: bool = typer.Option(False, "--all", help="Télécharge tous les épisodes."),
        range_episodes: Optional[str] = typer.Option(None, "--range", help="Plage d'épisodes, ex: 1-5"),
        resolution: Optional[str] = typer.Option(
            None,
            "--resolution",
            help="Résolution cible, par exemple 720p ou 1080p.",
        ),
        dry_run: bool = typer.Option(False, "--dry-run", help="Ne fait que simuler la résolution de l'épisode."),
        trace: bool = typer.Option(False, "--trace", help="Affiche les URLs visitées et les requêtes captées."),
    ) -> None:
        """Télécharge un épisode ou une saison à partir des paramètres fournis."""

        cfg: Config = ctx.obj or Config.from_env()
        scraper = Scraper(config=cfg)
        downloader = Downloader(aria2c_path=cfg.ARIA2C_PATH, extra_opts=cfg.ARIA2C_OPTS)

        episodes_to_download: List[int] = []

        if all_episodes:
            console.print(f"[cyan]Découverte des épisodes pour {serie} S{saison}...[/cyan]")
            found = scraper.get_episodes_list(serie=serie, saison=saison, trace=trace)
            if not found:
                console.print(f"[red]Aucun épisode trouvé pour la série {serie}.[/red]")
                raise typer.Exit(code=2)
            episodes_to_download = found
            console.print(f"[green]Épisodes trouvés : {found}[/green]")
        elif range_episodes:
            try:
                parts = range_episodes.split("-")
                if len(parts) == 2:
                    start, end = int(parts[0]), int(parts[1])
                    episodes_to_download = list(range(start, end + 1))
                else:
                    episodes_to_download = [int(p.strip()) for p in range_episodes.split(",")]
            except Exception:
                console.print("[red]Format de --range invalide. Utilisez '1-5' ou '1, 2, 3'.[/red]")
                raise typer.Exit(code=2)
        elif episode is not None:
            episodes_to_download = [episode]
        else:
            console.print("[red]Vous devez spécifier --episode, --all, ou --range.[/red]")
            raise typer.Exit(code=2)

        try:
            for ep_num in episodes_to_download:
                console.print(f"\n[bold cyan]Traitement de l'épisode {ep_num}[/bold cyan]")
                try:
                    ep = scraper.search_episode(
                        serie=serie, saison=saison, episode=ep_num, resolution=resolution or "1080p", trace=trace
                    )
                except Exception as exc:
                    console.print(f"[red]Erreur:[/red] impossible de résoudre l'épisode {ep_num}: {exc}")
                    continue

                if not ep or not getattr(ep, "stream_url", None):
                    console.print(f"[red]Aucun flux trouvé pour {serie} S{saison}E{ep_num}.[/red]")
                    continue

                if dry_run:
                    if trace:
                        console.print(
                            f"[yellow]Trace:[/yellow] page_url={ep.page_url} stream_url={ep.stream_url} raw_url={getattr(ep, 'raw_url', None)}"
                        )
                    console.print(f"[yellow]Dry-run:[/yellow] {ep}")
                    continue

                out_dir = Path(cfg.OUTPUT_DIR) / serie
                out_dir.mkdir(parents=True, exist_ok=True)
                out_name = f"S{saison:02d}E{ep_num:02d}.mp4"
                output_path = str(out_dir / out_name)

                ret = downloader.download_stream(ep.stream_url, output_path, headers=ep.headers)  # type: ignore
                if ret != 0:
                    console.print(f"[red]aria2c a échoué (code={ret}) sur l'épisode {ep_num}[/red]")
                    continue

                console.print(f"[green]Téléchargement terminé :[/green] {output_path}")

        except KeyboardInterrupt:
            console.print("\n[yellow]Interruption par l'utilisateur. Arrêt du batch.[/yellow]")
            raise typer.Exit(code=130)
        except Exception as exc:  # pragma: no cover
            logger.exception("Échec du batch")
            raise typer.Exit(code=1) from exc

        console.print("\n[bold green]Processus terminé.[/bold green]")
else:

    def download_fallback(argv: List[str]) -> None:
        """Fallback minimal pour 'download' si `typer` n'est pas installé."""

        import argparse

        parser = argparse.ArgumentParser(prog="magia download")
        parser.add_argument("--serie", required=True)
        parser.add_argument("--saison", type=int, default=1)
        parser.add_argument("--episode", type=int, default=None)
        parser.add_argument("--all", action="store_true")
        parser.add_argument("--range", default=None)
        parser.add_argument("--resolution", default=None)
        args = parser.parse_args(argv)

        cfg = _configure_global(verbose=False, config_file=None)
        scraper = Scraper(config=cfg)
        downloader = Downloader(aria2c_path=cfg.ARIA2C_PATH, extra_opts=cfg.ARIA2C_OPTS)

        episodes_to_download: List[int] = []
        if args.all:
            episodes_to_download = scraper.get_episodes_list(serie=args.serie, saison=args.saison)
            if not episodes_to_download:
                console.print(f"Aucun épisode trouvé pour {args.serie}.")
                sys.exit(2)
        elif args.range:
            parts = args.range.split("-")
            if len(parts) == 2:
                episodes_to_download = list(range(int(parts[0]), int(parts[1]) + 1))
            else:
                episodes_to_download = [int(p.strip()) for p in args.range.split(",")]
        elif args.episode is not None:
            episodes_to_download = [args.episode]
        else:
            console.print("Spécifiez --episode, --all ou --range.")
            sys.exit(2)

        try:
            for ep_num in episodes_to_download:
                try:
                    ep = scraper.search_episode(
                        serie=args.serie, saison=args.saison, episode=ep_num, resolution=args.resolution or "1080p"
                    )
                except Exception as exc:
                    console.print(f"Erreur sur l'épisode {ep_num}: {exc}")
                    continue

                if not ep or not getattr(ep, "stream_url", None):
                    console.print(f"Aucun flux trouvé pour {args.serie} S{args.saison}E{ep_num}")
                    continue

                out_dir = Path(cfg.OUTPUT_DIR) / args.serie
                out_dir.mkdir(parents=True, exist_ok=True)
                out_name = f"S{args.saison:02d}E{ep_num:02d}.mp4"
                output_path = str(out_dir / out_name)

                ret = downloader.download_stream(ep.stream_url, output_path, headers=ep.headers)  # type: ignore
                if ret != 0:
                    console.print(f"aria2c a échoué (code={ret}) sur l'épisode {ep_num}")
                    continue
                console.print(f"Téléchargement terminé : {output_path}")
        except KeyboardInterrupt:
            console.print("\nInterrompu par l'utilisateur.")
            sys.exit(130)
        except Exception:
            logger.exception("Échec du téléchargement")
            sys.exit(1)


if HAS_TYPER:

    @config_app.command(name="show")  # type: ignore
    def config_show(ctx: typer.Context) -> None:
        """Affiche la configuration effective."""

        cfg: Config = ctx.obj or Config.from_env()
        for k, v in cfg.to_dict().items():
            console.print(f"[bold]{k}[/bold]: {v}")

    @app.command(name="list")  # type: ignore
    def list_episodes(
        ctx: typer.Context,
        serie: str = typer.Argument(..., help="Nom de la série."),
        saison: int = typer.Option(1, "--saison", help="Numéro de saison."),
    ) -> None:
        """Liste les épisodes disponibles pour une série et saison données."""
        cfg: Config = ctx.obj or Config.from_env()
        scraper = Scraper(config=cfg)

        console.print(f"[cyan]Recherche des épisodes pour la série '{serie}' (Saison {saison})...[/cyan]")
        episodes = scraper.get_episodes_list(serie=serie, saison=saison)

        if not episodes:
            console.print("[red]Série introuvable ou aucun épisode disponible.[/red]")
            raise typer.Exit(code=1)

        try:
            from rich.table import Table

            table = Table(title=f"Épisodes trouvés pour '{serie}' (Saison {saison})")
            table.add_column("Saison", justify="center", style="cyan")
            table.add_column("Épisode", justify="center", style="magenta")

            for ep in episodes:
                table.add_row(str(saison), str(ep))
            console.print(table)
        except ImportError:
            console.print(f"Épisodes trouvés: {episodes}")

    @app.command(name="search")  # type: ignore
    def search_serie(
        ctx: typer.Context, requete: str = typer.Argument(..., help="Nom de la série à rechercher.")
    ) -> None:
        """Recherche une série sur le site et renvoie l'URL trouvée."""
        cfg: Config = ctx.obj or Config.from_env()
        scraper = Scraper(config=cfg)

        console.print(f"[cyan]Recherche de '{requete}'...[/cyan]")
        url = scraper._search_series_page_url(requete, trace=False)
        if url:
            console.print(f"[green]Série trouvée ![/green] URL : [bold]{url}[/bold]")
            slug = scraper._extract_slug_from_page_url(url)
            if slug:
                console.print(f"Slug officiel à utiliser : [bold cyan]{slug}[/bold cyan]")
        else:
            console.print("[red]Aucune série correspondante trouvée.[/red]")

    @app.command(name="cleanup")  # type: ignore
    def cleanup_tmp(
        ctx: typer.Context,
        force: bool = typer.Option(False, "--force", "-f", help="Supprime sans demander confirmation."),
    ) -> None:
        """Nettoie les dossiers temporaires laissés par MagiaStream."""
        cfg: Config = ctx.obj or Config.from_env()
        import shutil
        import tempfile

        temp_dirs_to_check = [Path(tempfile.gettempdir()), Path(cfg.TEMP_DIR)]
        to_delete = []
        total_size = 0

        for tdir in set(temp_dirs_to_check):
            if not tdir.exists():
                continue
            for item in tdir.iterdir():
                if item.is_dir() and (
                    item.name.startswith("magiastream_job_") or item.name.startswith("magia_scratch_")
                ):
                    to_delete.append(item)
                    for root, dirs, files in os.walk(item):
                        for f in files:
                            fp = os.path.join(root, f)
                            if not os.path.islink(fp):
                                total_size += os.path.getsize(fp)

        if not to_delete:
            console.print("[green]Aucun dossier temporaire MagiaStream trouvé. Le système est propre.[/green]")
            return

        mb_size = total_size / (1024 * 1024)
        console.print(f"[yellow]Trouvé {len(to_delete)} dossier(s) orphelin(s) occupant {mb_size:.2f} Mo.[/yellow]")

        if not force:
            confirm = typer.confirm("Voulez-vous supprimer ces dossiers définitivement ?")
            if not confirm:
                console.print("Nettoyage annulé.")
                raise typer.Exit()

        for d in to_delete:
            try:
                shutil.rmtree(d)
            except Exception as e:
                console.print(f"[red]Erreur lors de la suppression de {d}: {e}[/red]")

        console.print(
            f"[bold green]Nettoyage terminé : {len(to_delete)} dossiers supprimés ({mb_size:.2f} Mo libérés).[/bold green]"
        )

    @app.command(name="batch")  # type: ignore
    def batch_download(
        ctx: typer.Context, file: str = typer.Argument(..., help="Chemin vers le fichier JSON de batch.")
    ) -> None:
        """Exécute une série de téléchargements à partir d'un fichier JSON."""
        import json

        cfg: Config = ctx.obj or Config.from_env()
        scraper = Scraper(config=cfg)
        downloader = Downloader(aria2c_path=cfg.ARIA2C_PATH, extra_opts=cfg.ARIA2C_OPTS)

        file_path = Path(file)
        if not file_path.exists():
            console.print(f"[red]Fichier introuvable : {file}[/red]")
            raise typer.Exit(code=2)

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                jobs = json.load(f)
        except Exception as e:
            console.print(f"[red]Erreur de lecture du JSON : {e}[/red]")
            raise typer.Exit(code=2)

        if not isinstance(jobs, list):
            console.print("[red]Le fichier JSON doit contenir un tableau d'objets (liste).[/red]")
            raise typer.Exit(code=2)

        console.print(f"[bold cyan]Démarrage du batch avec {len(jobs)} tâche(s).[/bold cyan]")

        try:
            for i, job in enumerate(jobs, 1):
                serie = job.get("serie")
                if not serie:
                    console.print(f"[yellow]Tâche {i} ignorée : clé 'serie' manquante.[/yellow]")
                    continue

                saison = job.get("saison", 1)
                resolution = job.get("resolution", "1080p")
                all_episodes = job.get("all", False)
                range_episodes = job.get("range", None)
                episode = job.get("episode", None)

                episodes_to_download: List[int] = []

                console.print(
                    f"\n[bold magenta]=== Traitement de la tâche {i}/{len(jobs)} : {serie} (Saison {saison}) ===[/bold magenta]"
                )

                if all_episodes:
                    console.print(f"[cyan]Découverte des épisodes pour {serie}...[/cyan]")
                    found = scraper.get_episodes_list(serie=serie, saison=saison)
                    if not found:
                        console.print(f"[red]Aucun épisode trouvé pour la série {serie}.[/red]")
                        continue
                    episodes_to_download = found
                elif range_episodes:
                    try:
                        parts = str(range_episodes).split("-")
                        if len(parts) == 2:
                            start, end = int(parts[0]), int(parts[1])
                            episodes_to_download = list(range(start, end + 1))
                        else:
                            episodes_to_download = [int(p.strip()) for p in str(range_episodes).split(",")]
                    except Exception:
                        console.print(f"[red]Format de range invalide pour {serie}.[/red]")
                        continue
                elif episode is not None:
                    episodes_to_download = [int(episode)]
                else:
                    console.print(f"[red]Tâche {i} ignorée : aucune stratégie (episode, all, range) spécifiée.[/red]")
                    continue

                console.print(f"[cyan]Épisodes planifiés : {episodes_to_download}[/cyan]")

                for ep_num in episodes_to_download:
                    console.print(f"[bold cyan] -> Épisode {ep_num}[/bold cyan]")
                    try:
                        ep_obj = scraper.search_episode(
                            serie=serie, saison=saison, episode=ep_num, resolution=resolution
                        )
                        if not ep_obj or not getattr(ep_obj, "stream_url", None):
                            console.print(f"[red]Aucun flux trouvé pour S{saison}E{ep_num}.[/red]")
                            continue

                        out_dir = Path(cfg.OUTPUT_DIR) / serie
                        out_dir.mkdir(parents=True, exist_ok=True)
                        out_name = f"S{saison:02d}E{ep_num:02d}.mp4"
                        output_path = str(out_dir / out_name)

                        ret = downloader.download_stream(ep_obj.stream_url, output_path, headers=ep_obj.headers)  # type: ignore
                        if ret != 0:
                            console.print(f"[red]aria2c a échoué (code={ret}) sur l'épisode {ep_num}[/red]")
                            continue

                        console.print(f"[green]Succès : {output_path}[/green]")
                    except KeyboardInterrupt:
                        raise  # Remonte à l'exception parente pour stopper le batch
                    except Exception as e:
                        console.print(f"[red]Erreur sur {serie} S{saison}E{ep_num} : {e}[/red]")
                        continue

        except KeyboardInterrupt:
            console.print("\n[yellow]Interruption par l'utilisateur (Ctrl+C). Arrêt propre du mode batch.[/yellow]")
            raise typer.Exit(code=130)
        except Exception as e:
            logger.exception("Erreur fatale du batch")
            console.print(f"[red]Arrêt du batch suite à une erreur : {e}[/red]")
            raise typer.Exit(code=1)

        console.print("\n[bold green]Batch terminé ![/bold green]")
else:

    def config_show_fallback() -> None:
        cfg = _configure_global(verbose=False, config_file=None)
        for k, v in cfg.to_dict().items():
            console.print(f"{k}: {v}")


if HAS_TYPER:

    @app.command("interactive")  # type: ignore
    def interactive_command() -> None:
        """Lance l'assistant interactif (Wizard) de MagiaStream."""
        import questionary

        cfg = _configure_global(verbose=False, config_file=None)

        console.print("[bold magenta]Bienvenue dans l'assistant interactif MagiaStream ![/bold magenta]\n")

        serie = questionary.text("Quel animé cherchez-vous ?").ask()
        if not serie:
            return

        with console.status(f"Recherche de '{serie}'...", spinner="dots"):
            scraper = Scraper(config=cfg)
            try:
                scraper.browser_manager.start()  # type: ignore
                results = scraper.search_series_all_results(serie, trace=False)
            finally:
                scraper.browser_manager.stop()  # type: ignore

        if not results:
            console.print("[red]Aucune série trouvée pour cette recherche.[/red]")
            return

        # Select serie
        choices = [f"{r['title']} (Slug: {r['slug']})" for r in results]
        selected_text = questionary.select(
            "Plusieurs résultats trouvés. Sélectionnez la série :", choices=choices
        ).ask()

        if not selected_text:
            return

        selected_index = choices.index(selected_text)
        selected_result = results[selected_index]
        slug = selected_result["slug"]

        # Select action
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
        ep_single = None

        if action.startswith("1"):
            all_eps = True
        elif action.startswith("2"):
            ep_single = questionary.text("Quel numéro d'épisode ?").ask()
            if ep_single:
                ep_single = int(ep_single)
        elif action.startswith("3"):
            ep_range = questionary.text("Quelle plage (ex: 1-12) ?").ask()

        class DummyCtx:
            obj = cfg

        # Préchauffage du cache pour la commande `download`
        cache_key = scraper._series_cache_key(slug)
        scraper.cache.set(cache_key, selected_result["url"], ttl_seconds=7 * 24 * 60 * 60)

        console.print("\n[bold green]Lancement de l'orchestrateur de téléchargement...[/bold green]")

        download(
            ctx=DummyCtx(),  # type: ignore
            serie=slug,
            saison=saison_int,
            episode=ep_single,
            all_episodes=all_eps,
            range_episodes=ep_range,
            resolution=resolution,
            dry_run=False,
            trace=False,
        )


if HAS_TYPER:

    @app.command("update")  # type: ignore
    def update_command() -> None:
        """Met à jour MagiaStream vers la dernière version (pipx ou git)."""
        import shutil
        import subprocess

        console.print("[bold cyan]Recherche de mises à jour pour MagiaStream...[/bold cyan]")

        if shutil.which("pipx"):
            console.print("Environnement pipx détecté. Lancement de pipx upgrade...")
            res = subprocess.run(["pipx", "upgrade", "magiastream"])
            if res.returncode == 0:
                console.print("[bold green]Mise à jour réussie ![/bold green]")
            else:
                console.print("[bold red]Erreur lors de la mise à jour via pipx.[/bold red]")
        else:
            console.print("Mise à jour Git/Pip locale...")
            res = subprocess.run(["git", "pull"])
            if res.returncode == 0:
                subprocess.run([sys.executable, "-m", "pip", "install", "-e", "."])
                console.print("[bold green]Mise à jour locale réussie ![/bold green]")
            else:
                console.print("[bold red]Impossible de mettre à jour. Êtes-vous dans un dépôt Git valide ?[/bold red]")

    @app.command("setup")  # type: ignore
    def setup_command() -> None:
        """Finalise l'installation (Navigateur Playwright & Vérification des dépendances système)."""
        import platform
        import shutil
        import subprocess

        from rich.panel import Panel

        # 1. Vérification des dépendances système (non-Python)
        missing = []
        if not shutil.which("aria2c"):
            missing.append("aria2c")
        if not shutil.which("ffmpeg"):
            missing.append("ffmpeg")

        if missing:
            os_name = platform.system()
            if os_name == "Linux":
                if shutil.which("dnf"):
                    install_cmd = f"sudo dnf install {' '.join(missing)}"
                elif shutil.which("apt"):
                    install_cmd = f"sudo apt install {' '.join(missing)}"
                elif shutil.which("pacman"):
                    install_cmd = f"sudo pacman -S {' '.join(missing)}"
                elif shutil.which("zypper"):
                    install_cmd = f"sudo zypper install {' '.join(missing)}"
                else:
                    install_cmd = f"Installez via votre gestionnaire de paquets : {' '.join(missing)}"
            elif os_name == "Darwin":
                install_cmd = f"brew install {' '.join(missing)}"
            elif os_name == "Windows":
                install_cmd = f"winget install {' '.join(missing)}"
            else:
                install_cmd = f"Installez manuellement : {', '.join(missing)}"

            console.print(
                Panel(
                    f"MagiaStream utilise des moteurs externes pour télécharger à très haute vitesse.\n"
                    f"Veuillez exécuter cette commande dans votre terminal pour les installer :\n\n"
                    f"[bold yellow]{install_cmd}[/bold yellow]",
                    title="[bold red]⚠️ Dépendances système manquantes[/bold red]",
                    expand=False,
                )
            )
        else:
            console.print("[bold green]✔ aria2c et ffmpeg sont bien installés sur votre système.[/bold green]")

        # 2. Installation du navigateur fantôme
        console.print("\n[bold cyan]Installation du navigateur Playwright (Chromium)...[/bold cyan]")
        res = subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"])

        if res.returncode == 0:
            console.print(
                "\n[bold green]✨ MagiaStream est parfaitement configuré et prêt à fonctionner ![/bold green]"
            )
            if platform.system() == "Linux":
                console.print(
                    "\n[dim italic]Note pour Linux : Si vous rencontrez des erreurs liées au navigateur lors de la recherche,\n"
                    "il se peut qu'il manque des dépendances systèmes pour Chromium. Exécutez alors :\n"
                    "sudo python -m playwright install-deps chromium[/dim italic]"
                )
        else:
            console.print("\n[bold red]Erreur lors de l'installation de Playwright.[/bold red]")


def run() -> None:
    """Entrypoint utilisable par la console-script."""
    if HAS_TYPER:
        if len(sys.argv) == 1:
            sys.argv.append("interactive")
        app()  # type: ignore
        return

    # minimal fallback: parse args to support --help, config show, download
    argv = sys.argv[1:]
    if not argv or "--help" in argv or "-h" in argv:
        console.print(
            "MagiaStream (fallback) - fonctionnalités limitées:\n  config show\n  download --serie NAME --episode N [--saison N] [--resolution R]"
        )
        sys.exit(0)

    if argv[0] == "config" and len(argv) > 1 and argv[1] == "show":
        config_show_fallback()
        sys.exit(0)

    if argv[0] == "download":
        download_fallback(argv[1:])
        sys.exit(0)

    console.print(f"Commande inconnue: {' '.join(argv)}")
    sys.exit(2)


if __name__ == "__main__":
    run()
