"""Persistence of read/unread state (read.json)."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path

READ_FILENAME = "read.json"
FORMAT_VERSION = 1

logger = logging.getLogger(__name__)


class ReadStore:
    """Set of read article links, saved to a JSON file on every change."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.load_warning: str | None = None
        self._read: dict[str, str] = {}
        self._load()

    def is_read(self, link: str) -> bool:
        return link in self._read

    def mark_read(self, links: Iterable[str]) -> None:
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        changed = False
        for link in links:
            if link not in self._read:
                self._read[link] = now
                changed = True
        if changed:
            self._save()

    def mark_unread(self, link: str) -> None:
        if self._read.pop(link, None) is not None:
            self._save()

    def _load(self) -> None:
        try:
            text = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return
        except OSError as e:
            logger.error("既読情報を読み込めません: %s (%s)", self.path, e)
            self.load_warning = "既読情報を読み込めませんでした"
            return
        try:
            data = json.loads(text)
            read = data["read"]
            if not isinstance(read, dict) or not all(
                isinstance(k, str) and isinstance(v, str) for k, v in read.items()
            ):
                raise ValueError("invalid 'read' field")
        except (ValueError, KeyError, TypeError):
            self._backup_broken()
            return
        self._read = dict(read)

    def _backup_broken(self) -> None:
        backup = self.path.with_name(self.path.name + ".bak")
        try:
            os.replace(self.path, backup)
        except OSError as e:
            logger.error("壊れた既読情報を退避できません: %s (%s)", self.path, e)
        self.load_warning = "既読情報が壊れていたため初期化しました"

    def _save(self) -> None:
        data = {"version": FORMAT_VERSION, "read": self._read}
        try:
            fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=".read-", suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=1)
                os.replace(tmp, self.path)
            except BaseException:
                os.unlink(tmp)
                raise
        except OSError as e:
            logger.error("既読情報を保存できません: %s (%s)", self.path, e)
