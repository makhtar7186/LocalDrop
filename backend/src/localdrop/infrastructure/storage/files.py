"""Stockage disque des fichiers reçus (§8.4, §13).

- Fichiers temporaires ``<id>.part`` dans ``<dossier de réception>/.localdrop-tmp`` :
  même volume que la destination, donc publication atomique par renommage.
- Publication sans écrasement (FR-028), chemins confinés au dossier de réception.
- Ne jamais ouvrir ni exécuter un fichier reçu (§12.2-9).
"""

from __future__ import annotations

import contextlib
import hashlib
import logging
import os
import re
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

from localdrop.core.errors import LocalDropError
from localdrop.domain.transfers.filenames import candidate_name

logger = logging.getLogger(__name__)

TEMP_DIR_NAME = ".localdrop-tmp"
_TEMP_ID = re.compile(r"^[0-9a-f]{32}$")
_READ_BLOCK = 1024 * 1024
_MAX_COLLISIONS = 10_000


class StorageError(LocalDropError):
    code = "STORAGE_ERROR"
    status_code = 500


class InsufficientDiskSpaceError(StorageError):
    code = "INSUFFICIENT_DISK_SPACE"
    status_code = 507


class UnsafePathError(StorageError):
    code = "UNSAFE_PATH"
    status_code = 400


class FileStorage:
    def __init__(self, receive_dir: Path, *, free_space_margin: int) -> None:
        self.receive_dir = receive_dir
        self.temp_dir = receive_dir / TEMP_DIR_NAME
        self._margin = free_space_margin

    # ------------------------------------------------------------------ dossiers
    def ensure_directories(self) -> None:
        self.receive_dir.mkdir(parents=True, exist_ok=True)
        created = not self.temp_dir.exists()
        self.temp_dir.mkdir(exist_ok=True)
        if created:
            _hide(self.temp_dir)

    def _confined(self, root: Path, name: str) -> Path:
        root_resolved = root.resolve()
        path = (root_resolved / name).resolve()
        if path.parent != root_resolved:
            raise UnsafePathError("Chemin de fichier refusé")
        return path

    def temp_path(self, transfer_id: str) -> Path:
        if not _TEMP_ID.fullmatch(transfer_id):
            raise UnsafePathError("Identifiant de transfert invalide")
        return self._confined(self.temp_dir, f"{transfer_id}.part")

    # ------------------------------------------------------------------ écriture
    def check_free_space(self, size: int) -> None:
        self.ensure_directories()
        free = shutil.disk_usage(self.temp_dir).free
        if free < size + self._margin:
            raise InsufficientDiskSpaceError(
                "Espace disque insuffisant sur le PC",
                details={"required": size, "available": free},
            )

    def create_temp(self, transfer_id: str) -> Path:
        self.ensure_directories()
        path = self.temp_path(transfer_id)
        with path.open("xb"):
            pass
        return path

    def write_chunk(self, transfer_id: str, offset: int, data: bytes) -> None:
        """Écriture positionnelle durable (idempotente : réécrire un bloc est sans risque)."""
        path = self.temp_path(transfer_id)
        try:
            with path.open("r+b") as fh:
                fh.seek(offset)
                fh.write(data)
                fh.flush()
                os.fsync(fh.fileno())
        except FileNotFoundError as exc:
            raise StorageError("Fichier temporaire introuvable", code="TEMP_FILE_MISSING") from exc
        except OSError as exc:
            if _is_disk_full(exc):
                raise InsufficientDiskSpaceError("Espace disque insuffisant sur le PC") from exc
            raise

    def temp_size(self, transfer_id: str) -> int:
        return self.temp_path(transfer_id).stat().st_size

    def temp_sha256(self, transfer_id: str) -> str:
        digest = hashlib.sha256()
        with self.temp_path(transfer_id).open("rb") as fh:
            while block := fh.read(_READ_BLOCK):
                digest.update(block)
        return digest.hexdigest()

    def temp_modified_at(self, transfer_id: str) -> datetime | None:
        try:
            mtime = self.temp_path(transfer_id).stat().st_mtime
        except OSError:
            return None
        return datetime.fromtimestamp(mtime, tz=UTC)

    def temp_exists(self, transfer_id: str) -> bool:
        return self.temp_path(transfer_id).is_file()

    def list_temp_ids(self) -> list[str]:
        """Identifiants des fichiers temporaires présents (réconciliation au démarrage)."""
        if not self.temp_dir.is_dir():
            return []
        return sorted(p.stem for p in self.temp_dir.glob("*.part") if _TEMP_ID.fullmatch(p.stem))

    def delete_temp(self, transfer_id: str) -> None:
        with contextlib.suppress(FileNotFoundError):
            self.temp_path(transfer_id).unlink()

    # ------------------------------------------------------------------ publication
    def publish(self, transfer_id: str, safe_name: str) -> Path:
        """Déplace le fichier vérifié dans le dossier de réception, sans jamais écraser."""
        source = self.temp_path(transfer_id)
        for attempt in range(_MAX_COLLISIONS):
            target = self._confined(self.receive_dir, candidate_name(safe_name, attempt))
            try:
                _rename_no_replace(source, target)
            except FileExistsError:
                continue
            _mark_from_network(target)
            logger.info("Fichier reçu publié : %s", target.name)
            return target
        raise StorageError("Trop de fichiers portant ce nom", code="NAME_COLLISION")


def _rename_no_replace(source: Path, target: Path) -> None:
    if sys.platform == "win32":
        # Sous Windows, os.rename lève FileExistsError si la cible existe.
        source.rename(target)
    else:  # pragma: no cover - POSIX : rename écrase, link échoue si la cible existe
        os.link(source, target)
        source.unlink()


def _is_disk_full(exc: OSError) -> bool:
    import errno

    return exc.errno == errno.ENOSPC or getattr(exc, "winerror", None) in (39, 112)


def _mark_from_network(path: Path) -> None:
    """Mark-of-the-Web : Windows traite le fichier comme provenant du réseau."""
    if sys.platform != "win32":
        return
    try:
        with open(f"{path}:Zone.Identifier", "w", encoding="ascii") as stream:  # noqa: PTH123
            stream.write("[ZoneTransfer]\r\nZoneId=3\r\n")
    except OSError:
        logger.debug("Zone.Identifier non écrit pour %s", path.name)


def _hide(path: Path) -> None:
    if sys.platform != "win32":
        return
    import ctypes

    file_attribute_hidden = 0x2
    with contextlib.suppress(Exception):
        ctypes.windll.kernel32.SetFileAttributesW(str(path), file_attribute_hidden)
