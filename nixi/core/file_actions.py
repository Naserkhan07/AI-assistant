"""Shell-free, undoable file actions bounded to the user's home directory."""
from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

from nixi.security.permissions import UndoManager


class FileActionService:
    def __init__(self, undo_manager: UndoManager | None = None, home: str | Path | None = None):
        self.home = Path(home or Path.home()).expanduser().resolve()
        self.undo = undo_manager or UndoManager()

    def _resolve(self, raw: str | Path) -> Path:
        value = Path(raw).expanduser()
        if not value.is_absolute():
            value = self.home / value
        # strict=False permits a new destination but still resolves existing parents.
        resolved = value.resolve(strict=False)
        if resolved != self.home and self.home not in resolved.parents:
            raise ValueError("For safety, file actions are limited to your home directory.")
        return resolved

    def create_file(self, path: str, content: str = "") -> str:
        try:
            target = self._resolve(path)
            if not target.parent.is_dir():
                return f"Parent folder does not exist: {target.parent}"
            with target.open("x", encoding="utf-8", newline="") as handle:
                handle.write(content)
            self.undo.record_create(target)
            if not target.is_file() or target.read_text(encoding="utf-8") != content:
                return "File write could not be verified."
            return f"Created and verified {target}"
        except FileExistsError:
            return f"File already exists; nothing overwritten: {path}"
        except (OSError, ValueError) as exc:
            return f"Could not create file: {exc}"

    def rename_file(self, source: str, new_name: str) -> str:
        try:
            src = self._resolve(source)
            name = Path(new_name).name
            if not name or name in (".", ".."):
                return "Please provide a valid new filename."
            if not src.is_file():
                return f"File not found: {src}"
            dst = self._resolve(src.parent / name)
            if dst.exists():
                return f"Destination already exists; nothing overwritten: {dst}"
            result = self.undo.safe_move(src, dst)
            if not dst.is_file() or src.exists():
                return f"Rename verification failed: {result}"
            return f"Renamed and verified: {src.name} → {dst.name}"
        except (OSError, ValueError) as exc:
            return f"Could not rename file: {exc}"

    def move_file(self, source: str, destination: str) -> str:
        try:
            src = self._resolve(source)
            dest = self._resolve(destination)
            if not src.exists():
                return f"Source not found: {src}"
            dst = dest / src.name if dest.is_dir() else dest
            dst = self._resolve(dst)
            if dst.exists():
                return f"Destination already exists; nothing overwritten: {dst}"
            result = self.undo.safe_move(src, dst)
            if not dst.exists() or src.exists():
                return f"Move verification failed: {result}"
            return f"Moved and verified: {src} → {dst}"
        except (OSError, ValueError) as exc:
            return f"Could not move file: {exc}"

    def trash_file(self, path: str) -> str:
        try:
            target = self._resolve(path)
            if not target.exists():
                return f"File not found: {target}"
            result = self.undo.safe_delete(target)
            if target.exists():
                return f"Delete verification failed: {result}"
            return result
        except (OSError, ValueError) as exc:
            return f"Could not move file to Nixi trash: {exc}"

    def find_files(self, query: str, limit: int = 20) -> list[str]:
        term = query.casefold().strip()
        if not term:
            return []
        found: list[str] = []
        roots = [self.home / name for name in ("Desktop", "Documents", "Downloads", "Pictures")]
        roots = [root for root in roots if root.is_dir()]
        if not roots:
            roots = [self.home]
        skip = {".git", ".venv", "venv", "node_modules", "appdata", "$recycle.bin"}
        for root in roots:
            for current, dirs, files in os.walk(root, topdown=True):
                dirs[:] = [d for d in dirs if d.casefold() not in skip]
                for name in files:
                    if term in name.casefold():
                        found.append(str(Path(current) / name))
                        if len(found) >= max(1, min(int(limit), 100)):
                            return found
        return found
