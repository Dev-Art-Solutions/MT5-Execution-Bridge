from __future__ import annotations

import json
from pathlib import Path


class SymbolMapper:
    """Explicit symbol_raw -> broker symbol mapping. No automatic suffix guessing."""

    def __init__(self, mapping: dict[str, str]) -> None:
        self._mapping = mapping

    @classmethod
    def from_file(cls, path: str) -> SymbolMapper:
        file_path = Path(path)
        if not file_path.exists():
            return cls({})
        data = json.loads(file_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise TypeError(f"Symbol map at {path} must be a JSON object")
        return cls({str(k): str(v) for k, v in data.items()})

    def resolve(self, symbol_raw: str) -> str | None:
        """Return the mapped broker symbol, or None if no explicit mapping exists."""
        return self._mapping.get(symbol_raw)
