from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


class ExtractionError(Exception):
    """A clear, user-facing extraction failure. `code` is stable for the UI and tests."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class Limits:
    max_file_bytes: int = 25 * 1024 * 1024
    max_pages: int = 500
    max_slides: int = 500
    max_sheet_cells: int = 200_000
    max_extracted_chars: int = 2_000_000
    zip_max_entries: int = 5000
    zip_max_uncompressed_bytes: int = 300 * 1024 * 1024
    zip_max_ratio: int = 150
    feature_ocr: bool = False

    @classmethod
    def from_settings(cls, s: Any) -> Limits:
        return cls(
            max_file_bytes=s.max_file_bytes,
            max_pages=s.max_pages,
            max_slides=s.max_slides,
            max_sheet_cells=s.max_sheet_cells,
            max_extracted_chars=s.max_extracted_chars_per_file,
            zip_max_entries=s.zip_max_entries,
            zip_max_uncompressed_bytes=s.zip_max_uncompressed_bytes,
            zip_max_ratio=s.zip_max_ratio,
            feature_ocr=s.feature_ocr,
        )


@dataclass
class InjectionFlag:
    line: int
    phrase: str
    snippet: str


@dataclass
class ExtractionResult:
    filename: str
    kind: str
    text: str
    pages: int | None = None
    slides: int | None = None
    sheets: int | None = None
    warnings: list[str] = field(default_factory=list)
    injection_flags: list[InjectionFlag] = field(default_factory=list)

    @property
    def chars(self) -> int:
        return len(self.text)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["chars"] = self.chars
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ExtractionResult:
        flags = [InjectionFlag(**f) for f in d.get("injection_flags", [])]
        return cls(
            filename=d["filename"],
            kind=d["kind"],
            text=d["text"],
            pages=d.get("pages"),
            slides=d.get("slides"),
            sheets=d.get("sheets"),
            warnings=list(d.get("warnings", [])),
            injection_flags=flags,
        )
