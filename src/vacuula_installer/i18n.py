"""The fancy qt l18n methods seemed complicated, simple file with all strings instead.

Add a new language by dropping locales/<code>.json next to the
existing catalogs AND adding one entry to LANGUAGES in
constants.py -- no other code changes required.

NOTE: If strings are added, increment strings version!
Higest strings version language file is the one to translate from, keep it english ja?
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from PySide6.QtCore import QObject, Signal

logger = logging.getLogger(__name__)

Catalog = dict[str, str]


class Translator(QObject):
    """Loads ``locales/*.json`` catalogs and serves translated strings.

    Uses some fancy signaling I found that allows language changes live without rebuilding widgets
    """

    languageChanged = Signal(str)

    def __init__(self, locales_dir: Path, default_language: str) -> None:
        super().__init__()
        self._locales_dir = locales_dir
        self._catalogs: dict[str, Catalog] = {}
        self._load_catalogs()

        if default_language not in self._catalogs:
            available = ", ".join(sorted(self._catalogs)) or "<none>"
            raise ValueError(f"Default language {default_language!r} has no catalog in {locales_dir} (found: {available})")
        self._language = default_language

    def _load_catalogs(self) -> None:
        for path in sorted(self._locales_dir.glob("*.json")):
            try:
                with path.open(encoding="utf-8") as fh:
                    self._catalogs[path.stem] = json.load(fh)
            except (OSError, json.JSONDecodeError):
                logger.exception("Failed to load locale catalog %s", path)

    @property
    def language(self) -> str:
        """The currently active language code (e.g. ``"en"``)."""
        return self._language

    def available_languages(self) -> list[str]:
        """Language codes that have a loaded catalog, in file order."""
        return list(self._catalogs)

    def set_language(self, code: str) -> None:
        """Switch the active language and notify listeners, if it changed."""
        if code == self._language or code not in self._catalogs:
            return
        self._language = code
        self.languageChanged.emit(code)

    def tr(self, key: str, **kwargs: object) -> str:  # ty: ignore[invalid-method-override]
        """Look up ``key`` in the active catalog, falling back to English.

        Unknown keys return the key itself so a missing translation is
        obvious in the UI instead of crashing the app.
        """
        catalog = self._catalogs.get(self._language, {})
        fallback = self._catalogs.get("en", {})
        text = catalog.get(key, fallback.get(key, key))
        return text.format(**kwargs) if kwargs else text
