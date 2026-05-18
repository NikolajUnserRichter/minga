"""Storage-Abstraktion für Datei-Anhänge.

Aktuell: Local-FS-Backend, das STORAGE_ROOT aus env nutzt
(Railway: /data/attachments, IONOS-VPS: konfigurierbar via STORAGE_ROOT).

Für späteren S3-Wechsel (IONOS Object Storage): zweite Backend-Klasse
implementieren, gleiche Schnittstelle (save/load/delete), Auswahl per
STORAGE_BACKEND env. Schema bleibt unverändert.
"""
from __future__ import annotations

import os
import shutil
import uuid as uuid_pkg
from pathlib import Path
from typing import BinaryIO


class LocalStorage:
    """Speichert Dateien im lokalen Filesystem unter STORAGE_ROOT.

    storage_key: relativer Pfad ab STORAGE_ROOT, z.B.
        "attachments/supplier/{uuid}/{file-uuid}_filename.pdf"
    """

    def __init__(self, root: str | None = None):
        self.root = Path(root or os.getenv("STORAGE_ROOT", "/data"))
        # Auf Railway/IONOS sollte STORAGE_ROOT auf ein persistentes Volume zeigen.
        # Fallback für lokale Entwicklung: ./data
        try:
            self.root.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            # Falls /data nicht zugreifbar → Fallback ./storage_local
            self.root = Path("./storage_local").resolve()
            self.root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, storage_key: str) -> Path:
        # Schutz vor Path-Traversal: Storage-Keys werden gegen STORAGE_ROOT validiert
        candidate = (self.root / storage_key).resolve()
        root_resolved = self.root.resolve()
        if not str(candidate).startswith(str(root_resolved)):
            raise ValueError(f"Ungültiger storage_key (path traversal): {storage_key}")
        return candidate

    def save(self, file: BinaryIO, entity_type: str, entity_id: str, filename: str) -> tuple[str, int]:
        """Speichert die Datei und gibt (storage_key, size_bytes) zurück."""
        safe_filename = Path(filename).name  # nur Basename — keine Pfadteile
        file_uuid = uuid_pkg.uuid4().hex[:12]
        storage_key = f"attachments/{entity_type}/{entity_id}/{file_uuid}_{safe_filename}"
        target = self._resolve(storage_key)
        target.parent.mkdir(parents=True, exist_ok=True)
        size = 0
        with open(target, "wb") as out:
            while True:
                chunk = file.read(64 * 1024)
                if not chunk:
                    break
                out.write(chunk)
                size += len(chunk)
        return storage_key, size

    def open(self, storage_key: str) -> BinaryIO:
        path = self._resolve(storage_key)
        if not path.is_file():
            raise FileNotFoundError(storage_key)
        return open(path, "rb")

    def delete(self, storage_key: str) -> None:
        try:
            self._resolve(storage_key).unlink(missing_ok=True)
        except FileNotFoundError:
            pass


def get_storage() -> LocalStorage:
    """Storage-Backend nach env. Aktuell nur 'local'.

    Künftig: 'local' | 's3' (IONOS Object Storage / AWS / Cloudflare R2)."""
    backend = os.getenv("STORAGE_BACKEND", "local")
    if backend == "local":
        return LocalStorage()
    raise NotImplementedError(f"Storage-Backend '{backend}' noch nicht implementiert")
