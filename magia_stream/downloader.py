"""Downloader minimal wrapper around aria2c and ffmpeg for robust HLS streaming.

This module provides an interface to download HLS streams (.m3u8) or direct media files,
parsing manifests with provided headers, tracking segments locally, and utilizing aria2c
and ffmpeg for robust resume functionality and demuxing.
"""

from __future__ import annotations

import hashlib
import logging
import os
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urljoin

try:
    import requests
except ImportError:
    requests = None  # type: ignore

try:
    from rich.logging import RichHandler

    HAS_RICH = True
except ImportError:
    HAS_RICH = False


class Downloader:
    def __init__(self, config: Any = None, aria2c_path: str = "aria2c", extra_opts: str = ""):
        self.config = config
        self.aria2c_path = aria2c_path
        self.extra_opts = extra_opts
        self.aria2c_debug_log = Path.cwd() / "aria2c_debug.log"

        self.logger = logging.getLogger(self.__class__.__name__)
        if not self.logger.hasHandlers():
            if HAS_RICH:
                self.logger.addHandler(RichHandler(rich_tracebacks=True))
                self.logger.setLevel(logging.INFO)
            else:
                handler = logging.StreamHandler()
                formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
                handler.setFormatter(formatter)
                self.logger.addHandler(handler)
                self.logger.setLevel(logging.INFO)

    def download_stream(self, stream_url: str, output_path: str, headers: Optional[dict[str, str]] = None) -> int:
        """Download `stream_url` to `output_path`.

        Returns 0 on success and a non-zero exit code on failure.
        The temporary directory is preserved on error or interruption to allow
        a later resume.
        """
        if headers is None:
            headers = {}

        if not self._check_command(self.aria2c_path, ["--version"]):
            self.logger.error("aria2c non trouvé (commande: %s).", self.aria2c_path)
            return 1

        if not self._check_command("ffmpeg", ["-version"]):
            self.logger.error("ffmpeg non trouvé. Installez ffmpeg.")
            return 1

        if not isinstance(stream_url, str) or ".m3u8" not in stream_url.lower():
            return self._download_direct_mp4(stream_url, output_path, headers)

        temp_dir = self._build_temp_dir(output_path)
        temp_dir.mkdir(parents=True, exist_ok=True)
        self.logger.info("Dossier temporaire créé : %s", temp_dir)

        keep_temp_dir = False
        aria2c_proc: Optional[subprocess.Popen[Any]] = None
        ffmpeg_proc: Optional[subprocess.Popen[Any]] = None

        try:
            seg_urls = self._fetch_and_parse_m3u8(stream_url, headers)
            if not seg_urls:
                keep_temp_dir = True
                self.logger.error("Aucun segment trouvé dans le manifeste.")
                return 1

            self.logger.info("%s segments identifiés.", len(seg_urls))

            input_file_path = temp_dir / "input_segments.txt"
            segment_files: list[str] = []
            missing_segments: list[tuple[str, str]] = []

            for index, seg_url in enumerate(seg_urls, start=1):
                local_name = f"segment_{index:05d}.ts"
                segment_files.append(local_name)

            while True:
                missing_segments = []
                for index, seg_url in enumerate(seg_urls, start=1):
                    local_name = f"segment_{index:05d}.ts"
                    local_path = temp_dir / local_name
                    aria2_tracking_file = temp_dir / f"{local_name}.aria2"

                    if local_path.exists() and not aria2_tracking_file.exists() and local_path.stat().st_size > 0:
                        pass
                    else:
                        missing_segments.append((seg_url, local_name))

                if not missing_segments:
                    self.logger.info("Tous les segments sont déjà téléchargés.")
                    break

                with input_file_path.open("w", encoding="utf-8") as handle:
                    for seg_url, local_name in missing_segments:
                        handle.write(f"{seg_url}\n")
                        handle.write(f"  out={local_name}\n")

                aria2c_cmd = self._build_aria2c_command(input_file_path, temp_dir, headers)
                self.logger.info(
                    "Lancement du téléchargement parallèle des segments (%s manquants)...", len(missing_segments)
                )

                try:
                    from rich.progress import (
                        BarColumn,
                        Progress,
                        SpinnerColumn,
                        TextColumn,
                        TimeElapsedColumn,
                        TimeRemainingColumn,
                    )

                    def count_completed() -> int:
                        c = 0
                        for _, lname in missing_segments:
                            lpath = temp_dir / lname
                            trk = temp_dir / f"{lname}.aria2"
                            if lpath.exists() and not trk.exists() and lpath.stat().st_size > 0:
                                c += 1
                        return c

                    with Progress(
                        SpinnerColumn(),
                        TextColumn("[progress.description]{task.description}"),
                        BarColumn(),
                        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                        TextColumn("({task.completed}/{task.total})"),
                        TimeElapsedColumn(),
                        TimeRemainingColumn(),
                    ) as progress:
                        task_id = progress.add_task("[cyan]Téléchargement des segments...", total=len(missing_segments))

                        def poll_cb() -> None:
                            progress.update(task_id, completed=count_completed())

                        aria2c_proc, aria2c_stderr = self._run_aria2c(
                            aria2c_cmd, self.aria2c_debug_log, poll_callback=poll_cb
                        )
                except ImportError:
                    aria2c_proc, aria2c_stderr = self._run_aria2c(aria2c_cmd, self.aria2c_debug_log)

                if aria2c_proc.returncode != 0:
                    keep_temp_dir = True
                    # Check if user canceled (Ctrl+C often returns 130, or aria2c returns 2/7/etc for aborts, but 130 is universal SIGINT)
                    if aria2c_proc.returncode == 130:
                        self.logger.error("Téléchargement interrompu par l'utilisateur.")
                        return 130

                    error_text = aria2c_stderr.decode("utf-8", errors="ignore") if aria2c_stderr else ""
                    self.logger.warning("aria2c a échoué (code de sortie: %s).", aria2c_proc.returncode)
                    if error_text:
                        self.logger.debug("Détails erreur aria2c: %s", error_text.strip())

                    self.logger.info("Relance automatique du téléchargement dans 5 secondes...")
                    import time

                    time.sleep(5)
                    continue
                else:
                    break

            concat_file_path = temp_dir / "concat_list.txt"
            with concat_file_path.open("w", encoding="utf-8") as handle:
                for segment_file in segment_files:
                    safe_path = str((temp_dir / segment_file).resolve()).replace("'", "'\\''")
                    handle.write(f"file '{safe_path}'\n")

            output_parent = Path(output_path).expanduser().resolve().parent
            output_parent.mkdir(parents=True, exist_ok=True)

            ffmpeg_cmd = [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_file_path),
                "-c",
                "copy",
                output_path,
            ]

            self.logger.info("Fusion des segments via ffmpeg...")
            ffmpeg_proc = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            ffmpeg_stderr = ffmpeg_proc.communicate()[1]
            if ffmpeg_proc.returncode != 0:
                keep_temp_dir = True
                error_text = ffmpeg_stderr.decode("utf-8", errors="ignore") if ffmpeg_stderr else ""
                if error_text:
                    self.logger.error("Erreur ffmpeg: %s", error_text.strip())
                self.logger.error("Erreur ffmpeg (code de sortie: %s).", ffmpeg_proc.returncode)
                return ffmpeg_proc.returncode

            self.logger.info("Succès ! Fichier écrit : %s", output_path)
            keep_temp_dir = False
            return 0

        except KeyboardInterrupt:
            keep_temp_dir = True
            self._terminate_process(aria2c_proc)
            self._terminate_process(ffmpeg_proc)
            self.logger.warning("Téléchargement interrompu par l'utilisateur ; reprise possible depuis %s", temp_dir)
            return 130
        except Exception as exc:
            keep_temp_dir = True
            self._terminate_process(aria2c_proc)
            self._terminate_process(ffmpeg_proc)
            self.logger.error("Erreur pendant le téléchargement HLS: %s", exc)
            return 1
        finally:
            if keep_temp_dir:
                self.logger.info("Répertoire temporaire conservé pour reprise: %s", temp_dir)
            else:
                shutil.rmtree(temp_dir, ignore_errors=True)

    def _fetch_and_parse_m3u8(self, url: str, headers: dict[str, str]) -> list[str]:
        if requests is None:
            import urllib.request

            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as response:
                content = response.read().decode("utf-8", errors="ignore")
        else:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            content = response.text

        lines = [line.strip() for line in content.splitlines() if line.strip()]
        is_master = any(line.startswith("#EXT-X-STREAM-INF") for line in lines)

        if is_master:
            media_playlist_url = None
            expect_url = False
            for line in lines:
                if line.startswith("#EXT-X-STREAM-INF"):
                    expect_url = True
                elif expect_url and not line.startswith("#"):
                    media_playlist_url = urljoin(url, line)
                    break

            if not media_playlist_url:
                for line in lines:
                    if not line.startswith("#") and ".m3u8" in line.lower():
                        media_playlist_url = urljoin(url, line)
                        break

            if media_playlist_url:
                self.logger.info("Manifeste master détecté. Résolution du sous-manifeste: %s", media_playlist_url)
                return self._fetch_and_parse_m3u8(media_playlist_url, headers)
            return []

        segment_urls: list[str] = []
        for line in lines:
            if not line.startswith("#"):
                segment_urls.append(urljoin(url, line))

        return segment_urls

    def _download_direct_mp4(self, url: str, output_path: str, headers: dict[str, str]) -> int:
        output_parent = Path(output_path).expanduser().resolve().parent
        output_parent.mkdir(parents=True, exist_ok=True)
        output_name = Path(output_path).name

        cmd = [
            self.aria2c_path,
            "--continue=true",
            "-c",
            "--allow-overwrite=true",
            "--auto-file-renaming=false",
            "--max-tries=50",
            "--retry-wait=3",
            "-x",
            "4",
            "-s",
            "4",
            "-j",
            "4",
            "--connect-timeout=30",
            "--timeout=60",
            "--lowest-speed-limit=1K",
            "-d",
            str(output_parent),
            "-o",
            output_name,
        ]
        cmd.extend(self._aria2c_header_args(headers))
        if self.extra_opts:
            cmd.extend(shlex.split(self.extra_opts))
        cmd.append(url)

        proc: Optional[subprocess.Popen[Any]] = None
        try:
            proc, stderr_data = self._run_aria2c(cmd, self.aria2c_debug_log)
            if proc.returncode != 0 and stderr_data:
                self.logger.error("Erreur aria2c: %s", stderr_data.decode("utf-8", errors="ignore").strip())
            return proc.returncode
        except KeyboardInterrupt:
            self._terminate_process(proc)
            self.logger.warning("Téléchargement direct interrompu par l'utilisateur.")
            return 130
        except Exception as exc:
            self._terminate_process(proc)
            self.logger.error("Erreur pendant le téléchargement direct: %s", exc)
            return 1

    def _aria2c_header_args(self, headers: dict[str, str]) -> list[str]:
        args = []
        for key, value in headers.items():
            if key.lower() == "user-agent":
                args.extend(["--user-agent", value])
            else:
                args.append(f"--header={key}: {value}")
        return args

    def _build_aria2c_command(self, input_file_path: Path, temp_dir: Path, headers: dict[str, str]) -> list[str]:
        cmd = [
            self.aria2c_path,
            "-i",
            str(input_file_path),
            "--dir",
            str(temp_dir),
            "--continue=true",
            "-c",
            "--allow-overwrite=true",
            "--auto-file-renaming=false",
            "--max-tries=50",
            "--retry-wait=3",
            "-x",
            "4",
            "-s",
            "4",
            "-j",
            "4",
            "--connect-timeout=30",
            "--timeout=60",
            "--lowest-speed-limit=1K",
        ]
        cmd.extend(self._aria2c_header_args(headers))
        if self.extra_opts:
            cmd.extend(shlex.split(self.extra_opts))
        return cmd

    def _check_command(self, command: str, args: list[str]) -> bool:
        try:
            subprocess.run([command, *args], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            return True
        except Exception:
            return False

    def _build_temp_dir(self, output_path: str) -> Path:
        stable_key = hashlib.sha1(os.path.abspath(output_path).encode("utf-8")).hexdigest()[:12]
        return Path(f"/tmp/magiastream_job_{stable_key}")

    def _terminate_process(self, proc: Optional[subprocess.Popen[Any]]) -> None:
        if proc is None:
            return
        try:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except Exception:
                    proc.kill()
                    try:
                        proc.wait(timeout=5)
                    except Exception:
                        pass
        except Exception:
            pass

    def _run_aria2c(
        self, cmd: list[str], debug_log_path: Path, poll_callback: Optional[Any] = None
    ) -> tuple[subprocess.Popen[Any], bytes]:
        debug_log_path.parent.mkdir(parents=True, exist_ok=True)
        with debug_log_path.open("a", encoding="utf-8") as log_handle:
            log_handle.write("\n=== aria2c invocation ===\n")
            log_handle.write("CMD: " + " ".join(cmd) + "\n")
            log_handle.flush()
            proc = subprocess.Popen(
                cmd,
                stdout=log_handle,
                stderr=log_handle,
                text=True,
            )
            if poll_callback:
                import time

                while proc.poll() is None:
                    try:
                        poll_callback()
                    except Exception:
                        pass
                    time.sleep(0.5)
                try:
                    poll_callback()
                except Exception:
                    pass
            else:
                proc.wait()
        try:
            return proc, debug_log_path.read_bytes()
        except Exception:
            return proc, b""
